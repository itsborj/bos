import base64
import hashlib
import json
import logging
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_provider_registry import get_ai_auth_supported, is_ai_provider
from models.provider import ProviderKey

_OPENAI_CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
_OPENAI_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
_OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"
_OPENAI_REDIRECT_URI = "http://localhost:1455/auth/callback"
_OPENAI_SCOPE = "openid profile email offline_access"
_OPENAI_JWT_CLAIM_PATH = "https://api.openai.com/auth"
logger = logging.getLogger("bos.provider_auth")


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
            "originator": "pi",
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
            metadata={"account_id": account_id, "auth_surface": "chatgpt_codex", "supports_api_images": False},
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
            metadata={"account_id": account_id, "auth_surface": "chatgpt_codex", "supports_api_images": False},
        )



_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
_GOOGLE_SCOPES = "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly openid email"
_YOUTUBE_SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl openid email"
# Gemini AI OAuth uses the cloud-platform scope for user consent.
# The generative-language scope requires explicit addition to the OAuth consent
# screen in GCP Console (APIs & Services → OAuth consent screen → Add/remove scopes)
# AND Google app verification before it appears. cloud-platform is the broad
# scope that passes user consent without verification while in Testing mode.
# `openid email` lets us label the connected account in Admin.
_GEMINI_AI_SCOPES = "https://www.googleapis.com/auth/cloud-platform openid email"
_TIKTOK_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
_TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
_TIKTOK_USERINFO_URL = "https://open.tiktokapis.com/v2/user/info/"
_TIKTOK_SCOPES = "user.info.basic,video.publish"
_GOOGLE_DRIVE_SCOPES = "https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/drive.readonly openid email"
_GBP_SCOPES = "https://www.googleapis.com/auth/business.manage openid email"
_GBP_ACCOUNTS_URL = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
_GBP_INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"

# Paths for each Google OAuth callback — derived from FRONTEND_URL so no per-env redirect URI config is needed.
_GOOGLE_CALLBACK_PATHS: dict[str, str] = {
    "gmail": "/social/gmail/callback",
    "google_calendar": "/social/google-calendar/callback",
    "youtube": "/social/youtube/callback",
    "google_drive": "/social/google-drive/callback",
    "gemini": "/social/gemini/callback",
    "google": "/api/auth/google/callback",
    "google_business": "/social/google-business/callback",
}


def _google_redirect_uri(platform: str, settings) -> str:
    """Return the Google OAuth redirect URI.

    Relay mode: all Google platforms share one registered URI on the relay
    (https://auth.klaroha.com/relay/google/callback). The relay handles the
    code exchange and redirects back to the instance with a handoff_token.

    Dev mode: URI derived from FRONTEND_URL — the same OAuth client works across
    all environments as long as all callback URIs are registered in Google Console.
    """
    if getattr(settings, "klaroha_relay_url", ""):
        relay = settings.klaroha_relay_url.rstrip("/")
        return f"{relay}/relay/google/callback"
    base = (settings.frontend_url or "http://localhost").rstrip("/")
    path = _GOOGLE_CALLBACK_PATHS.get(platform, f"/social/{platform}/callback")
    return f"{base}{path}"


class GmailOAuthHandler:
    provider = "gmail"
    display_name = "Gmail"

    async def start_login(self, settings) -> LoginStart:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is not configured")
        if not settings.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET is not configured")
        redirect_uri = _google_redirect_uri("gmail", settings)
        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
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
        redirect_uri = _google_redirect_uri("google_calendar", settings)
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


class YouTubeOAuthHandler:
    provider = "youtube"
    display_name = "YouTube"

    async def start_login(self, settings, overrides: dict | None = None) -> LoginStart:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is not configured")
        if not settings.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET is not configured")
        redirect_uri = _google_redirect_uri("youtube", settings)
             
        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _YOUTUBE_SCOPES,
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
            raise ValueError("YouTube token exchange failed — no access_token in response")

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            userinfo = r.json()

        channel_id = None
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "id", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])
                if items:
                    channel_id = items[0].get("id")

        expires_in = token_data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
            metadata={
                "email": userinfo.get("email"),
                "name": userinfo.get("name"),
                "channel_id": channel_id,
            },
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
            raise ValueError("YouTube token refresh failed — no access_token in response")
        expires_in = data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
        )


