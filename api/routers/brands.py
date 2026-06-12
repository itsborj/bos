"""Brand management — POST/GET/PUT/DELETE /brands."""
from __future__ import annotations

import json
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError

from auth import require_api_key
from data_hygiene import contains_fuzzer_garbage, reject_fuzzer_garbage
from db import get_db
from models.workspace import Audience, Brand, Campaign, Product
from models.document import WorkspaceDocument
from models.run import Run
from routers.workspace import get_singleton
from schemas.brands import BrandCreate, BrandResponse, BrandUpdate


def _safe_json(data: dict) -> dict:
    """Round-trip through JSON to strip Unicode surrogates that crash PostgreSQL."""
    try:
        return json.loads(json.dumps(data, ensure_ascii=False))
    except (UnicodeEncodeError, ValueError):
        return json.loads(json.dumps(data, ensure_ascii=True))

router = APIRouter(prefix="/brands", tags=["brands"])


def _migrate_legacy_pm_config(bj: dict) -> dict | None:
    """One-time read-path upgrade: clickup_config → pm_config with plugin field."""
    legacy = bj.get("clickup_config")
    if not legacy:
        return None
    migrated = dict(legacy)
    migrated.setdefault("plugin", "channel.clickup")
    return migrated


def _to_response(brand: Brand) -> BrandResponse:
    bj = brand.brand_json or {}
    return BrandResponse(
        id=str(brand.id),
        workspace_id=str(brand.workspace_id),
        name=brand.name,
        voice=bj.get("voice", ""),
        tone=bj.get("tone", ""),
        values=bj.get("values", []),
        domain=bj.get("domain", ""),
        website_url=bj.get("website_url", ""),
        social_handles=bj.get("social_handles", {}),
        pm_config=bj.get("pm_config") or _migrate_legacy_pm_config(bj),
        created_at=brand.created_at.isoformat(),
        updated_at=brand.updated_at.isoformat(),
    )


class BrandListResponse(BaseModel):
    brands: list[BrandResponse]
    total: int


@router.get("", response_model=BrandListResponse)
async def list_brands(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return BrandListResponse(brands=[], total=0)
    rows = (await db.execute(
        select(Brand).where(Brand.workspace_id == ws.id).order_by(Brand.created_at.asc())
    )).scalars().all()
    rows = [b for b in rows if not contains_fuzzer_garbage(b.name) and not contains_fuzzer_garbage(b.brand_json or {})]
    items = [_to_response(b) for b in rows]
    return BrandListResponse(brands=items, total=len(items))


@router.post("", response_model=BrandResponse, status_code=201, responses={409: {"description": "Brand already exists"}})
async def create_brand(
    body: BrandCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    reject_fuzzer_garbage(body.model_dump(), ["body"])

    existing = (await db.execute(
        select(Brand).where(Brand.workspace_id == ws.id, Brand.name == body.name)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Brand '{body.name}' already exists")

    brand = Brand(
        workspace_id=ws.id,
        name=body.name,
        brand_json=_safe_json({
            "voice": body.voice,
            "tone": body.tone,
            "values": body.values,
            "domain": body.domain,
            "website_url": body.website_url,
            "social_handles": body.social_handles,
        }),
    )
    db.add(brand)
    try:
        await db.commit()
    except DBAPIError:
        await db.rollback()
        raise HTTPException(
                status_code=422,
                detail=[{"loc": ["body", "brand_json"], "msg": "Brand data contains invalid characters", "type": "value_error"}],
            )
    await db.refresh(brand)
    return _to_response(brand)


@router.get("/{brand_id}", response_model=BrandResponse, responses={404: {"description": "Brand not found"}})
async def get_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=404, detail="Brand not found")
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id, Brand.workspace_id == ws.id))).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return _to_response(brand)


