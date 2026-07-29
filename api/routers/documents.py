from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from models.document import WorkspaceDocument
from models.social import SocialConnection
from routers.social import get_page_token
from routers.workspace import get_singleton
from schemas.documents import WorkspaceDocumentCreate, WorkspaceDocumentOut, WorkspaceDocumentUpdate
from services.brand_kit_templates import ensure_template_manifest
from validation import NullableUUID

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


def _validate_status(status: Optional[str], *, strict: bool = False) -> Optional[str]:
    """For GET filters: return None for absent/null/unknown values (no filter applied).
    For writes (strict=True): raise 422 on unrecognized values."""
    if status is None or status in {"", "null", "none", "undefined"}:
        return None
    if status not in _ALLOWED_STATUSES:
        if strict:
            raise HTTPException(
                status_code=422,
                detail=[{"loc": ["query", "status"], "msg": f"value is not a valid status: '{status}'", "type": "value_error"}],
            )
        return None
    return status


async def _workspace_or_412(db: AsyncSession):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    return ws


def _brand_kit_drive_approval_problem(token_meta: dict | None) -> tuple[str, str] | None:
    meta = token_meta if isinstance(token_meta, dict) else {}
    if not str(meta.get("drive_root_folder_id") or "").strip():
        return "DRIVE_ROOT_REQUIRED", "Choose and validate a Brand Kit Drive folder before approving this Brand Creative Brief."
    validation = meta.get("imprint_asset_validation") if isinstance(meta.get("imprint_asset_validation"), dict) else {}
    logo_files = [item for item in (validation.get("logo_files") or []) if isinstance(item, dict) and item.get("id")]
    if not logo_files:
        return "DRIVE_ROOT_MISSING_LOGO", "The validated Brand Kit Drive folder must contain an indexed logo, wordmark, or brandmark before approval."
    return None


def _drive_approval_error(code: str, message: str, status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message, "details": None}})


async def _live_brand_kit_drive_problem(
    token_meta: dict,
    access_token: str,
    *,
    client: Any | None = None,
) -> tuple[str, str, int] | None:
    """Verify the cached root and primary logo still exist in Drive."""
    cached_problem = _brand_kit_drive_approval_problem(token_meta)
    if cached_problem:
        return cached_problem[0], cached_problem[1], 422

    validation = token_meta.get("imprint_asset_validation") or {}
    logo = next(item for item in validation.get("logo_files") or [] if isinstance(item, dict) and item.get("id"))
    checks = (
        (str(token_meta["drive_root_folder_id"]), "folder"),
        (str(logo["id"]), "logo"),
    )
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=15.0, headers={"Authorization": f"Bearer {access_token}"})
    try:
        for file_id, kind in checks:
            response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": "id,name,mimeType,trashed", "supportsAllDrives": "true"},
            )
            if response.status_code == 401:
                return "DRIVE_REAUTH_REQUIRED", "Reconnect Google Drive before approving this Brand Creative Brief.", 401
            if response.status_code == 403:
                return "DRIVE_PERMISSION_DENIED", f"Google Drive denied access to the indexed Brand Kit {kind}.", 403
            if response.status_code == 404:
                return "DRIVE_INDEX_STALE", f"The indexed Brand Kit {kind} no longer exists in Google Drive. Refresh the authorized folder before approval.", 422
            if not response.is_success:
                return "DRIVE_VALIDATION_FAILED", f"Google Drive could not validate the indexed Brand Kit {kind} (HTTP {response.status_code}).", 502
            metadata = response.json()
            if metadata.get("trashed"):
                return "DRIVE_INDEX_STALE", f"The indexed Brand Kit {kind} is in Google Drive trash. Restore it or refresh the authorized folder before approval.", 422
            mime = str(metadata.get("mimeType") or "")
            if kind == "folder" and mime != "application/vnd.google-apps.folder":
                return "DRIVE_ROOT_NOT_FOLDER", "The indexed Brand Kit root is no longer a Google Drive folder.", 422
            if kind == "logo" and not mime.startswith("image/"):
                return "DRIVE_LOGO_NOT_IMAGE", "The indexed Brand Kit logo is no longer an image file.", 422
    except httpx.RequestError:
        return "DRIVE_VALIDATION_UNAVAILABLE", "Google Drive could not be reached to validate the Brand Kit. Retry approval.", 503
    finally:
        if owns_client:
            await client.aclose()
    return None


