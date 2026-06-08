"""POST /chat — CMO conversational endpoint."""
from __future__ import annotations

import json
import logging
import re

from collections.abc import AsyncGenerator
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artifacts import ArtifactRef, artifact_ref_from_run
from auth import require_api_key
from capability_manifest import build_dispatchable_manifest, format_manifest_for_prompt, format_manifest_for_brand
from config import get_settings
from db import get_db
from executor import get_adapter, get_platform_key
from memory_events import write_memory_event
from model_overrides import get_backend_override, parse_model_ref
from provider_auth import resolve_stored_provider_credential
from providers.connector_registry import format_connector_status_for_prompt
from routers.backend_settings import resolve_backend_override
from registry import list_all
from skills.loader import format_activated_skill, get_skill, list_skill_manifests
from skills.memory import compile_memory_context, hydrate_memory_slots
from skills.router import route_chat_skills
from models.document import WorkspaceDocument
from models.intent import CampaignIntent, IntentContract
from models.run import Run, RunResult, RunTrace
from models.workspace import Audience, Brand, Campaign, Product
from routers.brands import find_brand_by_name, resolve_brand
from routers.runs import _execute_module, _resolve_brief, execute_declared_run_action
from routers.workspace import get_singleton
from schemas.runs import RunResponse, RunTraceOut

router = APIRouter(tags=["chat"])
logger = logging.getLogger("bos.chat")

_RUN_RE = re.compile(r"RUN:\s*([a-zA-Z0-9_.-]+)")
_ACTION_RE = re.compile(r"ACTION:\s*([0-9a-fA-F-]{36})\s+([a-zA-Z0-9_-]+)")
_ACTION_AUTHORIZATION_RE = re.compile(
    r"\b(approve|approved|apply|publish|post|send|dismiss|revise|redo|update|delete|remove|confirm|yes,? do it|go ahead)\b",
    re.IGNORECASE,
)
# Matches key: value lines immediately following a RUN: directive (until blank line or next RUN:)
_RUN_PARAMS_RE = re.compile(
    r"RUN:\s*([a-zA-Z0-9_.-]+)((?:\n(?![ \t]*RUN\s*:)[ \t]*[a-zA-Z_][a-zA-Z0-9_]*\s*:[^\n]*)*)",
    re.MULTILINE,
)
# Matches blocks of 2+ consecutive lowercase_snake_case key: value lines that appear outside
# any RUN: directive — "orphan params" emitted when the LLM retries or errors mid-generation.
_ORPHAN_PARAM_BLOCK_RE = re.compile(
    r"(?:^[ \t]*[a-z][a-z0-9_]+[ \t]*:[^\n]+)(?:\n[ \t]*[a-z][a-z0-9_]+[ \t]*:[^\n]+)+",
    re.MULTILINE,
)
# ── @council command routing ──────────────────────────────────────────────────
_COUNCIL_RE = re.compile(r"^\s*@council\b", re.IGNORECASE)


def _is_council_command(message: str) -> bool:
    return bool(_COUNCIL_RE.match(message))


def _parse_council_brief(message: str) -> str:
    return _COUNCIL_RE.sub("", message).strip()


# ── @klar command routing ─────────────────────────────────────────────────────
_KLAR_RE = re.compile(r"^\s*@klar\b", re.IGNORECASE)

_SCOPE_KEYS = {"conversation_brand", "execution_brand", "mode", "confidence", "reason"}
_SCOPE_PAIR_RE = re.compile(
    r"(conversation_brand|execution_brand|mode|confidence|reason)\s*:\s*(.*?)(?=\s+(?:conversation_brand|execution_brand|mode|confidence|reason)\s*:|$)",
    re.IGNORECASE,
)


def _is_klar_command(message: str) -> bool:
    return bool(_KLAR_RE.match(message))


def _parse_klar_command(message: str) -> dict:
    """Decompose an @klar message into action + args."""
    body = _KLAR_RE.sub("", message).strip()

    # @klar check brand X / switch to (brand) X
    m = re.match(r"(?:check brand|switch to brand|switch to)\s+(.+)", body, re.IGNORECASE)
    if m:
        return {"action": "brand_switch", "brand_name": m.group(1).strip()}

    # @klar plan [description]
    if re.match(r"plan\b", body, re.IGNORECASE):
        desc = re.sub(r"^plan\s*", "", body, flags=re.IGNORECASE).strip()
        return {"action": "plan", "description": desc}

    # @klar evaluate / evaluate [campaign]
    if re.match(r"evaluate\b", body, re.IGNORECASE):
        target = re.sub(r"^evaluate\s*", "", body, flags=re.IGNORECASE).strip()
        return {"action": "evaluate", "target": target}

    # @klar (what's) pending
    if re.match(r"(what'?s?\s+)?pending", body, re.IGNORECASE):
        return {"action": "pending"}

    # @klar (show) (all) brands
    if re.match(r"(show\s+)?(all\s+)?brands?", body, re.IGNORECASE):
        return {"action": "list_brands"}

    # @klar org — clear brand context, return to org level
    if re.match(r"org\b", body, re.IGNORECASE):
        return {"action": "org"}

    # @klar brief — handled by Stream; stub response
    if re.match(r"brief\b", body, re.IGNORECASE):
        return {"action": "brief"}

    # @klar confirm — confirm a previously drafted plan
    if re.match(r"confirm\b", body, re.IGNORECASE):
        return {"action": "confirm"}

    # @klar run [campaign name or id]
    if re.match(r"run\b", body, re.IGNORECASE):
        target = re.sub(r"^run\s*", "", body, flags=re.IGNORECASE).strip()
        return {"action": "run", "target": target}

    # generic @klar directive — needs brand context
    return {"action": "directive", "text": body}


def _parse_run_inline_params(text: str) -> dict[str, dict[str, str]]:
    """Extract per-module key-value params from lines following each RUN: directive.

    CMO output format:
        RUN: some.module.id
        key1: value one
        key2: value two
    Returns {module_id: {key1: value1, key2: value2}}.
    """
    result: dict[str, dict[str, str]] = {}
    for match in _RUN_PARAMS_RE.finditer(text):
        module_id = match.group(1)
        param_block = match.group(2)
        params: dict[str, str] = {}
        for line in param_block.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key and value:
                params[key] = value
        if params:
            result[module_id] = params
    return result