class GoogleDriveOAuthHandler:
    provider = "google_drive"
    display_name = "Google Drive"

    async def start_login(self, settings, overrides: dict | None = None) -> LoginStart:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is not configured")
        if not settings.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET is not configured")
        redirect_uri = _google_redirect_uri("google_drive", settings)

        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _GOOGLE_DRIVE_SCOPES,
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
            raise ValueError("Google Drive token exchange failed — no access_token in response")

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
            metadata={
                "email": userinfo.get("email"),
                "name": userinfo.get("name"),
            },
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
            raise ValueError("Google Drive token refresh failed — no access_token in response")
        expires_in = data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
        )


_FACEBOOK_AUTHORIZE_URL = "https://www.facebook.com/dialog/oauth"
_FACEBOOK_TOKEN_URL = "https://graph.facebook.com/oauth/access_token"
_FACEBOOK_GRAPH_URL = "https://graph.facebook.com/v21.0"
_FACEBOOK_SCOPES = "pages_show_list,pages_read_engagement,pages_manage_posts"
_INSTAGRAM_SCOPES = "instagram_basic,pages_show_list"


class TikTokOAuthHandler:
    provider = "tiktok"
    display_name = "TikTok"

    def _client_key(self, settings, overrides: dict) -> str:
        v = overrides.get("tiktok_client_key") or overrides.get("TIKTOK_CLIENT_KEY") or settings.tiktok_client_key or os.getenv("TIKTOK_CLIENT_KEY", "")
        if not v:
            raise ValueError("TIKTOK_CLIENT_KEY is not configured")
        return v

    def _client_secret(self, settings, overrides: dict) -> str:
        v = overrides.get("tiktok_client_secret") or overrides.get("TIKTOK_CLIENT_SECRET") or settings.tiktok_client_secret or os.getenv("TIKTOK_CLIENT_SECRET", "")
        if not v:
            raise ValueError("TIKTOK_CLIENT_SECRET is not configured")
        return v

    def _redirect_uri(self, settings, overrides: dict) -> str:
        v = overrides.get("tiktok_redirect_uri") or overrides.get("TIKTOK_REDIRECT_URI") or settings.tiktok_redirect_uri or os.getenv("TIKTOK_REDIRECT_URI", "")
        if not v:
            raise ValueError("TIKTOK_REDIRECT_URI is not configured")
        return v

    def _scopes(self, settings, overrides: dict) -> str:
        return overrides.get("tiktok_scopes") or overrides.get("TIKTOK_SCOPES") or settings.tiktok_scopes or os.getenv("TIKTOK_SCOPES", "") or _TIKTOK_SCOPES

    async def start_login(self, settings, overrides: dict | None = None) -> LoginStart:
        overrides = overrides or {}
        client_key = self._client_key(settings, overrides)
        redirect_uri = self._redirect_uri(settings, overrides)
        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "client_key": client_key,
            "response_type": "code",
            "scope": self._scopes(settings, overrides),
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return LoginStart(
            login_type="browser",
            authorize_url=f"{_TIKTOK_AUTHORIZE_URL}?{urlencode(params)}",
            state=state,
            verifier=verifier,
            redirect_uri=redirect_uri,
        )

    async def complete_login(self, code: str, settings, *, state: str, verifier: str, redirect_uri: str, overrides: dict | None = None) -> OAuthCredential:
        overrides = overrides or {}
        client_key = self._client_key(settings, overrides)
        client_secret = self._client_secret(settings, overrides)
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                _TIKTOK_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_key": client_key,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code_verifier": verifier,
                },
            )
            r.raise_for_status()
            token_data = r.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("TikTok token exchange failed — no access_token in response")

        metadata: dict = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                _TIKTOK_USERINFO_URL,
                params={"fields": "open_id,union_id,avatar_url,display_name,profile_deep_link"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code == 200:
                user = (r.json().get("data") or {}).get("user") or {}
                metadata = {
                    "open_id": user.get("open_id"),
                    "display_name": user.get("display_name"),
                    "profile_deep_link": user.get("profile_deep_link"),
                    "avatar_url": user.get("avatar_url"),
                }

        expires_in = token_data.get("expires_in", 86400)
        refresh_expires_in = token_data.get("refresh_expires_in")
        if refresh_expires_in:
            metadata["refresh_expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=int(refresh_expires_in))).isoformat()
        return OAuthCredential(
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
            metadata=metadata,
        )

    async def refresh_auth(self, refresh_token: str, settings, overrides: dict | None = None) -> OAuthCredential:
        overrides = overrides or {}
        client_key = self._client_key(settings, overrides)
        client_secret = self._client_secret(settings, overrides)
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                _TIKTOK_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_key": client_key,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
            r.raise_for_status()
            data = r.json()

        access_token = data.get("access_token")
        if not access_token:
            raise ValueError("TikTok token refresh failed — no access_token in response")
        expires_in = data.get("expires_in", 86400)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=data.get("refresh_token") or refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
        )


class FacebookOAuthHandler:
    provider = "facebook"
    display_name = "Facebook"
    scopes = _FACEBOOK_SCOPES
    callback_path = "/social/facebook/callback"

    def _config_id(self, overrides: dict) -> str:
        return ""

    def _app_id(self, settings, overrides: dict) -> str:
        v = overrides.get("meta_app_id") or overrides.get("META_APP_ID") or settings.meta_app_id
        if not v:
            raise ValueError("META_APP_ID not configured — add it via Admin → Capabilities → Meta Channel")
        return v

    def _app_secret(self, settings, overrides: dict) -> str:
        v = overrides.get("meta_app_secret") or overrides.get("META_APP_SECRET") or settings.meta_app_secret
        if not v:
            raise ValueError("META_APP_SECRET not configured — add it via Admin → Capabilities → Meta Channel")
        return v

    def _redirect_uri(self, settings, overrides: dict) -> str:
        from urllib.parse import urlparse

        frontend = settings.frontend_url or "http://localhost"
        frontend_host = urlparse(frontend).netloc
        expected_path = self.callback_path

        def _matches(candidate: str) -> bool:
            if not candidate:
                return False
            parsed = urlparse(candidate)
            if parsed.netloc and frontend_host and parsed.netloc != frontend_host:
                return False
            return parsed.path == expected_path

        stored = overrides.get("meta_redirect_uri") or overrides.get("META_REDIRECT_URI")
        if stored and _matches(stored):
            return stored

        env_redirect = settings.meta_redirect_uri or ""
        if env_redirect and _matches(env_redirect):
            return env_redirect

        base = frontend.rstrip("/")
        return f"{base}{expected_path}"

    async def start_login(self, settings, overrides: dict | None = None) -> LoginStart:
        overrides = overrides or {}
        app_id = self._app_id(settings, overrides)
        redirect_uri = self._redirect_uri(settings, overrides)
        state = secrets.token_hex(16)
        params = {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
        }
        config_id = self._config_id(overrides)
        if config_id:
            # Facebook Login for Business / Instagram API setups prefer config_id
            # over ad-hoc scope strings. This avoids developer-only "Invalid Scopes"
            # errors when the app has switched to a business login configuration.
            params["config_id"] = config_id
        else:
            params["scope"] = self.scopes
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


class InstagramOAuthHandler(FacebookOAuthHandler):
    provider = "instagram"
    display_name = "Instagram"
    scopes = _INSTAGRAM_SCOPES
    callback_path = "/social/instagram/callback"

    def _config_id(self, overrides: dict) -> str:
        return str(
            overrides.get("meta_instagram_config_id")
            or overrides.get("META_INSTAGRAM_CONFIG_ID")
            or ""
        ).strip()


class GoogleBusinessOAuthHandler:
    provider = "google_business"
    display_name = "Google Business Profile"

    async def start_login(self, settings) -> LoginStart:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is not configured")
        if not settings.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET is not configured")
        redirect_uri = _google_redirect_uri("google_business", settings)
        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _GBP_SCOPES,
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

        account_name = None
        location_name = None
        business_name = None
        gbp_error = None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    _GBP_ACCOUNTS_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if r.status_code == 200:
                    accounts = r.json().get("accounts", [])
                    if not accounts:
                        gbp_error = "no_account_returned"
                    else:
                        gbp_error = "no_location_returned"
                    for account in accounts:
                        candidate_account = account.get("name")
                        if not candidate_account:
                            continue
                        loc = await client.get(
                            f"{_GBP_INFO_BASE}/{candidate_account}/locations",
                            params={"readMask": "name,title"},
                            headers={"Authorization": f"Bearer {access_token}"},
                        )
                        if loc.status_code == 200:
                            locations = loc.json().get("locations", [])
                            if locations:
                                account_name = candidate_account
                                location_name = locations[0]["name"]
                                business_name = locations[0].get("title", "")
                                gbp_error = None
                                break
                        else:
                            try:
                                gbp_error = (
                                    (loc.json().get("error") or {}).get("message")
                                    or f"locations_http_{loc.status_code}"
                                )
                            except Exception:
                                gbp_error = f"locations_http_{loc.status_code}"
                else:
                    try:
                        gbp_error = (
                            (r.json().get("error") or {}).get("message")
                            or f"accounts_http_{r.status_code}"
                        )
                    except Exception:
                        gbp_error = f"accounts_http_{r.status_code}"
        except Exception as exc:
            gbp_error = f"gbp_request_failed: {exc}"

        expires_in = token_data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
            metadata={
                "email": userinfo.get("email"),
                "name": userinfo.get("name"),
                "account_name": account_name,
                "location_name": location_name,
                "business_name": business_name,
                "gbp_error": gbp_error,
            },
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
            raise ValueError("Google Business Profile token refresh failed")
        expires_in = data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
        )


