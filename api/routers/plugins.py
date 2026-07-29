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

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from models.provider import ProviderKey
from models.workspace import Brand
from plugin_loader import get_loaded_plugins, get_error_plugins, required_plugin_vars, _plugin_provider_key
from registry import _ensure as _ensure_registry
from provider_auth import decrypt_secret, encrypt_secret
from routers.workspace import get_singleton
from validation import NullableUUID, parse_optional_uuid

router = APIRouter(prefix="/plugins", tags=["plugins"])
log = logging.getLogger("bos.plugins")


def _normalize_backend_provider(provider: str | None) -> str:
    value = str(provider or "").strip().lower()
    if value in {"byteplus_modelark", "byteplus", "modelark"}:
        return "bytedance"
    return value


class MediaModelOption(BaseModel):
    value: str
    label: str


class MediaProviderOption(BaseModel):
    provider: str
    label: str
    models: list[MediaModelOption]


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
    media_modality: Optional[str] = None      # "image" | "video" | None — from default_backend.modality
    connections: list[PluginConnectionInfo] = []
    supports_backend_override: bool = False   # True iff manifest has backend_override_provider slots


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


@router.get("", responses={404: {"description": "Brand not found"}})
async def list_plugins(
    brand_id: NullableUUID = Query(None),
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
    _=Depends(require_api_key),
):
    _ensure_registry()  # guarantees plugin scan has run before reading _loaded
    ws = await get_singleton(db)
    loaded = get_loaded_plugins()
    errors = get_error_plugins()
    result = []

    # C5: filter social connections by brand when provided so readiness is brand-scoped.
    # Invalid brand_id must not fall back to global readiness.
    from models.social import SocialConnection as _SC
    brand_uuid = parse_optional_uuid(brand_id, ["query", "brand_id"])
    if brand_uuid is not None:
        if not ws or not (await db.execute(select(Brand.id).where(Brand.id == brand_uuid, Brand.workspace_id == ws.id))).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Brand not found")

    _sc_query = select(_SC).where(_SC.status == "connected")
    if brand_uuid:
        _sc_query = _sc_query.where(_SC.brand_id == brand_uuid)
    social_rows = (await db.execute(_sc_query)).scalars().all()
    connected_social_platforms: set[str] = {r.platform for r in social_rows}
    social_meta_by_platform: dict[str, dict] = {
        r.platform: (r.token_meta_json or {}) for r in social_rows
    }

    # C1: read-only — load existing activation rows without writing new ones.
    # Missing rows are synthesised as installed/inactive in the response only.
    from models.plugin_activation import PluginActivation
    activation_rows = (await db.execute(select(PluginActivation))).scalars().all()

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

        social_token_platforms = {
            s.platform for s in m.credential_slots
            if s.type == "social_token" and s.platform
        }
        social_meta_slots = [
            s for s in m.credential_slots
            if s.type == "social_meta_field" and s.platform and s.field
        ]
        social_configured = social_token_platforms.issubset(connected_social_platforms)
        social_meta_configured = all(
            (social_meta_by_platform.get(s.platform) or {}).get(s.field) not in (None, "")
            for s in social_meta_slots
        )

        media_opts = [MediaProviderOption(**opt) for opt in m.provider_options]
        has_backend_override_slot = any(
            s.type == "backend_override_provider" for s in m.credential_slots
        )
        backend_provider_slots = [
            s for s in m.credential_slots
            if s.type == "backend_provider_api_key" and s.module
        ]
        backend_ok = True
        backend_sources: set[str] = set()
        if backend_provider_slots and ws:
            from provider_auth import resolve_stored_provider_credential
            from executor import get_platform_key
            from routers.backend_settings import get_db_backend_override
            from plugin_loader import get_plugin_default_backend
            from model_overrides import get_backend_override

            for slot in backend_provider_slots:
                provider_name = ""
                row = await get_db_backend_override(db, ws.id, slot.module)
                if row and row.provider:
                    provider_name = str(row.provider)
                else:
                    plugin_default = get_plugin_default_backend(slot.module)
                    env_override = get_backend_override(settings, slot.module)
                    if plugin_default and plugin_default.provider:
                        provider_name = str(plugin_default.provider)
                    elif env_override and env_override.provider:
                        provider_name = str(env_override.provider)
                provider_name = _normalize_backend_provider(provider_name)
                if not provider_name:
                    backend_ok = False
                    continue
                provider_key, _auth_mode = await resolve_stored_provider_credential(
                    db, ws.id, provider_name, settings, brand_id=brand_uuid
                )
                if provider_key:
                    backend_sources.add("database")
                    continue
                if get_platform_key(provider_name, settings):
                    backend_sources.add("env_var")
                    continue
                backend_ok = False
        elif backend_provider_slots:
            backend_ok = False

        credentials_configured = not missing and social_configured and social_meta_configured and backend_ok
        if backend_sources and cred_source == "none":
            cred_source = "database" if "database" in backend_sources and "env_var" not in backend_sources else "env_var"

        default_modality = (m.default_backend or {}).get("modality") if m.default_backend else None
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
            media_modality=default_modality if default_modality in ("image", "video") else None,
            supports_backend_override=has_backend_override_slot,
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


