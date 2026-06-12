import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from executor import get_adapter, get_platform_key
from models.capability import Capability, ModelOption
from models.provider import ProviderKey, ProviderLoginSession
from models.workspace import Brand
from models.run import RunAttempt
from provider_auth import (
    decrypt_secret,
    encrypt_secret,
    get_auth_supported,
    get_oauth_handler,
    resolve_stored_provider_credential,
)
from routers.workspace import get_singleton
from schemas.providers import (
    CheckRequest,
    CheckResponse,
    KeyListItem,
    KeyRegisterRequest,
    LoginCompleteRequest,
    LoginCompleteResponse,
    LoginPrompt,
    LoginStartRequest,
    LoginStartResponse,
    ProviderInfo,
    ProviderModelInfo,
    ProviderModelLive,
)

router = APIRouter(prefix="/providers", tags=["providers"])
logger = logging.getLogger("bos.providers")


async def _require_workspace(db: AsyncSession):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(
            status_code=412,
            detail={"error": {"code": "WORKSPACE_NOT_INITIALIZED", "message": "Initialize workspace first", "details": None}},
        )
    return ws


async def _resolve_brand_id(db: AsyncSession, workspace_id, brand_id: str | None):
    if not brand_id:
        return None
    try:
        bid = uuid.UUID(brand_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid brand_id")
    brand = (await db.execute(
        select(Brand).where(Brand.id == bid, Brand.workspace_id == workspace_id)
    )).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return bid


async def _provider_rows_for_scope(db: AsyncSession, workspace_id, brand_id):
    if brand_id:
        rows = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == workspace_id,
                ProviderKey.provider != "gmail",
            )
        )).scalars().all()
        scoped: dict[str, ProviderKey] = {}
        for row in rows:
            if row.brand_id == brand_id:
                scoped[row.provider] = row
        for row in rows:
            if row.brand_id is None and row.auth_mode != "api_key" and row.provider not in scoped:
                scoped[row.provider] = row
        return scoped
    return {
        row.provider: row
        for row in (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == workspace_id,
                ProviderKey.brand_id == None,  # noqa: E711
            )
        )).scalars().all()
    }


# ── GET /providers ─────────────────────────────────────────────────────────────

