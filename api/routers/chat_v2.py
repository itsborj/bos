"""CMO v2 — thin CMO loop with native tool calls.

Architecture (Smith pattern):
    LOOP(Goal: Input(state) : Evaluate(gap?) : Act)

    chat_v2.py        — thin loop + models + endpoints (this file)
    cmo_providers.py  — unified LLM provider interface (streaming, retry, fallback)
    cmo_tools.py      — tool registry from manifest + execution + hooks

Anti-bloat: this file owns only the loop. Context is skills, not dataclasses.
Tools come from the manifest. Providers are a separate file. No domain objects.

Endpoints:
  GET  /cmo_v2/test        — serve test HTML page
  POST /cmo_v2/chat        — thin CMO loop with native tools
  POST /cmo_v2/chat/stream — SSE streaming version
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from attachment_context import (
    brief_fields as _attachment_brief_fields,
    enrich_drive_references as _enrich_drive_references,
    ensure_reference_identity as _ensure_reference_identity,
    format_for_prompt as _format_reference_context,
    persist_chat_references as _persist_chat_references,
    _shrink_image_for_vision, _VISION_MAX_BYTES,
)
from config import get_settings
from data_hygiene import reject_fuzzer_garbage
from db import get_db, get_session_factory
from routers.cmo_providers import call_cmo, resolve_provider
from routers.brands import resolve_brand
from routers.cmo_tools import (
    build_system_prompt, build_tools,
    execute_all, load_campaign_goal, preflight_tool_call,
)
from routers.workspace import get_singleton

router = APIRouter(prefix="/cmo_v2", tags=["cmo_v2"])
logger = logging.getLogger("bos.cmo_v2")

_MAX_STEPS = 10
_TEST_HTML_PATH = Path(__file__).parent / "chat_v2_test.html"


# ── Tool result predicates ───────────────────────────────────────────────────

def _is_setup_blocker_result(result: dict) -> bool:
    """Deterministic setup blockers that should stop the loop."""
    return (
        result.get("artifact_type") == "setup_blocker"
        or result.get("reason_code") in {"postcraft_preflight_failed", "storyboard_preflight_failed"}
    )


def _is_report_artifact_result(result: dict) -> bool:
    artifact_type = str(result.get("artifact_type") or "")
    module_id = str(result.get("module_id") or result.get("tool") or "")
    return bool(result.get("report_content")) or "report" in artifact_type or "insights.report" in module_id


def _artifact_ref_from_tool_result(result: dict) -> dict | None:
    """Build the complete CMO stream artifact ref shape expected by the UI."""
    run_id = result.get("run_id")
    if not run_id:
        return None
    raw_type = str(result.get("artifact_type") or "draft_artifact")
    if _is_setup_blocker_result(result):
        artifact_type = "setup_blocker"
    elif _is_report_artifact_result(result):
        artifact_type = "intelligence_artifact"
    elif raw_type in {"draft_artifact", "plan_artifact", "intelligence_artifact", "action_result", "decision_artifact"}:
        artifact_type = raw_type
    else:
        artifact_type = "draft_artifact"

    tool = str(result.get("tool") or result.get("module_id") or "")
    if artifact_type == "setup_blocker":
        renderer = "artifact_detail"
    elif "storyboard" in tool:
        renderer = "storyboard_preview"
    elif "postcraft" in tool or raw_type == "post_image":
        renderer = "approval_bundle"
    else:
        renderer = "artifact_detail"

    return {
        "artifact_id": run_id,
        "title": result.get("artifact_title") or result.get("summary") or "Generated artifact",
        "type": artifact_type,
        "status": "failed" if result.get("status") == "failed" else "pending_review",
        "renderer": renderer,
        "workspace_url": f"/workspace/artifacts/{run_id}",
    }


# ── Models ───────────────────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    role: str
    text: str


class ChatV2Reference(BaseModel):
    id: str | None = None
    kind: str = "text"
    source: str = "inline"
    title: str | None = None
    notes: str | None = None
    text: str | None = None
    drive_file_id: str | None = None
    drive_file_name: str | None = None
    drive_web_view_link: str | None = None
    mime_type: str | None = None
    thumbnail_link: str | None = None
    storage_url: str | None = None
    sha256: str | None = None
    metadata_json: dict | None = None
    extraction_status: str | None = None
    extraction_error: str | None = None
    extracted_chars: int | None = None
    extraction_json: Any = None
    variables_json: dict | None = None


class ChatV2Request(BaseModel):
    message: str
    history: list[HistoryItem] = []
    brand_id: str | None = None
    campaign_id: str | None = None
    conversation_id: str | None = None
    references: list[ChatV2Reference] = []


class ChatV2Response(BaseModel):
    reply: str
    tool_calls: list[dict] = []
    provider: str | None = None
    model: str | None = None
    campaign_id: str | None = None
    latency_ms: int = 0
    steps: int = 0


class DeleteChatResponse(BaseModel):
    conversation_id: str
    deleted_references: int


# ── Context ──────────────────────────────────────────────────────────────────

def _is_council_command(message: str) -> bool:
    return message.strip().lower().startswith("@council")


async def _workspace_brands(db: AsyncSession, ws) -> list:
    if not ws or not hasattr(db, "execute"):
        return []
    from models.workspace import Brand
    from sqlalchemy import select
    return (await db.execute(
        select(Brand).where(Brand.workspace_id == ws.id).order_by(Brand.name.asc())
    )).scalars().all()


async def _resolve_active_brand(db: AsyncSession, ws, brand_id: str | None, message: str = ""):
    """Resolve brand: explicit ID → single-brand default → exact name match → None."""
    if brand_id:
        brand = await resolve_brand(db, brand_id)
        if brand:
            return brand

    all_brands = await _workspace_brands(db, ws)
    if len(all_brands) == 1:
        return all_brands[0]

    # Exact brand-name match in message (unambiguous only)
    msg_lower = (message or "").lower()
    if msg_lower and len(all_brands) > 1:
        matches = [b for b in all_brands if b.name and b.name.lower() in msg_lower]
        if len(matches) == 1:
            return matches[0]

    return None


def _is_affirmative_approval(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    approvals = {
        "yes", "yes proceed", "proceed", "go", "go ahead", "approved", "approve",
        "looks good", "good", "good enough", "do it", "render it", "make it",
        "use that", "great", "perfect", "love it", "continue", "continue please",
    }
    return text in approvals or ("proceed" in text and len(text) <= 80)


def _is_retry_request(message: str) -> bool:
    text = re.sub(r"\s+", " ", (message or "").strip().lower())
    if not text:
        return False
    retries = {
        "retry",
        "retry please",
        "please retry",
        "try again",
        "try that again",
        "run it again",
        "rerun",
        "rerender",
        "render again",
        "generate again",
    }
    return text in retries


def _history_item_role_text(item: Any) -> tuple[str, str]:
    if isinstance(item, dict):
        return str(item.get("role") or ""), str(item.get("text") or item.get("content") or "")
    return str(getattr(item, "role", "") or ""), str(getattr(item, "text", None) or getattr(item, "content", None) or "")


def _brand_from_recent_foundation_draft(history: list[HistoryItem] | None, brands: list[Any]):
    """Recover the brand bound to the recent creative draft being approved/retried."""
    if not history:
        return None
    recent = [h for h in history[-6:] if _history_item_role_text(h)[0] != "user" and _history_item_role_text(h)[1]]
    for item in reversed(recent):
        text = _history_item_role_text(item)[1]
        lowered = text.lower()
        is_postcraft_style_draft = (
            ("**headline:**" in lowered and "**body copy:**" in lowered and "**visual direction:**" in lowered)
            or _looks_like_postcraft_draft(text)
        )
        is_storyboard_style_draft = _looks_like_storyboard_draft(text)
        if not (is_postcraft_style_draft or is_storyboard_style_draft):
            continue
        matches = [b for b in brands if getattr(b, "name", None) and b.name.lower() in lowered]
        if len(matches) == 1:
            return matches[0]
    return None


def _campaign_name_candidates(name: str) -> list[str]:
    text = str(name or "").strip()
    if not text:
        return []
    out: list[str] = []
    for part in [text, *re.split(r"\s*[—\-:\|]\s*", text)]:
        token = re.sub(r"\s+", " ", part.strip().lower())
        if token and token not in out and len(token) >= 3:
            out.append(token)
    return out


def _campaign_from_text(text: str, campaigns: list[Any]):
    hay = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not hay:
        return None
    matches: list[Any] = []
    for campaign in campaigns:
        name = str(getattr(campaign, "name", "") or "")
        candidates = _campaign_name_candidates(name)
        if any(candidate in hay for candidate in candidates):
            matches.append(campaign)
    return matches[0] if len(matches) == 1 else None


def _campaign_from_recent_user_messages(history: list[HistoryItem] | None, campaigns: list[Any], *, limit: int = 12):
    if not history:
        return None
    for item in reversed(history[-limit:]):
        role, text = _history_item_role_text(item)
        if role != "user" or not text:
            continue
        matched = _campaign_from_text(text, campaigns)
        if matched:
            return matched
    return None


def _campaign_from_recent_approval_context(history: list[HistoryItem] | None, campaigns: list[Any]):
    """Recover campaign context for a terse approval like 'proceed'.

    Only rebound when the immediately previous assistant message is a creative
    draft that is meant to be approved/rendered now. This avoids leaking old
    campaign mentions into unrelated approvals.
    """
    if not history:
        return None
    latest_draft = _latest_assistant_text_if_immediate(history)
    if not latest_draft:
        return None
    if not (_looks_like_storyboard_draft(latest_draft) or _looks_like_postcraft_draft(latest_draft)):
        return None
    return _campaign_from_recent_user_messages(history, campaigns, limit=8)


def _looks_like_same_campaign_reference(message: str) -> bool:
    text = re.sub(r"\s+", " ", str(message or "").strip().lower())
    if not text:
        return False
    phrases = (
        "same campaign",
        "that campaign",
        "that same campaign",
        "this campaign",
        "same one",
    )
    return any(phrase in text for phrase in phrases)


async def _active_campaigns_for_brand(db: AsyncSession, ws, brand_uuid: UUID | None, *, limit: int = 12):
    if not ws or not brand_uuid:
        return []
    from campaign import db as campaign_db

    return await campaign_db.active_campaigns(
        db, workspace_id=ws.id, brand_id=brand_uuid, limit=limit
    )


async def _resolve_brand_and_campaign(db: AsyncSession, ws, body: ChatV2Request):
    """Resolve brand + active campaign_id once before context assembly.

    ChatV2 no longer uses deterministic campaign/report/daily/draft renderers;
    this resolver only establishes safe brand/campaign scope for the CMO loop
    and for tool execution.
    """
    from models.workspace import Brand
    from sqlalchemy import select
    from campaign import db as campaign_db

    brand = await _resolve_active_brand(db, ws, body.brand_id, body.message)
    if ws and (_is_affirmative_approval(body.message) or _is_retry_request(body.message)):
        draft_brand = _brand_from_recent_foundation_draft(body.history, await _workspace_brands(db, ws))
        if draft_brand and (not brand or draft_brand.id != brand.id):
            logger.info(
                "Creative brand rebound from %s to draft brand %s",
                getattr(brand, "name", None), draft_brand.name,
            )
            brand = draft_brand
    brand_uuid = brand.id if brand else None
    brand_name = brand.name if brand else ""

    # Only active campaigns can be the live CMO execution context. A stale
    # localStorage campaign_id from a completed/archived campaign must not turn
    # a plural inventory question ("what campaigns do we have") into a selected
    # campaign continuation brief.
    resolved_campaign_id = None
    active_campaigns: list[Any] = []
    if brand_uuid and ws:
        try:
            active_campaigns = await _active_campaigns_for_brand(db, ws, brand_uuid)
        except Exception:
            logger.debug("Could not load active campaigns", exc_info=True)
            active_campaigns = []

    if body.campaign_id and brand_uuid and ws:
        try:
            cid = UUID(str(body.campaign_id))
            selected = await campaign_db.get_campaign_record(
                db, cid, workspace_id=ws.id, brand_id=brand_uuid
            )
            if selected and selected.status != "active":
                selected = None
            if selected:
                resolved_campaign_id = str(selected.id)
        except (TypeError, ValueError):
            resolved_campaign_id = None

    if not resolved_campaign_id and active_campaigns:
        selected_from_message = _campaign_from_text(body.message, active_campaigns)
        if selected_from_message:
            resolved_campaign_id = str(selected_from_message.id)

    if not resolved_campaign_id and active_campaigns and _looks_like_same_campaign_reference(body.message):
        selected_from_history = _campaign_from_recent_user_messages(body.history, active_campaigns)
        if selected_from_history:
            resolved_campaign_id = str(selected_from_history.id)

    if not resolved_campaign_id and active_campaigns and _is_affirmative_approval(body.message):
        selected_from_history = (
            _campaign_from_recent_approval_context(body.history, active_campaigns)
            or _campaign_from_recent_user_messages(body.history, active_campaigns)
        )
        if selected_from_history:
            resolved_campaign_id = str(selected_from_history.id)

    if not resolved_campaign_id and active_campaigns and _is_retry_request(body.message):
        selected_from_history = (
            _campaign_from_recent_approval_context(body.history, active_campaigns)
            or _campaign_from_recent_user_messages(body.history, active_campaigns)
        )
        if selected_from_history:
            resolved_campaign_id = str(selected_from_history.id)

    campaign_goal = await load_campaign_goal(
        db, resolved_campaign_id,
        workspace_id=ws.id if ws else None,
        brand_id=brand_uuid,
    )

    # Auto-resolve single active campaign
    if not resolved_campaign_id and len(active_campaigns) == 1:
        resolved_campaign_id = str(active_campaigns[0].id)
        campaign_goal = await load_campaign_goal(
            db, resolved_campaign_id, workspace_id=ws.id if ws else None, brand_id=brand_uuid,
        ) or campaign_goal

    return brand, brand_uuid, brand_name, resolved_campaign_id, campaign_goal


async def _prepare_context(
    db: AsyncSession, ws, body: ChatV2Request, settings,
    *, brand, brand_uuid, brand_name: str, resolved_campaign_id: str | None, campaign_goal: str,
):
    """Shared context loading for both endpoints. Brand/campaign already resolved by caller."""
    from models.workspace import Brand
    from sqlalchemy import select

    brands_list = await _workspace_brands(db, ws)

    brand_obj = None
    if brand_uuid:
        brand_obj = (await db.execute(select(Brand).where(Brand.id == brand_uuid))).scalar_one_or_none()

    # ── References ──────────────────────────────────────────────────────
    refs = [r.model_dump() for r in (body.references or [])]
    for ref in refs:
        _ensure_reference_identity(ref)
    if refs:
        brand_id_str = str(brand_uuid) if brand_uuid else None
        await _enrich_drive_references(refs, brand_id_str, db, settings)
        await _persist_chat_references(
            refs,
            workspace_id=ws.id if ws else None,
            brand_id=brand_uuid,
            conversation_id=body.conversation_id,
            campaign_id=resolved_campaign_id,
            db=db,
        )
        await db.commit()

    reference_context = _format_reference_context(refs) if refs else ""

    # ── System prompt: instructions + tools, then compact prompt context ──
    # Campaign truth is not assembled here; CMO must use Campaign V2 tools/rows.
    from plugin_loader import get_active_plugin_ids
    from services.working_context import build_working_context, working_context_prompt_block
    active_plugin_ids = await get_active_plugin_ids(db, brand_uuid)
    tools = build_tools(db, active_plugin_ids=active_plugin_ids)
    working_doc = await build_working_context(
        db, ws, brand_obj, resolved_campaign_id,
        references_text=reference_context,
    )
    system_prompt = build_system_prompt(brand_name, tools)
    system_prompt += "\n\n" + working_context_prompt_block(working_doc)

    history: list[dict] = []
    for h in body.history[-16:]:
        history.append({"role": "user" if h.role == "user" else "assistant", "content": h.text})
    return brand_name, brand_uuid, campaign_goal, resolved_campaign_id, system_prompt, history, brands_list, refs


# Campaign inventory, context, reports, and mutations stay on the CMO tool loop.


def _latest_assistant_text_if_immediate(history: list[dict] | list[HistoryItem] | None) -> str | None:
    """Return the immediately previous visible assistant text, if any.

    Approval short-circuits are intentionally strict: an affirmative user reply
    may only approve the assistant message directly above it. Scanning past
    intervening user turns can re-run an older expensive artifact (e.g.
    storyboard.render) when the operator says "yes" to something else.
    """
    if not history:
        return None
    for item in reversed(history):
        role, raw_text = _history_item_role_text(item)
        text = raw_text.strip()
        if not text:
            continue
        if role == "user":
            return None
        return text
    return None


def _looks_like_postcraft_draft(text: str) -> bool:
    lowered = str(text or "").lower()
    if not lowered:
        return False
    plain = all(token in lowered for token in ("template:", "format:", "headline:", "cta:", "visual direction:"))
    markdown = all(token in lowered for token in ("**headline:**", "**visual direction:**"))
    return plain or markdown



def _looks_like_storyboard_draft(text: str) -> bool:
    lowered = str(text or "").lower()
    has_storyboard = "storyboard" in lowered or "shot 1" in lowered or "voiceover:" in lowered or "0–3s" in lowered or "scene 1" in lowered
    has_enough_detail = len(text) >= 40 and ("shot" in lowered or "scene" in lowered or "voiceover" in lowered or "text overlay" in lowered or "visual:" in lowered)
    return has_storyboard and has_enough_detail


def _field_from_draft(text: str, label: str) -> str:
    pattern = rf"(?:^|\n)\s*(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*:\s*(.*?)(?=\n\s*(?:\*\*)?(?:Template|Format|Headline|Subheadline|Body copy|CTA|Visual direction|Asset/brand notes)(?:\*\*)?\s*:|\Z)"
    m = re.search(pattern, text or "", re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    value = m.group(1).strip()
    value = re.sub(r"^\*\*|\*\*$", "", value).strip()
    return value


def _postcraft_args_from_draft(text: str) -> dict:
    return {
        "render_approved": True,
        "approved_draft": True,
        "image_quality": "high",
        "postcraft_text": text.strip(),
        "template_type": "promo",
        "creative_direction": _field_from_draft(text, "Template"),
        "post_format": _field_from_draft(text, "Format") or "square",
        "headline": _field_from_draft(text, "Headline"),
        "subheadline": _field_from_draft(text, "Subheadline"),
        "body_copy": _field_from_draft(text, "Body copy"),
        "cta_text": _field_from_draft(text, "CTA"),
        "visual_direction": _field_from_draft(text, "Visual direction"),
        "asset_brand_notes": _field_from_draft(text, "Asset/brand notes"),
    }


async def _approval_continuation_tool_call(
    message: str,
    history: list[dict],
    tools: dict,
) -> dict | None:
    """Return a plugin tool call for terse approval of an immediately prior draft.

    This prevents the CMO from saying "rendering now" without actually starting
    the plugin execution. The plugin still owns execution/preflight; this only
    converts an explicit approval continuation into the matching tool call.
    """
    normalized = re.sub(r"\s+", " ", str(message or "").strip().lower())
    # Only force terse one-word/stock approvals. Compound approvals still go
    # through the CMO model so it can incorporate extra operator intent.
    if normalized not in {"continue", "continue please", "proceed", "go", "go ahead", "approved", "approve", "yes"}:
        return None
    latest_draft = _latest_assistant_text_if_immediate(history)
    if not latest_draft:
        return None
    if _looks_like_postcraft_draft(latest_draft) and "postcraft_render" in tools:
        return {"id": "forced_postcraft_render", "name": "postcraft_render", "args": _postcraft_args_from_draft(latest_draft)}
    if _looks_like_storyboard_draft(latest_draft) and "storyboard_render" in tools:
        return {
            "id": "forced_storyboard_render",
            "name": "storyboard_render",
            "args": {"storyboard_text": latest_draft.strip(), "render_approved": True, "approved_draft": True, "image_quality": "high"},
        }
    return None


# ── User message builder ─────────────────────────────────────────────────────

def _build_user_message_content(text: str, references: list[dict]) -> "str | list":
    """Return plain string or OpenAI-style multipart with vision images."""
    import re as _re
    import base64 as _b64

    image_refs = [
        r for r in (references or [])
        if r.get("kind") == "image" and r.get("text")
        and r.get("extraction_status") != "vision_ready"
    ][:4]
    if not image_refs:
        return text

    parts: list[dict] = [{"type": "text", "text": text}]
    for ref in image_refs:
        raw = (ref.get("text") or "").strip()
        if raw.startswith("data:"):
            m = _re.match(r"data:([^;]+);base64,(.+)", raw, _re.DOTALL)
            if m:
                mime, b64 = m.group(1), m.group(2)
            else:
                continue
        else:
            mime = ref.get("mime_type") or "image/png"
            b64 = raw
        raw_bytes = len(b64) * 3 // 4
        if raw_bytes > _VISION_MAX_BYTES:
            try:
                resized_data, mime = _shrink_image_for_vision(_b64.b64decode(b64), mime)
                b64 = _b64.b64encode(resized_data).decode()
            except Exception:
                continue
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })
    return parts


async def _call_prepare_context(
    db: AsyncSession,
    ws,
    body: ChatV2Request,
    settings,
    *,
    brand,
    brand_uuid,
    brand_name: str,
    resolved_campaign_id: str | None,
    campaign_goal: str,
):
    """Call _prepare_context while tolerating older test doubles.

    Production _prepare_context receives pre-resolved brand/campaign state so we
    don't repeat DB lookups. Some endpoint tests monkeypatch the old 4-argument
    shape; keep that contract harmless without hiding real TypeErrors from the
    production function.
    """
    sig = inspect.signature(_prepare_context)
    if "brand" not in sig.parameters:
        return await _prepare_context(db, ws, body, settings)
    return await _prepare_context(
        db, ws, body, settings,
        brand=brand, brand_uuid=brand_uuid, brand_name=brand_name,
        resolved_campaign_id=resolved_campaign_id, campaign_goal=campaign_goal,
    )


# ── The loop ─────────────────────────────────────────────────────────────────

def _tool_progress_label(tool_call: dict, tools: dict) -> str:
    """Operator-facing progress label for long-running CMO tool calls.

    The frontend turns these labels into the same pipeline status banner used by
    approval-bundle revisions. Keep this deterministic for expensive media
    tools; generic labels like "Run artifact action" make chat look frozen.
    """
    name = str((tool_call or {}).get("name") or "")
    args = (tool_call or {}).get("args") or {}
    tool_def = tools.get(name, {}) if isinstance(tools, dict) else {}
    module_id = str(tool_def.get("module_id") or "")
    action = str(args.get("action") or "").lower() if isinstance(args, dict) else ""
    haystack = " ".join([name, module_id, action]).lower()

    if "storyboard.motion" in haystack or "previs" in haystack or action == "generate_video":
        return "Previs Motion video generation in progress"
    if name == "storyboard_render" or module_id == "storyboard.render":
        return "Storyboard image generation in progress"

    label = str(tool_def.get("label") or name or "tool")
    return f"Running {label}…"


async def _creative_campaign_preflight(
    db: AsyncSession,
    *,
    workspace_id: UUID | None,
    brand_uuid: UUID | None,
    campaign_uuid: UUID | None,
    tool_call: dict,
    tools: dict,
) -> dict | None:
    if campaign_uuid or not workspace_id or not brand_uuid:
        return None

    name = str((tool_call or {}).get("name") or "")
    args = (tool_call or {}).get("args") or {}
    tool_def = tools.get(name, {}) if isinstance(tools, dict) else {}
    module_id = str(tool_def.get("module_id") or "")
    action = str(args.get("action") or "").lower() if isinstance(args, dict) else ""

    needs_campaign = (
        module_id in {"postcraft.render", "storyboard.render"}
        or (name == "run_artifact_action" and action == "generate_video")
    )
    if not needs_campaign:
        return None

    if name == "run_artifact_action":
        source_run_id = str(args.get("source_run_id") or args.get("run_id") or "").strip()
        if source_run_id:
            try:
                from models.run import Run
                source = (await db.execute(select(Run).where(Run.id == UUID(source_run_id)))).scalar_one_or_none()
                if source and source.campaign_id:
                    return None
            except Exception:
                logger.debug("Could not inspect source run for campaign preflight", exc_info=True)

    active_campaigns = await _active_campaigns_for_brand(db, type("_Ws", (), {"id": workspace_id})(), brand_uuid, limit=6)
    if len(active_campaigns) == 1:
        return None

    reason_code = "active_campaign_required" if not active_campaigns else "campaign_selection_required"
    error = (
        "Creative execution requires an active campaign for this brand."
        if not active_campaigns else
        "Campaign alignment is ambiguous. Read the relevant Campaign V2 record with campaign_read, then retry the creative action."
    )
    return {
        "tool": name,
        "module_id": module_id or name,
        "input": args,
        "status": "failed",
        "latency_ms": 0,
        "reason_code": reason_code,
        "error": error,
        "available_campaigns": [
            {"id": str(c.id), "name": str(c.name or "")}
            for c in active_campaigns
        ],
    }


async def _cmo_loop(
    message: str,
    history: list[dict],
    brand_name: str,
    brand_uuid: UUID | None,
    campaign_goal: str,
    system_prompt: str,
    references: list[dict],
    db: AsyncSession,
    settings,
    provider_config: dict,
    workspace_id: UUID | None = None,
    campaign_id: str | None = None,
    on_text=None,
    on_step=None,
) -> ChatV2Response:
    """Thin CMO loop: evaluate → act → append. One path, no branches.

    LOOP(Goal: Input(state) : Evaluate(gap?) : Act)
    """
    total_start = time.perf_counter()

    from plugin_loader import get_active_plugin_ids
    active_plugin_ids = await get_active_plugin_ids(db, brand_uuid)
    tools = build_tools(db, active_plugin_ids=active_plugin_ids)
    provider_config = {**provider_config, "system_prompt": system_prompt}

    campaign_uuid: UUID | None = None
    if campaign_id:
        try:
            campaign_uuid = UUID(str(campaign_id))
        except (TypeError, ValueError):
            campaign_uuid = None

    reference_brief = _attachment_brief_fields(
        references,
        brand_id=str(brand_uuid) if brand_uuid else None,
        objective=campaign_goal or message,
    ) if references else {}
    tool_extra_brief = {**reference_brief, "_operator_message": message}

    state: list[dict] = list(history)

    all_results: list[dict] = []
    provider = provider_config["provider"]
    model = provider_config["model"]

    # Let the CMO resolve campaign context through Campaign V2 when approval
    # arrives without a selected campaign. The deterministic shortcut is safe
    # only when the session already carries campaign alignment.
    forced_tool_call = (
        await _approval_continuation_tool_call(message, state, tools)
        if campaign_uuid else None
    )
    if forced_tool_call:
        preflight = await _creative_campaign_preflight(
            db,
            workspace_id=workspace_id,
            brand_uuid=brand_uuid,
            campaign_uuid=campaign_uuid,
            tool_call=forced_tool_call,
            tools=tools,
        )
        if preflight:
            return ChatV2Response(
                reply=preflight.get("error") or "Creative execution is blocked by campaign setup.",
                tool_calls=[preflight], provider=provider, model=model,
                campaign_id=str(campaign_uuid) if campaign_uuid else None,
                latency_ms=round((time.perf_counter() - total_start) * 1000), steps=1,
            )
        if on_step:
            on_step(_tool_progress_label(forced_tool_call, tools))
        result = (await execute_all(
            [forced_tool_call], db, settings, tools,
            brand_id=brand_uuid,
            workspace_id=workspace_id,
            campaign_id=campaign_uuid,
            extra_brief=tool_extra_brief,
        ))[0]
        failed = result.get("status") == "failed"
        reply = (
            result.get("error") or result.get("summary") or "Rendering failed."
        ) if failed else (
            "Rendering started. I added the generated artifact to Stream for review."
        )
        return ChatV2Response(
            reply=reply,
            tool_calls=[result], provider=provider, model=model,
            campaign_id=str(campaign_uuid) if campaign_uuid else None,
            latency_ms=round((time.perf_counter() - total_start) * 1000), steps=1,
        )

    state.append({"role": "user", "content": _build_user_message_content(message, references)})

    for step in range(1, _MAX_STEPS + 1):
        logger.info("CMO v2 step %d/%d", step, _MAX_STEPS)

        # EVALUATE
        decision = await call_cmo(state, provider_config, tools, on_text=on_text)
        provider = decision.get("provider") or provider
        model = decision.get("model") or model

        if decision["type"] == "error":
            total_ms = round((time.perf_counter() - total_start) * 1000)
            return ChatV2Response(
                reply=f"Error: {decision['text']}",
                tool_calls=all_results, provider=provider, model=model,
                campaign_id=str(campaign_uuid) if campaign_uuid else None,
                latency_ms=total_ms, steps=step,
            )

        if decision["type"] == "text":
            total_ms = round((time.perf_counter() - total_start) * 1000)
            return ChatV2Response(
                reply=decision["text"],
                tool_calls=all_results, provider=provider, model=model,
                campaign_id=str(campaign_uuid) if campaign_uuid else None,
                latency_ms=total_ms, steps=step,
            )

        # ACT: deduplicate + preflight + execute tool calls
        tool_calls = []
        seen: set[str] = set()
        for tc in decision["tool_calls"]:
            key = json.dumps({"name": tc.get("name"), "args": tc.get("args") or {}}, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                tool_calls.append(tc)

        ordered_results: list[dict | None] = [None] * len(tool_calls)
        executable: list[tuple[int, dict]] = []
        for idx, tc in enumerate(tool_calls):
            creative_scope_preflight = await _creative_campaign_preflight(
                db,
                workspace_id=workspace_id,
                brand_uuid=brand_uuid,
                campaign_uuid=campaign_uuid,
                tool_call=tc,
                tools=tools,
            )
            if creative_scope_preflight:
                ordered_results[idx] = creative_scope_preflight
                continue
            preflight = preflight_tool_call(
                tc["name"], tc.get("args") or {}, tools,
                extra_brief=tool_extra_brief,
                campaign_id=campaign_uuid,
            )
            if preflight:
                ordered_results[idx] = preflight
            else:
                executable.append((idx, tc))

        # Execute tool calls and always feed results back to the CMO. Do not
        # short-circuit setup blockers, report artifacts, or approval-gated
        # artifacts into deterministic prose; if the CMO called a tool, the next
        # LLM step must decide how to explain or continue from that result.
        for idx, tc in executable:
            if on_step:
                on_step(_tool_progress_label(tc, tools))
            result = (await execute_all(
                [tc], db, settings, tools,
                brand_id=brand_uuid,
                workspace_id=workspace_id,
                campaign_id=campaign_uuid,
                extra_brief=tool_extra_brief,
            ))[0]
            ordered_results[idx] = result
            # A CMO-selected Campaign V2 record becomes the live execution
            # context for later tools in this same streamed turn. This keeps
            # campaign choice semantic/model-driven without guessing from user
            # wording or hardcoded audience labels.
            if (
                tc.get("name") == "campaign_read"
                and result.get("status") == "succeeded"
                and not campaign_uuid
            ):
                requested_campaign = str((tc.get("args") or {}).get("campaign_id") or "").strip()
                if requested_campaign and requested_campaign.lower() not in {"all", "active", "both"}:
                    try:
                        campaign_uuid = UUID(requested_campaign)
                    except (TypeError, ValueError):
                        logger.debug("CMO campaign_read returned a non-UUID campaign_id: %s", requested_campaign)

        results = [r for r in ordered_results if isinstance(r, dict)]
        all_results.extend(results)

        # Append assistant turn + tool results to state for next iteration
        state.append({
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": tc["id"], "type": "function",
                "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])},
            } for tc in tool_calls],
        })
        for i, r in enumerate(results):
            # Feed structured tool results back to the CMO, not just prose
            # summaries. IDs such as campaign_id/run_id/snapshot_id are often
            # needed in the final answer and for the next tool call.
            result_payload = {k: v for k, v in r.items() if k != "input"}
            content = json.dumps(result_payload, ensure_ascii=False, default=str)[:5000]
            # Campaign tools should behave like modern agent tools: return
            # structured truth, not a prewritten answer shape. Do not prepend
            # campaign_read's human summary to the model context; let the CMO
            # synthesize from portfolio/campaign JSON.
            if r.get("summary") and r.get("tool") != "campaign_read":
                content = f"{r['summary']}\n{content}"
            if r.get("error") and "error" not in content.lower():
                content += f"\nError: {r['error']}"
            state.append({
                "role": "tool",
                "tool_call_id": tool_calls[i]["id"] if i < len(tool_calls) else "",
                "content": content,
            })

    # Budget exhausted
    completed = [r["tool"] for r in all_results if r["status"] == "succeeded"]
    reply = f"Reached step limit ({_MAX_STEPS}). Completed: {', '.join(completed)}." if completed else f"Reached step limit ({_MAX_STEPS}) without completing any actions."
    total_ms = round((time.perf_counter() - total_start) * 1000)
    return ChatV2Response(
        reply=reply, tool_calls=all_results,
        provider=provider, model=model,
        campaign_id=str(campaign_uuid) if campaign_uuid else None,
        latency_ms=total_ms, steps=_MAX_STEPS,
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.delete("/chat/conversations/{conversation_id}", response_model=DeleteChatResponse)
async def delete_cmo_chat_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Delete server-side rows owned by a browser-stored CMO chat.

    Chat transcripts live in browser localStorage today; the server only keeps
    durable attachment/reference rows keyed by conversation_id.
    """
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    from models.chat_reference import ChatReference

    result = await db.execute(
        sa_delete(ChatReference).where(
            ChatReference.workspace_id == ws.id,
            ChatReference.conversation_id == conversation_id,
        )
    )
    await db.commit()
    deleted = result.rowcount if result.rowcount is not None and result.rowcount > 0 else 0
    return DeleteChatResponse(
        conversation_id=conversation_id,
        deleted_references=int(deleted),
    )


