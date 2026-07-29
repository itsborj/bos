"""PM plugin run sync helpers — PM-system agnostic.

Extracted from routers/runs.py _sync_run_to_pm, _update_pm_task_status, _pm_cfg.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.run import Run
from models.workspace import Brand

logger = logging.getLogger("bos.services.pm_sync")


def _pm_cfg(brand: Brand) -> dict:
    bj = brand.brand_json or {}
    return bj.get("pm_config") or {}


async def sync_run_to_pm(
    run: Run,
    brand: Brand,
    db: AsyncSession,
    settings,
    _is_plugin_module_active_fn=None,
    _get_module_fn=None,
    _inject_channel_credentials_fn=None,
) -> str | None:
    """Create a PM task for this run if brand has sync enabled. Returns task_id or None."""
    cfg = _pm_cfg(brand)
    if not cfg.get("sync_enabled") or not cfg.get("list_id") or not cfg.get("plugin"):
        return None
    plugin = cfg["plugin"]
    create_id = f"marketing.channel.{plugin}.tasks.create"
    try:
        if _is_plugin_module_active_fn is None or _get_module_fn is None or _inject_channel_credentials_fn is None:
            return None
        if not await _is_plugin_module_active_fn(create_id, run.brand_id, db):
            return None
        cls = _get_module_fn(create_id)
        if not cls:
            return None
        pending_status = cfg.get("status_map", {}).get("pending", "review")
        brief: dict = {
            "list_id": cfg["list_id"],
            "tasks": [{"name": f"[BOS] {run.module_id}", "description": f"Run ID: {run.id}", "status": pending_status}],
        }
        brief = await _inject_channel_credentials_fn(create_id, brief, run.brand_id, db, settings)
        _, result = cls().execute_tool_result(brief)
        created = result.get("block", {}).get("created", [])
        return created[0].get("id") if created else None
    except Exception:
        logger.exception("PM run sync (create) failed for run %s plugin=%s", run.id, plugin)
        return None


async def update_pm_task_status(
    run: Run,
    new_bos_status: str,
    brand: Brand,
    db: AsyncSession,
    settings,
    _is_plugin_module_active_fn=None,
    _get_module_fn=None,
    _inject_channel_credentials_fn=None,
) -> None:
    """Update PM task status when run approval_status changes."""
    if not run.pm_task_id:
        return
    cfg = _pm_cfg(brand)
    if not cfg.get("plugin"):
        return
    plugin = cfg["plugin"]
    new_pm_status = cfg.get("status_map", {}).get(new_bos_status, new_bos_status)
    update_id = f"marketing.channel.{plugin}.tasks.update"
    try:
        if _is_plugin_module_active_fn is None or _get_module_fn is None or _inject_channel_credentials_fn is None:
            return
        if not await _is_plugin_module_active_fn(update_id, run.brand_id, db):
            return
        cls = _get_module_fn(update_id)
        if not cls:
            return
        brief: dict = {"task_id": run.pm_task_id, "new_status": new_pm_status}
        brief = await _inject_channel_credentials_fn(update_id, brief, run.brand_id, db, settings)
        cls().execute_tool_result(brief)
    except Exception:
        logger.exception("PM task status update failed for run %s plugin=%s", run.id, plugin)
