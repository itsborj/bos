"""
Plugin credential management — store plugin env vars in DB so users
configure connectors through the BOS admin UI rather than editing .env.

Storage: reuses provider_keys table.
  provider  = "plugin.{plugin_id}"
  auth_mode = "plugin_vars"
  key_encrypted = Fernet-encrypted JSON of all requires_platform_vars values
"""
from __future__ import annotations

import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from models.provider import ProviderKey
from plugin_loader import get_loaded_plugins, _plugin_provider_key
from registry import _ensure as _ensure_registry
from provider_auth import decrypt_secret, encrypt_secret
from routers.workspace import get_singleton

router = APIRouter(prefix="/plugins", tags=["plugins"])
log = logging.getLogger("bos.plugins")


class PluginInfo(BaseModel):
    plugin_id: str
    name: str
    version: str
    implements: list[str]
    requires_platform_vars: list[str]
    credentials_configured: bool
    missing_vars: list[str]
    credential_source: str


class SaveCredentialsRequest(BaseModel):
    vars: dict[str, str]


class ResolveWorkspacesRequest(BaseModel):
    api_token: str


async def _db_vars(db: AsyncSession, workspace_id, plugin_id: str, settings) -> dict:
    if not workspace_id:
        return {}
    row = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == workspace_id,
            ProviderKey.provider == _plugin_provider_key(plugin_id),
            ProviderKey.auth_mode == "plugin_vars",
        )
    )).scalar_one_or_none()
    if not row:
        return {}
    try:
        return json.loads(decrypt_secret(row.key_encrypted, settings))
    except Exception:
        return {}


@router.get("")
async def list_plugins(
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
    _=Depends(require_api_key),
):
    _ensure_registry()  # guarantees plugin scan has run before reading _loaded
    ws = await get_singleton(db)
    loaded = get_loaded_plugins()
    result = []

    for plugin_id, state in loaded.items():
        m = state.manifest
        db_v = await _db_vars(db, ws.id if ws else None, plugin_id, settings) if ws else {}

        missing: list[str] = []
        sources: set[str] = set()
        for var in m.requires_platform_vars:
            if os.getenv(var):
                sources.add("env_var")
            elif db_v.get(var):
                sources.add("database")
            else:
                missing.append(var)

        if not m.requires_platform_vars:
            source = "none"
        elif missing and len(missing) == len(m.requires_platform_vars):
            source = "none"
        elif missing:
            source = "partial"
        elif "database" in sources and "env_var" not in sources:
            source = "database"
        elif "env_var" in sources:
            source = "env_var"
        else:
            source = "none"

        result.append(PluginInfo(
            plugin_id=plugin_id,
            name=m.name,
            version=m.version,
            implements=m.implements,
            requires_platform_vars=m.requires_platform_vars,
            credentials_configured=not missing and bool(m.requires_platform_vars),
            missing_vars=missing,
            credential_source=source,
        ).model_dump())

    return {"plugins": result}


_WORKSPACE_RESOLVERS: dict[str, str] = {
    "channel.clickup": "https://api.clickup.com/api/v2/team",
}


@router.post("/{plugin_id}/resolve-workspaces")
async def resolve_workspaces(
    plugin_id: str,
    body: ResolveWorkspacesRequest,
    _=Depends(require_api_key),
):
    url = _WORKSPACE_RESOLVERS.get(plugin_id)
    if not url:
        raise HTTPException(status_code=404, detail=f"Workspace discovery not supported for plugin '{plugin_id}'")
    try:
        req = Request(url, headers={"Authorization": body.api_token.strip(), "Content-Type": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"ClickUp returned HTTP {exc.code} — check your API token")
    except URLError:
        raise HTTPException(status_code=502, detail="Could not reach ClickUp API")
    teams = [{"id": t["id"], "name": t["name"]} for t in data.get("teams", [])]
    return {"workspaces": teams}


@router.post("/{plugin_id}/credentials")
async def save_credentials(
    plugin_id: str,
    body: SaveCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
    _=Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    loaded = get_loaded_plugins()
    if plugin_id not in loaded:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not installed")

    manifest = loaded[plugin_id].manifest
    missing = [v for v in manifest.requires_platform_vars if not body.vars.get(v, "").strip()]
    if missing:
        raise HTTPException(status_code=400, detail={"code": "MISSING_VARS", "missing_vars": missing})

    encrypted = encrypt_secret(json.dumps(body.vars), settings)
    provider_name = _plugin_provider_key(plugin_id)

    existing = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.provider == provider_name,
        )
    )).scalar_one_or_none()

    if existing:
        existing.key_encrypted = encrypted
        existing.auth_mode = "plugin_vars"
    else:
        db.add(ProviderKey(
            workspace_id=ws.id,
            provider=provider_name,
            auth_mode="plugin_vars",
            key_encrypted=encrypted,
            metadata_json={"plugin_id": plugin_id},
        ))

    await db.commit()
    log.info("Plugin credentials saved: %s", plugin_id)
    return {"ok": True, "plugin_id": plugin_id}


@router.delete("/{plugin_id}/credentials", status_code=204)
async def delete_credentials(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    _settings=Depends(get_settings),
    _=Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return

    row = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.provider == _plugin_provider_key(plugin_id),
        )
    )).scalar_one_or_none()

    if row:
        await db.delete(row)
        await db.commit()
        log.info("Plugin credentials removed: %s", plugin_id)
