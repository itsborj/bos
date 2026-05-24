from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from models.provider import ProviderLoginSession
from models.social import SocialConnection
from models.workspace import Brand
from plugin_loader import get_plugin_vars
from provider_auth import (
    encrypt_secret,
    decrypt_secret,
    get_oauth_handler,
    relay_claim_handoff,
    relay_refresh_token,
    GOOGLE_RELAY_PLATFORMS,
)
from routers.workspace import get_singleton

# Platforms that load OAuth app credentials from plugin vars (DB) rather than .env
_PLATFORM_PLUGIN_ID: dict[str, str] = {
    "facebook": "channel.meta",
    "tiktok": "channel.tiktok",
}

router = APIRouter(prefix="/social", tags=["social"])
logger = logging.getLogger("bos.social")


# ── Schemas ──────────────────────────────────────────────────────────────────

class ConnectStartRequest(BaseModel):
    brand_id: str
    platform: str = "gmail"


class ConnectStartResponse(BaseModel):
    session_id: str
    authorize_url: str
    platform: str


class SocialConnectionResponse(BaseModel):
    id: str
    brand_id: Optional[str]
    platform: str
    page_id: str
    page_name: Optional[str]
    page_handle: Optional[str]
    status: str


class SelectPageRequest(BaseModel):
    session_id: str
    page_id: str


def _admin_connectors_redirect(frontend: str, **params: str | None) -> RedirectResponse:
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    qs = urlencode(clean)
    suffix = f"?{qs}" if qs else ""
    return RedirectResponse(url=f"{frontend}/admin/connectors{suffix}")


def _admin_brands_redirect(frontend: str, **params: str | None) -> RedirectResponse:
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    qs = urlencode(clean)
    suffix = f"?{qs}" if qs else ""
    return RedirectResponse(url=f"{frontend}/admin/brands{suffix}")


# ── Start OAuth ───────────────────────────────────────────────────────────────

