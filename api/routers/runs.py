import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from auth import require_api_key
from capability_router import route
from config import get_settings
from plugin_loader import inject_channel_credentials
from db import get_db
from errors import BosError
from executor import execute_live, execute_mock, get_platform_key
from memory_events import write_memory_event
from model_overrides import effective_strict, get_module_model_override, reorder_candidates_for_model_override
from provider_auth import resolve_stored_provider_credential
from routers.backend_settings import resolve_backend_override
from models.document import WorkspaceDocument
from models.run import Run, RunAttempt, RunResult, RunTrace
from models.workspace import Audience, Brand, Campaign, Product, Workspace
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

router = APIRouter(tags=["runs"])
logger = logging.getLogger("bos.runs")


# ── Brief resolution ───────────────────────────────────────────────────────────

async def _resolve_brief(db: AsyncSession, ws: Workspace, brief: dict) -> dict:
    """Merge workspace context into brief. Explicit brief fields always win."""
    resolved = dict(brief)

    # Brand context
    if not resolved.get("brand_name") and ws.name:
        resolved["brand_name"] = ws.name

    if ws.brand_json:
        for field in ("tone", "voice", "values", "domain", "website_url", "social_handles"):
            if not resolved.get(field) and ws.brand_json.get(field):
                resolved[field] = ws.brand_json[field]
        social_handles = ws.brand_json.get("social_handles") or {}
        if not resolved.get("brand_handle"):
            resolved["brand_handle"] = social_handles.get("x") or social_handles.get("twitter") or social_handles.get("instagram")
        if not resolved.get("display_url"):
            resolved["display_url"] = ws.brand_json.get("domain") or ws.brand_json.get("website_url")

    # Product context
    if not resolved.get("product_name"):
        prod_row = await db.execute(
            select(Product).where(Product.workspace_id == ws.id).limit(1)
        )
        prod = prod_row.scalar_one_or_none()
        if prod:
            resolved["product_name"] = prod.name
            if not resolved.get("tagline") and prod.tagline:
                resolved["tagline"] = prod.tagline
            if prod.benefits_json:
                benefits = prod.benefits_json.get("benefits", [])
                if benefits:
                    if not resolved.get("key_benefit"):
                        resolved["key_benefit"] = benefits[0]
                    resolved["benefits"] = benefits  # full list

    # Audience context
    if not resolved.get("audience"):
        aud_row = await db.execute(
            select(Audience).where(Audience.workspace_id == ws.id).limit(1)
        )
        aud = aud_row.scalar_one_or_none()
        if aud:
            resolved["audience"] = aud.name
            if aud.segment_json:
                if not resolved.get("demographics") and aud.segment_json.get("demographics"):
                    resolved["demographics"] = aud.segment_json["demographics"]
                if not resolved.get("pain_points") and aud.segment_json.get("pain_points"):
                    resolved["pain_points"] = aud.segment_json["pain_points"]

    return resolved


# ── Image pre-generation (injected into brief before channel module dispatch) ──

