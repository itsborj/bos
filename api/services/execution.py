"""Execution strategies — Strategy pattern for the three module execution paths.

Extracted from routers/runs.py _execute_module to eliminate the 400-line god function
with three divergent code paths.

Paths:
  1. SDKExecutionStrategy  — async execute() returning klaroha_sdk.RunResult
  2. ToolExecutionStrategy — synchronous execute_tool_result() returning (attempt, result)
  3. AIRoutingStrategy     — AI provider routing via capability_router + execute_live
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from executor import execute_live, execute_mock, get_platform_key
from memory_events import write_memory_event
from model_overrides import BackendRef, effective_strict, get_module_model_override
from models.run import Run, RunAttempt, RunResult, RunTrace
from models.workspace import Brand, Workspace
from provider_auth import resolve_stored_provider_credential
from routers.backend_settings import resolve_backend_override
from schemas.runs import RunExecutionOut, RunResponse, RunResultOut, RunTraceOut
from services.approval_state import derive_approval_status, derive_run_status
from services.brand_context import brand_fields_from_row, scope_artifact_block
from campaign import db as campaign_db
from services.self_check import self_check_repair_guidance
from services.workflow_persistence import persist_workflow_record

logger = logging.getLogger("bos.services.execution")


# ── Shared result type ────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    """Unified result from any execution strategy."""
    run: Run
    run_result_row: RunResult
    attempt_data: dict
    routing_meta: dict
    block: dict | None
    verdict: str
    failures: list[str]
    platform: str
    module_id: str
    capability: str
    policy: str
    sdk_block: dict | None = None  # only set by SDK strategy


# ── Shared helpers ────────────────────────────────────────────────────────────

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


def _recorded_sell_price(attempt_data: dict, result_data: dict | None, markup_multiplier: float) -> float | None:
    explicit = result_data.get("sell_price") if isinstance(result_data, dict) else None
    if explicit is not None:
        return explicit
    if (
        str(attempt_data.get("status") or "").lower() in {"succeeded", "success"}
        and attempt_data.get("mode") == "platform"
        and (attempt_data.get("provider_cost") or 0) > 0
    ):
        return round(float(attempt_data["provider_cost"]) * markup_multiplier, 6)
    return None


def _apply_backend_ref_to_brief(brief: dict, ref: BackendRef | None) -> dict:
    """Apply an operator/plugin backend selection to a tool brief."""
    out = dict(brief or {})
    if not ref:
        return out
    if ref.model_id:
        out["model"] = ref.model_id
        out["backend_model_id"] = ref.model_id
    if ref.provider:
        out["backend_provider"] = ref.provider
    override = {
        "provider": ref.provider,
        "model_id": ref.model_id,
        "tool_id": ref.tool_id,
        "modality": ref.modality,
        "strict": ref.strict,
    }
    out["_backend_override"] = {k: v for k, v in override.items() if v is not None}
    return out


async def _create_run(
    db: AsyncSession,
    ws: Workspace,
    module_id: str,
    campaign_id: UUID | None,
    brand_id: UUID | None,
    is_supporting: bool,
) -> Run:
    run = Run(
        workspace_id=ws.id,
        module_id=module_id,
        status="running",
        campaign_id=campaign_id,
        brand_id=brand_id,
        approval_status="supporting" if is_supporting else "pending",
    )
    db.add(run)
    await db.flush()
    return run


async def _finalize_run(
    db: AsyncSession,
    ws: Workspace,
    result: ExecutionResult,
    brief: dict,
    settings,
    is_supporting: bool,
    hook_ctx,
    _get_hook_registry_fn=None,
    _sync_run_to_pm_fn=None,
) -> RunResponse:
    """Shared post-execution: persist traces, derive status, write events, fire hooks, build response."""
    from hooks import RUN_AFTER_COMPLETE

    run = result.run
    block = result.block

    # Persist WorkflowRun + WorkflowComponents for strategy_workflow artifacts
    if block and block.get("type") == "strategy_workflow":
        block = await persist_workflow_record(db, ws, run, run.brand_id, brief, block)
        result.block = block

    db.add(RunTrace(
        run_id=run.id,
        routing_json=result.routing_meta,
        lineage_json={
            "connector": result.attempt_data.get("provider", ""),
            "self_check": result.verdict,
            "self_check_failures": result.failures,
            "block": block,
        },
    ))

    run.status = derive_run_status(
        verdict=result.verdict,
        attempt_failed=str(result.attempt_data.get("status") or "").lower() == "failed",
        block_failed=isinstance(block, dict) and str(block.get("status") or "").lower() == "failed",
    )

    allowed_actions = (block or {}).get("allowed_actions") or []
    run.approval_status = derive_approval_status(
        run_status=run.status,
        attempt_failed=str(result.attempt_data.get("status") or "").lower() == "failed",
        block_failed=isinstance(block, dict) and str(block.get("status") or "").lower() == "failed",
        is_supporting=is_supporting,
        block=block,
        allowed_actions=allowed_actions,
    )

    await write_memory_event(
        db,
        workspace_id=ws.id,
        brand_id=run.brand_id,
        event_type="artifact_created",
        topic_tags=[],
        summary=f"Artifact created by {run.module_id}",
        source_ref=f"run:{run.id}",
        full_record={
            "run_id": str(run.id),
            "module_id": run.module_id,
            "status": run.status,
            "approval_status": run.approval_status,
            "campaign_id": str(run.campaign_id) if run.campaign_id else None,
            "self_check": result.verdict,
        },
    )

    # Report/intelligence artifacts may emit a normalized campaign_signal. When
    # campaign_id is present, append the signal as a Campaign row. Unbound source
    # evidence remains artifact/run evidence, not Campaign truth.
    if isinstance(block, dict) and isinstance(block.get("campaign_signal"), dict):
        signal = block.get("campaign_signal") or {}
        summary = str(signal.get("summary") or block.get("recommended_next_step") or "").strip()
        if summary:
            full_record = {
                "run_id": str(run.id),
                "module_id": run.module_id,
                "report_scope": block.get("report_scope"),
                "coverage_label": block.get("coverage_label"),
                "campaign_binding": block.get("campaign_binding"),
                "metrics_overview": block.get("metrics_overview"),
                "insight_bullets": block.get("insight_bullets"),
                "objective_feedback": block.get("objective_feedback"),
                "not_available": block.get("not_available"),
                "recommended_next_step": block.get("recommended_next_step"),
            }
            if run.campaign_id:
                metrics = block.get("metrics_overview") if isinstance(block.get("metrics_overview"), dict) else {}
                feedback_rows = block.get("objective_feedback") if isinstance(block.get("objective_feedback"), list) else []
                feedback = feedback_rows[0] if feedback_rows and isinstance(feedback_rows[0], dict) else {}
                assessment = feedback.get("assessment") if isinstance(feedback.get("assessment"), dict) else {}
                def _metric_int(value):
                    if isinstance(value, bool) or value in (None, "", [], {}):
                        return None
                    if isinstance(value, (int, float)):
                        return int(value)
                    try:
                        return int(float(value))
                    except (TypeError, ValueError):
                        return None

                await campaign_db.append_campaign_row(db, run.campaign_id, {
                    "workspace_id": ws.id,
                    "brand_id": run.brand_id,
                    "campaign_id": run.campaign_id,
                    "period_type": "report",
                    "time_period": str(block.get("window") or block.get("period") or "latest"),
                    "distribution_channel": str(signal.get("channel") or result.platform or "channel"),
                    "source_type": "tool_execution",
                    "source_ref": f"run:{run.id}",
                    "producer": run.module_id,
                    "reach": _metric_int(metrics.get("reach") or metrics.get("followers")),
                    "impressions": _metric_int(metrics.get("impressions")),
                    "engagement": _metric_int(metrics.get("engagements") or metrics.get("recent_posts_with_engagement_counts")),
                    "clicks": _metric_int(metrics.get("clicks")),
                    "conversions": _metric_int(metrics.get("conversions")),
                    "source_health": str(block.get("coverage_label") or "reported"),
                    "verification_status": "producer_reported",
                    "objective_verdict": str(assessment.get("objective_evaluation") or "inconclusive"),
                    "confidence": str(signal.get("confidence") or "medium"),
                    "what_changed": summary,
                    "next_action": str(block.get("recommended_next_step") or "") or None,
                    "raw_payload": full_record,
                    "evidence_refs": [f"run:{run.id}"],
                })

    await db.commit()

    # PM sync
    if run.brand_id and _sync_run_to_pm_fn:
        _brand = (await db.execute(select(Brand).where(Brand.id == run.brand_id))).scalar_one_or_none()
        if _brand:
            task_id = await _sync_run_to_pm_fn(run, _brand, db, settings)
            if task_id:
                run.pm_task_id = task_id
                await db.commit()

    await db.refresh(run)

    # Fire after_complete hook
    if _get_hook_registry_fn:
        hook_ctx.run_id = run.id
        hook_ctx.result = {
            "block": block,
            "status": run.status,
            "approval_status": run.approval_status,
        }
        await _get_hook_registry_fn().fire_action(RUN_AFTER_COMPLETE, hook_ctx)

    brand_name = brief.get("brand_name")
    brand_handle = brief.get("brand_handle")

    return RunResponse(
        run_id=str(run.id),
        module_id=run.module_id,
        vertical=result.routing_meta.get("vertical", "marketing"),
        status=run.status,
        approval_status=run.approval_status,
        campaign_id=str(run.campaign_id) if run.campaign_id else None,
        brand_id=str(run.brand_id) if run.brand_id else None,
        brand_name=brand_name,
        result=_scope_result_out(
            content=result.run_result_row.content,
            self_check=result.verdict,
            platform=result.platform,
            block=block,
            brand_id=run.brand_id,
            brand_name=brand_name,
            brand_handle=brand_handle,
        ),
        execution=RunExecutionOut(
            provider=result.attempt_data.get("provider", ""),
            model=result.attempt_data.get("model_id", ""),
            mode=result.attempt_data.get("mode", "tool"),
            attempts=1,
            latency_ms=result.attempt_data.get("latency_ms", 0),
            tokens_used=result.attempt_data.get("tokens_output", 0),
            provider_cost=result.attempt_data.get("provider_cost", 0.0),
            sell_price=result.run_result_row.sell_price,
        ),
        trace=RunTraceOut(
            capability=result.capability,
            policy=result.policy,
            candidates_considered=result.routing_meta.get("candidates_considered", 1),
            candidates_filtered=result.routing_meta.get("candidates_filtered", 0),
            winner=result.routing_meta.get("winner"),
            routing_reason=result.routing_meta.get("routing_reason", ""),
        ),
        created_at=run.created_at,
    )


# ── Strategy 1: SDK async execute() ───────────────────────────────────────────

async def execute_sdk(
    db: AsyncSession,
    ws: Workspace,
    module,
    module_id: str,
    brief: dict,
    settings,
    policy: str,
    campaign_id: UUID | None,
    brand_id: UUID | None,
    is_supporting: bool,
    hook_ctx,
    _get_hook_registry_fn=None,
    _sync_run_to_pm_fn=None,
) -> RunResponse:
    """Execute a module via its async execute() method (klaroha_sdk.RunResult)."""
    _sdk_execute = getattr(module, "execute", None)

    run = await _create_run(db, ws, module_id, campaign_id, brand_id, is_supporting)

    try:
        sdk_result = await _sdk_execute(brief)
    except Exception as exc:
        logger.exception("SDK execute() raised for run %s", run.id)
        run.status = "failed"
        run.approval_status = "failed"
        await db.commit()
        from errors import BosError
        raise BosError(500, "MODULE_EXECUTE_FAILED", str(exc), None) from exc

    _plugin_prefix = (module_id or "sdk").split(".")[0]
    _platform = getattr(module, "platform_hint", "") or _plugin_prefix
    _capability = getattr(module, "capability", "marketing.execute") or "marketing.execute"

    attempt_data = {
        "provider": _platform,
        "model_id": module_id,
        "mode": "tool",
        "status": "succeeded" if sdk_result.status != "failed" else "failed",
        "tokens_input": 0,
        "tokens_output": 0,
        "provider_cost": 0.0,
        "latency_ms": sdk_result.metadata.get("latency_ms", 0),
        "error": sdk_result.error,
    }

    _sdk_block: dict | None = None
    if sdk_result.artifact_blocks:
        _ab = sdk_result.artifact_blocks[0]
        _sdk_block = {
            "type": _ab.block_type,
            "artifact_type": "action_result",
            "platform": _platform,
            "status": "succeeded" if sdk_result.status == "success" else sdk_result.status,
            "allowed_actions": _ab.allowed_actions,
            "renderer_hint": _ab.renderer_hint,
            **_ab.content,
        }
        _sdk_block = scope_artifact_block(
            _sdk_block,
            brand_id=brand_id,
            brand_name=brief.get("brand_name"),
            brand_handle=brief.get("brand_handle"),
        )

    _content = sdk_result.metadata.get("content") or (
        json.dumps(_sdk_block) if _sdk_block else ""
    )
    verdict = sdk_result.self_check or "pass"
    failures: list[str] = []

    db.add(RunAttempt(run_id=run.id, **attempt_data))
    run_result_row = RunResult(
        run_id=run.id,
        content=_content,
        self_check_verdict=verdict,
        sell_price=_recorded_sell_price(attempt_data, {"sell_price": sdk_result.metadata.get("sell_price")}, settings.markup_multiplier),
    )
    db.add(run_result_row)

    routing_meta = {
        "vertical": getattr(module, "vertical", "marketing"),
        "capability": _capability,
        "policy": policy,
        "candidates_considered": 1,
        "candidates_filtered": 0,
        "winner": f"{_platform}/{module_id}",
        "routing_reason": "sdk execute() — external plugin",
    }

    result = ExecutionResult(
        run=run,
        run_result_row=run_result_row,
        attempt_data=attempt_data,
        routing_meta=routing_meta,
        block=_sdk_block,
        verdict=verdict,
        failures=failures,
        platform=_platform,
        module_id=module_id,
        capability=_capability,
        policy=policy,
        sdk_block=_sdk_block,
    )

    return await _finalize_run(
        db, ws, result, brief, settings, is_supporting, hook_ctx,
        _get_hook_registry_fn=_get_hook_registry_fn,
        _sync_run_to_pm_fn=_sync_run_to_pm_fn,
    )


# ── Strategy 2: Legacy tool execute_tool_result() ─────────────────────────────

async def execute_tool(
    db: AsyncSession,
    ws: Workspace,
    module,
    module_id: str,
    brief: dict,
    settings,
    policy: str,
    campaign_id: UUID | None,
    brand_id: UUID | None,
    is_supporting: bool,
    hook_ctx,
    _get_hook_registry_fn=None,
    _sync_run_to_pm_fn=None,
) -> RunResponse:
    """Execute a module via its synchronous execute_tool_result() method."""
    tool_executor = getattr(module, "execute_tool_result", None)

    # Resolve backend override for tool modules
    tool_backend_override = (
        await resolve_backend_override(db, ws.id, module_id)
        or (await resolve_backend_override(db, ws.id, "storyboard.motion.render") if module_id == "storyboard.motion.edit" else None)
        or get_module_model_override(settings, module_id)
        or (get_module_model_override(settings, "storyboard.motion.render") if module_id == "storyboard.motion.edit" else None)
        or _get_plugin_default_backend(module_id)
    )
    if tool_backend_override:
        brief = _apply_backend_ref_to_brief(brief, tool_backend_override)

    run = await _create_run(db, ws, module_id, campaign_id, brand_id, is_supporting)

    attempt_data, result_data = tool_executor(brief)
    # Guard: tool modules that fail early may omit required fields
    attempt_data.setdefault("provider", module_id.split(".")[0])
    attempt_data.setdefault("model_id", module_id)
    attempt_data.setdefault("mode", "tool")
    attempt_data.setdefault("status", "succeeded")
    attempt_data.setdefault("latency_ms", 0)

    try:
        verdict, failures = module.self_check(result_data["content"], brief)
    except Exception as exc:
        logger.exception("self_check raised for run %s", run.id)
        verdict, failures = "fail", [str(exc)]

    if isinstance(result_data.get("block"), dict):
        result_data["block"] = scope_artifact_block(
            result_data.get("block"),
            brand_id=brand_id,
            brand_name=brief.get("brand_name"),
            brand_handle=brief.get("brand_handle"),
        )

    db.add(RunAttempt(run_id=run.id, **attempt_data))
    run_result_row = RunResult(
        run_id=run.id,
        content=result_data["content"],
        self_check_verdict=verdict,
        sell_price=_recorded_sell_price(attempt_data, result_data, settings.markup_multiplier),
    )
    db.add(run_result_row)

    routing_meta = {
        "vertical": getattr(module, "vertical", "marketing"),
        "capability": getattr(module, "capability", ""),
        "policy": policy,
        "candidates_considered": 1,
        "candidates_filtered": 0,
        "winner": f"{attempt_data['provider']}/{attempt_data['model_id']}",
        "routing_reason": "deterministic tool connector execution",
    }

    result = ExecutionResult(
        run=run,
        run_result_row=run_result_row,
        attempt_data=attempt_data,
        routing_meta=routing_meta,
        block=result_data.get("block"),
        verdict=verdict,
        failures=failures,
        platform=getattr(module, "platform_hint", ""),
        module_id=module_id,
        capability=getattr(module, "capability", ""),
        policy=policy,
    )

    return await _finalize_run(
        db, ws, result, brief, settings, is_supporting, hook_ctx,
        _get_hook_registry_fn=_get_hook_registry_fn,
        _sync_run_to_pm_fn=_sync_run_to_pm_fn,
    )


def _get_plugin_default_backend(module_id: str):
    """Lazy import to avoid circular dependency."""
    try:
        from plugin_loader import get_plugin_default_backend
        return get_plugin_default_backend(module_id)
    except Exception:
        return None


# ── Strategy 3: AI provider routing ───────────────────────────────────────────

async def execute_ai_routing(
    db: AsyncSession,
    ws: Workspace,
    module,
    module_id: str,
    brief: dict,
    settings,
    policy: str,
    campaign_id: UUID | None,
    brand_id: UUID | None,
    is_supporting: bool,
    hook_ctx,
    _get_hook_registry_fn=None,
    _sync_run_to_pm_fn=None,
) -> RunResponse:
    """Execute a module via AI provider routing (capability_router + execute_live)."""
    from capability_router import route

    candidates, routing_meta = await route(db, module.capability, policy)
    original_candidates = list(candidates)

    # Apply model overrides
    model_override = (
        await resolve_backend_override(db, ws.id, module_id)
        or get_module_model_override(settings, module_id)
    )
    override_is_strict = effective_strict(settings, model_override) if model_override else False
    if model_override:
        def _override_candidate(ref) -> dict:
            c: dict = {"provider": ref.provider, "model_id": ref.model_id}
            if ref.routing_hints:
                c["extra_body"] = {"_routing_hints": dict(ref.routing_hints)}
            return c

        all_or = (
            model_override.provider == "openrouter"
            and bool(model_override.fallbacks)
            and all(f.provider == "openrouter" for f in model_override.fallbacks)
        )
        if all_or:
            model_ids = [model_override.model_id] + [f.model_id for f in model_override.fallbacks if f.model_id]
            extra: dict = {"models": model_ids}
            if model_override.routing_hints:
                extra["_routing_hints"] = dict(model_override.routing_hints)
            candidates = [{"provider": "openrouter", "model_id": model_ids[0], "extra_body": extra}]
        else:
            explicit_queue = [_override_candidate(model_override)] + [_override_candidate(f) for f in model_override.fallbacks]
            candidates = explicit_queue if override_is_strict else explicit_queue + original_candidates

        override_display_id = f"{model_override.provider}/{model_override.model_id or model_override.tool_id or 'unknown'}"
        routing_meta["backend_override"] = {
            "provider": model_override.provider,
            "model_id": model_override.model_id,
            "tool_id": model_override.tool_id,
            "modality": model_override.modality,
            "strict": override_is_strict,
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
        from errors import BosError
        raise BosError(503, "NO_ELIGIBLE_CANDIDATES", "No healthy model options for this capability and policy", routing_meta)

    run = await _create_run(db, ws, module_id, campaign_id, brand_id, is_supporting)

    prompt = module.build_prompt(brief)
    attempt_data: dict | None = None
    result_data: dict | None = None
    failed_attempts: list[dict] = []
    last_error: str | None = None
    run_mode: str = "mock"
    api_key: str | None = None
    candidate: dict | None = None

    # Try each candidate in order — first success wins
    for candidate in candidates:
        provider = candidate["provider"]
        api_key, auth_mode = await resolve_stored_provider_credential(
            db,
            ws.id,
            provider,
            settings,
            brand_id=brand_id,
            tolerate_decryption_failure=True,
        )
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
                candidate, prompt, api_key, settings.markup_multiplier,
                byok=(run_mode != "platform"), auth_mode=auth_mode,
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
            from errors import BosError
            raise BosError(500, "EXECUTION_FAILED", "All provider candidates failed", {"error": last_error})
        else:
            attempt_data, result_data = execute_mock(
                candidates[0], brief, module_id, settings.markup_multiplier
            )
            run_mode = "mock"

    # Normalize content
    normalizer = getattr(module, "normalize_content", None)
    if callable(normalizer) and result_data and result_data.get("content"):
        result_data["content"] = normalizer(result_data["content"], brief)

    # Self-check
    try:
        verdict, failures = module.self_check(result_data["content"], brief)
    except Exception as exc:
        logger.exception("self_check raised for run %s", run.id)
        verdict, failures = "fail", [str(exc)]

    # Repair loop (max 2 rounds)
    repair_round = 0
    while verdict == "fail" and attempt_data is not None and result_data is not None and api_key and repair_round < 2:
        repair_round += 1
        repair_prompt = "\n\n".join([
            prompt,
            "SELF-CHECK FAILED. Revise the artifact and return the full corrected artifact only.",
            "Failures: " + ", ".join(failures[:12]),
            "Required fixes:\n" + (self_check_repair_guidance(failures) or "Correct every listed failure explicitly."),
            "Do not include placeholder instruction text. Do not violate any listed self-check failure.",
        ])
        try:
            retry_attempt, retry_result = await execute_live(
                candidate,
                repair_prompt,
                api_key,
                settings.markup_multiplier,
                byok=(run_mode != "platform"),
                auth_mode=auth_mode,
            )
            if callable(normalizer) and retry_result.get("content"):
                retry_result["content"] = normalizer(retry_result["content"], brief)
            retry_verdict, retry_failures = module.self_check(retry_result["content"], brief)
            if retry_verdict == "pass" or len(retry_failures) <= len(failures):
                failed_attempts.append({
                    "provider": attempt_data["provider"],
                    "model": attempt_data["model_id"],
                    "status": "self_check_failed",
                    "failures": failures,
                })
                attempt_data, result_data = retry_attempt, retry_result
                verdict, failures = retry_verdict, retry_failures
            else:
                break
        except Exception as exc:
            logger.warning("Self-check repair attempt failed for %s: %s", module_id, exc)
            break

    db.add(RunAttempt(run_id=run.id, **attempt_data))

    run_result_row = RunResult(
        run_id=run.id,
        content=result_data["content"],
        self_check_verdict=verdict,
        sell_price=_recorded_sell_price(attempt_data, result_data, settings.markup_multiplier),
    )
    db.add(run_result_row)

    # Build structured artifact block
    block = None
    if hasattr(module, '_build_block') and result_data.get("content"):
        try:
            build_block = module._build_block
            if len(inspect.signature(build_block).parameters) >= 2:
                block = build_block(result_data["content"], brief)
            else:
                block = build_block(result_data["content"])
        except Exception:
            pass
    block = scope_artifact_block(
        block,
        brand_id=brand_id,
        brand_name=brief.get("brand_name"),
        brand_handle=brief.get("brand_handle"),
    )

    routing_meta["vertical"] = getattr(module, "vertical", "marketing")

    result = ExecutionResult(
        run=run,
        run_result_row=run_result_row,
        attempt_data=attempt_data,
        routing_meta=routing_meta,
        block=block,
        verdict=verdict,
        failures=failures,
        platform=getattr(module, "platform_hint", ""),
        module_id=module_id,
        capability=getattr(module, "capability", ""),
        policy=policy,
    )

    return await _finalize_run(
        db, ws, result, brief, settings, is_supporting, hook_ctx,
        _get_hook_registry_fn=_get_hook_registry_fn,
        _sync_run_to_pm_fn=_sync_run_to_pm_fn,
    )