class GeminiOAuthHandler:
    provider = "gemini"
    display_name = "Google Gemini AI"

    async def start_login(self, settings) -> LoginStart:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is not configured")
        if not settings.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET is not configured")
        # Always use direct BOS callback — Gemini stores its session in BOS DB
        # (ProviderLoginSession), not relay Redis, so the relay callback cannot
        # find it and would return session_not_found.
        base = (settings.frontend_url or "http://localhost").rstrip("/")
        redirect_uri = f"{base}/social/gemini/callback"
        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _GEMINI_AI_SCOPES,
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
            raise ValueError("Google token refresh failed — no access_token in response")
        expires_in = data.get("expires_in", 3600)
        return OAuthCredential(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
        )

# Google Login handler — for admin panel "Sign in with Google".
# Uses ONLY openid/email/profile scopes (no Gmail/Drive/etc.) so Google
# never blocks it for unverified apps. Always uses the direct /api/auth/google/callback
# path regardless of relay settings.
_GOOGLE_LOGIN_SCOPES = "openid email profile"


class GoogleLoginOAuthHandler:
    provider = "google"
    display_name = "Google"

    async def start_login(self, settings) -> LoginStart:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is not configured")
        if not settings.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET is not configured")
        # Always use direct callback — never relay
        base = (settings.frontend_url or "http://localhost").rstrip("/")
        redirect_uri = f"{base}/api/auth/google/callback"
        verifier, challenge = _generate_pkce()
        state = secrets.token_hex(16)
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _GOOGLE_LOGIN_SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
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
            raise ValueError("Google token exchange failed — no access_token")

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
            raise ValueError("Google token refresh failed")
        return OAuthCredential(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600))),
        )