@router.get("", response_model=dict[str, list[ProviderInfo]], summary="List all known providers with auth status")
async def list_providers(
    brand_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()

    rows = (await db.execute(
        select(
            ModelOption.provider,
            func.count().label("model_count"),
            func.bool_and(ModelOption.status == "healthy").label("all_healthy"),
        ).group_by(ModelOption.provider)
    )).all()
    model_info = {
        r.provider: {
            "model_count": int(r.model_count or 0),
            "status": "healthy" if r.all_healthy else "degraded",
        }
        for r in rows
    }

    ws = await get_singleton(db)
    stored: dict[str, ProviderKey] = {}
    latencies: dict[str, float] = {}
    last_used: dict[str, object] = {}
    last_attempt_status: dict[str, str] = {}
    target_brand_id = await _resolve_brand_id(db, ws.id, brand_id) if ws else None
    if ws:
        stored = await _provider_rows_for_scope(db, ws.id, target_brand_id)
        lat_rows = (await db.execute(
            select(RunAttempt.provider, func.avg(RunAttempt.latency_ms))
            .group_by(RunAttempt.provider)
        )).all()
        latencies = {r.provider: r[1] for r in lat_rows}

        attempt_rows = (await db.execute(
            select(RunAttempt.provider, RunAttempt.status, RunAttempt.error, RunAttempt.created_at)
            .order_by(RunAttempt.created_at.desc())
        )).all()
        for provider, status, error, created_at in attempt_rows:
            if provider not in last_used:
                last_used[provider] = created_at
                last_attempt_status[provider] = "error" if status == "failed" or error else "ok"

    model_rows = (await db.execute(
        select(ModelOption, Capability.key)
        .join(Capability, Capability.id == ModelOption.capability_id)
        .order_by(
            ModelOption.provider.asc(),
            ModelOption.status.asc(),
            ModelOption.quality_tier.desc(),
            ModelOption.availability_score.desc(),
            ModelOption.latency_ms.asc(),
        )
    )).all()
    top_models: dict[str, list[ProviderModelInfo]] = {}
    seen_models: dict[str, set[str]] = {}
    for option, capability_key in model_rows:
        seen = seen_models.setdefault(option.provider, set())
        if option.model_id in seen or len(top_models.setdefault(option.provider, [])) >= 6:
            continue
        seen.add(option.model_id)
        top_models[option.provider].append(ProviderModelInfo(
            model_id=option.model_id,
            capability=capability_key,
            quality_tier=option.quality_tier,
            latency_ms=option.latency_ms,
            supports_json=option.supports_json,
            status=option.status,
        ))

    known = set(model_info) | {"openrouter", "gemini", "nvidia", "openai", "google", "bytedance"}

    providers: list[ProviderInfo] = []
    for provider in sorted(known):
        metadata = stored[provider].metadata_json if provider in stored and stored[provider].metadata_json else {}
        last_check_status = metadata.get("last_check_status") if isinstance(metadata, dict) else None
        last_check_message = metadata.get("last_check_message") if isinstance(metadata, dict) else None
        last_check_at = metadata.get("last_check_at") if isinstance(metadata, dict) else None
        effective_status = model_info.get(provider, {}).get("status", "unknown")
        platform_available = bool(get_platform_key(provider, settings))
        if provider in stored or platform_available:
            # An explicit provider check is the clearest connectivity signal and
            # should override older failed run attempts. Otherwise the UI can show
            # contradictory states like "Error" beside "last check: connected".
            if last_check_status == "ok":
                effective_status = "live"
            elif last_check_status == "error":
                effective_status = "error"
            elif provider in stored and last_attempt_status.get(provider) == "ok":
                effective_status = "live"
            elif provider in stored and last_attempt_status.get(provider) == "error":
                effective_status = "error"
            elif provider in stored:
                effective_status = "stored_unverified"
            elif platform_available:
                effective_status = "platform_available"

        display_models = top_models.get(provider, [])
        if provider == "openai" and provider in stored and stored[provider].auth_mode == "oauth" and display_models:
            first = display_models[0]
            display_models = [
                ProviderModelInfo(
                    model_id="gpt-5.3-codex",
                    capability=first.capability,
                    quality_tier=first.quality_tier,
                    latency_ms=first.latency_ms,
                    supports_json=first.supports_json,
                    status=first.status,
                ),
                *display_models[1:],
            ]

        providers.append(ProviderInfo(
            provider=provider,
            brand_id=str(target_brand_id) if target_brand_id else None,
            model_count=model_info.get(provider, {}).get("model_count", 0),
            status=effective_status,
            auth_supported=get_auth_supported(provider),
            connected=provider in stored,
            auth_mode=stored[provider].auth_mode if provider in stored else None,
            expires_at=stored[provider].expires_at if provider in stored else None,
            has_platform_key=bool(get_platform_key(provider, settings)),
            has_byok_key=provider in stored and stored[provider].auth_mode == "api_key",
            avg_latency_ms=latencies.get(provider),
            last_used_at=last_used.get(provider),
            last_check_status=last_check_status,
            last_check_message=last_check_message,
            last_check_at=last_check_at,
            top_models=display_models,
        ))

    return {"providers": providers}


# ── POST /providers/keys ───────────────────────────────────────────────────────

@router.post("/keys", status_code=201, summary="Register or replace a direct provider API key")
async def register_key(
    body: KeyRegisterRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    # AI model providers are workspace-level infrastructure — no brand required.
    # Plugin/channel providers (social, email, etc.) remain brand-scoped.
    _AI_PROVIDERS = {"openrouter", "gemini", "nvidia", "openai", "bytedance"}
    settings = get_settings()
    ws = await _require_workspace(db)

    # Reject keys that contain non-ASCII characters — they will silently fail in HTTP headers.
    try:
        body.key.encode("ascii")
    except UnicodeEncodeError:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_KEY", "message": "API key contains non-ASCII characters. Paste the key directly — do not copy masked text.", "details": None}},
        )

    if body.provider in _AI_PROVIDERS:
        target_brand_id = None
    else:
        target_brand_id = await _resolve_brand_id(db, ws.id, body.brand_id)
        if target_brand_id is None:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "BRAND_REQUIRED", "message": "BYOK API keys must be registered against a specific brand", "details": None}},
            )

    existing = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.brand_id == target_brand_id if target_brand_id else ProviderKey.brand_id == None,  # noqa: E711
            ProviderKey.provider == body.provider,
        )
    )).scalar_one_or_none()

    encrypted = encrypt_secret(body.key, settings)
    if existing:
        existing.auth_mode = "api_key"
        existing.key_encrypted = encrypted
        existing.refresh_token_encrypted = None
        existing.expires_at = None
        existing.metadata_json = None
    else:
        db.add(ProviderKey(
            workspace_id=ws.id,
            brand_id=target_brand_id,
            provider=body.provider,
            auth_mode="api_key",
            key_encrypted=encrypted,
            refresh_token_encrypted=None,
            expires_at=None,
            metadata_json=None,
        ))

    await db.commit()
    logger.info("Provider API key registered for provider '%s' brand_id=%s", body.provider, target_brand_id)
    return {"provider": body.provider, "brand_id": str(target_brand_id) if target_brand_id else None, "status": "registered"}


