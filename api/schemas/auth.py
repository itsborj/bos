from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ApiKeyCreate(BaseModel):
    label: Optional[str] = None


class ApiKeyCreated(BaseModel):
    key: str  # shown exactly once — not stored
    key_id: UUID
    label: Optional[str] = None
    created_at: datetime


class ApiKeyItem(BaseModel):
    key_id: UUID
    label: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