def _dig_path(data: dict, path: str | None, default=None):
    if not path:
        return default
    current = data
    for part in str(path).split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)] if int(part) < len(current) else None
        else:
            return default
        if current is None:
            return default
    return current


class GenericPluginOAuthHandler:
    """Generic OAuth2 handler backed by a plugin's channel.json connection declaration.

    It intentionally implements only protocol mechanics. Platform behavior remains
    in the plugin: manifest fields describe endpoints/field paths, and the plugin's
    validation capability proves the connection before downstream use.
    """

    def __init__(self, connection, plugin_id: str):
        self.connection = connection
        self.plugin_id = plugin_id
        self.provider = connection.platform
        self.display_name = connection.platform.replace("_", " ").title()

    def _var(self, overrides: dict, name: str | None) -> str:
        if not name:
            return ""
        return str(overrides.get(name.lower()) or overrides.get(name.upper()) or overrides.get(name) or "").strip()

    def _client_id(self, overrides: dict) -> str:
        value = self._var(overrides, self.connection.client_id_var)
        if not value:
            raise ValueError(f"{self.connection.client_id_var} not configured for plugin connection {self.provider}")
        return value

    def _client_secret(self, overrides: dict) -> str:
        value = self._var(overrides, self.connection.client_secret_var)
        if not value:
            raise ValueError(f"{self.connection.client_secret_var} not configured for plugin connection {self.provider}")
        return value

    def _redirect_uri(self, settings, overrides: dict) -> str:
        configured = self._var(overrides, self.connection.redirect_uri_var)
        if configured:
            return configured
        base = (settings.frontend_url or "http://localhost").rstrip("/")
        callback_path = self.connection.callback_path or f"/social/{self.provider}/callback"
        if not callback_path.startswith("/"):
            callback_path = "/" + callback_path
        return f"{base}{callback_path}"

    async def start_login(self, settings, overrides: dict | None = None) -> LoginStart:
        overrides = overrides or {}
        if self.connection.type != "oauth2":
            raise ValueError(f"Unsupported plugin connection type: {self.connection.type}")
        if not self.connection.auth_url or not self.connection.token_url:
            raise ValueError(f"Plugin connection {self.provider} is missing auth_url/token_url")
        state = secrets.token_hex(16)
        redirect_uri = self._redirect_uri(settings, overrides)
        params: dict[str, Any] = {
            self.connection.auth_client_param: self._client_id(overrides),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        if self.connection.scopes:
            params["scope"] = self.connection.scope_separator.join(self.connection.scopes)
        params.update(self.connection.authorization_params or {})
        return LoginStart(
            login_type="browser",
            authorize_url=f"{self.connection.auth_url}?{urlencode(params)}",
            state=state,
            verifier=state,
            redirect_uri=redirect_uri,
        )

    async def complete_login(self, code: str, settings, *, state: str, verifier: str, redirect_uri: str, overrides: dict | None = None) -> OAuthCredential:
        overrides = overrides or {}
        if not code:
            raise ValueError("Missing authorization code")
        payload: dict[str, Any] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            self.connection.token_client_param: self._client_id(overrides),
            self.connection.token_client_secret_param: self._client_secret(overrides),
        }
        payload.update(self.connection.token_params or {})
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                self.connection.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=payload,
            )
            response.raise_for_status()
            token_data = response.json()

        access_token = _dig_path(token_data, self.connection.access_token_path)
        if not access_token:
            raise ValueError(f"Plugin connection {self.provider} token exchange failed — no access token")
        refresh_token = _dig_path(token_data, self.connection.refresh_token_path)
        expires_in = _dig_path(token_data, self.connection.expires_in_path)
        expires_at = None
        if expires_in is not None:
            try:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            except Exception:
                expires_at = None

        account: dict[str, Any] = {"id": self.provider, "name": self.display_name}
        if self.connection.userinfo_url:
            params = dict(self.connection.userinfo_params or {})
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            headers.update(self.connection.userinfo_headers or {})
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(self.connection.userinfo_url, params=params, headers=headers)
                response.raise_for_status()
                userinfo = response.json()
            account = {
                "id": str(_dig_path(userinfo, self.connection.id_path, self.provider)),
                "name": str(_dig_path(userinfo, self.connection.name_path, self.display_name)),
            }
            if self.connection.handle_path:
                account["username"] = str(_dig_path(userinfo, self.connection.handle_path, ""))
            if self.connection.email_path:
                email = _dig_path(userinfo, self.connection.email_path)
                if email:
                    account["email"] = str(email)

        return OAuthCredential(
            access_token=str(access_token),
            refresh_token=str(refresh_token) if refresh_token else None,
            expires_at=expires_at,
            metadata={"account": account, "plugin_id": self.plugin_id, "platform": self.provider},
        )

    async def refresh_auth(self, refresh_token: str, settings, overrides: dict | None = None) -> OAuthCredential:
        overrides = overrides or {}
        if not self.connection.token_url:
            raise ValueError(f"Plugin connection {self.provider} is missing token_url")
        payload: dict[str, Any] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            self.connection.token_client_param: self._client_id(overrides),
            self.connection.token_client_secret_param: self._client_secret(overrides),
        }
        payload.update(self.connection.token_params or {})
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                self.connection.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=payload,
            )
            response.raise_for_status()
            data = response.json()
        access_token = _dig_path(data, self.connection.access_token_path)
        if not access_token:
            raise ValueError(f"Plugin connection {self.provider} refresh failed")
        expires_in = _dig_path(data, self.connection.expires_in_path, 3600)
        return OAuthCredential(
            access_token=str(access_token),
            refresh_token=str(_dig_path(data, self.connection.refresh_token_path, refresh_token)),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
            metadata={"plugin_id": self.plugin_id, "platform": self.provider},
        )


