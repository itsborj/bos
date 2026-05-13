from datetime import datetime

from pydantic import BaseModel, model_validator


class BackendOverrideIn(BaseModel):
    provider: str
    model_id: str | None = None
    tool_id: str | None = None
    modality: str = "text"
    strict: bool = True

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
    source: str = "db"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BackendOverrideListResponse(BaseModel):
    overrides: list[BackendOverrideOut]
