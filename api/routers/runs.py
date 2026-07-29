"""Run execution and lifecycle — FastAPI router for /runs endpoints.

Architecture (refactored):
  - Endpoints live here (thin handlers)
  - Execution strategies → services/execution.py (SDK, tool, AI routing)
  - Brand context → services/brand_context.py
  - Contract hydration → services/contract_hydration.py
  - Brand kit injection → services/brand_kit.py
  - Media resolution → services/media_resolution.py
  - PM sync → services/pm_sync.py
  - Workflow persistence → services/workflow_persistence.py
  - Approval state machine → services/approval_state.py
  - Self-check repair → services/self_check.py
  - Export formatting → services/export_format.py
"""

import asyncio
import inspect
import json
import logging
import os
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from attachment_context import (
    brief_fields as attachment_brief_fields,
    enrich_drive_references,
    ensure_reference_identity,
    persist_chat_references,
)
from config import get_settings
from db import get_db
from errors import BosError
from hooks import BRIEF_BEFORE_DISPATCH, RUN_AFTER_COMPLETE, HookContext, get_registry as _get_hook_registry
from memory_events import write_memory_event
from models.document import WorkspaceDocument
from models.run import Run, RunAttempt, RunResult, RunTrace
from models.objective import Objective
from models.workspace import Brand, Workspace
from campaign import db as campaign_db
from plugin_loader import (
    get_active_plugin_ids,
    get_plugin_default_backend,
    get_plugin_for_module,
    inject_channel_credentials,
)
from registry import get_module
from routers.workspace import get_singleton
from schemas.runs import (
    RunExecutionOut,
    RunListItem,
    RunListResponse,
    RunRequest,
    RunResponse,
    RunResultOut,
    RunTraceOut,
)
from validation import NullableUUID, parse_optional_datetime, parse_optional_uuid
from data_hygiene import looks_like_fuzzer_text

# ── Extracted services ────────────────────────────────────────────────────────
from services.approval_state import (
    derive_approval_status,
    transition_on_approve,
    transition_on_reject,
    transition_on_revise,
    transition_on_action_failed,
)
from services.brand_context import (
    brand_fields_from_row,
    brand_handle_from_json,
    resolve_brief,
    scope_artifact_block,
)
from services.brand_kit import inject_brand_asset_spec, inject_campaign_brand_kit_style
from services.contract_hydration import hydrate_module_upstream_context
from services.execution import (
    execute_ai_routing,
    execute_sdk,
    execute_tool,
)
from services.export_format import format_for_platform
from services.media_resolution import (
    resolve_drive_attachment,
    resolve_drive_video,
)
from services.pm_sync import sync_run_to_pm, update_pm_task_status
from services.self_check import self_check_repair_guidance
from services.workflow_persistence import persist_workflow_record

router = APIRouter(tags=["runs"])
logger = logging.getLogger("bos.runs")


# ── Helpers (thin, kept in router because they're router-level concerns) ──────


def _creative_module_requires_live_campaign(module_id: str) -> bool:
    plugin = get_plugin_for_module(str(module_id or ""))
    if not plugin:
        return False
    modality = (plugin.manifest.default_backend or {}).get("modality") if plugin.manifest.default_backend else None
    return plugin.manifest.risk_policy == "generate_with_gates" and modality in {"image", "video"}


async def _resolve_live_campaign_for_creative_module(
    db: AsyncSession,
    ws: Workspace,
    *,
    module_id: str,
    campaign_id: UUID | None,
    brand_id: UUID | None,
) -> UUID | None:
    """Auto-bind one live campaign when unambiguous; otherwise leave unset.

    Campaign ambiguity belongs above specialist execution (CMO/work-order level),
    not inside individual creative modules. Creative runs should inherit an
    explicit campaign when one is already resolved, auto-bind only when exactly
    one active campaign exists, and otherwise continue with campaign_id=None so
    higher layers can decide whether to ask, infer, or stage the work.
    """
    if not _creative_module_requires_live_campaign(module_id):
        return campaign_id
    if not brand_id:
        return None

    if campaign_id:
        campaign = await campaign_db.get_campaign_record(
            db, campaign_id, workspace_id=ws.id, brand_id=brand_id
        )
        if not campaign or campaign.status != "active":
            raise BosError(
                409,
                "CAMPAIGN_SCOPE_MISMATCH",
                "The selected Campaign is not active for this workspace/brand.",
                {"campaign_id": str(campaign_id), "brand_id": str(brand_id)},
            )
        return campaign.id

    active = await campaign_db.active_campaigns(
        db, workspace_id=ws.id, brand_id=brand_id, limit=2
    )
    return active[0].id if len(active) == 1 else None


def _parse_run_uuid(run_id: str) -> UUID:
    try:
        return UUID(run_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["path", "run_id"], "msg": "value is not a valid UUID", "type": "uuid_parsing"}],
        )


def _scope_result_out(
    *,
    content: str,
    self_check: str,
    platform: str | None,
    block: dict | None,
    brand_id: Any = None,
    brand_name: str | None = None,
    brand_handle: str | None = None,
) -> RunResultOut:
    return RunResultOut(
        content=content,
        self_check=self_check,
        platform=platform,
        brand_name=brand_name,
        brand_handle=brand_handle,
        block=scope_artifact_block(block, brand_id=brand_id, brand_name=brand_name, brand_handle=brand_handle),
    )


async def _is_plugin_module_active(module_id: str, brand_id, db: AsyncSession) -> bool:
    plugin = get_plugin_for_module(module_id)
    if not plugin:
        return True
    return plugin.manifest.plugin_id in await get_active_plugin_ids(db, brand_id)


async def _is_plugin_platform_active(platform: str, brand_id, db: AsyncSession) -> bool:
    from plugin_loader import get_loaded_plugins
    active_ids = await get_active_plugin_ids(db, brand_id)
    for pid, state in get_loaded_plugins().items():
        if pid not in active_ids:
            continue
        if any(
            s.type in {"social_token", "social_meta_field"} and s.platform == platform
            for s in state.manifest.credential_slots
        ):
            return True
        if any(conn.platform == platform for conn in state.manifest.connections):
            return True
    return False


