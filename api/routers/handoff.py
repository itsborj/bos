import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from memory_events import resolve_active_objective_id, write_memory_event
from models.decision_brief import DecisionBrief
from models.memory import MemoryEvent
from models.objective import Objective
from models.outcome import OutcomeRecord
from models.pending_decision import PendingDecision
from models.workspace import Brand
from routers.workspace import get_singleton
from validation import NullableUUID, parse_optional_uuid
from schemas.handoff import (
    HandoffBriefOut,
    PendingDecisionCreate,
    PendingDecisionListResponse,
    PendingDecisionOut,
    PendingDecisionResolve,
)

router = APIRouter(tags=["handoff"])


@router.get("/pending-decisions", response_model=PendingDecisionListResponse, summary="List pending decisions", responses={404: {"description": "Brand not found"}})
async def list_pending_decisions(
    brand_id: NullableUUID = None,
    status: Optional[str] = Query(default="open"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return PendingDecisionListResponse(pending_decisions=[], total=0)
    filters = [PendingDecision.workspace_id == ws.id]
    if brand_id is not None:
        await _require_brand(db, ws.id, brand_id)
        filters.append(PendingDecision.brand_id == brand_id)
    if status is not None:
        filters.append(PendingDecision.status == status)
    total = (await db.execute(select(func.count()).select_from(PendingDecision).where(*filters))).scalar_one()
    rows = (
        await db.execute(select(PendingDecision).where(*filters).order_by(PendingDecision.created_at.desc()).limit(100))
    ).scalars().all()
    return PendingDecisionListResponse(pending_decisions=[PendingDecisionOut.model_validate(r) for r in rows], total=total)


@router.post("/pending-decisions", response_model=PendingDecisionOut, status_code=201, summary="Create a pending decision")
async def create_pending_decision(
    body: PendingDecisionCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    await _validate_brand_scope(db, ws.id, body.brand_id)
    objective_id = body.objective_id or await resolve_active_objective_id(db, ws.id, body.brand_id)
    if objective_id is not None:
        await _require_objective(db, ws.id, objective_id, body.brand_id)

    pending = PendingDecision(
        workspace_id=ws.id,
        brand_id=body.brand_id,
        objective_id=objective_id,
        what_is_deferred=body.what_is_deferred,
        waiting_for=body.waiting_for,
        leading_hypothesis=body.leading_hypothesis,
        action_blocked=body.action_blocked,
        source_ref=body.source_ref,
        full_record=body.full_record,
    )
    db.add(pending)
    await db.flush()
    await write_memory_event(
        db,
        workspace_id=ws.id,
        brand_id=body.brand_id,
        objective_id=objective_id,
        event_type="decision_not_to_act",
        topic_tags=["commitment"],
        summary=f"Pending decision created: {body.what_is_deferred}",
        rationale=body.waiting_for,
        source_ref=f"pending_decision:{pending.id}",
        full_record={
            "pending_decision_id": str(pending.id),
            "what_is_deferred": body.what_is_deferred,
            "waiting_for": body.waiting_for,
            "action_blocked": body.action_blocked,
            "leading_hypothesis": body.leading_hypothesis,
        },
    )
    await db.commit()
    await db.refresh(pending)
    return PendingDecisionOut.model_validate(pending)


@router.post("/pending-decisions/{pending_id}/resolve", response_model=PendingDecisionOut, summary="Resolve a pending decision", responses={404: {"description": "Pending decision not found"}})
async def resolve_pending_decision(
    pending_id: uuid.UUID,
    body: PendingDecisionResolve,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    pending = (
        await db.execute(select(PendingDecision).where(PendingDecision.id == pending_id, PendingDecision.workspace_id == ws.id))
    ).scalar_one_or_none()
    if not pending:
        raise HTTPException(status_code=404, detail="Pending decision not found")
    pending.status = "resolved"
    pending.resolved_at = datetime.now(UTC)
    await write_memory_event(
        db,
        workspace_id=ws.id,
        brand_id=pending.brand_id,
        objective_id=pending.objective_id,
        event_type="decision_made",
        topic_tags=["commitment"],
        summary=f"Pending decision resolved: {pending.what_is_deferred}",
        rationale=body.resolution_summary or "Resolved by operator.",
        source_ref=f"pending_decision:{pending.id}",
        full_record={"pending_decision_id": str(pending.id), "resolution_summary": body.resolution_summary},
    )
    await db.commit()
    await db.refresh(pending)
    return PendingDecisionOut.model_validate(pending)


@router.get("/handoff/brief", response_model=HandoffBriefOut, summary="Generate handoff brief on demand")
async def get_handoff_brief(
    brand_id: NullableUUID = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    parsed_brand_id = brand_id
    if parsed_brand_id is not None:
        await _require_brand(db, ws.id, parsed_brand_id)

    objective_filters = [Objective.workspace_id == ws.id]
    if parsed_brand_id is not None:
        objective_filters.append(Objective.brand_id == parsed_brand_id)
    objectives = (
        await db.execute(select(Objective).where(*objective_filters).order_by(Objective.updated_at.desc()).limit(5))
    ).scalars().all()

    shared_filters = [OutcomeRecord.workspace_id == ws.id]
    memory_filters = [MemoryEvent.workspace_id == ws.id]
    decision_filters = [DecisionBrief.workspace_id == ws.id]
    pending_filters = [PendingDecision.workspace_id == ws.id, PendingDecision.status == "open"]
    if parsed_brand_id is not None:
        shared_filters.append(OutcomeRecord.brand_id == parsed_brand_id)
        memory_filters.append(MemoryEvent.brand_id == parsed_brand_id)
        decision_filters.append(DecisionBrief.brand_id == parsed_brand_id)
        pending_filters.append(PendingDecision.brand_id == parsed_brand_id)

    outcomes = (await db.execute(select(OutcomeRecord).where(*shared_filters).order_by(OutcomeRecord.recorded_at.desc()).limit(8))).scalars().all()
    memories = (await db.execute(select(MemoryEvent).where(*memory_filters).order_by(MemoryEvent.timestamp.desc()).limit(20))).scalars().all()
    decision_briefs = (await db.execute(select(DecisionBrief).where(*decision_filters).order_by(DecisionBrief.created_at.desc()).limit(5))).scalars().all()
    pending = (await db.execute(select(PendingDecision).where(*pending_filters).order_by(PendingDecision.created_at.desc()).limit(10))).scalars().all()

    known_risks = _known_risks(decision_briefs, pending, memories)
    working = _working(outcomes, memories)
    not_working = _not_working(decision_briefs, memories)
    decided_against = [m.summary for m in memories if m.event_type == "decision_not_to_act"][:5]
    recommended_first_action = _recommended_first_action(pending, decision_briefs, outcomes)

    return HandoffBriefOut(
        brand_id=parsed_brand_id,
        generated_at=datetime.now(UTC),
        active_objectives=[
            {
                "objective_id": str(o.id),
                "status": o.status,
                "summary": o.summary,
                "success_metric": o.success_metric,
                "horizon": o.horizon,
            }
            for o in objectives if o.status == "active"
        ],
        performance_narrative={
            "summary": _performance_summary(outcomes, decision_briefs),
            "confidence": "directional" if outcomes else "low",
            "recent_outcomes": [
                {"outcome_id": str(o.id), "summary": o.summary, "metrics": o.metrics_json, "confidence_source": o.confidence_source}
                for o in outcomes[:5]
            ],
        },
        pending_decisions=[PendingDecisionOut.model_validate(p) for p in pending],
        committed_actions=[
            {"decision_brief_id": str(d.id), "recommended_next": d.recommended_next, "confidence": d.confidence}
            for d in decision_briefs[:5]
        ],
        known_risks=known_risks,
        working=working,
        not_working=not_working,
        decided_against=decided_against,
        recommended_first_action=recommended_first_action,
    )


async def _require_brand(db: AsyncSession, workspace_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id, Brand.workspace_id == workspace_id))).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


async def _require_objective(db: AsyncSession, workspace_id: uuid.UUID, objective_id: uuid.UUID, brand_id: Optional[uuid.UUID]) -> Objective:
    filters = [Objective.id == objective_id, Objective.workspace_id == workspace_id]
    if brand_id is not None:
        filters.append(Objective.brand_id == brand_id)
    objective = (await db.execute(select(Objective).where(*filters))).scalar_one_or_none()
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    return objective


async def _validate_brand_scope(db: AsyncSession, workspace_id: uuid.UUID, brand_id: Optional[uuid.UUID]) -> None:
    if brand_id is not None:
        await _require_brand(db, workspace_id, brand_id)
        return
    brand_count = (await db.execute(select(func.count()).select_from(Brand).where(Brand.workspace_id == workspace_id))).scalar_one()
    if brand_count:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["query", "brand_id"], "msg": "brand_id is required when brands exist in this workspace", "type": "value_error"}],
        )


