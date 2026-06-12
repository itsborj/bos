import uuid
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
from models.run import Run
from models.workspace import Brand
from routers.workspace import get_singleton
from schemas.decision_brief import (
    DecisionBriefCreate,
    DecisionBriefGenerateIn,
    DecisionBriefListResponse,
    DecisionBriefOut,
)
from validation import NullableUUID

router = APIRouter(prefix="/decision-briefs", tags=["decision-briefs"])

_TOPIC_TAGS = {"creative_fatigue", "tracking", "attribution", "offer", "objection", "commitment", "outcome"}


@router.get("", response_model=DecisionBriefListResponse, summary="List decision briefs", responses={404: {"description": "Brand not found"}})
async def list_decision_briefs(
    brand_id: NullableUUID = None,
    objective_id: NullableUUID = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return DecisionBriefListResponse(decision_briefs=[], total=0)

    filters = [DecisionBrief.workspace_id == ws.id]
    if brand_id is not None:
        await _require_brand(db, ws.id, brand_id)
        filters.append(DecisionBrief.brand_id == brand_id)
    if objective_id is not None:
        await _require_objective(db, ws.id, objective_id, brand_id)
        filters.append(DecisionBrief.objective_id == objective_id)
    if status is not None:
        filters.append(DecisionBrief.status == status)

    total = (await db.execute(select(func.count()).select_from(DecisionBrief).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(DecisionBrief).where(*filters).order_by(DecisionBrief.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return DecisionBriefListResponse(decision_briefs=[DecisionBriefOut.model_validate(r) for r in rows], total=total)


@router.post("", response_model=DecisionBriefOut, status_code=201, summary="Create a decision brief")
async def create_decision_brief(
    body: DecisionBriefCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    await _validate_brand_scope(db, ws.id, body.brand_id)
    if body.objective_id is not None:
        await _require_objective(db, ws.id, body.objective_id, body.brand_id)

    brief = DecisionBrief(
        workspace_id=ws.id,
        brand_id=body.brand_id,
        objective_id=body.objective_id,
        status=body.status,
        summary=body.summary,
        objective_affected=body.objective_affected,
        evidence=body.evidence,
        hypothesis_ranking=body.hypothesis_ranking,
        confidence=body.confidence,
        recommended_next=body.recommended_next,
        do_not_list=body.do_not_list,
        allowed_actions=body.allowed_actions,
        source_refs=body.source_refs,
        full_record=body.full_record,
    )
    db.add(brief)
    await db.flush()
    await write_memory_event(
        db,
        workspace_id=ws.id,
        brand_id=body.brand_id,
        objective_id=body.objective_id,
        event_type="constraint_flag",
        topic_tags=_extract_topic_tags(body.evidence),
        summary=f"DecisionBrief created: {body.summary}",
        source_ref=f"decision_brief:{brief.id}",
        full_record={"recommended_next": body.recommended_next, "confidence": body.confidence},
    )
    await db.commit()
    await db.refresh(brief)
    return DecisionBriefOut.model_validate(brief)


@router.post("/generate", response_model=DecisionBriefOut, status_code=201, summary="Generate DecisionBrief v0 from current memory")
async def generate_decision_brief(
    body: DecisionBriefGenerateIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    await _validate_brand_scope(db, ws.id, body.brand_id)

    objective_id = body.objective_id or await resolve_active_objective_id(db, ws.id, body.brand_id)
    objective: Objective | None = None
    if objective_id is not None:
        objective = await _require_objective(db, ws.id, objective_id, body.brand_id)

    outcomes = (
        await db.execute(
            select(OutcomeRecord)
            .where(*_brand_objective_filters(OutcomeRecord, ws.id, body.brand_id, objective_id))
            .order_by(OutcomeRecord.recorded_at.desc())
            .limit(8)
        )
    ).scalars().all()
    memories = (
        await db.execute(
            select(MemoryEvent)
            .where(*_brand_objective_filters(MemoryEvent, ws.id, body.brand_id, objective_id))
            .order_by(MemoryEvent.timestamp.desc())
            .limit(12)
        )
    ).scalars().all()
    runs = (
        await db.execute(
            select(Run)
            .where(Run.workspace_id == ws.id, Run.brand_id == body.brand_id if body.brand_id else Run.brand_id.is_(None))
            .order_by(Run.created_at.desc())
            .limit(8)
        )
    ).scalars().all()

    evidence = _build_evidence(outcomes, memories, runs)
    hypothesis_ranking = _build_hypotheses(outcomes, memories, runs)
    confidence = _confidence(outcomes, memories)
    summary = body.summary_override or _summary(objective, outcomes, memories)
    recommended_next = body.recommended_next_override or _recommended_next(outcomes, memories)
    do_not_list = _do_not_list(outcomes, memories)
    source_refs = [f"outcome:{o.id}" for o in outcomes[:5]] + [f"memory:{m.id}" for m in memories[:5]]

    brief = DecisionBrief(
        workspace_id=ws.id,
        brand_id=body.brand_id,
        objective_id=objective_id,
        status="active",
        summary=summary,
        objective_affected=objective.summary if objective else None,
        evidence=evidence,
        hypothesis_ranking=hypothesis_ranking,
        confidence=confidence,
        recommended_next=recommended_next,
        do_not_list=do_not_list,
        allowed_actions=["ask CMO", "investigate", "approve next artifact", "record outcome", "dismiss"],
        source_refs=source_refs,
        full_record={
            "inputs": {
                "outcome_count": len(outcomes),
                "memory_event_count": len(memories),
                "recent_run_count": len(runs),
            },
            "topic_tags": sorted(_extract_topic_tags(evidence)),
        },
    )
    db.add(brief)
    await db.flush()
    await write_memory_event(
        db,
        workspace_id=ws.id,
        brand_id=body.brand_id,
        objective_id=objective_id,
        event_type="constraint_flag",
        topic_tags=sorted(_extract_topic_tags(evidence)),
        summary=f"DecisionBrief generated: {summary}",
        source_ref=f"decision_brief:{brief.id}",
        full_record={"decision_brief_id": str(brief.id), "recommended_next": recommended_next, "confidence": confidence},
    )
    await db.commit()
    await db.refresh(brief)
    return DecisionBriefOut.model_validate(brief)


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
        raise HTTPException(status_code=400, detail="brand_id is required when brands exist in this workspace")


def _brand_objective_filters(model, workspace_id: uuid.UUID, brand_id: Optional[uuid.UUID], objective_id: Optional[uuid.UUID]) -> list:
    filters = [model.workspace_id == workspace_id]
    filters.append(model.brand_id == brand_id if brand_id else model.brand_id.is_(None))
    if objective_id is not None:
        filters.append(model.objective_id == objective_id)
    return filters


def _build_evidence(outcomes: list[OutcomeRecord], memories: list[MemoryEvent], runs: list[Run]) -> list[dict]:
    evidence: list[dict] = []
    for outcome in outcomes[:5]:
        evidence.append({
            "type": "outcome",
            "summary": outcome.summary,
            "metrics": outcome.metrics_json or {},
            "confidence_source": outcome.confidence_source,
            "source_ref": f"outcome:{outcome.id}",
            "topic_tags": ["outcome"],
        })
    for memory in memories[:5]:
        evidence.append({
            "type": "memory_event",
            "event_type": memory.event_type,
            "summary": memory.summary,
            "topic_tags": memory.topic_tags or [],
            "source_ref": f"memory:{memory.id}",
        })
    if runs:
        evidence.append({
            "type": "run_history",
            "summary": f"{len(runs)} recent run(s) available for this brand scope.",
            "topic_tags": [],
        })
    return evidence[:10]


def _build_hypotheses(outcomes: list[OutcomeRecord], memories: list[MemoryEvent], runs: list[Run]) -> list[dict]:
    hypotheses: list[dict] = []
    if outcomes:
        hypotheses.append({
            "rank": 1,
            "hypothesis": "Recent outcomes should guide the next action more than generic campaign assumptions.",
            "support": f"{len(outcomes)} OutcomeRecord(s) found.",
            "confidence": "medium",
        })
    if any("objection" in (m.topic_tags or []) for m in memories):
        hypotheses.append({
            "rank": len(hypotheses) + 1,
            "hypothesis": "Buyer objections are shaping response quality and should be addressed before scaling.",
            "support": "Objection-tagged memory exists.",
            "confidence": "directional",
        })
    if any("tracking" in (m.topic_tags or []) for m in memories):
        hypotheses.append({
            "rank": len(hypotheses) + 1,
            "hypothesis": "Measurement or list freshness may be limiting confidence.",
            "support": "Tracking-tagged memory exists.",
            "confidence": "directional",
        })
    if not hypotheses:
        hypotheses.append({
            "rank": 1,
            "hypothesis": "There is not enough measured outcome data yet; run a small approved proof step before scaling.",
            "support": "No recent OutcomeRecords found for this objective scope.",
            "confidence": "low",
        })
    return hypotheses


def _confidence(outcomes: list[OutcomeRecord], memories: list[MemoryEvent]) -> str:
    if len(outcomes) >= 2 and len(memories) >= 3:
        return "directional · 0.72"
    if outcomes:
        return "directional · 0.62"
    return "low · 0.38"


def _summary(objective: Optional[Objective], outcomes: list[OutcomeRecord], memories: list[MemoryEvent]) -> str:
    base = objective.summary if objective else "the active objective"
    if outcomes:
        return f"Next recommendation for {base} is informed by {len(outcomes)} recorded outcome(s)."
    if memories:
        return f"Next recommendation for {base} is based on memory, but needs an outcome to improve confidence."
    return f"Next recommendation for {base} needs a small approved action so BOS can start learning."


def _recommended_next(outcomes: list[OutcomeRecord], memories: list[MemoryEvent]) -> str:
    if outcomes:
        return "Prepare the next Gmail artifact using the recorded outcome pattern; keep the approval boundary before sending."
    return "Run a small Gmail proof step, then record the outcome before scaling."


def _do_not_list(outcomes: list[OutcomeRecord], memories: list[MemoryEvent]) -> list[str]:
    items = ["Do not auto-send or scale without explicit approval."]
    if not outcomes:
        items.append("Do not claim the recommendation improved from memory until an outcome is recorded.")
    if any("tracking" in (m.topic_tags or []) for m in memories):
        items.append("Do not overstate confidence while tracking/list freshness is unresolved.")
    return items


def _extract_topic_tags(evidence: list[dict]) -> set[str]:
    tags: set[str] = set()
    for item in evidence:
        for tag in item.get("topic_tags") or []:
            if tag in _TOPIC_TAGS:
                tags.add(tag)
    return tags
