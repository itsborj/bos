"""Narrative generator — LLM-authored or templated organizational update."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.run import Run
from models.workspace import Workspace
from stream.types import defaults

logger = logging.getLogger("bos.stream.narrative")


async def generate(db: AsyncSession, workspace: Workspace, openrouter_key: str = "") -> list[dict]:
    """One narrative block summarising recent activity in an organizational voice."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    today_key = f"narrative:{datetime.now(UTC).date()}"

    total = (
        await db.execute(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == workspace.id,
                Run.created_at >= cutoff,
            )
        )
    ).scalar_one()

    if total == 0:
        return []

    success = (
        await db.execute(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == workspace.id,
                Run.created_at >= cutoff,
                Run.status == "success",
            )
        )
    ).scalar_one()

    module_rows = await db.execute(
        select(Run.module_id).where(
            Run.workspace_id == workspace.id,
            Run.created_at >= cutoff,
        ).distinct()
    )
    modules = [r[0] for r in module_rows.all()]
    module_labels = [m.split(".")[-1].replace("_", " ") for m in modules]

    body = await _generate_text(workspace.name, total, success, module_labels, openrouter_key)

    return [{
        "type": "narrative",
        **defaults("narrative"),
        "data_json": {"body": body},
        "source_key": today_key,
        "campaign_id": None,
    }]


async def _generate_text(
    workspace_name: str,
    total: int,
    success: int,
    module_labels: list[str],
    openrouter_key: str,
) -> str:
    if openrouter_key:
        try:
            return await _llm_text(workspace_name, total, success, module_labels, openrouter_key)
        except Exception as exc:
            logger.warning("LLM narrative generation failed, using template: %s", exc)

    # Template fallback
    pass_rate = int(success / total * 100) if total else 0
    activity = ", ".join(module_labels[:3]) if module_labels else "content"
    if pass_rate >= 90:
        tone = "performing well"
    elif pass_rate >= 70:
        tone = "on track"
    else:
        tone = "flagging a few items for review"
    return (
        f"{workspace_name} ran {total} content outputs today — {pass_rate}% passed quality checks. "
        f"Active work: {activity}. {tone.capitalize()}."
    )


async def _llm_text(
    workspace_name: str,
    total: int,
    success: int,
    module_labels: list[str],
    openrouter_key: str,
) -> str:
    from providers.openrouter import OpenRouterAdapter

    adapter = OpenRouterAdapter(openrouter_key)
    activity = ", ".join(module_labels[:3]) if module_labels else "content production"
    prompt = (
        f"You are the CMO reporting to the CEO.\n\n"
        f"Workspace: {workspace_name}\n"
        f"Last 24 hours: {total} outputs generated, {success} passed quality checks.\n"
        f"Active areas: {activity}.\n\n"
        "Write a 2-sentence organizational update in a professional but conversational tone. "
        "Focus on business outcomes. Never mention: modules, providers, API calls, or technical infrastructure."
    )
    response = await adapter.complete(prompt, "openai/gpt-4o-mini")
    return response.content.strip()