def _performance_summary(outcomes: list[OutcomeRecord], decision_briefs: list[DecisionBrief]) -> str:
    if outcomes:
        return f"{len(outcomes)} recent outcome(s) are available. Latest: {outcomes[0].summary}"
    if decision_briefs:
        return "DecisionBriefs exist, but no OutcomeRecord has closed the loop yet."
    return "No measured outcome has been recorded yet."


def _known_risks(decision_briefs: list[DecisionBrief], pending: list[PendingDecision], memories: list[MemoryEvent]) -> list[str]:
    risks: list[str] = []
    for d in decision_briefs:
        risks.extend(d.do_not_list or [])
    risks.extend([p.action_blocked for p in pending])
    for m in memories:
        if m.event_type in {"constraint_flag", "run_failed"}:
            risks.append(m.summary)
    return list(dict.fromkeys(risks))[:8]


def _working(outcomes: list[OutcomeRecord], memories: list[MemoryEvent]) -> list[str]:
    items = [o.summary for o in outcomes[:4]]
    items.extend(m.summary for m in memories if m.event_type == "artifact_approved")
    return list(dict.fromkeys(items))[:6]


def _not_working(decision_briefs: list[DecisionBrief], memories: list[MemoryEvent]) -> list[str]:
    items: list[str] = []
    for d in decision_briefs:
        items.extend(d.do_not_list or [])
    items.extend(m.summary for m in memories if m.event_type in {"artifact_dismissed", "run_failed"})
    return list(dict.fromkeys(items))[:6]


def _recommended_first_action(pending: list[PendingDecision], decision_briefs: list[DecisionBrief], outcomes: list[OutcomeRecord]) -> str:
    if pending:
        return f"Resolve pending decision: {pending[0].what_is_deferred}. Waiting for: {pending[0].waiting_for}."
    if decision_briefs:
        return decision_briefs[0].recommended_next
    if not outcomes:
        return "Create or approve a small Gmail action, then record the outcome."
    return "Generate the next DecisionBrief from the latest outcome memory."