async def _require_brand_kit_drive_ready(db: AsyncSession, doc: WorkspaceDocument) -> None:
    if doc.doc_type != "campaign_brand_kit" or doc.brand_id is None:
        return
    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.workspace_id == doc.workspace_id,
            SocialConnection.brand_id == doc.brand_id,
            SocialConnection.platform == "google_drive",
            SocialConnection.status == "connected",
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    meta = row.token_meta_json if row and isinstance(row.token_meta_json, dict) else {}
    problem = _brand_kit_drive_approval_problem(meta)
    if problem:
        raise _drive_approval_error(problem[0], problem[1])

    settings = get_settings()
    token, _ = await get_page_token(db, str(doc.brand_id), "google_drive", settings)
    if not token:
        if row and row.status != "needs_reauth":
            row.status = "needs_reauth"
            await db.commit()
        raise _drive_approval_error("DRIVE_REAUTH_REQUIRED", "Reconnect Google Drive before approving this Brand Creative Brief.", 401)
    live_problem = await _live_brand_kit_drive_problem(meta, token)
    if live_problem:
        code, message, status_code = live_problem
        if status_code == 401 and row and row.status != "needs_reauth":
            row.status = "needs_reauth"
            await db.commit()
        raise _drive_approval_error(code, message, status_code)


@router.get("", response_model=List[WorkspaceDocumentOut], summary="List workspace documents")
async def list_documents(
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    brand_id: NullableUUID = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    status = _validate_status(status)
    ws = await _workspace_or_412(db)

    stmt = select(WorkspaceDocument).where(WorkspaceDocument.workspace_id == ws.id)
    if doc_type:
        stmt = stmt.where(WorkspaceDocument.doc_type == doc_type)
    if status:
        stmt = stmt.where(WorkspaceDocument.status == status)
    if brand_id is not None:
        stmt = stmt.where(WorkspaceDocument.brand_id == brand_id)
    stmt = stmt.order_by(WorkspaceDocument.updated_at.desc(), WorkspaceDocument.created_at.desc())

    rows = (await db.execute(stmt)).scalars().all()
    return [_serialize(row) for row in rows]


@router.post("", response_model=WorkspaceDocumentOut, status_code=201, summary="Create a workspace document")
async def create_document(
    body: WorkspaceDocumentCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    _validate_status(body.status, strict=True)
    ws = await _workspace_or_412(db)
    now = datetime.now(timezone.utc)
    status = body.status or "draft"

    metadata = body.metadata or {}
    if body.doc_type == "campaign_brand_kit":
        metadata = ensure_template_manifest(metadata)
    doc = WorkspaceDocument(
        workspace_id=ws.id,
        doc_type=body.doc_type,
        title=body.title,
        content_markdown=body.content_markdown,
        status=status,
        tags_json=body.tags or [],
        metadata_json=metadata,
        source_run_id=body.source_run_id,
        approved_at=now if status == "approved" else None,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _serialize(doc)


@router.get("/{document_id}", response_model=WorkspaceDocumentOut, summary="Get a workspace document", responses={404: {"description": "Document not found"}})
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


@router.patch("/{document_id}", response_model=WorkspaceDocumentOut, summary="Update a workspace document", responses={404: {"description": "Document not found"}})
async def update_document(
    document_id: UUID,
    body: WorkspaceDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    _validate_status(body.status, strict=True)
    ws = await _workspace_or_412(db)
    doc = (await db.execute(
        select(WorkspaceDocument).where(WorkspaceDocument.id == document_id, WorkspaceDocument.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if body.status == "approved":
        await _require_brand_kit_drive_ready(db, doc)

    if body.title is not None:
        doc.title = body.title
    if body.content_markdown is not None:
        doc.content_markdown = body.content_markdown
    if body.tags is not None:
        doc.tags_json = body.tags
    if body.metadata is not None:
        doc.metadata_json = ensure_template_manifest(body.metadata) if doc.doc_type == "campaign_brand_kit" else body.metadata
    if body.status is not None:
        doc.status = body.status
        doc.approved_at = datetime.now(timezone.utc) if body.status == "approved" else None
        if body.status == "approved" and doc.doc_type == "campaign_brand_kit":
            doc.metadata_json = ensure_template_manifest(doc.metadata_json)

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
