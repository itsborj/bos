from __future__ import annotations

import base64
import binascii
import hashlib
import importlib.util
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from attachment_context import (
    DOC_EXTRACT_CAP,
    apply_extraction_json,
    ensure_reference_identity,
    extract_doc_text,
    persist_chat_references,
    sha256_hex,
)
from auth import require_api_key
from config import get_settings
from db import get_db
from models.provider import ProviderLoginSession
from models.social import SocialConnection
from provider_auth import decrypt_secret, encrypt_secret, get_oauth_handler, relay_claim_handoff
from routers.social import get_page_token
from routers.workspace import get_singleton

drive_router = APIRouter(prefix="/social/drive", tags=["google-drive"])
callback_router = APIRouter(prefix="/social", tags=["google-drive"])
router = drive_router
logger = logging.getLogger("bos.plugins.google_drive.api")


class SetDriveRootRequest(BaseModel):
    brand_id: str
    folder_id: str
    folder_name: Optional[str] = None
    folder_path: Optional[str] = None


class UploadDriveReferenceRequest(BaseModel):
    brand_id: str
    file_name: str
    mime_type: str
    data_b64: str


_ALLOWED_REFERENCE_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_BRAND_KIT_IMAGE_MIMES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
_MAX_REFERENCE_UPLOAD_BYTES = 10 * 1024 * 1024
_MAX_ATTACHMENT_UPLOAD_BYTES = 25 * 1024 * 1024
_MAX_THUMBNAIL_SOURCE_BYTES = 15 * 1024 * 1024

_ATTACHMENT_MIME_TO_KIND: dict[str, str] = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "document",
    "application/vnd.ms-powerpoint": "document",
    "application/pdf": "document",
    "application/json": "document",
    "text/plain": "document",
}


def _admin_brands_redirect(frontend: str, **params: str | None) -> RedirectResponse:
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    qs = urlencode(clean)
    suffix = f"?{qs}" if qs else ""
    return RedirectResponse(url=f"{frontend}/admin/brands{suffix}", status_code=302)


def _oauth_callback_status(error: str) -> str:
    return "denied" if error in {"access_denied", "user_denied", "user_cancelled"} else "error"


async def _store_drive_connection(db: AsyncSession, workspace_id, brand_id: str | None, settings, page: dict) -> SocialConnection:
    brand_uuid = uuid.UUID(brand_id) if brand_id else None
    existing = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand_uuid,
            SocialConnection.platform == "google_drive",
            SocialConnection.page_id == page["id"],
        )
    )).scalar_one_or_none()

    token_encrypted = encrypt_secret(page["access_token"], settings)
    token_meta = page.get("token_meta")

    if existing:
        existing.access_token_encrypted = token_encrypted
        existing.page_name = page.get("name")
        existing.page_handle = page.get("username")
        # Reconnect/reauth must refresh OAuth tokens without forgetting the
        # operator-selected Brand Kit root folder or imprint validation.
        merged_meta = dict(existing.token_meta_json or {})
        if token_meta:
            merged_meta.update(token_meta)
        existing.token_meta_json = merged_meta or token_meta
        existing.status = "connected"
        return existing

    conn = SocialConnection(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        brand_id=brand_uuid,
        platform="google_drive",
        page_id=page["id"],
        page_name=page.get("name"),
        page_handle=page.get("username"),
        access_token_encrypted=token_encrypted,
        token_meta_json=token_meta,
        status="connected",
    )
    db.add(conn)
    return conn


