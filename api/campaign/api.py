from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from routers.workspace import get_singleton
from . import db as campaign_db

router = APIRouter(prefix="/campaigns", tags=["campaign"])


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    brand_id: UUID | None = None
    status: str = "active"
    objective_id: UUID | None = None
    audience: str | None = None
    message_angle: str | None = None
    campaign_json: dict[str, Any] | None = None


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    status: str | None = None
    objective_id: UUID | None = None
    audience: str | None = None
    message_angle: str | None = None
    campaign_json: dict[str, Any] | None = None
    confirm_status_change: bool | None = None


class CampaignRowWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID | None = None
    brand_id: UUID | None = None
    brand: str | None = None
    campaign_id: UUID | None = None
    campaign: str | None = None
    status: str | None = None
    objective_id: UUID | None = None
    business_objective: str | None = None
    success_metric: str | None = None
    target: str | None = None
    baseline: str | None = None
    current_value: str | None = None
    primary_kpi: str | None = None
    actual: str | None = None
    period_type: str | None = None
    time_period: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    distribution_channel: str | None = None
    channel_role: str | None = None
    market: str | None = None
    planned_activity: str | None = None
    actual_activity: str | None = None
    reach: int | None = None
    impressions: int | None = None
    engagement: int | None = None
    engagement_rate: float | None = None
    reach_metric: str | None = None
    engagement_metric: str | None = None
    action_metric: str | None = None
    efficiency_metric: str | None = None
    value_metric: str | None = None
    clicks: int | None = None
    leads: int | None = None
    calls: int | None = None
    qualified_calls: int | None = None
    conversions: int | None = None
    spend: Decimal | None = None
    budget: Decimal | None = None
    revenue: Decimal | None = None
    source_health: str = "reported"
    freshness: str | None = None
    verification_status: str = "producer_reported"
    objective_verdict: str | None = None
    confidence: str | None = None
    what_changed: str | None = None
    top_learning: str | None = None
    recommended_action: str | None = None
    note: str | None = None
    blocker: str | None = None
    decision_needed: str | None = None
    owner: str | None = None
    next_action: str | None = None
    due_date: datetime | None = None
    source_type: str | None = None
    source_ref: str | None = None
    producer: str | None = None
    evidence_refs: list[Any] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class CampaignRowEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_objective: str | None = None
    success_metric: str | None = None
    target: str | None = None
    baseline: str | None = None
    current_value: str | None = None
    primary_kpi: str | None = None
    actual: str | None = None
    period_type: str | None = None
    time_period: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    distribution_channel: str | None = None
    channel_role: str | None = None
    market: str | None = None
    planned_activity: str | None = None
    actual_activity: str | None = None
    reach: int | None = None
    impressions: int | None = None
    engagement: int | None = None
    engagement_rate: float | None = None
    reach_metric: str | None = None
    engagement_metric: str | None = None
    action_metric: str | None = None
    efficiency_metric: str | None = None
    value_metric: str | None = None
    clicks: int | None = None
    leads: int | None = None
    calls: int | None = None
    qualified_calls: int | None = None
    conversions: int | None = None
    spend: Decimal | None = None
    budget: Decimal | None = None
    revenue: Decimal | None = None
    source_health: str | None = None
    freshness: str | None = None
    verification_status: str | None = None
    objective_verdict: str | None = None
    confidence: str | None = None
    what_changed: str | None = None
    top_learning: str | None = None
    recommended_action: str | None = None
    note: str | None = None
    blocker: str | None = None
    decision_needed: str | None = None
    owner: str | None = None
    next_action: str | None = None
    due_date: datetime | None = None
    source_type: str | None = None
    source_ref: str | None = None
    producer: str | None = None
    evidence_refs: list[Any] | None = None
    raw_payload: dict[str, Any] | None = None
    superseded_at: datetime | None = None
    superseded_by_id: UUID | None = None


@router.get("")
async def list_campaigns(
    brand_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    return await campaign_db.list_campaigns(
        db, workspace_id=ws.id if ws else None, brand_id=brand_id
    )


@router.post("", status_code=201)
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    data = payload.model_dump()
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    data["workspace_id"] = ws.id
    row = await campaign_db.create_campaign_record(db, data)
    return campaign_db.campaign_out(row)


@router.get("/rows")
async def read_campaign_rows(
    brand_id: UUID | None = None,
    campaign_id: UUID | None = None,
    objective_id: UUID | None = None,
    distribution_channel: str | None = None,
    period_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    source_health: str | None = None,
    verification_status: str | None = None,
    objective_verdict: str | None = None,
    owner: str | None = None,
    include_superseded: bool = False,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    rows = await campaign_db.read_rows(
        db,
        workspace_id=ws.id if ws else None,
        brand_id=brand_id,
        campaign_id=campaign_id,
        objective_id=objective_id,
        distribution_channel=distribution_channel,
        period_type=period_type,
        start=start,
        end=end,
        source_health=source_health,
        verification_status=verification_status,
        objective_verdict=objective_verdict,
        owner=owner,
        include_superseded=include_superseded,
        limit=limit,
    )
    return {"rows": [campaign_db.row_dict(row) for row in rows]}


@router.post("/rows", status_code=201)
async def write_campaign_row(
    payload: CampaignRowWrite,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    data = payload.model_dump()
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    data["workspace_id"] = ws.id
    try:
        row = await campaign_db.write_row(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return campaign_db.row_dict(row)


@router.patch("/rows/{row_id}")
async def edit_campaign_row(
    row_id: UUID,
    payload: CampaignRowEdit,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    row = await campaign_db.edit_row(
        db,
        row_id,
        payload.model_dump(exclude_unset=True),
        workspace_id=ws.id if ws else None,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Campaign row not found")
    return campaign_db.row_dict(row)


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    rows = await campaign_db.rows_for_campaign(
        db, campaign_id, workspace_id=ws.id if ws else None, limit=1
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign_db.campaign_out(rows[0])


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    try:
        ws = await get_singleton(db)
        row = await campaign_db.update_campaign_record(
            db,
            campaign_id,
            payload.model_dump(exclude_unset=True),
            workspace_id=ws.id if ws else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign_db.campaign_out(row)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    deleted = await campaign_db.delete_campaign_record(
        db, campaign_id, workspace_id=ws.id if ws else None
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return None


@router.get("/{campaign_id}/sheet")
async def get_campaign_sheet(
    campaign_id: UUID,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    sheet = await campaign_db.campaign_sheet(
        db, campaign_id, workspace_id=ws.id if ws else None, limit=limit
    )
    if not sheet:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return sheet


@router.post("/{campaign_id}/rows", status_code=201)
async def append_campaign_row_for_campaign(
    campaign_id: UUID,
    payload: CampaignRowWrite,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    data = payload.model_dump()
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    data["workspace_id"] = ws.id
    try:
        row = await campaign_db.append_campaign_row(db, campaign_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return campaign_db.row_dict(row)