def _parse_scope_pairs(fragment: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for match in _SCOPE_PAIR_RE.finditer(fragment or ""):
        key = match.group(1).strip().lower()
        value = match.group(2).strip().strip('"\'')
        if key in _SCOPE_KEYS and value:
            parsed[key] = value
    return parsed


def _extract_scope_directive(text: str) -> tuple[dict[str, str], str]:
    """Parse and remove the hidden CMO SCOPE block from a provider reply.

    Providers sometimes compress the block into one line, e.g.
    `SCOPE: conversation_brand: X execution_brand: Y ...`; accept that shape
    so the directive never leaks into visible chat.
    """
    scope: dict[str, str] = {}
    kept: list[str] = []
    in_scope = False

    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("SCOPE:"):
            scope.update(_parse_scope_pairs(stripped.split(":", 1)[1]))
            in_scope = not bool(scope)
            continue
        if in_scope:
            if not stripped:
                in_scope = False
                continue
            inline_pairs = _parse_scope_pairs(stripped)
            if inline_pairs:
                scope.update(inline_pairs)
                continue
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                normalized = key.strip().lower()
                if normalized in _SCOPE_KEYS:
                    scope[normalized] = value.strip().strip('"\'')
                    continue
            in_scope = False
        else:
            # LLM sometimes emits scope keys without SCOPE: prefix — strip those too
            inline_pairs = _parse_scope_pairs(stripped)
            if inline_pairs and all(k in _SCOPE_KEYS for k in inline_pairs):
                scope.update(inline_pairs)
                continue
        kept.append(line)

    return scope, "\n".join(kept)


def _strip_control_directives(text: str) -> str:
    """Remove hidden scope/module/action-control directives from user-visible CMO copy."""
    _scope, without_scope = _extract_scope_directive(text)
    # Strip the full RUN block — the RUN: line AND any indented key:value param lines
    # under it (e.g. caption:, image_prompt:) — so hidden params never leak into the
    # user-visible reply. _RUN_PARAMS_RE matches RUN lines with or without params.
    cleaned = _RUN_PARAMS_RE.sub("", without_scope)
    cleaned = _ORPHAN_PARAM_BLOCK_RE.sub("", cleaned)
    cleaned = _RUN_RE.sub("", cleaned)
    cleaned = _ACTION_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.strip(" \n\t-—")


def _strip_run_directives(text: str) -> str:
    """Backward-compatible wrapper for revision paths."""
    return _strip_control_directives(text)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped



async def _chat_modules(db: AsyncSession, brand_id=None) -> list[dict]:
    """All modules the CMO is allowed to dispatch for this Brand."""
    from plugin_loader import get_active_plugin_ids, get_plugin_for_module

    active_plugin_ids = await get_active_plugin_ids(db, brand_id)
    allowed_module_ids = {
        s.module_id for s in list_skill_manifests()
        if s.allowed_from_chat and s.module_id
    }
    modules: list[dict] = []
    for module in list_all():
        module_id = module.get("id")
        if module_id not in allowed_module_ids:
            continue
        plugin = get_plugin_for_module(module_id)
        if plugin and plugin.manifest.plugin_id not in active_plugin_ids:
            continue
        modules.append(module)
    return modules


def _marketing_plan_module_id() -> str | None:
    """Find the installed native marketing.plan artifact capability from SKILL.md metadata.

    Prefer the Strategy Workflow contract. This keeps @klar plan generic while
    letting SKILL.md metadata, not chat phrase rules, own which module implements
    the top-level planning artifact.
    """
    fallback: str | None = None
    for skill in list_skill_manifests():
        metadata = getattr(skill, "metadata", {}) or {}
        if not (
            skill.allowed_from_chat
            and skill.module_id
            and metadata.get("implements") == "marketing.plan"
            and metadata.get("artifact_type") == "plan_artifact"
        ):
            continue
        if metadata.get("output_contract") == "strategy_workflow":
            return skill.module_id
        if metadata.get("platform") == "planning" or metadata.get("specialist") in {"planning", "gtm_planning"}:
            fallback = fallback or skill.module_id
    return fallback


def _module_label_from_manifest(module_id: str) -> str:
    """Human-readable display label for a module_id, from the live capability manifest."""
    for entry in build_dispatchable_manifest():
        if entry.module_id == module_id:
            return entry.label
    return module_id.rsplit(".", 1)[-1].replace("_", " ").title()


def _sse(event: dict) -> str:
    """Format a dict as a Server-Sent Event data line."""
    return f"data: {json.dumps(event)}\n\n"


async def _latest_failed_run_response(
    db: AsyncSession,
    ws,
    module_id: str,
    campaign_id,
    brand_id,
) -> RunResponse | None:
    """Return the failed Run row created by `_execute_module()`, if any.

    `_execute_module()` persists failed runs for routing/provider failures before
    raising. Chat/stream must still surface that failed result instead of making
    the specialist step disappear.
    """
    if not ws:
        return None
    stmt = select(Run).where(
        Run.workspace_id == ws.id,
        Run.module_id == module_id,
        Run.status == "failed",
    )
    if brand_id:
        stmt = stmt.where(Run.brand_id == brand_id)
    if campaign_id:
        stmt = stmt.where(Run.campaign_id == campaign_id)
    failed_run = (await db.execute(stmt.order_by(Run.created_at.desc()).limit(1))).scalar_one_or_none()
    if not failed_run:
        return None
    trace_row = (await db.execute(
        select(RunTrace).where(RunTrace.run_id == failed_run.id)
    )).scalar_one_or_none()
    routing = trace_row.routing_json if trace_row and trace_row.routing_json else {}
    return RunResponse(
        run_id=str(failed_run.id),
        module_id=failed_run.module_id,
        vertical="marketing",
        status=failed_run.status,
        approval_status=failed_run.approval_status,
        campaign_id=str(failed_run.campaign_id) if failed_run.campaign_id else None,
        brand_id=str(failed_run.brand_id) if failed_run.brand_id else None,
        result=None,
        execution=None,
        trace=RunTraceOut(
            capability=routing.get("capability", ""),
            policy=routing.get("policy", "balanced"),
            candidates_considered=routing.get("candidates_considered", 0),
            candidates_filtered=routing.get("candidates_filtered", 0),
            winner=routing.get("winner"),
            routing_reason=routing.get("routing_reason", routing.get("error", "failed before execution")),
        ) if routing else None,
        created_at=failed_run.created_at,
    )


async def _run_modules_streaming(
    db: AsyncSession,
    ws,
    triggered_modules: list[str],
    brief: dict,
    settings,
    campaign_id,
    brand_id,
    run_inline_params: dict,
) -> AsyncGenerator[dict, None]:
    """Async generator — dispatches each module and yields typed events.

    Yields:
        {"type": "module_start", "module_id": str, "label": str}
        {"type": "module_result", "module_id": str, "run": RunResponse}
    """
    for module_id in triggered_modules:
        label = _module_label_from_manifest(module_id)
        yield {"type": "module_start", "module_id": module_id, "label": label}
        try:
            module_brief = dict(brief)
            module_brief.update(run_inline_params.get(module_id, {}))
            result = await _execute_module(
                db, ws, module_id, module_brief, settings,
                campaign_id=campaign_id,
                brand_id=brand_id,
            )
            yield {"type": "module_result", "module_id": module_id, "run": result}
        except Exception as exc:
            logger.error("Module dispatch failed for %s: %s", module_id, exc)
            failed_result = await _latest_failed_run_response(db, ws, module_id, campaign_id, brand_id)
            if failed_result:
                yield {"type": "module_result", "module_id": module_id, "run": failed_result}


async def _workspace_brands(db: AsyncSession, ws) -> list[Brand]:
    if not ws:
        return []
    return (await db.execute(
        select(Brand).where(Brand.workspace_id == ws.id).order_by(Brand.name.asc())
    )).scalars().all()


async def _resolve_active_brand_for_turn(
    db: AsyncSession,
    ws,
    body: "ChatRequest",
) -> tuple[Brand | None, KlarAction | None]:
    """Resolve Brand scope for a chat turn without channel/capability routing.

    This is the pre-LLM scope boundary. It only honors persisted UI state (or a
    single-brand workspace). Cross-brand follow-up interpretation belongs to the
    `workspace.scope_resolution` SKILL.md contract and hidden SCOPE directive,
    not deterministic phrase matching.
    """
    if not ws:
        return None, None

    active_brand = await resolve_brand(db, body.brand_id)
    if active_brand:
        return active_brand, None

    all_brands = await _workspace_brands(db, ws)
    if len(all_brands) == 1:
        only = all_brands[0]
        return only, KlarAction(
            action="brand_switch",
            data={"brand_id": str(only.id), "brand_name": only.name},
        )

    return None, None


async def _resolve_scope_brand(db: AsyncSession, ws, value: str | None) -> Brand | None:
    """Resolve a Brand name emitted by the hidden SCOPE directive."""
    raw = (value or "").strip()
    if not raw or raw.lower() in {"none", "null", "n/a", "unknown", "unclear"}:
        return None
    if not ws:
        return None
    return await find_brand_by_name(db, ws.id, raw)


async def _brand_scoped_brief(db: AsyncSession, ws, brand: Brand | None, base: dict) -> dict:
    """Build a module brief scoped to the active Brand when available.

    Active-brand briefs must not call the workspace fallback resolver first: that
    resolver can inject the first workspace product/audience before brand rows
    are inspected, which is the exact cross-brand bleed this path prevents.
    """
    if not brand:
        return await _resolve_brief(db, ws, base)

    brief = dict(base)
    brief["brand_name"] = brand.name
    bj = brand.brand_json or {}
    for field in ("tone", "voice", "values", "domain", "website_url", "social_handles"):
        if bj.get(field):
            brief[field] = bj[field]
    social_handles = bj.get("social_handles") or {}
    brief.setdefault("brand_handle", social_handles.get("x") or social_handles.get("twitter") or social_handles.get("instagram"))
    brief.setdefault("display_url", bj.get("domain") or bj.get("website_url"))

    product_rows = (await db.execute(
        select(Product).where(Product.brand_id == brand.id).order_by(Product.created_at.asc())
    )).scalars().all()
    if product_rows:
        prod = product_rows[0]
        brief["product_name"] = prod.name
        if prod.tagline:
            brief["tagline"] = prod.tagline
        benefits = (prod.benefits_json or {}).get("benefits", [])
        if benefits:
            brief["key_benefit"] = benefits[0]
            brief["benefits"] = benefits
        brief["product_catalog_summary"] = "\n".join(
            f"- {p.name}: {p.tagline or 'no tagline'}" for p in product_rows
        )

    audience_rows = (await db.execute(
        select(Audience).where(Audience.brand_id == brand.id).order_by(Audience.created_at.asc())
    )).scalars().all()
    if audience_rows:
        aud = audience_rows[0]
        brief["audience"] = aud.name
        seg = aud.segment_json or {}
        if seg.get("demographics"):
            brief["demographics"] = seg["demographics"]
        if seg.get("pain_points"):
            brief["pain_points"] = seg["pain_points"]
        brief["audience_profiles_summary"] = "\n".join(
            f"- {a.name}: {(a.segment_json or {}).get('demographics', 'no demographics')}"
            for a in audience_rows
        )

    docs = (await db.execute(
        select(WorkspaceDocument)
        .where(WorkspaceDocument.brand_id == brand.id)
        .order_by(WorkspaceDocument.updated_at.desc())
    )).scalars().all()
    logger.info(
        "CMO brand brief scope brand_id=%s products=%s audiences=%s docs=%s",
        brand.id,
        len(product_rows),
        len(audience_rows),
        len(docs),
    )
    by_type: dict[str, list[str]] = {}
    for doc in docs:
        if doc.content_markdown:
            by_type.setdefault(doc.doc_type, []).append(doc.content_markdown)
    brief["brand_guidelines_excerpt"] = "\n\n".join(by_type.get("brand_guideline", []))[:4000]
    brief["campaign_brand_kit_excerpt"] = "\n\n".join(by_type.get("campaign_brand_kit", []))[:4000]
    brief["marketing_reports_excerpt"] = "\n\n".join(by_type.get("marketing_report", []))[:3000]
    brief["campaign_reports_excerpt"] = "\n\n".join(by_type.get("campaign_report", []))[:3000]
    brief["competitor_profiles_excerpt"] = "\n\n".join(by_type.get("competitor_profile", []))[:3000]
    brief["industry_data_excerpt"] = "\n\n".join(by_type.get("industry_report", []))[:3000]
    return brief


class ChatHistoryItem(BaseModel):
    role: str  # "user" or "ai"
    text: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatHistoryItem] = []
    brand_id: Optional[str] = None      # active brand; set by frontend after @klar switch
    campaign_id: Optional[str] = None   # active campaign; set after @klar confirm


class KlarAction(BaseModel):
    action: str  # "brand_switch" | "brand_clear" | "plan_draft" | "plan_confirmed" | "evaluate_stub" | "pending_summary" | "brand_list"
    data: dict = {}



class ChatResponse(BaseModel):
    reply: str
    runs: list[RunResponse] = Field(default_factory=list)
    # kept for single-run callers; mirrors runs[0] when there is exactly one result
    run: RunResponse | None = None
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    module_id: str | None = None
    klar_action: KlarAction | None = None  # structured @klar command result


class ChatReviseRequest(BaseModel):
    feedback: str = ""
    history: list[ChatHistoryItem] = []



def _platform_display_name(platform: str) -> str:
    return platform.replace("_", " ").replace("-", " ").title()


async def _brand_channel_readiness(db: AsyncSession, brand: Brand | None) -> str:
    """Brand-scoped connected-channel facts for dispatch decisions. Facts, not routing —
    the LLM still chooses. Prevents dispatching publish/store capabilities to channels the
    active brand has not connected (e.g. a failed Facebook publish, or a Drive store with
    no Drive connection)."""
    if not brand:
        return ""
    from models.social import SocialConnection

    from plugin_loader import get_active_plugin_ids, get_loaded_plugins

    active_plugin_ids = await get_active_plugin_ids(db, brand.id)
    active_plugins = [p for pid, p in get_loaded_plugins().items() if pid in active_plugin_ids]
    allowed_platforms = {
        platform
        for plugin in active_plugins
        for platform in list(plugin.manifest.requires_social_connection)
    } | {
        conn.platform
        for plugin in active_plugins
        for conn in plugin.manifest.connections
        if conn.platform
    }
    if not allowed_platforms:
        return ""

    rows = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand.id,
            SocialConnection.status == "connected",
            SocialConnection.platform.in_(allowed_platforms),
        )
    )).scalars().all()
    # Google Drive requires a root folder selection before it can store assets.
    # Report it as connected only when drive_root_folder_id is set; otherwise
    # the CMO would dispatch creative.post.image which fails mid-run.
    connected = sorted({
        r.platform for r in rows
        if r.platform != "google_drive"
        or (r.token_meta_json or {}).get("drive_root_folder_id")
    })
    if connected:
        names = ", ".join(_platform_display_name(p) for p in connected)
        connected_line = f"Connected for {brand.name}: {names}."
    else:
        connected_line = f"No external channels are connected for {brand.name} yet."
    return (
        "\nActive-brand channel readiness (use this for dispatch decisions):\n"
        f"- {connected_line}\n"
        "- Only dispatch a capability that PUBLISHES, SENDS, or POSTS to an external platform, "
        "or that STORES to a channel, when that channel is connected for the active brand above.\n"
        "- If a needed channel is not connected: produce the offline deliverable you can (the creative/copy) "
        "and tell the user in ONE line to connect that channel in Admin → Brands. "
        "Never dispatch a publish/send/post action for an unconnected channel.\n"
    )


