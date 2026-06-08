"""
Klaroha Channel Plugin Loader
------------------------------
Discovers, validates, and registers installed channel plugins from the external
plugin root only by default:

  1. EXTERNAL_PLUGINS_DIR (env var, default /external_plugins/) — volume-mounted
     from ~/bos-plugins/. This is the operational plugin install directory.
  2. api/plugins/ is SDK/examples/deprecated bundled source. It is NOT loaded
     unless KLAROHA_LOAD_INTERNAL_PLUGINS=true is set for local compatibility.

Each plugin directory must contain a channel.json manifest. The loader:
  - Validates the manifest schema
  - Warns (never crashes) on missing platform vars or bad manifests
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
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

log = logging.getLogger("bos.plugin_loader")

_PLUGIN_ROOT = Path(__file__).parent / "plugins"
_KLAROHA_VERSION = "3.5"

# External plugin directory — volume-mounted from ~/bos-plugins/ in production.
# Override via EXTERNAL_PLUGINS_DIR env var. Bundled api/plugins are not an
# installed plugin registry; enable only for local/backward-compat testing.
_EXTERNAL_PLUGIN_ROOT: Path | None = None
_LOAD_INTERNAL_PLUGINS = os.getenv("KLAROHA_LOAD_INTERNAL_PLUGINS", "").lower() in {"1", "true", "yes"}


def _get_external_root() -> Path | None:
    global _EXTERNAL_PLUGIN_ROOT
    if _EXTERNAL_PLUGIN_ROOT is not None:
        return _EXTERNAL_PLUGIN_ROOT
    env_path = os.getenv("EXTERNAL_PLUGINS_DIR", "/external_plugins")
    p = Path(env_path)
    _EXTERNAL_PLUGIN_ROOT = p if p.exists() else None
    if _EXTERNAL_PLUGIN_ROOT:
        log.info("External plugin root: %s", _EXTERNAL_PLUGIN_ROOT)
    return _EXTERNAL_PLUGIN_ROOT

_loaded: dict[str, "_PluginState"] = {}          # plugin_id → state
_error_states: dict[str, dict] = {}              # plugin_id → {reason, path, source}
_module_to_plugin: dict[str, str] = {}           # module_id → plugin_id
_connection_to_plugin: dict[str, str] = {}       # platform → plugin_id


class PluginConnectionManifest(BaseModel):
    """Declarative connection contract owned by a plugin.

    This lets a third-party plugin expose an OAuth/API connection without adding
    platform-specific branches to core. Core only understands generic OAuth2
    mechanics and stores the resulting token as a SocialConnection.
    """

    platform: str
    type: str = "oauth2"
    auth_url: Optional[str] = None
    token_url: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    scope_separator: str = " "
    client_id_var: str = "CLIENT_ID"
    client_secret_var: str = "CLIENT_SECRET"
    redirect_uri_var: Optional[str] = None
    callback_path: Optional[str] = None
    auth_client_param: str = "client_id"
    token_client_param: str = "client_id"
    token_client_secret_param: str = "client_secret"
    authorization_params: Dict[str, Any] = Field(default_factory=dict)
    token_params: Dict[str, Any] = Field(default_factory=dict)
    userinfo_url: Optional[str] = None
    userinfo_params: Dict[str, Any] = Field(default_factory=dict)
    userinfo_headers: Dict[str, str] = Field(default_factory=dict)
    id_path: str = "id"
    name_path: str = "name"
    handle_path: Optional[str] = None
    email_path: Optional[str] = "email"
    access_token_path: str = "access_token"
    refresh_token_path: str = "refresh_token"
    expires_in_path: str = "expires_in"
    validate_capability: Optional[str] = None
    display_name: Optional[str] = None  # human label, e.g. "Google Drive"
    icon: Optional[str] = None          # emoji or short icon string, e.g. "▣"


class CredentialSlot(BaseModel):
    """Declarative credential requirement. Core resolves each slot by type;
    no platform-specific branches live in the resolver.

    Slot types:
      social_token           — full SocialConnection(brand_id, platform): injects
                               {key} + {platform}_page_token + {platform}_page_id/name/handle
      social_meta_field      — SocialConnection.token_meta_json[field]
      platform_var           — env var (var), fallback to DB-stored plugin var
      brand_json_path        — brand.brand_json at dotted path
      backend_override_provider — BackendOverride(module).provider, fallback to fallback_var env var
      backend_override_model    — BackendOverride(module).model_id
      backend_provider_api_key  — provider API key from provider_keys; second-pass slot,
                                   depends on backend_override_provider for same module
    """
    key: str
    type: str
    platform: Optional[str] = None    # social_token, social_meta_field
    field: Optional[str] = None       # social_meta_field
    var: Optional[str] = None         # platform_var
    path: Optional[str] = None        # brand_json_path
    module: Optional[str] = None      # backend_override_*, backend_provider_api_key
    fallback_var: Optional[str] = None  # backend_override_provider fallback env var


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
    credential_slots: List[CredentialSlot] = Field(default_factory=list)
    connections: List[PluginConnectionManifest] = Field(default_factory=list)
    capability_ids: List[str] = Field(default_factory=list)


def required_plugin_vars(manifest: ChannelPluginManifest) -> list[str]:
    """Return env var names that must be configured for this plugin to execute.

    Derived from platform_var credential slots plus OAuth client credentials
    declared in connection manifests. Order is stable; duplicates removed.
    """
    values: list[str] = []
    for slot in manifest.credential_slots:
        if slot.type == "platform_var" and slot.var and slot.var not in values:
            values.append(slot.var)
    for connection in manifest.connections:
        for var in (connection.client_id_var, connection.client_secret_var, connection.redirect_uri_var):
            if var and var not in values:
                values.append(var)
    return values


class _PluginState:
    def __init__(
        self,
        manifest: ChannelPluginManifest,
        root_path: Path,
        source: str = "internal",
    ) -> None:
        self.manifest = manifest
        self.root_path = root_path
        self.source = source  # "external" | "internal"

    @property
    def capabilities_path(self) -> Path:
        return self.root_path / self.manifest.capabilities_root.rstrip("/")


def load_plugin(plugin_dir: Path, source: str = "internal") -> Optional["_PluginState"]:
    """Load and validate a single plugin directory.

    Returns None on any failure. Quarantine-eligible failures (where plugin_id
    is readable) are recorded in _error_states so GET /plugins can surface them.
    """
    manifest_path = plugin_dir / "channel.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path) as f:
            raw = json.load(f)
    except Exception as exc:
        log.warning("Plugin at %s — channel.json unreadable: %s", plugin_dir, exc)
        return None

    # Extract plugin_id before full validation so the error is recoverable.
    plugin_id_raw = raw.get("plugin_id") if isinstance(raw, dict) else None

    try:
        manifest = ChannelPluginManifest(**raw)
    except Exception as exc:
        log.warning("Plugin at %s — manifest validation failed: %s", plugin_dir, exc)
        if plugin_id_raw:
            _error_states[plugin_id_raw] = {
                "reason": f"invalid_channel_json: {exc}",
                "path": str(plugin_dir),
                "source": source,
            }
        return None

    if manifest.klaroha_min_version > _KLAROHA_VERSION:
        reason = (
            f"incompatible_klaroha_version: requires >= {manifest.klaroha_min_version}"
            f" (current: {_KLAROHA_VERSION})"
        )
        log.warning("Plugin %s — %s", manifest.plugin_id, reason)
        _error_states[manifest.plugin_id] = {
            "reason": reason,
            "path": str(plugin_dir),
            "source": source,
        }
        return None

    missing_vars = [v for v in required_plugin_vars(manifest) if not os.getenv(v)]
    if missing_vars:
        log.warning(
            "Plugin %s: missing env vars %s — plugin will load but execution may fail",
            manifest.plugin_id, missing_vars,
        )

    return _PluginState(manifest, plugin_dir, source=source)


def _scan_root(root: Path, source: str) -> list[_PluginState]:
    """Scan a single plugin root directory. Quarantines bad plugins (never raises)."""
    states: list[_PluginState] = []
    for plugin_dir in sorted(root.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
            continue
        try:
            state = load_plugin(plugin_dir, source=source)
        except Exception as exc:
            log.warning("Unexpected error loading plugin at %s: %s", plugin_dir, exc)
            continue
        if not state:
            continue

        existing = _loaded.get(state.manifest.plugin_id)
        if existing:
            if existing.source == "external" and source == "internal":
                # External plugins take precedence over optional internal examples.
                log.debug("Skipping internal plugin %s — shadowed by external", state.manifest.plugin_id)
                continue
            reason = f"duplicate_plugin_id: {state.manifest.plugin_id} already loaded from {existing.root_path}"
            log.warning("Plugin %s quarantined — %s", state.manifest.plugin_id, reason)
            quarantine_plugin(state.manifest.plugin_id, reason)
            _error_states[state.manifest.plugin_id] = {
                "reason": reason,
                "path": str(state.root_path),
                "source": source,
            }
            continue

        # Quarantine if any capability_id already claimed by a different plugin
        duplicate_caps = [
            cap_id for cap_id in state.manifest.capability_ids
            if cap_id in _module_to_plugin and _module_to_plugin[cap_id] != state.manifest.plugin_id
        ]
        if duplicate_caps:
            reason = f"duplicate_module_id: {', '.join(duplicate_caps)}"
            log.warning("Plugin %s quarantined — %s", state.manifest.plugin_id, reason)
            _error_states[state.manifest.plugin_id] = {
                "reason": reason,
                "path": str(state.root_path),
                "source": source,
            }
            continue

        _loaded[state.manifest.plugin_id] = state
        for cap_id in state.manifest.capability_ids:
            _module_to_plugin[cap_id] = state.manifest.plugin_id
        for connection in state.manifest.connections:
            if connection.platform:
                _connection_to_plugin[connection.platform] = state.manifest.plugin_id

        log.info(
            "Plugin loaded [%s]: %s v%s — %d capabilities",
            source, state.manifest.plugin_id, state.manifest.version,
            len(state.manifest.capability_ids),
        )
        states.append(state)
    return states


def scan_plugins() -> list[_PluginState]:
    """
    Discover all installed plugins. Called once by registry._scan().
    External plugin root is operational truth. Bundled api/plugins are examples /
    deprecated compatibility and are skipped unless explicitly enabled.
    Registers module_id → plugin_id mappings and returns plugin states so the
    registry can load each plugin's module.py files.
    """
    states: list[_PluginState] = []

    # 1. External plugins (~/bos-plugins/ mounted at /external_plugins/)
    ext_root = _get_external_root()
    if ext_root:
        states.extend(_scan_root(ext_root, source="external"))
    else:
        log.info("No external plugin root found — external plugins disabled")

    # 2. Internal bundled plugins are NOT installed plugins. Load only when an
    # operator explicitly opts into legacy/local compatibility.
    if _LOAD_INTERNAL_PLUGINS and _PLUGIN_ROOT.exists():
        states.extend(_scan_root(_PLUGIN_ROOT, source="internal"))
    elif _PLUGIN_ROOT.exists():
        log.info("Bundled api/plugins skipped — set KLAROHA_LOAD_INTERNAL_PLUGINS=true for local compatibility")

    return states


def get_error_plugins() -> dict[str, dict]:
    """Return quarantined plugins as {plugin_id: {reason, path, source}}."""
    return dict(_error_states)


def register_plugin_module(plugin_id: str, module_id: str) -> str | None:
    """Register actual imported module ownership; return conflict reason if any."""
    existing = _module_to_plugin.get(module_id)
    if existing and existing != plugin_id:
        return f"duplicate_module_id: {module_id} already claimed by {existing}"
    _module_to_plugin[module_id] = plugin_id
    state = _loaded.get(plugin_id)
    if state and module_id not in state.manifest.capability_ids:
        state.manifest.capability_ids.append(module_id)
    return None


def quarantine_plugin(plugin_id: str, reason: str) -> None:
    """Mark a loaded plugin as quarantined and remove its dispatch mappings.

    Used when a manifest validates but later import/registration fails. The
    plugin stays visible via GET /plugins as status=error, but its capabilities
    are no longer dispatchable.
    """
    state = _loaded.pop(plugin_id, None)
    if state:
        _error_states[plugin_id] = {
            "reason": reason,
            "path": str(state.root_path),
            "source": state.source,
        }
    else:
        _error_states.setdefault(plugin_id, {"reason": reason, "path": "", "source": "unknown"})
    for module_id, owner in list(_module_to_plugin.items()):
        if owner == plugin_id:
            _module_to_plugin.pop(module_id, None)
    for platform, owner in list(_connection_to_plugin.items()):
        if owner == plugin_id:
            _connection_to_plugin.pop(platform, None)


async def get_active_plugin_ids(db, brand_id=None) -> set[str]:
    """Return set of active plugin_ids for the given brand.

    Precedence: brand-specific activation row overrides org-level row.
    Stale rows (plugin directory gone) are silently ignored.
    Returns empty set on any DB error.
    """
    try:
        from sqlalchemy import select as _select
        from models.plugin_activation import PluginActivation

        loaded_ids = set(_loaded.keys())
        if not loaded_ids:
            return set()

        # Org-level rows (brand_id IS NULL)
        org_rows = (await db.execute(
            _select(PluginActivation).where(PluginActivation.brand_id.is_(None))
        )).scalars().all()

        activation_map: dict[str, str] = {}  # plugin_id → status
        for row in org_rows:
            if row.plugin_id in loaded_ids:
                activation_map[row.plugin_id] = row.status

        # Brand-specific rows override org-level for that plugin
        if brand_id:
            brand_rows = (await db.execute(
                _select(PluginActivation).where(PluginActivation.brand_id == brand_id)
            )).scalars().all()
            for row in brand_rows:
                if row.plugin_id in loaded_ids:
                    activation_map[row.plugin_id] = row.status

        return {pid for pid, status in activation_map.items() if status == "active"}
    except Exception as exc:
        log.warning("get_active_plugin_ids failed: %s", exc)
        return set()


def get_plugin_for_module(module_id: str) -> Optional[_PluginState]:
    """Return the plugin state for a module, or None if module is first-party."""
    plugin_id = _module_to_plugin.get(module_id)
    return _loaded.get(plugin_id) if plugin_id else None


def get_loaded_plugins() -> dict[str, "_PluginState"]:
    return dict(_loaded)


def get_plugin_connection(platform: str) -> Optional[Tuple["_PluginState", PluginConnectionManifest]]:
    """Return the plugin-owned connection declaration for a platform, if any."""
    if not _loaded:
        scan_plugins()
    plugin_id = _connection_to_plugin.get(platform)
    state = _loaded.get(plugin_id) if plugin_id else None
    if not state:
        return None
    for connection in state.manifest.connections:
        if connection.platform == platform:
            return state, connection
    return None


def get_plugin_id_for_connection(platform: str) -> Optional[str]:
    found = get_plugin_connection(platform)
    return found[0].manifest.plugin_id if found else None


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


def _get_nested(d: dict, path: str):
    """Traverse a nested dict by dotted path. Returns None if any step is missing."""
    for part in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(part)
    return d


async def _resolve_slot(
    slot: CredentialSlot,
    credentials: dict,
    brand_id,
    db,
    settings,
    db_vars: dict,
    all_slots: List[CredentialSlot],
) -> None:
    """Resolve one credential slot into the credentials dict. Never raises."""
    try:
        if slot.type == "social_token":
            if not brand_id or not slot.platform:
                return
            from models.social import SocialConnection
            from routers.social import get_page_token
            from sqlalchemy import select as _select
            token, page_id = await get_page_token(db, str(brand_id), slot.platform, settings)
            if not token:
                return
            credentials[slot.key] = token
            credentials[f"{slot.platform}_page_token"] = token
            if page_id:
                credentials[f"{slot.platform}_page_id"] = page_id
            conn = (await db.execute(
                _select(SocialConnection).where(
                    SocialConnection.brand_id == brand_id,
                    SocialConnection.platform == slot.platform,
                    SocialConnection.status == "connected",
                ).order_by(SocialConnection.created_at.desc()).limit(1)
            )).scalar_one_or_none()
            if conn:
                if conn.page_name:
                    credentials[f"{slot.platform}_page_name"] = conn.page_name
                if conn.page_handle:
                    credentials[f"{slot.platform}_page_handle"] = conn.page_handle

        elif slot.type == "social_meta_field":
            if not brand_id or not slot.platform or not slot.field:
                return
            from models.social import SocialConnection
            from sqlalchemy import select as _select
            conn = (await db.execute(
                _select(SocialConnection).where(
                    SocialConnection.brand_id == brand_id,
                    SocialConnection.platform == slot.platform,
                    SocialConnection.status == "connected",
                ).order_by(SocialConnection.created_at.desc()).limit(1)
            )).scalar_one_or_none()
            if conn:
                val = (conn.token_meta_json or {}).get(slot.field)
                if val is not None:
                    credentials[slot.key] = val

        elif slot.type == "platform_var":
            if not slot.var:
                return
            val = os.getenv(slot.var) or db_vars.get(slot.var) or db_vars.get(slot.var.lower())
            if val:
                credentials[slot.key] = val

        elif slot.type == "brand_json_path":
            if not brand_id or not slot.path:
                return
            from models.workspace import Brand as _Brand
            from sqlalchemy import select as _sel
            brand = (await db.execute(_sel(_Brand).where(_Brand.id == brand_id))).scalar_one_or_none()
            if brand:
                val = _get_nested(brand.brand_json or {}, slot.path)
                if val is not None:
                    credentials[slot.key] = val

        elif slot.type == "backend_override_provider":
            if not slot.module:
                return
            try:
                from routers.backend_settings import resolve_backend_override as _rbo
                from routers.workspace import get_singleton as _get_ws
                ws = await _get_ws(db)
                if ws:
                    override = await _rbo(db, ws.id, slot.module)
                    if override and override.provider:
                        credentials[slot.key] = override.provider
                        return
            except Exception:
                pass
            if slot.fallback_var:
                val = os.getenv(slot.fallback_var)
                if val:
                    credentials[slot.key] = val

        elif slot.type == "backend_override_model":
            if not slot.module:
                return
            from routers.backend_settings import resolve_backend_override as _rbo
            from routers.workspace import get_singleton as _get_ws
            ws = await _get_ws(db)
            if ws:
                override = await _rbo(db, ws.id, slot.module)
                if override and override.model_id:
                    credentials[slot.key] = override.model_id

        elif slot.type == "backend_provider_api_key":
            # Find the provider resolved by the matching backend_override_provider slot.
            # This is a second-pass slot — must run after all other slots are resolved.
            if not slot.module:
                return
            provider_val = ""
            for s in all_slots:
                if s.type == "backend_override_provider" and s.module == slot.module:
                    provider_val = str(credentials.get(s.key) or "").lower().strip()
                    break
            if not provider_val:
                return
            from provider_auth import resolve_stored_provider_credential
            from routers.workspace import get_singleton as _get_ws
            ws = await _get_ws(db)
            if ws:
                pk, _ = await resolve_stored_provider_credential(db, ws.id, provider_val, settings)
                if pk:
                    credentials[slot.key] = pk

    except Exception as exc:
        log.warning("inject credential slot [%s/%s]: %s", slot.type, slot.key, exc)


async def inject_channel_credentials(
    module_id: str,
    brief: dict,
    brand_id,           # UUID | None — passed through from runs.py
    db,                 # AsyncSession
    settings,
) -> dict:
    """Resolve and inject credentials for plugin modules before build_prompt is called.

    Reads credential_slots from the plugin's channel.json. Each slot declares
    what it needs (type + parameters); the resolver handles retrieval generically.
    No platform-specific branches exist here — new plugins declare their own slots.

    First-party modules (not in any plugin) pass through unchanged.
    """
    state = get_plugin_for_module(module_id)
    if not state:
        return brief

    slots = state.manifest.credential_slots
    if not slots:
        return brief

    credentials: dict = {}
    db_vars = await _load_db_plugin_vars(db, state.manifest.plugin_id, settings)

    # First pass: all slot types except backend_provider_api_key
    for slot in slots:
        if slot.type != "backend_provider_api_key":
            await _resolve_slot(slot, credentials, brand_id, db, settings, db_vars, slots)

    # Second pass: backend_provider_api_key (depends on provider resolved above)
    for slot in slots:
        if slot.type == "backend_provider_api_key":
            await _resolve_slot(slot, credentials, brand_id, db, settings, db_vars, slots)

    if credentials:
        return {**brief, "_channel_credentials": credentials}
    return brief
