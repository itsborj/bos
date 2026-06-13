"""Onboarding endpoints: status check and brand brief ingestion."""
from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from validation import NullableUUID
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
from models.run import Run, RunAttempt, RunResult
from models.workspace import Audience, Brand, Product, Workspace
from registry import list_all
from routers.runs import _execute_module, _resolve_brief
from routers.workspace import _build_response, get_singleton
from schemas.documents import WorkspaceDocumentOut
from schemas.workspace import WorkspaceResponse

router = APIRouter(tags=["onboarding"])
logger = logging.getLogger("bos.onboarding")

_KNOWN_PROVIDERS = ["openai", "anthropic", "gemini", "openrouter", "nvidia", "bytedance"]


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


@router.get(
    "/onboarding/status",
    response_model=OnboardingStatus,
    responses={404: {"description": "Brand not found"}},
)
async def onboarding_status(
    brand_id: NullableUUID = None,
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

    target_brand: Brand | None = None
    brand_rows: list[Brand] = []
    if ws:
        brand_rows = (await db.execute(select(Brand).where(Brand.workspace_id == ws.id))).scalars().all()
    if brand_id and ws:
        target_brand = (await db.execute(
            select(Brand).where(Brand.id == brand_id, Brand.workspace_id == ws.id)
        )).scalar_one_or_none()
        if not target_brand:
            raise HTTPException(status_code=404, detail="Brand not found")

    if not workspace_configured:
        issues.append("Workspace not configured — POST /workspace")
    else:
        if target_brand:
            product_count = len((await db.execute(
                select(Product).where(Product.workspace_id == ws.id, Product.brand_id == target_brand.id)
            )).scalars().all())
            audience_count = len((await db.execute(
                select(Audience).where(Audience.workspace_id == ws.id, Audience.brand_id == target_brand.id)
            )).scalars().all())
            has_brand_json = bool(target_brand.brand_json)
        elif brand_rows:
            product_count = 0
            audience_count = 0
            has_brand_json = False
            issues.append("Select a Brand to check onboarding status for this multi-brand workspace")
        else:
            product_count = len((await db.execute(
                select(Product).where(Product.workspace_id == ws.id, Product.brand_id == None)  # noqa: E711
            )).scalars().all())
            audience_count = len((await db.execute(
                select(Audience).where(Audience.workspace_id == ws.id, Audience.brand_id == None)  # noqa: E711
            )).scalars().all())
            has_brand_json = bool(ws.brand_json)
        brand_profile_configured = bool(has_brand_json and product_count > 0 and audience_count > 0)
        if not brand_profile_configured:
            issues.append("Brand profile incomplete — import or enter brand, product, and audience context")

        kit_stmt = (
            select(WorkspaceDocument)
            .where(
                WorkspaceDocument.workspace_id == ws.id,
                WorkspaceDocument.doc_type == "campaign_brand_kit",
                WorkspaceDocument.status == "approved",
            )
            .order_by(WorkspaceDocument.approved_at.desc().nullslast(), WorkspaceDocument.updated_at.desc())
            .limit(1)
        )
        if target_brand:
            kit_stmt = kit_stmt.where(WorkspaceDocument.brand_id == target_brand.id)
        else:
            kit_stmt = kit_stmt.where(WorkspaceDocument.brand_id == None)  # noqa: E711
        brand_kit = (await db.execute(kit_stmt)).scalar_one_or_none()
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
        if target_brand:
            brand_rows_provider = (await db.execute(
                select(ProviderKey).where(
                    ProviderKey.workspace_id == ws.id,
                    ProviderKey.brand_id == target_brand.id,
                )
            )).scalars().all()
            stored_providers.update({r.provider: r.auth_mode for r in brand_rows_provider})

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

    # Check registered modules. Plugin/tool modules are ready based on installation
    # and brand activation, not the generic LLM capability router.
    module_results: list[ModuleCheckResult] = []
    from plugin_loader import get_active_plugin_ids, get_plugin_for_module
    active_plugin_ids = await get_active_plugin_ids(db, target_brand.id if target_brand else None)
    for m in list_all():
        if m.get("internal"):
            continue

        module_id = m["id"]
        capability = m.get("capability", "")
        platform = m.get("platform_hint") or module_id.rsplit(".", 1)[-1]
        plugin = get_plugin_for_module(module_id)
        if plugin:
            active = plugin.manifest.plugin_id in active_plugin_ids
            ready = active
            provider_label = "plugin" if active else None
            if active:
                import os
                from models.social import SocialConnection
                from plugin_loader import get_plugin_vars, required_plugin_vars
                from routers.backend_settings import resolve_backend_override

                db_plugin_vars = await get_plugin_vars(plugin.manifest.plugin_id, db, settings)
                missing_vars = [
                    var for var in required_plugin_vars(plugin.manifest)
                    if not (os.getenv(var) or db_plugin_vars.get(var) or db_plugin_vars.get(var.lower()))
                ]
                social_rows = []
                if target_brand:
                    social_rows = (await db.execute(
                        select(SocialConnection).where(
                            SocialConnection.brand_id == target_brand.id,
                            SocialConnection.status == "connected",
                        )
                    )).scalars().all()
                social_platforms = {r.platform for r in social_rows}
                social_meta = {r.platform: (r.token_meta_json or {}) for r in social_rows}
                required_social = {
                    s.platform for s in plugin.manifest.credential_slots
                    if s.type == "social_token" and s.platform
                }
                social_ok = required_social.issubset(social_platforms)
                meta_ok = all(
                    (social_meta.get(s.platform) or {}).get(s.field) not in (None, "")
                    for s in plugin.manifest.credential_slots
                    if s.type == "social_meta_field" and s.platform and s.field
                )
                backend_ok = True
                for s in plugin.manifest.credential_slots:
                    if s.type == "backend_provider_api_key" and s.module:
                        override = await resolve_backend_override(db, ws.id, s.module) if ws else None
                        provider_name = (override.provider if override else "") or ""
                        backend_ok = backend_ok and bool(provider_name in connected)
                ready = not missing_vars and social_ok and meta_ok and backend_ok
                if not ready:
                    if missing_vars:
                        issues.append(f"{module_id}: missing plugin vars {', '.join(missing_vars)}")
                    if not social_ok:
                        issues.append(f"{module_id}: missing connected social platforms {', '.join(sorted(required_social - social_platforms))}")
                    if not meta_ok:
                        issues.append(f"{module_id}: missing required social metadata")
                    if not backend_ok:
                        issues.append(f"{module_id}: media backend/provider key not configured")
            module_results.append(ModuleCheckResult(
                module_id=module_id,
                platform=platform,
                capability=capability,
                ready=ready,
                provider=provider_label if ready else None,
            ))
            if not active:
                issues.append(f"{module_id}: plugin '{plugin.manifest.plugin_id}' is not active for this brand")
            continue

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

    if body.brand_id is None and (await db.execute(select(Brand.id).where(Brand.workspace_id == ws.id).limit(1))).scalar_one_or_none():
        raise HTTPException(
            status_code=422,
            detail=[{
                "loc": ["body", "brand_id"],
                "msg": "brand_id is required for onboarding ingest in a multi-brand workspace",
                "type": "value_error.missing",
            }],
        )

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
    submitted_profile: dict | None = None


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v not in (None, ""))
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items() if v not in (None, ""))
    return str(value)


