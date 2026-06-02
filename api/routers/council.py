"""
Council router — live boardroom deliberation API.

Endpoints:
  GET  /council/seats              — list all seat configs
  PUT  /council/seats/{seat_id}    — update a seat (writes SKILL.md)
  POST /council/convene            — start session, run Round 1, return + C6 prompt
  POST /council/{id}/c6-respond    — C6 injects or passes, run next round
  POST /council/{id}/finalize      — C6 closes session, extract settlement
  GET  /council/sessions           — list sessions for this workspace
  GET  /council/sessions/{id}      — full session detail
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from models.council import CouncilSession
from routers.workspace import get_singleton

router = APIRouter(prefix="/council", tags=["council"])

_SEATS_DIR = Path(__file__).parent.parent / "capabilities" / "workspace" / "council" / "seats"


# ── Seat schema ───────────────────────────────────────────────────────────────

class SeatConfig(BaseModel):
    seat_id: str
    display_name: str
    status: str
    provider: str
    model_id: Optional[str] = None
    ideology: Optional[str] = None


class SeatUpdateRequest(BaseModel):
    display_name: str
    status: str
    provider: str
    model_id: Optional[str] = None
    ideology: Optional[str] = None


def _read_seat(seat_dir: Path) -> SeatConfig | None:
    skill_path = seat_dir / "SKILL.md"
    if not skill_path.exists():
        return None
    raw = skill_path.read_text()
    parts = raw.split("---", 2)
    if len(parts) < 2:
        return None
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None
    model = meta.get("model") or {}
    return SeatConfig(
        seat_id=meta.get("seat", seat_dir.name),
        display_name=meta.get("display_name", ""),
        status=meta.get("status", "vacant"),
        provider=model.get("provider") or "openrouter",
        model_id=model.get("model_id") or None,
        ideology=meta.get("ideology") or None,
    )


def _write_seat(seat_dir: Path, seat_id: str, update: SeatUpdateRequest) -> None:
    skill_path = seat_dir / "SKILL.md"
    model_id_yaml = f'"{update.model_id}"' if update.model_id else "~"
    ideology_yaml = f'"{update.ideology}"' if update.ideology else "~"
    content = f"""---
seat: {seat_id}
display_name: "{update.display_name}"
status: {update.status}

model:
  provider: {update.provider}
  model_id: {model_id_yaml}

tools: []

