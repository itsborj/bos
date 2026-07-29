import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_provider_registry import is_ai_provider, list_ai_provider_ids, list_dominant_text_provider_ids
from auth import require_api_key
from config import get_settings
from db import get_db
from executor import get_adapter, get_platform_key
from models.capability import Capability, ModelOption
from models.provider import ProviderKey, ProviderLoginSession
from models.workspace import Brand
from models.run import Run, RunAttempt
from provider_auth import (
    decrypt_secret,
    encrypt_secret,
    get_auth_supported,
    get_oauth_handler,
    resolve_stored_provider_credential,
)
from routers.workspace import get_singleton
from validation import NullableUUID, is_nullish, parse_optional_uuid
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


async def _resolve_brand_id(db: AsyncSession, workspace_id, brand_id: uuid.UUID | str | None, loc: list[str] | None = None):
    if is_nullish(brand_id):
        return None
    bid = parse_optional_uuid(brand_id, loc or ["query", "brand_id"])
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
            if row.brand_id is None and row.provider not in scoped:
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

@router.get("", response_model=dict[str, list[ProviderInfo]], summary="List active providers with auth status", responses={404: {"description": "Brand not found"}})
async def list_providers(
    brand_id: NullableUUID = Query(None),
    include_available: bool = Query(False, description="Include supported but not yet configured providers for add/connect UI"),
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
        lat_stmt = (
            select(RunAttempt.provider, func.avg(RunAttempt.latency_ms))
            .join(Run, RunAttempt.run_id == Run.id)
            .where(Run.workspace_id == ws.id)
        )
        if target_brand_id:
            lat_stmt = lat_stmt.where(Run.brand_id == target_brand_id)
        lat_rows = (await db.execute(lat_stmt.group_by(RunAttempt.provider))).all()
        latencies = {r.provider: r[1] for r in lat_rows}

        attempt_stmt = (
            select(RunAttempt.provider, RunAttempt.status, RunAttempt.error, RunAttempt.created_at)
            .join(Run, RunAttempt.run_id == Run.id)
            .where(Run.workspace_id == ws.id)
        )
        if target_brand_id:
            attempt_stmt = attempt_stmt.where(Run.brand_id == target_brand_id)
        attempt_rows = (await db.execute(
            attempt_stmt.order_by(RunAttempt.created_at.desc())
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

    # Default view is intentionally activation-based. The static provider
    # registry is a capability catalog, not a health list: unsupported-looking
    # inactive rows (for example Anthropic with no key) should not appear until
    # they are configured, have a platform key, or have runtime history. Admin
    # add/connect UI can request include_available=true to show the catalog.
    known = {
        provider
        for provider in stored
        if is_ai_provider(provider)
    }
    known.update(
        provider
        for provider in list_ai_provider_ids()
        if get_platform_key(provider, settings)
    )
    known.update(
        provider
        for provider in last_used
        if is_ai_provider(provider)
    )
    if include_available:
        known.update(list_ai_provider_ids())

    providers: list[ProviderInfo] = []
    for provider in sorted(known):
        metadata = stored[provider].metadata_json if provider in stored and stored[provider].metadata_json else {}
        last_check_status = metadata.get("last_check_status") if isinstance(metadata, dict) else None
        last_check_message = metadata.get("last_check_message") if isinstance(metadata, dict) else None
        last_check_at = metadata.get("last_check_at") if isinstance(metadata, dict) else None
        effective_status = model_info.get(provider, {}).get("status", "unknown")
        platform_available = bool(get_platform_key(provider, settings))
        stored_row = stored.get(provider)
        expires_at = stored_row.expires_at if stored_row else None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        is_expired = bool(expires_at and expires_at <= datetime.now(timezone.utc))
        if provider in stored or platform_available:
            # An explicit provider check is the clearest connectivity signal and
            # should override older failed run attempts. Otherwise the UI can show
            # contradictory states like "Error" beside "last check: connected".
            if is_expired:
                effective_status = "expired"
            elif last_check_status == "ok":
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
                    model_id="gpt-5.5",
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
            expires_at=expires_at if provider in stored else None,
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

@router.post("/keys", status_code=201, summary="Register or replace a direct provider API key", responses={400: {"description": "Invalid provider key"}, 412: {"description": "Workspace not initialized"}})
async def register_key(
    body: KeyRegisterRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    # AI providers can be workspace defaults or brand/client BYOK overrides.
    # Channel providers remain brand-scoped unless the workspace has a single brand.
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

    if is_ai_provider(body.provider):
        # Agency/company operators usually set a workspace default, then override
        # selected client brands with BYOK. Supplying brand_id stores the key at
        # that brand scope; omitting it keeps the key as the workspace default.
        target_brand_id = await _resolve_brand_id(db, ws.id, body.brand_id, ["body", "brand_id"])
    else:
        target_brand_id = await _resolve_brand_id(db, ws.id, body.brand_id, ["body", "brand_id"])
        if target_brand_id is None:
            brand_rows = (await db.execute(
                select(Brand.id).where(Brand.workspace_id == ws.id).limit(2)
            )).scalars().all()
            if len(brand_rows) == 1:
                target_brand_id = brand_rows[0]
            else:
                raise HTTPException(
                    status_code=422,
                    detail=[{"loc": ["body", "brand_id"], "msg": "brand_id is required when registering a non-AI provider key and the workspace has zero or multiple brands", "type": "value_error"}],
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

@router.get("/keys", response_model=list[KeyListItem], summary="List registered provider keys and workspace channel credentials", responses={404: {"description": "Brand not found"}})
async def list_keys(
    brand_id: NullableUUID = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return []
    target_brand_id = await _resolve_brand_id(db, ws.id, brand_id)
    if target_brand_id:
        # Brand-scoped: only direct API keys for that brand
        rows = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == ws.id,
                ProviderKey.brand_id == target_brand_id,
                ProviderKey.auth_mode == "api_key",
            )
        )).scalars().all()
    else:
        # Workspace-level: API keys + plugin_vars (agency master channel credentials)
        rows = (await db.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == ws.id,
                ProviderKey.brand_id == None,  # noqa: E711
                ProviderKey.auth_mode.in_(["api_key", "plugin_vars"]),
            )
        )).scalars().all()
    return [
        KeyListItem(
            provider=r.provider,
            brand_id=str(r.brand_id) if r.brand_id else None,
            auth_mode=r.auth_mode,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ── DELETE /providers/keys/{provider} ─────────────────────────────────────────

@router.delete("/keys/{provider}", status_code=204, summary="Remove a direct provider API key", responses={404: {"description": "Provider key not found"}})
async def delete_key(
    provider: str,
    brand_id: NullableUUID = Query(None),
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

@router.post("/login", response_model=LoginStartResponse, summary="Start interactive provider login", responses={400: {"description": "Provider login not supported"}, 412: {"description": "Workspace not initialized"}})
async def login_provider(
    body: LoginStartRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await _require_workspace(db)
    if not is_ai_provider(body.provider) or "oauth" not in get_auth_supported(body.provider):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "LOGIN_NOT_SUPPORTED", "message": f"Provider '{body.provider}' is not an AI provider login", "details": None}},
        )
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

@router.post("/login/complete", response_model=LoginCompleteResponse, summary="Complete interactive provider login", responses={400: {"description": "Provider login failed or not supported"}, 404: {"description": "Provider login session not found"}, 412: {"description": "Workspace not initialized"}})
async def complete_login(
    body: LoginCompleteRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await _require_workspace(db)
    if not is_ai_provider(body.provider) or "oauth" not in get_auth_supported(body.provider):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "LOGIN_NOT_SUPPORTED", "message": f"Provider '{body.provider}' is not an AI provider login", "details": None}},
        )
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

