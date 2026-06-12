from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field, model_validator

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_MODEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_./:-]{0,255}$"


class FallbackModel(BaseModel):
    provider: str = Field(pattern=_IDENTIFIER_PATTERN)
    model_id: str | None = Field(default=None, pattern=_MODEL_PATTERN)
    tool_id: str | None = Field(default=None, pattern=_MODEL_PATTERN)
    routing_hints: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def has_model_or_tool(self):
        if not self.model_id and not self.tool_id:
            raise ValueError("Either model_id or tool_id is required")
        return self


class BackendOverrideIn(BaseModel):
    provider: str = Field(pattern=_IDENTIFIER_PATTERN)
    model_id: str | None = Field(default=None, pattern=_MODEL_PATTERN)
    tool_id: str | None = Field(default=None, pattern=_MODEL_PATTERN)
    modality: Literal["text", "image", "video", "data_analysis"] = "text"
    strict: bool = True
    fallbacks: list[FallbackModel] = Field(default_factory=list)
    routing_hints: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def has_model_or_tool(self):
        if not self.model_id and not self.tool_id:
            raise ValueError("Either model_id or tool_id is required")
        return self


class BackendOverrideOut(BaseModel):
    target: str
    provider: str
    model_id: str | None = None
    tool_id: str | None = None
    modality: str
    strict: bool
    fallbacks: list[FallbackModel] = Field(default_factory=list)
    routing_hints: dict = Field(default_factory=dict)
    source: str = "db"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BackendOverrideListResponse(BaseModel):
    overrides: list[BackendOverrideOut]
