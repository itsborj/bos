from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class WorkspaceNamePayload(BaseModel):
    name: str


class BrandPayload(BaseModel):
    voice: Optional[str] = None
    tone: Optional[str] = None
    values: list[str] = []
    visual_guidelines: Optional[str] = None
    domain: Optional[str] = None
    website_url: Optional[str] = None
    social_handles: dict[str, str] = {}


class ProductPayload(BaseModel):
    id: Optional[UUID] = None  # present → update; absent → create
    name: str
    tagline: Optional[str] = None
    benefits: list[str] = []


class ProductsPayload(BaseModel):
    products: list[ProductPayload]


class AudiencePayload(BaseModel):
    id: Optional[UUID] = None
    name: str
    demographics: Optional[str] = None
    pain_points: list[str] = []


class AudiencesPayload(BaseModel):
    audiences: list[AudiencePayload]


# ── Response models ────────────────────────────────────────────────────────────

class BrandOut(BaseModel):
    voice: Optional[str] = None
    tone: Optional[str] = None
    values: list[str] = []
    visual_guidelines: Optional[str] = None
    domain: Optional[str] = None
    website_url: Optional[str] = None
    social_handles: dict[str, str] = {}


class ProductOut(BaseModel):
    id: UUID
    name: str
    tagline: Optional[str] = None
    benefits: list[str] = []
    brand_id: Optional[UUID] = None


class AudienceOut(BaseModel):
    id: UUID
    name: str
    demographics: Optional[str] = None
    pain_points: list[str] = []
    brand_id: Optional[UUID] = None


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    brand: Optional[BrandOut] = None
    products: list[ProductOut] = []
    audiences: list[AudienceOut] = []
    booking_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
