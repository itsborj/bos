"""
Council router — direct API access to the council deliberation engine.

Endpoints:
  POST /council/convene        — start a session (same as @council in CMO chat)
  POST /council/{id}/inject    — inject operator context into a running session
  GET  /council/sessions       — list sessions for this workspace
  GET  /council/sessions/{id}  — get full session detail
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from models.council import CouncilSession
from routers.workspace import get_singleton

router = APIRouter(prefix="/council", tags=["council"])


class ConveneRequest(BaseModel):
    brief: str
    brand_id: Optional[str] = None
    operator_injection: str = ""


class ConveneResponse(BaseModel):
    session_id: str
    output: str
    marching_orders: list[str]
    parked_decisions: list[dict]
    rounds_completed: int


class SessionSummary(BaseModel):
    session_id: str
    brief: str
    status: str
    rounds_completed: int
    brand_id: Optional[str]
    created_at: str
    settled_at: Optional[str]


@router.post("/convene", response_model=ConveneResponse)
async def convene(
    body: ConveneRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    from capabilities.workspace.council.module import convene as run_council
    from models.workspace import Brand

    ws = await get_singleton(db)
    brand: Brand | None = None
    if body.brand_id:
        brand = (await db.execute(
            select(Brand).where(Brand.id == uuid.UUID(body.brand_id))
        )).scalar_one_or_none()

    result = await run_council(
        brief=body.brief,
        db=db,
        ws=ws,
        brand=brand,
        operator_injection=body.operator_injection,
    )
    return ConveneResponse(
        session_id=result["session_id"],
        output=result["formatted_output"],
        marching_orders=result["marching_orders"],
        parked_decisions=result["parked_decisions"],
        rounds_completed=len(result["rounds"]),
    )


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    ws_id = ws.id if ws else None
    rows = (await db.execute(
        select(CouncilSession)
        .where(CouncilSession.workspace_id == ws_id)
        .order_by(CouncilSession.created_at.desc())
        .limit(50)
    )).scalars().all()
    return [
        SessionSummary(
            session_id=str(r.id),
            brief=r.brief,
            status=r.status,
            rounds_completed=r.rounds_completed,
            brand_id=str(r.brand_id) if r.brand_id else None,
            created_at=r.created_at.isoformat(),
            settled_at=r.settled_at.isoformat() if r.settled_at else None,
        )
        for r in rows
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    row = (await db.execute(
        select(CouncilSession).where(CouncilSession.id == uuid.UUID(session_id))
    )).scalar_one_or_none()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": str(row.id),
        "brief": row.brief,
        "status": row.status,
        "rounds_completed": row.rounds_completed,
        "rounds": row.rounds,
        "marching_orders": row.marching_orders,
        "parked_decisions": row.parked_decisions,
        "brand_id": str(row.brand_id) if row.brand_id else None,
        "created_at": row.created_at.isoformat(),
        "settled_at": row.settled_at.isoformat() if row.settled_at else None,
    }