# ── GET /providers/keys ────────────────────────────────────────────────────────

@router.get("/keys", response_model=list[KeyListItem], summary="List registered direct provider API keys")
async def list_keys(
    brand_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return []
    target_brand_id = await _resolve_brand_id(db, ws.id, brand_id)
    rows = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.brand_id == target_brand_id if target_brand_id else ProviderKey.brand_id == None,  # noqa: E711
            ProviderKey.auth_mode == "api_key",
        )
    )).scalars().all()
    return [KeyListItem(provider=r.provider, brand_id=str(r.brand_id) if r.brand_id else None, created_at=r.created_at) for r in rows]


# ── DELETE /providers/keys/{provider} ─────────────────────────────────────────

@router.delete("/keys/{provider}", status_code=204, summary="Remove a direct provider API key")
async def delete_key(
    provider: str,
    brand_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    target_brand_id = await _resolve_brand_id(db, ws.id, brand_id) if ws else None
    row = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.brand_id == target_brand_id if target_brand_id else ProviderKey.brand_id == None,  # noqa: E711
            ProviderKey.provider == provider,
            ProviderKey.auth_mode == "api_key",
        )
    )).scalar_one_or_none() if ws else None

    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "KEY_NOT_FOUND", "message": f"No API key registered for provider '{provider}'", "details": None}},
        )
    await db.delete(row)
    await db.commit()


# ── POST /providers/login ──────────────────────────────────────────────────────

