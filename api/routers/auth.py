import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from models.api_key import ApiKey
from models.workspace import Workspace
from routers.workspace import get_singleton
from schemas.auth import ApiKeyCreate, ApiKeyCreated, ApiKeyItem

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@router.post("/bootstrap", response_model=ApiKeyCreated, status_code=201, summary="Create the first API key (no auth required — one-time only)")
async def bootstrap(db: AsyncSession = Depends(get_db)):
    key_count = (await db.execute(select(func.count()).select_from(ApiKey))).scalar_one()
    if key_count > 0:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "BOOTSTRAP_ALREADY_DONE", "message": "An API key already exists. Use POST /auth/keys to create additional keys.", "details": None}},
        )

    ws = await get_singleton(db)
    if ws is None:
        ws = Workspace(name="My Workspace")
        db.add(ws)
        await db.flush()

    raw_key = "bos_" + secrets.token_hex(32)
    api_key = ApiKey(workspace_id=ws.id, key_hash=_hash(raw_key), label="bootstrap")
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreated(key=raw_key, key_id=api_key.id, label=api_key.label, created_at=api_key.created_at)


@router.post("/keys", response_model=ApiKeyCreated, status_code=201, summary="Create an API key")
async def create_key(
    body: ApiKeyCreate = ApiKeyCreate(),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(
            status_code=412,
            detail={
                "error": {
                    "code": "WORKSPACE_NOT_INITIALIZED",
                    "message": "Initialize workspace first: PUT /workspace/brand",
                    "details": None,
                }
            },
        )

    raw_key = "bos_" + secrets.token_hex(32)
    api_key = ApiKey(
        workspace_id=ws.id,
        key_hash=_hash(raw_key),
        label=body.label,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreated(
        key=raw_key,  # only time the raw key is returned
        key_id=api_key.id,
        label=api_key.label,
        created_at=api_key.created_at,
    )


@router.get("/keys", response_model=list[ApiKeyItem], summary="List API keys (no key values)")
async def list_keys(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return []

    rows = (
        await db.execute(
            select(ApiKey)
            .where(ApiKey.workspace_id == ws.id)
            .order_by(ApiKey.created_at.desc())
        )
    ).scalars().all()

    return [
        ApiKeyItem(
            key_id=k.id,
            label=k.label,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in rows
    ]


@router.delete("/keys/{key_id}", status_code=204, summary="Revoke an API key", responses={404: {"description": "API key not found"}})
async def delete_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    row = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.workspace_id == (ws.id if ws else None))
    )
    api_key = row.scalar_one_or_none()
    if not api_key:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "KEY_NOT_FOUND", "message": f"Key '{key_id}' not found", "details": None}},
        )
    await db.delete(api_key)
    await db.commit()