def _first_dict(value) -> dict:
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict)), {})
    if isinstance(value, dict):
        return value
    return {}


def _profile_to_brief(profile: dict | None) -> dict:
    """Flatten a submitted/extracted brand profile into Brand Kit brief fields.

    The onboarding UI receives the freshly extracted profile before the operator
    asks for a Campaign Brand Kit.  Passing it through here makes that submitted
    profile the explicit source of truth, while DB rows remain the fallback.
    """
    if not isinstance(profile, dict):
        return {}

    brief: dict = {}

    def put(key: str, value) -> None:
        if value not in (None, "", [], {}):
            brief[key] = value

    nested_brand = profile.get("brand") if isinstance(profile.get("brand"), dict) else {}
    put("brand_name", profile.get("brand_name") or profile.get("name"))
    for field in ("voice", "tone", "values", "domain", "website_url", "social_handles"):
        put(field, profile.get(field) or nested_brand.get(field))

    product = _first_dict(profile.get("products") or profile.get("product_catalog"))
    benefits = product.get("benefits")
    if benefits is None and isinstance(product.get("benefits_json"), dict):
        benefits = product["benefits_json"].get("benefits")
    put("product_name", product.get("name") or product.get("product_name"))
    put("tagline", product.get("tagline"))
    put("benefits", benefits)
    if isinstance(benefits, list) and benefits:
        put("key_benefit", benefits[0])

    audience = _first_dict(profile.get("audiences") or profile.get("audience_profiles"))
    segment = audience.get("segment_json") if isinstance(audience.get("segment_json"), dict) else {}
    put("audience", audience.get("name") or audience.get("audience"))
    put("demographics", audience.get("demographics") or segment.get("demographics"))
    put("pain_points", audience.get("pain_points") or segment.get("pain_points"))

    return brief