# ── Core execution dispatcher ─────────────────────────────────────────────────

async def _execute_module(
    db: AsyncSession,
    ws: Workspace,
    module_id: str,
    brief: dict,
    settings,
    policy: str | None = None,
    campaign_id: UUID | None = None,
    brand_id: UUID | None = None,
    _upstream_stack: tuple[str, ...] | None = None,
    _supporting: bool = False,
) -> RunResponse:
    """Route, execute, persist, and return a RunResponse for any module.

    Dispatches to one of three execution strategies based on module capabilities:
      1. SDK async execute()      → services/execution.py:execute_sdk
      2. Legacy execute_tool_result() → services/execution.py:execute_tool
      3. AI provider routing      → services/execution.py:execute_ai_routing
    """
    module_cls = get_module(module_id)
    if not module_cls:
        raise BosError(404, "MODULE_NOT_FOUND", f"Module '{module_id}' is not registered", None)

    # Plugin activation check
    plugin_state = get_plugin_for_module(module_id)
    if plugin_state:
        active_plugin_ids = await get_active_plugin_ids(db, brand_id)
        if plugin_state.manifest.plugin_id not in active_plugin_ids:
            raise BosError(
                403,
                "PLUGIN_INACTIVE",
                f"Plugin '{plugin_state.manifest.plugin_id}' is installed but not active for this Brand",
                {"plugin_id": plugin_state.manifest.plugin_id, "module_id": module_id, "brand_id": str(brand_id) if brand_id else None},
            )

    module = module_cls()
    eff_policy = policy or module.policy_default
    campaign_id = await _resolve_live_campaign_for_creative_module(
        db,
        ws,
        module_id=module_id,
        campaign_id=campaign_id,
        brand_id=brand_id,
    )

    # ── Brief enrichment pipeline ────────────────────────────────────────────

    # Brand scope
    if brand_id:
        brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
        if brand:
            scoped_brief = dict(brief)
            scoped_brief["brand_name"] = brand.name
            bj = brand.brand_json or {}
            for field in ("tone", "voice", "values", "domain", "website_url", "social_handles"):
                if bj.get(field):
                    scoped_brief[field] = bj[field]
            handle = brand_handle_from_json(bj)
            if handle:
                scoped_brief["brand_handle"] = handle
            if bj.get("domain") or bj.get("website_url"):
                scoped_brief.setdefault("display_url", bj.get("domain") or bj.get("website_url"))
            brief = scoped_brief

    # Execution context for report/intelligence artifacts. Channel modules should
    # be able to anchor insights to the selected campaign without trusting the
    # LLM to serialize campaign_id/campaign_name into every tool call.
    if campaign_id or (brand_id and ("report" in module_id or "insights" in module_id or "analytics" in module_id or "read" in module_id)):
        scoped_brief = dict(brief)
        try:
            if campaign_id:
                scoped_brief.setdefault("campaign_id", str(campaign_id))
                campaign = await campaign_db.get_campaign_record(
                    db, campaign_id, workspace_id=ws.id, brand_id=brand_id
                )
                if campaign:
                    scoped_brief.setdefault("campaign_name", campaign.name)
            if brand_id and "_campaign_index" not in scoped_brief:
                scoped_brief["_campaign_index"] = await campaign_db.campaign_index(
                    db, workspace_id=ws.id, brand_id=brand_id, limit=12
                )
        except Exception:
            logger.warning("Campaign context injection failed for module %s campaign_id=%s", module_id, campaign_id, exc_info=True)
        brief = scoped_brief

    # Brand asset spec for brand-locked generator plugins.
    plugin_state_for_assets = get_plugin_for_module(module_id)
    asset_modality = (plugin_state_for_assets.manifest.default_backend or {}).get("modality") if plugin_state_for_assets and plugin_state_for_assets.manifest.default_backend else None
    if brand_id and asset_modality in {"image", "video"}:
        brief = await inject_brand_asset_spec(brief, ws, brand_id, db)

    # Credential injection
    brief = await inject_channel_credentials(module_id, brief, brand_id, db, settings)

    # Brand kit style (image generation)
    if brief.get("image_prompt"):
        brief = await inject_campaign_brand_kit_style(brief, ws, brand_id, db)

    # Drive attachment resolution
    _drive_mime = str(brief.get("drive_file_mime") or "").lower()
    if brief.get("drive_file_id") and not _drive_mime.startswith("video/"):
        brief = await resolve_drive_attachment(brief, brand_id, db, settings, _is_plugin_platform_active_fn=_is_plugin_platform_active)

    # Drive video resolution
    if brief.get("video_path") or brief.get("drive_file_id"):
        brief = await resolve_drive_video(brief, brand_id, db, settings, _is_plugin_platform_active_fn=_is_plugin_platform_active)

    # Upstream contract hydration
    try:
        brief = await hydrate_module_upstream_context(
            db,
            ws,
            module_id,
            brief,
            brand_id,
            settings=settings,
            policy=eff_policy,
            campaign_id=campaign_id,
            upstream_stack=_upstream_stack,
            _execute_module_fn=_execute_module,
        )
    except BosError as upstream_exc:
        # Persist a failed Run so chat can surface an artifact reference
        failed_run = Run(
            workspace_id=ws.id, module_id=module_id, status="failed",
            campaign_id=campaign_id, brand_id=brand_id,
        )
        db.add(failed_run)
        await db.flush()
        db.add(RunTrace(
            run_id=failed_run.id,
            routing_json={"error": upstream_exc.message, "code": upstream_exc.code},
            lineage_json=None,
        ))
        await db.commit()
        raise

    # ── brief.before_dispatch hook ───────────────────────────────────────────
    _hook_ctx = HookContext(
        module_id=module_id,
        brand_id=brand_id,
        db=db,
        ws=ws,
        settings=settings,
    )
    brief = await _get_hook_registry().fire_filter(BRIEF_BEFORE_DISPATCH, brief, _hook_ctx)

    # ── Dispatch to execution strategy ───────────────────────────────────────

    _sdk_execute = getattr(module, "execute", None)
    if callable(_sdk_execute) and asyncio.iscoroutinefunction(_sdk_execute):
        return await execute_sdk(
            db, ws, module, module_id, brief, settings, eff_policy,
            campaign_id, brand_id, _supporting, _hook_ctx,
            _get_hook_registry_fn=_get_hook_registry,
            _sync_run_to_pm_fn=sync_run_to_pm,
        )

    tool_executor = getattr(module, "execute_tool_result", None)
    if callable(tool_executor):
        return await execute_tool(
            db, ws, module, module_id, brief, settings, eff_policy,
            campaign_id, brand_id, _supporting, _hook_ctx,
            _get_hook_registry_fn=_get_hook_registry,
            _sync_run_to_pm_fn=sync_run_to_pm,
        )

    return await execute_ai_routing(
        db, ws, module, module_id, brief, settings, eff_policy,
        campaign_id, brand_id, _supporting, _hook_ctx,
        _get_hook_registry_fn=_get_hook_registry,
        _sync_run_to_pm_fn=sync_run_to_pm,
    )


