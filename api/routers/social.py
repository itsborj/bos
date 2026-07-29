from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from attachment_context import DOC_EXTRACT_CAP, apply_extraction_json, ensure_reference_identity, extract_doc_text, persist_chat_references, sha256_hex
from auth import require_api_key
from config import get_settings
from db import get_db
from models.provider import ProviderKey, ProviderLoginSession
from models.document import WorkspaceDocument
from models.social import SocialConnection
from models.workspace import Brand
from plugin_loader import get_plugin_id_for_connection, get_plugin_vars
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
    "instagram": "channel.meta",
    "tiktok": "channel.tiktok",
}


def _normalize_platform_key(platform: str | None) -> str:
    return str(platform or "").strip().lower().replace("-", "_")


def _plugin_id_for_platform(platform: str) -> str | None:
    key = _normalize_platform_key(platform)
    return _PLATFORM_PLUGIN_ID.get(key) or get_plugin_id_for_connection(key)


router = APIRouter(prefix="/social", tags=["social"])
logger = logging.getLogger("bos.social")


def _load_google_drive_client():
    import importlib.util
    from pathlib import Path

    candidates = [Path("/external_plugins/google-drive/drive_client.py")]
    try:
        from plugin_loader import get_loaded_plugins
        state = get_loaded_plugins().get("google.drive")
        if state:
            candidates.insert(0, state.root_path / "drive_client.py")
    except Exception:
        pass

    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location("_bos_social_drive_client", path)
            module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            return module.DriveClient
    raise FileNotFoundError("google-drive/drive_client.py not found")


def _parse_brand_uuid(brand_id: str | None, field: str = "brand_id") -> uuid.UUID | None:
    """Return a UUID or raise 422. Treats None and the string 'null' as absent."""
    if brand_id is None or brand_id == "" or brand_id == "null":
        return None
    try:
        return uuid.UUID(brand_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["query", field], "msg": "value is not a valid UUID", "type": "uuid_parsing"}],
        )


def _coerce_datetime(value) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


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
    return RedirectResponse(url=f"{frontend}/admin/modules{suffix}", status_code=302)


def _admin_brands_redirect(frontend: str, **params: str | None) -> RedirectResponse:
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    qs = urlencode(clean)
    suffix = f"?{qs}" if qs else ""
    return RedirectResponse(url=f"{frontend}/admin/brands{suffix}", status_code=302)


def _admin_providers_redirect(frontend: str, **params: str | None) -> RedirectResponse:
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    qs = urlencode(clean)
    suffix = f"?{qs}" if qs else ""
    return RedirectResponse(url=f"{frontend}/admin/providers{suffix}", status_code=302)