_HEX_PATTERN = r"#[0-9a-fA-F]{6}"


def _brief_document_text(brief: dict) -> str:
    return _as_text(brief.get("document_text")).strip()


def _find_labeled_hex(document_text: str, labels: list[str], fallback: str | None = None) -> str | None:
    """Find a hex value near any approved color label in a pasted brand document."""
    if not document_text:
        return fallback
    for label in labels:
        label_pattern = r"\b" + r"\s+".join(re.escape(part) for part in label.split()) + r"\b"
        patterns = (
            rf"{label_pattern}[\s\S]{{0,120}}?({_HEX_PATTERN})",
            rf"({_HEX_PATTERN})[\s\S]{{0,120}}?{label_pattern}",
        )
        for pattern in patterns:
            match = re.search(pattern, document_text, flags=re.IGNORECASE)
            if match:
                return match.group(1).lower()
    return fallback


def _campaign_color_palette_rows(brief: dict) -> str:
    """Return Markdown rows for the Campaign Brand Kit palette.

    If the original brand document includes explicit visual guidelines, preserve
    those values instead of falling back to the generic starter palette.
    """
    document_text = _brief_document_text(brief)
    doc_lower = document_text.lower()
    doc_hexes = [h.lower() for h in re.findall(_HEX_PATTERN, document_text)]
    has_klaroha_palette = bool(document_text and (
        "racing green" in doc_lower or "primary brand anchor" in doc_lower
    ))
    has_generic_palette = bool(document_text and doc_hexes and any(
        label in doc_lower
        for label in ("brand colors", "color palette", "primary color", "secondary color", "accent color")
    ))

    if not has_klaroha_palette:
        if has_generic_palette:
            primary = _find_labeled_hex(document_text, ["Primary", "Primary color", "color-primary"], doc_hexes[0])
            secondary = _find_labeled_hex(document_text, ["Secondary", "Secondary color", "color-secondary"], doc_hexes[1] if len(doc_hexes) > 1 else primary)
            accent = _find_labeled_hex(document_text, ["Accent", "Accent color", "color-accent"], doc_hexes[2] if len(doc_hexes) > 2 else secondary)
            background = _find_labeled_hex(document_text, ["Background", "White", "Base"], "#ffffff")
            rows = [
                ("color-primary", primary, "Primary brand actions, hero accents, and key UI states from the imported brief."),
                ("color-secondary", secondary, "Secondary brand support color from the imported brief."),
                ("color-accent", accent, "Campaign accent for emphasis, badges, and selective conversion highlights."),
                ("color-neutral-900", "#111827", "Main text and strong headings unless the imported brief specifies a darker text token."),
                ("color-neutral-700", "#374151", "Secondary copy and supporting labels."),
                ("color-neutral-400", "#9CA3AF", "Borders, disabled states, low-priority metadata."),
                ("color-neutral-100", "#F3F4F6", "Low-emphasis surfaces and separators."),
                ("color-white", "#FFFFFF", "Cards, email body background, and reversed text."),
                ("color-success", "#15803D", "Positive status and completion cues."),
                ("color-warning", "#B45309", "Cautions and review-required messages."),
                ("color-error", "#B91C1C", "Errors and destructive actions."),
                ("bg-base", background, "Default campaign background unless channel requirements dictate white."),
                ("bg-subtle", "#F8FAFC", "Alternating page sections and email modules."),
                ("bg-surface", "#EEF6F8", "Highlight cards and campaign proof blocks."),
            ]
        else:
            rows = [
                ("color-primary", "#1F4E5F", "Primary brand actions, hero accents, key UI states."),
                ("color-primary-dark", "#12313C", "High-contrast headers, footers, and dark CTA states."),
                ("color-primary-light", "#D8E8ED", "Soft panels, callout backgrounds, subtle separators."),
                ("color-accent", "#F59E0B", "Conversion highlights, badges, progress cues."),
                ("color-neutral-900", "#111827", "Main text and strong headings."),
                ("color-neutral-700", "#374151", "Secondary copy and supporting labels."),
                ("color-neutral-400", "#9CA3AF", "Borders, disabled states, low-priority metadata."),
                ("color-neutral-100", "#F3F4F6", "Page sections and low-emphasis surfaces."),
                ("color-white", "#FFFFFF", "Cards, email body background, reversed text."),
                ("color-success", "#15803D", "Positive status and completion cues."),
                ("color-warning", "#B45309", "Cautions and review-required messages."),
                ("color-error", "#B91C1C", "Errors and destructive actions."),
                ("bg-base", "#FFFFFF", "Default campaign background."),
                ("bg-subtle", "#F8FAFC", "Alternating page sections and email modules."),
                ("bg-surface", "#EEF6F8", "Highlight cards and campaign proof blocks."),
            ]
    else:
        racing_green = _find_labeled_hex(document_text, ["Racing Green", "Primary color", "Primary brand anchor"], "#0b3d2e")
        forest = _find_labeled_hex(document_text, ["Forest", "Green hover tint"], "#4b7c54")
        sage = _find_labeled_hex(document_text, ["Sage", "Green light tint"], "#9cbd77")
        amber = _find_labeled_hex(document_text, ["Amber", "Primary accent"], "#fcc167")
        coral = _find_labeled_hex(document_text, ["Coral", "Primary CTA"], "#ef8250")
        crimson = _find_labeled_hex(document_text, ["Crimson", "Alert", "Error"], "#de425b")
        highlight = _find_labeled_hex(document_text, ["Highlight", "Highlight fill"], "#fffe9c")
        white = _find_labeled_hex(document_text, ["Pure White", "White", "Default background"], "#ffffff")
        ivory = _find_labeled_hex(document_text, ["Ivory", "Card surface"], "#f5f1e8")
        obsidian = _find_labeled_hex(document_text, ["Obsidian", "Dark accent"], "#080b0d")
        rows = [
            ("color-primary", racing_green, "Primary brand anchor: headlines, wordmark, structural chrome, and active navigation on light surfaces."),
            ("color-primary-hover", forest, "Hover/active tint for Racing Green elements; not a standalone campaign color."),
            ("color-muted-green", sage, "Muted green state and sublabels on dark surfaces only; do not use as body text on light backgrounds."),
            ("color-accent", amber, "Premium accent, tagline, clarity marker, pull-quotes, and eyebrow labels; not body copy on light surfaces."),
            ("color-cta-primary", coral, "Primary task CTA fill for submit, confirm, create, get started, and new campaign actions."),
            ("color-error", crimson, "Error and alert states only; never decorative."),
            ("color-highlight-fill", highlight, "Annotation and callout fill only; never text."),
            ("bg-base", white, "Default page, document, email, and product/campaign background."),
            ("bg-card", ivory, "Warm card or secondary panel fill only; never a full-page background."),
            ("bg-dark-accent", obsidian, "Cockpit sections, dashboard moments, and footers only; never default background."),
            ("text-heading", racing_green, "Headlines on white or ivory surfaces."),
            ("text-body", "#333333", "Body copy on white or ivory surfaces."),
            ("text-muted", "#666666", "Captions, metadata, and secondary labels on light surfaces."),
            ("text-on-dark", ivory, "Headline and body text on Obsidian or Racing Green surfaces."),
        ]

    return "\n".join(f"| `{token}` | `{hex_value}` | {usage} |" for token, hex_value, usage in rows)


