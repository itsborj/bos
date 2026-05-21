import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PendingDecisionCreate(BaseModel):
    brand_id: Optional[uuid.UUID] = None
    objective_id: Optional[uuid.UUID] = None
    what_is_deferred: str = Field(min_length=1)
    waiting_for: str = Field(min_length=1)
    leading_hypothesis: Optional[str] = None
    action_blocked: str = Field(min_length=1)
    source_ref: Optional[str] = Field(default=None, max_length=255)
    full_record: dict = Field(default_factory=dict)


class PendingDecisionResolve(BaseModel):
    resolution_summary: Optional[str] = None


class PendingDecisionOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    objective_id: Optional[uuid.UUID]
    status: str
    what_is_deferred: str
    waiting_for: str
    leading_hypothesis: Optional[str]
    action_blocked: str
    source_ref: Optional[str]
    full_record: dict
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PendingDecisionListResponse(BaseModel):
    pending_decisions: list[PendingDecisionOut]
    total: int


class HandoffBriefOut(BaseModel):
    brand_id: Optional[uuid.UUID]
    generated_at: datetime
    active_objectives: list[dict]
    performance_narrative: dict
    pending_decisions: list[PendingDecisionOut]
    committed_actions: list[dict]
    known_risks: list[str]
    working: list[str]
    not_working: list[str]
    decided_against: list[str]
    recommended_first_action: str
