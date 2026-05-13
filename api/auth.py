import hashlib
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _unauthorized(msg: str = "Invalid or missing API key") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"error": {"code": "UNAUTHORIZED", "message": msg, "details": None}},
    )


async def require_api_key(
    api_key: str = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> str:
    if not api_key:
        raise _unauthorized("Missing X-API-Key header")

    from config import get_settings

    # Bootstrap / dev: match against API_SECRET_KEY env var (never stored in DB)
    if api_key == get_settings().api_secret_key:
        return api_key

    # DB-backed key lookup
    from models.api_key import ApiKey

    row = await db.execute(select(ApiKey).where(ApiKey.key_hash == _hash(api_key)))
    key_record = row.scalar_one_or_none()
    if not key_record:
        raise _unauthorized()

    # Track last usage
    key_record.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return api_key
