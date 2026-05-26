import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db import get_db
from memory_events import write_memory_event
from models.run import Run
from plugin_loader import get_plugin_vars

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("bos.webhooks")

# ── ClickUp handler ────────────────────────────────────────────────────────────

_CLICKUP_DONE = {"complete", "completed", "done", "closed", "resolved"}
_CLICKUP_REVISE = {"revise", "revision", "rework", "changes requested"}


def _clickup_verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower().lstrip("sha256="))


def _clickup_map_status(clickup_status: str) -> str | None:
    s = clickup_status.lower().strip()
    if s in _CLICKUP_DONE:
        return "approved"
    if s in _CLICKUP_REVISE:
        return "rejected"
    return None


async def _handle_clickup(request: Request, body: bytes, db: AsyncSession) -> dict:
    settings = get_settings()
    plugin_vars = await get_plugin_vars("channel.clickup", db, settings)
    secret = os.getenv("CLICKUP_WEBHOOK_SECRET") or plugin_vars.get("clickup_webhook_secret")
    if secret:
        sig = request.headers.get("X-Signature", "")
        if not sig or not _clickup_verify_hmac(body, sig, secret):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = payload.get("event", "")
    task_id = str(payload.get("task_id", "")).strip()

    if event == "taskStatusUpdated" and task_id:
        new_status_raw = ""
        for item in payload.get("history_items", []):
            after = item.get("after") or {}
            if isinstance(after, dict) and after.get("status"):
                new_status_raw = after["status"]
                break

        bos_status = _clickup_map_status(new_status_raw)
        if bos_status:
            run = (await db.execute(select(Run).where(Run.pm_task_id == task_id))).scalar_one_or_none()
            if run and run.approval_status != bos_status:
                run.approval_status = bos_status
                await write_memory_event(
                    db,
                    workspace_id=run.workspace_id,
                    brand_id=run.brand_id,
                    event_type="artifact_approved" if bos_status == "approved" else "artifact_dismissed",
                    topic_tags=[],
                    summary=f"PM webhook marked {run.module_id} as {bos_status}",
                    source_ref=f"run:{run.id}",
                    full_record={
                        "run_id": str(run.id),
                        "module_id": run.module_id,
                        "pm_task_id": task_id,
                        "webhook_status": new_status_raw,
                        "approval_status": bos_status,
                    },
                )
                await db.commit()
                logger.info("Webhook clickup: run %s → approval_status=%s (ClickUp: %s)", run.id, bos_status, new_status_raw)
        else:
            logger.debug("Webhook clickup: taskStatusUpdated task=%s status=%r — no BOS mapping", task_id, new_status_raw)

    return {"ok": True}


# ── Generic PM webhook dispatcher ─────────────────────────────────────────────
# Add a handler function above and register it in _HANDLERS when a new PM plugin
# is added. The plugin_id matches channel.json plugin_id (e.g. "channel.clickup").

_HANDLERS = {
    "channel.clickup": _handle_clickup,
}


@router.post("/{plugin_id}")
async def plugin_webhook(plugin_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    handler = _HANDLERS.get(plugin_id)
    if not handler:
        raise HTTPException(status_code=404, detail=f"No webhook handler registered for plugin '{plugin_id}'")
    body = await request.body()
    return await handler(request, body, db)