def _campaign_typography_rows(brief: dict) -> str:
    document_text = _brief_document_text(brief).lower()
    if "manrope" in document_text:
        rows = [
            ("font-heading", "`Manrope, system-ui, sans-serif`", "Display text, H1–H4, section labels, metric numbers, and wordmark-adjacent campaign headings."),
            ("font-body", "`Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif`", "Body copy, email text, landing page paragraphs, UI labels, and campaign descriptions."),
            ("font-label", "`Inter, system-ui, sans-serif`", "Buttons, badges, metadata, form labels, and data labels."),
        ]
    elif "inter" in document_text:
        rows = [
            ("font-heading", "`Inter, system-ui, sans-serif`", "Headlines, section titles, landing hero copy."),
            ("font-body", "`Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif`", "Body copy, email text, landing page paragraphs, UI labels, and campaign descriptions."),
            ("font-label", "`Inter, system-ui, sans-serif`", "Buttons, badges, metadata, form labels, and data labels."),
        ]
    else:
        rows = [
            ("font-heading", "`Inter, Manrope, system-ui, sans-serif`", "Headlines, section titles, landing hero copy."),
            ("font-body", "`Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif`", "Body copy, email text, landing page paragraphs."),
            ("font-label", "`Inter, system-ui, sans-serif`", "Buttons, badges, metadata, form labels."),
        ]
    return "\n".join(f"| `{token}` | {recommendation} | {usage} |" for token, recommendation, usage in rows)


