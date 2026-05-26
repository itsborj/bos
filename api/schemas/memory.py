import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

MemoryEventType = Literal[
    "artifact_created",
    "artifact_approved",
    "artifact_dismissed",
    "artifact_revised",
    "run_failed",
    "decision_made",
    "decision_not_to_act",
    "outcome_recorded",
    "constraint_flag",
]

_RATIONALE_REQUIRED = {"decision_made", "decision_not_to_act"}


class MemoryEventCreate(BaseModel):
    brand_id: Optional[uuid.UUID] = None
    objective_id: Optional[uuid.UUID] = None
    event_type: MemoryEventType
    topic_tags: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    rationale: Optional[str] = None
    source_ref: Optional[str] = Field(default=None, max_length=255)
    full_record: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_decision_rationale(self):
        if self.event_type in _RATIONALE_REQUIRED and not (self.rationale or "").strip():
            raise ValueError("rationale is required for decision_made and decision_not_to_act events")
        return self


class MemoryEventOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    objective_id: Optional[uuid.UUID]
    event_type: MemoryEventType
    topic_tags: list[str]
    summary: str
    rationale: Optional[str]
    source_ref: Optional[str]
    full_record: dict
    timestamp: datetime

    model_config = {"from_attributes": True}


class MemoryEventListResponse(BaseModel):
    events: list[MemoryEventOut]
    total: int
