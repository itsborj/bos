"""Strategy workflow persistence — create WorkflowRun + WorkflowComponent rows.

Extracted from routers/runs.py _persist_workflow_record, _component_summary.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.run import Run
from models.workflow import WorkflowComponent, WorkflowRun
from models.workspace import Workspace

logger = logging.getLogger("bos.services.workflow_persistence")

# Component types that are generated in the initial full-chain run
_WIRED_COMPONENTS = [
    "buyer_map",
    "strategic_thesis",
    "offer_architecture",
    "channel_stack",
    "tactical_funnel",
    "work_orders",
]

# Component types that are placeholders (not_wired) in the initial run
_NOT_WIRED_COMPONENTS = [
    "market_context",
    "framework_lenses",
    "channel_content_matrix",
    "measurement_model",
]


def _component_summary(component_type: str, data: dict) -> str | None:
    """One-sentence summary for Stream card / CMO chat from component data."""
    if component_type == "buyer_map":
        al = data.get("awareness_level", "")
        bt = data.get("buyer_type", "")
        tg = data.get("trust_gap", "")
        if al and bt:
            base = f"{bt.replace('_', ' ').title()} buyer at {al.replace('_', ' ')} stage"
            return f"{base} — trust gap: {tg}" if tg else f"{base}."
    if component_type == "strategic_thesis":
        motion = data.get("primary_motion", "")
        wedge = data.get("wedge", "")
        return f"{motion.replace('-', ' ').title()} motion — {wedge}" if motion and wedge else None
    if component_type == "offer_architecture":
        mc = data.get("micro_commitment", "")
        return f"Entry: {mc}" if mc else None
    if component_type == "channel_stack":
        do_now = data.get("do_now") or []
        if do_now:
            channels = ", ".join(c.get("channel", "") for c in do_now[:3] if c.get("channel"))
            return f"Do now: {channels}." if channels else None
    if component_type == "tactical_funnel":
        cta = data.get("action_cta", "")
        return f"CTA: {cta}" if cta else None
    if component_type == "work_orders":
        briefs = data.get("briefs") or []
        return f"{len(briefs)} work order{'s' if len(briefs) != 1 else ''} generated." if briefs else None
    return None


async def persist_workflow_record(
    db: AsyncSession,
    ws: Workspace,
    run: Run,
    brand_id: Optional[UUID],
    brief: dict,
    block: dict,
) -> dict:
    """Create WorkflowRun + WorkflowComponent rows from a strategy_workflow block.

    Returns the block with workflow_id and workflow_url injected.
    """
    try:
        archetype = block.get("archetype") or "direct_sales"
        request = brief.get("request") or brief.get("message") or brief.get("objective") or ""

        wf = WorkflowRun(
            workspace_id=ws.id,
            brand_id=brand_id,
            run_id=run.id,
            archetype=archetype,
            request=str(request)[:2000],
            status="complete",
        )
        db.add(wf)
        await db.flush()

        component_list = block.get("components") or []
        comp_map = {c.get("type"): c for c in component_list if c.get("type")}

        for ctype in _WIRED_COMPONENTS:
            comp_data = comp_map.get(ctype, {})
            db.add(WorkflowComponent(
                workflow_run_id=wf.id,
                component_type=ctype,
                status="complete",
                version=1,
                data=comp_data.get("data") or {},
                summary=_component_summary(ctype, comp_data.get("data") or {}),
                run_id=run.id,
            ))

        for ctype in _NOT_WIRED_COMPONENTS:
            db.add(WorkflowComponent(
                workflow_run_id=wf.id,
                component_type=ctype,
                status="not_wired",
                version=1,
                data={},
                summary=None,
                run_id=None,
            ))

        block = {**block, "workflow_id": str(wf.id), "workflow_url": f"/strategy-workflows/{wf.id}"}
        logger.info("WorkflowRun created: %s (archetype=%s)", wf.id, archetype)
    except Exception:
        logger.exception("Failed to persist WorkflowRun — block returned without workflow_id")

    return block