_OAUTH_HANDLERS: dict[str, OAuthProviderHandler] = {
    "openai": OpenAICodexOAuthHandler(),
    "gemini": GeminiOAuthHandler(),
    "gmail": GmailOAuthHandler(),
    "google_calendar": GoogleCalendarOAuthHandler(),
    "youtube": YouTubeOAuthHandler(),
    "tiktok": TikTokOAuthHandler(),
    "google_drive": GoogleDriveOAuthHandler(),
    "google_business": GoogleBusinessOAuthHandler(),
    "facebook": FacebookOAuthHandler(),
    "instagram": InstagramOAuthHandler(),
    "google": GoogleLoginOAuthHandler(),
}


def get_oauth_handler(provider: str):
    built_in = _OAUTH_HANDLERS.get(provider)
    if built_in:
        return built_in
    try:
        from plugin_loader import get_plugin_connection
        found = get_plugin_connection(provider)
        if found:
            state, connection = found
            return GenericPluginOAuthHandler(connection, state.manifest.plugin_id)
    except Exception:
        return None
    return None


def get_auth_supported(provider: str) -> list[str]:
    supports: list[str] = []
    if is_ai_provider(provider):
        supports.extend(get_ai_auth_supported(provider))
    elif provider in _OAUTH_HANDLERS and provider != "gemini":
        supports.append("oauth")
    elif get_oauth_handler(provider):
        supports.append("oauth")
    return list(dict.fromkeys(supports))


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


