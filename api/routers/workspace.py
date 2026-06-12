import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from models.workspace import Audience, Campaign, Product, Workspace
from schemas.workspace import (
    AudienceOut,
    AudiencesPayload,
    BrandOut,
    BrandPayload,
    ProductOut,
    ProductsPayload,
    WorkspaceNamePayload,
    WorkspaceResponse,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _safe_json(data: dict) -> dict:
    try:
        return json.loads(json.dumps(data, ensure_ascii=False))
    except (UnicodeEncodeError, ValueError):
        return json.loads(json.dumps(data, ensure_ascii=True))


# ── Helpers ────────────────────────────────────────────────────────────────────

async def get_singleton(db: AsyncSession) -> Workspace | None:
    result = await db.execute(select(Workspace).order_by(Workspace.created_at.asc()).limit(1))
    return result.scalar_one_or_none()


async def _build_response(db: AsyncSession, ws: Workspace) -> WorkspaceResponse:
    prods = (await db.execute(select(Product).where(Product.workspace_id == ws.id))).scalars().all()
    auds = (await db.execute(select(Audience).where(Audience.workspace_id == ws.id))).scalars().all()

    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        booking_url=ws.booking_url,
        brand=BrandOut(**(ws.brand_json or {})) if ws.brand_json else None,
        products=[
            ProductOut(
                id=p.id,
                name=p.name,
                tagline=p.tagline,
                benefits=(p.benefits_json or {}).get("benefits", []),
                brand_id=p.brand_id,
            )
            for p in prods
        ],
        audiences=[
            AudienceOut(
                id=a.id,
                name=a.name,
                demographics=(a.segment_json or {}).get("demographics"),
                pain_points=(a.segment_json or {}).get("pain_points", []),
                brand_id=a.brand_id,
            )
            for a in auds
        ],
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


def _not_initialized():
    raise HTTPException(
        status_code=412,
        detail={
            "error": {
                "code": "WORKSPACE_NOT_INITIALIZED",
                "message": "No workspace configured. Use PUT /workspace/brand to initialize.",
                "details": None,
            }
        },
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=WorkspaceResponse, summary="Get workspace state")
async def get_workspace(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        _not_initialized()
    return await _build_response(db, ws)


@router.put("", response_model=WorkspaceResponse, summary="Rename the workspace")
async def put_workspace(
    payload: WorkspaceNamePayload,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        _not_initialized()
    ws.name = payload.name
    await db.commit()
    await db.refresh(ws)
    return await _build_response(db, ws)


@router.get("/brand", response_model=WorkspaceResponse, summary="Get workspace state including brand context")
async def get_brand(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        _not_initialized()
    return await _build_response(db, ws)


@router.put("/brand", response_model=WorkspaceResponse, summary="Update brand context")
async def put_brand(
    payload: BrandPayload,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    brand_data = _safe_json(payload.model_dump(exclude_none=True))
    if ws is None:
        ws = Workspace(name="My Workspace", brand_json=brand_data)
        db.add(ws)
    else:
        ws.brand_json = brand_data
    try:
        await db.commit()
    except DBAPIError:
        await db.rollback()
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body"], "msg": "Brand data contains invalid characters", "type": "value_error"}],
        )
    await db.refresh(ws)
    return await _build_response(db, ws)


@router.get("/products", response_model=WorkspaceResponse, summary="Get workspace state including product catalog")
async def get_products(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        _not_initialized()
    return await _build_response(db, ws)


@router.put("/products", response_model=WorkspaceResponse, summary="Upsert product catalog")
async def put_products(
    payload: ProductsPayload,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        _not_initialized()

    payload_ids: set[uuid.UUID] = {
        uuid.UUID(str(item.id)) for item in payload.products if item.id
    }
    for item in payload.products:
        existing = None
        if item.id:
            row = await db.execute(
                select(Product).where(Product.id == item.id, Product.workspace_id == ws.id)
            )
            existing = row.scalar_one_or_none()

        benefits = _safe_json({"benefits": item.benefits or []})
        if existing:
            existing.name = item.name
            existing.tagline = item.tagline
            existing.benefits_json = benefits
        else:
            db.add(
                Product(
                    workspace_id=ws.id,
                    name=item.name,
                    tagline=item.tagline,
                    benefits_json=benefits,
                )
            )

    # Delete workspace-level rows not referenced in the payload (replace semantics)
    del_stmt = sa_delete(Product).where(
        Product.workspace_id == ws.id,
        Product.brand_id == None,  # noqa: E711 — workspace-level rows only
    )
    if payload_ids:
        del_stmt = del_stmt.where(~Product.id.in_(payload_ids))
    await db.execute(del_stmt)

    try:
        await db.commit()
    except DBAPIError:
        await db.rollback()
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", "products"], "msg": "Product data contains invalid characters", "type": "value_error"}],
        )
    await db.refresh(ws)
    return await _build_response(db, ws)


class BookingUrlPayload(BaseModel):
    url: Optional[str] = None


@router.get("/booking", response_model=WorkspaceResponse, summary="Get workspace state including booking page URL")
async def get_booking_url(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        _not_initialized()
    return await _build_response(db, ws)


@router.put("/booking", response_model=WorkspaceResponse, summary="Set booking page URL")
async def put_booking_url(
    payload: BookingUrlPayload,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        _not_initialized()
    ws.booking_url = payload.url or None
    await db.commit()
    await db.refresh(ws)
    return await _build_response(db, ws)


@router.get("/audiences", response_model=WorkspaceResponse, summary="Get workspace state including audience segments")
async def get_audiences(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        _not_initialized()
    return await _build_response(db, ws)


@router.put("/audiences", response_model=WorkspaceResponse, summary="Upsert audience segments")
async def put_audiences(
    payload: AudiencesPayload,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        _not_initialized()

    payload_aud_ids: set[uuid.UUID] = {
        uuid.UUID(str(item.id)) for item in payload.audiences if item.id
    }
    for item in payload.audiences:
        existing = None
        if item.id:
            row = await db.execute(
                select(Audience).where(Audience.id == item.id, Audience.workspace_id == ws.id)
            )
            existing = row.scalar_one_or_none()

        if existing:
            existing.name = item.name
            existing.segment_json = {
                "demographics": item.demographics,
                "pain_points": item.pain_points,
            }
        else:
            db.add(
                Audience(
                    workspace_id=ws.id,
                    name=item.name,
                    segment_json={
                        "demographics": item.demographics,
                        "pain_points": item.pain_points,
                    },
                )
            )

    # Delete workspace-level rows not referenced in the payload (replace semantics)
    del_aud_stmt = sa_delete(Audience).where(
        Audience.workspace_id == ws.id,
        Audience.brand_id == None,  # noqa: E711 — workspace-level rows only
    )
    if payload_aud_ids:
        del_aud_stmt = del_aud_stmt.where(~Audience.id.in_(payload_aud_ids))
    await db.execute(del_aud_stmt)

    await db.commit()
    await db.refresh(ws)
    return await _build_response(db, ws)