# ── POST /runs ─────────────────────────────────────────────────────────────────

@router.post("/runs", response_model=RunResponse, status_code=201,
             summary="Trigger a module run",
             responses={404: {"description": "Module not found"}, 412: {"description": "Workspace not initialized"}})
async def post_run(
    body: RunRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()

    module_cls = get_module(body.module_id)
    if not module_cls:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MODULE_NOT_FOUND", "message": f"Module '{body.module_id}' is not registered", "details": None}},
        )

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(
            status_code=412,
            detail={"error": {"code": "WORKSPACE_NOT_INITIALIZED", "message": "Initialize your workspace first: PUT /workspace/brand", "details": None}},
        )

    brief = await resolve_brief(db, ws, body.payload.brief.model_dump(exclude_none=True))
    return await _execute_module(
        db, ws, body.module_id, brief, settings, body.policy,
        campaign_id=body.campaign_id,
        brand_id=body.brand_id,
    )


# ── GET /runs ──────────────────────────────────────────────────────────────────

@router.get("/runs", response_model=RunListResponse, summary="List run history")
async def list_runs(
    module_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    approval_status: Optional[str] = Query(None),
    exclude_approval_status: Optional[str] = Query(None),
    brand_id: NullableUUID = Query(None),
    created_after: Optional[str] = Query(None),
    created_before: Optional[str] = Query(None),
    include_preview: bool = Query(False, description="Include compact result/block preview metadata with large inline assets stripped."),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    parsed_created_after = parse_optional_datetime(created_after, ["query", "created_after"])
    parsed_created_before = parse_optional_datetime(created_before, ["query", "created_before"])

    if status and looks_like_fuzzer_text(status):
        status = None
    if approval_status and looks_like_fuzzer_text(approval_status):
        approval_status = None
    if exclude_approval_status and looks_like_fuzzer_text(exclude_approval_status):
        exclude_approval_status = None
    if module_id and looks_like_fuzzer_text(module_id):
        module_id = None

    filters = []
    if module_id and module_id != "null":
        filters.append(Run.module_id == module_id)
    if status and status != "null":
        filters.append(Run.status == status)
    if approval_status and approval_status != "null":
        filters.append(Run.approval_status == approval_status)
    if exclude_approval_status and exclude_approval_status != "null":
        filters.append(or_(Run.approval_status.is_(None), Run.approval_status != exclude_approval_status))
    if brand_id is not None:
        filters.append(Run.brand_id == brand_id)
    if parsed_created_after:
        filters.append(Run.created_at >= parsed_created_after)
    if parsed_created_before:
        filters.append(Run.created_at <= parsed_created_before)

    count_stmt = select(func.count()).select_from(Run)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    if include_preview:
        stmt = select(Run, Brand, RunResult, RunTrace).join(
            Brand, Brand.id == Run.brand_id, isouter=True
        ).join(
            RunResult, RunResult.run_id == Run.id, isouter=True
        ).join(
            RunTrace, RunTrace.run_id == Run.id, isouter=True
        ).order_by(Run.created_at.desc()).limit(limit).offset(offset)
    else:
        stmt = select(Run, Brand).join(
            Brand, Brand.id == Run.brand_id, isouter=True
        ).order_by(Run.created_at.desc()).limit(limit).offset(offset)
    if filters:
        stmt = stmt.where(*filters)
    rows_with_attempts = (await db.execute(stmt)).all()

    run_ids = [row.Run.id for row in rows_with_attempts]
    campaign_ids = list({row.Run.campaign_id for row in rows_with_attempts if row.Run.campaign_id})
    campaign_name_by_id = await campaign_db.campaign_names(db, campaign_ids)
    attempt_by_run_id: dict[Any, RunAttempt] = {}
    if run_ids:
        attempts = (await db.execute(
            select(RunAttempt)
            .where(RunAttempt.run_id.in_(run_ids))
            .order_by(RunAttempt.created_at.desc())
        )).scalars().all()
        for attempt in attempts:
            attempt_by_run_id.setdefault(attempt.run_id, attempt)

    def _attempt_for(row: Any) -> RunAttempt | None:
        return attempt_by_run_id.get(row.Run.id)

    module_cache: dict[str, Any] = {}

    def _module_cls(mid: str) -> Any:
        if mid not in module_cache:
            module_cache[mid] = get_module(mid)
        return module_cache[mid]

    def _vertical(mid: str) -> str:
        cls = _module_cls(mid)
        return cls.vertical if cls else mid.split(".")[0]

    def _platform(mid: str) -> str | None:
        cls = _module_cls(mid)
        return cls.platform_hint if cls else None

    def _preview(row: Any) -> RunResultOut | None:
        if not include_preview or not getattr(row, "RunResult", None):
            return None
        lineage = row.RunTrace.lineage_json if getattr(row, "RunTrace", None) else {}
        block = (lineage or {}).get("block")
        if block:
            block = _with_video_proxy_url(_strip_large_block_assets(block))
        brand_name, brand_handle = brand_fields_from_row(getattr(row, "Brand", None))
        return _scope_result_out(
            content=row.RunResult.content,
            self_check=row.RunResult.self_check_verdict,
            platform=_platform(row.Run.module_id),
            block=block,
            brand_id=row.Run.brand_id,
            brand_name=brand_name,
            brand_handle=brand_handle,
        )

    return RunListResponse(
        runs=[
            RunListItem(
                run_id=str(r.Run.id),
                module_id=r.Run.module_id,
                vertical=_vertical(r.Run.module_id),
                status=r.Run.status,
                approval_status=r.Run.approval_status,
                campaign_id=str(r.Run.campaign_id) if r.Run.campaign_id else None,
                campaign_name=campaign_name_by_id.get(r.Run.campaign_id),
                brand_id=str(r.Run.brand_id) if r.Run.brand_id else None,
                brand_name=r.Brand.name if getattr(r, "Brand", None) else None,
                created_at=r.Run.created_at,
                provider=_attempt_for(r).provider if _attempt_for(r) else None,
                model=_attempt_for(r).model_id if _attempt_for(r) else None,
                latency_ms=_attempt_for(r).latency_ms if _attempt_for(r) else None,
                tokens=_attempt_for(r).tokens_output if _attempt_for(r) else None,
                cost=_attempt_for(r).provider_cost if _attempt_for(r) else None,
                result=_preview(r),
            )
            for r in rows_with_attempts
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── GET /runs/{run_id} ─────────────────────────────────────────────────────────

_LARGE_BLOCK_FIELDS = {
    "image_data_b64",
    "_image_data_b64",
    "content_b64",
    "audio_data_b64",
    "video_data_b64",
}


def _strip_large_block_assets(value: Any) -> Any:
    """Return a copy of a result block with large inline asset payloads removed."""
    if isinstance(value, dict):
        stripped = False
        out = {}
        for key, child in value.items():
            if key in _LARGE_BLOCK_FIELDS and isinstance(child, str) and child:
                stripped = True
                continue
            out[key] = _strip_large_block_assets(child)
        if stripped:
            out["asset_omitted"] = True
        return out
    if isinstance(value, list):
        return [_strip_large_block_assets(item) for item in value]
    return value


def _with_video_proxy_url(block: Any) -> Any:
    """Attach a same-origin preview URL only when the local video file exists."""
    if not isinstance(block, dict):
        return block
    path = str(block.get("video_path") or "").strip()
    filename = os.path.basename(path) if path else ""
    out = dict(block)
    out.pop("video_proxy_url", None)
    if filename and os.path.exists(path):
        out["video_proxy_url"] = f"/api/media/video/{filename}"
    return out


@router.get("/runs/{run_id}", response_model=RunResponse, summary="Get run detail with full trace",
            responses={404: {"description": "Run not found"}})
async def get_run(
    run_id: UUID,
    include_assets: bool = Query(True, description="Include large inline asset payloads such as image_data_b64."),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
    settings=Depends(get_settings),
):
    run_uuid = run_id
    detail_row = await db.execute(
        select(Run, RunAttempt, RunResult, RunTrace)
        .join(RunAttempt, RunAttempt.run_id == Run.id, isouter=True)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
        .where(Run.id == run_uuid)
        .limit(1)
    )
    row = detail_row.one_or_none()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' not found", "details": None}},
        )

    run, attempt, result, trace = row

    cls = get_module(run.module_id)
    vertical = cls.vertical if cls else run.module_id.split(".")[0]
    platform = cls.platform_hint if cls else None

    routing = trace.routing_json if trace else {}
    lineage = trace.lineage_json if trace else {}

    block = (lineage or {}).get("block")
    if block and include_assets and (block.get("video_path") or block.get("drive_file_id")):
        block = await resolve_drive_video(block, run.brand_id, db, settings, _is_plugin_platform_active_fn=_is_plugin_platform_active)
    if block and not include_assets:
        block = _strip_large_block_assets(block)
    if block:
        block = _with_video_proxy_url(block)

    brand = None
    if run.brand_id:
        brand = (await db.execute(select(Brand).where(Brand.id == run.brand_id))).scalar_one_or_none()
    brand_name, brand_handle = brand_fields_from_row(brand)

    return RunResponse(
        run_id=str(run.id),
        module_id=run.module_id,
        vertical=vertical,
        status=run.status,
        approval_status=run.approval_status,
        campaign_id=str(run.campaign_id) if run.campaign_id else None,
        brand_id=str(run.brand_id) if run.brand_id else None,
        brand_name=brand_name,
        result=_scope_result_out(
            content=result.content,
            self_check=result.self_check_verdict,
            platform=platform,
            block=block,
            brand_id=run.brand_id,
            brand_name=brand_name,
            brand_handle=brand_handle,
        ) if result else None,
        execution=RunExecutionOut(
            provider=attempt.provider,
            model=attempt.model_id,
            mode=attempt.mode,
            attempts=1,
            latency_ms=attempt.latency_ms or 0,
            tokens_used=attempt.tokens_output,
            provider_cost=attempt.provider_cost,
            sell_price=result.sell_price if result else None,
        ) if attempt else None,
        trace=RunTraceOut(
            capability=routing.get("capability", ""),
            policy=routing.get("policy", ""),
            candidates_considered=routing.get("candidates_considered", 0),
            candidates_filtered=routing.get("candidates_filtered", 0),
            winner=routing.get("winner"),
            routing_reason=routing.get("routing_reason", ""),
        ) if trace else None,
        created_at=run.created_at,
    )


# ── Approval Endpoints ────────────────────────────────────────────────────────

class ApprovalRequest(BaseModel):
    feedback: Optional[str] = None


class RunActionRequest(BaseModel):
    confirm: bool = False
    overrides: dict = Field(default_factory=dict)


class RunActionResponse(BaseModel):
    source_run_id: str
    source_approval_status: str
    action: str
    action_run: RunResponse


def _action_module_from_block(block: dict, action: str) -> str | None:
    """Resolve an approved artifact action to a module using plugin-provided block metadata."""
    allowed = block.get("allowed_actions") if isinstance(block, dict) else []
    action_modules = block.get("action_modules") if isinstance(block, dict) else {}
    if not isinstance(allowed, list) or action not in allowed:
        return None
    if not isinstance(action_modules, dict):
        return None
    module_id = action_modules.get(action)
    if not isinstance(module_id, str) or not module_id:
        return None
    legacy_aliases = {
        "meta.pages.post": "marketing.channel.meta.posts.publish",
    }
    return legacy_aliases.get(module_id, module_id)


def _brief_from_action_artifact(run: Run, result: RunResult, block: dict, overrides: dict | None = None, action: str | None = None) -> dict:
    """Build a minimal action brief from a reviewed artifact block."""
    brief = {
        k: v for k, v in (block or {}).items()
        if k not in {"allowed_actions", "action_modules"} and not k.startswith("_")
    }
    brief.update({
        "source_run_id": str(run.id),
        "source_module_id": run.module_id,
        "approved_artifact_type": (block or {}).get("type"),
        "original_artifact_block": block or {},
    })
    if action:
        brief["action"] = action
        brief["artifact_action"] = action
        if action == "render":
            brief["render_approved"] = True
        elif action == "revise":
            if brief.get("image_data_b64") and not brief.get("source_image_data_b64"):
                brief["source_image_data_b64"] = brief.get("image_data_b64")
            if brief.get("output_path") and not brief.get("source_image_path"):
                brief["source_image_path"] = brief.get("output_path")
    if not brief.get("message") and (block or {}).get("message"):
        brief["message"] = block["message"]
    if overrides:
        brief.update(overrides)
    if brief.get("_image_swapped"):
        for stale_key in (
            "image_data_b64",
            "source_image_data_b64",
            "_image_data_b64",
            "image_url",
            "output_path",
            "source_image_path",
            "image_path",
            "path",
        ):
            brief.pop(stale_key, None)
    return brief


def _revision_objective_text(payload: dict | None) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("revision_prompt", "edit_instruction", "revision_feedback", "feedback"):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            return str(value).strip()
    return ""


async def _merge_operator_revision_references_into_brief(
    brief: dict,
    refs: list[dict] | None,
    *,
    workspace_id: UUID | str | None,
    brand_id: UUID | str | None,
    campaign_id: UUID | str | None,
    db: AsyncSession,
    settings,
    objective: str | None = None,
) -> dict:
    """Enrich operator revision references and merge them into a module brief.

    This is the generic revision-reference contract used by plugin-owned revise
    endpoints and by legacy chat revision entrypoints. Operator attachments are
    converted into attachment-context fields plus prioritized
    ``reference_images`` records so image/video editors can use them without
    each plugin re-implementing Drive enrichment.
    """
    if not refs:
        return brief

    normalized_refs = [dict(ref) for ref in refs if isinstance(ref, dict)]
    if not normalized_refs:
        return brief

    for ref in normalized_refs:
        ensure_reference_identity(ref)

    brand_id_str = str(brand_id) if brand_id else None
    await enrich_drive_references(normalized_refs, brand_id_str, db, settings)
    await persist_chat_references(
        normalized_refs,
        workspace_id=workspace_id,
        brand_id=brand_id,
        campaign_id=campaign_id,
        db=db,
    )

    reference_fields = attachment_brief_fields(
        normalized_refs,
        brand_id=brand_id_str,
        objective=(objective or _revision_objective_text(brief) or None),
    )

    operator_revision_refs: list[dict] = []
    for idx, ref in enumerate(reference_fields.get("reference_images") or [], start=1):
        if not isinstance(ref, dict):
            continue
        enriched = dict(ref)
        enriched["revision_reference"] = True
        enriched["priority"] = "operator_revision"
        enriched["source"] = "operator_attachment"
        enriched.setdefault("role", "unknown_revision_reference")
        enriched.setdefault("panel_label", f"OPERATOR REVISION REF {idx} — use according to revision instruction")
        operator_revision_refs.append(enriched)

    for key, value in reference_fields.items():
        if key == "reference_images":
            continue
        if key not in brief and value not in (None, "", [], {}):
            brief[key] = value

    if operator_revision_refs:
        existing_refs = brief.get("reference_images") if isinstance(brief.get("reference_images"), list) else []
        brief["reference_images"] = operator_revision_refs + [r for r in existing_refs if isinstance(r, dict)]
        brief["operator_revision_reference_count"] = len(operator_revision_refs)

    return brief


@router.patch("/runs/{run_id}/approve", status_code=200, summary="Approve a run",
              responses={404: {"description": "Run not found"}})
async def approve_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    trace = (await db.execute(select(RunTrace).where(RunTrace.run_id == run.id))).scalar_one_or_none()
    block = ((trace.lineage_json or {}).get("block") if trace and trace.lineage_json else None) or {}
    action_modules = block.get("action_modules") if isinstance(block, dict) else {}

    # If an artifact declares that approve maps to a render transition, execute
    # that declared action. Core does not branch on plugin artifact types.
    if isinstance(action_modules, dict) and action_modules.get("render"):
        if "render" in (block.get("allowed_actions") or []):
            return await execute_declared_run_action(db, str(run_id), "render", get_settings())
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "ACTION_NOT_AVAILABLE", "message": "This artifact is not currently renderable. Revise or refresh the draft before approving render.", "details": {"run_id": str(run_id), "status": block.get("status"), "allowed_actions": block.get("allowed_actions")}}},
        )

    run.approval_status = transition_on_approve(run.approval_status or "pending")
    run.feedback = None
    await write_memory_event(
        db,
        workspace_id=run.workspace_id,
        brand_id=run.brand_id,
        campaign_id=run.campaign_id,
        event_type="artifact_approved",
        topic_tags=[],
        summary=f"Artifact approved for {run.module_id}",
        source_ref=f"run:{run.id}",
        full_record={"run_id": str(run.id), "module_id": run.module_id, "approval_status": "approved"},
    )
    await db.commit()

    if run.brand_id:
        _brand = (await db.execute(select(Brand).where(Brand.id == run.brand_id))).scalar_one_or_none()
        if _brand:
            await update_pm_task_status(
                run, "approved", _brand, db, get_settings(),
                _is_plugin_module_active_fn=_is_plugin_module_active,
                _get_module_fn=get_module,
                _inject_channel_credentials_fn=inject_channel_credentials,
            )

    return {"run_id": run_id, "approval_status": "approved"}


