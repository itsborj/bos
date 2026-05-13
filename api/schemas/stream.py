import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class StreamUpdateOut(BaseModel):
    id: uuid.UUID
    type: str
    layout_hint: str
    interaction: str
    priority: str
    data_json: Any
    campaign_id: Optional[uuid.UUID]
    source_key: Optional[str]
    created_at: datetime
    read_at: Optional[datetime]
    dismissed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class StreamListResponse(BaseModel):
    updates: list[StreamUpdateOut]
    total: int


class StreamRefreshOut(BaseModel):
    created: int
    message: str
