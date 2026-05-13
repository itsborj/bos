from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from model_overrides import get_backend_override, parse_backend_overrides
from models.backend import ExecutionBackendOverride
from routers.workspace import get_singleton
from schemas.backend_settings import BackendOverrideIn, BackendOverrideListResponse, BackendOverrideOut

router = APIRouter(tags=["settings"])


def _row_to_out(row: ExecutionBackendOverride) -> BackendOverrideOut:
    return BackendOverrideOut(
        target=row.target,
        provider=row.provider,
        model_id=row.model_id,
        tool_id=row.tool_id,
        modality=row.modality,
        strict=row.strict,
        source="db",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def get_db_backend_override(db: AsyncSession, workspace_id, target: str):
    return (
        await db.execute(
            select(ExecutionBackendOverride).where(
                ExecutionBackendOverride.workspace_id == workspace_id,
                ExecutionBackendOverride.target == target,
            )
        )
    ).scalar_one_or_none()


async def resolve_backend_override(db: AsyncSession, workspace_id, target: str):
    row = await get_db_backend_override(db, workspace_id, target)
    if row:
        return row
    return get_backend_override(get_settings(), target)


@router.get("/settings/backends", response_model=BackendOverrideListResponse, summary="List execution backend overrides")
async def list_backend_overrides(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    rows = (
        await db.execute(
            select(ExecutionBackendOverride)
            .where(ExecutionBackendOverride.workspace_id == ws.id)
            .order_by(ExecutionBackendOverride.target.asc())
        )
    ).scalars().all()
    outputs = [_row_to_out(row) for row in rows]

    env_overrides = parse_backend_overrides(getattr(get_settings(), "execution_backend_overrides", ""))
    db_targets = {out.target for out in outputs}
    for target, ref in sorted(env_overrides.items()):
        if target in db_targets:
            continue
        outputs.append(BackendOverrideOut(
            target=target,
            provider=ref.provider,
            model_id=ref.model_id,
            tool_id=ref.tool_id,
            modality=ref.modality,
            strict=ref.strict if ref.strict is not None else True,
            source="env",
        ))

    return BackendOverrideListResponse(overrides=outputs)


@router.put("/settings/backends/{target:path}", response_model=BackendOverrideOut, summary="Set execution backend override")
async def put_backend_override(
    target: str,
    body: BackendOverrideIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    row = await get_db_backend_override(db, ws.id, target)
    if row:
        row.provider = body.provider
        row.model_id = body.model_id
        row.tool_id = body.tool_id
        row.modality = body.modality
        row.strict = body.strict
    else:
        row = ExecutionBackendOverride(
            workspace_id=ws.id,
            target=target,
            provider=body.provider,
            model_id=body.model_id,
            tool_id=body.tool_id,
            modality=body.modality,
            strict=body.strict,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)
    return _row_to_out(row)


@router.delete("/settings/backends/{target:path}", status_code=204, summary="Delete execution backend override")
async def delete_backend_override(
    target: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    row = await get_db_backend_override(db, ws.id, target)
    if row:
        await db.delete(row)
        await db.commit()
    return None
