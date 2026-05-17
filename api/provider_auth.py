import base64
import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.provider import ProviderKey

_OPENAI_CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
_OPENAI_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
_OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"
_OPENAI_REDIRECT_URI = "http://localhost:1455/auth/callback"
_OPENAI_SCOPE = "openid profile email offline_access"
_OPENAI_JWT_CLAIM_PATH = "https://api.openai.com/auth"


@dataclass
class LoginStart:
    login_type: str
    authorize_url: str | None = None
    user_code: str | None = None
    verification_uri: str | None = None
    state: str | None = None
    verifier: str | None = None
    redirect_uri: str | None = None


@dataclass
class OAuthCredential:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    metadata: dict | None = None


class OAuthProviderHandler(Protocol):
    provider: str
    display_name: str

    async def start_login(self, settings) -> LoginStart: ...

    async def complete_login(self, callback_url: str, settings, *, state: str, verifier: str, redirect_uri: str) -> OAuthCredential: ...

    async def refresh_auth(self, refresh_token: str, settings) -> OAuthCredential: ...


class OpenAICodexOAuthHandler:
    provider = "openai"
    display_name = "OpenAI Chat"

    async def start_login(self, settings) -> LoginStart:
        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "response_type": "code",
            "client_id": _OPENAI_CODEX_CLIENT_ID,
            "redirect_uri": _OPENAI_REDIRECT_URI,
            "scope": _OPENAI_SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": "bos",
        }
        return LoginStart(
            login_type="browser",
            authorize_url=f"{_OPENAI_AUTHORIZE_URL}?{urlencode(params)}",
            state=state,
            verifier=verifier,
            redirect_uri=_OPENAI_REDIRECT_URI,
        )

    async def complete_login(self, callback_url: str, settings, *, state: str, verifier: str, redirect_uri: str) -> OAuthCredential:
        code, returned_state = _parse_callback_input(callback_url)
        if not code:
            raise ValueError("Missing authorization code")
        if returned_state and returned_state != state:
            raise ValueError("OAuth state mismatch")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                _OPENAI_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "authorization_code",
                    "client_id": _OPENAI_CODEX_CLIENT_ID,
                    "code": code,
                    "code_verifier": verifier,
                    "redirect_uri": redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()

        access = data.get("access_token")
        refresh = data.get("refresh_token")
        expires_in = data.get("expires_in")
        if not access or not refresh or not isinstance(expires_in, int):
            raise ValueError("Token exchange failed")
        account_id = _extract_account_id(access)
        return OAuthCredential(
            access_token=access,
            refresh_token=refresh,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            metadata={"account_id": account_id},
        )

    async def refresh_auth(self, refresh_token: str, settings) -> OAuthCredential:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                _OPENAI_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": _OPENAI_CODEX_CLIENT_ID,
                },
            )
            response.raise_for_status()
            data = response.json()

        access = data.get("access_token")
        refresh = data.get("refresh_token") or refresh_token
        expires_in = data.get("expires_in")
        if not access or not isinstance(expires_in, int):
            raise ValueError("Failed to refresh OpenAI token")
        account_id = _extract_account_id(access)
        return OAuthCredential(
            access_token=access,
            refresh_token=refresh,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            metadata={"account_id": account_id},
        )



_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
_GOOGLE_SCOPES = "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly openid email"


class GmailOAuthHandler:
    provider = "gmail"
    display_name = "Gmail"

    async def start_login(self, settings) -> LoginStart:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is not configured")
        if not settings.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET is not configured")
        if not settings.google_redirect_uri:
            raise ValueError("GOOGLE_REDIRECT_URI is not configured")
        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": _GOOGLE_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        return LoginStart(
            login_type="browser",
            authorize_url=f"{_GOOGLE_AUTHORIZE_URL}?{urlencode(params)}",
            state=state,
            verifier=verifier,
            redirect_uri=settings.google_redirect_uri,
        )

    async def complete_login(self, code: str, settings, *, state: str, verifier: str, redirect_uri: str) -> OAuthCredential:
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
            r.raise_for_status()
            token_data = r.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("Google token exchange failed — no access_token in response")

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            userinfo = r.json()

        expires_in = token_data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
            metadata={"email": userinfo.get("email"), "name": userinfo.get("name")},
        )

    async def refresh_auth(self, refresh_token: str, settings) -> OAuthCredential:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": refresh_token,
                },
            )
            r.raise_for_status()
            data = r.json()

        access_token = data.get("access_token")
        if not access_token:
            raise ValueError("Google token refresh failed — no access_token in response")
        expires_in = data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
        )


_GOOGLE_CALENDAR_SCOPES = "https://www.googleapis.com/auth/calendar openid email"


