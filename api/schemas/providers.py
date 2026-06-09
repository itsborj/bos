from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class KeyRegisterRequest(BaseModel):
    provider: str
    key: str
    brand_id: str | None = None


class KeyListItem(BaseModel):
    provider: str
    brand_id: str | None = None
    created_at: datetime


class CheckRequest(BaseModel):
    provider: str
    brand_id: str | None = None


class CheckResponse(BaseModel):
    provider: str
    status: str
    message: str
    auth_mode: str | None = None


class ProviderModelInfo(BaseModel):
    model_id: str
    capability: str | None = None
    quality_tier: str
    latency_ms: int
    supports_json: bool
    status: str


class ProviderModelLive(BaseModel):
    """A model available for selection — sourced live from provider APIs or seeded catalog."""
    provider: str
    model_id: str
    name: str
    is_free: bool
    input_cost_per_token: float
    output_cost_per_token: float
    context_length: int
    quality_tier: str  # "high" | "medium" | "low"
    supports_json: bool
    modality: str = "text"  # "text" | "image" | "video"


class ProviderInfo(BaseModel):
    provider: str
    brand_id: str | None = None
    model_count: int
    status: str
    auth_supported: list[str]
    connected: bool
    auth_mode: str | None = None
    expires_at: datetime | None = None
    has_platform_key: bool
    has_byok_key: bool
    avg_latency_ms: float | None = None
    last_used_at: datetime | None = None
    last_check_status: str | None = None
    last_check_message: str | None = None
    last_check_at: datetime | None = None
    top_models: list[ProviderModelInfo] = []


class LoginStartRequest(BaseModel):
    provider: str


class LoginPrompt(BaseModel):
    type: Literal["browser", "device_code", "prompt"]
    authorize_url: str | None = None
    user_code: str | None = None
    verification_uri: str | None = None


class LoginStartResponse(BaseModel):
    provider: str
    auth_mode: Literal["oauth"]
    login_id: str
    login: LoginPrompt


class LoginCompleteRequest(BaseModel):
    provider: str
    login_id: str
    callback_url: str


class LoginCompleteResponse(BaseModel):
    provider: str
    connected: bool
    auth_mode: str
    expires_at: datetime | None = None
