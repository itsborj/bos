import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from models.objective import Objective
from models.workspace import Brand
from routers.workspace import get_singleton
from schemas.objective import ObjectiveCreate, ObjectiveListResponse, ObjectiveOut, ObjectiveUpdate

router = APIRouter(prefix="/objectives", tags=["objectives"])

_ALLOWED_STATUSES = {"draft", "active", "paused", "completed", "archived"}


@router.get("", response_model=ObjectiveListResponse, summary="List objectives for the workspace")
async def list_objectives(
    brand_id: Optional[uuid.UUID] = None,
    status: Optional[str] = Query(default=None, pattern="^(draft|active|paused|completed|archived)$"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return ObjectiveListResponse(objectives=[], total=0)

    filters = [Objective.workspace_id == ws.id]
    if brand_id is not None:
        await _require_brand(db, ws.id, brand_id)
        filters.append(Objective.brand_id == brand_id)
    if status is not None:
        filters.append(Objective.status == status)

    total = (await db.execute(select(func.count()).select_from(Objective).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(Objective).where(*filters).order_by(Objective.updated_at.desc(), Objective.created_at.desc()).limit(100)
        )
    ).scalars().all()
    return ObjectiveListResponse(objectives=[ObjectiveOut.model_validate(r) for r in rows], total=total)


@router.get("/active", response_model=ObjectiveOut, summary="Get the current active objective")
async def get_active_objective(
    brand_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    await _validate_brand_scope(db, ws.id, brand_id)

    filters = [Objective.workspace_id == ws.id, Objective.status == "active"]
    if brand_id is not None:
        filters.append(Objective.brand_id == brand_id)

    objective = (
        await db.execute(
            select(Objective).where(*filters).order_by(Objective.updated_at.desc(), Objective.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if not objective:
        raise HTTPException(status_code=404, detail="No active objective found")
    return ObjectiveOut.model_validate(objective)


@router.post("", response_model=ObjectiveOut, status_code=201, summary="Create an objective anchor")
async def create_objective(
    body: ObjectiveCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    await _validate_brand_scope(db, ws.id, body.brand_id)

    objective = Objective(
        workspace_id=ws.id,
        brand_id=body.brand_id,
        status=body.status,
        summary=body.summary,
        success_metric=body.success_metric,
        horizon=body.horizon,
        created_from=body.created_from,
    )
    db.add(objective)
    await db.commit()
    await db.refresh(objective)
    return ObjectiveOut.model_validate(objective)


@router.get("/{objective_id}", response_model=ObjectiveOut, summary="Get an objective")
async def get_objective(
    objective_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    objective = await _get_objective(db, ws.id, objective_id)
    return ObjectiveOut.model_validate(objective)


@router.patch("/{objective_id}", response_model=ObjectiveOut, summary="Update an objective anchor")
async def update_objective(
    objective_id: uuid.UUID,
    body: ObjectiveUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    objective = await _get_objective(db, ws.id, objective_id)

    updates = body.model_dump(exclude_unset=True)
    if "brand_id" in updates:
        await _validate_brand_scope(db, ws.id, updates["brand_id"])
    if "status" in updates and updates["status"] not in _ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid objective status")

    for key, value in updates.items():
        setattr(objective, key, value)

    await db.commit()
    await db.refresh(objective)
    return ObjectiveOut.model_validate(objective)


async def _get_objective(db: AsyncSession, workspace_id: uuid.UUID, objective_id: uuid.UUID) -> Objective:
    objective = (
        await db.execute(select(Objective).where(Objective.id == objective_id, Objective.workspace_id == workspace_id))
    ).scalar_one_or_none()
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    return objective


async def _require_brand(db: AsyncSession, workspace_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    brand = (
        await db.execute(select(Brand).where(Brand.id == brand_id, Brand.workspace_id == workspace_id))
    ).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


async def _validate_brand_scope(db: AsyncSession, workspace_id: uuid.UUID, brand_id: Optional[uuid.UUID]) -> None:
    if brand_id is not None:
        await _require_brand(db, workspace_id, brand_id)
        return

    brand_count = (await db.execute(select(func.count()).select_from(Brand).where(Brand.workspace_id == workspace_id))).scalar_one()
    if brand_count:
        raise HTTPException(status_code=400, detail="brand_id is required when brands exist in this workspace")
