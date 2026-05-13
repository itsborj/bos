"""Recommendation generator — surfaces actionable suggestions based on run health."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.run import Run
from models.workspace import Workspace
from stream.types import defaults


async def generate(db: AsyncSession, workspace: Workspace) -> list[dict]:
    """One recommendation block if the recent pass rate is below threshold."""
    cutoff = datetime.now(UTC) - timedelta(hours=48)
    today_key = f"recommendation:{datetime.now(UTC).date()}"

    total = (
        await db.execute(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == workspace.id,
                Run.created_at >= cutoff,
            )
        )
    ).scalar_one()

    if total < 3:
        return []

    failed = (
        await db.execute(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == workspace.id,
                Run.created_at >= cutoff,
                Run.status != "success",
            )
        )
    ).scalar_one()

    fail_rate = failed / total if total else 0

    if fail_rate < 0.2:
        return []

    pct = int(fail_rate * 100)
    return [{
        "type": "recommendation",
        **defaults("recommendation"),
        "data_json": {
            "body": (
                f"{pct}% of recent outputs did not pass quality checks. "
                "Consider reviewing the active brief in the workspace — "
                "tightening product context or tone guidelines typically improves pass rates."
            ),
        },
        "source_key": today_key,
        "campaign_id": None,
    }]