@router.delete("/auth/{provider}", status_code=204, summary="Remove any stored provider credential", responses={404: {"description": "Provider auth not found"}})
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


# ── Provider connectivity checks ───────────────────────────────────────────────

@router.post("/check", response_model=CheckResponse, summary="Verify stored provider credential connectivity", responses={404: {"description": "Provider credential not found"}, 412: {"description": "Workspace not initialized"}})
async def check_key(
    body: CheckRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await _require_workspace(db)
    target_brand_id = await _resolve_brand_id(db, ws.id, body.brand_id, ["body", "brand_id"])
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
        if body.provider == "openai" and auth_mode == "oauth" and ok:
            message = "connected via OpenAI OAuth."
        else:
            message = "connected" if ok else "credential rejected or provider unreachable"
    except Exception as exc:
        from providers.openai_codex import QuotaExhaustedError
        if isinstance(exc, QuotaExhaustedError):
            status = "ok"
            message = "connected (usage quota exhausted — will reset automatically)"
        else:
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


def _cache_key(provider: str, api_key: str) -> str:
    return f"{provider}:{hash(api_key)}"


def _is_text_model_id(model_id: str) -> bool:
    return _infer_modality(model_id) == "text"


def _provider_model(
    provider: str,
    model_id: str,
    name: str | None = None,
    *,
    context_length: int = 0,
    quality_tier: str = "medium",
    modality: str | None = None,
    is_free: bool = False,
) -> ProviderModelLive:
    inferred = modality or _infer_modality(model_id)
    return ProviderModelLive(
        provider=provider,
        model_id=model_id,
        name=name or model_id,
        is_free=is_free,
        input_cost_per_token=0.0,
        output_cost_per_token=0.0,
        context_length=context_length,
        quality_tier=quality_tier,
        supports_json=inferred == "text",
        modality=inferred,
    )


def _openai_model_rank(model_id: str) -> tuple[int, str]:
    mid = model_id.lower()
    if mid.startswith("gpt-5"):
        return (0, mid)
    if mid.startswith("gpt-4.1"):
        return (1, mid)
    if mid.startswith("gpt-4o"):
        return (2, mid)
    if mid.startswith("o"):
        return (3, mid)
    if mid.startswith(("gpt-", "chatgpt-")):
        return (4, mid)
    return (99, mid)


def _openai_text_models_from_payload(data: dict, *, limit: int = 3) -> list[ProviderModelLive]:
    blocked = (
        "audio", "embedding", "image", "realtime", "search", "speech", "tts",
        "transcribe", "whisper", "vision", "dall-e", "preview", "beta", "mini", "nano", "moderation",
    )
    rows = []
    for m in data.get("data", []):
        model_id = str((m or {}).get("id") or "").strip()
        mid = model_id.lower()
        if not model_id or not (mid.startswith("gpt-") or mid.startswith("chatgpt-") or mid.startswith("o")):
            continue
        if any(token in mid for token in blocked):
            continue
        rows.append((m, model_id))
    rows.sort(key=lambda pair: (_openai_model_rank(pair[1])[0], -int((pair[0] or {}).get("created") or 0), pair[1].lower()))
    return [
        _provider_model("openai", model_id, model_id, quality_tier="high", modality="text")
        for _, model_id in rows[:limit]
    ]


def _gemini_model_rank(model_id: str) -> tuple[int, str]:
    mid = model_id.lower()
    if "2.5-pro" in mid:
        return (0, mid)
    if "2.5-flash" in mid:
        return (1, mid)
    if "2.0-flash" in mid:
        return (2, mid)
    if "1.5-pro" in mid:
        return (3, mid)
    if "1.5-flash" in mid:
        return (4, mid)
    return (9, mid)


def _gemini_text_models_from_payload(data: dict, *, limit: int = 3) -> list[ProviderModelLive]:
    rows = []
    for m in data.get("models", []):
        raw_name = str((m or {}).get("name") or "").strip()
        model_id = raw_name.split("/", 1)[1] if raw_name.startswith("models/") else raw_name
        mid = model_id.lower()
        methods = set(m.get("supportedGenerationMethods") or [])
        if not model_id or "generateContent" not in methods:
            continue
        if not mid.startswith("gemini-") or any(x in mid for x in ("embedding", "image", "veo", "tts")):
            continue
        rows.append((m, model_id))
    rows.sort(key=lambda pair: _gemini_model_rank(pair[1]))
    return [
        _provider_model(
            "gemini",
            model_id,
            m.get("displayName") or m.get("display_name") or model_id,
            context_length=int(m.get("inputTokenLimit") or m.get("input_token_limit") or 0),
            quality_tier="high" if "pro" in model_id.lower() else "medium",
            modality="text",
        )
        for m, model_id in rows[:limit]
    ]


def _gemini_video_model_rank(model_id: str) -> tuple[int, str]:
    mid = model_id.lower()
    if "veo-3.1" in mid and "fast" not in mid and "lite" not in mid:
        return (0, mid)
    if "veo-3.1-fast" in mid:
        return (1, mid)
    if "veo-3.1-lite" in mid:
        return (2, mid)
    if "veo-3" in mid:
        return (3, mid)
    if "veo-2" in mid:
        return (4, mid)
    return (9, mid)


def _gemini_video_models_from_payload(data: dict, *, limit: int = 3) -> list[ProviderModelLive]:
    """Return Gemini/Veo long-running video models from the native model list."""
    rows = []
    for m in data.get("models", []):
        raw_name = str((m or {}).get("name") or "").strip()
        model_id = raw_name.split("/", 1)[1] if raw_name.startswith("models/") else raw_name
        mid = model_id.lower()
        methods = set(m.get("supportedGenerationMethods") or [])
        if not model_id or "predictLongRunning" not in methods:
            continue
        if "veo" not in mid:
            continue
        rows.append((m, model_id))
    rows.sort(key=lambda pair: _gemini_video_model_rank(pair[1]))
    return [
        _provider_model(
            "gemini",
            model_id,
            m.get("displayName") or m.get("display_name") or model_id,
            context_length=int(m.get("inputTokenLimit") or m.get("input_token_limit") or 0),
            quality_tier="high" if "fast" not in model_id.lower() and "lite" not in model_id.lower() else "medium",
            modality="video",
        )
        for m, model_id in rows[:limit]
    ]


async def _fetch_openai_models(api_key: str, *, limit: int = 3, auth_mode: str | None = None) -> list[ProviderModelLive]:
    cache_key = _cache_key(f"openai_live:{auth_mode or 'api_key'}", api_key)
    cached = _model_cache.get(cache_key)
    if cached and time.time() - cached[1] < _CACHE_TTL:
        return cached[0]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if auth_mode == "oauth":
                from providers.openai_codex import _extract_account_id

                r = await client.get(
                    "https://chatgpt.com/backend-api/codex/models",
                    params={"client_version": "1.0.0"},
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "chatgpt-account-id": _extract_account_id(api_key),
                        "originator": "pi",
                        "User-Agent": "pi (browser)",
                        "accept": "application/json",
                    },
                )
                r.raise_for_status()
                models = [
                    _provider_model(
                        "openai",
                        str(m.get("slug")),
                        m.get("display_name") or m.get("title") or str(m.get("slug")),
                        context_length=int(m.get("context_window") or m.get("max_context_window") or 0),
                        quality_tier="high",
                        modality="text",
                    )
                    for m in (r.json().get("models") or [])[:limit]
                    if m.get("slug")
                ]
            else:
                r = await client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {api_key}"})
                r.raise_for_status()
                models = _openai_text_models_from_payload(r.json(), limit=limit)
    except Exception as exc:
        logger.warning("OpenAI model list fetch failed: %s", exc)
        return _model_cache.get(cache_key, ([], 0))[0]
    _model_cache[cache_key] = (models, time.time())
    return models