def _http_detail_code(exc: HTTPException) -> str | None:
    detail = exc.detail
    if isinstance(detail, dict):
        error = detail.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            return str(code) if code else None
    return None


async def resolve_stored_provider_credential(
    db: AsyncSession,
    workspace_id,
    provider: str,
    settings,
    brand_id=None,
    *,
    tolerate_decryption_failure: bool = False,
) -> tuple[str | None, str | None]:
    rows: list[ProviderKey] = []
    if isinstance(brand_id, str):
        try:
            brand_id = uuid.UUID(brand_id)
        except ValueError:
            brand_id = None
    if brand_id:
        # Prefer a brand-owned credential, then fall back to the workspace/org
        # credential saved in Admin. Operators commonly configure one OpenAI or
        # BytePlus key at workspace scope and expect brand-scoped CMO/media runs
        # to use it unless a brand-specific override exists. If a stored row was
        # encrypted with an old ENCRYPTION_KEY, execution paths can tolerate that
        # decryption failure and continue to the workspace/platform fallback.
        brand_row = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == workspace_id,
                ProviderKey.brand_id == brand_id,
                ProviderKey.provider == provider,
            )
        )).scalar_one_or_none()
        if brand_row is not None:
            rows.append(brand_row)
        workspace_row = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == workspace_id,
                ProviderKey.brand_id == None,  # noqa: E711
                ProviderKey.provider == provider,
            )
        )).scalar_one_or_none()
        if workspace_row is not None:
            rows.append(workspace_row)
    else:
        row = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == workspace_id,
                ProviderKey.brand_id == None,  # noqa: E711
                ProviderKey.provider == provider,
            )
        )).scalar_one_or_none()
        if row is not None:
            rows.append(row)
    if not rows:
        return None, None

    def _decrypt_or_none(row: ProviderKey, value: str | None, field: str) -> str | None:
        if not value:
            return None
        try:
            return decrypt_secret(value, settings)
        except HTTPException as exc:
            if tolerate_decryption_failure and _http_detail_code(exc) == "DECRYPTION_FAILED":
                logger.warning(
                    "Stored %s credential for provider=%s workspace_id=%s brand_id=%s could not be decrypted; treating it as unavailable",
                    field,
                    row.provider,
                    row.workspace_id,
                    row.brand_id,
                )
                return None
            raise

    for row in rows:
        if row.auth_mode == "oauth":
            token = _decrypt_or_none(row, row.key_encrypted, "oauth_access_token")
            if not token:
                continue
            if row.expires_at and row.expires_at <= datetime.now(timezone.utc):
                if not row.refresh_token_encrypted:
                    continue
                handler = get_oauth_handler(provider)
                if not handler:
                    continue
                refresh_token = _decrypt_or_none(row, row.refresh_token_encrypted, "oauth_refresh_token")
                if not refresh_token:
                    continue
                refreshed = await handler.refresh_auth(refresh_token, settings)
                row.key_encrypted = encrypt_secret(refreshed.access_token, settings)
                row.refresh_token_encrypted = (
                    encrypt_secret(refreshed.refresh_token, settings) if refreshed.refresh_token else None
                )
                row.expires_at = refreshed.expires_at
                row.metadata_json = refreshed.metadata
                await db.commit()
                token = refreshed.access_token
            return token, "oauth"

        token = _decrypt_or_none(row, row.key_encrypted, "api_key")
        if token:
            return token, "api_key"

    return None, None