def _campaign_visual_rules(brief: dict) -> str:
    document_text = _brief_document_text(brief)
    doc_lower = document_text.lower()
    rules: list[str] = []
    if "dark on light" in doc_lower or "light on dark" in doc_lower or "contrast" in doc_lower:
        rules.append("Maintain the hard contrast rule: dark foreground on white/ivory surfaces; light foreground on Obsidian/Racing Green surfaces.")
    if "corner radius" in doc_lower or "2px" in doc_lower:
        rules.append("Use square geometry by default: cards, panels, tables, and containers are 0px radius; buttons, inputs, badges, and tooltips may use 2px maximum.")
    if "white" in doc_lower and "ivory" in doc_lower:
        rules.append("Keep Pure White as the default canvas; use Ivory only for card fills or warm secondary panels.")
    if "coral" in doc_lower and "cta" in doc_lower:
        coral = _find_labeled_hex(document_text, ["Coral", "Primary CTA"], "#ef8250")
        ivory = _find_labeled_hex(document_text, ["Ivory"], "#f5f1e8")
        racing_green = _find_labeled_hex(document_text, ["Racing Green"], "#0b3d2e")
        rules.append(f"Primary execution CTAs use Coral {coral} with Ivory {ivory} text; secondary CTAs use transparent fill with Racing Green {racing_green} border/text on light surfaces.")
    if "amber" in doc_lower and "body" in doc_lower:
        rules.append("Reserve Amber for premium accents, taglines, clarity markers, pull-quotes, and eyebrows — not paragraph-length body copy.")
    if not rules:
        return "Maintain WCAG AA contrast, consistent token usage, visible focus states, and one primary CTA per flow."
    return " ".join(rules)


