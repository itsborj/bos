import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DecisionBriefGenerateIn(BaseModel):
    brand_id: Optional[uuid.UUID] = None
    objective_id: Optional[uuid.UUID] = None
    summary_override: Optional[str] = None
    recommended_next_override: Optional[str] = None


class DecisionBriefCreate(BaseModel):
    brand_id: Optional[uuid.UUID] = None
    objective_id: Optional[uuid.UUID] = None
    status: str = Field(default="active", max_length=32)
    summary: str = Field(min_length=1)
    objective_affected: Optional[str] = None
    evidence: list[dict] = Field(default_factory=list)
    hypothesis_ranking: list[dict] = Field(default_factory=list)
    confidence: str = Field(default="directional", max_length=64)
    recommended_next: str = Field(min_length=1)
    do_not_list: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=lambda: ["ask CMO", "investigate", "dismiss"])
    source_refs: list[str] = Field(default_factory=list)
    full_record: dict = Field(default_factory=dict)


class DecisionBriefOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    objective_id: Optional[uuid.UUID]
    status: str
    summary: str
    objective_affected: Optional[str]
    evidence: list
    hypothesis_ranking: list
    confidence: str
    recommended_next: str
    do_not_list: list
    allowed_actions: list
    source_refs: list
    full_record: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DecisionBriefListResponse(BaseModel):
    decision_briefs: list[DecisionBriefOut]
    total: int
