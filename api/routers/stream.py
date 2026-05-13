import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from models.stream import StreamUpdate
from routers.workspace import get_singleton
from schemas.stream import StreamListResponse, StreamRefreshOut, StreamUpdateOut
from stream.builder import build
from stream.types import PRIORITY_ORDER

router = APIRouter(tags=["stream"])

_PRIORITY_CASE = case(
    (StreamUpdate.priority == "urgent", 0),
    (StreamUpdate.priority == "high", 1),
    (StreamUpdate.priority == "normal", 2),
    (StreamUpdate.priority == "low", 3),
    else_=4,
)


@router.get("/stream", response_model=StreamListResponse, summary="Briefing blocks for workspace")
async def get_stream(
    include_read: bool = False,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return StreamListResponse(updates=[], total=0)

    filters = [
        StreamUpdate.workspace_id == ws.id,
        StreamUpdate.dismissed_at.is_(None),
    ]
    if not include_read:
        filters.append(StreamUpdate.read_at.is_(None))

    total = (
        await db.execute(select(func.count()).select_from(StreamUpdate).where(*filters))
    ).scalar_one()

    rows = (
        await db.execute(
            select(StreamUpdate)
            .where(*filters)
            .order_by(_PRIORITY_CASE, StreamUpdate.created_at.desc())
            .limit(50)
        )
    ).scalars().all()

    return StreamListResponse(
        updates=[StreamUpdateOut.model_validate(r) for r in rows],
        total=total,
    )


@router.post(
    "/stream/refresh",
    response_model=StreamRefreshOut,
    summary="Rebuild stream blocks from current workspace state",
)
async def refresh_stream(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(
            status_code=412,
            detail={"error": {"code": "WORKSPACE_NOT_INITIALIZED", "message": "Initialize workspace first", "details": None}},
        )
    created = await build(db, ws, openrouter_key=settings.platform_openrouter_key)
    return StreamRefreshOut(
        created=created,
        message=f"{created} new block(s) added to stream." if created else "Stream is up to date.",
    )


@router.post(
    "/stream/{update_id}/read",
    response_model=StreamUpdateOut,
    summary="Mark a stream update as read",
)
async def mark_read(
    update_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    update = await _get_update(db, update_id)
    if not update.read_at:
        update.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(update)
    return StreamUpdateOut.model_validate(update)


@router.delete(
    "/stream/{update_id}",
    response_model=StreamUpdateOut,
    summary="Dismiss a stream update",
)
async def dismiss_update(
    update_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    update = await _get_update(db, update_id)
    if not update.dismissed_at:
        update.dismissed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(update)
    return StreamUpdateOut.model_validate(update)


async def _get_update(db: AsyncSession, update_id: uuid.UUID) -> StreamUpdate:
    row = await db.execute(select(StreamUpdate).where(StreamUpdate.id == update_id))
    update = row.scalar_one_or_none()
    if not update:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "UPDATE_NOT_FOUND", "message": f"Stream update '{update_id}' not found", "details": None}},
        )
    return update
