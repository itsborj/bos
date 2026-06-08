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
from typing import Optional
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
from plugin_loader import get_loaded_plugins, get_error_plugins, required_plugin_vars, _plugin_provider_key
from registry import _ensure as _ensure_registry
from provider_auth import decrypt_secret, encrypt_secret
from routers.workspace import get_singleton

router = APIRouter(prefix="/plugins", tags=["plugins"])
log = logging.getLogger("bos.plugins")


class MediaModelOption(BaseModel):
    value: str
    label: str


class MediaProviderOption(BaseModel):
    provider: str
    label: str
    models: list[MediaModelOption]


# Supported providers per media plugin — single source of truth.
# Keys match plugin_id. Order determines display order in the UI.
_MEDIA_PROVIDER_OPTIONS: dict[str, list[dict]] = {
    "media.image": [
        {
            "provider": "openai",
            "label": "OpenAI",
            "models": [
                {"value": "gpt-image-2", "label": "gpt-image-2 — flagship (2026)"},
                {"value": "gpt-image-1", "label": "gpt-image-1 — deprecating Oct 2026"},
                {"value": "gpt-image-1-mini", "label": "gpt-image-1-mini — cheapest"},
            ],
        },
        {
            "provider": "gemini",
            "label": "Google Gemini",
            "models": [
                {"value": "gemini-2.5-flash-image", "label": "Gemini 2.5 Flash Image"},
                {"value": "imagen-4.0-generate-001", "label": "Imagen 4.0 — paid Gemini plan"},
            ],
        },
        {
            "provider": "bytedance",
            "label": "ByteDance ModelArk",
            "models": [
                {"value": "seedream-4-0-250828", "label": "Seedream 4.0"},
                {"value": "seedream-4-5-251128", "label": "Seedream 4.5"},
                {"value": "seedream-5-0-260128", "label": "Seedream 5.0"},
            ],
        },
        {
            "provider": "local",
            "label": "Local Sample Renderer",
            "models": [
                {"value": "local-sample-renderer", "label": "Local sample PNG renderer"},
            ],
        },
        {
            "provider": "custom",
            "label": "Custom Worker",
            "models": [],
        },
    ],
    "media.video": [
        {
            "provider": "local_ffmpeg",
            "label": "Local FFmpeg",
            "models": [],
        },
        {
            "provider": "gemini",
            "label": "Google Gemini (Veo)",
            "models": [
                {"value": "veo-3.0-generate-001", "label": "Veo 3.0 — preview"},
                {"value": "veo-2.0-generate-001", "label": "Veo 2.0"},
            ],
        },
        {
            "provider": "seedance",
            "label": "Seedance",
            "models": [
                {"value": "seedance-1-lite", "label": "Seedance 1 Lite"},
                {"value": "seedance-1-pro", "label": "Seedance 1 Pro"},
            ],
        },
        {
            "provider": "custom",
            "label": "Custom Provider",
            "models": [],
        },
    ],
}


class PluginConnectionInfo(BaseModel):
    platform: str
    type: str = "oauth2"
    scopes: list[str] = []
    client_id_var: Optional[str] = None
    client_secret_var: Optional[str] = None
    redirect_uri_var: Optional[str] = None
    validate_capability: Optional[str] = None
    display_name: Optional[str] = None
    icon: Optional[str] = None


class ActivationState(BaseModel):
    brand_id: Optional[str]  # None = org-level
    status: str
    error_reason: Optional[str] = None


