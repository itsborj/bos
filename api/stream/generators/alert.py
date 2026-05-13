"""Alert generator — surfaces failed module runs as decisions needed in the Stream."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.run import Run, RunResult
from models.workspace import Workspace
from stream.types import defaults


async def generate(db: AsyncSession, workspace: Workspace) -> list[dict]:
    """One alert block per failed run in the last 24 hours (not yet dismissed)."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    rows = await db.execute(
        select(Run, RunResult)
        .join(RunResult, RunResult.run_id == Run.id)
        .where(
            Run.workspace_id == workspace.id,
            Run.created_at >= cutoff,
            RunResult.self_check_verdict != "pass",
        )
        .order_by(Run.created_at.desc())
        .limit(5)
    )

    blocks = []
    for run, result in rows.all():
        module_label = run.module_id.replace(".", " ").replace("_", " ").title()
        blocks.append({
            "type": "alert",
            **defaults("alert"),
            "data_json": {
                "headline": f"{module_label} failed quality check",
                "body": (
                    f"Self-check verdict: {result.self_check_verdict}. "
                    "Should I adjust the brief and retry?"
                ),
                "action": {"label": "Tell CMO →", "target": "cmo"},
            },
            "source_key": f"alert:run:{run.id}",
            "campaign_id": None,
        })

    return blocks
