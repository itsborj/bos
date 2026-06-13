import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from memory_events import resolve_active_objective_id, write_memory_event
from models.objective import Objective
from models.outcome import OutcomeRecord
from models.workspace import Brand
from routers.workspace import get_singleton
from schemas.outcome import EvaluateOutcomeIn, EvaluateOutcomeOut, OutcomeListResponse, OutcomeRecordOut
from validation import NullableUUID

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


@router.get("", response_model=OutcomeListResponse, summary="List outcome records", responses={404: {"description": "Brand not found"}})
async def list_outcomes(
    brand_id: NullableUUID = None,
    objective_id: NullableUUID = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return OutcomeListResponse(outcomes=[], total=0)

    filters = [OutcomeRecord.workspace_id == ws.id]
    if brand_id is not None:
        await _require_brand(db, ws.id, brand_id)
        filters.append(OutcomeRecord.brand_id == brand_id)
    if objective_id is not None:
        await _require_objective(db, ws.id, objective_id, brand_id)
        filters.append(OutcomeRecord.objective_id == objective_id)

    total = (await db.execute(select(func.count()).select_from(OutcomeRecord).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(OutcomeRecord).where(*filters).order_by(OutcomeRecord.recorded_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return OutcomeListResponse(outcomes=[OutcomeRecordOut.model_validate(r) for r in rows], total=total)


@router.post("/evaluate", response_model=EvaluateOutcomeOut, status_code=201, summary="Manually evaluate an outcome")
async def evaluate_outcome(
    body: EvaluateOutcomeIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    await _validate_brand_scope(db, ws.id, body.brand_id)

    objective_id = body.objective_id
    if objective_id is not None:
        await _require_objective(db, ws.id, objective_id, body.brand_id)
    else:
        objective_id = await resolve_active_objective_id(db, ws.id, body.brand_id)

    outcome = OutcomeRecord(
        workspace_id=ws.id,
        brand_id=body.brand_id,
        objective_id=objective_id,
        source_ref=body.source_ref,
        summary=body.summary,
        metrics_json=body.metrics,
        confidence_source=body.confidence_source or "manually_reported",
        full_record=body.full_record,
    )
    db.add(outcome)
    await db.flush()

    event = await write_memory_event(
        db,
        workspace_id=ws.id,
        brand_id=body.brand_id,
        objective_id=objective_id,
        event_type="outcome_recorded",
        topic_tags=body.topic_tags or ["outcome"],
        summary=body.summary,
        source_ref=f"outcome:{outcome.id}",
        full_record={
            "outcome_id": str(outcome.id),
            "source_ref": body.source_ref,
            "metrics": body.metrics,
            "confidence_source": body.confidence_source or "manually_reported",
            "full_record": body.full_record,
        },
    )

    await db.commit()
    await db.refresh(outcome)
    await db.refresh(event)
    return EvaluateOutcomeOut(outcome=OutcomeRecordOut.model_validate(outcome), memory_event_id=event.id)


async def _require_brand(db: AsyncSession, workspace_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    brand = (
        await db.execute(select(Brand).where(Brand.id == brand_id, Brand.workspace_id == workspace_id))
    ).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


async def _require_objective(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    objective_id: uuid.UUID,
    brand_id: Optional[uuid.UUID],
) -> Objective:
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
            detail=[{"loc": ["body", "brand_id"], "msg": "brand_id is required when brands exist in this workspace", "type": "value_error"}],
        )