@router.post("/{plugin_id}/resolve-workspaces")
async def resolve_workspaces(
    plugin_id: str,
    body: ResolveWorkspacesRequest,
    _=Depends(require_api_key),
):
    # T091: URL comes from plugin manifest workspace_discovery_url, not a hardcoded dict
    loaded = get_loaded_plugins()
    if plugin_id not in loaded:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not installed")
    url = loaded[plugin_id].manifest.workspace_discovery_url
    if not url:
        raise HTTPException(status_code=404, detail=f"Workspace discovery not supported for plugin '{plugin_id}'")
    try:
        req = Request(url, headers={"Authorization": body.api_token.strip(), "Content-Type": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"Plugin returned HTTP {exc.code} — check your API token")
    except URLError:
        raise HTTPException(status_code=502, detail=f"Could not reach {url}")
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


# ── Per-brand activation ──────────────────────────────────────────────────────

class ActivateRequest(BaseModel):
    brand_id: NullableUUID = Field(
        default=None,
        description="Optional only for single-brand workspaces or explicit org-wide activation.",
    )
    # C2: org-wide activation requires explicit opt-in to prevent accidental leakage
    scope: Optional[str] = None          # must be "org" for org-wide
    confirm_org_wide: bool = False        # must be True when scope="org"


@router.post("/{plugin_id}/activate")
async def activate_plugin(
    plugin_id: str,
    body: ActivateRequest = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_api_key),
):
    """Activate a plugin for a Brand.

    brand_id is required for normal activation. Org-wide activation (brand_id
    omitted) requires scope='org' and confirm_org_wide=true to prevent
    accidental cross-brand capability leakage.
    """
    if body is None:
        body = ActivateRequest()

    # C2: block silent org-wide activation, but accept an omitted body in the
    # common single-brand workspace case so the optional schema remains true.
    if body.brand_id is None and not (body.scope == "org" and body.confirm_org_wide):
        ws = await get_singleton(db)
        brand_rows = (await db.execute(
            select(Brand.id).where(Brand.workspace_id == ws.id).limit(2)
        )).scalars().all() if ws else []
        if len(brand_rows) == 1:
            body.brand_id = str(brand_rows[0])
        else:
            raise HTTPException(
                status_code=422,
                detail=[{"loc": ["body", "brand_id"], "msg": "brand_id is required for plugin activation when the workspace has zero or multiple brands. To activate org-wide pass scope='org' and confirm_org_wide=true.", "type": "value_error"}],
            )

    loaded = get_loaded_plugins()
    if plugin_id not in loaded:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not installed")

    from models.plugin_activation import PluginActivation

    brand_uuid = parse_optional_uuid(body.brand_id, ["body", "brand_id"])
    if brand_uuid:
        ws = await get_singleton(db)
        exists = (await db.execute(
            select(Brand.id).where(Brand.id == brand_uuid, Brand.workspace_id == ws.id)
        )).scalar_one_or_none() if ws else None
        if not exists:
            raise HTTPException(status_code=404, detail="Brand not found")

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
    log.info("Plugin activated: %s (brand=%s)", plugin_id, brand_uuid or "org-level")
    return {"ok": True, "plugin_id": plugin_id, "brand_id": str(brand_uuid) if brand_uuid else None, "status": "active"}


@router.delete("/{plugin_id}/activate", status_code=204)
async def deactivate_plugin(
    plugin_id: str,
    brand_id: NullableUUID = Query(None),
    scope: Optional[str] = Query(None),
    confirm_org_wide: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_api_key),
):
    """Deactivate a plugin for a Brand (or org-wide).

    Keep an explicit inactive row so brand-specific inactive can override an
    org-level active row. Deleting would incorrectly fall back to org active.

    Org-wide deactivation (brand_id omitted) requires scope='org' and
    confirm_org_wide=true to prevent accidentally disabling all brands.
    """
    from models.plugin_activation import PluginActivation

    loaded = get_loaded_plugins()
    if plugin_id not in loaded:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not installed")

    if brand_id is None and not (scope == "org" and confirm_org_wide):
        ws = await get_singleton(db)
        brand_rows = (await db.execute(
            select(Brand.id).where(Brand.workspace_id == ws.id).limit(2)
        )).scalars().all() if ws else []
        if len(brand_rows) == 1:
            brand_id = str(brand_rows[0])
        else:
            raise HTTPException(
                status_code=422,
                detail=[{"loc": ["query", "brand_id"], "msg": "brand_id is required for plugin deactivation when the workspace has zero or multiple brands. To deactivate org-wide add scope=org&confirm_org_wide=true.", "type": "value_error"}],
            )

    brand_uuid = parse_optional_uuid(brand_id, ["query", "brand_id"])
    if brand_uuid:
        ws = await get_singleton(db)
        exists = (await db.execute(
            select(Brand.id).where(Brand.id == brand_uuid, Brand.workspace_id == ws.id)
        )).scalar_one_or_none() if ws else None
        if not exists:
            raise HTTPException(status_code=404, detail="Brand not found")

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
    brand_id: NullableUUID = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_api_key),
):
    """Return the CMO capability manifest for a given brand.

    Useful for debugging activation, SKILL.md trigger issues, and confirming
    plugin-to-CMO wiring without sending a real chat message.
    """
    from capability_manifest import build_dispatchable_manifest
    from plugin_loader import get_active_plugin_ids

    brand_uuid = parse_optional_uuid(brand_id, ["query", "brand_id"])
    active_ids = await get_active_plugin_ids(db, brand_uuid)
    entries = build_dispatchable_manifest(active_plugin_ids=active_ids)
    return {
        "brand_id": str(brand_uuid) if brand_uuid else None,
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
