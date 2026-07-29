"""Onboarding endpoints: status check and brand brief ingestion."""
from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from validation import NullableUUID
from pydantic import BaseModel, Field
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
from models.social import SocialConnection
from models.workspace import Audience, Brand, Product, Workspace
from registry import list_all
from routers.runs import _execute_module, _resolve_brief
from routers.workspace import _build_response, get_singleton
from schemas.documents import WorkspaceDocumentOut
from services.brand_kit_templates import ensure_template_manifest
from campaign import db as campaign_db
from schemas.workspace import WorkspaceResponse

router = APIRouter(tags=["onboarding"])
logger = logging.getLogger("bos.onboarding")

_KNOWN_PROVIDERS = ["openai", "gemini", "bytedance", "openrouter", "nvidia"]


def _normalize_backend_provider(provider: str | None) -> str:
    value = str(provider or "").strip().lower()
    if value in {"byteplus_modelark", "byteplus", "modelark"}:
        return "bytedance"
    return value


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


class BrandVisualAssetCategory(BaseModel):
    label: str
    count: int


class ClientReadinessCell(BaseModel):
    ok: bool
    label: str


class ClientReadinessAction(BaseModel):
    key: str
    label: str


class ClientReadinessSnapshot(BaseModel):
    brief: ClientReadinessCell
    brand_kit: ClientReadinessCell
    drive: ClientReadinessCell
    capabilities: ClientReadinessCell
    publish_channels: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_action: ClientReadinessAction | None = None
    drive_setup_debt: bool = False


def _build_client_readiness_snapshot(
    *,
    brand_profile_configured: bool,
    campaign_brand_kit_approved: bool,
    drive_connection_status: str | None,
    drive_root_name: str | None,
    brand_mark_configured: bool,
    publish_channels: list[str],
    live_campaign_present: bool,
    capability_ready_count: int,
    capability_total_count: int,
    installed_plugin_count: int,
    active_plugin_count: int,
) -> ClientReadinessSnapshot:
    drive_ready = drive_connection_status == "connected" and bool(drive_root_name) and brand_mark_configured

    if drive_connection_status == "needs_reauth":
        drive_label = "Reconnect required"
    elif drive_connection_status != "connected":
        drive_label = "Not connected"
    elif not drive_root_name:
        drive_label = "Choose folder"
    elif not brand_mark_configured:
        drive_label = "Add logo"
    else:
        drive_label = "Ready"

    capability_ok = capability_total_count > 0 and capability_ready_count == capability_total_count
    if capability_total_count <= 0:
        capability_label = "None installed"
    elif capability_ok:
        capability_label = f"{capability_ready_count} ready"
    else:
        capability_label = f"{capability_ready_count}/{capability_total_count} ready"

    blockers: list[tuple[str, str]] = []
    if not brand_profile_configured:
        blockers.append(("Import brand brief", "import_brief"))
    if not campaign_brand_kit_approved:
        blockers.append(("Approve brand kit", "approve_brand_kit"))
    if drive_connection_status == "needs_reauth":
        blockers.append(("Reconnect Drive", "reconnect_drive"))
    elif drive_connection_status != "connected":
        blockers.append(("Connect Drive", "connect_drive"))
    elif not drive_root_name:
        blockers.append(("Choose Drive folder", "choose_drive_folder"))
    elif not brand_mark_configured:
        blockers.append(("Add logo", "add_logo"))
    if not publish_channels:
        blockers.append(("Connect publish channel", "connect_publish_channel"))
    if not live_campaign_present:
        blockers.append(("Create live campaign", "create_live_campaign"))
    if capability_total_count <= 0:
        blockers.append(("Install capabilities", "install_capabilities"))
    elif not capability_ok:
        blockers.append((
            "Activate capabilities" if installed_plugin_count > 0 and active_plugin_count <= 0 else "Fix capability setup",
            "activate_capabilities" if installed_plugin_count > 0 and active_plugin_count <= 0 else "configure_capabilities",
        ))

    next_action = ClientReadinessAction(key=blockers[0][1], label=blockers[0][0]) if blockers else None
    return ClientReadinessSnapshot(
        brief=ClientReadinessCell(ok=brand_profile_configured, label="Imported" if brand_profile_configured else "Missing"),
        brand_kit=ClientReadinessCell(
            ok=campaign_brand_kit_approved,
            label="Approved" if campaign_brand_kit_approved else ("Needs approval" if brand_profile_configured else "Missing"),
        ),
        drive=ClientReadinessCell(ok=drive_ready, label=drive_label),
        capabilities=ClientReadinessCell(ok=capability_ok, label=capability_label),
        publish_channels=publish_channels,
        blockers=[label for label, _key in blockers],
        next_action=next_action,
        drive_setup_debt=not drive_ready,
    )


