"""
CMO Agent Harness — pi model: read, execute, write.

Direct execution surface for agents that already know what module to run.
No LLM routing, no SKILL.md matching — the agent owns the decision.

Endpoints:
  GET  /agent/state                 monitor: all brands, pending approvals
  GET  /agent/context/{brand_id}    brand profile + recent runs for brief building
  GET  /agent/capabilities          installed module IDs available for dispatch
  POST /agent/execute               run a module directly, result lands at pending_review
  PATCH /agent/review/{run_id}      approve / reject / flag a run
"""
from __future__ import annotations

import logging
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from memory_events import write_memory_event
from models.run import Run
from models.workspace import Brand
from registry import get_module
from routers.runs import _execute_module, _update_pm_task_status
from routers.workspace import get_singleton
from schemas.runs import RunResponse
from skills.loader import list_skill_manifests

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger("bos.agent")


# ── Schemas ───────────────────────────────────────────────────────────────────

class BrandState(BaseModel):
    brand_id: str
    name: str
    pending_approvals: int
    pm_sync_enabled: bool


class AgentStateResponse(BaseModel):
    workspace_name: str
    brands: list[BrandState]
    total_pending: int


class AgentContextResponse(BaseModel):
    brand_id: str
    name: str
    voice: str
    tone: str
    values: list[str]
    domain: str
    website_url: str
    social_handles: dict
    pm_config: Optional[dict]
    recent_approved_run_ids: list[str]


class AgentCapability(BaseModel):
    module_id: str
    label: str
    description: str
    triggers: list[str]


class AgentExecuteRequest(BaseModel):
    module_id: str
    brand_id: Optional[UUID] = None
    brief: dict = {}


class AgentReviewRequest(BaseModel):
    action: Literal["approve", "reject", "flag"]
    reason: Optional[str] = None


class AgentReviewResponse(BaseModel):
    run_id: str
    approval_status: str
    reason: Optional[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/state", response_model=AgentStateResponse, summary="CMO state: all brands and pending approvals", responses={412: {"description": "Workspace not initialized"}})
async def get_agent_state(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    brands = (await db.execute(select(Brand).order_by(Brand.name))).scalars().all()

    pending_rows = (await db.execute(
        select(Run.brand_id, func.count().label("cnt"))
        .where(Run.approval_status == "pending", Run.brand_id.isnot(None))
        .group_by(Run.brand_id)
    )).all()
    pending_by_brand = {str(row.brand_id): row.cnt for row in pending_rows}

    brand_states = [
        BrandState(
            brand_id=str(b.id),
            name=b.name,
            pending_approvals=pending_by_brand.get(str(b.id), 0),
            pm_sync_enabled=bool(((b.brand_json or {}).get("pm_config") or {}).get("sync_enabled")),
        )
        for b in brands
    ]

    return AgentStateResponse(
        workspace_name=ws.name or "",
        brands=brand_states,
        total_pending=sum(b.pending_approvals for b in brand_states),
    )


@router.get("/context/{brand_id}", response_model=AgentContextResponse, summary="Brand context for brief building", responses={404: {"description": "Brand not found"}})
async def get_agent_context(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    brand_uuid = brand_id

    brand = (await db.execute(select(Brand).where(Brand.id == brand_uuid))).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    bj = brand.brand_json or {}
    recent_run_ids = (await db.execute(
        select(Run.id)
        .where(Run.brand_id == brand_uuid, Run.approval_status == "approved")
        .order_by(Run.created_at.desc())
        .limit(5)
    )).scalars().all()

    return AgentContextResponse(
        brand_id=str(brand.id),
        name=brand.name,
        voice=bj.get("voice") or "",
        tone=bj.get("tone") or "",
        values=bj.get("values") or [],
        domain=bj.get("domain") or "",
        website_url=bj.get("website_url") or "",
        social_handles=bj.get("social_handles") or {},
        pm_config=bj.get("pm_config") or None,
        recent_approved_run_ids=[str(r) for r in recent_run_ids],
    )


@router.get("/capabilities", response_model=list[AgentCapability], summary="Installed capabilities available for dispatch")
async def get_capabilities(
    brand_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    from plugin_loader import get_active_plugin_ids, get_plugin_for_module

    active_ids = await get_active_plugin_ids(db, brand_id)
    skills = sorted(
        [s for s in list_skill_manifests() if s.allowed_from_chat and s.module_id],
        key=lambda s: s.module_id,
    )
    result = []
    for s in skills:
        owner = get_plugin_for_module(s.module_id)
        if owner is not None and owner.manifest.plugin_id not in active_ids:
            continue
        result.append(AgentCapability(
            module_id=s.module_id,
            label=(s.name or s.module_id.rsplit(".", 1)[-1]).replace("_", " ").title(),
            description=(s.description or "").strip(),
            triggers=list(s.triggers)[:8],
        ))
    return result


@router.post("/execute", response_model=RunResponse, status_code=201, summary="Execute a capability directly", responses={404: {"description": "Module not found"}, 412: {"description": "Workspace not initialized"}})
async def agent_execute(
    body: AgentExecuteRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    if not get_module(body.module_id):
        raise HTTPException(status_code=404, detail=f"Module '{body.module_id}' not found")

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    brand_uuid: Optional[UUID] = body.brand_id
    if brand_uuid:
        brand_exists = (await db.execute(
            select(Brand.id).where(Brand.id == brand_uuid, Brand.workspace_id == ws.id)
        )).scalar_one_or_none()
        if not brand_exists:
            raise HTTPException(status_code=404, detail="Brand not found")

    return await _execute_module(
        db, ws, body.module_id, body.brief, get_settings(),
        brand_id=brand_uuid,
    )


@router.patch("/review/{run_id}", response_model=AgentReviewResponse, summary="Approve, reject, or flag a run", responses={404: {"description": "Run not found"}})
async def agent_review(
    run_id: UUID,
    body: AgentReviewRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    run_uuid = run_id

    run = (await db.execute(select(Run).where(Run.id == run_uuid))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    status_map = {"approve": "approved", "reject": "rejected", "flag": "flagged"}
    new_status = status_map[body.action]
    run.approval_status = new_status
    if body.reason:
        run.feedback = body.reason
    event_type = {
        "approved": "artifact_approved",
        "rejected": "artifact_dismissed",
        "flagged": "constraint_flag",
    }[new_status]
    await write_memory_event(
        db,
        workspace_id=run.workspace_id,
        brand_id=run.brand_id,
        event_type=event_type,
        topic_tags=[],
        summary=f"Agent review marked {run.module_id} as {new_status}",
        rationale=body.reason,
        source_ref=f"run:{run.id}",
        full_record={
            "run_id": str(run.id),
            "module_id": run.module_id,
            "approval_status": new_status,
            "agent_action": body.action,
            "reason": body.reason,
        },
    )
    await db.commit()

    if run.brand_id and new_status in ("approved", "rejected"):
        brand = (await db.execute(select(Brand).where(Brand.id == run.brand_id))).scalar_one_or_none()
        if brand:
            await _update_pm_task_status(run, new_status, brand, db, get_settings())

    return AgentReviewResponse(run_id=run_id, approval_status=new_status, reason=body.reason)
