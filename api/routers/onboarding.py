"""Onboarding endpoints: status check and brand brief ingestion."""
from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from capability_router import route
from config import get_settings
from db import get_db
from executor import get_platform_key
from models.document import WorkspaceDocument
from models.provider import ProviderKey
from models.workspace import Audience, Brand, Product, Workspace
from registry import list_all
from routers.runs import _execute_module, _resolve_brief
from routers.workspace import _build_response, get_singleton
from schemas.documents import WorkspaceDocumentOut
from schemas.workspace import WorkspaceResponse

router = APIRouter(tags=["onboarding"])
logger = logging.getLogger("bos.onboarding")

_KNOWN_PROVIDERS = ["openrouter", "gemini", "nvidia", "openai"]


class ProviderCheckResult(BaseModel):
    provider: str
    connected: bool
    mode: str | None  # "byok" | "oauth" | "platform" | None


class ModuleCheckResult(BaseModel):
    module_id: str
    platform: str
    capability: str
    ready: bool
    provider: str | None


class OnboardingStatus(BaseModel):
    workspace_configured: bool
    workspace_name: str | None
    brand_profile_configured: bool
    campaign_brand_kit_approved: bool
    campaign_brand_kit_document_id: str | None = None
    providers: list[ProviderCheckResult]
    modules: list[ModuleCheckResult]
    all_ready: bool
    issues: list[str]