class PluginInfo(BaseModel):
    plugin_id: str
    name: str
    version: str
    source: str = "external"              # "external" | "internal"
    status: str = "installed"             # "installed" | "error"
    reason: Optional[str] = None
    capability_ids: list[str] = []
    implements: list[str] = []
    requires_platform_vars: list[str] = []    # derived from platform_var credential_slots
    requires_social_connection: list[str] = []  # derived from social_token credential_slots
    credentials_configured: bool = False
    missing_vars: list[str] = []
    credential_source: str = "none"
    activation_by_brand: list[ActivationState] = []
    media_provider_options: list[MediaProviderOption] = []
    connections: list[PluginConnectionInfo] = []


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
    errors = get_error_plugins()
    result = []

    # Preload connected social platforms across all brands (display-level, not security gate)
    from models.social import SocialConnection as _SC
    connected_social_platforms: set[str] = set(
        (await db.execute(select(_SC.platform).where(_SC.status == "connected"))).scalars().all()
    )

    # Load activation rows for all plugins in one query
    from models.plugin_activation import PluginActivation
    activation_rows = (await db.execute(select(PluginActivation))).scalars().all()

    # D4: directory present + no activation row means installed/inactive. Persist
    # an org-level inactive row so Admin can show explicit lifecycle state.
    existing_keys = {(row.plugin_id, str(row.brand_id) if row.brand_id else None) for row in activation_rows}
    for plugin_id in list(loaded.keys()):
        if (plugin_id, None) not in existing_keys:
            row = PluginActivation(plugin_id=plugin_id, brand_id=None, status="inactive")
            db.add(row)
            activation_rows.append(row)
    if any((pid, None) not in existing_keys for pid in loaded.keys()):
        await db.commit()

    activation_by_plugin: dict[str, list[ActivationState]] = {}
    for row in activation_rows:
        activation_by_plugin.setdefault(row.plugin_id, []).append(
            ActivationState(
                brand_id=str(row.brand_id) if row.brand_id else None,
                status=row.status,
                error_reason=row.error_reason,
            )
        )

    for plugin_id, state in loaded.items():
        m = state.manifest
        db_v = await _db_vars(db, ws.id if ws else None, plugin_id, settings) if ws else {}

        required_vars = required_plugin_vars(m)
        missing: list[str] = []
        sources: set[str] = set()
        for var in required_vars:
            if os.getenv(var):
                sources.add("env_var")
            elif db_v.get(var):
                sources.add("database")
            else:
                missing.append(var)

        if not required_vars:
            cred_source = "none"
        elif missing and len(missing) == len(required_vars):
            cred_source = "none"
        elif missing:
            cred_source = "partial"
        elif "database" in sources and "env_var" not in sources:
            cred_source = "database"
        elif "env_var" in sources:
            cred_source = "env_var"
        else:
            cred_source = "none"

        # T100/T101: credentials_configured covers three slot types:
        # - platform_var: missing[] must be empty
        # - social_token: at least one declared platform must have a connected SocialConnection
        # - backend_override_*/backend_provider_api_key: treated as configured when no platform_var
        #   vars are missing (backend overrides are set via Admin → AI Providers, not this check)
        social_token_platforms = {
            s.platform for s in m.credential_slots
            if s.type == "social_token" and s.platform
        }
        social_configured = (
            not social_token_platforms
            or bool(social_token_platforms & connected_social_platforms)
        )
        credentials_configured = not missing and social_configured

        media_opts = [
            MediaProviderOption(**opt)
            for opt in _MEDIA_PROVIDER_OPTIONS.get(plugin_id, [])
        ]
        result.append(PluginInfo(
            plugin_id=plugin_id,
            name=m.name,
            version=m.version,
            source=state.source,
            status="installed",
            capability_ids=m.capability_ids,
            implements=m.implements,
            requires_platform_vars=required_vars,
            requires_social_connection=sorted(social_token_platforms),
            credentials_configured=credentials_configured,
            missing_vars=missing,
            credential_source=cred_source,
            activation_by_brand=activation_by_plugin.get(plugin_id, []),
            media_provider_options=media_opts,
            connections=[
                PluginConnectionInfo(
                    platform=c.platform,
                    type=c.type,
                    scopes=c.scopes,
                    client_id_var=c.client_id_var,
                    client_secret_var=c.client_secret_var,
                    redirect_uri_var=c.redirect_uri_var,
                    validate_capability=c.validate_capability,
                    display_name=c.display_name,
                    icon=c.icon,
                ) for c in m.connections
            ],
        ).model_dump())

    # Surface quarantined plugins so Admin can see what failed and why
    for plugin_id, err in errors.items():
        result.append(PluginInfo(
            plugin_id=plugin_id,
            name=plugin_id,
            version="unknown",
            source=err.get("source", "unknown"),
            status="error",
            reason=err.get("reason"),
            activation_by_brand=activation_by_plugin.get(plugin_id, []),
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
    required_vars = required_plugin_vars(manifest)
    missing = [v for v in required_vars if not body.vars.get(v, "").strip()]
    if missing:
        raise HTTPException(status_code=400, detail={"code": "MISSING_VARS", "missing_vars": missing})

    clean_vars = {k: v for k, v in body.vars.items() if str(v).strip()}
    encrypted = encrypt_secret(json.dumps(clean_vars), settings)
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


# ── D4: Per-brand activation ──────────────────────────────────────────────────

class ActivateRequest(BaseModel):
    brand_id: Optional[str] = None  # None = org-level activation


@router.post("/{plugin_id}/activate")
async def activate_plugin(
    plugin_id: str,
    body: ActivateRequest = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_api_key),
):
    """Activate a plugin for a Brand (or org-wide when brand_id is omitted).

    Directory present + no row → installed/inactive by default.
    This endpoint creates or flips the activation row to status='active'.
    """
    if body is None:
        body = ActivateRequest()

    loaded = get_loaded_plugins()
    if plugin_id not in loaded:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not installed")

    from models.plugin_activation import PluginActivation
    import uuid as _uuid

    brand_uuid = _uuid.UUID(body.brand_id) if body.brand_id else None

    existing = (await db.execute(
        select(PluginActivation).where(
            PluginActivation.plugin_id == plugin_id,
            PluginActivation.brand_id == brand_uuid,
        )
    )).scalar_one_or_none()

    if existing:
        existing.status = "active"
        existing.error_reason = None
    else:
        db.add(PluginActivation(
            plugin_id=plugin_id,
            brand_id=brand_uuid,
            status="active",
        ))

    await db.commit()
    log.info("Plugin activated: %s (brand=%s)", plugin_id, body.brand_id or "org-level")
    return {"ok": True, "plugin_id": plugin_id, "brand_id": body.brand_id, "status": "active"}


@router.delete("/{plugin_id}/activate", status_code=204)
async def deactivate_plugin(
    plugin_id: str,
    brand_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_api_key),
):
    """Deactivate a plugin for a Brand (or org-wide).

    Keep an explicit inactive row so brand-specific inactive can override an
    org-level active row. Deleting would incorrectly fall back to org active.
    """
    from models.plugin_activation import PluginActivation
    import uuid as _uuid

    loaded = get_loaded_plugins()
    if plugin_id not in loaded:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not installed")

    brand_uuid = _uuid.UUID(brand_id) if brand_id else None

    row = (await db.execute(
        select(PluginActivation).where(
            PluginActivation.plugin_id == plugin_id,
            PluginActivation.brand_id == brand_uuid,
        )
    )).scalar_one_or_none()

    if row:
        row.status = "inactive"
        row.error_reason = None
    else:
        db.add(PluginActivation(plugin_id=plugin_id, brand_id=brand_uuid, status="inactive"))
    await db.commit()
    log.info("Plugin deactivated: %s (brand=%s)", plugin_id, brand_id or "org-level")


# ── T102: Read-only capability manifest endpoint ──────────────────────────────

capability_manifest_router = APIRouter(prefix="/capability-manifest", tags=["capability-manifest"])


@capability_manifest_router.get("")
async def get_capability_manifest(
    brand_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_api_key),
):
    """Return the CMO capability manifest for a given brand.

    Useful for debugging activation, SKILL.md trigger issues, and confirming
    plugin-to-CMO wiring without sending a real chat message.
    """
    from capability_manifest import build_dispatchable_manifest
    from plugin_loader import get_active_plugin_ids

    active_ids = await get_active_plugin_ids(db, brand_id)
    entries = build_dispatchable_manifest(active_plugin_ids=active_ids)
    return {
        "brand_id": brand_id,
        "capabilities": [
            {
                "module_id": e.module_id,
                "label": e.label,
                "description": e.description,
                "triggers": list(e.triggers),
                "allowed_from_chat": True,
            }
            for e in entries
        ],
    }
