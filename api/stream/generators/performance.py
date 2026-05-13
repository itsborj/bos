"""Performance generator — assembles a metrics table from the last 24 hours of runs."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.run import Run, RunAttempt, RunResult
from models.workspace import Workspace
from stream.types import defaults


async def generate(db: AsyncSession, workspace: Workspace) -> list[dict]:
    """One performance table block summarising run activity in the last 24 hours."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    today_key = f"performance:{datetime.now(UTC).date()}"

    # Total runs
    total_runs = (
        await db.execute(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == workspace.id,
                Run.created_at >= cutoff,
            )
        )
    ).scalar_one()

    if total_runs == 0:
        return []

    # Success / fail counts
    success_count = (
        await db.execute(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == workspace.id,
                Run.created_at >= cutoff,
                Run.status == "success",
            )
        )
    ).scalar_one()

    # Provider cost total
    cost_row = await db.execute(
        select(func.sum(RunAttempt.provider_cost))
        .join(Run, RunAttempt.run_id == Run.id)
        .where(
            Run.workspace_id == workspace.id,
            Run.created_at >= cutoff,
            RunAttempt.provider_cost.is_not(None),
        )
    )
    total_cost = cost_row.scalar_one() or 0.0

    pass_rate = f"{int(success_count / total_runs * 100)}%" if total_runs else "N/A"

    rows = [
        {"label": "Runs completed", "value": str(total_runs)},
        {"label": "Pass rate", "value": pass_rate},
        {"label": "Provider cost", "value": f"${total_cost:.4f}"},
    ]

    return [{
        "type": "performance",
        **defaults("performance"),
        "data_json": {
            "title": "Last 24 hours",
            "rows": rows,
        },
        "source_key": today_key,
        "campaign_id": None,
    }]