@router.put("/{brand_id}", response_model=BrandResponse, responses={404: {"description": "Brand not found"}, 409: {"description": "Brand name already exists"}})
async def update_brand(
    brand_id: UUID,
    body: BrandUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=404, detail="Brand not found")
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id, Brand.workspace_id == ws.id))).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    reject_fuzzer_garbage(body.model_dump(exclude_unset=True), ["body"])
    if body.name is not None and body.name != brand.name:
        conflict = (await db.execute(
            select(Brand).where(Brand.workspace_id == ws.id, Brand.name == body.name, Brand.id != brand_id)
        )).scalar_one_or_none()
        if conflict:
            raise HTTPException(status_code=409, detail=f"Brand '{body.name}' already exists")
    bj = dict(brand.brand_json or {})
    if body.name is not None:
        brand.name = body.name
    if body.voice is not None:
        bj["voice"] = body.voice
    if body.tone is not None:
        bj["tone"] = body.tone
    if body.values is not None:
        bj["values"] = body.values
    if body.domain is not None:
        bj["domain"] = body.domain
    if body.website_url is not None:
        bj["website_url"] = body.website_url
    if body.social_handles is not None:
        bj["social_handles"] = body.social_handles
    if body.pm_config is not None:
        bj["pm_config"] = body.pm_config
        bj.pop("clickup_config", None)  # remove legacy key on first write
    brand.brand_json = _safe_json(bj)

    try:
        await db.commit()
    except DBAPIError:
        await db.rollback()
        raise HTTPException(
                status_code=422,
                detail=[{"loc": ["body", "brand_json"], "msg": "Brand data contains invalid characters", "type": "value_error"}],
            )
    await db.refresh(brand)
    return _to_response(brand)


@router.delete("/{brand_id}", status_code=204, responses={404: {"description": "Brand not found"}})
async def delete_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=404, detail="Brand not found")
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id, Brand.workspace_id == ws.id))).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    await db.delete(brand)
    await db.commit()


class ClaimResult(BaseModel):
    brand: BrandResponse
    claimed: dict[str, int]


@router.post("/{brand_id}/claim-workspace", response_model=ClaimResult, responses={404: {"description": "Brand not found"}})
async def claim_workspace(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Promote all workspace-level data (brand_id IS NULL) to belong to this brand.
    Also merges workspace.brand_json into brand profile for any empty fields."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    # Merge workspace brand_json into brand profile for empty fields
    ws_brand = ws.brand_json or {}
    bj = dict(brand.brand_json or {})
    for field in ("voice", "tone", "values", "domain", "website_url", "social_handles"):
        if not bj.get(field) and ws_brand.get(field):
            bj[field] = ws_brand[field]
    brand.brand_json = bj

    # Claim all unlinked workspace rows
    tables = [
        ("products",            Product),
        ("audiences",           Audience),
        ("workspace_documents", WorkspaceDocument),
        ("campaigns",           Campaign),
        ("runs",                Run),
    ]
    claimed: dict[str, int] = {}
    for label, Model in tables:
        result = await db.execute(
            update(Model)
            .where(Model.workspace_id == ws.id, Model.brand_id == None)  # noqa: E711
            .values(brand_id=brand.id)
        )
        claimed[label] = result.rowcount

    await db.commit()
    await db.refresh(brand)
    return ClaimResult(brand=_to_response(brand), claimed=claimed)


async def resolve_brand(db: AsyncSession, brand_id: Optional[uuid.UUID | str]) -> Optional[Brand]:
    """Load a Brand by ID. Returns None silently if brand_id is absent or invalid."""
    if not brand_id:
        return None
    if isinstance(brand_id, uuid.UUID):
        bid = brand_id
    else:
        try:
            bid = uuid.UUID(brand_id)
        except (ValueError, AttributeError):
            return None
    return (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()


async def find_brand_by_name(db: AsyncSession, workspace_id: uuid.UUID, name: str) -> Optional[Brand]:
    """Case-insensitive brand name lookup within a workspace."""
    rows = (await db.execute(
        select(Brand).where(Brand.workspace_id == workspace_id)
    )).scalars().all()
    name_lower = name.strip().lower()
    for b in rows:
        if b.name.lower() == name_lower:
            return b
    # Partial match fallback
    for b in rows:
        if name_lower in b.name.lower() or b.name.lower() in name_lower:
            return b
    return None
