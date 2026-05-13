from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from models.document import WorkspaceDocument
from routers.workspace import get_singleton
from schemas.documents import WorkspaceDocumentCreate, WorkspaceDocumentOut, WorkspaceDocumentUpdate

router = APIRouter(prefix="/workspace/documents", tags=["workspace-documents"])

_ALLOWED_STATUSES = {"draft", "approved", "changes_requested", "archived"}


def _serialize(doc: WorkspaceDocument) -> WorkspaceDocumentOut:
    tags = doc.tags_json if isinstance(doc.tags_json, list) else []
    metadata = doc.metadata_json if isinstance(doc.metadata_json, dict) else {}
    return WorkspaceDocumentOut(
        id=doc.id,
        workspace_id=doc.workspace_id,
        brand_id=doc.brand_id,
        doc_type=doc.doc_type,
        title=doc.title,
        content_markdown=doc.content_markdown,
        status=doc.status,
        tags=tags,
        metadata=metadata,
        source_run_id=doc.source_run_id,
        approved_at=doc.approved_at,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _validate_status(status: Optional[str]) -> None:
    if status is not None and status not in _ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid document status '{status}'")


async def _workspace_or_412(db: AsyncSession):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    return ws


@router.get("", response_model=List[WorkspaceDocumentOut], summary="List workspace documents")
async def list_documents(
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    brand_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    _validate_status(status)
    ws = await _workspace_or_412(db)

    stmt = select(WorkspaceDocument).where(WorkspaceDocument.workspace_id == ws.id)
    if doc_type:
        stmt = stmt.where(WorkspaceDocument.doc_type == doc_type)
    if status:
        stmt = stmt.where(WorkspaceDocument.status == status)
    if brand_id:
        try:
            stmt = stmt.where(WorkspaceDocument.brand_id == _uuid.UUID(brand_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid brand_id")
    stmt = stmt.order_by(WorkspaceDocument.updated_at.desc(), WorkspaceDocument.created_at.desc())

    rows = (await db.execute(stmt)).scalars().all()
    return [_serialize(row) for row in rows]


@router.post("", response_model=WorkspaceDocumentOut, status_code=201, summary="Create a workspace document")
async def create_document(
    body: WorkspaceDocumentCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    _validate_status(body.status)
    ws = await _workspace_or_412(db)
    now = datetime.now(timezone.utc)
    status = body.status or "draft"

    doc = WorkspaceDocument(
        workspace_id=ws.id,
        doc_type=body.doc_type,
        title=body.title,
        content_markdown=body.content_markdown,
        status=status,
        tags_json=body.tags or [],
        metadata_json=body.metadata or {},
        source_run_id=body.source_run_id,
        approved_at=now if status == "approved" else None,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _serialize(doc)


@router.get("/{document_id}", response_model=WorkspaceDocumentOut, summary="Get a workspace document")
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await _workspace_or_412(db)
    doc = (await db.execute(
        select(WorkspaceDocument).where(WorkspaceDocument.id == document_id, WorkspaceDocument.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialize(doc)


@router.patch("/{document_id}", response_model=WorkspaceDocumentOut, summary="Update a workspace document")
async def update_document(
    document_id: UUID,
    body: WorkspaceDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    _validate_status(body.status)
    ws = await _workspace_or_412(db)
    doc = (await db.execute(
        select(WorkspaceDocument).where(WorkspaceDocument.id == document_id, WorkspaceDocument.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if body.title is not None:
        doc.title = body.title
    if body.content_markdown is not None:
        doc.content_markdown = body.content_markdown
    if body.tags is not None:
        doc.tags_json = body.tags
    if body.metadata is not None:
        doc.metadata_json = body.metadata
    if body.status is not None:
        doc.status = body.status
        doc.approved_at = datetime.now(timezone.utc) if body.status == "approved" else None

    await db.commit()
    await db.refresh(doc)
    return _serialize(doc)


@router.post("/{document_id}/approve", response_model=WorkspaceDocumentOut, summary="Approve a workspace document")
async def approve_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    return await update_document(
        document_id,
        WorkspaceDocumentUpdate(status="approved"),
        db,
        _,
    )