async def _build_system_prompt(db: AsyncSession, ws, skill_context: str = "", brand: Brand | None = None) -> str:
    # Active brand name takes precedence over workspace name
    ws_name = (brand.name if brand else None) or (ws.name if ws else "this business")

    org_brand_rows = await _workspace_brands(db, ws) if ws and not brand else []

    # Resolve brand identity: prefer active Brand row. Legacy workspace.brand_json
    # is only safe when no Brand rows exist; otherwise it may describe a
    # previously imported Brand and bleed into org-level prompts.
    active_brand_json = (brand.brand_json if brand else None) or ((ws.brand_json if ws else None) if not org_brand_rows else None) or {}

    brand_ctx = ""
    if active_brand_json:
        voice = active_brand_json.get("voice", "")
        tone = active_brand_json.get("tone", "")
        values = active_brand_json.get("values", [])
        domain = active_brand_json.get("domain", "")
        website_url = active_brand_json.get("website_url", "")
        social_handles = active_brand_json.get("social_handles", {}) or {}
        socials = ", ".join(f"{channel}: {handle}" for channel, handle in social_handles.items() if handle)
        parts = [
            f"voice: {voice}" if voice else "",
            f"tone: {tone}" if tone else "",
            f"values: {', '.join(values)}" if values else "",
            f"domain: {domain}" if domain else "",
            f"website: {website_url}" if website_url else "",
            f"social handles: {socials}" if socials else "",
        ]
        brand_ctx = "\nBrand — " + ", ".join(p for p in parts if p) + "."

    workspace_ctx = ""
    if ws:
        org_brands = org_brand_rows
        org_scope = bool(not brand and org_brands)
        if org_scope:
            brand_lines = [f"- {b.name}" for b in org_brands]
            workspace_ctx = "\n\nKnown org context (no active brand):\n"
            workspace_ctx += f"Workspace: {ws.name}\n"
            workspace_ctx += "Available brands:\n" + "\n".join(brand_lines) + "\n"
            workspace_ctx += "No Brand is active. Do not use workspace products, audiences, or documents as brand facts. For brand-specific artifacts, ask which brand unless the user names one.\n"
            product_rows = []
            audience_rows = []
            kit = None
            brand_guideline = None
        else:
            # When a brand is active, scope products/audiences/docs to that brand.
            # Legacy workspace fallback is only allowed when no Brand rows exist yet.
            if brand:
                product_rows = (await db.execute(
                    select(Product).where(Product.brand_id == brand.id).order_by(Product.created_at.asc())
                )).scalars().all()
                audience_rows = (await db.execute(
                    select(Audience).where(Audience.brand_id == brand.id).order_by(Audience.created_at.asc())
                )).scalars().all()
                kit = (await db.execute(
                    select(WorkspaceDocument)
                    .where(WorkspaceDocument.brand_id == brand.id, WorkspaceDocument.doc_type == "campaign_brand_kit")
                    .order_by(WorkspaceDocument.status.desc(), WorkspaceDocument.updated_at.desc())
                    .limit(1)
                )).scalar_one_or_none()
                brand_guideline = (await db.execute(
                    select(WorkspaceDocument)
                    .where(WorkspaceDocument.brand_id == brand.id, WorkspaceDocument.doc_type == "brand_guideline")
                    .order_by(WorkspaceDocument.status.desc(), WorkspaceDocument.updated_at.desc())
                    .limit(1)
                )).scalar_one_or_none()
            else:
                product_rows = (await db.execute(
                    select(Product).where(Product.workspace_id == ws.id).order_by(Product.created_at.asc())
                )).scalars().all()
                audience_rows = (await db.execute(
                    select(Audience).where(Audience.workspace_id == ws.id).order_by(Audience.created_at.asc())
                )).scalars().all()
                kit = (await db.execute(
                    select(WorkspaceDocument)
                    .where(WorkspaceDocument.workspace_id == ws.id, WorkspaceDocument.doc_type == "campaign_brand_kit")
                    .order_by(WorkspaceDocument.status.desc(), WorkspaceDocument.updated_at.desc())
                    .limit(1)
                )).scalar_one_or_none()
                brand_guideline = (await db.execute(
                    select(WorkspaceDocument)
                    .where(WorkspaceDocument.workspace_id == ws.id, WorkspaceDocument.doc_type == "brand_guideline")
                    .order_by(WorkspaceDocument.status.desc(), WorkspaceDocument.updated_at.desc())
                    .limit(1)
                )).scalar_one_or_none()

        product_lines = []
        for p in product_rows:
            benefits = (p.benefits_json or {}).get("benefits", [])
            product_lines.append(f"- {p.name}: {p.tagline or 'no tagline'}" + (f"; benefits: {', '.join(benefits)}" if benefits else ""))

        audience_lines = []
        for a in audience_rows:
            seg = a.segment_json or {}
            pain = seg.get("pain_points", [])
            examples = seg.get("examples", [])
            priority = seg.get("priority", [])
            detail_parts = [seg.get('demographics', 'no demographics')]
            if examples:
                detail_parts.append(f"examples: {', '.join(examples)}")
            if priority:
                detail_parts.append(f"priority: {', '.join(priority)}")
            if pain:
                detail_parts.append(f"pains: {', '.join(pain)}")
            audience_lines.append(f"- {a.name}: " + "; ".join(detail_parts))

        kit_excerpt = ""
        kit_status = "none"
        if kit and kit.content_markdown:
            kit_status = kit.status or "ingested"
            kit_excerpt = kit.content_markdown[:5000]

        guideline_excerpt = ""
        if brand_guideline and brand_guideline.content_markdown:
            guideline_excerpt = brand_guideline.content_markdown[:6000]

        if not org_scope:
            brand_scope_label = f"brand: {brand.name}" if brand else "workspace"
            workspace_ctx = f"\n\nKnown project context ({brand_scope_label}):\n"
            workspace_ctx += f"Company/brand: {ws_name}\n"
            workspace_ctx += f"Brand kit status: {kit_status}\n"
            if product_lines:
                workspace_ctx += "Products/offers:\n" + "\n".join(product_lines) + "\n"
            if audience_lines:
                workspace_ctx += "Target audiences:\n" + "\n".join(audience_lines) + "\n"
            if guideline_excerpt:
                workspace_ctx += "Brand Guidelines / Strategic Brief excerpt:\n" + guideline_excerpt + "\n"
            if kit_excerpt:
                workspace_ctx += "Campaign Brand Kit excerpt:\n" + kit_excerpt + "\n"

    modules_str = await format_manifest_for_brand(db, brand.id if brand else None)
    actionable_artifacts = await _actionable_artifacts_context(db, ws, brand=brand)
    channel_readiness = await _brand_channel_readiness(db, brand)

    operational_ctx = f"""
{channel_readiness}

Actionable approved/reviewable artifacts, for explicit deploy/publish/send/upload commands only:
{actionable_artifacts}
- To deploy an artifact action from this list, append hidden directive: ACTION: <run_id> <action>
- Use ACTION only when the user explicitly asks to deploy/publish/send/upload an existing artifact or clearly approves it now.
- Do not use ACTION for newly generated copy/image/audio/video unless the user is approving an existing artifact.

Operational connector context, for explicit system/connector questions only:
- MCP means Model Context Protocol, a connector layer BOS can use behind the scenes.
{format_connector_status_for_prompt()}
- If the user asks generally to check the MCP system, answer with connector status from the registry. Do not say you are unaware of MCP.
- If the user asks for a channel/report and a matching connector-backed module is available, use that module rather than explaining MCP.
"""

    return f"""You are the Chief Marketing Officer for {ws_name}.

HARD RULES — no exceptions:
1. Never generate ad copy, email copy, social posts, or any platform-native content inline in your reply.
2. Dispatch-first: if the user's request matches an installed capability below, output 1–2 lines and append the RUN: directive. Do not also draft the artifact inline.
3. Broad or ambiguous sample/draft/example request (no specific platform named): ask exactly one clarifying question and offer installed artifact categories in plain language. Append no RUN line until the user clarifies.
4. One question max per reply. Never ask multiple clarifying questions in one turn.
5. "What can you do" replies: group into at most 5 CMO capability areas (e.g. Plan, Execute, Optimize). One short phrase per area. Do not list the brand's own products or services as capabilities.
6. Active brand isolation: when Known project context says `brand: X`, use only that brand's profile/products/audiences/docs as business facts. Ignore chat-history facts that refer to a different brand unless the scope-resolution note sets a different execution_brand for a new artifact.
7. Hidden scope directive: every reply must start with a SCOPE block exactly like the scope-resolution skill describes. If you append any RUN line, `execution_brand` must be one existing Brand name, not none.
8. When the scope-resolution note sets a clear execution_brand for a new/equivalent artifact, append the matching RUN line if the installed capability exists. Do not ask for Brand profile details; BOS hydrates the execution Brand for the module.
8a. If a capability requires upstream contracts (buyer maps, message architecture, briefs, reports, or other substrate), do not ask the user to provide those internal artifacts. Append the RUN line for the requested capability; BOS execution will load or generate required upstream contracts from the Brand Brief.
9. RUN lines must use ONLY the exact module IDs listed under "Deployable capabilities" below. Never invent, guess, or extrapolate a module ID. If no listed capability matches the request, say so — do not fabricate a RUN line.
9a. Passing parameters to a RUN: when a capability's description asks for inputs (e.g. `caption`, `image_prompt`), append them as indented `key: value` lines directly under the RUN line, one per line, no blank line between. Example:
   RUN: creative.post.image
   caption: <the full post copy you composed, in the brand voice>
   image_prompt: <vivid visual description — scene, mood, no text or logos>
   Always supply the inputs a capability's description requests; these params are hidden from the user and feed the specialist. Composing copy for a hidden param like `caption` does NOT violate Rule 1 — Rule 1 only forbids platform copy in your VISIBLE reply; RUN params are stripped before the user sees the reply.
10. ACTION lines must use ONLY run IDs and actions listed under "Actionable approved/reviewable artifacts". Never invent a run ID or action. ACTION is for approved artifact deployment; RUN is for specialist creation/read/action modules.
11. Never mass-dispatch. When a user asks to "trigger all capabilities", "test everything", "showcase all tools", or any similar blanket command: do NOT emit multiple RUN lines. Respond with a short capability summary and ask which specific job or brand to start with. A single turn must never dispatch more than 3 RUN lines unless the user has explicitly named each capability they want.
{brand_ctx}{workspace_ctx}{operational_ctx}
Be mobile-first by default: short lines, one idea per line, no dense paragraphs. When the user asks what the project/brand/system is about, answer using the known project and operational context above. Do not claim details are unspecified if products, audiences, a brand kit, or connector context are present.

Activated BOS skill context:
{skill_context or "No activated skill context."}

Deployable capabilities — these are ALL installed capabilities. Use ONLY these exact module IDs in any RUN: line. Do not use any other ID:
{modules_str}"""


# Preferred model per provider for the conversational intent call
_CHAT_MODELS: dict[str, str] = {
    "gemini": "gemini-2.0-flash",
    "nvidia": "meta/llama-3.3-70b-instruct",
    "openrouter": "openai/gpt-4o-mini",
    "openai": "gpt-5.1",
}


