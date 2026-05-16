from __future__ import annotations

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
from provider_auth import encrypt_secret, decrypt_secret, get_oauth_handler
from routers.workspace import get_singleton

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

    try:
        start = await handler.start_login(settings)
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
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    frontend = settings.frontend_url.rstrip("/")

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
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    logger.info("Calendar callback received — code=%r state=%r error=%r all_params=%s",
                code[:8] + "..." if code else "", state[:8] + "..." if state else "", error,
                dict(request.query_params))
    frontend = settings.frontend_url.rstrip("/")

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
