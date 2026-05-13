from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BriefPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    product_name: Optional[str] = None
    tagline: Optional[str] = None
    audience: Optional[str] = None
    tone: Optional[str] = None
    key_benefit: Optional[str] = None


class RunConstraints(BaseModel):
    max_chars: Optional[int] = None
    must_mention: list[str] = []
    banned_phrases: list[str] = []


class RunPayload(BaseModel):
    brief: BriefPayload = BriefPayload()
    constraints: RunConstraints = RunConstraints()


class RunRequest(BaseModel):
    module_id: str
    policy: Literal["cheap", "balanced", "premium"] = "balanced"
    payload: RunPayload = RunPayload()
    brand_id: Optional[UUID] = None
    campaign_id: Optional[UUID] = None


# ── Response models ────────────────────────────────────────────────────────────

class RunResultOut(BaseModel):
    content: str
    self_check: str
    platform: Optional[str] = None
    block: Optional[dict] = None  # Module-specific structured block (performance_report, google_ads_text, etc.)


class RunExecutionOut(BaseModel):
    provider: str
    model: str
    mode: str
    attempts: int
    latency_ms: int
    tokens_used: Optional[int] = None
    provider_cost: Optional[float] = None
    sell_price: Optional[float] = None


class RunTraceOut(BaseModel):
    capability: str
    policy: str
    candidates_considered: int
    candidates_filtered: int
    winner: Optional[str] = None
    routing_reason: str


class RunResponse(BaseModel):
    run_id: str
    module_id: str
    vertical: str
    status: str
    approval_status: Optional[str] = None
    campaign_id: Optional[str] = None
    brand_id: Optional[str] = None
    result: Optional[RunResultOut] = None
    execution: Optional[RunExecutionOut] = None
    trace: Optional[RunTraceOut] = None
    created_at: datetime


class RunListItem(BaseModel):
    run_id: str
    module_id: str
    vertical: str
    status: str
    approval_status: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    brand_id: Optional[str] = None
    created_at: datetime
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    tokens: Optional[int] = None
    cost: Optional[float] = None


class RunListResponse(BaseModel):
    runs: list[RunListItem]
    total: int
    limit: int
    offset: int
