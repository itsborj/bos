from typing import Optional
from pydantic import BaseModel


class BrandCreate(BaseModel):
    name: str
    voice: str = ""
    tone: str = ""
    values: list[str] = []
    domain: str = ""
    website_url: str = ""
    social_handles: dict = {}


class BrandUpdate(BaseModel):
    name: Optional[str] = None
    voice: Optional[str] = None
    tone: Optional[str] = None
    values: Optional[list[str]] = None
    domain: Optional[str] = None
    website_url: Optional[str] = None
    social_handles: Optional[dict] = None


class BrandResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    voice: str
    tone: str
    values: list[str]
    domain: str
    website_url: str
    social_handles: dict
    created_at: str
    updated_at: str