async def _complete_cmo_messages(
    db: AsyncSession,
    ws,
    settings,
    messages: list[dict],
    plan_mode: bool = False,
    brand_id: str | None = None,
) -> str | None:
    candidates: list[tuple[str, str, str, str | None]] = []

    configured_chat_model = None
    if ws:
        configured_chat_model = await resolve_backend_override(db, ws.id, "cmo.main")
    configured_chat_model = configured_chat_model or get_backend_override(settings, "cmo.main") or parse_model_ref(getattr(settings, "cmo_chat_model", ""))
    if configured_chat_model and configured_chat_model.modality != "text":
        logger.error("Configured CMO backend must use text modality, got '%s'", configured_chat_model.modality)
        return None
    chat_models = (
        {configured_chat_model.provider: configured_chat_model.model_id}
        if configured_chat_model and configured_chat_model.model_id
        else _CHAT_MODELS
    )

    def add_candidate(provider: str, model_id: str, key: str, auth_mode: str | None) -> None:
        identity = (provider, model_id, auth_mode or "platform")
        if any((p, m, a or "platform") == identity for p, m, _, a in candidates):
            return
        candidates.append((provider, model_id, key, auth_mode))

    # Try the operator-configured CMO backend first, but do not let a bad model
    # override take the whole CMO offline when other credentials are available.
    if configured_chat_model and configured_chat_model.model_id:
        provider = configured_chat_model.provider
        model_id = configured_chat_model.model_id
        if ws:
            key, auth_mode = await resolve_stored_provider_credential(db, ws.id, provider, settings, brand_id=brand_id)
            if key:
                add_candidate(provider, model_id, key, auth_mode)
        platform_key = get_platform_key(provider, settings)
        if platform_key:
            add_candidate(provider, model_id, platform_key, None)

    if ws:
        for provider, model_id in _CHAT_MODELS.items():
            key, auth_mode = await resolve_stored_provider_credential(db, ws.id, provider, settings, brand_id=brand_id)
            if key:
                if provider == "openai" and auth_mode == "api_key":
                    model_id = "gpt-4o-mini"
                add_candidate(provider, model_id, key, auth_mode)

    for provider, model_id in _CHAT_MODELS.items():
        platform_key = get_platform_key(provider, settings)
        if platform_key:
            add_candidate(provider, model_id, platform_key, None)

    if configured_chat_model and not candidates:
        logger.error(
            "Configured CMO_CHAT_MODEL %s/%s has no available credential and no fallback credentials are available",
            configured_chat_model.provider,
            configured_chat_model.model_id,
        )

    for provider, model_id, api_key, auth_mode in candidates:
        try:
            adapter = get_adapter(provider, api_key, auth_mode)
            if plan_mode and hasattr(adapter, "_upgrade_for_thinking"):
                model_id = adapter._upgrade_for_thinking(model_id)
                response = await adapter.complete_messages(
                    messages, model_id, thinking=True, thinking_budget=8000
                )
                logger.info("Plan-mode (high-think) via %s/%s", provider, model_id)
            else:
                response = await adapter.complete_messages(messages, model_id)
                logger.info("Chat via %s/%s", provider, model_id)
            return response.content
        except Exception as exc:
            logger.warning("Chat %s/%s failed: %s", provider, model_id, exc)

    return None


_MAX_CMO_LOOP_DEPTH = 3