class GoogleCalendarOAuthHandler:
    provider = "google_calendar"
    display_name = "Google Calendar"

    async def start_login(self, settings) -> LoginStart:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is not configured")
        if not settings.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET is not configured")
        redirect_uri = settings.google_calendar_redirect_uri or (
            settings.google_redirect_uri.replace("/social/gmail/callback", "/social/google-calendar/callback")
        )
        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _GOOGLE_CALENDAR_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        return LoginStart(
            login_type="browser",
            authorize_url=f"{_GOOGLE_AUTHORIZE_URL}?{urlencode(params)}",
            state=state,
            verifier=verifier,
            redirect_uri=redirect_uri,
        )

    async def complete_login(self, code: str, settings, *, state: str, verifier: str, redirect_uri: str) -> OAuthCredential:
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
            r.raise_for_status()
            token_data = r.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("Google token exchange failed — no access_token in response")

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            userinfo = r.json()

        expires_in = token_data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
            metadata={"email": userinfo.get("email"), "name": userinfo.get("name")},
        )

    async def refresh_auth(self, refresh_token: str, settings) -> OAuthCredential:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": refresh_token,
                },
            )
            r.raise_for_status()
            data = r.json()

        access_token = data.get("access_token")
        if not access_token:
            raise ValueError("Google Calendar token refresh failed")
        expires_in = data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
        )


_FACEBOOK_AUTHORIZE_URL = "https://www.facebook.com/dialog/oauth"
_FACEBOOK_TOKEN_URL = "https://graph.facebook.com/oauth/access_token"
_FACEBOOK_GRAPH_URL = "https://graph.facebook.com/v21.0"
_FACEBOOK_SCOPES = "pages_show_list,pages_manage_posts"


class FacebookOAuthHandler:
    provider = "facebook"
    display_name = "Facebook"

    def _app_id(self, settings, overrides: dict) -> str:
        v = overrides.get("meta_app_id") or overrides.get("META_APP_ID") or settings.meta_app_id
        if not v:
            raise ValueError("META_APP_ID not configured — add it via Admin → Plugins → Meta Channel")
        return v

    def _app_secret(self, settings, overrides: dict) -> str:
        v = overrides.get("meta_app_secret") or overrides.get("META_APP_SECRET") or settings.meta_app_secret
        if not v:
            raise ValueError("META_APP_SECRET not configured — add it via Admin → Plugins → Meta Channel")
        return v

    def _redirect_uri(self, settings, overrides: dict) -> str:
        return (
            overrides.get("meta_redirect_uri")
            or overrides.get("META_REDIRECT_URI")
            or settings.meta_redirect_uri
        )

    async def start_login(self, settings, overrides: dict | None = None) -> LoginStart:
        overrides = overrides or {}
        app_id = self._app_id(settings, overrides)
        redirect_uri = self._redirect_uri(settings, overrides)
        state = secrets.token_hex(16)
        params = {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "scope": _FACEBOOK_SCOPES,
            "state": state,
            "response_type": "code",
        }
        return LoginStart(
            login_type="browser",
            authorize_url=f"{_FACEBOOK_AUTHORIZE_URL}?{urlencode(params)}",
            state=state,
            verifier=state,
            redirect_uri=redirect_uri,
        )

    async def complete_login(self, code: str, settings, *, state: str, verifier: str, redirect_uri: str, overrides: dict | None = None) -> OAuthCredential:
        overrides = overrides or {}
        app_id = self._app_id(settings, overrides)
        app_secret = self._app_secret(settings, overrides)

        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                _FACEBOOK_TOKEN_URL,
                params={
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            r.raise_for_status()
            short_data = r.json()

        short_token = short_data.get("access_token")
        if not short_token:
            raise ValueError("Facebook token exchange failed — no access_token")

        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                _FACEBOOK_TOKEN_URL,
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": short_token,
                },
            )
            r.raise_for_status()
            long_data = r.json()

        long_token = long_data.get("access_token")
        if not long_token:
            raise ValueError("Facebook long-lived token exchange failed")

        expires_in = long_data.get("expires_in", 5184000)

        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                f"{_FACEBOOK_GRAPH_URL}/me/accounts",
                params={
                    "fields": "id,name,access_token,instagram_business_account",
                    "access_token": long_token,
                },
            )
            r.raise_for_status()
            accounts = r.json()

        pages = [
            {
                "id": p["id"],
                "name": p.get("name", p["id"]),
                "access_token": p.get("access_token", ""),
                "ig_account_id": (p.get("instagram_business_account") or {}).get("id"),
            }
            for p in accounts.get("data", [])
        ]

        return OAuthCredential(
            access_token=long_token,
            refresh_token=None,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
            metadata={"pages": pages},
        )

    async def refresh_auth(self, refresh_token: str, settings) -> OAuthCredential:
        raise NotImplementedError("Facebook Page Access Tokens do not expire — refresh is not supported")


