from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from data_hygiene import contains_fuzzer_garbage
from db import get_db
from model_overrides import BackendRef, get_backend_override, parse_backend_overrides, parse_backend_ref
from models.backend import ExecutionBackendOverride
from models.provider import ProviderKey
from routers.workspace import get_singleton
from schemas.backend_settings import BackendOverrideIn, BackendOverrideListResponse, BackendOverrideOut, FallbackModel

router = APIRouter(tags=["settings"])

_TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./:-]{0,255}$")
_ALLOWED_MODALITIES = {"text", "image", "video", "data_analysis"}


def _valid_target(target: str) -> bool:
    return bool(_TARGET_RE.fullmatch(target or "")) and not contains_fuzzer_garbage(target)


def _valid_row(row: ExecutionBackendOverride) -> bool:
    values = [row.target, row.provider, row.model_id, row.tool_id, row.modality]
    if contains_fuzzer_garbage(values):
        return False
    if not _valid_target(row.target):
        return False
    if not _IDENTIFIER_RE.fullmatch(row.provider or ""):
        return False
    if row.model_id and not _MODEL_RE.fullmatch(row.model_id):
        return False
    if row.tool_id and not _MODEL_RE.fullmatch(row.tool_id):
        return False
    return row.modality in _ALLOWED_MODALITIES


def _reject_invalid_target(target: str) -> None:
    if not _valid_target(target):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["path", "target"], "msg": "target must be a module-style identifier", "type": "value_error"}],
        )


def _row_to_backendref(row: ExecutionBackendOverride) -> BackendRef:
    raw_fallbacks = row.fallbacks_json or []
    fallbacks = tuple(
        f for f in (parse_backend_ref(fb) for fb in raw_fallbacks if isinstance(fb, dict))
        if f is not None
    )
    routing_hints = row.routing_hints_json or {}
    if not isinstance(routing_hints, dict):
        routing_hints = {}
    return BackendRef(
        provider=row.provider,
        model_id=row.model_id,
        tool_id=row.tool_id,
        modality=row.modality,
        strict=row.strict,
        fallbacks=fallbacks,
        routing_hints=routing_hints,
    )


def _row_to_out(row: ExecutionBackendOverride) -> BackendOverrideOut:
    raw_fallbacks = row.fallbacks_json or []
    fallbacks = [
        FallbackModel(provider=fb["provider"], model_id=fb.get("model_id"), tool_id=fb.get("tool_id"), routing_hints=fb.get("routing_hints") or {})
        for fb in raw_fallbacks
        if isinstance(fb, dict) and fb.get("provider")
    ]
    return BackendOverrideOut(
        target=row.target,
        provider=row.provider,
        model_id=row.model_id,
        tool_id=row.tool_id,
        modality=row.modality,
        strict=row.strict,
        fallbacks=fallbacks,
        routing_hints=row.routing_hints_json or {},
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


async def _provider_is_unavailable(db: AsyncSession, workspace_id, provider: str) -> bool:
    row = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == workspace_id,
            ProviderKey.brand_id == None,  # noqa: E711
            ProviderKey.provider == provider,
        )
    )).scalar_one_or_none()
    if not row:
        return False
    expires_at = row.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= datetime.now(timezone.utc):
        return True
    metadata = row.metadata_json or {}
    return isinstance(metadata, dict) and metadata.get("last_check_status") == "error"


async def resolve_backend_override(db: AsyncSession, workspace_id, target: str) -> BackendRef | None:
    # 1. Admin DB override (highest precedence)
    row = await get_db_backend_override(db, workspace_id, target)
    if row:
        if await _provider_is_unavailable(db, workspace_id, row.provider):
            return None
        return _row_to_backendref(row)

    # 2. channel.json default_backend (plugin-declared preference)
    from plugin_loader import get_plugin_default_backend
    plugin_default = get_plugin_default_backend(target)
    if plugin_default:
        if await _provider_is_unavailable(db, workspace_id, plugin_default.provider):
            return None
        return plugin_default

    # 3. Env var override (lowest explicit precedence)
    ref = get_backend_override(get_settings(), target)
    if ref and await _provider_is_unavailable(db, workspace_id, ref.provider):
        return None
    return ref


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
    outputs = [_row_to_out(row) for row in rows if _valid_row(row)]

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
            fallbacks=[
                FallbackModel(provider=f.provider, model_id=f.model_id, tool_id=f.tool_id, routing_hints=f.routing_hints)
                for f in ref.fallbacks
            ],
            routing_hints=ref.routing_hints,
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
    _reject_invalid_target(target)
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    fallbacks_json = [
        {"provider": f.provider, "model_id": f.model_id, "tool_id": f.tool_id, "routing_hints": f.routing_hints}
        for f in body.fallbacks
    ]

    row = await get_db_backend_override(db, ws.id, target)
    if row:
        row.provider = body.provider
        row.model_id = body.model_id
        row.tool_id = body.tool_id
        row.modality = body.modality
        row.strict = body.strict
        row.fallbacks_json = fallbacks_json
        row.routing_hints_json = body.routing_hints
    else:
        row = ExecutionBackendOverride(
            workspace_id=ws.id,
            target=target,
            provider=body.provider,
            model_id=body.model_id,
            tool_id=body.tool_id,
            modality=body.modality,
            strict=body.strict,
            fallbacks_json=fallbacks_json,
            routing_hints_json=body.routing_hints,
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
    _reject_invalid_target(target)
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    row = await get_db_backend_override(db, ws.id, target)
    if row:
        await db.delete(row)
        await db.commit()
    return None