def _normalize_self_check(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in {"pass", "passed", "ok", "success"}:
        return "passed"
    if raw in {"fail", "failed", "error"}:
        return "failed"
    if raw:
        return "warnings"
    return "unknown"


def _specialist_result_summaries(run_results: list[RunResponse]) -> list[dict]:
    """Build the only run context the CMO may see during synthesis.

    Native artifact fields stay out of chat context. Workspace/Stream own those
    previews; the CMO receives artifact refs, status, self-check, and decisions.
    """
    summaries: list[dict] = []
    for run in run_results:
        ref = artifact_ref_from_run(run)
        block = run.result.block if run.result and isinstance(run.result.block, dict) else {}
        allowed_actions = block.get("allowed_actions")
        if not isinstance(allowed_actions, list) or not allowed_actions:
            allowed_actions = ["review", "revise", "dismiss", "ask_cmo"]
        summary = block.get("summary") if isinstance(block.get("summary"), str) else None
        error = block.get("error") or block.get("message") if isinstance(block, dict) else None
        is_failed_ref = ref.status == "failed"
        summaries.append({
            "run_id": run.run_id,
            "artifact_ref": ref.artifact_id,
            "artifact_title": ref.title,
            "artifact_type": ref.type,
            "status": "failed" if is_failed_ref else (ref.status if run.status == "completed" else run.status),
            "summary": summary or (str(error) if is_failed_ref and error else f"{ref.title} created for Stream review."),
            "self_check": _normalize_self_check(run.result.self_check if run.result else None),
            "recommended_decision": "fix_setup" if ref.type == "setup_blocker" else ("review" if ref.status in {"pending_review", "saved"} else ref.status),
            "objective_ref": run.campaign_id,
            "brand_ref": run.brand_id,
            "allowed_actions": allowed_actions,
        })
    return summaries


def _extract_action_directives(text: str) -> list[tuple[str, str]]:
    return [(match.group(1), match.group(2)) for match in _ACTION_RE.finditer(text or "")]


def _user_authorized_artifact_action(message: str) -> bool:
    """Return true only when the latest user turn explicitly asks to act on an artifact.

    The CMO may recommend review after a specialist returns, but it cannot approve,
    publish, send, dismiss, or mutate artifacts merely because synthesis is running.
    """
    return bool(_ACTION_AUTHORIZATION_RE.search(message or ""))


async def _actionable_artifacts_context(db: AsyncSession, ws, brand: Brand | None = None) -> str:
    if not ws:
        return "No actionable artifacts available."
    stmt = (
        select(Run, RunTrace)
        .join(RunTrace, RunTrace.run_id == Run.id)
        .where(Run.workspace_id == ws.id)
        .where(Run.status.in_(["success", "partial"]))
        .order_by(Run.created_at.desc())
        .limit(20)
    )
    if brand:
        stmt = stmt.where(Run.brand_id == brand.id)
    try:
        rows = (await db.execute(stmt)).all()
    except Exception as exc:
        logger.debug("Could not load actionable artifacts context: %s", exc)
        return "No actionable artifacts available."
    lines: list[str] = []
    for run, trace in rows:
        block = ((trace.lineage_json or {}).get("block") if trace else None) or {}
        if not isinstance(block, dict):
            continue
        action_modules = block.get("action_modules")
        allowed_actions = block.get("allowed_actions")
        if not isinstance(action_modules, dict) or not isinstance(allowed_actions, list):
            continue
        actions = [a for a in allowed_actions if isinstance(a, str) and isinstance(action_modules.get(a), str)]
        if not actions:
            continue
        block_type = block.get("type") or "artifact"
        status = run.approval_status or "pending"
        lines.append(
            f"- run_id: {run.id}; artifact_type: {block_type}; source_module: {run.module_id}; "
            f"approval_status: {status}; actions: {', '.join(actions)}"
        )
    if not lines:
        return "No actionable artifacts available."
    return "\n".join(lines[:8])


def _build_synthesis_context(run_results: list[RunResponse], *, final_turn: bool) -> str:
    return "\n".join([
        "Specialist results are now available.",
        "Write the operator-facing CMO reply only after reading these summaries.",
        "Use artifact references/titles only; do not paste native artifact content, copy, prompts, targeting, budgets, or provider details.",
        "Do not mention raw module IDs in the visible reply.",
        "If useful and allowed, you may emit RUN directives for additional installed specialists only when more work is truly required. Do not emit ACTION directives unless the latest user message explicitly approved or requested that action." if not final_turn else "This is the final allowed loop turn. Do not emit RUN or ACTION directives; summarize current results and next review action.",
        "Specialist result summaries:",
        "```json",
        json.dumps(_specialist_result_summaries(run_results), indent=2),
        "```",
    ])


async def _run_actions_streaming(
    db: AsyncSession,
    actions: list[tuple[str, str]],
    settings,
) -> AsyncGenerator[dict, None]:
    for run_id, action in actions:
        yield {"type": "module_start", "module_id": f"artifact_action.{action}", "label": f"Artifact {action}"}
        try:
            result = await execute_declared_run_action(db, run_id, action, settings)
            yield {"type": "module_result", "module_id": f"artifact_action.{action}", "run": result.action_run}
        except Exception as exc:
            logger.error("Artifact action failed for run_id=%s action=%s: %s", run_id, action, exc)


async def _continue_cmo_loop_after_results(
    db: AsyncSession,
    ws,
    settings,
    messages: list[dict],
    first_raw_reply: str,
    initial_run_results: list[RunResponse],
    modules: list[dict],
    body: ChatRequest,
    active_brand: Brand | None,
    initial_execution_brand: Brand | None,
    active_campaign_uuid: UUID | None,
) -> AsyncGenerator[dict, None]:
    """Generic CMO loop primitive: specialist results → CMO synthesis.

    This mirrors tool-result loops without introducing capability-specific routing.
    The CMO sees safe result summaries, may request more allowed RUN directives up
    to a small depth limit, and must produce the final visible reply after results.
    """
    all_run_results = list(initial_run_results)
    current_messages = list(messages)
    current_reply = _strip_control_directives(first_raw_reply)
    final_conversation_brand: Brand | None = None
    final_execution_brand: Brand | None = initial_execution_brand
    allowed_module_ids = set(m["id"] for m in modules)
    depth = 2

    while all_run_results and depth <= _MAX_CMO_LOOP_DEPTH:
        yield {"type": "step", "label": "Synthesizing results..."}
        final_turn = depth >= _MAX_CMO_LOOP_DEPTH
        current_messages.append({"role": "assistant", "content": current_reply or "I requested specialist work."})
        current_messages.append({"role": "user", "content": _build_synthesis_context(all_run_results, final_turn=final_turn)})
        raw_reply = await _complete_cmo_messages(
            db, ws, settings, current_messages, plan_mode=False, brand_id=body.brand_id
        )
        if raw_reply is None:
            logger.warning("CMO synthesis failed; falling back to pre-synthesis reply")
            break

        scope_decision, reply_without_scope = _extract_scope_directive(raw_reply)
        current_reply = _strip_control_directives(raw_reply)
        scope_conversation_brand = await _resolve_scope_brand(db, ws, scope_decision.get("conversation_brand"))
        scope_execution_brand = await _resolve_scope_brand(db, ws, scope_decision.get("execution_brand"))
        final_conversation_brand = scope_conversation_brand or final_conversation_brand
        final_execution_brand = scope_execution_brand or final_execution_brand

        requested_actions = _extract_action_directives(reply_without_scope)
        if requested_actions and not _user_authorized_artifact_action(body.message):
            logger.warning("CMO synthesis emitted unauthorized ACTION directives — skipping: %s", requested_actions)
            requested_actions = []
        if requested_actions and not final_turn:
            yield {"type": "step", "label": "Executing approved artifact action..."}
            async for event in _run_actions_streaming(db, requested_actions, settings):
                yield event
                if event["type"] == "module_result":
                    all_run_results.append(event["run"])

        requested_modules = _RUN_RE.findall(reply_without_scope)
        invalid = [mid for mid in requested_modules if mid not in allowed_module_ids]
        if invalid:
            logger.warning("CMO synthesis triggered modules outside allowed set — skipping: %s", invalid)
        requested_modules = _dedupe_preserve_order([mid for mid in requested_modules if mid in allowed_module_ids])

        # Never re-dispatch a module already run in this CMO turn. Synthesis may explain,
        # revise, or ask for approval, but it must not create duplicate artifacts unless a
        # later user turn explicitly requests another version.
        already_ran = {run.module_id for run in all_run_results}
        duplicate_requests = [mid for mid in requested_modules if mid in already_ran]
        if duplicate_requests:
            logger.warning("CMO synthesis re-requested already-run modules — skipping: %s", duplicate_requests)
        requested_modules = [mid for mid in requested_modules if mid not in already_ran]

        # Never re-dispatch a module that already produced a permanent credential/config failure.
        # These errors require operator action (e.g. connect an account); retrying won't help.
        _PERMANENT_FAILURE_CODES = {"missing_credentials", "invalid_brief"}
        hard_failed = {
            run.module_id
            for run in all_run_results
            if (run.result and isinstance(run.result.block, dict)
                and run.result.block.get("status") == "failed"
                and run.result.block.get("reason_code") in _PERMANENT_FAILURE_CODES)
        }
        if hard_failed:
            blocked = [mid for mid in requested_modules if mid in hard_failed]
            if blocked:
                logger.warning("CMO synthesis re-requested permanently-failed modules — skipping: %s", blocked)
            requested_modules = [mid for mid in requested_modules if mid not in hard_failed]

        if final_turn or not requested_modules:
            if final_turn and requested_modules:
                logger.warning("CMO loop depth limit reached; skipping additional RUN directives: %s", requested_modules)
            break

        execution_brand = scope_execution_brand
        if await _workspace_brands(db, ws) and not execution_brand:
            logger.warning("CMO synthesis requested RUN without execution_brand; skipping: %s", requested_modules)
            break

        conversation_lines = [f"{h.role.upper()}: {h.text}" for h in body.history[-12:]] + [f"USER: {body.message}"]
        brief = await _brand_scoped_brief(
            db, ws, execution_brand or active_brand, {
                "request": body.message,
                "objective": body.message,
                "message": body.message,
                "conversation_context": "\n".join(conversation_lines),
            }
        )
        run_inline_params = _parse_run_inline_params(reply_without_scope)
        yield {"type": "step", "label": "Routing to specialists..."}
        async for event in _run_modules_streaming(
            db, ws, requested_modules, brief, settings,
            active_campaign_uuid, (execution_brand or active_brand).id if (execution_brand or active_brand) else None,
            run_inline_params,
        ):
            yield event
            if event["type"] == "module_result":
                all_run_results.append(event["run"])

        depth += 1

    yield {
        "type": "loop_complete",
        "reply_text": current_reply,
        "run_results": all_run_results,
        "scope_conversation_brand": final_conversation_brand,
        "scope_execution_brand": final_execution_brand,
    }


async def _pending_summary(db: AsyncSession, ws) -> str:
    """Return a short cross-brand pending decisions summary."""
    if not ws:
        return "No workspace configured."
    from models.run import Run as RunModel
    pending = (await db.execute(
        select(RunModel).where(
            RunModel.workspace_id == ws.id,
            RunModel.approval_status == "pending",
            RunModel.status == "completed",
        ).order_by(RunModel.created_at.desc()).limit(20)
    )).scalars().all()
    if not pending:
        return "No pending decisions right now."
    def artifact_label(module_id: str) -> str:
        leaf = module_id.rsplit('.', 1)[-1].replace('_', ' ').replace('-', ' ').title()
        return f'{leaf} artifact review'

    lines = [f"- {artifact_label(r.module_id)}" for r in pending]
    return f"{len(pending)} pending decision(s):\n" + "\n".join(lines)


async def _generate_chat_stream(body: ChatRequest, db: AsyncSession, settings) -> AsyncGenerator[str, None]:
    """Async generator that runs the CMO chat pipeline and yields SSE-formatted strings.

    Yields step events as the pipeline progresses, module_result events as each
    module completes, and a final reply event. The existing POST /chat endpoint
    is unchanged; this generator powers POST /chat/stream only.
    """
    ws = await get_singleton(db)
    _resolved_brand_switch: KlarAction | None = None

    # ── Brand-reply detection ─────────────────────────────────────────────────
    if not body.brand_id and ws and body.history:
        _last_ai = next((h.text for h in reversed(body.history) if h.role == "ai"), "")
        _last_user = body.message.strip()
        if ("Which brand" in _last_ai or "which brand" in _last_ai) and len(_last_user.split()) <= 4:
            _matched = await find_brand_by_name(db, ws.id, _last_user)
            if _matched:
                _original_cmd: str | None = None
                for _i in range(len(body.history) - 1, -1, -1):
                    _h = body.history[_i]
                    if _h.role == "ai" and ("Which brand" in _h.text or "which brand" in _h.text):
                        if _i > 0 and body.history[_i - 1].role == "user":
                            _original_cmd = body.history[_i - 1].text.strip()
                        break
                body = ChatRequest(
                    message=_original_cmd if _original_cmd else body.message,
                    history=body.history,
                    brand_id=str(_matched.id),
                    campaign_id=body.campaign_id,
                )
                _resolved_brand_switch = KlarAction(
                    action="brand_switch",
                    data={"brand_id": str(_matched.id), "brand_name": _matched.name},
                )

    # ── @council command ──────────────────────────────────────────────────────
    if _is_council_command(body.message):
        from council import start_session as _council_start
        from models.workspace import Brand as _Brand
        _council_brief = _parse_council_brief(body.message)
        if not _council_brief:
            yield _sse({"type": "reply", "text": "What question should the council deliberate on?\n\nUsage: @council <question>", "klar_action": None})
            yield _sse({"type": "done"})
            return
        yield _sse({"type": "step", "label": "Convening council…"})
        _council_brand: _Brand | None = None
        if body.brand_id:
            _council_brand = (await db.execute(
                select(_Brand).where(_Brand.id == UUID(body.brand_id))
            )).scalar_one_or_none()
        _council_result = await _council_start(
            brief=_council_brief,
            db=db,
            ws=ws,
            brand=_council_brand,
        )
        if _council_result.get("error"):
            yield _sse({"type": "reply", "text": _council_result["error"], "klar_action": None})
        else:
            yield _sse({"type": "reply", "text": "", "klar_action": {
                "action": "council_session",
                "data": {
                    "session_id": _council_result["session_id"],
                    "brief": _council_brief,
                    "status": _council_result["status"],
                    "current_round": _council_result["current_round"],
                    "rounds_completed": _council_result["rounds_completed"],
                    "rounds": _council_result["rounds"],
                    "c6_injections": _council_result["c6_injections"],
                    "pending_c6_prompt": _council_result["pending_c6_prompt"],
                },
            }})
        yield _sse({"type": "done"})
        return

    # ── @klar commands ────────────────────────────────────────────────────────
    if _is_klar_command(body.message):
        yield _sse({"type": "step", "label": "Processing command..."})
        cmd = _parse_klar_command(body.message)

        if cmd["action"] == "brand_switch":
            if not ws:
                yield _sse({"type": "reply", "text": "No workspace configured.", "klar_action": None})
            else:
                brand = await find_brand_by_name(db, ws.id, cmd["brand_name"])
                if not brand:
                    yield _sse({"type": "reply", "text": f"I can't find {cmd['brand_name']}.", "klar_action": None})
                else:
                    bj = brand.brand_json or {}
                    summary_parts = [p for p in [bj.get("voice"), bj.get("tone")] if p]
                    summary = f" — {', '.join(summary_parts)}" if summary_parts else ""
                    action = KlarAction(action="brand_switch", data={"brand_id": str(brand.id), "brand_name": brand.name})
                    yield _sse({"type": "reply", "text": f"Switched to {brand.name}{summary}.\n\nWorkspace context loaded.", "klar_action": action.model_dump()})
            yield _sse({"type": "done"})
            return

        if cmd["action"] == "list_brands":
            if not ws:
                yield _sse({"type": "reply", "text": "No workspace configured.", "klar_action": None})
            else:
                all_brands = (await db.execute(
                    select(Brand).where(Brand.workspace_id == ws.id).order_by(Brand.name.asc())
                )).scalars().all()
                if not all_brands:
                    yield _sse({"type": "reply", "text": "No brands yet.\n\nCreate one in Admin → Brands.", "klar_action": None})
                else:
                    lines = [f"- {b.name}" for b in all_brands]
                    action = KlarAction(action="brand_list", data={"brands": [{"id": str(b.id), "name": b.name} for b in all_brands]})
                    yield _sse({"type": "reply", "text": "Brands:\n" + "\n".join(lines), "klar_action": action.model_dump()})
            yield _sse({"type": "done"})
            return

        if cmd["action"] == "pending":
            summary = await _pending_summary(db, ws)
            yield _sse({"type": "reply", "text": summary, "klar_action": KlarAction(action="pending_summary", data={}).model_dump()})
            yield _sse({"type": "done"})
            return

        if cmd["action"] == "plan":
            if not ws:
                yield _sse({"type": "reply", "text": "No workspace configured.", "klar_action": None})
                yield _sse({"type": "done"})
                return
            plan_desc = cmd.get("description") or "the current campaign priority"
            resolved_brand_id = body.brand_id
            resolved_brand: Brand | None = await resolve_brand(db, resolved_brand_id)
            if not resolved_brand:
                named_brand = await find_brand_by_name(db, ws.id, plan_desc) if plan_desc else None
                if named_brand:
                    resolved_brand = named_brand
                    resolved_brand_id = str(named_brand.id)
                else:
                    all_brands_rows = (await db.execute(
                        select(Brand).where(Brand.workspace_id == ws.id).order_by(Brand.name.asc())
                    )).scalars().all()
                    if len(all_brands_rows) == 1:
                        resolved_brand = all_brands_rows[0]
                        resolved_brand_id = str(resolved_brand.id)
                    elif len(all_brands_rows) > 1:
                        names = ", ".join(b.name for b in all_brands_rows)
                        yield _sse({"type": "reply", "text": f"Which brand are we planning for?\n\nAvailable: {names}", "klar_action": None})
                        yield _sse({"type": "done"})
                        return
                    else:
                        yield _sse({"type": "reply", "text": "No brands set up yet.\n\nCreate one in Admin → Brands first.", "klar_action": None})
                        yield _sse({"type": "done"})
                        return
            plan_module_id = _marketing_plan_module_id()
            if not plan_module_id:
                yield _sse({"type": "reply", "text": "The planning specialist isn't installed yet.\n\nI can still discuss the plan in chat.", "klar_action": None})
                yield _sse({"type": "done"})
                return
            yield _sse({"type": "step", "label": "Building campaign plan..."})
            try:
                conversation_lines = [f"{h.role.upper()}: {h.text}" for h in body.history[-8:]] + [f"USER: {body.message}"]
                brief = await _brand_scoped_brief(db, ws, resolved_brand, {
                    "request": plan_desc, "objective": plan_desc,
                    "conversation_context": "\n".join(conversation_lines),
                    "constraints": "Create a draft plan artifact only. Do not execute, spend, send, publish, or mutate external systems.",
                })
                async for event in _run_modules_streaming(db, ws, [plan_module_id], brief, settings, None, UUID(resolved_brand_id) if resolved_brand_id else None, {}):
                    if event["type"] == "module_start":
                        yield _sse({"type": "step", "label": f"Running {event['label']}..."})
                    elif event["type"] == "module_result":
                        yield _sse({"type": "module_result", "artifact_ref": artifact_ref_from_run(event["run"]).model_dump()})
                brand_action = KlarAction(action="brand_switch", data={"brand_id": resolved_brand_id, "brand_name": resolved_brand.name}) if resolved_brand else None
                yield _sse({"type": "reply", "text": f"Plan draft ready for {resolved_brand.name}.\n\nReview it in Workspace.", "klar_action": brand_action.model_dump() if brand_action else None})
            except Exception as exc:
                logger.error("Native marketing plan failed: %s", exc)
                yield _sse({"type": "reply", "text": "Couldn't create the plan artifact.\n\nCheck provider readiness, then try again.", "klar_action": None})
            yield _sse({"type": "done"})
            return

        if cmd["action"] == "confirm":
            if not body.brand_id and ws:
                all_brands_rows = (await db.execute(select(Brand).where(Brand.workspace_id == ws.id))).scalars().all()
                if len(all_brands_rows) == 1:
                    body = ChatRequest(message=body.message, history=body.history, brand_id=str(all_brands_rows[0].id), campaign_id=body.campaign_id)
                else:
                    yield _sse({"type": "reply", "text": "Which brand are we working on?", "klar_action": None})
                    yield _sse({"type": "done"})
                    return
            plan_text = next((h.text for h in reversed(body.history) if h.role == "ai" and len(h.text) > 80), None)
            first_line = (plan_text or "").strip().splitlines()[0].lstrip("#- ").strip()
            campaign_name = first_line[:120] if first_line else "Campaign"
            brand_uuid = UUID(body.brand_id) if body.brand_id else None
            new_campaign = Campaign(workspace_id=ws.id, brand_id=brand_uuid, name=campaign_name, status="active")
            db.add(new_campaign)
            await db.flush()
            intent = IntentContract(contract_type="campaign", version="1.0.0", description=plan_text or campaign_name, criteria_json=[], scoring_json={})
            db.add(intent)
            await db.flush()
            db.add(CampaignIntent(campaign_id=new_campaign.id, intent_contract_id=intent.id, active=True))
            await db.commit()
            action = KlarAction(action="plan_confirmed", data={"campaign_id": str(new_campaign.id), "campaign_name": campaign_name})
            yield _sse({"type": "reply", "text": f"Plan confirmed.\n\n{campaign_name} is active.\n\nUse @klar run when you're ready.", "klar_action": action.model_dump()})
            yield _sse({"type": "done"})
            return

        if cmd["action"] == "run":
            if not body.brand_id and not body.campaign_id:
                yield _sse({"type": "reply", "text": "Which brand or campaign are we running?\n\nUse @klar plan first, or send the campaign name.", "klar_action": None})
                yield _sse({"type": "done"})
                return
            target = cmd.get("target", "").strip()
            campaign_uuid: UUID | None = None
            resolved_campaign_name = target or "this campaign"
            if body.campaign_id:
                try:
                    campaign_uuid = UUID(body.campaign_id)
                    c_row = (await db.execute(select(Campaign).where(Campaign.id == campaign_uuid))).scalar_one_or_none()
                    if c_row:
                        resolved_campaign_name = c_row.name
                except (ValueError, TypeError):
                    pass
            elif target:
                c_row = (await db.execute(select(Campaign).where(Campaign.name.ilike(f"%{target}%")).order_by(Campaign.created_at.desc()))).scalar_one_or_none()
                if c_row:
                    campaign_uuid = c_row.id
                    resolved_campaign_name = c_row.name
            body = ChatRequest(
                message=f"[RUN MODE] Execute the planned modules for campaign: {resolved_campaign_name}. Dispatch all relevant marketing modules now.",
                history=body.history, brand_id=body.brand_id,
                campaign_id=str(campaign_uuid) if campaign_uuid else body.campaign_id,
            )
            # fall through to LLM path below

        elif cmd["action"] == "evaluate":
            target = cmd.get("target") or "the current campaign"
            yield _sse({"type": "reply", "text": f"Evaluate mode is staged.\n\nPhase 5 will score {target}: pass, fail, or escalate.", "klar_action": KlarAction(action="evaluate_stub", data={"target": target}).model_dump()})
            yield _sse({"type": "done"})
            return

        elif cmd["action"] == "org":
            yield _sse({"type": "reply", "text": "Back to org level.\n\nNo brand is active.\nYou're talking cross-brand now.", "klar_action": KlarAction(action="brand_clear", data={}).model_dump()})
            yield _sse({"type": "done"})
            return

        elif cmd["action"] == "brief":
            yield _sse({"type": "reply", "text": "Your daily brief is in Stream.\n\nCheck signals, approvals, and campaign status there.", "klar_action": None})
            yield _sse({"type": "done"})
            return

        elif cmd["action"] == "directive" and not body.brand_id:
            yield _sse({"type": "reply", "text": "Which brand are we working on?", "klar_action": None})
            yield _sse({"type": "done"})
            return

    # ── Main LLM path ─────────────────────────────────────────────────────────
    yield _sse({"type": "step", "label": "Thinking..."})

    active_brand, inferred_brand_action = await _resolve_active_brand_for_turn(db, ws, body)
    if active_brand and body.brand_id != str(active_brand.id):
        body = ChatRequest(message=body.message, history=body.history, brand_id=str(active_brand.id), campaign_id=body.campaign_id)
        _resolved_brand_switch = _resolved_brand_switch or inferred_brand_action

    routed = route_chat_skills(body.message)
    if not routed.module_ids and len(body.message.strip().split()) <= 5 and body.history:
        recent_user_context = "\n".join(h.text for h in body.history[-6:] if h.role == "user")
        contextual_routed = route_chat_skills((recent_user_context + "\n" + body.message).strip())
        if contextual_routed.module_ids:
            routed = contextual_routed

    modules = await _chat_modules(db, active_brand.id if active_brand else None)
    activated_skill_ids = [route.skill.id for route in routed.routes]
    memory_slots = sorted({slot for route in routed.routes for slot in route.skill.memory_slots})

    scope_skill_manifest = next((s for s in list_skill_manifests() if s.id == "workspace.scope_resolution"), None)
    if scope_skill_manifest and ws and scope_skill_manifest.id not in activated_skill_ids and await _workspace_brands(db, ws):
        activated_skill_ids = [scope_skill_manifest.id] + activated_skill_ids
        memory_slots = sorted(set(memory_slots) | set(scope_skill_manifest.memory_slots))

    hydrated_memory = await hydrate_memory_slots(db, ws, memory_slots, brand=active_brand)
    loaded_skills = [get_skill(sid) for sid in activated_skill_ids]
    skill_sections = [format_activated_skill(s) for s in loaded_skills if s is not None]
    skill_context = "\n\n".join(skill_sections + ["## Hydrated Workspace Memory\n" + compile_memory_context(hydrated_memory)])

    system = await _build_system_prompt(db, ws, skill_context, brand=active_brand)
    messages: list[dict] = [{"role": "system", "content": system}]
    for h in body.history[-8:]:
        messages.append({"role": "user" if h.role == "user" else "assistant", "content": h.text})
    messages.append({"role": "user", "content": body.message})

    raw_reply = await _complete_cmo_messages(db, ws, settings, messages, plan_mode=False, brand_id=body.brand_id)

    if raw_reply is None:
        yield _sse({"type": "reply", "text": "I'm having trouble connecting right now.\n\nCheck provider settings, or try again in a moment.", "klar_action": None})
        yield _sse({"type": "done"})
        return

    scope_decision, reply_without_scope = _extract_scope_directive(raw_reply)
    triggered_actions = _extract_action_directives(reply_without_scope)
    triggered_modules = _RUN_RE.findall(reply_without_scope)
    reply_text = _strip_control_directives(raw_reply)

    scope_conversation_brand = await _resolve_scope_brand(db, ws, scope_decision.get("conversation_brand"))
    scope_execution_brand = await _resolve_scope_brand(db, ws, scope_decision.get("execution_brand"))
    execution_brand = scope_execution_brand

    allowed_module_ids = set(m["id"] for m in modules)
    invalid = [mid for mid in triggered_modules if mid not in allowed_module_ids]
    if invalid:
        logger.warning("LLM triggered modules outside allowed set — skipping: %s", invalid)
    triggered_modules = _dedupe_preserve_order([mid for mid in triggered_modules if mid in allowed_module_ids])

    run_results: list[RunResponse] = []

    active_campaign_uuid: UUID | None = None
    if body.campaign_id:
        try:
            active_campaign_uuid = UUID(body.campaign_id)
        except (ValueError, TypeError):
            pass

    if triggered_actions and not _user_authorized_artifact_action(body.message):
        logger.warning("CMO emitted unauthorized ACTION directives — skipping: %s", triggered_actions)
        triggered_actions = []

    if triggered_actions and ws:
        yield _sse({"type": "step", "label": "Executing approved artifact action..."})
        async for event in _run_actions_streaming(db, triggered_actions, settings):
            if event["type"] == "module_start":
                yield _sse({"type": "step", "label": f"Running {event['label']}..."})
            elif event["type"] == "module_result":
                run_results.append(event["run"])
                yield _sse({"type": "module_result", "artifact_ref": artifact_ref_from_run(event["run"]).model_dump()})

    if triggered_modules and ws:
        if await _workspace_brands(db, ws) and not execution_brand:
            yield _sse({"type": "reply", "text": reply_text or "Which brand is this artifact for?", "klar_action": KlarAction(action="pending_brand", data={"reason": "artifact_generation_requires_execution_brand"}).model_dump()})
            yield _sse({"type": "done"})
            return
        try:
            conversation_lines = [f"{h.role.upper()}: {h.text}" for h in body.history[-12:]] + [f"USER: {body.message}"]
            brief = await _brand_scoped_brief(db, ws, execution_brand or active_brand, {
                "request": body.message,
                "objective": body.message,
                "message": body.message,
                "conversation_context": "\n".join(conversation_lines),
                "cmo_directive_text": reply_without_scope,
            })
            active_brand_uuid: UUID | None = (execution_brand or active_brand).id if (execution_brand or active_brand) else None
            run_inline_params = _parse_run_inline_params(reply_without_scope)

            yield _sse({"type": "step", "label": "Routing to specialists..."})

            async for event in _run_modules_streaming(db, ws, triggered_modules, brief, settings, active_campaign_uuid, active_brand_uuid, run_inline_params):
                if event["type"] == "module_start":
                    yield _sse({"type": "step", "label": f"Running {event['label']}..."})
                elif event["type"] == "module_result":
                    run_results.append(event["run"])
                    yield _sse({"type": "module_result", "artifact_ref": artifact_ref_from_run(event["run"]).model_dump()})
        except Exception as exc:
            logger.error("Brief resolution failed: %s", exc)

    final_conversation_brand = scope_conversation_brand
    final_execution_brand = scope_execution_brand
    if run_results:
        async for loop_event in _continue_cmo_loop_after_results(
            db, ws, settings, messages, raw_reply, run_results, modules, body,
            active_brand, execution_brand, active_campaign_uuid,
        ):
            if loop_event["type"] == "step":
                yield _sse({"type": "step", "label": loop_event["label"]})
            elif loop_event["type"] == "module_start":
                yield _sse({"type": "step", "label": f"Running {loop_event['label']}..."})
            elif loop_event["type"] == "module_result":
                yield _sse({"type": "module_result", "artifact_ref": artifact_ref_from_run(loop_event["run"]).model_dump()})
            elif loop_event["type"] == "loop_complete":
                reply_text = loop_event["reply_text"]
                run_results = loop_event["run_results"]
                final_conversation_brand = loop_event["scope_conversation_brand"] or final_conversation_brand
                final_execution_brand = loop_event["scope_execution_brand"] or final_execution_brand

    scope_switch_brand = final_execution_brand if run_results else final_conversation_brand
    if scope_switch_brand and body.brand_id != str(scope_switch_brand.id):
        _final_klar = KlarAction(action="brand_switch", data={"brand_id": str(scope_switch_brand.id), "brand_name": scope_switch_brand.name})
    else:
        _final_klar = _resolved_brand_switch

    yield _sse({"type": "reply", "text": reply_text, "klar_action": _final_klar.model_dump() if _final_klar else None})
    yield _sse({"type": "done"})


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Streaming version of POST /chat. Returns SSE events as the pipeline progresses.

    Event types:
      {"type": "step", "label": str}            — pipeline phase label (live)
      {"type": "module_result", "artifact_ref"} — a module completed; artifact ready
      {"type": "reply", "text", "klar_action"}  — final CMO reply text
      {"type": "done"}                          — stream complete
    """
    settings = get_settings()

    async def generate():
        try:
            async for chunk in _generate_chat_stream(body, db, settings):
                yield chunk
        except Exception as exc:
            logger.error("chat_stream unhandled error: %s", exc)
            yield _sse({"type": "error", "message": "Something went wrong. Try again."})
            yield _sse({"type": "done"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await get_singleton(db)
    pending_plan_action = False  # set True when @klar plan falls through to LLM
    _resolved_brand_switch: KlarAction | None = None

    # ── Brand-reply detection (before @klar parsing) ──────────────────────────
    # When the previous AI message asked "Which brand?" and the user replies with
    # a short plain-text message, resolve the brand and replay the original @klar
    # command so the request proceeds as if brand_id had been set from the start.
    if not body.brand_id and ws and body.history:
        _last_ai = next((h.text for h in reversed(body.history) if h.role == "ai"), "")
        _last_user = body.message.strip()
        if ("Which brand" in _last_ai or "which brand" in _last_ai) and len(_last_user.split()) <= 4:
            _matched = await find_brand_by_name(db, ws.id, _last_user)
            if _matched:
                _original_cmd: str | None = None
                for _i in range(len(body.history) - 1, -1, -1):
                    _h = body.history[_i]
                    if _h.role == "ai" and ("Which brand" in _h.text or "which brand" in _h.text):
                        if _i > 0 and body.history[_i - 1].role == "user":
                            _original_cmd = body.history[_i - 1].text.strip()
                        break
                body = ChatRequest(
                    message=_original_cmd if _original_cmd else body.message,
                    history=body.history,
                    brand_id=str(_matched.id),
                    campaign_id=body.campaign_id,
                )
                _resolved_brand_switch = KlarAction(
                    action="brand_switch",
                    data={"brand_id": str(_matched.id), "brand_name": _matched.name},
                )

    # ── @council command routing ──────────────────────────────────────────────
    if _is_council_command(body.message):
        from council import start_session as _council_start
        _council_brief = _parse_council_brief(body.message)
        if not _council_brief:
            return ChatResponse(reply="What question should the council deliberate on?\n\nUsage: @council <question>")
        _council_brand: Brand | None = None
        if body.brand_id:
            _council_brand = (await db.execute(
                select(Brand).where(Brand.id == UUID(body.brand_id))
            )).scalar_one_or_none()
        _council_result = await _council_start(
            brief=_council_brief,
            db=db,
            ws=ws,
            brand=_council_brand,
        )
        if _council_result.get("error"):
            return ChatResponse(reply=_council_result["error"])
        return ChatResponse(
            reply="",
            klar_action=KlarAction(
                action="council_session",
                data={
                    "session_id": _council_result["session_id"],
                    "brief": _council_brief,
                    "status": _council_result["status"],
                    "current_round": _council_result["current_round"],
                    "rounds_completed": _council_result["rounds_completed"],
                    "rounds": _council_result["rounds"],
                    "c6_injections": _council_result["c6_injections"],
                    "pending_c6_prompt": _council_result["pending_c6_prompt"],
                },
            ),
        )

    # ── @klar command routing ─────────────────────────────────────────────────
    if _is_klar_command(body.message):
        cmd = _parse_klar_command(body.message)

        if cmd["action"] == "brand_switch":
            if not ws:
                return ChatResponse(reply="No workspace configured.")
            brand = await find_brand_by_name(db, ws.id, cmd["brand_name"])
            if not brand:
                all_brands = (await db.execute(
                    select(Brand).where(Brand.workspace_id == ws.id).order_by(Brand.name.asc())
                )).scalars().all()
                names = ", ".join(b.name for b in all_brands) or "none created yet"
                return ChatResponse(reply=f"I can’t find {cmd['brand_name']}.\n\nAvailable:\n{names}")
            bj = brand.brand_json or {}
            summary_parts = [p for p in [bj.get("voice"), bj.get("tone")] if p]
            summary = f" — {', '.join(summary_parts)}" if summary_parts else ""
            return ChatResponse(
                reply=f"Switched to {brand.name}{summary}.\n\nWorkspace context loaded.",
                klar_action=KlarAction(
                    action="brand_switch",
                    data={"brand_id": str(brand.id), "brand_name": brand.name},
                ),
            )

        if cmd["action"] == "list_brands":
            if not ws:
                return ChatResponse(reply="No workspace configured.")
            all_brands = (await db.execute(
                select(Brand).where(Brand.workspace_id == ws.id).order_by(Brand.name.asc())
            )).scalars().all()
            if not all_brands:
                return ChatResponse(reply="No brands yet.\n\nCreate one in Admin → Brands.")
            lines = [f"- {b.name}" for b in all_brands]
            return ChatResponse(
                reply="Brands:\n" + "\n".join(lines),
                klar_action=KlarAction(
                    action="brand_list",
                    data={"brands": [{"id": str(b.id), "name": b.name} for b in all_brands]},
                ),
            )

        if cmd["action"] == "pending":
            summary = await _pending_summary(db, ws)
            return ChatResponse(
                reply=summary,
                klar_action=KlarAction(action="pending_summary", data={}),
            )

        if cmd["action"] == "plan":
            if not ws:
                return ChatResponse(reply="No workspace configured.")

            plan_desc = cmd.get("description") or "the current campaign priority"
            resolved_brand_id = body.brand_id
            resolved_brand: Brand | None = await resolve_brand(db, resolved_brand_id)

            if not resolved_brand:
                # Generic brand resolution: if the plan text includes a known brand name,
                # use it. Otherwise single brand auto-selects; multiple brands ask once.
                named_brand = await find_brand_by_name(db, ws.id, plan_desc) if plan_desc else None
                if named_brand:
                    resolved_brand = named_brand
                    resolved_brand_id = str(named_brand.id)
                else:
                    all_brands_rows = (await db.execute(
                        select(Brand).where(Brand.workspace_id == ws.id).order_by(Brand.name.asc())
                    )).scalars().all()
                    if len(all_brands_rows) == 1:
                        resolved_brand = all_brands_rows[0]
                        resolved_brand_id = str(resolved_brand.id)
                    elif len(all_brands_rows) > 1:
                        names = ", ".join(b.name for b in all_brands_rows)
                        return ChatResponse(
                            reply=f"Which brand are we working on?\n\nAvailable: {names}",
                            klar_action=KlarAction(action="pending_klar", data={"command": body.message}),
                        )
                    else:
                        return ChatResponse(reply="No brands set up yet.\n\nCreate one in Admin → Brands first.")

            plan_module_id = _marketing_plan_module_id()
            if not plan_module_id:
                return ChatResponse(reply="The planning specialist isn’t installed yet.\n\nI can still discuss the plan in chat.")

            try:
                conversation_lines = [
                    f"{h.role.upper()}: {h.text}" for h in body.history[-8:]
                ] + [f"USER: {body.message}"]
                brief = await _brand_scoped_brief(db, ws, resolved_brand, {
                    "request": plan_desc,
                    "objective": plan_desc,
                    "conversation_context": "\n".join(conversation_lines),
                    "constraints": "Create a draft plan artifact only. Do not execute, spend, send, publish, or mutate external systems.",
                })
                result = await _execute_module(
                    db,
                    ws,
                    plan_module_id,
                    brief,
                    settings,
                    brand_id=UUID(resolved_brand_id) if resolved_brand_id else None,
                )
            except Exception as exc:
                logger.error("Native marketing plan failed: %s", exc)
                return ChatResponse(reply="I couldn’t create the plan artifact yet.\n\nCheck provider readiness, then try again.")

            return ChatResponse(
                reply=f"Plan draft is ready for {resolved_brand.name if resolved_brand else 'this brand'}.\n\nReview it in Workspace.",
                runs=[result],
                run=result,
                artifact_refs=[artifact_ref_from_run(result)],
                module_id=plan_module_id,
                klar_action=KlarAction(
                    action="brand_switch",
                    data={"brand_id": resolved_brand_id, "brand_name": resolved_brand.name},
                ) if resolved_brand and resolved_brand_id else None,
            )
        else:
            pending_plan_action = False

        if cmd["action"] == "confirm":
            if not body.brand_id and ws:
                all_brands_rows = (await db.execute(
                    select(Brand).where(Brand.workspace_id == ws.id)
                )).scalars().all()
                if len(all_brands_rows) == 1:
                    body = ChatRequest(message=body.message, history=body.history,
                                       brand_id=str(all_brands_rows[0].id), campaign_id=body.campaign_id)
                else:
                    return ChatResponse(reply="Which brand are we working on?")
            # Extract the most recent plan text from history (last AI turn).
            plan_text = next(
                (h.text for h in reversed(body.history) if h.role == "ai" and len(h.text) > 80),
                None,
            )
            # Derive a campaign name: first line of plan or fallback
            if plan_text:
                first_line = plan_text.strip().splitlines()[0].lstrip("#- ").strip()
                campaign_name = first_line[:120] if first_line else "Campaign"
            else:
                campaign_name = "Campaign"

            brand_uuid = UUID(body.brand_id) if body.brand_id else None
            new_campaign = Campaign(
                workspace_id=ws.id,
                brand_id=brand_uuid,
                name=campaign_name,
                status="active",
            )
            db.add(new_campaign)
            await db.flush()

            intent = IntentContract(
                contract_type="campaign",
                version="1.0.0",
                description=plan_text or campaign_name,
                criteria_json=[],
                scoring_json={},
            )
            db.add(intent)
            await db.flush()

            db.add(CampaignIntent(
                campaign_id=new_campaign.id,
                intent_contract_id=intent.id,
                active=True,
            ))
            await db.commit()

            return ChatResponse(
                reply=f"Plan confirmed.\n\n{campaign_name} is active.\n\nUse @klar run when you’re ready.",
                klar_action=KlarAction(
                    action="plan_confirmed",
                    data={"campaign_id": str(new_campaign.id), "campaign_name": campaign_name},
                ),
            )

        if cmd["action"] == "run":
            if not body.brand_id and not body.campaign_id:
                return ChatResponse(reply="Which brand or campaign are we running?\n\nUse @klar plan first, or send the campaign name.")
            target = cmd.get("target", "").strip()

            # Resolve campaign: explicit campaign_id in request, or lookup by name from target
            campaign_uuid: UUID | None = None
            resolved_campaign_name = target or "this campaign"
            if body.campaign_id:
                try:
                    campaign_uuid = UUID(body.campaign_id)
                    c_row = (await db.execute(select(Campaign).where(Campaign.id == campaign_uuid))).scalar_one_or_none()
                    if c_row:
                        resolved_campaign_name = c_row.name
                except (ValueError, TypeError):
                    pass
            elif target:
                c_row = (await db.execute(
                    select(Campaign).where(Campaign.name.ilike(f"%{target}%")).order_by(Campaign.created_at.desc())
                )).scalar_one_or_none()
                if c_row:
                    campaign_uuid = c_row.id
                    resolved_campaign_name = c_row.name

            # Fall through to LLM routing but with campaign context injected
            body = ChatRequest(
                message=f"[RUN MODE] Execute the planned modules for campaign: {resolved_campaign_name}. Dispatch all relevant marketing modules now.",
                history=body.history,
                brand_id=body.brand_id,
                campaign_id=str(campaign_uuid) if campaign_uuid else body.campaign_id,
            )

        if cmd["action"] == "evaluate":
            target = cmd.get("target") or "the current campaign"
            return ChatResponse(
                reply=f"Evaluate mode is staged.\n\nPhase 5 will score {target}: pass, fail, or escalate.\n\nThe intent hook is already live.",
                klar_action=KlarAction(action="evaluate_stub", data={"target": target}),
            )

        elif cmd["action"] == "org":
            return ChatResponse(
                reply="Back to org level.\n\nNo brand is active.\nYou’re talking cross-brand now.",
                klar_action=KlarAction(action="brand_clear", data={}),
            )

        elif cmd["action"] == "brief":
            return ChatResponse(
                reply="Your daily brief is in Stream.\n\nCheck signals, approvals, and campaign status there.",
            )

        elif cmd["action"] == "directive" and not body.brand_id:
            return ChatResponse(reply="Which brand are we working on?")

    active_brand, inferred_brand_action = await _resolve_active_brand_for_turn(db, ws, body)
    if active_brand and body.brand_id != str(active_brand.id):
        body = ChatRequest(
            message=body.message,
            history=body.history,
            brand_id=str(active_brand.id),
            campaign_id=body.campaign_id,
        )
        _resolved_brand_switch = _resolved_brand_switch or inferred_brand_action

    list_all()  # ensure plugin skill roots are registered before chat skill routing
    routed = route_chat_skills(body.message)
    if not routed.module_ids and len(body.message.strip().split()) <= 5 and body.history:
        recent_user_context = "\n".join(h.text for h in body.history[-6:] if h.role == "user")
        contextual_routed = route_chat_skills((recent_user_context + "\n" + body.message).strip())
        if contextual_routed.module_ids:
            routed = contextual_routed

    modules = await _chat_modules(db, active_brand.id if active_brand else None)
    user_message = body.message
    activated_skill_ids = [route.skill.id for route in routed.routes]
    memory_slots = sorted({slot for route in routed.routes for slot in route.skill.memory_slots})

    scope_skill_manifest = next(
        (s for s in list_skill_manifests() if s.id == "workspace.scope_resolution"), None
    )
    if scope_skill_manifest and ws and scope_skill_manifest.id not in activated_skill_ids and await _workspace_brands(db, ws):
        activated_skill_ids = [scope_skill_manifest.id] + activated_skill_ids
        memory_slots = sorted(set(memory_slots) | set(scope_skill_manifest.memory_slots))

    # Plan mode: front-load the plan_mode skill and its full resource memory set.
    # This replaces the plain PLAN MODE instruction injected into body.message
    # with a governed skill contract that declares all context slots explicitly.
    if pending_plan_action:
        plan_skill_manifest = next(
            (s for s in list_skill_manifests() if s.id == "workspace.plan_mode"), None
        )
        if plan_skill_manifest and plan_skill_manifest.id not in activated_skill_ids:
            activated_skill_ids = [plan_skill_manifest.id] + activated_skill_ids
            memory_slots = sorted(set(memory_slots) | set(plan_skill_manifest.memory_slots))

    hydrated_memory = await hydrate_memory_slots(db, ws, memory_slots, brand=active_brand)
    logger.info(
        "CMO context scope=%s brand_id=%s skills=%s memory_slots=%s",
        f"brand:{active_brand.name}" if active_brand else "workspace",
        body.brand_id,
        activated_skill_ids,
        memory_slots,
    )
    loaded_skills = [get_skill(skill_id) for skill_id in activated_skill_ids]
    skill_sections = [
        format_activated_skill(skill)
        for skill in loaded_skills
        if skill is not None
    ]
    skill_context = "\n\n".join(skill_sections + ["## Hydrated Workspace Memory\n" + compile_memory_context(hydrated_memory)])

    system = await _build_system_prompt(db, ws, skill_context, brand=active_brand)
    messages: list[dict] = [{"role": "system", "content": system}]
    for h in body.history[-8:]:
        messages.append({"role": "user" if h.role == "user" else "assistant", "content": h.text})
    messages.append({"role": "user", "content": user_message})

    raw_reply = await _complete_cmo_messages(db, ws, settings, messages, plan_mode=pending_plan_action, brand_id=body.brand_id)

    if raw_reply is None:
        logger.error("All chat providers failed — returning error to user")
        return ChatResponse(
            reply="I’m having trouble connecting right now.\n\nCheck provider settings, or try again in a moment.",
            runs=[],
            run=None,
            module_id=None,
        )

    scope_decision, reply_without_scope = _extract_scope_directive(raw_reply)
    triggered_actions = _extract_action_directives(reply_without_scope)
    triggered_modules = _RUN_RE.findall(reply_without_scope)
    reply_text = _strip_control_directives(raw_reply)

    scope_conversation_brand = await _resolve_scope_brand(db, ws, scope_decision.get("conversation_brand"))
    scope_execution_brand = await _resolve_scope_brand(db, ws, scope_decision.get("execution_brand"))
    execution_brand = scope_execution_brand
    logger.info("CMO scope decision: %s", {k: v for k, v in scope_decision.items() if k in _SCOPE_KEYS})

    # Plan mode: hard-zero all dispatch.
    if pending_plan_action:
        triggered_modules = []
    else:
        allowed_module_ids = set(m["id"] for m in modules)
        invalid = [mid for mid in triggered_modules if mid not in allowed_module_ids]
        if invalid:
            logger.warning("LLM triggered modules outside allowed set — skipping: %s", invalid)
        triggered_modules = _dedupe_preserve_order([mid for mid in triggered_modules if mid in allowed_module_ids])
        logger.warning("CMO dispatch: %s", triggered_modules)

    run_results: list[RunResponse] = []
    active_campaign_uuid: UUID | None = None
    if body.campaign_id:
        try:
            active_campaign_uuid = UUID(body.campaign_id)
        except (ValueError, TypeError):
            pass

    if triggered_actions and not _user_authorized_artifact_action(body.message):
        logger.warning("CMO emitted unauthorized ACTION directives — skipping: %s", triggered_actions)
        triggered_actions = []

    if triggered_actions and ws:
        async for event in _run_actions_streaming(db, triggered_actions, settings):
            if event["type"] == "module_result":
                run_results.append(event["run"])

    if triggered_modules and ws:
        if await _workspace_brands(db, ws) and not execution_brand:
            logger.warning("CMO blocked artifact dispatch without SCOPE execution_brand modules=%s scope=%s", triggered_modules, scope_decision)
            return ChatResponse(
                reply=reply_text or "Which brand is this artifact for?",
                klar_action=KlarAction(action="pending_brand", data={"reason": "artifact_generation_requires_execution_brand"}),
            )
        try:
            conversation_lines = [
                f"{h.role.upper()}: {h.text}" for h in body.history[-12:]
            ] + [f"USER: {body.message}"]
            chat_overrides = {
                "request": body.message,
                "objective": body.message,
                "message": body.message,
                "conversation_context": "\n".join(conversation_lines),
                "cmo_directive_text": reply_without_scope,
            }
            brief = await _brand_scoped_brief(db, ws, execution_brand or active_brand, chat_overrides)
            active_brand_uuid: UUID | None = (execution_brand or active_brand).id if (execution_brand or active_brand) else None

            run_inline_params = _parse_run_inline_params(reply_without_scope)
            async for event in _run_modules_streaming(
                db, ws, triggered_modules, brief, settings,
                active_campaign_uuid, active_brand_uuid, run_inline_params,
            ):
                if event["type"] == "module_result":
                    run_results.append(event["run"])
        except Exception as exc:
            logger.error("Brief resolution failed: %s", exc)

    final_conversation_brand = scope_conversation_brand
    final_execution_brand = scope_execution_brand
    if run_results:
        async for loop_event in _continue_cmo_loop_after_results(
            db, ws, settings, messages, raw_reply, run_results, modules, body,
            active_brand, execution_brand, active_campaign_uuid,
        ):
            if loop_event["type"] == "loop_complete":
                reply_text = loop_event["reply_text"]
                run_results = loop_event["run_results"]
                final_conversation_brand = loop_event["scope_conversation_brand"] or final_conversation_brand
                final_execution_brand = loop_event["scope_execution_brand"] or final_execution_brand

    if pending_plan_action:
        _final_klar = KlarAction(
            action="plan_draft",
            data={
                "brand_id": body.brand_id,
                "brand_name": active_brand.name if active_brand else None,
            },
        )
    else:
        scope_switch_brand = final_execution_brand if run_results else final_conversation_brand
        if scope_switch_brand and body.brand_id != str(scope_switch_brand.id):
            _final_klar = KlarAction(
                action="brand_switch",
                data={"brand_id": str(scope_switch_brand.id), "brand_name": scope_switch_brand.name},
            )
        else:
            _final_klar = _resolved_brand_switch

    return ChatResponse(
        reply=reply_text,
        runs=run_results,
        run=run_results[0] if run_results else None,
        artifact_refs=[artifact_ref_from_run(run) for run in run_results],
        module_id=triggered_modules[0] if triggered_modules else None,
        klar_action=_final_klar,
    )


@router.post("/chat/runs/{run_id}/revise", response_model=ChatResponse, status_code=201)
async def chat_revise_run(
    run_id: str,
    body: ChatReviseRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")

    row = (
        await db.execute(
            select(Run, RunResult)
            .join(RunResult, RunResult.run_id == Run.id, isouter=True)
            .where(Run.id == run_uuid)
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    original_run, original_result = row
    previous_content = original_result.content if original_result else ""
    feedback = body.feedback.strip() or "Make this draft stronger, clearer, and more conversion-focused while preserving the original intent."
    revise_brand: Brand | None = await resolve_brand(db, str(original_run.brand_id) if original_run.brand_id else None)
    modules = await _chat_modules(db, revise_brand.id if revise_brand else original_run.brand_id)
    module_cls = next((m for m in modules if m["id"] == original_run.module_id), None)
    channel = (module_cls.get("platform_hint") if module_cls else original_run.module_id.rsplit(".", 1)[-1]) or "asset"

    system = await _build_system_prompt(db, ws, brand=revise_brand) + """

Revision thread mode:
- The user is giving feedback on an existing generated asset.
- Respond as the CMO in 1–2 short mobile-friendly lines about the revision you are making.
- Do not mention module IDs, RUN syntax, APIs, or providers.
- Do not include the revised asset text; it will be rendered separately."""
    messages: list[dict] = [{"role": "system", "content": system}]
    for h in body.history[-8:]:
        messages.append({"role": "user" if h.role == "user" else "assistant", "content": h.text})
    messages.append({
        "role": "user",
        "content": (
            f"Revise this {channel} draft.\n\n"
            f"Previous draft:\n{previous_content}\n\n"
            f"My feedback:\n{feedback}"
        ),
    })

    raw_reply = await _complete_cmo_messages(db, ws, settings, messages, brand_id=str(original_run.brand_id) if original_run.brand_id else None)
    reply_text = (_strip_run_directives(raw_reply) if raw_reply else "Revised.\n\nReview the updated version in Workspace.")

    original_run.approval_status = "rejected"
    original_run.feedback = feedback
    await db.flush()

    brief = await _brand_scoped_brief(db, ws, revise_brand, {
        "revision_context": (
            "This is a revision request from a CMO review thread. Rewrite the asset using the feedback below; "
            "do not explain the changes, only output the revised asset.\n\n"
            f"Previous draft:\n{previous_content}\n\n"
            f"Requested change:\n{feedback}"
        )
    })
    revised = await _execute_module(
        db, ws, original_run.module_id, brief, settings,
        brand_id=revise_brand.id if revise_brand else None,
    )

    new_run = (await db.execute(select(Run).where(Run.id == UUID(revised.run_id)))).scalar_one_or_none()
    if new_run:
        new_run.parent_run_id = original_run.id
        await write_memory_event(
            db,
            workspace_id=ws.id,
            brand_id=revise_brand.id if revise_brand else original_run.brand_id,
            event_type="artifact_revised",
            topic_tags=[],
            summary=f"Artifact revised for {original_run.module_id}",
            rationale=feedback,
            source_ref=f"run:{new_run.id}",
            full_record={
                "original_run_id": str(original_run.id),
                "revised_run_id": str(new_run.id),
                "module_id": original_run.module_id,
                "feedback": feedback,
            },
        )
        await db.commit()

    return ChatResponse(
        reply=reply_text,
        runs=[revised],
        run=revised,
        artifact_refs=[artifact_ref_from_run(revised)],
        module_id=original_run.module_id,
    )
