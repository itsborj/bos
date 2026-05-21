import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

ObjectiveStatus = Literal["draft", "active", "paused", "completed", "archived"]


class ObjectiveCreate(BaseModel):
    brand_id: Optional[uuid.UUID] = None
    status: ObjectiveStatus = "draft"
    summary: str = Field(min_length=1)
    success_metric: str = Field(min_length=1)
    horizon: str = Field(min_length=1, max_length=120)
    created_from: str = Field(default="manual", min_length=1, max_length=120)


class ObjectiveUpdate(BaseModel):
    brand_id: Optional[uuid.UUID] = None
    status: Optional[ObjectiveStatus] = None
    summary: Optional[str] = Field(default=None, min_length=1)
    success_metric: Optional[str] = Field(default=None, min_length=1)
    horizon: Optional[str] = Field(default=None, min_length=1, max_length=120)
    created_from: Optional[str] = Field(default=None, min_length=1, max_length=120)


class ObjectiveOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    status: ObjectiveStatus
    summary: str
    success_metric: str
    horizon: str
    created_from: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ObjectiveListResponse(BaseModel):
    objectives: list[ObjectiveOut]
    total: int