@callback_router.get("/google-drive/callback")
async def google_drive_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    handoff_token: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    """Google Drive OAuth callback owned by the google-drive plugin."""
    frontend = settings.frontend_url.rstrip("/")

    if handoff_token and settings.klaroha_relay_url:
        try:
            payload = await relay_claim_handoff(handoff_token, settings)
        except Exception:
            return _admin_brands_redirect(frontend, google_drive="error", reason="relay_claim_failed")
        meta = payload.get("metadata") or {}
        email = meta.get("email", "")
        brand_id = payload.get("brand_id") or ""
        if not email:
            return _admin_brands_redirect(frontend, google_drive="error", reason="incomplete_metadata")
        ws = await get_singleton(db)
        token_meta = None
        if payload.get("refresh_token"):
            token_meta = {
                "refresh_token_encrypted": encrypt_secret(payload["refresh_token"], settings),
                "expires_at": payload.get("expires_at"),
            }
        await _store_drive_connection(db, ws.id if ws else None, brand_id or None, settings, {
            "id": email,
            "access_token": payload["access_token"],
            "name": meta.get("name") or email,
            "username": email,
            "token_meta": token_meta,
        })
        await db.commit()
        return _admin_brands_redirect(frontend, google_drive="connected", brand_id=brand_id, account=meta.get("name") or email)

    if error or not code:
        return _admin_brands_redirect(frontend, google_drive=_oauth_callback_status(error) if error else "denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "google_drive",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_brands_redirect(frontend, google_drive="error", reason="session_not_found")

    raw = decrypt_secret(session.verifier_encrypted, settings)
    stored_verifier, brand_id = (raw.split("|", 1) + [""])[:2]

    ws = await get_singleton(db)
    handler = get_oauth_handler("google_drive")

    try:
        credential = await handler.complete_login(
            code,
            settings,
            state=session.state,
            verifier=stored_verifier,
            redirect_uri=session.redirect_uri,
        )
    except Exception:
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, google_drive="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    email = metadata.get("email", "")

    if not email:
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, google_drive="error", reason="incomplete_metadata")

    token_meta = None
    if credential.refresh_token:
        token_meta = {
            "refresh_token_encrypted": encrypt_secret(credential.refresh_token, settings),
            "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
        }

    await _store_drive_connection(db, ws.id if ws else None, brand_id or None, settings, {
        "id": email,
        "access_token": credential.access_token,
        "name": metadata.get("name") or email,
        "username": email,
        "token_meta": token_meta,
    })
    await db.delete(session)
    await db.commit()
    return _admin_brands_redirect(frontend, google_drive="connected", brand_id=brand_id, account=metadata.get("name") or email)


def _load_google_drive_client():
    path = Path(__file__).with_name("drive_client.py")
    spec = importlib.util.spec_from_file_location("_bos_google_drive_client", path)
    if not spec or not spec.loader:
        raise FileNotFoundError("google-drive/drive_client.py not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DriveClient


def _parse_brand_uuid(brand_id: str | None, field: str = "brand_id") -> uuid.UUID | None:
    if brand_id is None or brand_id == "" or brand_id == "null":
        return None
    try:
        return uuid.UUID(brand_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["query", field], "msg": "value is not a valid UUID", "type": "uuid_parsing"}],
        )


