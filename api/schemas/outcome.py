import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EvaluateOutcomeIn(BaseModel):
    brand_id: Optional[uuid.UUID] = None
    objective_id: Optional[uuid.UUID] = None
    source_ref: Optional[str] = Field(default=None, max_length=255)
    summary: str = Field(min_length=1)
    metrics: dict = Field(default_factory=dict)
    topic_tags: list[str] = Field(default_factory=lambda: ["outcome"])
    confidence_source: str = Field(default="manually_reported", max_length=64)
    full_record: dict = Field(default_factory=dict)


class OutcomeRecordOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    objective_id: Optional[uuid.UUID]
    source_ref: Optional[str]
    summary: str
    metrics_json: dict
    confidence_source: str
    full_record: dict
    recorded_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluateOutcomeOut(BaseModel):
    outcome: OutcomeRecordOut
    memory_event_id: uuid.UUID


class OutcomeListResponse(BaseModel):
    outcomes: list[OutcomeRecordOut]
    total: int