# ── Auth relay helpers ────────────────────────────────────────────────────────

# Google platforms that can use the central relay for token refresh.
GOOGLE_RELAY_PLATFORMS: frozenset[str] = frozenset({"gmail", "google_calendar", "youtube", "google_drive", "gemini", "google_business"})


async def relay_claim_handoff(handoff_token: str, settings) -> dict:
    """Claim a one-time handoff token from the central auth relay.

    Returns the token payload: platform, brand_id, access_token, refresh_token,
    expires_at, metadata. Token is deleted from relay Redis on first claim.
    """
    relay = settings.klaroha_relay_url.rstrip("/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{relay}/relay/claim",
            json={"handoff_token": handoff_token, "relay_key": settings.klaroha_relay_key},
        )
        r.raise_for_status()
        return r.json()


async def relay_refresh_token(platform: str, refresh_token: str, settings) -> OAuthCredential:
    """Delegate a Google token refresh to the central auth relay.

    The relay holds the client_secret so it never ships in the BOS Docker image.
    `refresh_token` must be the plaintext (already decrypted) refresh token.
    """
    relay = settings.klaroha_relay_url.rstrip("/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{relay}/relay/refresh",
            json={"platform": platform, "refresh_token": refresh_token, "relay_key": settings.klaroha_relay_key},
        )
        r.raise_for_status()
        data = r.json()
    expires_at = datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return OAuthCredential(
        access_token=data["access_token"],
        refresh_token=None,
        expires_at=expires_at,
    )


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