async def _drive_connection_row(db: AsyncSession, brand_id: str) -> SocialConnection | None:
    brand_uuid = _parse_brand_uuid(brand_id)
    if brand_uuid is None:
        return None
    return (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand_uuid,
            SocialConnection.platform == "google_drive",
            SocialConnection.status.in_(["connected", "needs_reauth"]),
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()


async def _resolve_drive_root_folder(db: AsyncSession, brand_id: str) -> tuple[str, str | None]:
    row = await _drive_connection_row(db, brand_id)
    meta = (row.token_meta_json or {}) if row else {}
    return str(meta.get("drive_root_folder_id") or "root"), meta.get("drive_root_name")


async def _mark_drive_reauth_required(db: AsyncSession, brand_id: str) -> None:
    row = await _drive_connection_row(db, brand_id)
    if row and row.status != "needs_reauth":
        row.status = "needs_reauth"
        await db.commit()


def _brand_kit_asset_validation(folder_id: str, folder_name: str | None, image_files: list[dict]) -> dict:
    def _named(pattern: str) -> list[dict]:
        rx = re.compile(pattern, re.IGNORECASE)
        return [f for f in image_files if rx.search(str(f.get("name") or ""))]

    logo_files = _named(r"(^|[-_ .])(logo|wordmark|brandmark|mark)([-_ .]|$)")
    creative_reference_files = _named(r"(^|[-_ .])(template\d*|template|master|reference|ref)([-_ .]|$)")
    mascot_files = _named(r"(^|[-_ .])(mascot|character|avatar|spokes?person)([-_ .]|$)")
    product_files = _named(r"(^|[-_ .])(product|hero|packshot|item|vehicle|bike|property|location|team|portrait)([-_ .]|$)")
    logo_ids = {str(f.get("id") or "") for f in logo_files}
    visual_asset_files = [f for f in image_files if str(f.get("id") or "") not in logo_ids]
    return {
        "status": "ok" if logo_files else "missing_logo",
        "folder_id": folder_id,
        "folder_name": folder_name,
        "image_count": len(image_files),
        "logo_files": logo_files,
        "creative_reference_files": creative_reference_files,
        "mascot_files": mascot_files,
        "product_files": product_files,
        "visual_asset_files": visual_asset_files,
        "supporting_asset_files": visual_asset_files,
    }


def _resolve_drive_root_path(meta: dict, folder_id: str, requested_path: str | None) -> str | None:
    """Keep an omitted path only for a same-folder re-index; never leak it across roots."""
    if requested_path is not None:
        return requested_path
    if str(meta.get("drive_root_folder_id") or "") == str(folder_id):
        existing = meta.get("drive_root_path")
        return str(existing) if existing is not None else None
    return None


def _drive_reauth_exception() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"error": {"code": "DRIVE_REAUTH_REQUIRED", "message": "Reconnect Google Drive for this brand. The saved token expired or was revoked.", "details": None}},
    )


def _drive_auth_invalid(exc: httpx.HTTPStatusError) -> bool:
    if exc.response.status_code == 401:
        return True
    if exc.response.status_code != 403:
        return False
    try:
        payload = exc.response.json()
    except Exception:
        return False
    error = payload.get("error") if isinstance(payload, dict) else {}
    if isinstance(error, dict) and str(error.get("status") or "").upper() == "UNAUTHENTICATED":
        return True
    reasons = {
        str(item.get("reason") or "")
        for item in (error.get("errors") or [])
        if isinstance(item, dict)
    } if isinstance(error, dict) else set()
    return bool(reasons & {"authError", "invalidCredentials"})


async def _raise_drive_http_error(exc: httpx.HTTPStatusError, db: AsyncSession, brand_id: str) -> None:
    status = exc.response.status_code
    if _drive_auth_invalid(exc):
        await _mark_drive_reauth_required(db, brand_id)
        raise _drive_reauth_exception() from exc
    if status == 403:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "DRIVE_PERMISSION_DENIED", "message": "Google Drive denied this operation. Check folder permissions or quota and retry.", "details": None}},
        ) from exc
    if status == 429:
        raise HTTPException(
            status_code=429,
            detail={"error": {"code": "DRIVE_RATE_LIMITED", "message": "Google Drive rate-limited this operation. Retry shortly.", "details": None}},
        ) from exc
    raise exc


