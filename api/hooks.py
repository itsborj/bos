"""
BOS hook dispatcher — minimal filter + action hook system.

Plugins declare hook subscriptions in channel.json. Core fires hooks at named
pipeline boundaries. Plugins react without modifying core files.

Published hooks
───────────────
  brief.before_dispatch  (filter) — enrich brief before module execution.
      Signature: async (brief: dict, ctx: HookContext) -> dict
      Fires after credential injection and upstream hydration, before execute().

  run.after_complete     (action) — react to a successful committed run.
      Signature: async (ctx: HookContext) -> None
      ctx.run_id and ctx.result are populated. Fires after db.commit().

Hook contract
─────────────
  • Adding a new hook: add a fire call in the pipeline; document it above.
  • Renaming or removing a hook is a breaking change — same deprecation policy
    as brief fields and ChannelPluginManifest schema fields.
  • A subscriber failure is logged and skipped. It never aborts the pipeline.
  • Filter hooks are called in priority order (lower = earlier, default 10).
"""
from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import UUID

log = logging.getLogger(__name__)

# ── Published hook names ───────────────────────────────────────────────────────

BRIEF_BEFORE_DISPATCH = "brief.before_dispatch"
RUN_AFTER_COMPLETE = "run.after_complete"


# ── Context passed to every handler ───────────────────────────────────────────

@dataclass
class HookContext:
    """Carry-all context passed to every hook handler.

    db, ws, and settings are typed Any to avoid importing BOS internals here.
    Handlers that need typed access cast them at use.
    """
    module_id: str
    brand_id: Optional[UUID]
    db: Any        # sqlalchemy.ext.asyncio.AsyncSession
    ws: Any        # models.workspace.Workspace
    settings: Any
    run_id: Optional[UUID] = None
    result: Optional[dict] = None   # populated for run.after_complete


# ── Registry ──────────────────────────────────────────────────────────────────

@dataclass
class _Subscription:
    plugin_id: str
    hook: str
    handler_fn: Callable
    applies_to: list[str]   # empty = applies to all module_ids
    priority: int


class HookRegistry:
    """Stores and dispatches plugin hook subscriptions.

    Two types:
      fire_filter — each subscriber receives and returns (modified) data.
      fire_action — each subscriber receives context; return value ignored.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[_Subscription]] = {}

    def register(
        self,
        plugin_id: str,
        hook: str,
        handler_fn: Callable,
        applies_to: list[str],
        priority: int = 10,
    ) -> None:
        bucket = self._subs.setdefault(hook, [])
        bucket.append(_Subscription(plugin_id, hook, handler_fn, applies_to, priority))
        bucket.sort(key=lambda s: s.priority)
        log.debug(
            "Hook registered: [%s] plugin=%s applies_to=%s",
            hook, plugin_id, applies_to or "*",
        )

    def deregister_plugin(self, plugin_id: str) -> None:
        """Remove all subscriptions for a deactivated or quarantined plugin."""
        for hook in list(self._subs):
            self._subs[hook] = [s for s in self._subs[hook] if s.plugin_id != plugin_id]

    def subscriber_count(self, hook: str) -> int:
        return len(self._subs.get(hook, []))

    async def fire_filter(self, hook: str, data: dict, ctx: HookContext) -> dict:
        """Fire a filter hook. Each subscriber may modify and return data.
        Filter failures are not hidden: before-dispatch enrichment failures must
        surface to the caller instead of silently rendering with stale context.
        """
        for sub in self._subs.get(hook, []):
            if sub.applies_to and ctx.module_id not in sub.applies_to:
                continue
            try:
                data = await sub.handler_fn(data, ctx)
            except Exception:
                log.exception("Hook [%s] subscriber plugin=%s raised", hook, sub.plugin_id)
                raise
        return data

    async def fire_action(self, hook: str, ctx: HookContext) -> None:
        """Fire an action hook. Return values are ignored.
        Failures are logged and skipped — the pipeline is never aborted."""
        for sub in self._subs.get(hook, []):
            if sub.applies_to and ctx.module_id not in sub.applies_to:
                continue
            try:
                await sub.handler_fn(ctx)
            except Exception as exc:
                log.warning(
                    "Hook [%s] subscriber plugin=%s raised: %s", hook, sub.plugin_id, exc
                )


_registry = HookRegistry()


def get_registry() -> HookRegistry:
    """Return the process-level hook registry singleton."""
    return _registry


# ── Handler loading ───────────────────────────────────────────────────────────

def _load_handler(plugin_dir: Path, handler_path: str) -> Optional[Callable]:
    """Load a callable from a plugin directory using a dotted path.

    handler_path format: "module_name.function_name"
    e.g. "hooks.on_brief_before_dispatch"
      → loads <plugin_dir>/hooks.py, returns on_brief_before_dispatch.

    Supports one level of subdirectory:
    e.g. "capabilities/my_cap/hooks.on_brief_before_dispatch"
      → loads <plugin_dir>/capabilities/my_cap/hooks.py
    """
    parts = handler_path.rsplit(".", 1)
    if len(parts) != 2:
        log.warning(
            "Invalid hook handler path (expected 'module.function'): %s", handler_path
        )
        return None
    module_rel, fn_name = parts
    py_path = plugin_dir / f"{module_rel.replace('.', '/')}.py"
    if not py_path.exists():
        log.warning("Hook handler module not found: %s", py_path)
        return None
    spec = importlib.util.spec_from_file_location(
        f"_bos_hook_{plugin_dir.name}_{module_rel.replace('/', '_')}", py_path
    )
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        log.warning("Failed to import hook module %s: %s", py_path, exc)
        return None
    fn = getattr(mod, fn_name, None)
    if fn is None:
        log.warning("Hook handler '%s' not found in %s", fn_name, py_path)
    return fn


def register_plugin_hooks(plugin_id: str, plugin_dir: Path, subscriptions: list[dict]) -> None:
    """Called by plugin_loader during scan. Registers all declared hook subscriptions.

    Each subscription dict may contain:
      hook       (required) — hook name, e.g. "brief.before_dispatch"
      handler    (required) — dotted path, e.g. "hooks.on_brief_before_dispatch"
      applies_to (optional) — list of module_ids; empty = applies to all
      priority   (optional) — int, default 10 (lower fires first)
    """
    for sub in subscriptions:
        hook = sub.get("hook", "")
        handler_path = sub.get("handler", "")
        applies_to: list[str] = sub.get("applies_to") or []
        priority = int(sub.get("priority", 10))

        if not hook or not handler_path:
            log.warning(
                "Plugin %s: hook subscription missing 'hook' or 'handler' — skipped",
                plugin_id,
            )
            continue

        fn = _load_handler(plugin_dir, handler_path)
        if fn is None:
            log.warning(
                "Plugin %s: could not load hook handler '%s' — skipped",
                plugin_id, handler_path,
            )
            continue

        _registry.register(plugin_id, hook, fn, applies_to, priority)