ideology: {ideology_yaml}
---
"""
    skill_path.write_text(content)


# ── Seat endpoints ────────────────────────────────────────────────────────────

@router.get("/seats", response_model=list[SeatConfig])
async def list_seats(_: str = Depends(require_api_key)):
    seats = []
    if not _SEATS_DIR.exists():
        return seats
    for seat_dir in sorted(_SEATS_DIR.iterdir()):
        if not seat_dir.is_dir():
            continue
        seat = _read_seat(seat_dir)
        if seat:
            seats.append(seat)
    return seats


@router.put("/seats/{seat_id}", response_model=SeatConfig)
async def update_seat(
    seat_id: str,
    body: SeatUpdateRequest,
    _: str = Depends(require_api_key),
):
    seat_dir = _SEATS_DIR / seat_id
    if not seat_dir.exists():
        raise HTTPException(status_code=404, detail=f"Seat {seat_id!r} not found")
    _write_seat(seat_dir, seat_id, body)
    seat = _read_seat(seat_dir)
    if not seat:
        raise HTTPException(status_code=500, detail="Failed to read seat after write")
    return seat


# ── Session schemas ───────────────────────────────────────────────────────────

class ConveneRequest(BaseModel):
    brief: str
    brand_id: Optional[str] = None
    safety_ceiling: int = 10


class SessionStateResponse(BaseModel):
    session_id: str
    status: str
    current_round: int
    rounds_completed: int
    rounds: list
    c6_injections: list
    pending_c6_prompt: Optional[str]
    safety_ceiling: int


class C6RespondRequest(BaseModel):
    input: Optional[str] = None  # None or empty = pass


class FinalizeResponse(BaseModel):
    session_id: str
    status: str
    brief: str
    settlement: str
    marching_orders: list[str]
    parked_decisions: list[str]
    c6_injections: list
    rounds_completed: int
    transcript: str


class SessionSummary(BaseModel):
    session_id: str
    brief: str
    status: str
    current_round: int
    rounds_completed: int
    brand_id: Optional[str]
    created_at: str
    settled_at: Optional[str]


# ── Session endpoints ─────────────────────────────────────────────────────────

@router.post("/convene", response_model=SessionStateResponse)
async def convene(
    body: ConveneRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    from capabilities.workspace.council.module import start_session
    from models.workspace import Brand

    ws = await get_singleton(db)
    brand = None
    if body.brand_id:
        brand = (await db.execute(
            select(Brand).where(Brand.id == uuid.UUID(body.brand_id))
        )).scalar_one_or_none()

    result = await start_session(
        brief=body.brief,
        db=db,
        ws=ws,
        brand=brand,
        safety_ceiling=body.safety_ceiling,
    )
    return SessionStateResponse(
        session_id=result["session_id"],
        status=result["status"],
        current_round=result["current_round"],
        rounds_completed=result["rounds_completed"],
        rounds=result["rounds"],
        c6_injections=result["c6_injections"],
        pending_c6_prompt=result["pending_c6_prompt"],
        safety_ceiling=result["safety_ceiling"],
    )


@router.post("/{session_id}/c6-respond", response_model=SessionStateResponse)
async def c6_respond(
    session_id: str,
    body: C6RespondRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    from capabilities.workspace.council.module import process_c6
    from models.workspace import Brand

    row = (await db.execute(
        select(CouncilSession).where(CouncilSession.id == uuid.UUID(session_id))
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if row.status not in ("awaiting_c6",):
        raise HTTPException(status_code=409, detail=f"Session is not awaiting C6 (status: {row.status})")

    ws = await get_singleton(db)
    brand_name = ws.name if ws else "this business"
    if row.brand_id:
        brand = (await db.execute(
            select(Brand).where(Brand.id == row.brand_id)
        )).scalar_one_or_none()
        if brand:
            brand_name = brand.name

    result = await process_c6(
        row=row,
        c6_input=body.input,
        brand_name=brand_name,
        db=db,
    )
    return SessionStateResponse(
        session_id=result["session_id"],
        status=result["status"],
        current_round=result["current_round"],
        rounds_completed=result["rounds_completed"],
        rounds=result["rounds"],
        c6_injections=result["c6_injections"],
        pending_c6_prompt=result["pending_c6_prompt"],
        safety_ceiling=result["safety_ceiling"],
    )


@router.post("/{session_id}/finalize", response_model=FinalizeResponse)
async def finalize_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    from capabilities.workspace.council.module import finalize

    row = (await db.execute(
        select(CouncilSession).where(CouncilSession.id == uuid.UUID(session_id))
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if row.status == "settled":
        raise HTTPException(status_code=409, detail="Session already settled")

    result = await finalize(row=row, db=db)
    return FinalizeResponse(
        session_id=result["session_id"],
        status=result["status"],
        brief=result["brief"],
        settlement=result["settlement"],
        marching_orders=result["marching_orders"],
        parked_decisions=result["parked_decisions"],
        c6_injections=result["c6_injections"],
        rounds_completed=result["rounds_completed"],
        transcript=result["transcript"],
    )


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    rows = (await db.execute(
        select(CouncilSession)
        .where(CouncilSession.workspace_id == (ws.id if ws else None))
        .order_by(CouncilSession.created_at.desc())
        .limit(50)
    )).scalars().all()
    return [
        SessionSummary(
            session_id=str(r.id),
            brief=r.brief,
            status=r.status,
            current_round=r.current_round,
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
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": str(row.id),
        "brief": row.brief,
        "status": row.status,
        "current_round": row.current_round,
        "rounds_completed": row.rounds_completed,
        "rounds": row.rounds,
        "c6_injections": row.c6_injections,
        "pending_c6_prompt": row.pending_c6_prompt,
        "safety_ceiling": row.safety_ceiling,
        "settlement": row.settlement,
        "marching_orders": row.marching_orders,
        "parked_decisions": row.parked_decisions,
        "brand_id": str(row.brand_id) if row.brand_id else None,
        "created_at": row.created_at.isoformat(),
        "settled_at": row.settled_at.isoformat() if row.settled_at else None,
    }
