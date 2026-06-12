from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI(title="Klaroha Auth Relay")

# ── Config ────────────────────────────────────────────────────────────────────

GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
RELAY_KEY            = os.environ.get("RELAY_KEY", "")
RELAY_BASE_URL       = os.environ.get("RELAY_BASE_URL", "http://localhost:8090").rstrip("/")
REDIS_URL            = os.environ.get("REDIS_URL", "redis://redis:6379/0")

_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL     = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL  = "https://www.googleapis.com/oauth2/v1/userinfo"
_GBP_ACCOUNTS_URL   = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
_GBP_INFO_BASE      = "https://mybusinessbusinessinformation.googleapis.com/v1"

_PLATFORM_SCOPES: dict[str, str] = {
    "gmail":           "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly openid email",
    "google_calendar": "https://www.googleapis.com/auth/calendar openid email",
    "youtube":         "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl openid email",
    "google_drive":    "https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/drive.readonly openid email",
    "google_business": "https://www.googleapis.com/auth/business.manage openid email",
    "gemini":          "https://www.googleapis.com/auth/cloud-platform openid email",
}

_PLATFORM_BOS_CALLBACK: dict[str, str] = {
    "gmail":           "/social/gmail/callback",
    "google_calendar": "/social/google-calendar/callback",
    "youtube":         "/social/youtube/callback",
    "google_drive":    "/social/google-drive/callback",
    "google_business": "/social/google-business/callback",
    "gemini":          "/social/gemini/callback",
}

# ── Redis ─────────────────────────────────────────────────────────────────────

_redis: Optional[aioredis.Redis] = None


async def _r() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pkce() -> tuple[str, str]:
    verifier  = urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _check_key(key: str) -> None:
    if not RELAY_KEY:
        raise HTTPException(status_code=500, detail="RELAY_KEY not set on relay")
    if not secrets.compare_digest(key, RELAY_KEY):
        raise HTTPException(status_code=403, detail="Invalid relay_key")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/relay/health")
async def health():
    return {"ok": True}


@app.get("/relay/{platform}/start")
async def relay_start(
    platform: str,
    instance_url: str = Query(...),
    relay_key: str   = Query(...),
    brand_id: str    = Query(...),
):
    _check_key(relay_key)
    if platform not in _PLATFORM_SCOPES:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    verifier, challenge = _pkce()
    state        = secrets.token_hex(16)
    redirect_uri = f"{RELAY_BASE_URL}/relay/google/callback"

    params = {
        "client_id":             GOOGLE_CLIENT_ID,
        "redirect_uri":          redirect_uri,
        "response_type":         "code",
        "scope":                 _PLATFORM_SCOPES[platform],
        "access_type":           "offline",
        "prompt":                "consent",
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
        "state":                 state,
    }

    r = await _r()
    await r.setex(
        f"relay:session:{state}",
        600,
        json.dumps({
            "platform":     platform,
            "instance_url": instance_url.rstrip("/"),
            "brand_id":     brand_id,
            "verifier":     verifier,
            "redirect_uri": redirect_uri,
        }),
    )

    return {"authorize_url": f"{_GOOGLE_AUTHORIZE_URL}?{urlencode(params)}", "session_id": state}


