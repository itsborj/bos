"""
Klaroha Channel Plugin Loader
------------------------------
Discovers, validates, and registers third-party channel plugins from api/plugins/.

Each plugin directory must contain a channel.json manifest. The loader:
  - Validates the manifest schema
  - Warns (never crashes) on missing platform vars
  - Registers plugin template roots with module_base
  - Tracks module_id → plugin mapping for credential injection at execution time

Credential injection (inject_channel_credentials) is called by runs.py
just before module.build_prompt(brief). Plugins never touch the DB or
settings directly — all credentials arrive via brief["_channel_credentials"].
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

log = logging.getLogger("bos.plugin_loader")

_PLUGIN_ROOT = Path(__file__).parent / "plugins"
_KLAROHA_VERSION = "3.5"

_loaded: dict[str, "_PluginState"] = {}     # plugin_id → state
_module_to_plugin: dict[str, str] = {}      # module_id → plugin_id


class ChannelPluginManifest(BaseModel):
    plugin_id: str
    name: str
    version: str
    klaroha_min_version: str = "3.4"
    capabilities_root: str = "capabilities/"
    # CMO-facing jobs this plugin can support. Internal module IDs remain
    # audit/dispatch details; product language stays at job level.
    implements: List[str] = Field(default_factory=list)
    specialty: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    connector_protocol: Optional[str] = None
    risk_policy: str = "draft_or_read_only"
    output_contracts: List[str] = Field(default_factory=list)
    requires_social_connection: List[str] = Field(default_factory=list)
    requires_platform_vars: List[str] = Field(default_factory=list)
    capability_ids: List[str] = Field(default_factory=list)


class _PluginState:
    def __init__(self, manifest: ChannelPluginManifest, root_path: Path) -> None:
        self.manifest = manifest
        self.root_path = root_path

    @property
    def capabilities_path(self) -> Path:
        return self.root_path / self.manifest.capabilities_root.rstrip("/")


def load_plugin(plugin_dir: Path) -> Optional[_PluginState]:
    """Load and validate a single plugin directory. Returns None on any failure."""
    manifest_path = plugin_dir / "channel.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path) as f:
            data = json.load(f)
        manifest = ChannelPluginManifest(**data)
    except Exception as exc:
        log.warning("Plugin at %s — manifest validation failed: %s", plugin_dir, exc)
        return None

    if manifest.klaroha_min_version > _KLAROHA_VERSION:
        log.warning(
            "Plugin %s requires Klaroha >= %s (current: %s) — skipped",
            manifest.plugin_id, manifest.klaroha_min_version, _KLAROHA_VERSION,
        )
        return None

    missing_vars = [v for v in manifest.requires_platform_vars if not os.getenv(v)]
    if missing_vars:
        log.warning(
            "Plugin %s: missing env vars %s — plugin will load but execution may fail",
            manifest.plugin_id, missing_vars,
        )

    return _PluginState(manifest, plugin_dir)


def scan_plugins() -> list[_PluginState]:
    """
    Discover all valid plugins under api/plugins/. Called once by registry._scan().
    Registers module_id → plugin_id mappings and returns plugin states so the
    registry can load each plugin's module.py files.
    """
    if not _PLUGIN_ROOT.exists():
        return []

    states: list[_PluginState] = []
    for plugin_dir in sorted(_PLUGIN_ROOT.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
            continue
        state = load_plugin(plugin_dir)
        if not state:
            continue

        _loaded[state.manifest.plugin_id] = state
        for cap_id in state.manifest.capability_ids:
            _module_to_plugin[cap_id] = state.manifest.plugin_id

        log.info(
            "Plugin loaded: %s v%s — %d capabilities",
            state.manifest.plugin_id, state.manifest.version, len(state.manifest.capability_ids),
        )
        states.append(state)

    return states


def get_plugin_for_module(module_id: str) -> Optional[_PluginState]:
    """Return the plugin state for a module, or None if module is first-party."""
    plugin_id = _module_to_plugin.get(module_id)
    return _loaded.get(plugin_id) if plugin_id else None


def get_loaded_plugins() -> dict[str, "_PluginState"]:
    return dict(_loaded)


def _plugin_provider_key(plugin_id: str) -> str:
    return f"plugin.{plugin_id}"


async def _load_db_plugin_vars(db, plugin_id: str, settings) -> dict:
    """Load DB-stored plugin vars (saved via Admin UI). Falls back to {} on any error."""
    import json as _json
    from sqlalchemy import select as _select
    from models.provider import ProviderKey as _ProviderKey
    from models.workspace import Workspace as _Workspace
    from provider_auth import decrypt_secret as _decrypt

    try:
        ws = (await db.execute(_select(_Workspace).limit(1))).scalar_one_or_none()
        if not ws:
            return {}
        row = (await db.execute(
            _select(_ProviderKey).where(
                _ProviderKey.workspace_id == ws.id,
                _ProviderKey.provider == _plugin_provider_key(plugin_id),
                _ProviderKey.auth_mode == "plugin_vars",
            )
        )).scalar_one_or_none()
        if not row:
            return {}
        return _json.loads(_decrypt(row.key_encrypted, settings))
    except Exception:
        return {}


async def get_plugin_vars(plugin_id: str, db, settings) -> dict:
    """Public: load DB-stored vars for a plugin. Returns {} on any error."""
    return await _load_db_plugin_vars(db, plugin_id, settings)


async def inject_channel_credentials(
    module_id: str,
    brief: dict,
    brand_id,           # UUID | None — passed through from runs.py
    db,                 # AsyncSession
    settings,
) -> dict:
    """
    Resolve and inject credentials for plugin modules before build_prompt is called.
    First-party modules (not in any plugin) pass through unchanged.

    Injected into brief["_channel_credentials"]:
      - For each platform in requires_social_connection: {platform}_page_token, {platform}_page_id
      - Convenience aliases "page_token" / "page_id" for the first declared platform
      - For each var in requires_platform_vars: env var value keyed by var.lower()
    """
    state = get_plugin_for_module(module_id)
    if not state:
        return brief

    manifest = state.manifest
    credentials: dict = {}

    if manifest.requires_social_connection:
        from routers.social import get_page_token

        # Auto-resolve brand when none is provided: find the first brand with a matching connection.
        resolved_brand_id = brand_id
        if not resolved_brand_id:
            from models.social import SocialConnection
            from sqlalchemy import select as _select
            for platform in manifest.requires_social_connection:
                row = (await db.execute(
                    _select(SocialConnection)
                    .where(
                        SocialConnection.platform == platform,
                        SocialConnection.status == "connected",
                    )
                    .order_by(SocialConnection.created_at.desc())
                    .limit(1)
                )).scalar_one_or_none()
                if row and row.brand_id:
                    resolved_brand_id = row.brand_id
                    break

        if resolved_brand_id:
            brand_id_str = str(resolved_brand_id)
            first = True
            for platform in manifest.requires_social_connection:
                token, page_id = await get_page_token(db, brand_id_str, platform, settings)
                if token:
                    credentials[f"{platform}_page_token"] = token
                    credentials[f"{platform}_page_id"] = page_id
                    if first:
                        credentials["page_token"] = token
                        credentials["page_id"] = page_id
                        credentials["access_token"] = token
                        first = False

            # Google Drive: surface the operator-picked root folder so storage
            # capabilities know where to write. Stored on the connection's token_meta.
            if "google_drive" in manifest.requires_social_connection:
                from models.social import SocialConnection
                from sqlalchemy import select as _select

                drive_row = (await db.execute(
                    _select(SocialConnection).where(
                        SocialConnection.brand_id == resolved_brand_id,
                        SocialConnection.platform == "google_drive",
                        SocialConnection.status == "connected",
                    ).order_by(SocialConnection.created_at.desc()).limit(1)
                )).scalar_one_or_none()
                meta = (drive_row.token_meta_json or {}) if drive_row else {}
                if meta.get("drive_root_folder_id"):
                    credentials["drive_root_folder_id"] = meta["drive_root_folder_id"]
                    credentials["drive_root_name"] = meta.get("drive_root_name")

    if manifest.requires_platform_vars or True:
        db_vars = await _load_db_plugin_vars(db, manifest.plugin_id, settings)
        # Inject all stored DB vars (required + extras like CLICKUP_TEAM_ID saved alongside token)
        for var, val in db_vars.items():
            if val:
                credentials[var.lower()] = val
        # Env var overrides take precedence for declared required vars
        for var in manifest.requires_platform_vars:
            env_val = os.getenv(var)
            if env_val:
                credentials[var.lower()] = env_val

    # Inject per-brand pm_config (team_id, list_id) so plugin modules can scope reads/writes
    if brand_id and credentials:
        try:
            from models.workspace import Brand as _Brand
            from sqlalchemy import select as _sel
            _brand = (await db.execute(_sel(_Brand).where(_Brand.id == brand_id))).scalar_one_or_none()
            if _brand:
                _pm = (_brand.brand_json or {}).get("pm_config") or {}
                if _pm.get("team_id"):
                    credentials["pm_team_id"] = _pm["team_id"]
                    credentials["clickup_team_id"] = _pm["team_id"]  # override workspace-level default
                if _pm.get("list_id"):
                    credentials["pm_list_id"] = _pm["list_id"]
        except Exception as exc:
            log.warning("inject_channel_credentials pm_config injection failed: %s", exc)

    if credentials:
        return {**brief, "_channel_credentials": credentials}
    return brief
