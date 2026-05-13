from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CampaignCreate(BaseModel):
    name: str
    status: Optional[str] = "draft"


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None


class CampaignOut(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class CampaignDetail(CampaignOut):
    # Future: include related runs, modules, etc.
    pass


class CampaignRunPayload(BaseModel):
    module_ids: Optional[list[str]] = None  # If None, run all eligible modules
    brief: Optional[dict] = None  # Override brief for this run