@app.get("/relay/google/callback")
async def google_callback(
    code:  str = "",
    state: str = "",
    error: str = "",
):
    r   = await _r()
    raw = await r.get(f"relay:session:{state}")

    if not raw:
        return RedirectResponse("/relay/error?reason=session_not_found", status_code=302)

    session = json.loads(raw)
    await r.delete(f"relay:session:{state}")

    platform     = session["platform"]
    instance_url = session["instance_url"]
    brand_id     = session["brand_id"]
    verifier     = session["verifier"]
    redirect_uri = session["redirect_uri"]
    bos_callback = _PLATFORM_BOS_CALLBACK.get(platform, f"/social/{platform}/callback")

    if error or not code:
        return RedirectResponse(f"{instance_url}{bos_callback}?error={error or 'no_code'}", status_code=302)

    async with httpx.AsyncClient(timeout=20.0) as client:
        tok = await client.post(_GOOGLE_TOKEN_URL, data={
            "grant_type":    "authorization_code",
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  redirect_uri,
            "code":          code,
            "code_verifier": verifier,
        })

    if not tok.is_success:
        return RedirectResponse(f"{instance_url}{bos_callback}?error=token_exchange_failed", status_code=302)

    token_data   = tok.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return RedirectResponse(f"{instance_url}{bos_callback}?error=no_access_token", status_code=302)

    expires_in = int(token_data.get("expires_in", 3600))
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    metadata: dict = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        ui = await client.get(_GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if ui.is_success:
            u = ui.json()
            metadata["email"] = u.get("email", "")
            metadata["name"]  = u.get("name", "")

    if platform == "youtube":
        async with httpx.AsyncClient(timeout=10.0) as client:
            ch = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "id", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if ch.is_success:
                items = ch.json().get("items", [])
                if items:
                    metadata["channel_id"] = items[0].get("id")

    if platform == "google_business":
        metadata["gbp_error"] = "no_account_returned"
        async with httpx.AsyncClient(timeout=10.0) as client:
            accounts_resp = await client.get(
                _GBP_ACCOUNTS_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if accounts_resp.is_success:
                accounts = accounts_resp.json().get("accounts", [])
                if accounts:
                    metadata["gbp_error"] = "no_location_returned"
                for account in accounts:
                    account_name = account.get("name")
                    if not account_name:
                        continue
                    locations_resp = await client.get(
                        f"{_GBP_INFO_BASE}/{account_name}/locations",
                        params={"readMask": "name,title"},
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    if not locations_resp.is_success:
                        try:
                            metadata["gbp_error"] = (
                                (locations_resp.json().get("error") or {}).get("message")
                                or f"locations_http_{locations_resp.status_code}"
                            )
                        except Exception:
                            metadata["gbp_error"] = f"locations_http_{locations_resp.status_code}"
                        continue
                    locations = locations_resp.json().get("locations", [])
                    if locations:
                        location = locations[0]
                        metadata["account_name"] = account_name
                        metadata["location_name"] = location.get("name", "")
                        metadata["business_name"] = location.get("title", "")
                        metadata.pop("gbp_error", None)
                        break
            else:
                try:
                    metadata["gbp_error"] = (
                        (accounts_resp.json().get("error") or {}).get("message")
                        or f"accounts_http_{accounts_resp.status_code}"
                    )
                except Exception:
                    metadata["gbp_error"] = f"accounts_http_{accounts_resp.status_code}"

    handoff = str(uuid.uuid4())
    await r.setex(
        f"relay:handoff:{handoff}",
        60,
        json.dumps({
            "platform":      platform,
            "brand_id":      brand_id,
            "access_token":  access_token,
            "refresh_token": token_data.get("refresh_token"),
            "expires_at":    expires_at,
            "metadata":      metadata,
        }),
    )

    return RedirectResponse(f"{instance_url}{bos_callback}?handoff_token={handoff}", status_code=302)


class ClaimRequest(BaseModel):
    handoff_token: str
    relay_key: str


@app.post("/relay/claim")
async def relay_claim(body: ClaimRequest):
    _check_key(body.relay_key)
    r   = await _r()
    raw = await r.get(f"relay:handoff:{body.handoff_token}")
    if not raw:
        raise HTTPException(status_code=404, detail="Handoff token not found or expired")
    await r.delete(f"relay:handoff:{body.handoff_token}")
    return json.loads(raw)


class RefreshRequest(BaseModel):
    platform: str
    refresh_token: str
    relay_key: str


@app.post("/relay/refresh")
async def relay_refresh(body: RefreshRequest):
    _check_key(body.relay_key)
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(_GOOGLE_TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": body.refresh_token,
        })
    if not r.is_success:
        raise HTTPException(status_code=502, detail=f"Google refresh failed: {r.text[:300]}")
    data = r.json()
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="No access_token in Google refresh response")
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600)))
    ).isoformat()
    return {"access_token": access_token, "expires_at": expires_at}


@app.get("/relay/error")
async def relay_error(reason: str = "unknown"):
    return {"error": reason}