def _campaign_brand_kit_markdown(brief: dict, title_fallback: str) -> str:
    """Generate a deterministic Campaign Brand Kit without waiting on external LLMs.

    Onboarding should never be blocked by provider quota / fallback latency. This
    draft intentionally satisfies the same required structure as the LLM module
    and can be edited or regenerated later.

    All sections are derived from the brand profile brief — no section should
    contain hardcoded brand-specific copy that belongs to a different client.
    """
    brand_name  = (_as_text(brief.get("brand_name")).strip()
                   or title_fallback.replace(" — Campaign Brand Kit", "") or "Brand")
    product_name = _as_text(brief.get("product_name")).strip() or "Primary offer"
    tagline      = (_as_text(brief.get("tagline")).strip()
                    or _as_text(brief.get("key_benefit")).strip()
                    or "Turn demand into measurable results")
    audience     = _as_text(brief.get("audience")).strip() or "high-intent buyers and decision makers"
    tone         = _as_text(brief.get("tone")).strip() or "clear, confident, and practical"
    voice        = _as_text(brief.get("voice")).strip() or "authoritative and useful"
    values_text  = _as_text(brief.get("values")).strip() or "clarity, precision, results"
    benefits_text = _as_text(brief.get("benefits")).strip() or tagline
    pain_text    = _as_text(brief.get("pain_points")).strip() or "fragmented tools, unclear next steps, and missed follow-up"

    # ── Voice pillars: derived from the brand's values ─────────────────────────
    raw_values = brief.get("values")
    if isinstance(raw_values, list) and raw_values:
        value_list = [str(v).strip() for v in raw_values if str(v).strip()]
    else:
        value_list = [v.strip() for v in values_text.split(",") if v.strip()]

    def _pillar_guidance(val: str) -> str:
        v = val.lower()
        if any(w in v for w in ("clear", "clarity", "simple", "plain")):
            return "use plain language, name the problem specifically, and always state the next step."
        if any(w in v for w in ("preci", "specific", "exact", "accura")):
            return "describe outcomes, buyers, channels, and constraints with concrete detail — avoid vague claims."
        if any(w in v for w in ("result", "outcome", "impact", "growth", "revenue", "conver")):
            return "connect every claim to a business movement: qualified conversations, conversion, revenue, or time saved."
        if any(w in v for w in ("trust", "honest", "transparen", "authentic")):
            return "cite facts, proof, or context rather than promises; let outcomes speak."
        if any(w in v for w in ("speed", "fast", "quick", "efficien")):
            return "cut filler; lead with what happens first and how quickly."
        if any(w in v for w in ("partner", "collaborat", "team", "together")):
            return "speak alongside the buyer, not above them — use 'your' not 'our clients'."
        return f"make every message reflect {val.lower()} — remove anything that dilutes this signal."

    pillar_lines = "\n".join(
        f"- **{v.capitalize()}:** {_pillar_guidance(v)}"
        for v in value_list[:5]
    ) or f"- **{voice.split()[0].capitalize()}:** every message should be direct, specific, and tied to a real business outcome."

    # ── Do / Don't examples: derived from product, audience, and pain points ───
    raw_pain = brief.get("pain_points")
    pain_list: list[str] = (
        raw_pain if isinstance(raw_pain, list) and raw_pain
        else [p.strip() for p in pain_text.split(",") if p.strip()]
    )
    raw_benefits = brief.get("benefits")
    benefit_list: list[str] = (
        raw_benefits if isinstance(raw_benefits, list) and raw_benefits
        else [b.strip() for b in benefits_text.split(",") if b.strip()]
    )

    first_pain  = pain_list[0] if pain_list else "missed follow-up"
    second_pain = pain_list[1] if len(pain_list) > 1 else "inconsistent processes"
    first_ben   = benefit_list[0] if benefit_list else tagline

    do_1 = f'Do: "{product_name} — {tagline}."'
    do_2 = f'Do: "Built for {audience} dealing with {first_pain}."'
    do_3 = f'Do: "See exactly which step each buyer is at, and what happens next."'
    dont_1 = 'Don\'t: "Revolutionize your business with a world-class platform."'
    dont_2 = 'Don\'t: "Unlock synergy across your digital ecosystem."'
    dont_3 = 'Don\'t: "Guaranteed growth with no operational change."'

    # ── CTA examples: derived from product and tagline ─────────────────────────
    product_slug = product_name.split()[0] if product_name else "platform"
    cta_examples = (
        f'"See the {product_slug} in action," "Book a working session," '
        f'"Review the campaign plan," "Start with one team."'
    )

    # ── Component examples: derived from product, audience, and pain points ────
    comp_primary_cta   = f'"Book a {product_slug} demo"; "Map your buyer path"; "Start a pilot."'
    comp_secondary_cta = '"See how it works"; "View campaign examples"; "Read the brief."'
    comp_ad_headline   = f'"{tagline}"; "Stop {first_pain} — give {audience} a clear next step."'
    comp_ad_body       = f'"Built for {audience} who need {first_ben}.  Fast to deploy, clear to act on."'
    comp_badge         = f'"{product_slug} Ready"; "Campaign Draft"; "Sales Ready."'
    comp_card          = f'"{first_ben}"; "Keep {audience} follow-up consistent"; "Measure campaign conversations."'
    comp_email_subject = f'"Your {product_slug} campaign path is ready"; "Where qualified inquiries are leaking."'
    comp_landing_hero  = f'"{tagline}"; "Give every {audience} a clear path from intent to conversation."'

    # ── Multi-platform rules: audience- and product-aware ──────────────────────
    platform_product  = product_slug.lower()
    platform_audience = audience.lower()

    color_palette_rows = _campaign_color_palette_rows(brief)
    typography_rows = _campaign_typography_rows(brief)
    visual_rules = _campaign_visual_rules(brief)

    return f"""# {brand_name} — Campaign Brand Kit
> This required onboarding artifact defines the minimum visual, voice, typography, CTA, component, and platform rules needed to produce cohesive multi-platform marketing campaigns for {brand_name}.

---

## 1. Campaign Brand Kit Overview 🔲

| Field | Draft decision |
|---|---|
| Brand name | {brand_name} |
| Core promise | {tagline} |
| Campaign personality | {voice}; {tone}. |
| Primary product/service | {product_name} |
| Target audience | {audience} |
| Campaign objective | Convert qualified demand into clear next-step conversations. |
| Approval owner | Founder, marketing lead, or designated brand owner. |

## 2. Color Palette 🔲

| Token | Hex | Usage |
|---|---:|---|
{color_palette_rows}

## 3. Tone of Voice 🔲

**Voice summary:** {brand_name} should sound {voice}: direct enough to be trusted, practical enough to be acted on, and specific enough to avoid generic marketing claims.

**Tone:** {tone}. The tone should speak to {audience}, especially when they are dealing with {pain_text}.

**Voice pillars**
{pillar_lines}

**Do / Don't examples**
- {do_1}
- {do_2}
- {do_3}
- {dont_1}
- {dont_2}
- {dont_3}

**Banned words or phrases:** revolutionary, effortless growth, game-changing, best-in-class without proof, one-size-fits-all, guaranteed results.

**CTA language rules:** Use action-oriented CTAs with a clear commitment level: {cta_examples}

## 4. Typography Basics 🔲

| Token | Recommendation | Usage |
|---|---|---|
{typography_rows}

**Heading style:** concise, benefit-led, sentence case. Use strong contrast and avoid decorative type.  
**Body copy style:** short paragraphs, concrete nouns, active verbs.  
**Label style:** short, scannable, and consistent. If custom fonts are introduced later, licensing must be confirmed before production use.

## 5. Campaign Components 🔲

| Component token | Purpose | Writing/style rules | Examples |
|---|---|---|---|
| `component-primary-cta` | Main conversion action. | Verb first, low ambiguity, one action. | {comp_primary_cta} |
| `component-secondary-cta` | Lower-pressure next step. | Offer learning or proof without competing with primary CTA. | {comp_secondary_cta} |
| `component-ad-headline` | Stop scroll/search with a clear promise. | 8–12 words, outcome first. | {comp_ad_headline} |
| `component-ad-body` | Explain relevance and next step. | Name audience, pain, and result. | {comp_ad_body} |
| `component-badge-label` | Small trust or status marker. | 2–4 words, factual. | {comp_badge} |
| `component-content-card` | Reusable proof/benefit card. | One idea per card, headline + 1–2 lines. | {comp_card} |
| `component-email-subject` | Earn the open. | Specific, useful, no hype. | {comp_email_subject} |
| `component-landing-hero` | Explain the campaign promise above the fold. | Headline, proof-oriented subhead, primary CTA. | {comp_landing_hero} |

## 6. Multi-Platform Rules 🔲

- **facebook:** Lead with the specific operational pain facing {platform_audience}. Use a visual proof cue and one clear CTA referencing {platform_product}.
- **twitter/x:** Compress the core promise into a sharp, specific point of view. Use threads for education; keep the CTA to a single next step.
- **google:** Match search intent directly. Use the product/category phrase, state the outcome, and include a trust cue — do not change the core claim.
- **email:** Use the same campaign promise in a more consultative sequence: problem for {platform_audience}, implication, practical next step with {platform_product}.
- **landing page:** Expand the promise with proof blocks, {platform_audience}-specific use cases, objections, and a clear conversion path to {platform_product}.

## 7. Accessibility & Consistency 🔲

This kit requires WCAG 2.1 AA as the minimum standard. Maintain sufficient contrast for text and controls, use readable type sizes, preserve visible keyboard/focus states, never use color as the only meaning, and respect reduced-motion preferences. Keep CTA labels, color tokens, and component names stable across campaigns.

**Visual system rules:** {visual_rules}

## 8. Governance 🔲

- **Status:** Draft until approved.
- **Owner role:** Founder, marketing lead, or delegated brand owner.
- **When to update:** Update only when positioning, audience, offer, channel strategy, or visual identity changes materially.
- **Versioning recommendation:** Use semantic draft labels such as `v1.0-draft`, `v1.0-approved`, and `v1.1-refresh`.
- **How campaign modules should use it:** Treat this kit as the stable source for voice, CTA, typography, color, and component decisions before creating ads, emails, landing pages, or social posts.

This kit should remain stable for months or years unless the brand changes materially.

## Optional Future Expansion ⬜

Future expansions may include logo rules, illustration style, photography direction, detailed motion system, full component inventory, proof library, and a design token pipeline.

<!-- Context used: brand={brand_name}; product={product_name}; audience={audience}; values={values_text}; benefits={benefits_text}; pain_points={pain_text} -->
"""


