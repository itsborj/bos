from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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


# ── Helpers ────────────────────────────────────────────────────────────────────

async def get_singleton(db: AsyncSession) -> Workspace | None:
    result = await db.execute(select(Workspace).limit(1))
    return result.scalar_one_or_none()


async def _build_response(db: AsyncSession, ws: Workspace) -> WorkspaceResponse:
    prods = (await db.execute(select(Product).where(Product.workspace_id == ws.id))).scalars().all()
    auds = (await db.execute(select(Audience).where(Audience.workspace_id == ws.id))).scalars().all()

    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
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


@router.put("/brand", response_model=WorkspaceResponse, summary="Update brand context")
async def put_brand(
    payload: BrandPayload,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if ws is None:
        ws = Workspace(name="My Workspace", brand_json=payload.model_dump(exclude_none=True))
        db.add(ws)
    else:
        ws.brand_json = payload.model_dump(exclude_none=True)
    await db.commit()
    await db.refresh(ws)
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

    for item in payload.products:
        existing = None
        if item.id:
            row = await db.execute(
                select(Product).where(Product.id == item.id, Product.workspace_id == ws.id)
            )
            existing = row.scalar_one_or_none()

        if existing:
            existing.name = item.name
            existing.tagline = item.tagline
            existing.benefits_json = {"benefits": item.benefits}
        else:
            db.add(
                Product(
                    workspace_id=ws.id,
                    name=item.name,
                    tagline=item.tagline,
                    benefits_json={"benefits": item.benefits},
                )
            )

    await db.commit()
    await db.refresh(ws)
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

    await db.commit()
    await db.refresh(ws)
    return await _build_response(db, ws)
