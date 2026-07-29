from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any
from uuid import UUID

from services.brand_kit_templates import (
    TemplateSelectionError,
    derive_selection_context,
    select_brand_kit_template,
    template_source_drive_id,
    validate_brand_kit_template_id,
)


def _load_drive():
    candidates = [
        Path(__file__).resolve().parent.parent / "google-drive" / "drive_client.py",
        Path("/external_plugins/google-drive/drive_client.py"),
        Path("/app/plugins/google-drive/drive_client.py"),
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location("postcraft_hook_drive_client", str(path))
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError("google-drive/drive_client.py not found in plugin search paths")


def _live_template_source_problem(brief: dict, template: dict) -> dict | None:
    """Verify the selected indexed source live when Drive credentials are present."""
    drive_file_id = template_source_drive_id(template)
    credentials = brief.get("_channel_credentials") if isinstance(brief.get("_channel_credentials"), dict) else {}
    token = str(credentials.get("google_drive_page_token") or credentials.get("page_token") or credentials.get("access_token") or "").strip()
    if not drive_file_id or not token:
        # The final Postcraft Drive download remains the live guard when the
        # normal credential injector did not provide a Drive token here.
        return None
    try:
        drive_mod = _load_drive()
        with drive_mod.DriveClient(token) as client:
            client.get_file_meta(drive_file_id)
    except Exception as exc:
        return {
            "drive_file_id": drive_file_id,
            "live_validation_error": str(exc)[:500],
        }
    return None


def _as_uuid(value: Any) -> UUID | None:
    try:
        if value in (None, "", [], {}):
            return None
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _campaign_key(campaign_db, row) -> UUID:
    try:
        return campaign_db.campaign_key(row)
    except Exception:
        return row.campaign_id or row.id


def _raw(row) -> dict:
    return row.raw_payload if isinstance(getattr(row, "raw_payload", None), dict) else {}


def _first(*values: Any) -> str:
    for value in values:
        if value not in (None, "", [], {}):
            return str(value)
    return ""



def _alignment_from_rows(campaign_db, rows: list[Any]) -> dict:
    if not rows:
        return {}
    first = rows[0]
    raw = _raw(first)
    campaign_json = raw.get("campaign_json") if isinstance(raw.get("campaign_json"), dict) else {}
    raw_sources = [raw, campaign_json]

    def raw_first(*keys: str) -> str:
        for src in raw_sources:
            for key in keys:
                value = src.get(key) if isinstance(src, dict) else None
                if value not in (None, "", [], {}):
                    return str(value)
        return ""

    channels = []
    for row in rows:
        channel = getattr(row, "distribution_channel", None)
        if channel and channel not in channels:
            channels.append(str(channel))

    campaign_id = str(_campaign_key(campaign_db, first))
    campaign_name = _first(getattr(first, "campaign", None), raw_first("name", "campaign"), "Untitled Campaign")
    goal = _first(
        getattr(first, "business_objective", None),
        raw_first("business_objective", "objective", "goal", "initial_intent"),
        getattr(first, "planned_activity", None),
        campaign_name,
    )
    audience = raw_first("audience", "target_audience", "icp", "segment")
    offer = raw_first("offer", "product", "service", "promotion", "cta_offer")
    message_angle = _first(
        raw_first("message_angle", "full_message_angle", "message_focus", "angle"),
        getattr(first, "recommended_action", None),
        getattr(first, "planned_activity", None),
    )

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "goal": goal,
        "objective": goal,
        "business_objective": _first(getattr(first, "business_objective", None), goal),
        "audience": audience,
        "offer": offer,
        "message_angle": message_angle,
        "primary_kpi": _first(getattr(first, "primary_kpi", None), raw_first("primary_kpi", "success_metric")),
        "target": _first(getattr(first, "target", None), raw_first("target")),
        "action_metric": _first(getattr(first, "action_metric", None), raw_first("action_metric")),
        "distribution_channel": channels[0] if channels else _first(getattr(first, "distribution_channel", None)),
        "channels": channels,
        "market": _first(getattr(first, "market", None), raw_first("market")),
        "source": "campaign_rows.v2",
    }


