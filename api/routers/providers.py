import logging
import uuid
from datetime import datetime, timezone

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

    known = set(model_info) | {"openrouter", "gemini", "nvidia", "openai"}

    providers: list[ProviderInfo] = []
    for provider in sorted(known):
        metadata = stored[provider].metadata_json if provider in stored and stored[provider].metadata_json else {}
        last_check_status = metadata.get("last_check_status") if isinstance(metadata, dict) else None
        last_check_message = metadata.get("last_check_message") if isinstance(metadata, dict) else None
        last_check_at = metadata.get("last_check_at") if isinstance(metadata, dict) else None
        effective_status = model_info.get(provider, {}).get("status", "unknown")
        if provider in stored or get_platform_key(provider, settings):
            # An explicit provider check is the clearest connectivity signal and
            # should override older failed run attempts. Otherwise the UI can show
            # contradictory states like "Error" beside "last check: connected".
            if last_check_status == "ok":
                effective_status = "live"
            elif last_check_status == "error":
                effective_status = "error"
            elif last_attempt_status.get(provider) == "ok":
                effective_status = "live"
            elif last_attempt_status.get(provider) == "error":
                effective_status = "error"
            elif provider in stored:
                effective_status = "stored_unverified"
            elif get_platform_key(provider, settings):
                effective_status = "platform_available"

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
            top_models=top_models.get(provider, []),
        ))

    return {"providers": providers}


# ── POST /providers/keys ───────────────────────────────────────────────────────

@router.post("/keys", status_code=201, summary="Register or replace a direct provider API key")
async def register_key(
    body: KeyRegisterRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()
    ws = await _require_workspace(db)
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
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "KEY_NOT_FOUND", "message": f"No stored credential for provider '{body.provider}'", "details": None}},
        )

    row = (await db.execute(
        select(ProviderKey).where(
            ProviderKey.workspace_id == ws.id,
            ProviderKey.brand_id == target_brand_id if target_brand_id else ProviderKey.brand_id == None,  # noqa: E711
            ProviderKey.provider == body.provider,
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