@router.get("/folders", dependencies=[Depends(require_api_key)])
async def list_drive_folders(
    brand_id: str,
    parent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    DriveClient = _load_google_drive_client()
    conn = await _drive_connection_row(db, brand_id)
    if not conn:
        raise HTTPException(status_code=404, detail={"error": {"code": "DRIVE_NOT_CONNECTED", "message": "Connect Google Drive for this brand first.", "details": None}})

    token, _ = await get_page_token(db, brand_id, "google_drive", settings)
    if not token:
        raise _drive_reauth_exception()

    target_folder = parent_id
    root_name = None
    if not target_folder:
        target_folder, root_name = await _resolve_drive_root_folder(db, brand_id)

    try:
        with DriveClient(token) as drive:
            if target_folder == "root":
                my_drive = drive.list_children("root", mime_type="application/vnd.google-apps.folder")
                items = [{"id": f["id"], "name": f["name"]} for f in my_drive]
                try:
                    shared_with_me = drive.list_shared_with_me_folders()
                    seen = {f["id"] for f in my_drive}
                    for f in shared_with_me:
                        if f["id"] not in seen:
                            items.append({"id": f["id"], "name": f["name"]})
                except Exception:
                    pass
                try:
                    for sd in drive.list_shared_drives():
                        items.append({"id": sd["id"], "name": sd["name"]})
                except Exception:
                    pass
            else:
                subfolders = drive.list_children(target_folder, mime_type="application/vnd.google-apps.folder", all_drives=True)
                items = [{"id": f["id"], "name": f["name"]} for f in subfolders]
    except httpx.HTTPStatusError as exc:
        await _raise_drive_http_error(exc, db, brand_id)

    return {"folder_id": target_folder, "folder_name": root_name, "folders": sorted(items, key=lambda x: x["name"].lower())}


@router.get("/images", dependencies=[Depends(require_api_key)])
async def list_drive_images(
    brand_id: str,
    folder_id: Optional[str] = None,
    media_type: Optional[str] = "image",
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    DriveClient = _load_google_drive_client()
    token, _ = await get_page_token(db, brand_id, "google_drive", settings)
    if not token:
        raise _drive_reauth_exception()

    target_folder = folder_id
    if not target_folder:
        target_folder, _ = await _resolve_drive_root_folder(db, brand_id)

    image_mimes = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    doc_mimes = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/pdf",
        "application/msword",
        "application/vnd.ms-powerpoint",
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.presentation",
        "application/json",
        "text/plain",
    ]
    mime_types: dict[str, list[str]] = {
        "image": image_mimes,
        "video": ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"],
        "document": doc_mimes,
        "all": image_mimes + doc_mimes,
    }
    mimes = mime_types.get(media_type or "image", mime_types["image"])

    try:
        with DriveClient(token) as drive:
            all_files = drive.search_files(mimes, parent_id=target_folder)
    except httpx.HTTPStatusError as exc:
        await _raise_drive_http_error(exc, db, brand_id)

    query = (q or "").strip().lower()
    if query:
        all_files = [f for f in all_files if query in str(f.get("name") or "").lower()]
    all_files.sort(key=lambda f: f.get("name", ""))
    return {"folder_id": target_folder, "files": all_files}


async def _validate_api_key_query(api_key: str | None, db: AsyncSession, settings) -> None:
    if not api_key:
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "Missing api_key query parameter", "details": None}})
    if api_key == settings.api_secret_key:
        return
    from models.api_key import ApiKey
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    row = (await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key", "details": None}})


_THUMB_CACHE_DIR = Path(os.getenv("BOS_DRIVE_THUMB_CACHE_DIR", "/tmp/bos_drive_thumb_cache"))
_THUMB_CACHE_TTL = int(os.getenv("BOS_DRIVE_THUMB_CACHE_TTL", "86400"))
_THUMBNAIL_IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _thumb_cache_path(brand_id: str, file_id: str) -> Path:
    digest = hashlib.sha256(f"{brand_id}:{file_id}".encode()).hexdigest()
    return _THUMB_CACHE_DIR / f"{digest}.bin"


def _thumb_meta_path(path: Path) -> Path:
    return path.with_suffix(".json")


def _read_thumb_cache(brand_id: str, file_id: str) -> tuple[bytes, str] | None:
    path = _thumb_cache_path(brand_id, file_id)
    meta_path = _thumb_meta_path(path)
    try:
        if not path.exists() or not meta_path.exists():
            return None
        if time.time() - path.stat().st_mtime > _THUMB_CACHE_TTL:
            return None
        meta = json.loads(meta_path.read_text())
        mime = str(meta.get("mime") or "image/jpeg")
        return path.read_bytes(), mime
    except Exception:
        return None


def _write_thumb_cache(brand_id: str, file_id: str, data: bytes, mime: str) -> None:
    try:
        _THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _thumb_cache_path(brand_id, file_id)
        path.write_bytes(data)
        _thumb_meta_path(path).write_text(json.dumps({"mime": mime, "cached_at": time.time()}))
    except Exception:
        logger.debug("Could not write Drive thumbnail cache", exc_info=True)


def _validate_thumbnail_source(mime: str, size: object = None) -> str:
    normalized_mime = (mime or "").split(";")[0].strip().lower()
    if normalized_mime not in _THUMBNAIL_IMAGE_MIMES:
        raise HTTPException(status_code=415, detail={"error": {"code": "DRIVE_THUMBNAIL_NOT_IMAGE", "message": "Drive thumbnail previews only support image files.", "details": None}})
    try:
        byte_size = int(size) if size not in (None, "") else None
    except (TypeError, ValueError):
        byte_size = None
    if byte_size is not None and byte_size > _MAX_THUMBNAIL_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail={"error": {"code": "DRIVE_THUMBNAIL_TOO_LARGE", "message": "Drive image is too large to preview safely.", "details": None}})
    return normalized_mime


