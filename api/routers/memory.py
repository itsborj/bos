import uuid
from typing import Optional, get_args

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from memory_events import write_memory_event
from models.memory import MemoryEvent
from models.objective import Objective
from models.workspace import Brand
from routers.workspace import get_singleton
from schemas.memory import MemoryEventCreate, MemoryEventListResponse, MemoryEventOut, MemoryEventType
from validation import NullableUUID

_EVENT_TYPE_VALUES = list(get_args(MemoryEventType))

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/events", response_model=MemoryEventListResponse, summary="List memory events", responses={400: {"description": "Invalid event type"}, 404: {"description": "Brand not found"}})
async def list_memory_events(
    brand_id: NullableUUID = None,
    objective_id: NullableUUID = None,
    event_type: Optional[str] = Query(default=None, enum=_EVENT_TYPE_VALUES),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return MemoryEventListResponse(events=[], total=0)

    filters = [MemoryEvent.workspace_id == ws.id]
    if brand_id is not None:
        await _require_brand(db, ws.id, brand_id)
        filters.append(MemoryEvent.brand_id == brand_id)
    if objective_id is not None:
        await _require_objective(db, ws.id, objective_id, brand_id)
        filters.append(MemoryEvent.objective_id == objective_id)
    if event_type is not None and event_type not in _EVENT_TYPE_VALUES:
        event_type = None
    if event_type is not None:
        filters.append(MemoryEvent.event_type == event_type)

    total = (await db.execute(select(func.count()).select_from(MemoryEvent).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(MemoryEvent).where(*filters).order_by(MemoryEvent.timestamp.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return MemoryEventListResponse(events=[MemoryEventOut.model_validate(r) for r in rows], total=total)


@router.post("/events", response_model=MemoryEventOut, status_code=201, summary="Write an explicit memory event", responses={400: {"description": "Invalid memory event or brand scope"}, 412: {"description": "Workspace not initialized"}})
async def create_memory_event(
    body: MemoryEventCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    await _validate_brand_scope(db, ws.id, body.brand_id)
    if body.objective_id is not None:
        await _require_objective(db, ws.id, body.objective_id, body.brand_id)

    try:
        event = await write_memory_event(
            db,
            workspace_id=ws.id,
            brand_id=body.brand_id,
            objective_id=body.objective_id,
            event_type=body.event_type,
            topic_tags=body.topic_tags,
            summary=body.summary,
            rationale=body.rationale,
            source_ref=body.source_ref,
            full_record=body.full_record,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    await db.refresh(event)
    return MemoryEventOut.model_validate(event)


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
