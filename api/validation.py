from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import HTTPException
from pydantic import BeforeValidator


def is_nullish(value: Any) -> bool:
    return value is None or value == "" or str(value).lower() in {"null", "none", "undefined"}


def parse_optional_uuid(value: Any, loc: list[str]) -> uuid.UUID | None:
    if is_nullish(value):
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": loc, "msg": "value is not a valid UUID", "type": "uuid_parsing"}],
        )


def _coerce_nullable_uuid(v: Any) -> Any:
    """Convert null-ish strings to None before UUID parsing."""
    if is_nullish(v):
        return None
    return v


NullableUUID = Annotated[uuid.UUID | None, BeforeValidator(_coerce_nullable_uuid)]


def parse_optional_datetime(value: Any, loc: list[str]) -> datetime | None:
    if is_nullish(value):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": loc, "msg": "value is not a valid datetime", "type": "datetime_parsing"}],
        )