async def _rows_for_explicit_campaign(ctx, campaign_db, campaign_id: UUID) -> list[Any]:
    return await campaign_db.rows_for_campaign(
        ctx.db,
        campaign_id,
        workspace_id=ctx.ws.id if ctx.ws else None,
        brand_id=ctx.brand_id,
        limit=20,
    )


async def _rows_for_single_active_campaign(ctx, campaign_db) -> list[Any]:
    if not ctx.brand_id or not ctx.ws:
        return []
    active = await campaign_db.active_campaigns(
        ctx.db, workspace_id=ctx.ws.id, brand_id=ctx.brand_id, limit=2
    )
    if len(active) != 1:
        return []
    return await campaign_db.rows_for_campaign(
        ctx.db,
        active[0].id,
        workspace_id=ctx.ws.id,
        brand_id=ctx.brand_id,
        limit=20,
    )


def _post_format_from_manifest(fmt: str) -> str:
    mapping = {
        "square_feed": "square",
        "portrait_feed": "portrait_feed",
        "story_reel": "story_reel",
        "landscape": "landscape",
    }
    return mapping.get(str(fmt or ""), str(fmt or ""))


def _base_family_from_template(template: dict, brief: dict) -> str:
    supported = {"promo", "price_card", "photo_hero", "agent_award", "educational"}
    for value in (template.get("base_family"), brief.get("base_family"), brief.get("template_type"), template.get("content_type")):
        text = str(value or "").strip()
        if text in supported:
            return text
    content_type = str(template.get("content_type") or "").strip()
    if content_type == "educational":
        return "educational"
    if content_type in {"testimonial", "brand_story"}:
        return "photo_hero"
    return "promo"


def _template_blocker(code: str, message: str, *, details: dict | None = None) -> dict:
    return {
        "status": "blocked",
        "reason_code": code,
        "message": message,
        "details": details or {},
        "suggested_resolution": "Open Admin → Brands → Brand Kit, approve a fitting template, fix slot metadata/assets, or lower the brand template confidence threshold intentionally.",
    }


def _with_template_blocker(brief: dict, blocker: dict) -> dict:
    enriched = dict(brief)
    enriched["_postcraft_template_blocker"] = blocker
    enriched["template_selection_status"] = "blocked"
    return enriched


def _apply_template_selection(brief: dict, selection) -> dict:
    enriched = dict(brief)
    template = dict(selection.template or {})
    enriched["template_id"] = selection.template_id
    enriched["selected_template_id"] = selection.template_id
    enriched["selection_confidence"] = selection.confidence
    enriched["selection_reason"] = list(selection.reason)
    enriched["brand_kit_template"] = template
    if template.get("format") and not enriched.get("post_format"):
        enriched["post_format"] = _post_format_from_manifest(str(template.get("format") or ""))
    family = _base_family_from_template(template, enriched)
    enriched["base_family"] = enriched.get("base_family") or family
    # Current renderer still expects template_type as a fallback base family.
    # Do not use arbitrary chat Template: labels as identity; template_id above is
    # the approved Brand Kit template identity.
    if not enriched.get("template_type"):
        enriched["template_type"] = family

    drive_file_id = template_source_drive_id(template)
    if drive_file_id:
        brand_kit = dict(enriched.get("brand_kit") or {}) if isinstance(enriched.get("brand_kit"), dict) else {}
        nested_brand_spec = brand_kit.get("brand_spec") if isinstance(brand_kit.get("brand_spec"), dict) else {}
        brand_spec = dict(nested_brand_spec or enriched.get("brand_spec") or {})
        visual_assets = list(brand_spec.get("brand_visual_assets") or brand_spec.get("visual_assets") or [])
        if not any(str(a.get("drive_file_id") or "") == drive_file_id for a in visual_assets if isinstance(a, dict)):
            visual_assets.insert(0, {
                "drive_file_id": drive_file_id,
                "title": template.get("name") or "Approved Brand Kit template",
                "panel_label": f"APPROVED BRAND KIT TEMPLATE — {template.get('name') or selection.template_id}; follow this layout, required slots, and negative rules",
                "placement_role": "approved_template",
                "priority": "approved_brand_kit_template",
            })
        brand_spec["brand_visual_assets"] = visual_assets
        enriched["brand_spec"] = brand_spec
        if brand_kit:
            brand_kit["brand_spec"] = brand_spec
            enriched["brand_kit"] = brand_kit
    return enriched