class AttachImageRequest(BaseModel):
    drive_file_id: str
    drive_file_name: str = ""
    drive_file_mime: str = "image/jpeg"


@router.patch("/runs/{run_id}/attach-image", status_code=200,
              summary="Attach a Drive image to a pending artifact",
              responses={404: {"description": "Run not found"}})
async def attach_image_to_run(
    run_id: UUID,
    body: AttachImageRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    row = (await db.execute(
        select(Run, RunTrace).join(RunTrace, RunTrace.run_id == Run.id).where(Run.id == run_id)
    )).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    run, trace = row
    if not run.brand_id:
        raise HTTPException(status_code=400, detail={"error": {"code": "BRAND_REQUIRED", "message": "Artifact image swaps require a brand-scoped run.", "details": {"run_id": str(run_id)}}})

    # Validate that the selected Drive file is accessible through the artifact's
    # own brand connection and is actually an image. Do not trust caller-supplied
    # file name/mime for artifact swaps.
    from routers.social import get_page_token, _load_google_drive_client, _drive_reauth_exception, _mark_drive_reauth_required
    DriveClient = _load_google_drive_client()
    token, _ = await get_page_token(db, str(run.brand_id), "google_drive", get_settings())
    if not token:
        raise _drive_reauth_exception()
    try:
        with DriveClient(token) as drive:
            meta = drive.get_file_meta(body.drive_file_id)
    except Exception as exc:
        if getattr(getattr(exc, "response", None), "status_code", None) in (401, 403):
            await _mark_drive_reauth_required(db, str(run.brand_id))
            raise _drive_reauth_exception() from exc
        raise HTTPException(status_code=400, detail={"error": {"code": "DRIVE_FILE_NOT_ACCESSIBLE", "message": "Selected Drive file is not accessible from this brand connection.", "details": None}}) from exc
    mime = str(meta.get("mimeType") or body.drive_file_mime or "")
    if not mime.startswith("image/"):
        raise HTTPException(status_code=400, detail={"error": {"code": "DRIVE_FILE_NOT_IMAGE", "message": "Artifact image swap requires an image file.", "details": {"mimeType": mime}}})

    lineage = dict(trace.lineage_json or {})
    block = dict(lineage.get("block") or {})
    block["drive_file_id"] = body.drive_file_id
    block["drive_file_name"] = str(meta.get("name") or body.drive_file_name or body.drive_file_id)
    block["drive_file_mime"] = mime
    block["drive_web_view_link"] = meta.get("webViewLink") or block.get("drive_web_view_link")
    block["image_swapped"] = True
    # Remove embedded/generated image bytes so future publish actions resolve
    # the selected Drive file instead of reusing the original artifact image.
    block.pop("image_url", None)
    block.pop("image_data_b64", None)
    block.pop("_image_data_b64", None)
    lineage["block"] = block
    trace.lineage_json = lineage
    await db.commit()

    return {"run_id": run_id, "drive_file_id": body.drive_file_id, "drive_file_name": body.drive_file_name}


async def execute_declared_run_action(
    db: AsyncSession,
    run_id: str,
    action: str,
    settings,
    overrides: dict | None = None,
) -> RunActionResponse:
    """Execute an action declared by a persisted artifact block.

    Generic core primitive used by Stream/Workspace and CMO chat.
    """
    run_uuid = _parse_run_uuid(run_id)

    row = (await db.execute(
        select(Run, RunResult, RunTrace)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
        .where(Run.id == run_uuid)
    )).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    source_run, source_result, source_trace = row
    if not source_result:
        raise HTTPException(status_code=404, detail="Run result not found")

    block = ((source_trace.lineage_json or {}).get("block") if source_trace else None) or {}
    if not isinstance(block, dict):
        block = {}

    action_module_id = _action_module_from_block(block, action)
    if not action_module_id:
        raise HTTPException(status_code=400, detail={"error": {"code": "ACTION_NOT_AVAILABLE", "message": f"Artifact does not declare action '{action}'", "details": {"run_id": run_id}}})
    if not get_module(action_module_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "ACTION_MODULE_NOT_FOUND", "message": f"Action module '{action_module_id}' is not installed", "details": None}})

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    brand_count = (await db.execute(select(func.count()).select_from(Brand).where(Brand.workspace_id == ws.id))).scalar_one()
    if brand_count > 0 and not source_run.brand_id:
        raise HTTPException(status_code=400, detail={"error": {"code": "BRAND_REQUIRED", "message": "Approved external actions require a brand-scoped artifact", "details": {"run_id": run_id}}})

    workflow = block.get("workflow") if isinstance(block.get("workflow"), dict) else {}
    transition_holds_source = bool(workflow and action in {"render", "generate_video"} and action_module_id != source_run.module_id)

    if source_run.approval_status != "approved" and not transition_holds_source:
        source_run.approval_status = transition_on_approve(source_run.approval_status or "pending")
        source_run.feedback = None
        await write_memory_event(
            db,
            workspace_id=source_run.workspace_id,
            brand_id=source_run.brand_id,
            campaign_id=source_run.campaign_id,
            event_type="artifact_approved",
            topic_tags=[],
            summary=f"Artifact approved for {source_run.module_id}",
            source_ref=f"run:{source_run.id}",
            full_record={"run_id": str(source_run.id), "module_id": source_run.module_id, "approval_status": "approved", "action": action},
        )
        await db.commit()
    elif transition_holds_source:
        source_run.approval_status = "pending"
        await db.commit()

    if source_run.brand_id and not transition_holds_source:
        _brand = (await db.execute(select(Brand).where(Brand.id == source_run.brand_id))).scalar_one_or_none()
        if _brand:
            await update_pm_task_status(
                source_run, "approved", _brand, db, settings,
                _is_plugin_module_active_fn=_is_plugin_module_active,
                _get_module_fn=get_module,
                _inject_channel_credentials_fn=inject_channel_credentials,
            )

    action_brief = _brief_from_action_artifact(source_run, source_result, block, overrides, action=action)
    operator_refs = action_brief.pop("operator_references", None)
    if isinstance(operator_refs, list) and operator_refs:
        action_brief = await _merge_operator_revision_references_into_brief(
            action_brief,
            operator_refs,
            workspace_id=ws.id,
            brand_id=source_run.brand_id,
            campaign_id=source_run.campaign_id,
            db=db,
            settings=settings,
        )

    action_run = await _execute_module(
        db,
        ws,
        action_module_id,
        action_brief,
        settings,
        campaign_id=source_run.campaign_id,
        brand_id=source_run.brand_id,
    )

    source_approval_status = "pending" if transition_holds_source else "approved"
    try:
        action_uuid = UUID(action_run.run_id)
        action_row = (await db.execute(select(Run).where(Run.id == action_uuid))).scalar_one_or_none()
        action_block = action_run.result.block if action_run.result and isinstance(action_run.result.block, dict) else {}
        action_succeeded = action_block.get("status") == "succeeded" or (action_run.status == "success" and action_block.get("status") != "failed")
        if action_row and action_succeeded:
            if isinstance(action_block, dict) and action_block.get("approval_status"):
                next_status = str(action_block.get("approval_status") or "pending")
                action_row.approval_status = next_status
                action_run.approval_status = next_status
            elif transition_holds_source:
                action_row.approval_status = "pending"
                action_run.approval_status = "pending"
            else:
                action_row.approval_status = "approved"
                action_run.approval_status = "approved"
        elif action_row and not action_succeeded:
            source_run.approval_status = transition_on_action_failed(source_run.approval_status or "pending")
            source_approval_status = "pending"
        await db.commit()
    except Exception:
        logger.exception("Could not reconcile action approval state for source run %s", source_run.id)

    return RunActionResponse(
        source_run_id=run_id,
        source_approval_status=source_approval_status,
        action=action,
        action_run=action_run,
    )


