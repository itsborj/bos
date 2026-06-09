import time
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db import get_db

router = APIRouter(tags=["system"])

_start_time = time.time()


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    git_sha: str
    db: Literal["ok", "error"]
    uptime_seconds: float


@router.get("/", response_model=HealthResponse, summary="Health check")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status: Literal["ok", "error"] = "ok"
    except Exception:
        db_status = "error"

    settings = get_settings()
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version=settings.app_version,
        git_sha=settings.git_sha,
        db=db_status,
        uptime_seconds=round(time.time() - _start_time, 1),
    )