class OnboardingStatus(BaseModel):
    workspace_configured: bool
    workspace_name: str | None
    brand_profile_configured: bool
    campaign_brand_kit_approved: bool
    campaign_brand_kit_document_id: str | None = None
    live_campaign_present: bool = False
    live_campaign_id: str | None = None
    drive_connected: bool = False
    drive_connection_status: str | None = None
    drive_root_folder_id: str | None = None
    drive_root_name: str | None = None
    brand_mark_configured: bool = False
    brand_mark_file_id: str | None = None
    brand_mark_file_name: str | None = None
    brand_visual_assets: dict[str, BrandVisualAssetCategory] = Field(default_factory=dict)
    providers: list[ProviderCheckResult] = Field(default_factory=list)
    modules: list[ModuleCheckResult] = Field(default_factory=list)
    client_readiness: ClientReadinessSnapshot
    all_ready: bool
    issues: list[str] = Field(default_factory=list)


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
    live_campaign_present = False
    live_campaign_id = None
    drive_connected = False
    drive_connection_status: str | None = None
    brand_mark_configured = False
    brand_visual_assets: dict = {}
    drive_meta: dict = {}
    brand_social_rows: list[SocialConnection] = []
    connected_brand_social_rows: list[SocialConnection] = []
    connected_social_platforms: set[str] = set()
    connected_social_meta: dict[str, dict] = {}
    publish_channels: list[str] = []

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

    if target_brand:
        brand_social_rows = (await db.execute(
            select(SocialConnection)
            .where(
                SocialConnection.workspace_id == ws.id,
                SocialConnection.brand_id == target_brand.id,
            )
            .order_by(SocialConnection.created_at.desc())
        )).scalars().all()
        connected_brand_social_rows = [row for row in brand_social_rows if row.status == "connected"]
        connected_social_platforms = {row.platform for row in connected_brand_social_rows}
        connected_social_meta = {row.platform: (row.token_meta_json or {}) for row in connected_brand_social_rows}
        latest_drive = next((row for row in brand_social_rows if row.platform == "google_drive"), None)
        drive_connection_status = latest_drive.status if latest_drive else None
        for platform, label in (("facebook", "facebook"), ("youtube", "youtube"), ("tiktok", "tiktok"), ("google_business", "GBP")):
            if any(row.platform == platform and row.status == "connected" for row in brand_social_rows):
                publish_channels.append(label)

    if not workspace_configured:
        issues.append("Workspace not configured — POST /workspace")
    else:
        brand_json_data: dict | None = None
        if target_brand:
            product_count = len((await db.execute(
                select(Product).where(Product.workspace_id == ws.id, Product.brand_id == target_brand.id)
            )).scalars().all())
            audience_count = len((await db.execute(
                select(Audience).where(Audience.workspace_id == ws.id, Audience.brand_id == target_brand.id)
            )).scalars().all())
            brand_json_data = target_brand.brand_json if isinstance(target_brand.brand_json, dict) else None
            has_brand_json = bool(brand_json_data)
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
            brand_json_data = ws.brand_json if isinstance(ws.brand_json, dict) else None
            has_brand_json = bool(brand_json_data)
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
            issues.append("Brand Creative Brief not approved — generate and approve the required onboarding document")

        live_campaign_rows = await campaign_db.read_rows(
            db,
            workspace_id=ws.id,
            brand_id=target_brand.id if target_brand else None,
            status="active",
            limit=1,
        )
        if live_campaign_rows:
            live_campaign_present = True
            live_campaign_id = str(campaign_db.campaign_key(live_campaign_rows[0]))
        else:
            issues.append("No live campaign found — onboarding should extract the first active campaign from the brand profile")

        drive_meta = await _brand_drive_asset_folder_metadata(
            db, target_brand.id if target_brand else None
        )
        drive_connected = drive_meta.get("drive_connected", False)
        brand_mark_configured = drive_meta.get("brand_mark_configured", False)
        brand_visual_assets = drive_meta.get("brand_visual_assets", {})
        if target_brand and drive_connection_status == "needs_reauth":
            issues.append("Google Drive needs re-authentication — reconnect before image and video generation")
        elif target_brand and not drive_connected:
            issues.append("Google Drive not connected — required for image and video generation")
        elif target_brand and not brand_mark_configured:
            issues.append("Google Drive connected but no Brand Mark (logo/wordmark) found — validate the Brand Kit folder")
        if target_brand and not publish_channels:
            issues.append("No publish channel connected — connect Facebook, YouTube, TikTok, or Google Business before publishing")

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
    from plugin_loader import get_active_plugin_ids, get_loaded_plugins, get_plugin_for_module
    active_plugin_ids = await get_active_plugin_ids(db, target_brand.id if target_brand else None)
    loaded_plugins = get_loaded_plugins()
    installed_plugin_ids = {
        plugin_id for plugin_id in loaded_plugins.keys()
        if "test_stub" not in plugin_id.lower()
    }
    active_installed_plugin_ids = {plugin_id for plugin_id in active_plugin_ids if plugin_id in installed_plugin_ids}
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
                from plugin_loader import get_plugin_vars, required_plugin_vars
                from routers.backend_settings import resolve_backend_override

                db_plugin_vars = await get_plugin_vars(plugin.manifest.plugin_id, db, settings)
                missing_vars = [
                    var for var in required_plugin_vars(plugin.manifest)
                    if not (os.getenv(var) or db_plugin_vars.get(var) or db_plugin_vars.get(var.lower()))
                ]
                required_social = {
                    s.platform for s in plugin.manifest.credential_slots
                    if s.type == "social_token" and s.platform
                }
                social_ok = required_social.issubset(connected_social_platforms)
                meta_ok = all(
                    (connected_social_meta.get(s.platform) or {}).get(s.field) not in (None, "")
                    for s in plugin.manifest.credential_slots
                    if s.type == "social_meta_field" and s.platform and s.field
                )
                backend_ok = True
                for s in plugin.manifest.credential_slots:
                    if s.type == "backend_provider_api_key" and s.module:
                        override = await resolve_backend_override(db, ws.id, s.module) if ws else None
                        provider_name = _normalize_backend_provider((override.provider if override else "") or "")
                        backend_ok = backend_ok and bool(provider_name in connected)
                ready = not missing_vars and social_ok and meta_ok and backend_ok
                if not ready:
                    if missing_vars:
                        issues.append(f"{module_id}: missing plugin vars {', '.join(missing_vars)}")
                    if not social_ok:
                        issues.append(f"{module_id}: missing connected social platforms {', '.join(sorted(required_social - connected_social_platforms))}")
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
        and live_campaign_present
        and brand_mark_configured
        and bool(publish_channels)
        and bool(connected)
        and all(m.ready for m in module_results)
    )
    client_readiness = _build_client_readiness_snapshot(
        brand_profile_configured=brand_profile_configured,
        campaign_brand_kit_approved=campaign_brand_kit_approved,
        drive_connection_status=drive_connection_status,
        drive_root_name=drive_meta.get("drive_root_name"),
        brand_mark_configured=brand_mark_configured,
        publish_channels=publish_channels,
        live_campaign_present=live_campaign_present,
        capability_ready_count=sum(1 for module in module_results if module.ready),
        capability_total_count=len(module_results),
        installed_plugin_count=len(installed_plugin_ids),
        active_plugin_count=len(active_installed_plugin_ids),
    )

    return OnboardingStatus(
        workspace_configured=workspace_configured,
        workspace_name=workspace_name,
        brand_profile_configured=brand_profile_configured,
        campaign_brand_kit_approved=campaign_brand_kit_approved,
        campaign_brand_kit_document_id=campaign_brand_kit_document_id,
        live_campaign_present=live_campaign_present,
        live_campaign_id=live_campaign_id,
        drive_connected=drive_connected,
        drive_connection_status=drive_connection_status,
        drive_root_folder_id=drive_meta.get("drive_root_folder_id"),
        drive_root_name=drive_meta.get("drive_root_name"),
        brand_mark_configured=brand_mark_configured,
        brand_mark_file_id=drive_meta.get("brand_mark_file_id"),
        brand_mark_file_name=drive_meta.get("brand_mark_file_name"),
        brand_visual_assets=brand_visual_assets,
        providers=provider_results,
        modules=module_results,
        client_readiness=client_readiness,
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


def _profile_json_from_profile(profile: dict, *, brand_name: str | None = None) -> dict:
    """Persist the durable creative identity extracted during onboarding."""
    nested_visual = profile.get("visual_identity") if isinstance(profile.get("visual_identity"), dict) else {}
    fields = {
        "voice": profile.get("voice"),
        "tone": profile.get("tone"),
        "values": profile.get("values"),
        "industry": profile.get("industry"),
        "color_palette": profile.get("color_palette") or nested_visual.get("color_palette") or nested_visual.get("colors"),
        "visual_language": profile.get("visual_language") or nested_visual.get("visual_language") or nested_visual.get("style"),
        "typography": profile.get("typography") or nested_visual.get("typography"),
        "negative_prompts": profile.get("negative_prompts") or nested_visual.get("avoid"),
        "mandatory_treatments": profile.get("mandatory_treatments") or nested_visual.get("mandatory_treatments"),
    }
    return {key: value for key, value in fields.items() if value not in (None, "", [], {})}


def _clip_campaign_text(value: str | None, limit: int = 255) -> str | None:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return None
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


def _campaign_seed_from_profile(profile: dict, *, brand_name: str) -> dict:
    product = _first_dict(profile.get("products") or profile.get("product_catalog"))
    audience = _first_dict(profile.get("audiences") or profile.get("audience_profiles"))

    product_name = str(product.get("name") or product.get("product_name") or "").strip()
    tagline = str(product.get("tagline") or "").strip()
    benefits = product.get("benefits")
    if benefits is None and isinstance(product.get("benefits_json"), dict):
        benefits = product.get("benefits_json", {}).get("benefits")
    benefits = [str(item).strip() for item in (benefits or []) if str(item).strip()]
    first_benefit = benefits[0] if benefits else ""

    audience_name = str(audience.get("name") or audience.get("audience") or "").strip()
    demographics = str(audience.get("demographics") or ((audience.get("segment_json") or {}).get("demographics") if isinstance(audience.get("segment_json"), dict) else "") or "").strip()
    pain_points = audience.get("pain_points") or ((audience.get("segment_json") or {}).get("pain_points") if isinstance(audience.get("segment_json"), dict) else []) or []
    pain_points = [str(item).strip() for item in pain_points if str(item).strip()]

    campaign_subject = product_name or brand_name
    if product_name and product_name.lower() not in brand_name.lower():
        campaign_name = f"{brand_name} — {product_name} Campaign"
    else:
        campaign_name = f"{brand_name} Campaign"

    objective_parts: list[str] = []
    if audience_name:
        objective_parts.append(f"Generate qualified demand for {campaign_subject} among {audience_name}")
    else:
        objective_parts.append(f"Generate qualified demand for {campaign_subject}")
    if tagline:
        objective_parts.append(f"Core promise: {tagline}")
    elif first_benefit:
        objective_parts.append(f"Primary benefit: {first_benefit}")
    initial_intent = ". ".join(part.rstrip(".") for part in objective_parts if part).strip()
    if initial_intent and not initial_intent.endswith("."):
        initial_intent += "."
    if not initial_intent:
        initial_intent = f"Turn the approved brand profile for {brand_name} into a live campaign foundation."

    if tagline:
        message_angle = tagline
    elif first_benefit:
        message_angle = first_benefit
    elif pain_points:
        message_angle = f"Address {pain_points[0]} with a clear next step."
    else:
        message_angle = initial_intent

    audience_display = audience_name or demographics or ""
    campaign_json = {
        "source": "onboarding.brand_profile",
        "seed_origin": "brand_profile_ingest",
        "extracted_from_brand_profile": True,
        "initial_intent": initial_intent,
        "business_objective": initial_intent,
        "goal": initial_intent,
        "product_name": product_name or None,
        "tagline": tagline or None,
        "benefits": benefits,
        "audience_name": audience_name or None,
        "demographics": demographics or None,
        "pain_points": pain_points,
        "brand_name": brand_name,
    }

    return {
        "name": _clip_campaign_text(campaign_name, 255) or f"{brand_name} Campaign",
        "audience": _clip_campaign_text(audience_display, 255),
        "message_angle": _clip_campaign_text(message_angle, 255),
        "initial_intent": initial_intent,
        "campaign_json": {k: v for k, v in campaign_json.items() if v not in (None, "", [], {})},
    }


async def _ensure_live_campaign_from_profile(
    db: AsyncSession,
    ws: Workspace,
    *,
    brand_id: UUID | None,
    brand_name: str,
    profile: dict,
):
    existing = await campaign_db.read_rows(
        db,
        workspace_id=ws.id,
        brand_id=brand_id,
        status="active",
        limit=1,
    )
    if existing:
        return existing[0]

    seed = _campaign_seed_from_profile(profile, brand_name=brand_name)
    row = await campaign_db.create_campaign_record(db, {
        "workspace_id": ws.id,
        "brand_id": brand_id,
        "name": seed["name"],
        "status": "active",
        "audience": seed.get("audience"),
        "message_angle": seed.get("message_angle"),
        "campaign_json": seed.get("campaign_json") or {},
    })
    row.source_type = "onboarding.brand_profile_ingest"
    row.source_ref = "onboarding/ingest"
    row.producer = "onboarding"
    row.actual_activity = "Live campaign extracted from the onboarding brand profile."
    row.confidence = "medium"
    row.what_changed = "Created the first live campaign from onboarding brand profile data."
    row.next_action = "Confirm channel plan, first creative, and first evidence source."
    row.evidence_refs = ["onboarding.brand_setup"]
    await db.commit()
    await db.refresh(row)
    return row


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
    for field in (
        "tone", "voice", "values", "domain", "website_url", "social_handles",
        "industry", "color_palette", "visual_language", "typography",
        "negative_prompts", "mandatory_treatments",
    ):
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

    profile_json = _profile_json_from_profile(profile, brand_name=brand_name)

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

    await _ensure_live_campaign_from_profile(
        db,
        ws,
        brand_id=scoped_brand_id,
        brand_name=brand_name,
        profile={**profile, "brand_name": brand_name},
    )

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
    asks for a Brand Creative Brief. Passing it through here makes that submitted
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
    for field in (
        "voice", "tone", "values", "domain", "website_url", "social_handles",
        "industry", "color_palette", "visual_language", "typography",
        "negative_prompts", "mandatory_treatments",
    ):
        put(field, profile.get(field) or nested_brand.get(field))
    visual_identity = profile.get("visual_identity") if isinstance(profile.get("visual_identity"), dict) else {}
    put("color_palette", brief.get("color_palette") or visual_identity.get("color_palette") or visual_identity.get("colors"))
    put("visual_language", brief.get("visual_language") or visual_identity.get("visual_language") or visual_identity.get("style"))
    put("typography", brief.get("typography") or visual_identity.get("typography"))
    put("negative_prompts", brief.get("negative_prompts") or visual_identity.get("avoid"))
    put("mandatory_treatments", brief.get("mandatory_treatments") or visual_identity.get("mandatory_treatments"))

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


def _brand_creative_brief_markdown(brief: dict, title_fallback: str) -> str:
    """Compile durable brand evidence into a concise, agency-style creative brief."""
    brand_name = (_as_text(brief.get("brand_name")).strip()
                  or title_fallback.replace(" — Campaign Brand Kit", "") or "Brand")
    product_name = _as_text(brief.get("product_name")).strip() or "Not specified"
    tagline = (_as_text(brief.get("tagline")).strip()
               or _as_text(brief.get("key_benefit")).strip() or "Not specified")
    audience = _as_text(brief.get("audience")).strip() or "Not specified"
    voice = _as_text(brief.get("voice")).strip() or "Not specified"
    tone = _as_text(brief.get("tone")).strip() or "Not specified"
    values = _as_text(brief.get("values")).strip() or "Not specified"
    visual_language = _as_text(brief.get("visual_language")).strip()
    typography = _as_text(brief.get("typography")).strip()
    if not typography:
        typography_lines = [
            raw.strip() for raw in _brief_document_text(brief).splitlines()
            if any(token in raw.lower() for token in ("typography", "font", "typeface", "manrope", "inter"))
        ]
        typography = " ".join(typography_lines[:4])
    mandatory = _as_text(brief.get("mandatory_treatments")).strip()
    avoid = _as_text(brief.get("negative_prompts")).strip()

    palette = brief.get("color_palette")
    palette_lines: list[str] = []
    if isinstance(palette, dict):
        palette_lines = [f"- **{name}:** `{value}`" for name, value in palette.items() if value not in (None, "")]
    elif isinstance(palette, list):
        palette_lines = [f"- {_as_text(value)}" for value in palette if _as_text(value).strip()]
    if not palette_lines:
        document_text = _brief_document_text(brief)
        for raw in document_text.splitlines():
            if re.search(_HEX_PATTERN, raw):
                labelled = re.sub(f"({_HEX_PATTERN})", lambda match: f"`{match.group(1).lower()}`", raw.strip())
                palette_lines.append(f"- {labelled}")
        palette_lines = palette_lines[:12]
    palette_text = "\n".join(palette_lines) or "- No explicit palette supplied. Use colors sampled from the official logo conservatively until the brand owner adds exact values."

    asset_summary = brief.get("brand_visual_assets") if isinstance(brief.get("brand_visual_assets"), dict) else {}
    asset_lines = []
    for item in asset_summary.values():
        if not isinstance(item, dict) or not item.get("count"):
            continue
        asset_lines.append(f"- {item.get('label') or 'Brand asset'}: {item.get('count')}")
    assets_text = "\n".join(asset_lines) or "- Official logo is the required identity anchor. Additional references are optional and campaign-dependent."

    return f"""# {brand_name} — Brand Creative Brief
> The durable creative direction for agency and AI-assisted campaign production. It defines identity, taste, truth, and boundaries without prescribing a fixed layout.

## 1. Brand Foundation

- **Core promise:** {tagline}
- **Primary product/service:** {product_name}
- **Primary audience:** {audience}
- **Voice:** {voice}
- **Tone:** {tone}
- **Values:** {values}

## 2. Visual Identity

### Approved palette
{palette_text}

### Visual language
{visual_language or "Use the official logo, palette, audience, and campaign objective as the base. The agency has latitude to establish composition, imagery, lighting, and channel-specific art direction."}

### Typography
{typography or "Use accessible, legible typography appropriate to the channel. Do not imply ownership of unlicensed fonts."}

## 3. Creative Assets

{assets_text}

- Apply the official logo as a real source asset in post-production; never ask an image model to redraw it.
- Treat aesthetic references as guidance, not mandatory layouts.
- Use exact product, packaging, person, character, property, vehicle, or interface assets only when the campaign claims to depict them.

## 4. Creative Latitude and Boundaries

**Agency latitude:** The agency may create new compositions, environments, visual metaphors, crops, lighting, and channel adaptations consistent with this brief.

**Mandatory treatments:** {mandatory or "Preserve logo integrity, factual accuracy, legibility, and approved campaign claims."}

**Avoid:** {avoid or "Distorted logos, invented product facts, fabricated properties or people presented as real, unreadable text, and unapproved claims."}

## 5. Campaign Truth

Campaign-specific offers, claims, audiences, products, disclosures, and immutable source assets come from the active campaign. Missing campaign-specific evidence blocks only that deliverable—not the whole brand.

## 6. Governance

- Brand-folder authorization means assets in the selected Brand Kit folder are approved for production use.
- Human approval occurs on campaign direction and finished creative, not on every source image.
- Update this brief when identity, positioning, visual language, or legal boundaries change materially.
- Templates are optional production aids for intentionally locked layouts; they are not a universal readiness requirement.
"""


def _campaign_brand_kit_markdown(brief: dict, title_fallback: str) -> str:
    """Compatibility entry point for deterministic Brand Creative Brief generation."""
    return _brand_creative_brief_markdown(brief, title_fallback)


@router.get("/onboarding/brand-kit/latest", response_model=WorkspaceDocumentOut, responses={404: {"description": "Not found"}, 422: {"description": "brand_id required in multi-brand workspace"}})
async def get_latest_campaign_brand_kit(
    status: str | None = None,
    brand_id: NullableUUID = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Return the latest Brand Creative Brief document, including full Markdown content."""
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
        raise HTTPException(status_code=404, detail="Brand Creative Brief not found")
    return _document_out(doc)


def _asset_category(files: list, label: str) -> dict:
    count = sum(1 for f in files if isinstance(f, dict) and f.get("id"))
    return {"label": label, "count": count}


async def _brand_drive_asset_folder_metadata(db: AsyncSession, brand_id) -> dict:
    _empty = {"drive_connected": False, "brand_mark_configured": False, "brand_visual_assets": {}}
    if not brand_id:
        return _empty
    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand_id,
            SocialConnection.platform == "google_drive",
            SocialConnection.status == "connected",
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not row:
        return _empty

    meta = dict(row.token_meta_json or {})
    folder_id = str(meta.get("drive_root_folder_id") or "").strip()
    validation = meta.get("imprint_asset_validation") if isinstance(meta.get("imprint_asset_validation"), dict) else {}

    logo_files = validation.get("logo_files") or []
    first_logo = next((f for f in logo_files if isinstance(f, dict) and f.get("id")), None)

    result: dict = {
        "drive_connected": True,
        "brand_mark_configured": bool(first_logo),
        "brand_visual_assets": {
            "brand_mark":         _asset_category(logo_files, "Brand Mark"),
            "brand_character":    _asset_category(
                validation.get("brand_character_files") or validation.get("mascot_files") or [],
                "Brand Character",
            ),
            "hero_imagery":       _asset_category(validation.get("hero_imagery_files") or [], "Hero Imagery"),
            "lifestyle":          _asset_category(validation.get("lifestyle_files") or [], "Lifestyle & People"),
            "location":           _asset_category(validation.get("location_files") or [], "Location & Space"),
            "creative_references": _asset_category(validation.get("creative_reference_files") or [], "Creative References"),
            "supporting_visuals": _asset_category(validation.get("visual_asset_files") or [], "Supporting Visuals"),
        },
    }
    if folder_id:
        result["drive_root_folder_id"] = folder_id
        result["drive_root_name"] = meta.get("drive_root_name") or folder_id
    if first_logo:
        result["brand_mark_file_id"] = str(first_logo.get("id") or "")
        result["brand_mark_file_name"] = str(first_logo.get("name") or "")
    return result


@router.post("/onboarding/brand-kit", response_model=BrandKitResponse, status_code=201)
async def generate_campaign_brand_kit(
    body: BrandKitRequest = BrandKitRequest(),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Generate the required Brand Creative Brief and store it as a draft document."""
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
                detail="Brand profile must include brand voice, at least one product, and at least one audience before generating the Brand Creative Brief",
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
                detail="Brand profile must include brand, at least one product, and at least one audience before generating the Brand Creative Brief",
            )
        brief = await _resolve_brief(db, ws, brief_override)
        run_brand_id = None
        title_fallback = f"{ws.name} — Campaign Brand Kit"

    asset_metadata = await _brand_drive_asset_folder_metadata(db, run_brand_id)

    # Generate synchronously and deterministically. This onboarding step must not
    # be blocked by external LLM quota, slow provider fallback chains, or nginx
    # timeouts. The artifact is a practical draft and can be edited/approved by
    # the operator.
    content = _campaign_brand_kit_markdown({
        **brief,
        "brand_visual_assets": asset_metadata.get("brand_visual_assets") or {},
    }, title_fallback)
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
        metadata_json=ensure_template_manifest({
            "version": "brand_creative_brief.v1-draft",
            "artifact_kind": "brand_creative_brief",
            "generated_by_module": "onboarding.brand_guidelines",
            "generation_mode": "deterministic_local",
            "required_for_onboarding": True,
            **asset_metadata,
            "summary_fields": [
                "brand_foundation",
                "visual_identity",
                "creative_assets",
                "creative_boundaries",
                "campaign_truth",
            ],
        }),
        source_run_id=run.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return BrandKitResponse(run_id=str(run.id), document=_document_out(doc))