@router.post("/login", response_model=LoginStartResponse, summary="Start interactive provider login")
async def login_provider(
    body: LoginStartRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await _require_workspace(db)
    handler = get_oauth_handler(body.provider)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "LOGIN_NOT_SUPPORTED", "message": f"Provider '{body.provider}' does not support login auth", "details": None}},
        )

    start = await handler.start_login(settings)

    for row in (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.workspace_id == ws.id,
            ProviderLoginSession.provider == body.provider,
        )
    )).scalars().all():
        await db.delete(row)
    await db.flush()

    session = ProviderLoginSession(
        workspace_id=ws.id,
        provider=body.provider,
        login_type=start.login_type,
        state=start.state or "",
        verifier_encrypted=encrypt_secret(start.verifier or "", settings),
        redirect_uri=start.redirect_uri or "",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return LoginStartResponse(
        provider=body.provider,
        auth_mode="oauth",
        login_id=str(session.id),
        login=LoginPrompt(
            type=start.login_type,
            authorize_url=start.authorize_url,
            user_code=start.user_code,
            verification_uri=start.verification_uri,
        ),
    )


# ── POST /providers/login/complete ────────────────────────────────────────────

@router.post("/login/complete", response_model=LoginCompleteResponse, summary="Complete interactive provider login")
async def complete_login(
    body: LoginCompleteRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await _require_workspace(db)
    handler = get_oauth_handler(body.provider)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "LOGIN_NOT_SUPPORTED", "message": f"Provider '{body.provider}' does not support login auth", "details": None}},
        )

    login = (await db.execute(
        select(ProviderLoginSession).where(
            ProviderLoginSession.id == body.login_id,
            ProviderLoginSession.workspace_id == ws.id,
            ProviderLoginSession.provider == body.provider,
        )
    )).scalar_one_or_none()
    if not login:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "LOGIN_SESSION_NOT_FOUND", "message": "Provider login session not found", "details": None}},
        )

    try:
        credential = await handler.complete_login(
            body.callback_url,
            settings,
            state=login.state,
            verifier=decrypt_secret(login.verifier_encrypted, settings),
            redirect_uri=login.redirect_uri,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "LOGIN_FAILED", "message": str(exc), "details": None}},
        )

    existing = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.brand_id == None,  # noqa: E711
            ProviderKey.provider == body.provider,
        )
    )).scalar_one_or_none()

    if existing:
        existing.auth_mode = "oauth"
        existing.key_encrypted = encrypt_secret(credential.access_token, settings)
        existing.refresh_token_encrypted = (
            encrypt_secret(credential.refresh_token, settings) if credential.refresh_token else None
        )
        existing.expires_at = credential.expires_at
        existing.metadata_json = credential.metadata
    else:
        db.add(ProviderKey(
            workspace_id=ws.id,
            brand_id=None,
            provider=body.provider,
            auth_mode="oauth",
            key_encrypted=encrypt_secret(credential.access_token, settings),
            refresh_token_encrypted=(
                encrypt_secret(credential.refresh_token, settings) if credential.refresh_token else None
            ),
            expires_at=credential.expires_at,
            metadata_json=credential.metadata,
        ))

    await db.delete(login)
    await db.commit()
    logger.info("Provider login completed for provider '%s'", body.provider)
    return LoginCompleteResponse(
        provider=body.provider,
        connected=True,
        auth_mode="oauth",
        expires_at=credential.expires_at,
    )


# ── DELETE /providers/auth/{provider} ─────────────────────────────────────────

@router.delete("/auth/{provider}", status_code=204, summary="Remove any stored provider credential")
async def delete_auth(
    provider: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    row = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.brand_id == None,  # noqa: E711
            ProviderKey.provider == provider,
        )
    )).scalar_one_or_none() if ws else None
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "AUTH_NOT_FOUND", "message": f"No stored credential for provider '{provider}'", "details": None}},
        )
    await db.delete(row)
    await db.commit()


# ── POST /providers/check ──────────────────────────────────────────────────────

@router.post("/check", response_model=CheckResponse, summary="Verify stored provider credential connectivity")
async def check_key(
    body: CheckRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await _require_workspace(db)
    target_brand_id = await _resolve_brand_id(db, ws.id, body.brand_id)
    api_key, auth_mode = await resolve_stored_provider_credential(db, ws.id, body.provider, settings, brand_id=target_brand_id)
    if not api_key:
        platform_key = get_platform_key(body.provider, settings)
        if platform_key:
            api_key = platform_key
            auth_mode = "platform"

    if not api_key:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "KEY_NOT_FOUND", "message": f"No stored credential or platform key for provider '{body.provider}'", "details": None}},
        )

    row = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.brand_id == target_brand_id if target_brand_id else ProviderKey.brand_id == None,  # noqa: E711
            ProviderKey.provider == body.provider,
        )
    )).scalar_one_or_none()
    if row is None and target_brand_id:
        row = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == ws.id,
                ProviderKey.brand_id == None,  # noqa: E711
                ProviderKey.provider == body.provider,
                ProviderKey.auth_mode != "api_key",
            )
        )).scalar_one_or_none()

    try:
        ok = await get_adapter(body.provider, api_key, auth_mode).check()
        status = "ok" if ok else "error"
        message = "connected" if ok else "credential rejected or provider unreachable"
    except Exception as exc:
        logger.warning("Provider check failed for '%s': %s", body.provider, exc)
        status = "error"
        message = str(exc)

    if row:
        metadata = dict(row.metadata_json or {})
        metadata.update({
            "last_check_status": status,
            "last_check_message": message,
            "last_check_at": datetime.now(timezone.utc).isoformat(),
        })
        row.metadata_json = metadata
        await db.commit()

    return CheckResponse(provider=body.provider, status=status, message=message, auth_mode=auth_mode)