async def _fetch_gemini_models(api_key: str, *, limit: int = 3, auth_mode: str | None = None) -> list[ProviderModelLive]:
    cache_key = _cache_key(f"gemini_live:{auth_mode or 'api_key'}", api_key)
    cached = _model_cache.get(cache_key)
    if cached and time.time() - cached[1] < _CACHE_TTL:
        return cached[0]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if auth_mode == "oauth":
                r = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            else:
                r = await client.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": api_key})
            r.raise_for_status()
            payload = r.json()
            models = _gemini_text_models_from_payload(payload, limit=limit) + _gemini_video_models_from_payload(payload, limit=limit)
    except Exception as exc:
        logger.warning("Gemini model list fetch failed: %s", exc)
        return _model_cache.get(cache_key, ([], 0))[0]
    _model_cache[cache_key] = (models, time.time())
    return models


async def _fetch_bytedance_models(api_key: str) -> list[ProviderModelLive]:
    """Live-fetch available BytePlus models and classify by modality."""
    cache_key = _cache_key("bytedance_live", api_key)
    cached = _model_cache.get(cache_key)
    if cached and time.time() - cached[1] < _CACHE_TTL:
        return cached[0]

    try:
        api_key.encode("ascii")
    except UnicodeEncodeError:
        logger.warning(
            "BytePlus API key contains non-ASCII characters — re-enter the key via Admin → AI Providers"
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
        logger.warning("BytePlus model list fetch failed: %s", exc)
        return _model_cache.get(cache_key, ([], 0))[0]

    models = [
        _provider_model(
            "bytedance",
            m.get("id", ""),
            m.get("display_name") or m.get("name") or m.get("id", ""),
            context_length=m.get("context_window") or 0,
        )
        for m in data.get("data", [])
        if m.get("id")
    ]

    _model_cache[cache_key] = (models, time.time())
    return models


async def _fetch_live_text_models(provider: str, api_key: str, *, limit: int = 3, auth_mode: str | None = None) -> list[ProviderModelLive]:
    if provider == "openai":
        return await _fetch_openai_models(api_key, limit=limit, auth_mode=auth_mode)
    if provider == "gemini":
        return await _fetch_gemini_models(api_key, limit=limit, auth_mode=auth_mode)
    if provider == "bytedance":
        all_models = await _fetch_bytedance_models(api_key)
        text_models = [m for m in all_models if _is_text_model_id(m.model_id)]
        # Sort: prefer seed-2-0-pro > seed-2-0-lite > deepseek-v4 > deepseek-v3 > rest
        def _rank(m: ProviderModelLive) -> tuple[int, str]:
            mid = m.model_id.lower()
            if "seed-2-0-pro" in mid:
                return (0, mid)
            if "deepseek-v4-pro" in mid:
                return (1, mid)
            if "seed-2-0-lite" in mid:
                return (2, mid)
            if "deepseek-v3-2" in mid:
                return (3, mid)
            if "deepseek-v4-flash" in mid:
                return (4, mid)
            if "deepseek-r1" in mid:
                return (5, mid)
            if "skylark-pro" in mid:
                return (6, mid)
            return (99, mid)
        text_models.sort(key=_rank)
        return text_models[:limit]
    return []


@router.get("/models", summary="List available models from connected providers")
async def list_provider_models(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Returns available models for CMO Brain and Specialist selection.
    - First-class text providers (OpenAI, Anthropic, Gemini) are fetched live and capped to top 3.
    - OpenRouter free models are fetched live as optional free fallbacks.
    - Legacy seeded catalog remains only for non-dominant providers that do not expose a live catalog here.
    """
    settings = get_settings()
    ws = await get_singleton(db)

    seen: set[tuple[str, str]] = set()
    live_text_models: list[ProviderModelLive] = []
    if ws:
        for provider in list_dominant_text_provider_ids():
            stored_key, auth_mode = await resolve_stored_provider_credential(db, ws.id, provider, settings)
            api_key = stored_key if auth_mode in ("api_key", "oauth") else None
            effective_auth_mode = auth_mode if api_key else None
            if not api_key:
                api_key = get_platform_key(provider, settings)
                effective_auth_mode = "platform" if api_key else None
            if not api_key:
                continue
            for model in await _fetch_live_text_models(provider, api_key, limit=3, auth_mode=effective_auth_mode):
                key = (model.provider, model.model_id)
                if key in seen:
                    continue
                seen.add(key)
                live_text_models.append(model)

    # Live OpenRouter free models remain useful for fallback/proxy use, but are
    # not the source of truth for direct OpenAI/Anthropic/Gemini provider picks.
    free_models = []
    for model in await _fetch_openrouter_free_models():
        key = (model.provider, model.model_id)
        if key not in seen:
            seen.add(key)
            free_models.append(model)

    # Seeded models — only for non-dominant legacy providers (e.g. NVIDIA). The
    # dominant providers above must come from live provider catalogs.
    seeded_provider_rows = (await db.execute(
        select(ModelOption.provider).distinct().where(ModelOption.status == "healthy")
    )).scalars().all()
    dominant = set(list_dominant_text_provider_ids())
    seeded_providers = [p for p in seeded_provider_rows if p != "openrouter" and p not in dominant]

    providers_with_platform_key = {
        p for p in seeded_providers if bool(get_platform_key(p, settings))
    }

    seeded_opts = (await db.execute(
        select(ModelOption)
        .where(ModelOption.provider.in_(seeded_providers))
        .where(ModelOption.status == "healthy")
    )).scalars().all()

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

    # BytePlus — live fetch when a key is available; used by image/video media provider pickers.
    bytedance_models: list[ProviderModelLive] = []
    if ws:
        bd_key, _ = await resolve_stored_provider_credential(db, ws.id, "bytedance", settings)
        if not bd_key:
            bd_key = get_platform_key("bytedance", settings)
        if bd_key:
            bytedance_models = await _fetch_bytedance_models(bd_key)

    return {"models": [m.model_dump() for m in live_text_models + free_models + direct_models + bytedance_models]}