@router.get("/onboarding/status", response_model=OnboardingStatus)
async def onboarding_status(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await get_singleton(db)
    issues: list[str] = []

    workspace_configured = ws is not None
    workspace_name = ws.name if ws else None
    brand_profile_configured = False
    campaign_brand_kit_approved = False
    campaign_brand_kit_document_id = None

    if not workspace_configured:
        issues.append("Workspace not configured — POST /workspace")
    else:
        product_count = len((await db.execute(select(Product).where(Product.workspace_id == ws.id))).scalars().all())
        audience_count = len((await db.execute(select(Audience).where(Audience.workspace_id == ws.id))).scalars().all())
        # Accept brand_json at either workspace level OR on any Brand row (multi-brand setup)
        has_brand_json = bool(ws.brand_json)
        if not has_brand_json and product_count > 0:
            brand_rows = (await db.execute(select(Brand).where(Brand.workspace_id == ws.id))).scalars().all()
            has_brand_json = any(bool(b.brand_json) for b in brand_rows)
        brand_profile_configured = bool(has_brand_json and product_count > 0 and audience_count > 0)
        if not brand_profile_configured:
            issues.append("Brand profile incomplete — import or enter brand, product, and audience context")

        brand_kit = (await db.execute(
            select(WorkspaceDocument)
            .where(
                WorkspaceDocument.workspace_id == ws.id,
                WorkspaceDocument.doc_type == "campaign_brand_kit",
                WorkspaceDocument.status == "approved",
            )
            .order_by(WorkspaceDocument.approved_at.desc().nullslast(), WorkspaceDocument.updated_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if brand_kit:
            campaign_brand_kit_approved = True
            campaign_brand_kit_document_id = str(brand_kit.id)
        else:
            issues.append("Campaign Brand Kit not approved — generate and approve the required onboarding document")

    # Resolve which providers have keys
    stored_providers: dict[str, str] = {}
    if ws:
        rows = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == ws.id,
                ProviderKey.brand_id == None,  # noqa: E711
            )
        )).scalars().all()
        stored_providers = {r.provider: r.auth_mode for r in rows}

    provider_results: list[ProviderCheckResult] = []
    connected: set[str] = set()

    for p in _KNOWN_PROVIDERS:
        if p in stored_providers:
            provider_results.append(ProviderCheckResult(provider=p, connected=True, mode="oauth" if stored_providers[p] == "oauth" else "byok"))
            connected.add(p)
        elif get_platform_key(p, settings):
            provider_results.append(ProviderCheckResult(provider=p, connected=True, mode="platform"))
            connected.add(p)
        else:
            provider_results.append(ProviderCheckResult(provider=p, connected=False, mode=None))
            issues.append(f"{p}: no key configured")

    # Check each registered module against the capability router
    module_results: list[ModuleCheckResult] = []
    for m in list_all():
        if m.get("internal"):
            continue

        module_id = m["id"]
        capability = m.get("capability", "")
        platform = m.get("platform_hint") or module_id.rsplit(".", 1)[-1]

        candidates, _ = await route(db, capability, "balanced")
        routable = [c for c in candidates if c["provider"] in connected]

        if routable:
            module_results.append(ModuleCheckResult(
                module_id=module_id,
                platform=platform,
                capability=capability,
                ready=True,
                provider=routable[0]["provider"],
            ))
        else:
            module_results.append(ModuleCheckResult(
                module_id=module_id,
                platform=platform,
                capability=capability,
                ready=False,
                provider=None,
            ))
            issues.append(f"{module_id}: no connected provider for capability '{capability}'")

    all_ready = (
        workspace_configured
        and brand_profile_configured
        and campaign_brand_kit_approved
        and bool(connected)
        and all(m.ready for m in module_results)
    )

    return OnboardingStatus(
        workspace_configured=workspace_configured,
        workspace_name=workspace_name,
        brand_profile_configured=brand_profile_configured,
        campaign_brand_kit_approved=campaign_brand_kit_approved,
        campaign_brand_kit_document_id=campaign_brand_kit_document_id,
        providers=provider_results,
        modules=module_results,
        all_ready=all_ready,
        issues=issues,
    )


# ── POST /onboarding/ingest ────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    document_text: str
    workspace_name: str | None = None
    brand_id: UUID | None = None


class IngestResponse(BaseModel):
    run_id: str
    brand_name: str
    workspace: WorkspaceResponse
    profile: dict


class BrandKitResponse(BaseModel):
    run_id: str
    document: WorkspaceDocumentOut


def _document_out(doc: WorkspaceDocument) -> WorkspaceDocumentOut:
    return WorkspaceDocumentOut(
        id=doc.id,
        workspace_id=doc.workspace_id,
        brand_id=doc.brand_id,
        doc_type=doc.doc_type,
        title=doc.title,
        content_markdown=doc.content_markdown,
        status=doc.status,
        tags=doc.tags_json if isinstance(doc.tags_json, list) else [],
        metadata=doc.metadata_json if isinstance(doc.metadata_json, dict) else {},
        source_run_id=doc.source_run_id,
        approved_at=doc.approved_at,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _title_from_markdown(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()[:255] or fallback
    return fallback


def _parse_profile(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip().rstrip("`").strip()
    return json.loads(cleaned)


async def _resolve_target_brand(db: AsyncSession, ws: Workspace, brand_id: UUID | None) -> Brand | None:
    if brand_id is None:
        return None
    brand = (await db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


async def _ensure_brand_name_available(db: AsyncSession, ws: Workspace, brand: Brand, name: str) -> None:
    existing = (await db.execute(
        select(Brand).where(Brand.workspace_id == ws.id, Brand.name == name)
    )).scalar_one_or_none()
    if existing and existing.id != brand.id:
        raise HTTPException(status_code=409, detail=f"Brand '{name}' already exists")


async def _brand_brief(db: AsyncSession, ws: Workspace, brand: Brand, extra: dict | None = None) -> dict:
    """Build an execution brief scoped to one Brand, not the workspace default brand."""
    brief = dict(extra or {})
    brief["brand_name"] = brand.name

    bj = brand.brand_json or {}
    for field in ("tone", "voice", "values", "domain", "website_url", "social_handles"):
        if bj.get(field) and not brief.get(field):
            brief[field] = bj[field]
    social_handles = bj.get("social_handles") or {}
    if not brief.get("brand_handle"):
        brief["brand_handle"] = social_handles.get("x") or social_handles.get("twitter") or social_handles.get("instagram")
    if not brief.get("display_url"):
        brief["display_url"] = bj.get("domain") or bj.get("website_url")

    prod = (await db.execute(
        select(Product).where(Product.workspace_id == ws.id, Product.brand_id == brand.id).order_by(Product.created_at.asc()).limit(1)
    )).scalar_one_or_none()
    if prod:
        brief.setdefault("product_name", prod.name)
        if prod.tagline:
            brief.setdefault("tagline", prod.tagline)
        benefits = (prod.benefits_json or {}).get("benefits", [])
        if benefits:
            brief.setdefault("key_benefit", benefits[0])
            brief.setdefault("benefits", benefits)

    aud = (await db.execute(
        select(Audience).where(Audience.workspace_id == ws.id, Audience.brand_id == brand.id).order_by(Audience.created_at.asc()).limit(1)
    )).scalar_one_or_none()
    if aud:
        brief.setdefault("audience", aud.name)
        segment = aud.segment_json or {}
        if segment.get("demographics"):
            brief.setdefault("demographics", segment["demographics"])
        if segment.get("pain_points"):
            brief.setdefault("pain_points", segment["pain_points"])

    return brief


@router.post("/onboarding/ingest", response_model=IngestResponse)
async def ingest_brand_doc(
    body: IngestRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()

    ws = await get_singleton(db)
    if ws is None:
        ws = Workspace(name=body.workspace_name or "My Business")
        db.add(ws)
        await db.flush()
    elif body.workspace_name and body.brand_id is None:
        ws.name = body.workspace_name

    target_brand = await _resolve_target_brand(db, ws, body.brand_id)

    # Important: do not merge existing workspace/brand defaults into extraction.
    # The pasted document is the source of truth; otherwise existing workspace/brand
    # context can bias the model away from the newly imported brand name.
    extraction_brief = {"document_text": body.document_text}
    if body.workspace_name:
        extraction_brief["brand_name"] = body.workspace_name

    run_result = await _execute_module(
        db,
        ws,
        "onboarding.brand_setup",
        extraction_brief,
        settings,
        brand_id=target_brand.id if target_brand else None,
    )

    profile = _parse_profile(run_result.result.content)

    extracted_name = str(profile.get("brand_name") or "").strip()
    brand_name = body.workspace_name or extracted_name or (target_brand.name if target_brand else ws.name)

    profile_json = {
        k: profile[k] for k in ("voice", "tone", "values") if profile.get(k)
    }

    if target_brand:
        await _ensure_brand_name_available(db, ws, target_brand, brand_name)
        target_brand.name = brand_name
        target_brand.brand_json = {**(target_brand.brand_json or {}), **profile_json}
        scoped_brand_id = target_brand.id
    else:
        if extracted_name and not body.workspace_name:
            ws.name = extracted_name
        ws.brand_json = profile_json
        scoped_brand_id = None

    product_filter = Product.brand_id == scoped_brand_id if scoped_brand_id else Product.brand_id == None  # noqa: E711
    await db.execute(delete(Product).where(Product.workspace_id == ws.id, product_filter))
    for p in profile.get("products", []):
        db.add(Product(
            workspace_id=ws.id,
            brand_id=scoped_brand_id,
            name=p.get("name", "Unnamed"),
            tagline=p.get("tagline"),
            benefits_json={"benefits": p.get("benefits", [])},
        ))

    audience_filter = Audience.brand_id == scoped_brand_id if scoped_brand_id else Audience.brand_id == None  # noqa: E711
    await db.execute(delete(Audience).where(Audience.workspace_id == ws.id, audience_filter))
    for a in profile.get("audiences", []):
        db.add(Audience(
            workspace_id=ws.id,
            brand_id=scoped_brand_id,
            name=a.get("name", "Unnamed"),
            segment_json={
                "demographics": a.get("demographics"),
                "pain_points": a.get("pain_points", []),
            },
        ))

    await db.commit()
    await db.refresh(ws)

    return IngestResponse(
        run_id=run_result.run_id,
        brand_name=brand_name,
        workspace=await _build_response(db, ws),
        profile={**profile, "brand_name": brand_name},
    )


# ── POST /onboarding/brand-kit ────────────────────────────────────────────────

class BrandKitRequest(BaseModel):
    additional_context: str | None = None
    brand_id: UUID | None = None


@router.get("/onboarding/brand-kit/latest", response_model=WorkspaceDocumentOut)
async def get_latest_campaign_brand_kit(
    status: str | None = None,
    brand_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Return the latest Campaign Brand Kit document, including full Markdown content."""
    if status is not None and status not in {"draft", "approved", "changes_requested", "archived"}:
        raise HTTPException(status_code=400, detail=f"Invalid document status '{status}'")

    ws = await get_singleton(db)
    if ws is None:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    stmt = select(WorkspaceDocument).where(
        WorkspaceDocument.workspace_id == ws.id,
        WorkspaceDocument.doc_type == "campaign_brand_kit",
    )
    if status:
        stmt = stmt.where(WorkspaceDocument.status == status)
    if brand_id:
        stmt = stmt.where(WorkspaceDocument.brand_id == brand_id)
    else:
        stmt = stmt.where(WorkspaceDocument.brand_id == None)  # noqa: E711

    stmt = stmt.order_by(
        WorkspaceDocument.updated_at.desc(),
        WorkspaceDocument.created_at.desc(),
    ).limit(1)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign Brand Kit not found")
    return _document_out(doc)


@router.post("/onboarding/brand-kit", response_model=BrandKitResponse, status_code=201)
async def generate_campaign_brand_kit(
    body: BrandKitRequest = BrandKitRequest(),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Generate the required Campaign Brand Kit and store it as a draft document."""
    settings = get_settings()
    ws = await get_singleton(db)
    if ws is None:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    target_brand = await _resolve_target_brand(db, ws, body.brand_id)

    brief_override = {}
    if body.additional_context:
        brief_override["document_text"] = body.additional_context

    if target_brand:
        products = (await db.execute(
            select(Product).where(Product.workspace_id == ws.id, Product.brand_id == target_brand.id).limit(1)
        )).scalars().all()
        audiences = (await db.execute(
            select(Audience).where(Audience.workspace_id == ws.id, Audience.brand_id == target_brand.id).limit(1)
        )).scalars().all()
        if not (target_brand.brand_json and products and audiences):
            raise HTTPException(
                status_code=400,
                detail="Brand profile must include brand voice, at least one product, and at least one audience before generating the Campaign Brand Kit",
            )
        brief = await _brand_brief(db, ws, target_brand, brief_override)
        run_brand_id = target_brand.id
        title_fallback = f"{target_brand.name} — Campaign Brand Kit"
    else:
        workspace_response = await _build_response(db, ws)
        workspace_products = [p for p in workspace_response.products if p.brand_id is None]
        workspace_audiences = [a for a in workspace_response.audiences if a.brand_id is None]
        if not (workspace_response.brand and workspace_products and workspace_audiences):
            raise HTTPException(
                status_code=400,
                detail="Brand profile must include brand, at least one product, and at least one audience before generating the Campaign Brand Kit",
            )
        brief = await _resolve_brief(db, ws, brief_override)
        run_brand_id = None
        title_fallback = f"{ws.name} — Campaign Brand Kit"

    run_result = await _execute_module(db, ws, "onboarding.brand_guidelines", brief, settings, brand_id=run_brand_id)
    content = run_result.result.content if run_result.result else ""
    title = _title_from_markdown(content, title_fallback)

    doc = WorkspaceDocument(
        workspace_id=ws.id,
        brand_id=run_brand_id,
        doc_type="campaign_brand_kit",
        title=title,
        content_markdown=content,
        status="draft",
        tags_json=["required_onboarding", "brand", "design", "campaign-readiness"],
        metadata_json={
            "version": "v1.0-draft",
            "generated_by_module": "onboarding.brand_guidelines",
            "required_for_onboarding": True,
            "summary_fields": [
                "color_palette",
                "tone_of_voice",
                "typography_basics",
                "campaign_components",
                "platform_consistency_rules",
            ],
        },
        source_run_id=UUID(run_result.run_id),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return BrandKitResponse(run_id=run_result.run_id, document=_document_out(doc))