# ── GET /providers/models ──────────────────────────────────────────────────────
# In-memory cache: {cache_key: (models_list, fetched_at_epoch)}
_model_cache: dict[str, tuple[list[ProviderModelLive], float]] = {}
_CACHE_TTL = 3600  # 1 hour


def _openrouter_quality_tier(model_id: str) -> str:
    mid = model_id.lower()
    if any(x in mid for x in ["70b", "72b", "671b", "405b", "r1", "qwen-2.5-72"]):
        return "high"
    if any(x in mid for x in ["8b", "7b", "9b", "3b", "mini", "small", "phi-3"]):
        return "low"
    return "medium"


async def _fetch_openrouter_free_models() -> list[ProviderModelLive]:
    cache_key = "openrouter_free"
    cached = _model_cache.get(cache_key)
    if cached and time.time() - cached[1] < _CACHE_TTL:
        return cached[0]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"HTTP-Referer": "https://klaroha.com", "X-Title": "Klaroha BOS"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("OpenRouter model list fetch failed: %s", exc)
        return _model_cache.get(cache_key, ([], 0))[0]

    models: list[ProviderModelLive] = []
    for m in data.get("data", []):
        pricing = m.get("pricing", {})
        prompt_price = str(pricing.get("prompt", "1"))
        completion_price = str(pricing.get("completion", "1"))
        if prompt_price != "0" or completion_price != "0":
            continue
        model_id = m.get("id", "")
        if not model_id:
            continue
        models.append(ProviderModelLive(
            provider="openrouter",
            model_id=model_id,
            name=m.get("name", model_id),
            is_free=True,
            input_cost_per_token=0.0,
            output_cost_per_token=0.0,
            context_length=m.get("context_length") or 0,
            quality_tier=_openrouter_quality_tier(model_id),
            supports_json=True,
        ))

    # Sort high quality first, then alphabetically
    tier_order = {"high": 0, "medium": 1, "low": 2}
    models.sort(key=lambda m: (tier_order.get(m.quality_tier, 9), m.name.lower()))

    _model_cache[cache_key] = (models, time.time())
    return models


def _infer_modality(model_id: str) -> str:
    """Infer modality (text/image/video) from model ID naming conventions."""
    mid = model_id.lower()
    if any(x in mid for x in ["video", "t2v", "i2v", "v2v", "veo", "sora", "seedance", "dreamina"]):
        return "video"
    if any(x in mid for x in ["image", "img", "sdxl", "flux", "stable-diff", "imagen", "dall-e", "dall_e",
                               "seedream", "seededit", "t2i", "i2i"]):
        return "image"
    return "text"


# Known image-generation models per provider — surfaced in the image specialist picker
# when the provider is connected. These are not in the seeded text model catalog.
_PROVIDER_IMAGE_MODELS: dict[str, list[dict]] = {
    "openai": [
        {"model_id": "gpt-image-2", "name": "GPT Image 2", "quality_tier": "high"},
        {"model_id": "dall-e-3",    "name": "DALL-E 3",    "quality_tier": "high"},
    ],
    "gemini": [
        {"model_id": "gemini-2.5-flash-image",    "name": "Gemini 2.5 Flash Image",  "quality_tier": "medium"},
        {"model_id": "imagen-4.0-generate-001",   "name": "Imagen 4",                "quality_tier": "high"},
        {"model_id": "imagen-4.0-ultra-generate-001", "name": "Imagen 4 Ultra",      "quality_tier": "high"},
    ],
}