async def _inject_campaign_brand_kit_style(
    brief: dict,
    ws: Workspace,
    brand_id,
    db: AsyncSession,
) -> dict:
    """Attach approved Campaign Brand Kit excerpt/style constraints for image generation."""
    if brief.get("campaign_brand_kit_excerpt") or brief.get("brand_visual_constraints"):
        return brief

    filters = [
        WorkspaceDocument.workspace_id == ws.id,
        WorkspaceDocument.doc_type == "campaign_brand_kit",
        WorkspaceDocument.status == "approved",
    ]
    if brand_id:
        filters.append(WorkspaceDocument.brand_id == brand_id)
    else:
        filters.append(WorkspaceDocument.brand_id.is_(None))

    doc = (
        await db.execute(
            select(WorkspaceDocument)
            .where(*filters)
            .order_by(WorkspaceDocument.approved_at.desc().nullslast(), WorkspaceDocument.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not doc:
        return brief

    excerpt = (doc.content_markdown or "")[:2500]
    if not excerpt:
        return brief
    return {
        **brief,
        "campaign_brand_kit_excerpt": excerpt,
        "brand_visual_constraints": _extract_visual_constraints(excerpt),
    }


def _extract_visual_constraints(markdown: str) -> str:
    """Small heuristic extractor for image prompt style constraints."""
    keep: list[str] = []
    keywords = (
        "color", "colour", "palette", "visual", "style", "tone", "logo",
        "typography", "font", "imagery", "photography", "brand voice", "avoid",
    )
    for raw in markdown.splitlines():
        line = raw.strip(" -#\t")
        if not line:
            continue
        lowered = line.lower()
        if any(k in lowered for k in keywords):
            keep.append(line)
        if len("; ".join(keep)) > 700:
            break
    return "; ".join(keep)[:900]


async def _inject_generated_image(
    brief: dict,
    brand_id,
    db: AsyncSession,
    settings,
) -> dict:
    """
    If the brief contains image_prompt, call media.image.generate before the
    channel module runs and inject _image_data_b64 / _image_mime into the brief.
    Channel modules read these fields from brief — no cross-plugin imports needed.
    """
    try:
        from registry import get_module as _get_module
        img_cls = _get_module("media.image.generate")
        if not img_cls:
            return brief
        img_brief = await inject_channel_credentials("media.image.generate", brief, brand_id, db, settings)
        _, result = img_cls().execute_tool_result(img_brief)
        block = result.get("block", {})
        if block.get("status") == "succeeded" and block.get("image_data_b64"):
            return {
                **brief,
                "_image_data_b64": block["image_data_b64"],
                "_image_mime": block.get("mime_type", "image/png"),
                "_image_width": block.get("width", 1024),
                "_image_height": block.get("height", 1024),
            }
    except Exception:
        logger.exception("Image pre-generation failed — continuing without image")
    return brief


# ── PM plugin run sync helpers ────────────────────────────────────────────────
# These helpers are PM-system agnostic. The active plugin is read from
# brand.brand_json["pm_config"]["plugin"] (e.g. "channel.clickup").
# A different PM plugin just needs tasks.create / tasks.update capabilities
# following the same module ID pattern: marketing.channel.{plugin}.tasks.*

def _pm_cfg(brand: Brand) -> dict:
    bj = brand.brand_json or {}
    return bj.get("pm_config") or {}


async def _sync_run_to_pm(run: Run, brand: Brand, db: AsyncSession, settings) -> str | None:
    """Create a PM task for this run if brand has sync enabled. Returns task_id or None."""
    cfg = _pm_cfg(brand)
    if not cfg.get("sync_enabled") or not cfg.get("list_id") or not cfg.get("plugin"):
        return None
    plugin = cfg["plugin"]
    create_id = f"marketing.channel.{plugin}.tasks.create"
    try:
        cls = get_module(create_id)
        if not cls:
            return None
        pending_status = cfg.get("status_map", {}).get("pending", "review")
        brief: dict = {
            "list_id": cfg["list_id"],
            "tasks": [{"name": f"[BOS] {run.module_id}", "description": f"Run ID: {run.id}", "status": pending_status}],
        }
        brief = await inject_channel_credentials(create_id, brief, run.brand_id, db, settings)
        _, result = cls().execute_tool_result(brief)
        created = result.get("block", {}).get("created", [])
        return created[0].get("id") if created else None
    except Exception:
        logger.exception("PM run sync (create) failed for run %s plugin=%s", run.id, plugin)
        return None


async def _update_pm_task_status(run: Run, new_bos_status: str, brand: Brand, db: AsyncSession, settings) -> None:
    """Update PM task status when run approval_status changes."""
    if not run.pm_task_id:
        return
    cfg = _pm_cfg(brand)
    if not cfg.get("plugin"):
        return
    plugin = cfg["plugin"]
    new_pm_status = cfg.get("status_map", {}).get(new_bos_status, new_bos_status)
    update_id = f"marketing.channel.{plugin}.tasks.update"
    try:
        cls = get_module(update_id)
        if not cls:
            return
        brief: dict = {"task_id": run.pm_task_id, "new_status": new_pm_status}
        brief = await inject_channel_credentials(update_id, brief, run.brand_id, db, settings)
        cls().execute_tool_result(brief)
    except Exception:
        logger.exception("PM task status update failed for run %s plugin=%s", run.id, plugin)


# ── Core execution (shared by /runs and /chat) ─────────────────────────────────

async def _execute_module(
    db: AsyncSession,
    ws: "Workspace",
    module_id: str,
    brief: dict,
    settings,
    policy: str | None = None,
    campaign_id: UUID | None = None,
    brand_id: UUID | None = None,
) -> RunResponse:
    """Route, execute, persist, and return a RunResponse for any module."""
    module_cls = get_module(module_id)
    if not module_cls:
        raise BosError(404, "MODULE_NOT_FOUND", f"Module '{module_id}' is not registered", None)
    module = module_cls()

    eff_policy = policy or module.policy_default

    brief = await inject_channel_credentials(module_id, brief, brand_id, db, settings)

    if module_id == "media.image.generate" or brief.get("image_prompt"):
        brief = await _inject_campaign_brand_kit_style(brief, ws, brand_id, db)

    if module_id != "media.image.generate" and brief.get("image_prompt"):
        brief = await _inject_generated_image(brief, brand_id, db, settings)

    tool_executor = getattr(module, "execute_tool_result", None)
    if callable(tool_executor):
        run = Run(
            workspace_id=ws.id,
            module_id=module_id,
            status="running",
            campaign_id=campaign_id,
            brand_id=brand_id,
        )
        db.add(run)
        await db.flush()

        attempt_data, result_data = tool_executor(brief)
        try:
            verdict, failures = module.self_check(result_data["content"], brief)
        except Exception as exc:
            logger.exception("self_check raised for run %s", run.id)
            verdict, failures = "fail", [str(exc)]

        db.add(RunAttempt(run_id=run.id, **attempt_data))
        run_result_row = RunResult(
            run_id=run.id,
            content=result_data["content"],
            self_check_verdict=verdict,
            sell_price=result_data.get("sell_price"),
        )
        db.add(run_result_row)

        routing_meta = {
            "capability": module.capability,
            "policy": eff_policy,
            "candidates_considered": 1,
            "candidates_filtered": 0,
            "winner": f"{attempt_data['provider']}/{attempt_data['model_id']}",
            "routing_reason": "deterministic tool connector execution",
        }
        db.add(RunTrace(
            run_id=run.id,
            routing_json=routing_meta,
            lineage_json={
                "connector": attempt_data["provider"],
                "self_check": verdict,
                "self_check_failures": failures,
                "block": result_data.get("block"),
            },
        ))

        run.status = "success" if verdict == "pass" else "partial"
        await write_memory_event(
            db,
            workspace_id=ws.id,
            brand_id=brand_id,
            event_type="artifact_created",
            topic_tags=[],
            summary=f"Artifact created by {module_id}",
            source_ref=f"run:{run.id}",
            full_record={
                "run_id": str(run.id),
                "module_id": module_id,
                "status": run.status,
                "approval_status": run.approval_status,
                "campaign_id": str(campaign_id) if campaign_id else None,
            },
        )
        await db.commit()

        if brand_id:
            _brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
            if _brand:
                task_id = await _sync_run_to_pm(run, _brand, db, settings)
                if task_id:
                    run.pm_task_id = task_id
                    await db.commit()

        await db.refresh(run)

        return RunResponse(
            run_id=str(run.id),
            module_id=run.module_id,
            vertical=module.vertical,
            status=run.status,
            approval_status=run.approval_status,
            campaign_id=str(run.campaign_id) if run.campaign_id else None,
            brand_id=str(run.brand_id) if run.brand_id else None,
            result=RunResultOut(
                content=run_result_row.content,
                self_check=verdict,
                platform=module.platform_hint,
                block=result_data.get("block"),
            ),
            execution=RunExecutionOut(
                provider=attempt_data["provider"],
                model=attempt_data["model_id"],
                mode=attempt_data["mode"],
                attempts=1,
                latency_ms=attempt_data["latency_ms"],
                tokens_used=attempt_data["tokens_output"],
                provider_cost=attempt_data["provider_cost"],
                sell_price=run_result_row.sell_price,
            ),
            trace=RunTraceOut(
                capability=module.capability,
                policy=eff_policy,
                candidates_considered=routing_meta["candidates_considered"],
                candidates_filtered=routing_meta["candidates_filtered"],
                winner=routing_meta["winner"],
                routing_reason=routing_meta["routing_reason"],
            ),
            created_at=run.created_at,
        )

    candidates, routing_meta = await route(db, module.capability, eff_policy)

    model_override = await resolve_backend_override(db, ws.id, module_id) or get_module_model_override(settings, module_id)
    if model_override and candidates:
        candidates = reorder_candidates_for_model_override(
            candidates,
            model_override,
            strict=effective_strict(settings, model_override),
        )
        override_display_id = f"{model_override.provider}/{model_override.model_id or model_override.tool_id or 'unknown'}"
        routing_meta["backend_override"] = {
            "provider": model_override.provider,
            "model_id": model_override.model_id,
            "tool_id": model_override.tool_id,
            "modality": model_override.modality,
            "strict": effective_strict(settings, model_override),
        }
        routing_meta["routing_reason"] = (
            f"operator-configured backend override for {module_id}: "
            f"{override_display_id} ({model_override.modality})"
        )
        routing_meta["winner"] = (
            f"{candidates[0]['provider']}/{candidates[0]['model_id']}" if candidates else None
        )

    if not candidates:
        failed_run = Run(
            workspace_id=ws.id, module_id=module_id, status="failed",
            campaign_id=campaign_id, brand_id=brand_id,
        )
        db.add(failed_run)
        await db.flush()
        db.add(RunTrace(run_id=failed_run.id, routing_json=routing_meta, lineage_json=None))
        await write_memory_event(
            db,
            workspace_id=ws.id,
            brand_id=brand_id,
            event_type="run_failed",
            topic_tags=[],
            summary=f"Run failed for {module_id}: no eligible candidates",
            source_ref=f"run:{failed_run.id}",
            full_record={"run_id": str(failed_run.id), "module_id": module_id, "routing": routing_meta},
        )
        await db.commit()
        raise BosError(503, "NO_ELIGIBLE_CANDIDATES", "No healthy model options for this capability and policy", routing_meta)

    run = Run(
        workspace_id=ws.id, module_id=module_id, status="running",
        campaign_id=campaign_id, brand_id=brand_id,
    )
    db.add(run)
    await db.flush()

    prompt = module.build_prompt(brief)
    attempt_data: dict | None = None
    result_data: dict | None = None
    failed_attempts: list[dict] = []
    last_error: str | None = None

    for candidate in candidates:
        provider = candidate["provider"]
        api_key, auth_mode = await resolve_stored_provider_credential(db, ws.id, provider, settings, brand_id=brand_id)
        if api_key:
            run_mode = "oauth" if auth_mode == "oauth" else "byok"
        else:
            api_key = get_platform_key(provider, settings)
            auth_mode = None
            run_mode = "platform" if api_key else None

        if not api_key:
            continue

        try:
            attempt_data, result_data = await execute_live(
                candidate, prompt, api_key, settings.markup_multiplier, byok=(run_mode != "platform"), auth_mode=auth_mode
            )
            break
        except Exception as exc:
            logger.warning("Candidate %s/%s failed: %s", provider, candidate["model_id"], exc)
            failed_attempts.append({
                "provider": provider, "model": candidate["model_id"],
                "status": "failed", "error": str(exc),
            })
            db.add(RunAttempt(
                run_id=run.id, provider=provider, model_id=candidate["model_id"],
                mode=run_mode, status="failed", error=str(exc),
            ))
            last_error = str(exc)

    if attempt_data is None:
        if last_error:
            db.add(RunTrace(run_id=run.id, routing_json=routing_meta,
                            lineage_json={"failed_attempts": failed_attempts}))
            run.status = "failed"
            await write_memory_event(
                db,
                workspace_id=ws.id,
                brand_id=brand_id,
                event_type="run_failed",
                topic_tags=[],
                summary=f"Run failed for {module_id}: all provider candidates failed",
                source_ref=f"run:{run.id}",
                full_record={
                    "run_id": str(run.id),
                    "module_id": module_id,
                    "failed_attempts": failed_attempts,
                    "last_error": last_error,
                },
            )
            await db.commit()
            raise BosError(500, "EXECUTION_FAILED", "All provider candidates failed", {"error": last_error})
        else:
            attempt_data, result_data = execute_mock(
                candidates[0], brief, module_id, settings.markup_multiplier
            )
            run_mode = "mock"

    try:
        verdict, failures = module.self_check(result_data["content"], brief)
    except Exception as exc:
        logger.exception("self_check raised for run %s", run.id)
        verdict, failures = "fail", [str(exc)]

    db.add(RunAttempt(run_id=run.id, **attempt_data))

    run_result_row = RunResult(
        run_id=run.id,
        content=result_data["content"],
        self_check_verdict=verdict,
        sell_price=result_data["sell_price"],
    )
    db.add(run_result_row)

    # Build and persist structured artifact block for modules that expose native fields.
    block = None
    if hasattr(module, '_build_block') and result_data.get("content"):
        try:
            block = module._build_block(result_data["content"])
        except Exception:
            pass

    db.add(RunTrace(
        run_id=run.id,
        routing_json=routing_meta,
        lineage_json={
            "attempts": failed_attempts + [{"provider": attempt_data["provider"], "model": attempt_data["model_id"], "status": "succeeded"}],
            "self_check": verdict,
            "self_check_failures": failures,
            "block": block,
        },
    ))

    run.status = "success" if verdict == "pass" else "partial"

    await write_memory_event(
        db,
        workspace_id=ws.id,
        brand_id=brand_id,
        event_type="artifact_created",
        topic_tags=[],
        summary=f"Artifact created by {module_id}",
        source_ref=f"run:{run.id}",
        full_record={
            "run_id": str(run.id),
            "module_id": module_id,
            "status": run.status,
            "approval_status": run.approval_status,
            "campaign_id": str(campaign_id) if campaign_id else None,
            "self_check": verdict,
        },
    )

    await db.commit()

    if brand_id:
        _brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
        if _brand:
            task_id = await _sync_run_to_pm(run, _brand, db, settings)
            if task_id:
                run.pm_task_id = task_id
                await db.commit()

    await db.refresh(run)

    return RunResponse(
        run_id=str(run.id),
        module_id=run.module_id,
        vertical=module.vertical,
        status=run.status,
        approval_status=run.approval_status,
        campaign_id=str(run.campaign_id) if run.campaign_id else None,
        brand_id=str(run.brand_id) if run.brand_id else None,
        result=RunResultOut(
            content=run_result_row.content,
            self_check=verdict,
            platform=module.platform_hint,
            block=block,
        ),
        execution=RunExecutionOut(
            provider=attempt_data["provider"],
            model=attempt_data["model_id"],
            mode=attempt_data["mode"],
            attempts=1,
            latency_ms=attempt_data["latency_ms"],
            tokens_used=attempt_data["tokens_output"],
            provider_cost=attempt_data["provider_cost"],
            sell_price=run_result_row.sell_price,
        ),
        trace=RunTraceOut(
            capability=module.capability,
            policy=eff_policy,
            candidates_considered=routing_meta["candidates_considered"],
            candidates_filtered=routing_meta["candidates_filtered"],
            winner=routing_meta["winner"],
            routing_reason=routing_meta["routing_reason"],
        ),
        created_at=run.created_at,
    )


# ── POST /runs ─────────────────────────────────────────────────────────────────

@router.post("/runs", response_model=RunResponse, status_code=201, summary="Trigger a module run")
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

    brief = await _resolve_brief(db, ws, body.payload.brief.model_dump(exclude_none=True))
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
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    filters = []
    if module_id:
        filters.append(Run.module_id == module_id)
    if status:
        filters.append(Run.status == status)
    if approval_status:
        filters.append(Run.approval_status == approval_status)
    if created_after:
        filters.append(Run.created_at >= created_after)
    if created_before:
        filters.append(Run.created_at <= created_before)

    count_stmt = select(func.count()).select_from(Run)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = select(Run, RunAttempt, Campaign).join(
        RunAttempt, RunAttempt.run_id == Run.id, isouter=True
    ).join(
        Campaign, Campaign.id == Run.campaign_id, isouter=True
    ).order_by(Run.created_at.desc()).limit(limit).offset(offset)
    if filters:
        stmt = stmt.where(*filters)
    result = await db.execute(stmt)
    rows_with_attempts = result.all()

    verticals_cache: dict[str, str] = {}

    def _vertical(mid: str) -> str:
        if mid not in verticals_cache:
            cls = get_module(mid)
            verticals_cache[mid] = cls.vertical if cls else mid.split(".")[0]
        return verticals_cache[mid]

    return RunListResponse(
        runs=[
            RunListItem(
                run_id=str(r.Run.id),
                module_id=r.Run.module_id,
                vertical=_vertical(r.Run.module_id),
                status=r.Run.status,
                approval_status=r.Run.approval_status,
                campaign_id=str(r.Run.campaign_id) if r.Run.campaign_id else None,
                campaign_name=r.Campaign.name if r.Campaign else None,
                brand_id=str(r.Run.brand_id) if r.Run.brand_id else None,
                created_at=r.Run.created_at,
                provider=r.RunAttempt.provider if r.RunAttempt else None,
                model=r.RunAttempt.model_id if r.RunAttempt else None,
                latency_ms=r.RunAttempt.latency_ms if r.RunAttempt else None,
                tokens=r.RunAttempt.tokens_output if r.RunAttempt else None,
                cost=r.RunAttempt.provider_cost if r.RunAttempt else None,
            )
            for r in rows_with_attempts
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── GET /runs/{run_id} ─────────────────────────────────────────────────────────

@router.get("/runs/{run_id}", response_model=RunResponse, summary="Get run detail with full trace")
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    run_row = await db.execute(select(Run).where(Run.id == run_id))
    run = run_row.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' not found", "details": None}},
        )

    attempt_row = await db.execute(
        select(RunAttempt).where(RunAttempt.run_id == run.id).limit(1)
    )
    attempt = attempt_row.scalar_one_or_none()

    result_row = await db.execute(select(RunResult).where(RunResult.run_id == run.id))
    result = result_row.scalar_one_or_none()

    trace_row = await db.execute(select(RunTrace).where(RunTrace.run_id == run.id))
    trace = trace_row.scalar_one_or_none()

    cls = get_module(run.module_id)
    vertical = cls.vertical if cls else run.module_id.split(".")[0]
    platform = cls.platform_hint if cls else None

    routing = trace.routing_json if trace else {}
    lineage = trace.lineage_json if trace else {}

    return RunResponse(
        run_id=str(run.id),
        module_id=run.module_id,
        vertical=vertical,
        status=run.status,
        approval_status=run.approval_status,
        campaign_id=str(run.campaign_id) if run.campaign_id else None,
        brand_id=str(run.brand_id) if run.brand_id else None,
        result=RunResultOut(
            content=result.content,
            self_check=result.self_check_verdict,
            platform=platform,
            block=(lineage or {}).get("block"),
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


@router.patch("/runs/{run_id}/approve", status_code=200, summary="Approve a run")
async def approve_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Mark a run as approved."""
    from uuid import UUID
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    
    result = await db.execute(select(Run).where(Run.id == run_uuid))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run.approval_status = "approved"
    run.feedback = None
    await write_memory_event(
        db,
        workspace_id=run.workspace_id,
        brand_id=run.brand_id,
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
            await _update_pm_task_status(run, "approved", _brand, db, get_settings())

    return {"run_id": run_id, "approval_status": "approved"}


@router.patch("/runs/{run_id}/reject", status_code=200, summary="Reject a run with feedback")
async def reject_run(
    run_id: str,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Mark a run as rejected with feedback for revision."""
    from uuid import UUID
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    
    result = await db.execute(select(Run).where(Run.id == run_uuid))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run.approval_status = "rejected"
    run.feedback = body.feedback
    await write_memory_event(
        db,
        workspace_id=run.workspace_id,
        brand_id=run.brand_id,
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
            await _update_pm_task_status(run, "rejected", _brand, db, get_settings())

    return {"run_id": run_id, "approval_status": "rejected", "feedback": body.feedback}


@router.post("/runs/{run_id}/revise", status_code=201, summary="Revise a rejected run")
async def revise_run(
    run_id: str,
    body: ApprovalRequest = ApprovalRequest(),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Create a new run based on a rejected run (with feedback incorporated)."""
    from uuid import UUID
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    
    # Get the original run
    result = await db.execute(
        select(Run, RunResult, RunTrace)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
        .where(Run.id == run_uuid)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run, run_result, run_trace = row
    
    if body.feedback:
        run.approval_status = "rejected"
        run.feedback = body.feedback
        await db.flush()

    if run.approval_status != "rejected":
        raise HTTPException(status_code=400, detail="Can only revise rejected runs")
    
    # Get workspace
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
    
    # Link the new run to the original as a revision
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

# ── Export Endpoints ───────────────────────────────────────────────────────

class ExportResponse(BaseModel):
    run_id: str
    module_id: str
    platform: Optional[str]
    content: str
    formatted: dict  # Platform-specific formatted content
    self_check: str


@router.get("/runs/{run_id}/export", response_model=ExportResponse, summary="Export run content in copy-paste ready format")
async def export_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Export run content formatted for easy copy-pasting to the platform."""
    from uuid import UUID
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    
    # Get the run and related data
    result = await db.execute(
        select(Run, RunResult, RunAttempt)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunAttempt, RunAttempt.run_id == Run.id, isouter=True)
        .where(Run.id == run_uuid)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run, run_result, run_attempt = row
    
    if not run_result:
        raise HTTPException(status_code=404, detail="Run result not found")
    
    # Get module info
    cls = get_module(run.module_id)
    platform = cls.platform_hint if cls else "unknown"
    
    # Format content based on platform
    formatted = _format_for_platform(platform, run_result.content)
    
    return ExportResponse(
        run_id=run_id,
        module_id=run.module_id,
        platform=platform,
        content=run_result.content,
        formatted=formatted,
        self_check=run_result.self_check_verdict,
    )


def _format_for_platform(platform: str, content: str) -> dict:
    """Format content for easy copy-pasting based on platform."""
    
    if platform == "facebook":
        return {
            "type": "text",
            "content": content,
            "copy_paste": content,
            "instructions": "Copy and paste directly into Facebook Ads Manager"
        }
    
    elif platform == "twitter":
        return {
            "type": "text",
            "content": content,
            "copy_paste": content,
            "character_count": len(content),
            "max_chars": 280,
            "instructions": "Copy and paste directly into Twitter Ads"
        }
    
    elif platform == "google":
        # Parse headlines and descriptions
        import re
        headlines = re.findall(r"^Headline\s+\d+:\s*(.+)$", content, re.MULTILINE)
        descriptions = re.findall(r"^Description\s+\d+:\s*(.+)$", content, re.MULTILINE)
        
        return {
            "type": "google_rsa",
            "headlines": headlines,
            "descriptions": descriptions,
            "copy_paste": content,
            "instructions": "Copy each headline and description into the corresponding fields in Google Ads"
        }
    
    elif platform == "email":
        # Parse email components
        lines = content.split("\n")
        subject = ""
        body = content
        
        for line in lines:
            if line.lower().startswith("subject:"):
                subject = line[8:].strip()
                body = content[content.find("\n", content.find("Subject:"))+1:].strip()
                break
        
        return {
            "type": "email",
            "subject": subject,
            "body": body,
            "full_email": content,
            "instructions": "Copy subject and body into your email client"
        }
    
    else:
        return {
            "type": "text",
            "content": content,
            "copy_paste": content,
            "instructions": "Copy and paste the content"
        }
