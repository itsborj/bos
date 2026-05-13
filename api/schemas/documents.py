from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceDocumentCreate(BaseModel):
    doc_type: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    content_markdown: str = Field(..., min_length=1)
    status: Optional[str] = "draft"
    tags: Optional[List[str]] = None
    metadata: Optional[Dict] = None
    source_run_id: Optional[UUID] = None


class WorkspaceDocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content_markdown: Optional[str] = Field(None, min_length=1)
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict] = None


class WorkspaceDocumentOut(BaseModel):
    id: UUID
    workspace_id: UUID
    brand_id: Optional[UUID] = None
    doc_type: str
    title: str
    content_markdown: str
    status: str
    tags: List[str]
    metadata: Dict
    source_run_id: Optional[UUID]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