def _oauth_callback_status(error: str) -> str:
    """Return UI status for OAuth provider errors.

    Google returns `access_denied` for user cancellation. Relay/config/session
    failures also arrive in the `error` slot but should be shown as failures,
    not as a cancelled consent flow.
    """
    return "denied" if error in {"access_denied", "user_denied", "user_cancelled"} else "error"


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
    if body.platform == "gemini":
        raise HTTPException(status_code=400, detail={"error": {"code": "USE_PROVIDER_LOGIN", "message": "Gemini is a workspace AI provider. Connect it from Admin → AI Providers, not brand social connections.", "details": None}})

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail={"error": {"code": "WORKSPACE_NOT_INITIALIZED", "message": "Initialize workspace first", "details": None}})

    try:
        brand_uuid = uuid.UUID(body.brand_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", "brand_id"], "msg": "value is not a valid UUID", "type": "uuid_parsing"}],
        )
    brand = (await db.execute(
        select(Brand).where(Brand.id == brand_uuid, Brand.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail={"error": {"code": "BRAND_NOT_FOUND", "message": "Brand not found", "details": None}})

    # Relay mode — Google platforms use central auth relay (no local client credentials needed)
    if settings.klaroha_relay_url and body.platform in GOOGLE_RELAY_PLATFORMS:
        relay = settings.klaroha_relay_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{relay}/relay/{body.platform}/start",
                    params={
                        "instance_url": settings.frontend_url,
                        "relay_key": settings.klaroha_relay_key,
                        "brand_id": body.brand_id,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={"error": {"code": "RELAY_UNAVAILABLE", "message": f"Auth relay error: {exc}", "details": None}},
            ) from exc
        return ConnectStartResponse(
            session_id=data.get("session_id", "relay"),
            authorize_url=data["authorize_url"],
            platform=body.platform,
        )

    plugin_id = _plugin_id_for_platform(body.platform)
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
            return _admin_brands_redirect(frontend, gmail="error", reason="relay_claim_failed")
        meta = payload.get("metadata") or {}
        email = meta.get("email", "")
        brand_id = payload.get("brand_id") or ""
        if not email:
            return _admin_brands_redirect(frontend, gmail="error", reason="no_email_returned")
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
        return _admin_brands_redirect(frontend, gmail="connected", brand_id=brand_id, account=email)

    if error or not code:
        return _admin_brands_redirect(frontend, gmail=_oauth_callback_status(error) if error else "denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "gmail",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_brands_redirect(frontend, gmail="error", reason="session_not_found")

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
        return _admin_brands_redirect(frontend, gmail="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    email = metadata.get("email", "")
    if not email:
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, gmail="error", reason="no_email_returned")

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
    return _admin_brands_redirect(frontend, gmail="connected", brand_id=brand_id, account=email)


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
            return _admin_brands_redirect(frontend, google_calendar="error", reason="relay_claim_failed")
        meta = payload.get("metadata") or {}
        email = meta.get("email", "")
        brand_id = payload.get("brand_id") or ""
        if not email:
            return _admin_brands_redirect(frontend, google_calendar="error", reason="no_email_returned")
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
        return _admin_brands_redirect(frontend, google_calendar="connected", brand_id=brand_id, account=email)

    if error or not code:
        return _admin_brands_redirect(frontend, google_calendar=_oauth_callback_status(error) if error else "denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "google_calendar",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_brands_redirect(frontend, google_calendar="error", reason="session_not_found")

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
        return _admin_brands_redirect(frontend, google_calendar="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    email = metadata.get("email", "")
    if not email:
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, google_calendar="error", reason="no_email_returned")

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
    return _admin_brands_redirect(frontend, google_calendar="connected", brand_id=brand_id, account=email)


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
            return _admin_brands_redirect(frontend, youtube="error", reason="relay_claim_failed")
        meta = payload.get("metadata") or {}
        email = meta.get("email", "")
        channel_id = meta.get("channel_id", "")
        brand_id = payload.get("brand_id") or ""
        if not email or not channel_id:
            return _admin_brands_redirect(frontend, youtube="error", reason="incomplete_metadata")
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
        return _admin_brands_redirect(frontend, youtube="connected", brand_id=brand_id, account=meta.get("name") or email)

    if error or not code:
        return _admin_brands_redirect(frontend, youtube=_oauth_callback_status(error) if error else "denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "youtube",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_brands_redirect(frontend, youtube="error", reason="session_not_found")

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
        return _admin_brands_redirect(frontend, youtube="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    email = metadata.get("email", "")
    channel_id = metadata.get("channel_id", "")

    if not email or not channel_id:
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, youtube="error", reason="incomplete_metadata")

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
    return _admin_brands_redirect(frontend, youtube="connected", brand_id=brand_id, account=metadata.get("name") or email)


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
        return _admin_brands_redirect(frontend, tiktok="denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "tiktok",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_brands_redirect(frontend, tiktok="error", reason="session_not_found")

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
        return _admin_brands_redirect(frontend, tiktok="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    open_id = metadata.get("open_id", "")
    if not open_id:
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, tiktok="error", reason="no_account_returned")

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
    return _admin_brands_redirect(frontend, tiktok="connected", brand_id=brand_id, account=metadata.get("display_name") or open_id)


# ── Google Drive plugin API ───────────────────────────────────────────────────
# Google Drive OAuth callback and Drive asset endpoints are owned by
# plugins/google-drive/api.py and mounted by api/main.py.


# ── Google Business Profile OAuth Callback ───────────────────────────────────

@router.get("/google-business/callback")
async def google_business_callback(
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
            return _admin_brands_redirect(frontend, google_business="error", reason="relay_claim_failed")
        meta = payload.get("metadata") or {}
        location_name = meta.get("location_name") or ""
        business_name = meta.get("business_name") or meta.get("name") or location_name
        brand_id = payload.get("brand_id") or ""
        if not location_name:
            return _admin_brands_redirect(frontend, google_business="error", reason=meta.get("gbp_error") or "no_location_returned")
        ws = await get_singleton(db)
        token_meta = {"account_name": meta.get("account_name"), "location_name": location_name}
        if payload.get("refresh_token"):
            token_meta["refresh_token_encrypted"] = encrypt_secret(payload["refresh_token"], settings)
            token_meta["expires_at"] = payload.get("expires_at")
        await _store_connection(db, ws.id, brand_id or None, settings, "google_business", {
            "id": location_name,
            "access_token": payload["access_token"],
            "name": business_name,
            "username": meta.get("email"),
            "token_meta": token_meta,
        })
        await db.commit()
        return _admin_brands_redirect(frontend, google_business="connected", brand_id=brand_id, account=business_name)

    if error or not code:
        return _admin_brands_redirect(frontend, google_business=_oauth_callback_status(error) if error else "denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "google_business",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_brands_redirect(frontend, google_business="error", reason="session_not_found")

    raw = decrypt_secret(session.verifier_encrypted, settings)
    stored_verifier, brand_id = (raw.split("|", 1) + [""])[:2]

    ws = await get_singleton(db)
    handler = get_oauth_handler("google_business")

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
        return _admin_brands_redirect(frontend, google_business="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    location_name = metadata.get("location_name") or ""
    business_name = metadata.get("business_name") or metadata.get("name") or location_name

    if not location_name:
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, google_business="error", reason=metadata.get("gbp_error") or "no_location_returned")

    token_meta: dict = {
        "account_name": metadata.get("account_name"),
        "location_name": location_name,
    }
    if credential.refresh_token:
        token_meta["refresh_token_encrypted"] = encrypt_secret(credential.refresh_token, settings)
        token_meta["expires_at"] = credential.expires_at.isoformat() if credential.expires_at else None

    await _store_connection(db, ws.id, brand_id or None, settings, "google_business", {
        "id": location_name,
        "access_token": credential.access_token,
        "name": business_name,
        "username": metadata.get("email"),
        "token_meta": token_meta,
    })
    await db.delete(session)
    await db.commit()
    return _admin_brands_redirect(frontend, google_business="connected", brand_id=brand_id, account=business_name)


# ── Gemini OAuth Callback ────────────────────────────────────────────────────
# Gemini auth is a workspace-level LLM credential, stored in ProviderKey (not
# SocialConnection). The OAuth token is used as a Bearer credential for the
# OpenAI-compat Gemini endpoint; it falls back for any brand with no brand-
# specific Gemini key registered.

@router.get("/gemini/callback")
async def gemini_callback(
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
            return _admin_providers_redirect(frontend, gemini="error", reason="relay_claim_failed")
        meta = payload.get("metadata") or {}
        email = meta.get("email", "")
        expires_at = _coerce_datetime(payload.get("expires_at"))
        ws = await get_singleton(db)
        existing = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == ws.id,
                ProviderKey.brand_id == None,  # noqa: E711
                ProviderKey.provider == "gemini",
            )
        )).scalar_one_or_none()
        if existing:
            existing.auth_mode = "oauth"
            existing.key_encrypted = encrypt_secret(payload["access_token"], settings)
            existing.refresh_token_encrypted = encrypt_secret(payload["refresh_token"], settings) if payload.get("refresh_token") else None
            existing.expires_at = expires_at
            existing.metadata_json = {"email": email, "name": meta.get("name")}
        else:
            db.add(ProviderKey(
                workspace_id=ws.id,
                brand_id=None,
                provider="gemini",
                auth_mode="oauth",
                key_encrypted=encrypt_secret(payload["access_token"], settings),
                refresh_token_encrypted=encrypt_secret(payload["refresh_token"], settings) if payload.get("refresh_token") else None,
                expires_at=expires_at,
                metadata_json={"email": email, "name": meta.get("name")},
            ))
        await db.commit()
        return _admin_providers_redirect(frontend, gemini="connected", account=email)

    if error or not code:
        return _admin_providers_redirect(frontend, gemini=_oauth_callback_status(error) if error else "denied", reason=error or "no_code")

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == "gemini",
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_providers_redirect(frontend, gemini="error", reason="session_not_found")

    stored_verifier = decrypt_secret(session.verifier_encrypted, settings)
    ws = await get_singleton(db)
    handler = get_oauth_handler("gemini")

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
        return _admin_providers_redirect(frontend, gemini="error", reason="token_exchange_failed")

    metadata = credential.metadata or {}
    email = metadata.get("email", "")

    existing = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.brand_id == None,  # noqa: E711
            ProviderKey.provider == "gemini",
        )
    )).scalar_one_or_none()

    if existing:
        existing.auth_mode = "oauth"
        existing.key_encrypted = encrypt_secret(credential.access_token, settings)
        existing.refresh_token_encrypted = encrypt_secret(credential.refresh_token, settings) if credential.refresh_token else None
        existing.expires_at = credential.expires_at
        existing.metadata_json = {"email": email, "name": metadata.get("name")}
    else:
        db.add(ProviderKey(
            workspace_id=ws.id,
            brand_id=None,
            provider="gemini",
            auth_mode="oauth",
            key_encrypted=encrypt_secret(credential.access_token, settings),
            refresh_token_encrypted=encrypt_secret(credential.refresh_token, settings) if credential.refresh_token else None,
            expires_at=credential.expires_at,
            metadata_json={"email": email, "name": metadata.get("name")},
        ))

    await db.delete(session)
    await db.commit()
    logger.info("Gemini OAuth login completed for account '%s'", email)
    return _admin_providers_redirect(frontend, gemini="connected", account=email)


# ── Meta OAuth Callbacks (Facebook / Instagram) ──────────────────────────────

async def _store_meta_connection(db, workspace_id, brand_id, settings, provider: str, page: dict) -> SocialConnection:
    if provider == "instagram":
        ig_account_id = str(page.get("ig_account_id") or "").strip()
        if not ig_account_id:
            raise ValueError("Instagram Business Account ID missing from Meta page selection")
        display_name = page.get("name") or ig_account_id
        return await _store_connection(db, workspace_id, brand_id, settings, "instagram", {
            "id": ig_account_id,
            "name": f"{display_name} (Instagram)",
            "access_token": page["access_token"],
            "username": None,
            "token_meta": {
                "ig_account_id": ig_account_id,
                "facebook_page_id": page.get("id"),
                "facebook_page_name": page.get("name"),
            },
        })

    return await _store_connection(db, workspace_id, brand_id, settings, "facebook", {
        "id": page["id"],
        "name": page["name"],
        "access_token": page["access_token"],
        "username": None,
        "token_meta": {"ig_account_id": page.get("ig_account_id")},
    })


async def _complete_meta_callback(
    provider: str,
    code: str,
    state: str,
    error: str,
    db: AsyncSession,
    settings,
):
    frontend = settings.frontend_url.rstrip("/")

    if error or not code:
        return _admin_brands_redirect(frontend, **{provider: "denied", "reason": error or "no_code"})

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider == provider,
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return _admin_brands_redirect(frontend, **{provider: "error", "reason": "session_not_found"})

    raw = decrypt_secret(session.verifier_encrypted, settings)
    _, brand_id = (raw.split("|", 1) + [""])[:2]

    handler = get_oauth_handler(provider)
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
        return _admin_brands_redirect(frontend, **{provider: "error", "reason": "token_exchange_failed"})

    pages = (credential.metadata or {}).get("pages", [])
    if provider == "instagram":
        pages = [page for page in pages if page.get("ig_account_id")]

    if not pages:
        await db.delete(session)
        await db.commit()
        reason = "no_instagram_accounts_found" if provider == "instagram" else "no_pages_found"
        return _admin_brands_redirect(frontend, **{provider: "error", "reason": reason})

    ws = await get_singleton(db)

    if len(pages) == 1:
        conn = await _store_meta_connection(db, ws.id, brand_id or None, settings, provider, pages[0])
        await db.delete(session)
        await db.commit()
        return _admin_brands_redirect(frontend, **{provider: "connected", "brand_id": brand_id, "account": conn.page_name or pages[0].get("name") or conn.page_id})

    session.verifier_encrypted = encrypt_secret(
        json.dumps({"brand_id": brand_id or "", "pages": pages, "provider": provider}), settings
    )
    await db.commit()
    return _admin_brands_redirect(frontend, **{provider: "select_page", "session_id": str(session.id)})


@router.get("/facebook/callback")
async def facebook_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    return await _complete_meta_callback("facebook", code, state, error, db, settings)


@router.get("/instagram/callback")
async def instagram_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    return await _complete_meta_callback("instagram", code, state, error, db, settings)


async def _meta_pending_pages_response(
    provider: str,
    session_id: uuid.UUID,
    db: AsyncSession,
    settings,
):
    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.id == session_id,
            ProviderLoginSession.provider == provider,
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


@router.get(
    "/facebook/pending-pages",
    dependencies=[Depends(require_api_key)],
    responses={
        400: {"description": "Pending page session is corrupt"},
        404: {"description": "Pending page session not found"},
    },
)
async def facebook_pending_pages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    return await _meta_pending_pages_response("facebook", session_id, db, settings)


@router.get(
    "/instagram/pending-pages",
    dependencies=[Depends(require_api_key)],
    responses={
        400: {"description": "Pending page session is corrupt"},
        404: {"description": "Pending page session not found"},
    },
)
async def instagram_pending_pages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    return await _meta_pending_pages_response("instagram", session_id, db, settings)


async def _meta_select_page(
    provider: str,
    body: SelectPageRequest,
    db: AsyncSession,
    settings,
):
    try:
        sid = uuid.UUID(body.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_SESSION", "message": "Invalid session_id", "details": None}})

    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.id == sid,
            ProviderLoginSession.provider == provider,
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
    conn = await _store_meta_connection(db, ws.id, brand_id, settings, provider, page)
    await db.delete(session)
    await db.commit()
    return {"status": "connected", "page_id": conn.page_id, "page_name": conn.page_name or page.get("name")}


@router.post("/facebook/select-page", dependencies=[Depends(require_api_key)])
async def facebook_select_page(
    body: SelectPageRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    return await _meta_select_page("facebook", body, db, settings)


@router.post("/instagram/select-page", dependencies=[Depends(require_api_key)])
async def instagram_select_page(
    body: SelectPageRequest,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    return await _meta_select_page("instagram", body, db, settings)


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
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", "brand_id"], "msg": "value is not a valid UUID", "type": "uuid_parsing"}],
        )

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
    brand_uuid = _parse_brand_uuid(brand_id)
    if brand_uuid is not None:
        q = q.where(SocialConnection.brand_id == brand_uuid)
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


# ── Generic plugin-declared OAuth callback ─────────────────────────────────────

@router.get("/{platform}/callback")
async def generic_plugin_callback(
    platform: str,
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    """Complete OAuth for plugin-declared connections.

    Built-in routes above keep their existing platform-specific behavior. This
    fallback route is for third-party plugins that declare an OAuth2 connection
    in channel.json; core stores the token generically and the plugin validates
    it through its own connection.validate capability.
    """
    frontend = settings.frontend_url.rstrip("/")
    platform_key = _normalize_platform_key(platform)
    plugin_id = get_plugin_id_for_connection(platform_key)
    handler = get_oauth_handler(platform_key) if plugin_id else None
    if not plugin_id or not handler:
        return _admin_connectors_redirect(frontend, platform=platform_key or platform, status="unsupported")
    if error or not code:
        return _admin_connectors_redirect(frontend, platform=platform_key, status="denied", reason=error or "no_code")

    provider_keys = [platform_key] if platform_key == platform else [platform, platform_key]
    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider.in_(provider_keys),
            ProviderLoginSession.state == state,
        ).order_by(ProviderLoginSession.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not session:
        return _admin_connectors_redirect(frontend, platform=platform, status="error", reason="session_not_found")

    raw_verifier = decrypt_secret(session.verifier_encrypted, settings)
    if "|" in raw_verifier:
        verifier, brand_id = raw_verifier.split("|", 1)
    else:
        verifier, brand_id = raw_verifier, ""

    plugin_vars = await get_plugin_vars(plugin_id, db, settings)
    try:
        try:
            credential = await handler.complete_login(
                code,
                settings,
                state=state,
                verifier=verifier,
                redirect_uri=session.redirect_uri,
                overrides=plugin_vars,
            )
        except TypeError:
            credential = await handler.complete_login(
                code,
                settings,
                state=state,
                verifier=verifier,
                redirect_uri=session.redirect_uri,
            )
    except Exception as exc:
        logger.warning("Generic plugin OAuth callback failed for %s: %s", platform_key, exc)
        return _admin_connectors_redirect(frontend, platform=platform_key, status="error", reason="oauth_failed")

    ws = await get_singleton(db)
    if not ws:
        return _admin_connectors_redirect(frontend, platform=platform_key, status="error", reason="workspace_not_found")

    meta = credential.metadata or {}
    account = meta.get("account") or {}
    account_id = str(account.get("id") or account.get("email") or platform)
    account_name = str(account.get("name") or account.get("email") or account_id)
    token_meta = dict(meta)
    if credential.refresh_token:
        token_meta["refresh_token_encrypted"] = encrypt_secret(credential.refresh_token, settings)
    if credential.expires_at:
        token_meta["expires_at"] = credential.expires_at.isoformat()

    await _store_connection(db, ws.id, brand_id or None, settings, platform_key, {
        "id": account_id,
        "access_token": credential.access_token,
        "name": account_name,
        "username": account.get("username") or account.get("handle"),
        "token_meta": token_meta or None,
    })
    await db.delete(session)
    await db.commit()
    return _admin_connectors_redirect(frontend, platform=platform_key, status="connected", brand_id=brand_id, account=account_name)


# ── Token resolution helper ────────────────────────────────────────────────────

async def get_page_token(db: AsyncSession, brand_id: str, platform: str, settings) -> tuple[str, str] | tuple[None, None]:
    """Resolve a decrypted access token and page_id for a brand + platform.

    Auto-refreshes tokens within 5 minutes of expiry when a refresh token is stored.
    """
    brand_uuid = _parse_brand_uuid(brand_id)
    if brand_uuid is None:
        return None, None
    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand_uuid,
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
                        plugin_id = _plugin_id_for_platform(platform)
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
                    row.status = "connected"
                    await db.commit()
                    return refreshed.access_token, row.page_id
                except Exception as exc:
                    logger.warning(
                        "OAuth refresh failed for platform=%s brand_id=%s; marking connection for reauth: %s",
                        platform,
                        brand_id,
                        exc,
                    )
                    row.status = "needs_reauth"
                    await db.commit()
                    return None, None

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
        if platform == "google_drive":
            # Reconnect/reauth should refresh OAuth tokens without forgetting the
            # operator-selected brand asset root folder.
            merged_meta = dict(existing.token_meta_json or {})
            if token_meta:
                merged_meta.update(token_meta)
            existing.token_meta_json = merged_meta or token_meta
        else:
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