@router.post("/runs/{run_id}/actions/{action}", response_model=RunActionResponse,
             summary="Execute an approved artifact action",
             responses={404: {"description": "Run not found"}, 400: {"description": "Action not available or confirm not set"}})
async def execute_run_action(
    run_id: UUID,
    action: str,
    body: RunActionRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """HTTP wrapper for executing a plugin-declared artifact action."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail={"error": {"code": "CONFIRM_REQUIRED", "message": "Set confirm=true to execute an external action", "details": {"action": action}}})
    return await execute_declared_run_action(db, str(run_id), action, get_settings(), body.overrides)


@router.delete("/runs/{run_id}", status_code=200, summary="Delete a run artifact",
               responses={404: {"description": "Run not found"}})
async def delete_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    await write_memory_event(
        db,
        workspace_id=run.workspace_id,
        brand_id=run.brand_id,
        campaign_id=run.campaign_id,
        event_type="artifact_deleted",
        topic_tags=[],
        summary=f"Artifact deleted for {run.module_id}",
        rationale="Deleted by operator from Stream or artifact review.",
        source_ref=f"run:{run.id}",
        full_record={
            "run_id": str(run.id),
            "module_id": run.module_id,
            "deleted": True,
        },
    )
    await db.execute(update(Run).where(Run.parent_run_id == run.id).values(parent_run_id=None))
    await db.delete(run)
    await db.commit()
    return {"run_id": run_id, "deleted": True}



@router.patch("/runs/{run_id}/reject", status_code=200, summary="Reject a run with feedback",
              responses={404: {"description": "Run not found"}})
async def reject_run(
    run_id: UUID,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run.approval_status = transition_on_reject(run.approval_status or "pending")
    run.feedback = body.feedback
    await write_memory_event(
        db,
        workspace_id=run.workspace_id,
        brand_id=run.brand_id,
        campaign_id=run.campaign_id,
        event_type="artifact_dismissed",
        topic_tags=[],
        summary=f"Artifact rejected for {run.module_id}",
        rationale=body.feedback,
        source_ref=f"run:{run.id}",
        full_record={
            "run_id": str(run.id),
            "module_id": run.module_id,
            "approval_status": "rejected",
            "feedback": body.feedback,
        },
    )
    await db.commit()

    if run.brand_id:
        _brand = (await db.execute(select(Brand).where(Brand.id == run.brand_id))).scalar_one_or_none()
        if _brand:
            await update_pm_task_status(
                run, "rejected", _brand, db, get_settings(),
                _is_plugin_module_active_fn=_is_plugin_module_active,
                _get_module_fn=get_module,
                _inject_channel_credentials_fn=inject_channel_credentials,
            )

    return {"run_id": run_id, "approval_status": "rejected", "feedback": body.feedback}


@router.post("/runs/{run_id}/revise", status_code=201, summary="Revise a rejected run",
             responses={404: {"description": "Run not found"}, 400: {"description": "Run is not in rejected state"}})
async def revise_run(
    run_id: UUID,
    body: ApprovalRequest = ApprovalRequest(),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    row = (await db.execute(
        select(Run, RunResult, RunTrace)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
        .where(Run.id == run_id)
    )).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    run, run_result, run_trace = row

    if body.feedback:
        run.approval_status = transition_on_reject(run.approval_status or "pending")
        run.feedback = body.feedback
        await db.flush()

    if run.approval_status != "rejected":
        raise HTTPException(status_code=400, detail="Can only revise rejected runs")

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    settings = get_settings()
    previous_content = run_result.content if run_result else ""
    feedback = body.feedback or run.feedback or "Improve this draft while preserving the original intent."
    brief = {
        "revision_context": (
            "This is a revision request. Rewrite the asset using the feedback below; "
            "do not explain the changes, only output the revised asset.\n\n"
            f"Previous draft:\n{previous_content}\n\n"
            f"Requested change:\n{feedback}"
        )
    }

    response = await _execute_module(db, ws, run.module_id, brief, settings)

    new_run_result = await db.execute(
        select(Run).where(Run.id == UUID(response.run_id))
    )
    new_run = new_run_result.scalar_one_or_none()
    if new_run:
        new_run.parent_run_id = run.id
        await write_memory_event(
            db,
            workspace_id=run.workspace_id,
            brand_id=run.brand_id,
            campaign_id=run.campaign_id,
            event_type="artifact_revised",
            topic_tags=[],
            summary=f"Artifact revised for {run.module_id}",
            rationale=feedback,
            source_ref=f"run:{new_run.id}",
            full_record={
                "original_run_id": str(run.id),
                "revised_run_id": str(new_run.id),
                "module_id": run.module_id,
                "feedback": feedback,
            },
        )
        await db.commit()

    return response


# ── Chat revise endpoint ──────────────────────────────────────────────────────

class ChatReviseRequest(BaseModel):
    feedback: str = ""
    history: list = []
    references: list = []


class ChatReviseResponse(BaseModel):
    reply: str
    runs: list[RunResponse] = []
    run: RunResponse | None = None
    module_id: str | None = None


@router.post("/chat/runs/{run_id}/revise", response_model=ChatReviseResponse, status_code=201,
             summary="Revise an artifact via CMO chat (approval bundle revision button)")
async def chat_revise_run(
    run_id: UUID,
    body: ChatReviseRequest = ChatReviseRequest(),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Revision endpoint called by the approval bundle's 'Create revision' button."""
    row = (await db.execute(
        select(Run, RunResult, RunTrace)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
        .where(Run.id == run_id)
    )).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    source_run, source_result, source_trace = row
    block = ((source_trace.lineage_json or {}).get("block") if source_trace else None) or {}
    if not isinstance(block, dict):
        block = {}

    allowed = block.get("allowed_actions") if isinstance(block.get("allowed_actions"), list) else []
    modules = block.get("action_modules") if isinstance(block.get("action_modules"), dict) else {}
    revise_module_id = modules.get("revise") if "revise" in allowed else source_run.module_id

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    settings = get_settings()
    feedback = (body.feedback or "").strip() or "Make this draft stronger while preserving the original intent."

    refs = [dict(r) for r in (body.references or []) if isinstance(r, dict)]
    if refs and source_run.module_id == "postcraft.render":
        invalid_image_refs = [
            str(ref.get("title") or ref.get("drive_file_name") or ref.get("drive_file_id") or "attachment")
            for ref in refs
            if str(ref.get("kind") or "").lower() != "image"
            or (ref.get("mime_type") and not str(ref.get("mime_type")).lower().startswith("image/"))
        ]
        if invalid_image_refs:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "POSTCRAFT_IMAGE_REFERENCE_REQUIRED",
                        "message": "Postcraft image revisions accept image attachments only.",
                        "details": {"invalid_references": invalid_image_refs},
                    }
                },
            )

    skip = {"allowed_actions", "action_modules", "status", "message", "content"}
    brief: dict = {k: v for k, v in block.items() if k not in skip and not str(k).startswith("_")}
    if refs:
        brief = await _merge_operator_revision_references_into_brief(
            brief,
            refs,
            workspace_id=ws.id,
            brand_id=source_run.brand_id,
            campaign_id=source_run.campaign_id,
            db=db,
            settings=settings,
            objective=feedback,
        )
    brief.update({
        "source_run_id": str(run_id),
        "edit_instruction": feedback,
        "revision_prompt": feedback,
        "revision_feedback": feedback,
        "previous_content": source_result.content if source_result else "",
        "original_artifact_block": block,
        "artifact_data": block,
    })
    if block.get("image_data_b64") and "source_image_data_b64" not in brief:
        brief["source_image_data_b64"] = block["image_data_b64"]
    if block.get("output_path") and "source_image_path" not in brief:
        brief["source_image_path"] = block["output_path"]

    response = await _execute_module(
        db, ws, str(revise_module_id), brief, settings,
        campaign_id=source_run.campaign_id,
        brand_id=source_run.brand_id,
    )
    new_run = (await db.execute(select(Run).where(Run.id == UUID(response.run_id)))).scalar_one_or_none()
    if new_run:
        new_run.parent_run_id = source_run.id
        source_run.approval_status = transition_on_revise(source_run.approval_status or "pending")
        await db.commit()

    block_type = str(block.get("type") or "")
    module_str = str(revise_module_id or "")
    if "video" in block_type or "motion" in module_str:
        reply = "Processing your video edit. The revised video will appear as a new Needs approval artifact."
    elif "image" in block_type or "image" in module_str:
        reply = "Processing your image revision. The updated artifact will appear as a new Needs approval item."
    else:
        reply = "I applied your requested changes. The revised artifact is ready for approval."

    return ChatReviseResponse(reply=reply, runs=[response], run=response, module_id=str(revise_module_id))