async def _resolve_brand_template_contract(brief: dict, ctx) -> dict:
    if not ctx.brand_id or str(ctx.module_id or "") != "postcraft.render":
        return brief
    explicit_template_id = str(brief.get("template_id") or "").strip()
    # Templates are optional production aids. Brand identity, official logo,
    # campaign alignment, and creative references are sufficient for generation.
    # Select a template only when the caller explicitly requests one.
    auto_select = bool(brief.get("auto_select_template"))
    if not explicit_template_id and not auto_select:
        return brief
    try:
        if explicit_template_id:
            selection = await validate_brand_kit_template_id(ctx.db, ctx.ws, ctx.brand_id, explicit_template_id)
        else:
            selection_context = brief.get("selection_context") if isinstance(brief.get("selection_context"), dict) else derive_selection_context(brief)
            selection = await select_brand_kit_template(ctx.db, ctx.ws, ctx.brand_id, selection_context)
    except TemplateSelectionError as exc:
        return _with_template_blocker(brief, _template_blocker(exc.code, exc.message, details=exc.details))
    except Exception as exc:
        return _with_template_blocker(brief, _template_blocker("template_selection_error", f"Brand Kit template selection failed: {exc}"))
    live_problem = _live_template_source_problem(brief, dict(selection.template or {}))
    if live_problem:
        return _with_template_blocker(
            brief,
            _template_blocker(
                "approved_template_source_unavailable",
                "The approved Brand Kit template source could not be verified in Google Drive.",
                details=live_problem,
            ),
        )
    try:
        return _apply_template_selection(brief, selection)
    except Exception as exc:
        return _with_template_blocker(brief, _template_blocker("template_application_error", f"Approved Brand Kit template could not be applied to Postcraft render: {exc}"))


async def on_brief_before_dispatch(brief: dict, ctx) -> dict:
    """Postcraft-owned Campaign V2 alignment and Brand Kit template resolver.

    CMO/runs may pass only campaign_id, or no campaign_id when exactly one live
    campaign exists for the brand. Postcraft owns its preflight contract, so it
    resolves the structured alignment object it requires from Campaign rows here.
    """
    if not isinstance(brief, dict) or not str(ctx.module_id or "").startswith("postcraft."):
        return brief

    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    enriched_brief = dict(brief)

    # Caller payloads and Brand Kit metadata are not current Campaign truth.
    # Remove compatibility copies before rebuilding alignment from Campaign DB.
    enriched_brief.pop("campaign_context", None)
    enriched_brief.pop("campaign_alignment", None)
    clean_kit = dict(brand_kit)
    clean_kit.pop("campaign_alignment", None)
    enriched_brief["brand_kit"] = clean_kit

    from campaign import db as campaign_db

    requested_value = enriched_brief.get("campaign_id")
    requested = _as_uuid(requested_value)
    if requested_value and not requested:
        rows = []
    elif requested:
        rows = await _rows_for_explicit_campaign(ctx, campaign_db, requested)
    else:
        rows = await _rows_for_single_active_campaign(ctx, campaign_db)
    if rows:
        alignment = _alignment_from_rows(campaign_db, rows)
        if alignment:
            enriched_brief["campaign_id"] = alignment.get("campaign_id")
            enriched_brief["campaign_name"] = alignment.get("campaign_name")
            enriched_brief["campaign_alignment"] = alignment

    return await _resolve_brand_template_contract(enriched_brief, ctx)
