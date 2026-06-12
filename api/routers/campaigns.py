from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from data_hygiene import contains_fuzzer_garbage, reject_fuzzer_garbage
from db import get_db
from models.run import Run, RunAttempt, RunResult
from models.workspace import Campaign, Workspace
from registry import list_by_vertical
from routers.runs import _execute_module, _resolve_brief
from schemas.campaigns import CampaignCreate, CampaignDetail, CampaignOut, CampaignRunPayload, CampaignUpdate

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ── Helpers ────────────────────────────────────────────────────────────────────

async def get_workspace(db: AsyncSession) -> Workspace:
    """Get the singleton workspace."""
    result = await db.execute(select(Workspace).limit(1))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(
            status_code=412,
            detail={
                "error": {
                    "code": "WORKSPACE_NOT_INITIALIZED",
                    "message": "No workspace configured.",
                    "details": None,
                }
            },
        )
    return ws


async def get_campaign_or_404(campaign_id: UUID, db: AsyncSession) -> Campaign:
    """Get a campaign by ID or raise 404."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=CampaignOut, status_code=201, summary="Create a new campaign")
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_workspace(db)
    reject_fuzzer_garbage(payload.name, ["body", "name"])
    
    campaign = Campaign(
        workspace_id=ws.id,
        name=payload.name,
        status=payload.status or "draft",
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    
    return CampaignOut(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.get("", response_model=list[CampaignOut], summary="List all campaigns")
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_workspace(db)
    
    result = await db.execute(
        select(Campaign).where(Campaign.workspace_id == ws.id).order_by(Campaign.created_at.desc())
    )
    campaigns = [c for c in result.scalars().all() if not contains_fuzzer_garbage(c.name)]
    
    return [
        CampaignOut(
            id=c.id,
            name=c.name,
            status=c.status,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in campaigns
    ]


@router.get("/{campaign_id}", response_model=CampaignDetail, summary="Get campaign details", responses={404: {"description": "Campaign not found"}})
async def get_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    campaign = await get_campaign_or_404(campaign_id, db)
    
    return CampaignDetail(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.patch("/{campaign_id}", response_model=CampaignOut, summary="Update a campaign", responses={404: {"description": "Campaign not found"}})
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    campaign = await get_campaign_or_404(campaign_id, db)
    
    if payload.name is not None:
        reject_fuzzer_garbage(payload.name, ["body", "name"])
        campaign.name = payload.name
    if payload.status is not None:
        campaign.status = payload.status
    
    await db.commit()
    await db.refresh(campaign)
    
    return CampaignOut(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.post("/{campaign_id}/run", status_code=202, summary="Run all modules for a campaign", responses={404: {"description": "Campaign not found"}})
async def run_campaign(
    campaign_id: UUID,
    payload: CampaignRunPayload | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Trigger module runs for a campaign.
    
    If module_ids is provided, only run those modules.
    Otherwise, run all eligible marketing modules.
    """
    campaign = await get_campaign_or_404(campaign_id, db)
    ws = await get_workspace(db)
    
    # Determine which modules to run
    if payload and payload.module_ids:
        module_ids = payload.module_ids
    else:
        # Get all marketing modules
        marketing_modules = list_by_vertical("marketing")
        module_ids = [m["id"] for m in marketing_modules]
    
    if not module_ids:
        raise HTTPException(status_code=400, detail="No modules to run")
    
    # Build brief from workspace (with optional override)
    brief_override = payload.brief if payload and payload.brief else {}
    brief = await _resolve_brief(db, ws, brief_override)
    
    # Import settings here to avoid circular import
    from config import get_settings
    settings = get_settings()
    
    # Dispatch all modules
    run_results = []
    for module_id in module_ids:
        try:
            result = await _execute_module(db, ws, module_id, brief, settings)
            run_results.append(result)
        except Exception as exc:
            from fastapi import status
            from logging import getLogger
            getLogger("bos.campaigns").error("Module %s failed: %s", module_id, exc)
    
    return {
        "message": f"Campaign run triggered: {len(run_results)} module(s) executed",
        "campaign_id": str(campaign.id),
        "status": "completed",
        "run_ids": [str(r.run_id) for r in run_results],
    }

# ── Campaign Summary Endpoint ─────────────────────────────────────────

class CampaignSummaryResponse(BaseModel):
    campaign_id: str
    campaign_name: str
    total_runs: int
    passed_runs: int
    failed_runs: int
    total_cost: float
    total_sell_price: Optional[float]
    modules: list[dict]


@router.get("/{campaign_id}/summary", response_model=CampaignSummaryResponse, summary="Get campaign summary with module results and costs", responses={404: {"description": "Campaign not found"}})
async def get_campaign_summary(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    campaign = await get_campaign_or_404(campaign_id, db)
    
    # Get all runs for this campaign (stored in trace lineage_json)
    # For now, get all runs from the workspace
    result = await db.execute(
        select(Run, RunResult, RunAttempt)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunAttempt, RunAttempt.run_id == Run.id, isouter=True)
        .where(Run.workspace_id == campaign.workspace_id)
        .order_by(Run.created_at.desc())
    )
    rows = result.all()
    
    total_runs = len(rows)
    passed_runs = sum(1 for r in rows if r.RunResult and r.RunResult.self_check_verdict == "pass")
    failed_runs = total_runs - passed_runs
    
    total_cost = sum(r.RunAttempt.provider_cost or 0 for r in rows if r.RunAttempt)
    total_sell_price = sum(r.RunResult.sell_price or 0 for r in rows if r.RunResult and r.RunResult.sell_price)
    
    # Group by module
    module_stats = {}
    for r in rows:
        module_id = r.Run.module_id
        if module_id not in module_stats:
            module_stats[module_id] = {
                "module_id": module_id,
                "runs": 0,
                "passed": 0,
                "cost": 0.0,
                "sell_price": 0.0,
            }
        module_stats[module_id]["runs"] += 1
        if r.RunResult and r.RunResult.self_check_verdict == "pass":
            module_stats[module_id]["passed"] += 1
        if r.RunAttempt:
            module_stats[module_id]["cost"] += r.RunAttempt.provider_cost or 0
        if r.RunResult and r.RunResult.sell_price:
            module_stats[module_id]["sell_price"] += r.RunResult.sell_price
    
    return CampaignSummaryResponse(
        campaign_id=str(campaign.id),
        campaign_name=campaign.name,
        total_runs=total_runs,
        passed_runs=passed_runs,
        failed_runs=failed_runs,
        total_cost=total_cost,
        total_sell_price=total_sell_price if total_sell_price else None,
        modules=list(module_stats.values()),
    )