# ── Export Endpoints ───────────────────────────────────────────────────────────

class ExportResponse(BaseModel):
    run_id: str
    module_id: str
    platform: Optional[str]
    content: str
    formatted: dict
    self_check: str


@router.get("/runs/{run_id}/export", response_model=ExportResponse,
            summary="Export run content in copy-paste ready format",
            responses={404: {"description": "Run not found"}})
async def export_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Export run content formatted for easy copy-pasting to the platform."""
    run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run_result = (await db.execute(
        select(RunResult).where(RunResult.run_id == run_id)
    )).scalars().first()
    if not run_result:
        raise HTTPException(status_code=404, detail="Run result not found")

    cls = get_module(run.module_id)
    platform = cls.platform_hint if cls else "unknown"

    formatted = format_for_platform(platform, run_result.content)

    return ExportResponse(
        run_id=str(run_id),
        module_id=run.module_id,
        platform=platform,
        content=run_result.content,
        formatted=formatted,
        self_check=run_result.self_check_verdict,
    )


# ── Backward-compatible re-exports ────────────────────────────────────────────
# Other modules (onboarding, campaigns, agent, cmo_tools, tests, scripts)
# import from routers.runs. These aliases keep those imports working.

from services.brand_context import resolve_brief as _resolve_brief
from services.brand_kit import extract_visual_constraints as _extract_visual_constraints
from services.brand_kit import inject_campaign_brand_kit_style as _inject_campaign_brand_kit_style
from services.execution import _apply_backend_ref_to_brief
from services.pm_sync import update_pm_task_status as _update_pm_task_status

# _execute_module and execute_declared_run_action are defined in this file
# and are already importable by name.

__all__ = [
    "_execute_module",
    "_resolve_brief",
    "_extract_visual_constraints",
    "_inject_campaign_brand_kit_style",
    "_apply_backend_ref_to_brief",
    "_update_pm_task_status",
    "execute_declared_run_action",
    "list_runs",
]