def _thumbnail_bytes(data: bytes, mime: str) -> tuple[bytes, str]:
    normalized_mime = _validate_thumbnail_source(mime, len(data))
    try:
        import io
        from PIL import Image
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        if len(data) <= 400_000:
            return data, normalized_mime
        with Image.open(io.BytesIO(data)) as img:
            img.thumbnail((360, 360))
            if img.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.getchannel("A"))
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=82, optimize=True)
            return out.getvalue(), "image/jpeg"
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=415, detail={"error": {"code": "DRIVE_THUMBNAIL_UNDECODABLE", "message": "Drive image could not be decoded for preview.", "details": None}}) from exc


@router.get("/thumbnail/{file_id}")
async def drive_thumbnail_proxy(
    file_id: str,
    brand_id: str,
    api_key: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    await _validate_api_key_query(api_key, db, settings)

    cached = _read_thumb_cache(brand_id, file_id)
    if cached:
        data, mime = cached
        data, mime = _thumbnail_bytes(data, mime)
        return Response(content=data, media_type=mime, headers={"Cache-Control": "private, max-age=86400"})

    DriveClient = _load_google_drive_client()
    token, _ = await get_page_token(db, brand_id, "google_drive", settings)
    if not token:
        raise _drive_reauth_exception()

    try:
        with DriveClient(token) as drive:
            meta = drive.get_file_meta(file_id)
            mime = _validate_thumbnail_source(str(meta.get("mimeType") or ""), meta.get("size"))
            data = drive.download_file(file_id)
            data, mime = _thumbnail_bytes(data, mime)
            _write_thumb_cache(brand_id, file_id, data, mime)
    except httpx.HTTPStatusError as exc:
        await _raise_drive_http_error(exc, db, brand_id)

    return Response(content=data, media_type=mime, headers={"Cache-Control": "private, max-age=86400"})


@router.post("/reference-upload", dependencies=[Depends(require_api_key)])
async def upload_drive_reference(
    body: UploadDriveReferenceRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    brand_uuid = _parse_brand_uuid(body.brand_id)
    if brand_uuid is None:
        raise HTTPException(status_code=422, detail=[{"loc": ["body", "brand_id"], "msg": "value is not a valid UUID", "type": "uuid_parsing"}])

    mime = (body.mime_type or "").strip().lower()
    if mime not in _ALLOWED_REFERENCE_IMAGE_MIMES:
        raise HTTPException(status_code=415, detail={"error": {"code": "UNSUPPORTED_REFERENCE_MIME", "message": "Only JPG, PNG, WebP, or GIF image references are supported.", "details": None}})

    raw_b64 = re.sub(r"^data:[^;]+;base64,", "", (body.data_b64 or "").strip())
    try:
        data = base64.b64decode(raw_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_BASE64", "message": "Image upload payload is not valid base64.", "details": None}}) from exc
    if not data:
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_UPLOAD", "message": "Image upload is empty.", "details": None}})
    if len(data) > _MAX_REFERENCE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={"error": {"code": "REFERENCE_TOO_LARGE", "message": "Image references are limited to 10 MB.", "details": None}})

    safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", (body.file_name or "reference-image")).strip(" ._") or "reference-image"
    token, _ = await get_page_token(db, body.brand_id, "google_drive", settings)
    if not token:
        raise _drive_reauth_exception()
    root_id, _ = await _resolve_drive_root_folder(db, body.brand_id)
    DriveClient = _load_google_drive_client()
    try:
        with DriveClient(token) as drive:
            folder_id = drive.ensure_path(["CMO References"], root_id)
            uploaded = drive.upload_file(safe_name, data, mime, folder_id)
    except httpx.HTTPStatusError as exc:
        await _raise_drive_http_error(exc, db, body.brand_id)

    result = {
        "kind": "image",
        "source": "upload",
        "title": uploaded.get("name") or safe_name,
        "drive_file_id": uploaded.get("id"),
        "drive_file_name": uploaded.get("name") or safe_name,
        "drive_web_view_link": uploaded.get("webViewLink"),
        "mime_type": uploaded.get("mimeType") or mime,
        "drive_folder_id": folder_id,
        "sha256": sha256_hex(data),
        "metadata_json": {"byte_size": len(data), "drive_folder_id": folder_id},
        "extraction_status": "vision_ready",
        "extraction_json": {"image": {"title": uploaded.get("name") or safe_name, "mime_type": uploaded.get("mimeType") or mime, "byte_size": len(data), "drive_file_id": uploaded.get("id")}},
    }
    ensure_reference_identity(result)
    ws = await get_singleton(db)
    await persist_chat_references([result], workspace_id=ws.id if ws else None, brand_id=brand_uuid, db=db)
    await db.commit()
    return result


@router.post("/attachment-upload", dependencies=[Depends(require_api_key)])
async def upload_drive_attachment(
    brand_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    brand_uuid = _parse_brand_uuid(brand_id)
    if brand_uuid is None:
        raise HTTPException(status_code=422, detail=[{"loc": ["body", "brand_id"], "msg": "value is not a valid UUID", "type": "uuid_parsing"}])

    mime = (file.content_type or "").strip().lower().split(";")[0]
    kind = _ATTACHMENT_MIME_TO_KIND.get(mime)
    if not kind:
        raise HTTPException(status_code=415, detail={"error": {"code": "UNSUPPORTED_ATTACHMENT_MIME", "message": "Supported formats: JPG, PNG, WebP, GIF, DOCX, DOC, PPTX, PPT, PDF, JSON, TXT.", "details": None}})

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_UPLOAD", "message": "Attachment upload is empty.", "details": None}})
    if len(data) > _MAX_ATTACHMENT_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={"error": {"code": "ATTACHMENT_TOO_LARGE", "message": "Attachments are limited to 25 MB.", "details": None}})

    safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", (file.filename or "attachment")).strip(" ._") or "attachment"
    token, _ = await get_page_token(db, brand_id, "google_drive", settings)
    if not token:
        raise _drive_reauth_exception()
    root_id, _ = await _resolve_drive_root_folder(db, brand_id)
    DriveClient = _load_google_drive_client()
    try:
        with DriveClient(token) as drive:
            folder_id = drive.ensure_path(["CMO References"], root_id)
            uploaded = drive.upload_file(safe_name, data, mime, folder_id)
    except httpx.HTTPStatusError as exc:
        await _raise_drive_http_error(exc, db, brand_id)

    result = {
        "kind": kind,
        "source": "upload",
        "title": uploaded.get("name") or safe_name,
        "drive_file_id": uploaded.get("id"),
        "drive_file_name": uploaded.get("name") or safe_name,
        "drive_web_view_link": uploaded.get("webViewLink"),
        "mime_type": uploaded.get("mimeType") or mime,
        "drive_folder_id": folder_id,
        "sha256": sha256_hex(data),
        "metadata_json": {"byte_size": len(data), "drive_folder_id": folder_id},
    }
    ensure_reference_identity(result)
    if kind == "document":
        try:
            text = extract_doc_text(data, mime).strip()
            result["text"] = text[:DOC_EXTRACT_CAP] if text else ""
            result["extraction_status"] = "read" if result["text"] else "empty"
            result["extracted_chars"] = len(result["text"] or "")
            apply_extraction_json(result)
        except Exception as exc:
            result["extraction_status"] = "failed"
            result["extraction_error"] = str(exc)[:500]
    else:
        result["extraction_status"] = "vision_ready"
        result["extraction_json"] = {"image": {"title": result["title"], "mime_type": result["mime_type"], "byte_size": len(data), "drive_file_id": result["drive_file_id"]}}
    ws = await get_singleton(db)
    await persist_chat_references([result], workspace_id=ws.id if ws else None, brand_id=brand_uuid, db=db)
    await db.commit()
    return result


@router.post("/root", dependencies=[Depends(require_api_key)])
async def set_drive_root(
    body: SetDriveRootRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    brand_uuid = _parse_brand_uuid(body.brand_id)
    if brand_uuid is None:
        raise HTTPException(status_code=422, detail=[{"loc": ["body", "brand_id"], "msg": "value is not a valid UUID", "type": "uuid_parsing"}])
    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand_uuid,
            SocialConnection.platform == "google_drive",
            SocialConnection.status == "connected",
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail={"error": {"code": "DRIVE_NOT_CONNECTED", "message": "Connect Google Drive for this brand first", "details": None}})
    if body.folder_id == "root":
        raise HTTPException(status_code=400, detail={"error": {"code": "DRIVE_ROOT_REQUIRED", "message": "Choose a Brand Kit folder inside My Drive; My Drive itself cannot be used as the Brand Kit root.", "details": None}})

    DriveClient = _load_google_drive_client()
    token, _ = await get_page_token(db, body.brand_id, "google_drive", settings)
    if not token:
        raise _drive_reauth_exception()

    try:
        with DriveClient(token) as drive:
            folder_meta = drive.get_file_meta(body.folder_id)
            if folder_meta.get("mimeType") != "application/vnd.google-apps.folder":
                raise HTTPException(status_code=400, detail={"error": {"code": "DRIVE_ROOT_NOT_FOLDER", "message": "Select a Google Drive folder, not a file.", "details": None}})
            # Keep Brand Kit resource indexing aligned with /social/drive/images:
            # both scan the selected root recursively so references/templates in
            # Brand Assets, Templates, or campaign subfolders are classifiable.
            image_files = drive.search_files(_BRAND_KIT_IMAGE_MIMES, parent_id=body.folder_id)
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        await _raise_drive_http_error(exc, db, body.brand_id)

    folder_name = body.folder_name or folder_meta.get("name")
    validation = _brand_kit_asset_validation(body.folder_id, folder_name, image_files)
    logo_files = validation["logo_files"]
    creative_reference_files = validation["creative_reference_files"]
    visual_asset_files = validation["visual_asset_files"]
    if not logo_files:
        raise HTTPException(status_code=400, detail={"error": {"code": "DRIVE_ROOT_MISSING_LOGO", "message": "Selected Brand Kit folder must contain at least one image named like logo, wordmark, brandmark, or mark before image/video generators can run.", "details": None}})

    meta = dict(row.token_meta_json or {})
    drive_root_path = _resolve_drive_root_path(meta, body.folder_id, body.folder_path)
    meta["drive_root_folder_id"] = body.folder_id
    meta["drive_root_name"] = folder_name
    meta["drive_root_path"] = drive_root_path
    meta["imprint_asset_validation"] = validation
    row.token_meta_json = meta
    await db.commit()
    return {
        "status": "ok",
        "drive_root_folder_id": body.folder_id,
        "drive_root_name": body.folder_name or folder_meta.get("name"),
        "drive_root_path": meta.get("drive_root_path"),
        "image_count": len(image_files),
        "logo_count": len(logo_files),
        "creative_reference_count": len(creative_reference_files),
        "visual_asset_count": len(visual_asset_files),
    }

# Export one plugin-owned router for the host shell to mount.
_root_router = APIRouter(tags=["google-drive"])
_root_router.include_router(callback_router)
_root_router.include_router(drive_router)
router = _root_router
