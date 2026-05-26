"""Outcome Stream cards from manual OutcomeRecords."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.outcome import OutcomeRecord
from models.workspace import Workspace
from stream.types import defaults


async def generate(db: AsyncSession, workspace: Workspace) -> list[dict]:
    rows = (
        await db.execute(
            select(OutcomeRecord)
            .where(OutcomeRecord.workspace_id == workspace.id)
            .order_by(OutcomeRecord.recorded_at.desc())
            .limit(20)
        )
    ).scalars().all()

    blocks: list[dict] = []
    for outcome in rows:
        d = defaults("outcome")
        metrics = outcome.metrics_json or {}
        blocks.append(
            {
                "type": "outcome",
                "layout_hint": d["layout_hint"],
                "interaction": d["interaction"],
                "priority": "normal",
                "campaign_id": None,
                "source_key": f"outcome:{outcome.id}",
                "data_json": {
                    "card_type": "outcome",
                    "objective_ref": str(outcome.objective_id) if outcome.objective_id else None,
                    "brand_ref": str(outcome.brand_id) if outcome.brand_id else None,
                    "why_now": "An outcome was recorded and BOS memory was updated.",
                    "confidence": outcome.confidence_source,
                    "primary_evidence": _primary_evidence(metrics),
                    "recommended_next": "Use this learning in the next DecisionBrief.",
                    "approval_boundary": "No external action was taken. This card records learning only.",
                    "allowed_actions": ["ask CMO", "dismiss"],
                    "source_state": outcome.source_ref or outcome.confidence_source,
                    "summary": outcome.summary,
                    "metrics": metrics,
                    "outcome_id": str(outcome.id),
                    "recorded_at": outcome.recorded_at.isoformat() if outcome.recorded_at else None,
                },
            }
        )
    return blocks


def _primary_evidence(metrics: dict) -> list[str]:
    if not metrics:
        return []
    evidence: list[str] = []
    for key, value in metrics.items():
        label = str(key).replace("_", " ")
        evidence.append(f"{label}: {value}")
    return evidence[:6]
