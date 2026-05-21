"""DecisionBrief Stream cards."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.decision_brief import DecisionBrief
from models.workspace import Workspace
from stream.types import defaults


async def generate(db: AsyncSession, workspace: Workspace) -> list[dict]:
    rows = (
        await db.execute(
            select(DecisionBrief)
            .where(DecisionBrief.workspace_id == workspace.id, DecisionBrief.status == "active")
            .order_by(DecisionBrief.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    blocks: list[dict] = []
    for brief in rows:
        d = defaults("decision_brief")
        blocks.append(
            {
                "type": "decision_brief",
                "layout_hint": d["layout_hint"],
                "interaction": d["interaction"],
                "priority": "high",
                "campaign_id": None,
                "source_key": f"decision_brief:{brief.id}",
                "data_json": {
                    "card_type": "decision_brief",
                    "objective_ref": str(brief.objective_id) if brief.objective_id else None,
                    "brand_ref": str(brief.brand_id) if brief.brand_id else None,
                    "why_now": brief.summary,
                    "confidence": brief.confidence,
                    "primary_evidence": _primary_evidence(brief.evidence or []),
                    "recommended_next": brief.recommended_next,
                    "approval_boundary": "BOS can recommend and prepare. External Gmail actions still require approval.",
                    "allowed_actions": brief.allowed_actions or ["ask CMO", "investigate", "dismiss"],
                    "source_state": ", ".join((brief.source_refs or [])[:3]) or "DecisionBrief v0",
                    "summary": brief.summary,
                    "objective_affected": brief.objective_affected,
                    "hypothesis_ranking": brief.hypothesis_ranking or [],
                    "do_not_list": brief.do_not_list or [],
                    "decision_brief_id": str(brief.id),
                    "created_at": brief.created_at.isoformat() if brief.created_at else None,
                },
            }
        )
    return blocks


def _primary_evidence(evidence: list) -> list[str]:
    items: list[str] = []
    for row in evidence:
        if isinstance(row, dict):
            summary = row.get("summary")
            metrics = row.get("metrics") or {}
            if metrics:
                metric_text = ", ".join(f"{str(k).replace('_', ' ')}: {v}" for k, v in list(metrics.items())[:4])
                items.append(f"{summary} ({metric_text})" if summary else metric_text)
            elif summary:
                items.append(str(summary))
        elif row:
            items.append(str(row))
    return items[:6]