_OAUTH_HANDLERS: dict[str, OAuthProviderHandler] = {
    "openai": OpenAICodexOAuthHandler(),
    "gmail": GmailOAuthHandler(),
    "google_calendar": GoogleCalendarOAuthHandler(),
    "facebook": FacebookOAuthHandler(),
}


def get_oauth_handler(provider: str):
    return _OAUTH_HANDLERS.get(provider)


def get_auth_supported(provider: str) -> list[str]:
    supports: list[str] = []
    if provider in {"openrouter", "gemini", "nvidia", "openai"}:
        supports.append("api_key")
    if provider in _OAUTH_HANDLERS:
        supports.append("oauth")
    return supports


def get_fernet(settings) -> Fernet:
    if not settings.encryption_key:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "ENCRYPTION_NOT_CONFIGURED", "message": "ENCRYPTION_KEY is not set", "details": None}},
        )
    return Fernet(settings.encryption_key.encode())


def encrypt_secret(value: str, settings) -> str:
    return get_fernet(settings).encrypt(value.encode()).decode()


def decrypt_secret(value: str, settings) -> str:
    try:
        return get_fernet(settings).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "DECRYPTION_FAILED", "message": "Stored credential could not be decrypted", "details": None}},
        ) from exc


async def resolve_stored_provider_credential(
    db: AsyncSession,
    workspace_id,
    provider: str,
    settings,
    brand_id=None,
) -> tuple[str | None, str | None]:
    row = None
    if isinstance(brand_id, str):
        try:
            brand_id = uuid.UUID(brand_id)
        except ValueError:
            brand_id = None
    if brand_id:
        # BYOK credentials are brand-scoped. Do not fall back to a workspace-level
        # API key for a brand run, or one brand could accidentally spend another
        # brand/operator credential. Workspace-level OAuth login may still be used
        # as shared operator auth when no brand credential exists.
        row = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == workspace_id,
                ProviderKey.brand_id == brand_id,
                ProviderKey.provider == provider,
            )
        )).scalar_one_or_none()
        if row is None:
            row = (await db.execute(
                select(ProviderKey).where(
                    ProviderKey.workspace_id == workspace_id,
                    ProviderKey.brand_id == None,  # noqa: E711
                    ProviderKey.provider == provider,
                    ProviderKey.auth_mode != "api_key",
                )
            )).scalar_one_or_none()
    else:
        row = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == workspace_id,
                ProviderKey.brand_id == None,  # noqa: E711
                ProviderKey.provider == provider,
            )
        )).scalar_one_or_none()
    if not row:
        return None, None

    if row.auth_mode == "oauth":
        token = decrypt_secret(row.key_encrypted, settings)
        if row.expires_at and row.expires_at <= datetime.now(timezone.utc):
            if not row.refresh_token_encrypted:
                return None, None
            handler = get_oauth_handler(provider)
            if not handler:
                return None, None
            refreshed = await handler.refresh_auth(
                decrypt_secret(row.refresh_token_encrypted, settings), settings
            )
            row.key_encrypted = encrypt_secret(refreshed.access_token, settings)
            row.refresh_token_encrypted = (
                encrypt_secret(refreshed.refresh_token, settings) if refreshed.refresh_token else None
            )
            row.expires_at = refreshed.expires_at
            row.metadata_json = refreshed.metadata
            await db.commit()
            token = refreshed.access_token
        return token, "oauth"

    return decrypt_secret(row.key_encrypted, settings), "api_key"


def _generate_pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def _parse_callback_input(value: str) -> tuple[str | None, str | None]:
    text = value.strip()
    if not text:
        return None, None
    try:
        url = urlparse(text)
        if url.scheme and url.netloc:
            params = parse_qs(url.query)
            return (params.get("code") or [None])[0], (params.get("state") or [None])[0]
    except Exception:
        pass
    if "#" in text and "http" not in text:
        code, state = text.split("#", 1)
        return code or None, state or None
    if "code=" in text:
        params = parse_qs(text)
        return (params.get("code") or [None])[0], (params.get("state") or [None])[0]
    return text, None


def _extract_account_id(token: str) -> str:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("invalid token")
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        account_id = data.get(_OPENAI_JWT_CLAIM_PATH, {}).get("chatgpt_account_id")
        if not account_id:
            raise ValueError("missing account id")
        return str(account_id)
    except Exception as exc:
        raise ValueError("Failed to extract accountId from token") from exc
