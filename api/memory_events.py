import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.memory import MemoryEvent
from models.objective import Objective

MEMORY_EVENT_TYPES = {
    "artifact_created",
    "artifact_approved",
    "artifact_deleted",
    "artifact_dismissed",
    "artifact_revised",
    "run_failed",
    "decision_made",
    "decision_not_to_act",
    "outcome_recorded",
    "constraint_flag",
}

RATIONALE_REQUIRED_EVENT_TYPES = {"decision_made", "decision_not_to_act"}


async def resolve_active_objective_id(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    brand_id: Optional[uuid.UUID],
) -> Optional[uuid.UUID]:
    filters = [Objective.workspace_id == workspace_id, Objective.status == "active"]
    if brand_id is None:
        filters.append(Objective.brand_id.is_(None))
    else:
        filters.append(Objective.brand_id == brand_id)

    objective = (
        await db.execute(
            select(Objective).where(*filters).order_by(Objective.updated_at.desc(), Objective.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return objective.id if objective else None


async def write_memory_event(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    event_type: str,
    summary: str,
    brand_id: Optional[uuid.UUID] = None,
    objective_id: Optional[uuid.UUID] = None,
    campaign_id: Optional[uuid.UUID] = None,
    primitive_type: Optional[str] = None,
    primitive_status: Optional[str] = None,
    confidence: Optional[str] = None,
    source_type: Optional[str] = None,
    topic_tags: Optional[list[str]] = None,
    rationale: Optional[str] = None,
    source_ref: Optional[str] = None,
    full_record: Optional[dict] = None,
) -> MemoryEvent:
    """Add one append-only MemoryEvent to the current DB transaction."""

    if event_type not in MEMORY_EVENT_TYPES:
        raise ValueError(f"Unsupported MemoryEvent type: {event_type}")
    if event_type in RATIONALE_REQUIRED_EVENT_TYPES and not (rationale or "").strip():
        raise ValueError("rationale is required for decision_made and decision_not_to_act events")
    if not objective_id:
        objective_id = await resolve_active_objective_id(db, workspace_id, brand_id)

    event = MemoryEvent(
        workspace_id=workspace_id,
        brand_id=brand_id,
        objective_id=objective_id,
        campaign_id=campaign_id,
        event_type=event_type,
        primitive_type=primitive_type,
        primitive_status=primitive_status,
        confidence=confidence,
        source_type=source_type,
        topic_tags=topic_tags or [],
        summary=summary,
        rationale=rationale,
        source_ref=source_ref,
        full_record=full_record or {},
    )
    db.add(event)
    return event
