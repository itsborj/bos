import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import String, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from models.stream import StreamUpdate
from routers.workspace import get_singleton
from schemas.stream import StreamBulkDismissOut, StreamListResponse, StreamRefreshOut, StreamUpdateOut
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
    request: Request,
    include_read: bool = False,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    extra_query_keys = sorted(set(request.query_params.keys()) - {"include_read"})
    if extra_query_keys:
        raise HTTPException(
            status_code=422,
            detail=[
                {"loc": ["query", key], "msg": "extra query parameter is not permitted", "type": "extra_forbidden"}
                for key in extra_query_keys
            ],
        )
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
        await db.execute(
            select(func.count(func.distinct(func.coalesce(StreamUpdate.source_key, cast(StreamUpdate.id, String))))).where(*filters)
        )
    ).scalar_one()

    rows = (
        await db.execute(
            select(StreamUpdate)
            .where(*filters)
            .order_by(_PRIORITY_CASE, StreamUpdate.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    seen: set[str] = set()
    deduped: list[StreamUpdate] = []
    for row in rows:
        key = row.source_key or str(row.id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= 50:
            break

    return StreamListResponse(
        updates=[StreamUpdateOut.model_validate(r) for r in deduped],
        total=total,
    )


async def _refresh_stream_blocks(db: AsyncSession) -> StreamRefreshOut:
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
    "/stream/refresh",
    response_model=StreamRefreshOut,
    summary="Rebuild stream blocks from current workspace state",
)
async def refresh_stream(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    return await _refresh_stream_blocks(db)


@router.get(
    "/stream/refresh",
    response_model=StreamRefreshOut,
    summary="Rebuild stream blocks from current workspace state (GET-compatible)",
)
async def refresh_stream_get(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    return await _refresh_stream_blocks(db)


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


@router.post(
    "/stream/dismiss",
    response_model=StreamBulkDismissOut,
    summary="Bulk-dismiss unread stream updates",
)
async def bulk_dismiss_updates(
    priority: str | None = None,
    type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return StreamBulkDismissOut(dismissed=0, message="No workspace configured.")
    filters = [
        StreamUpdate.workspace_id == ws.id,
        StreamUpdate.dismissed_at.is_(None),
    ]
    if priority:
        filters.append(StreamUpdate.priority == priority)
    if type:
        filters.append(StreamUpdate.type == type)
    rows = (await db.execute(select(StreamUpdate).where(*filters))).scalars().all()
    now = datetime.now(UTC)
    for update in rows:
        update.dismissed_at = now
    if rows:
        await db.commit()
    return StreamBulkDismissOut(
        dismissed=len(rows),
        message=f"Dismissed {len(rows)} stream update(s).",
    )


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