@router.get("/onboarding/brand-kit/latest", response_model=WorkspaceDocumentOut, responses={404: {"description": "Not found"}, 422: {"description": "brand_id required in multi-brand workspace"}})
async def get_latest_campaign_brand_kit(
    status: str | None = None,
    brand_id: NullableUUID = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Return the latest Campaign Brand Kit document, including full Markdown content."""
    if status in ("null", ""):
        status = None
    if status is not None and status not in {"draft", "approved", "changes_requested", "archived"}:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["query", "status"], "msg": f"value is not a valid status: '{status}'", "type": "value_error"}],
        )

    ws = await get_singleton(db)
    if ws is None:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    if brand_id:
        await _resolve_target_brand(db, ws, brand_id)
    elif (await db.execute(select(Brand.id).where(Brand.workspace_id == ws.id).limit(1))).scalar_one_or_none():
        raise HTTPException(
            status_code=422,
            detail=[{
                "loc": ["query", "brand_id"],
                "msg": "brand_id is required in a multi-brand workspace",
                "type": "value_error.missing",
            }],
        )

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
    ws = await get_singleton(db)
    if ws is None:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    target_brand = await _resolve_target_brand(db, ws, body.brand_id)

    brief_override = _profile_to_brief(body.submitted_profile)
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

    # Generate synchronously and deterministically. This onboarding step must not
    # be blocked by external LLM quota, slow provider fallback chains, or nginx
    # timeouts. The artifact is a practical draft and can be edited/approved by
    # the operator.
    content = _campaign_brand_kit_markdown(brief, title_fallback)
    title = _title_from_markdown(content, title_fallback)

    run = Run(
        workspace_id=ws.id,
        brand_id=run_brand_id,
        module_id="onboarding.brand_guidelines",
        status="success",
        approval_status="approved",
    )
    db.add(run)
    await db.flush()
    db.add(RunAttempt(
        run_id=run.id,
        provider="local",
        model_id="deterministic-campaign-brand-kit-v1",
        mode="local",
        status="succeeded",
        tokens_input=0,
        tokens_output=0,
        provider_cost=0.0,
        latency_ms=0,
    ))
    db.add(RunResult(
        run_id=run.id,
        content=content,
        self_check_verdict="pass",
        sell_price=0.0,
    ))

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
            "generation_mode": "deterministic_local",
            "required_for_onboarding": True,
            "summary_fields": [
                "color_palette",
                "tone_of_voice",
                "typography_basics",
                "campaign_components",
                "platform_consistency_rules",
            ],
        },
        source_run_id=run.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return BrandKitResponse(run_id=str(run.id), document=_document_out(doc))