@router.post("/connect/start", response_model=ConnectStartResponse, dependencies=[Depends(require_api_key)])
async def start_social_connect(
    body: ConnectStartRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    handler = get_oauth_handler(body.platform)
    if not handler:
        raise HTTPException(status_code=400, detail={"error": {"code": "PLATFORM_NOT_SUPPORTED", "message": f"Platform '{body.platform}' does not support OAuth connect", "details": None}})

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail={"error": {"code": "WORKSPACE_NOT_INITIALIZED", "message": "Initialize workspace first", "details": None}})

    try:
        brand_uuid = uuid.UUID(body.brand_id)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_BRAND_ID", "message": "Invalid brand ID", "details": None}})
    brand = (await db.execute(
        select(Brand).where(Brand.id == brand_uuid, Brand.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail={"error": {"code": "BRAND_NOT_FOUND", "message": "Brand not found", "details": None}})

    plugin_id = _PLATFORM_PLUGIN_ID.get(body.platform)
    plugin_vars = await get_plugin_vars(plugin_id, db, settings) if plugin_id else {}

    try:
        start = await handler.start_login(settings, overrides=plugin_vars) if plugin_id else await handler.start_login(settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=412,
            detail={
                "error": {
                    "code": "PROVIDER_CONFIG_MISSING",
                    "message": str(exc),
                    "details": {"platform": body.platform},
                }
            },
        ) from exc

    session = ProviderLoginSession(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        provider=body.platform,
        login_type=start.login_type,
        state=start.state,
        verifier_encrypted=encrypt_secret(start.verifier or start.state, settings),
        redirect_uri=start.redirect_uri or "",
    )
    db.add(session)
    session.verifier_encrypted = encrypt_secret(f"{start.verifier or start.state}|{body.brand_id}", settings)
    await db.commit()

    return ConnectStartResponse(
        session_id=str(session.id),
        authorize_url=start.authorize_url,
        platform=body.platform,
    )


# ── Gmail OAuth Callback ──────────────────────────────────────────────────────

@router.get("/gmail/callback")
async def gmail_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    handoff_token: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    frontend = settings.frontend_url.rstrip("/")

    if handoff_token and settings.klaroha_relay_url:
        try:
            payload = await relay_claim_handoff(handoff_token, settings)
        except Exception:
            return _admin_connectors_redirect(frontend, gmail="error", reason="relay_claim_failed")
        meta = payload.get("metadata") or {}
        email = meta.get("email", "")
        brand_id = payload.get("brand_id") or ""
        if not email:
            return _admin_connectors_redirect(frontend, gmail="error", reason="no_email_returned")
        ws = await get_singleton(db)
        token_meta = None
        if payload.get("refresh_token"):
            token_meta = {
                "refresh_token_encrypted": encrypt_secret(payload["refresh_token"], settings),
                "expires_at": payload.get("expires_at"),
            }
        await _store_connection(db, ws.id, brand_id or None, settings, "gmail", {
            "id": email, "access_token": payload["access_token"],
            "name": meta.get("name") or email, "username": email, "token_meta": token_meta,
        })
        await db.commit()
        return _admin_connectors_redirect(frontend, gmail="connected", brand_id=brand_id, account=email)

    if error or not code:
        return _admin_connectors_redirect(frontend, gmail="denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "gmail",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_connectors_redirect(frontend, gmail="error", reason="session_not_found")

    raw = decrypt_secret(session.verifier_encrypted, settings)
    stored_verifier, brand_id = (raw.split("|", 1) + [""])[:2]

    ws = await get_singleton(db)
    handler = get_oauth_handler("gmail")

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
        return _admin_connectors_redirect(frontend, gmail="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    email = metadata.get("email", "")
    if not email:
        await db.delete(session)
        await db.commit()
        return _admin_connectors_redirect(frontend, gmail="error", reason="no_email_returned")

    token_meta = None
    if credential.refresh_token:
        token_meta = {
            "refresh_token_encrypted": encrypt_secret(credential.refresh_token, settings),
            "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
        }

    page = {
        "id": email,
        "access_token": credential.access_token,
        "name": metadata.get("name") or email,
        "username": email,
        "token_meta": token_meta,
    }

    await _store_connection(db, ws.id, brand_id or None, settings, "gmail", page)
    await db.delete(session)
    await db.commit()
    return _admin_connectors_redirect(frontend, gmail="connected", brand_id=brand_id, account=email)


# ── Google Calendar OAuth Callback ───────────────────────────────────────────

@router.get("/google-calendar/callback")
async def google_calendar_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    handoff_token: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    logger.info("Calendar callback received — code=%r state=%r error=%r all_params=%s",
                code[:8] + "..." if code else "", state[:8] + "..." if state else "", error,
                dict(request.query_params))
    frontend = settings.frontend_url.rstrip("/")

    if handoff_token and settings.klaroha_relay_url:
        try:
            payload = await relay_claim_handoff(handoff_token, settings)
        except Exception:
            return _admin_connectors_redirect(frontend, google_calendar="error", reason="relay_claim_failed")
        meta = payload.get("metadata") or {}
        email = meta.get("email", "")
        brand_id = payload.get("brand_id") or ""
        if not email:
            return _admin_connectors_redirect(frontend, google_calendar="error", reason="no_email_returned")
        ws = await get_singleton(db)
        token_meta = None
        if payload.get("refresh_token"):
            token_meta = {
                "refresh_token_encrypted": encrypt_secret(payload["refresh_token"], settings),
                "expires_at": payload.get("expires_at"),
            }
        await _store_connection(db, ws.id, brand_id or None, settings, "google_calendar", {
            "id": email, "access_token": payload["access_token"],
            "name": meta.get("name") or email, "username": email, "token_meta": token_meta,
        })
        await db.commit()
        return _admin_connectors_redirect(frontend, google_calendar="connected", brand_id=brand_id, account=email)

    if error or not code:
        return _admin_connectors_redirect(frontend, google_calendar="denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "google_calendar",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_connectors_redirect(frontend, google_calendar="error", reason="session_not_found")

    raw = decrypt_secret(session.verifier_encrypted, settings)
    stored_verifier, brand_id = (raw.split("|", 1) + [""])[:2]

    ws = await get_singleton(db)
    handler = get_oauth_handler("google_calendar")

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
        return _admin_connectors_redirect(frontend, google_calendar="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    email = metadata.get("email", "")
    if not email:
        await db.delete(session)
        await db.commit()
        return _admin_connectors_redirect(frontend, google_calendar="error", reason="no_email_returned")

    token_meta = None
    if credential.refresh_token:
        token_meta = {
            "refresh_token_encrypted": encrypt_secret(credential.refresh_token, settings),
            "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
        }

    page = {
        "id": email,
        "access_token": credential.access_token,
        "name": metadata.get("name") or email,
        "username": email,
        "token_meta": token_meta,
    }

    await _store_connection(db, ws.id, brand_id or None, settings, "google_calendar", page)
    await db.delete(session)
    await db.commit()
    return _admin_connectors_redirect(frontend, google_calendar="connected", brand_id=brand_id, account=email)


# ── YouTube OAuth Callback ──────────────────────────────────────────────────

@router.get("/youtube/callback")
async def youtube_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    handoff_token: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    frontend = settings.frontend_url.rstrip("/")

    if handoff_token and settings.klaroha_relay_url:
        try:
            payload = await relay_claim_handoff(handoff_token, settings)
        except Exception:
            return _admin_connectors_redirect(frontend, youtube="error", reason="relay_claim_failed")
        meta = payload.get("metadata") or {}
        email = meta.get("email", "")
        channel_id = meta.get("channel_id", "")
        brand_id = payload.get("brand_id") or ""
        if not email or not channel_id:
            return _admin_connectors_redirect(frontend, youtube="error", reason="incomplete_metadata")
        ws = await get_singleton(db)
        token_meta = None
        if payload.get("refresh_token"):
            token_meta = {
                "refresh_token_encrypted": encrypt_secret(payload["refresh_token"], settings),
                "expires_at": payload.get("expires_at"),
            }
        await _store_connection(db, ws.id, brand_id or None, settings, "youtube", {
            "id": channel_id, "access_token": payload["access_token"],
            "name": meta.get("name") or email, "username": email, "token_meta": token_meta,
        })
        await db.commit()
        return _admin_connectors_redirect(frontend, youtube="connected", brand_id=brand_id, account=meta.get("name") or email)

    if error or not code:
        return _admin_connectors_redirect(frontend, youtube="denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "youtube",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_connectors_redirect(frontend, youtube="error", reason="session_not_found")

    raw = decrypt_secret(session.verifier_encrypted, settings)
    stored_verifier, brand_id = (raw.split("|", 1) + [""])[:2]

    ws = await get_singleton(db)
    handler = get_oauth_handler("youtube")

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
        return _admin_connectors_redirect(frontend, youtube="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    email = metadata.get("email", "")
    channel_id = metadata.get("channel_id", "")

    if not email or not channel_id:
        await db.delete(session)
        await db.commit()
        return _admin_connectors_redirect(frontend, youtube="error", reason="incomplete_metadata")

    token_meta = None
    if credential.refresh_token:
        token_meta = {
            "refresh_token_encrypted": encrypt_secret(credential.refresh_token, settings),
            "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
        }

    page = {
        "id": channel_id,
        "access_token": credential.access_token,
        "name": metadata.get("name") or email,
        "username": email,
        "token_meta": token_meta,
    }

    await _store_connection(db, ws.id, brand_id or None, settings, "youtube", page)
    await db.delete(session)
    await db.commit()
    return _admin_connectors_redirect(frontend, youtube="connected", brand_id=brand_id, account=metadata.get("name") or email)


# ── TikTok OAuth Callback ────────────────────────────────────────────────────

@router.get("/tiktok/callback")
async def tiktok_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    frontend = settings.frontend_url.rstrip("/")

    if error or not code:
        return _admin_connectors_redirect(frontend, tiktok="denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "tiktok",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_connectors_redirect(frontend, tiktok="error", reason="session_not_found")

    raw = decrypt_secret(session.verifier_encrypted, settings)
    stored_verifier, brand_id = (raw.split("|", 1) + [""])[:2]

    ws = await get_singleton(db)
    handler = get_oauth_handler("tiktok")
    plugin_vars = await get_plugin_vars("channel.tiktok", db, settings)

    try:
        credential = await handler.complete_login(
            code,
            settings,
            state=session.state,
            verifier=stored_verifier,
            redirect_uri=session.redirect_uri,
            overrides=plugin_vars,
        )
    except Exception:
        await db.delete(session)
        await db.commit()
        return _admin_connectors_redirect(frontend, tiktok="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    open_id = metadata.get("open_id", "")
    if not open_id:
        await db.delete(session)
        await db.commit()
        return _admin_connectors_redirect(frontend, tiktok="error", reason="no_account_returned")

    token_meta = None
    if credential.refresh_token:
        token_meta = {
            "refresh_token_encrypted": encrypt_secret(credential.refresh_token, settings),
            "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
        }
        if metadata.get("refresh_expires_at"):
            token_meta["refresh_expires_at"] = metadata["refresh_expires_at"]

    page = {
        "id": open_id,
        "access_token": credential.access_token,
        "name": metadata.get("display_name") or open_id,
        "username": metadata.get("profile_deep_link") or None,
        "token_meta": token_meta,
    }

    await _store_connection(db, ws.id, brand_id or None, settings, "tiktok", page)
    await db.delete(session)
    await db.commit()
    return _admin_connectors_redirect(frontend, tiktok="connected", brand_id=brand_id, account=metadata.get("display_name") or open_id)


# ── Google Drive OAuth Callback ───────────────────────────────────────────────

@router.get("/google-drive/callback")
async def google_drive_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    handoff_token: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
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
        await _store_connection(db, ws.id, brand_id or None, settings, "google_drive", {
            "id": email, "access_token": payload["access_token"],
            "name": meta.get("name") or email, "username": email, "token_meta": token_meta,
        })
        await db.commit()
        return _admin_brands_redirect(frontend, google_drive="connected", brand_id=brand_id, account=meta.get("name") or email)

    if error or not code:
        return _admin_brands_redirect(frontend, google_drive="denied", reason=error or "no_code")

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

    page = {
        # page_id is the stable connection identity (the Drive account email).
        # The per-brand root folder ID is created later by drive.folder.setup.
        "id": email,
        "access_token": credential.access_token,
        "name": metadata.get("name") or email,
        "username": email,
        "token_meta": token_meta,
    }

    await _store_connection(db, ws.id, brand_id or None, settings, "google_drive", page)
    await db.delete(session)
    await db.commit()
    return _admin_brands_redirect(frontend, google_drive="connected", brand_id=brand_id, account=metadata.get("name") or email)


# ── Google Drive folder selection (Google Picker) ─────────────────────────────

class SetDriveRootRequest(BaseModel):
    brand_id: str
    folder_id: str
    folder_name: Optional[str] = None
    folder_path: Optional[str] = None


@router.get("/drive/picker-config", dependencies=[Depends(require_api_key)])
async def drive_picker_config(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    """Return what the browser Google Picker needs: a fresh OAuth token, the browser
    API key, and the app (project) id. The token is the operator's own Drive token —
    exposed only to the authenticated admin UI for the Picker session."""
    token, _ = await get_page_token(db, brand_id, "google_drive", settings)
    if not token:
        raise HTTPException(status_code=404, detail={"error": {"code": "DRIVE_NOT_CONNECTED", "message": "Connect Google Drive for this brand first", "details": None}})
    if not settings.google_picker_api_key:
        raise HTTPException(status_code=412, detail={"error": {"code": "PICKER_KEY_MISSING", "message": "GOOGLE_PICKER_API_KEY is not configured", "details": None}})
    app_id = (settings.google_client_id or "").split("-", 1)[0]
    return {"access_token": token, "api_key": settings.google_picker_api_key, "app_id": app_id}


@router.get("/drive/images", dependencies=[Depends(require_api_key)])
async def list_drive_images(
    brand_id: str,
    folder_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    """List image files from the brand's connected Google Drive folder.

    Uses the folder_id query param if supplied, otherwise the brand's stored
    drive_root_folder_id. Falls back to Drive 'root' if nothing is set.
    """
    import sys
    import os
    plugin_dir = os.path.join(os.path.dirname(__file__), "..", "plugins", "google-drive")
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)
    from drive_client import DriveClient

    token, _ = await get_page_token(db, brand_id, "google_drive", settings)
    if not token:
        raise HTTPException(status_code=404, detail={"error": {"code": "DRIVE_NOT_CONNECTED", "message": "Connect Google Drive for this brand first", "details": None}})

    # Resolve target folder
    target_folder = folder_id
    if not target_folder:
        row = (await db.execute(
            select(SocialConnection).where(
                SocialConnection.brand_id == uuid.UUID(brand_id),
                SocialConnection.platform == "google_drive",
                SocialConnection.status == "connected",
            ).order_by(SocialConnection.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        target_folder = ((row.token_meta_json or {}).get("drive_root_folder_id") if row else None) or "root"

    with DriveClient(token) as drive:
        all_files: list[dict] = []
        for mime in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            items = drive.list_children(target_folder, mime_type=mime)
            all_files.extend(items)

    # De-duplicate by id (list_children per mime can return overlaps)
    seen: set[str] = set()
    unique = []
    for f in all_files:
        if f["id"] not in seen:
            seen.add(f["id"])
            unique.append(f)
    unique.sort(key=lambda f: f.get("name", ""))

    return {"folder_id": target_folder, "files": unique}


@router.post("/drive/root", dependencies=[Depends(require_api_key)])
async def set_drive_root(
    body: SetDriveRootRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    """Store the operator-picked root folder on the brand's Drive connection.
    The creative factory, channel specialists, and CMO resolve asset paths from here."""
    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == uuid.UUID(body.brand_id),
            SocialConnection.platform == "google_drive",
            SocialConnection.status == "connected",
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail={"error": {"code": "DRIVE_NOT_CONNECTED", "message": "Connect Google Drive for this brand first", "details": None}})

    meta = dict(row.token_meta_json or {})
    meta["drive_root_folder_id"] = body.folder_id
    meta["drive_root_name"] = body.folder_name
    meta["drive_root_path"] = body.folder_path
    row.token_meta_json = meta
    await db.commit()
    return {
        "status": "ok",
        "drive_root_folder_id": body.folder_id,
        "drive_root_name": body.folder_name,
        "drive_root_path": body.folder_path,
    }


# ── Facebook OAuth Callback ───────────────────────────────────────────────────

@router.get("/facebook/callback")
async def facebook_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    frontend = settings.frontend_url.rstrip("/")

    if error or not code:
        return _admin_brands_redirect(frontend, facebook="denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "facebook",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_brands_redirect(frontend, facebook="error", reason="session_not_found")

    raw = decrypt_secret(session.verifier_encrypted, settings)
    _, brand_id = (raw.split("|", 1) + [""])[:2]

    handler = get_oauth_handler("facebook")
    plugin_vars = await get_plugin_vars("channel.meta", db, settings)

    try:
        credential = await handler.complete_login(
            code,
            settings,
            state=session.state,
            verifier=session.state,
            redirect_uri=session.redirect_uri,
            overrides=plugin_vars,
        )
    except Exception:
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, facebook="error", reason="token_exchange_failed")

    pages = (credential.metadata or {}).get("pages", [])

    if not pages:
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, facebook="error", reason="no_pages_found")

    ws = await get_singleton(db)

    if len(pages) == 1:
        page = pages[0]
        await _store_connection(db, ws.id, brand_id or None, settings, "facebook", {
            "id": page["id"],
            "name": page["name"],
            "access_token": page["access_token"],
            "username": None,
            "token_meta": {"ig_account_id": page.get("ig_account_id")},
        })
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, facebook="connected", brand_id=brand_id, account=page["name"])

    # Multiple pages: store pages in session for user selection
    session.verifier_encrypted = encrypt_secret(
        json.dumps({"brand_id": brand_id or "", "pages": pages}), settings
    )
    await db.commit()
    return _admin_brands_redirect(frontend, facebook="select_page", session_id=str(session.id))


@router.get("/facebook/pending-pages", dependencies=[Depends(require_api_key)])
async def facebook_pending_pages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_SESSION", "message": "Invalid session_id", "details": None}})

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.id == sid,
            ProviderLoginSession.provider == "facebook",
        )
    )).scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session not found or expired", "details": None}})

    try:
        data = json.loads(decrypt_secret(session.verifier_encrypted, settings))
        pages = data.get("pages", [])
    except Exception:
        raise HTTPException(status_code=400, detail={"error": {"code": "SESSION_CORRUPT", "message": "Could not read session data", "details": None}})

    return {"pages": [{"id": p["id"], "name": p["name"]} for p in pages]}


@router.post("/facebook/select-page", dependencies=[Depends(require_api_key)])
async def facebook_select_page(
    body: SelectPageRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    try:
        sid = uuid.UUID(body.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_SESSION", "message": "Invalid session_id", "details": None}})

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.id == sid,
            ProviderLoginSession.provider == "facebook",
        )
    )).scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session not found or expired", "details": None}})

    try:
        data = json.loads(decrypt_secret(session.verifier_encrypted, settings))
        brand_id = data.get("brand_id") or None
        pages = data.get("pages", [])
    except Exception:
        raise HTTPException(status_code=400, detail={"error": {"code": "SESSION_CORRUPT", "message": "Could not read session data", "details": None}})

    page = next((p for p in pages if p["id"] == body.page_id), None)
    if not page:
        raise HTTPException(status_code=404, detail={"error": {"code": "PAGE_NOT_FOUND", "message": f"Page {body.page_id!r} not in session", "details": None}})

    ws = await get_singleton(db)
    await _store_connection(db, ws.id, brand_id, settings, "facebook", {
        "id": page["id"],
        "name": page["name"],
        "access_token": page["access_token"],
        "username": None,
        "token_meta": {"ig_account_id": page.get("ig_account_id")},
    })
    await db.delete(session)
    await db.commit()
    return {"status": "connected", "page_id": page["id"], "page_name": page["name"]}


# ── Direct token storage (admin / dev bypass) ─────────────────────────────────

class FacebookDirectConnectRequest(BaseModel):
    brand_id: str
    page_id: str
    page_name: str
    page_token: str


@router.post("/facebook/direct-connect", dependencies=[Depends(require_api_key)])
async def facebook_direct_connect(
    body: FacebookDirectConnectRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    """Store a Facebook page token directly without OAuth — admin/dev use when OAuth
    redirect is misconfigured or for testing with a manually obtained page token.
    """
    try:
        brand_uuid = uuid.UUID(body.brand_id)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_BRAND_ID", "message": "Invalid brand_id", "details": None}})

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    brand = (await db.execute(
        select(Brand).where(Brand.id == brand_uuid, Brand.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail={"error": {"code": "BRAND_NOT_FOUND", "message": "Brand not found", "details": None}})

    conn = await _store_connection(db, ws.id, body.brand_id, settings, "facebook", {
        "id": body.page_id,
        "name": body.page_name,
        "access_token": body.page_token,
        "username": None,
        "token_meta": {},
    })
    await db.commit()
    return {"status": "connected", "page_id": conn.page_id, "page_name": conn.page_name, "brand_id": body.brand_id}


# ── List connections ──────────────────────────────────────────────────────────

@router.get("/connections", response_model=list[SocialConnectionResponse], dependencies=[Depends(require_api_key)])
async def list_connections(
    brand_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    ws = await get_singleton(db)
    q = select(SocialConnection).where(SocialConnection.workspace_id == ws.id)
    if brand_id:
        q = q.where(SocialConnection.brand_id == uuid.UUID(brand_id))
    rows = (await db.execute(q.order_by(SocialConnection.created_at.desc()))).scalars().all()
    return [
        SocialConnectionResponse(
            id=str(r.id),
            brand_id=str(r.brand_id) if r.brand_id else None,
            platform=r.platform,
            page_id=r.page_id,
            page_name=r.page_name,
            page_handle=r.page_handle,
            status=r.status,
        )
        for r in rows
    ]


# ── Disconnect ────────────────────────────────────────────────────────────────

@router.delete("/connections/{connection_id}", dependencies=[Depends(require_api_key)])
async def disconnect(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    ws = await get_singleton(db)
    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.id == uuid.UUID(connection_id),
            SocialConnection.workspace_id == ws.id,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Connection not found", "details": None}})
    await db.delete(row)
    await db.commit()
    return {"status": "disconnected"}


# ── Token resolution helper ────────────────────────────────────────────────────

async def get_page_token(db: AsyncSession, brand_id: str, platform: str, settings) -> tuple[str, str] | tuple[None, None]:
    """Resolve a decrypted access token and page_id for a brand + platform.

    Auto-refreshes tokens within 5 minutes of expiry when a refresh token is stored.
    """
    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == uuid.UUID(brand_id),
            SocialConnection.platform == platform,
            SocialConnection.status == "connected",
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not row:
        return None, None

    meta = row.token_meta_json or {}
    expires_at_str = meta.get("expires_at")
    refresh_token_enc = meta.get("refresh_token_encrypted")

    if expires_at_str and refresh_token_enc:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) >= expires_at - timedelta(minutes=5):
            handler = get_oauth_handler(platform)
            if handler:
                try:
                    refresh_token = decrypt_secret(refresh_token_enc, settings)
                    if settings.klaroha_relay_url and platform in GOOGLE_RELAY_PLATFORMS:
                        refreshed = await relay_refresh_token(platform, refresh_token, settings)
                    else:
                        plugin_id = _PLATFORM_PLUGIN_ID.get(platform)
                        plugin_vars = await get_plugin_vars(plugin_id, db, settings) if plugin_id else {}
                        try:
                            refreshed = await handler.refresh_auth(refresh_token, settings, overrides=plugin_vars) if plugin_id else await handler.refresh_auth(refresh_token, settings)
                        except TypeError:
                            refreshed = await handler.refresh_auth(refresh_token, settings)
                    row.access_token_encrypted = encrypt_secret(refreshed.access_token, settings)
                    new_meta = dict(meta)
                    new_meta["expires_at"] = refreshed.expires_at.isoformat() if refreshed.expires_at else None
                    if refreshed.refresh_token:
                        new_meta["refresh_token_encrypted"] = encrypt_secret(refreshed.refresh_token, settings)
                    row.token_meta_json = new_meta
                    await db.commit()
                    return refreshed.access_token, row.page_id
                except Exception:
                    pass

    return decrypt_secret(row.access_token_encrypted, settings), row.page_id


async def _store_connection(db, workspace_id, brand_id, settings, platform: str, page: dict) -> SocialConnection:
    brand_uuid = uuid.UUID(brand_id) if brand_id else None
    existing = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand_uuid,
            SocialConnection.platform == platform,
            SocialConnection.page_id == page["id"],
        )
    )).scalar_one_or_none()

    token_encrypted = encrypt_secret(page["access_token"], settings)
    token_meta = page.get("token_meta")

    if existing:
        existing.access_token_encrypted = token_encrypted
        existing.page_name = page.get("name")
        existing.page_handle = page.get("username")
        existing.token_meta_json = token_meta
        existing.status = "connected"
        return existing

    conn = SocialConnection(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        brand_id=brand_uuid,
        platform=platform,
        page_id=page["id"],
        page_name=page.get("name"),
        page_handle=page.get("username"),
        access_token_encrypted=token_encrypted,
        token_meta_json=token_meta,
        status="connected",
    )
    db.add(conn)
    return conn