@router.post("/chat", response_model=ChatV2Response)
async def cmo_v2_chat(
    body: ChatV2Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Non-streaming CMO chat with native tool calls."""
    reject_fuzzer_garbage(body.model_dump(), ["body"])
    settings = get_settings()
    ws = await get_singleton(db)

    if _is_council_command(body.message):
        return ChatV2Response(
            reply="Council deliberation is not yet available in v2. Use the main /chat endpoint.",
            latency_ms=0,
        )

    brand, brand_uuid, brand_name, resolved_campaign_id, campaign_goal = await _resolve_brand_and_campaign(db, ws, body)

    provider_config = await resolve_provider(db, ws, settings)
    if not provider_config:
        return ChatV2Response(reply="No LLM provider configured.", latency_ms=0)

    brand_name, brand_uuid, campaign_goal, resolved_campaign_id, system_prompt, history, _brands, refs = await _call_prepare_context(
        db, ws, body, settings,
        brand=brand, brand_uuid=brand_uuid, brand_name=brand_name,
        resolved_campaign_id=resolved_campaign_id, campaign_goal=campaign_goal,
    )
    return await _cmo_loop(
        message=body.message, history=history,
        brand_name=brand_name, brand_uuid=brand_uuid,
        campaign_goal=campaign_goal, system_prompt=system_prompt,
        references=refs,
        db=db, settings=settings, provider_config=provider_config,
        workspace_id=ws.id if ws else None, campaign_id=resolved_campaign_id,
    )


@router.post("/chat/stream")
async def cmo_v2_chat_stream(
    body: ChatV2Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Streaming CMO chat with SSE."""
    reject_fuzzer_garbage(body.model_dump(), ["body"])
    settings = get_settings()
    ws = await get_singleton(db)

    if _is_council_command(body.message):
        async def _council_err():
            yield f"data: {json.dumps({'type': 'reply', 'text': 'Council deliberation is not yet available in v2. Use the main /chat endpoint.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_council_err(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    brand, brand_uuid, brand_name, resolved_campaign_id, campaign_goal = await _resolve_brand_and_campaign(db, ws, body)

    provider_config = await resolve_provider(db, ws, settings)
    if not provider_config:
        async def _err():
            yield f"data: {json.dumps({'type': 'error', 'message': 'No LLM provider configured.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    brand_name, brand_uuid, campaign_goal, resolved_campaign_id, system_prompt, history, _brands, refs = await _call_prepare_context(
        db, ws, body, settings,
        brand=brand, brand_uuid=brand_uuid, brand_name=brand_name,
        resolved_campaign_id=resolved_campaign_id, campaign_goal=campaign_goal,
    )

    async def _stream():
        queue: asyncio.Queue = asyncio.Queue()

        def on_text(text: str):
            queue.put_nowait({"type": "text_delta", "text": text})

        def on_step(label: str):
            queue.put_nowait({"type": "step", "label": label})

        async def _run_loop():
            async with get_session_factory()() as stream_db:
                return await _cmo_loop(
                    message=body.message, history=history,
                    brand_name=brand_name, brand_uuid=brand_uuid,
                    campaign_goal=campaign_goal, system_prompt=system_prompt,
                    references=refs,
                    db=stream_db, settings=settings, provider_config=provider_config,
                    workspace_id=ws.id if ws else None, campaign_id=resolved_campaign_id,
                    on_text=on_text, on_step=on_step,
                )

        task = asyncio.create_task(_run_loop())

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                if task.done():
                    break
        while not queue.empty():
            yield f"data: {json.dumps(queue.get_nowait())}\n\n"

        try:
            result = task.result()
        except Exception as exc:
            logger.error("CMO v2 streaming loop failed", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"
            return

        for tool_result in result.tool_calls:
            artifact_ref = _artifact_ref_from_tool_result(tool_result)
            if artifact_ref:
                yield f"data: {json.dumps({'type': 'module_result', 'artifact_ref': artifact_ref})}\n\n"
        if result.reply:
            yield f"data: {json.dumps({'type': 'reply', 'text': result.reply, 'klar_action': None})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'provider': result.provider, 'model': result.model, 'campaign_id': result.campaign_id, 'latency_ms': result.latency_ms, 'steps': result.steps, 'tool_calls': result.tool_calls}, default=str)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Test page ────────────────────────────────────────────────────────────────

@router.get("/test", response_class=HTMLResponse, include_in_schema=False)
async def cmo_v2_test_page(db: AsyncSession = Depends(get_db)):
    """Serve test page with brand dropdown pre-populated from DB."""
    ws = await get_singleton(db)
    brands = await _workspace_brands(db, ws)
    brand_options = "".join(
        f'<option value="{b.id}">{b.name}</option>' for b in brands
    )
    html = _TEST_HTML_PATH.read_text()
    return HTMLResponse(content=html.replace(
        '<option value="">auto-detect</option>',
        f'<option value="">auto-detect</option>{brand_options}',
    ))
