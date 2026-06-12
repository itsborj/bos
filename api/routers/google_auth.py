import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import _hash
from config import get_settings
from db import get_db
from models.api_key import ApiKey
from models.provider import ProviderKey, ProviderLoginSession
from provider_auth import decrypt_secret, encrypt_secret, _generate_pkce
from routers.workspace import get_singleton

router = APIRouter(prefix="/auth/google", tags=["auth"])

# Minimal scopes — only openid + email/profile.
# Do NOT include googleapis.com API scopes for a login flow;
# those require app verification and cause "invalid_request".
_LOGIN_SCOPES = "openid email profile"

_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"


def _get_redirect_uri(settings) -> str:
    base = (settings.frontend_url or "http://localhost").rstrip("/")
    return f"{base}/api/auth/google/callback"


@router.get("/login", responses={302: {"description": "Redirect to Google OAuth"}, 412: {"description": "Workspace not initialized"}, 500: {"description": "Google OAuth not configured"}})
async def google_login(
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    redirect_uri = _get_redirect_uri(settings)
    verifier, challenge = _generate_pkce()
    state = secrets.token_hex(16)

    # Delete stale sessions for this workspace to avoid duplicate state
    old_sessions = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.workspace_id == ws.id,
            ProviderLoginSession.provider == "google_login",
        )
    )).scalars().all()
    for s in old_sessions:
        await db.delete(s)
    await db.flush()

    session = ProviderLoginSession(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        provider="google_login",
        login_type="browser",
        state=state,
        verifier_encrypted=encrypt_secret(verifier, settings),
        redirect_uri=redirect_uri,
    )
    db.add(session)
    await db.commit()

    # NOTE: Do NOT include access_type=offline here — it triggers stricter
    # Google validation requiring app verification for unverified apps.
    # We use PKCE (code_challenge) for security instead.
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _LOGIN_SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }

    auth_url = f"{_GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"
    print(f"GOOGLE_AUTH: Redirecting to: {auth_url[:120]}...")
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback")
async def google_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
):
    frontend = (settings.frontend_url or "http://localhost").rstrip("/")

    if error or not code:
        return RedirectResponse(url=f"{frontend}/auth?error={error or 'google_denied'}")

    # Find session — works for both the login-page flow (provider="google_login")
    # and the Admin Providers "Connect Google" flow (provider="google")
    session = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.provider.in_(["google_login", "google"]),
            ProviderLoginSession.state == state,
        )
    )).scalar_one_or_none()

    if not session:
        return RedirectResponse(url=f"{frontend}/auth?error=session_expired")

    verifier = decrypt_secret(session.verifier_encrypted, settings)
    redirect_uri = session.redirect_uri

    # Exchange authorization code for tokens
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                    "code_verifier": verifier,
                },
            )
            if r.status_code != 200:
                print(f"GOOGLE_AUTH: Token exchange failed: {r.text}")
                return RedirectResponse(url=f"{frontend}/auth?error=token_exchange_failed")
            token_data = r.json()
    except Exception:
        return RedirectResponse(url=f"{frontend}/auth?error=exchange_exception")

    access_token = token_data.get("access_token")
    if not access_token:
        return RedirectResponse(url=f"{frontend}/auth?error=no_access_token")

    # Fetch user info
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code != 200:
                return RedirectResponse(url=f"{frontend}/auth?error=userinfo_failed")
            userinfo = r.json()
    except Exception:
        return RedirectResponse(url=f"{frontend}/auth?error=userinfo_exception")

    email = userinfo.get("email", "").lower()
    if not email:
        return RedirectResponse(url=f"{frontend}/auth?error=no_email")

    # Enforce admin whitelist
    raw_allowed = getattr(settings, "admin_emails", "") or ""
    allowed = [e.strip().lower() for e in raw_allowed.split(",") if e.strip()]
    if allowed and email not in allowed:
        print(f"GOOGLE_AUTH: Rejected email {email} (not in whitelist)")
        return RedirectResponse(url=f"{frontend}/auth?error=unauthorized_email")

    ws = await get_singleton(db)
    if not ws:
        return RedirectResponse(url=f"{frontend}/auth?error=workspace_missing")

    # Upsert ProviderKey for 'google' so it shows as Connected in Admin → Providers
    existing_prov = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.provider == "google",
            ProviderKey.brand_id == None,  # noqa: E711
        )
    )).scalar_one_or_none()

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token_data.get("expires_in", 3600)))
    meta = {"email": email, "name": userinfo.get("name", "")}

    if existing_prov:
        existing_prov.auth_mode = "oauth"
        existing_prov.key_encrypted = encrypt_secret(access_token, settings)
        existing_prov.refresh_token_encrypted = (
            encrypt_secret(token_data["refresh_token"], settings)
            if token_data.get("refresh_token") else None
        )
        existing_prov.expires_at = expires_at
        existing_prov.metadata_json = meta
    else:
        db.add(ProviderKey(
            workspace_id=ws.id,
            provider="google",
            brand_id=None,
            auth_mode="oauth",
            key_encrypted=encrypt_secret(access_token, settings),
            refresh_token_encrypted=(
                encrypt_secret(token_data["refresh_token"], settings)
                if token_data.get("refresh_token") else None
            ),
            expires_at=expires_at,
            metadata_json=meta,
        ))

    # Always create a fresh API key so the frontend can authenticate
    raw_key = "bos_" + secrets.token_hex(32)
    db.add(ApiKey(
        workspace_id=ws.id,
        key_hash=_hash(raw_key),
        label=f"google:{email}",
    ))

    # Clean up login session
    await db.delete(session)
    await db.commit()

    print(f"GOOGLE_AUTH: Login successful for {email}")
    return RedirectResponse(url=f"{frontend}/auth?key={raw_key}")