async def _fetch_bytedance_models(api_key: str) -> list[ProviderModelLive]:
    """Live-fetch available models from BytePlus ModelArk and classify by modality."""
    cache_key = "bytedance_live"
    cached = _model_cache.get(cache_key)
    if cached and time.time() - cached[1] < _CACHE_TTL:
        return cached[0]

    try:
        api_key.encode("ascii")
    except UnicodeEncodeError:
        logger.warning(
            "ByteDance ModelArk API key contains non-ASCII characters — re-enter the key via Admin → AI Providers"
        )
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://ark.ap-southeast.bytepluses.com/api/v3/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("ByteDance ModelArk model list fetch failed: %s", exc)
        return _model_cache.get(cache_key, ([], 0))[0]

    models: list[ProviderModelLive] = []
    for m in data.get("data", []):
        model_id = m.get("id", "")
        if not model_id:
            continue
        modality = _infer_modality(model_id)
        models.append(ProviderModelLive(
            provider="bytedance",
            model_id=model_id,
            name=m.get("display_name") or m.get("name") or model_id,
            is_free=False,
            input_cost_per_token=0.0,
            output_cost_per_token=0.0,
            context_length=m.get("context_window") or 0,
            quality_tier="medium",
            supports_json=modality == "text",
            modality=modality,
        ))

    _model_cache[cache_key] = (models, time.time())
    return models


@router.get("/models", summary="List available models from connected providers")
async def list_provider_models(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Returns available models for CMO Brain and Specialist selection.
    - OpenRouter free models: fetched live from OpenRouter API, cached 1 hour.
    - Direct providers (OpenAI, Gemini, NVIDIA): served from seeded model catalog.
    Paid OpenRouter proxy entries are excluded — use direct provider keys for paid models.
    """
    # Live OpenRouter free models
    free_models = await _fetch_openrouter_free_models()

    settings = get_settings()

    # Seeded models — pull every provider in the catalog except openrouter
    # (openrouter is served live above; no hardcoded provider list here)
    seeded_provider_rows = (await db.execute(
        select(ModelOption.provider).distinct().where(ModelOption.status == "healthy")
    )).scalars().all()
    seeded_providers = [p for p in seeded_provider_rows if p != "openrouter"]

    providers_with_platform_key = {
        p for p in seeded_providers if bool(get_platform_key(p, settings))
    }

    seeded_opts = (await db.execute(
        select(ModelOption)
        .where(ModelOption.provider.in_(seeded_providers))
        .where(ModelOption.status == "healthy")
    )).scalars().all()

    seen: set[tuple[str, str]] = set()
    direct_models: list[ProviderModelLive] = []
    for o in seeded_opts:
        key = (o.provider, o.model_id)
        if key in seen:
            continue
        seen.add(key)
        direct_models.append(ProviderModelLive(
            provider=o.provider,
            model_id=o.model_id,
            name=o.model_id,
            is_free=o.provider in providers_with_platform_key,
            input_cost_per_token=float(o.input_cost_per_token),
            output_cost_per_token=float(o.output_cost_per_token),
            context_length=0,
            quality_tier=o.quality_tier,
            supports_json=o.supports_json,
            modality=_infer_modality(o.model_id),
        ))

    ws = await get_singleton(db)

    # Inject known image-generation models for connected providers (not in text catalog).
    # A provider is "connected" if it has a platform key or a stored BYOK key.
    connected_providers = set(providers_with_platform_key)
    if ws:
        byok_rows = (await db.execute(
            select(ProviderKey.provider).where(ProviderKey.workspace_id == ws.id, ProviderKey.brand_id == None)  # noqa: E711
        )).scalars().all()
        connected_providers.update(byok_rows)

    for provider, img_models in _PROVIDER_IMAGE_MODELS.items():
        if provider not in connected_providers:
            continue
        is_free = provider in providers_with_platform_key
        for m in img_models:
            key = (provider, m["model_id"])
            if key in seen:
                continue
            seen.add(key)
            direct_models.append(ProviderModelLive(
                provider=provider,
                model_id=m["model_id"],
                name=m["name"],
                is_free=is_free,
                input_cost_per_token=0.0,
                output_cost_per_token=0.0,
                context_length=0,
                quality_tier=m["quality_tier"],
                supports_json=False,
                modality="image",
            ))

    # ByteDance ModelArk — live fetch when a key is available
    bytedance_models: list[ProviderModelLive] = []
    if ws:
        from provider_auth import resolve_stored_provider_credential
        bd_key, _ = await resolve_stored_provider_credential(db, ws.id, "bytedance", settings)
        if not bd_key:
            bd_key = get_platform_key("bytedance", settings)
        if bd_key:
            bytedance_models = await _fetch_bytedance_models(bd_key)

    return {"models": [m.model_dump() for m in free_models + direct_models + bytedance_models]}
