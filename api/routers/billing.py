import uuid as _uuid
from uuid import UUID

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db
from models.cmo_usage import CmoTokenUsage
from models.run import Run, RunAttempt, RunResult
from models.workspace import Brand
from routers.workspace import get_singleton
from schemas.billing import BillingRunItem, BillingSummary
from validation import NullableUUID

router = APIRouter(prefix="/billing", tags=["billing"])


async def _resolve_billing_brand(db: AsyncSession, workspace_id, brand_id: _uuid.UUID | None):
    if brand_id is None:
        return None
    brand = (await db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.workspace_id == workspace_id)
    )).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand_id


# ── GET /billing/summary ───────────────────────────────────────────────────────

@router.get("/summary", response_model=BillingSummary, summary="Aggregated cost and revenue summary", responses={404: {"description": "Brand not found"}})
async def billing_summary(
    brand_id: Annotated[NullableUUID, Query(description="Filter by brand UUID for per-client cost attribution")] = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return BillingSummary(
            total_runs=0, successful_runs=0,
            total_provider_cost=0.0, total_sell_price=0.0, total_tokens=0,
            platform_provider_cost=0.0, byok_provider_cost=0.0, oauth_provider_cost=0.0,
            external_provider_cost=0.0, platform_tokens=0, byok_tokens=0, oauth_tokens=0,
            gross_margin=0.0,
            missing_sell_price_runs=0, missing_sell_price_provider_cost=0.0,
        )

    target_brand_id = await _resolve_billing_brand(db, ws.id, brand_id)

    run_base = [Run.workspace_id == ws.id]
    if target_brand_id:
        run_base.append(Run.brand_id == target_brand_id)

    total_runs = (await db.execute(
        select(func.count()).select_from(Run).where(*run_base)
    )).scalar_one()

    successful_runs = (await db.execute(
        select(func.count()).select_from(Run).where(*run_base, Run.status == "success")
    )).scalar_one()

    attempt_agg = (await db.execute(
        select(
            func.coalesce(func.sum(RunAttempt.provider_cost), 0).label("total_cost"),
            func.coalesce(func.sum(func.coalesce(RunAttempt.tokens_input, 0) + func.coalesce(RunAttempt.tokens_output, 0)), 0).label("total_tokens"),
        ).join(Run, RunAttempt.run_id == Run.id).where(
            *run_base,
            RunAttempt.mode.in_(["platform", "byok", "oauth"]),
        )
    )).one()

    sell_agg = (await db.execute(
        select(func.coalesce(func.sum(RunResult.sell_price), 0)).join(
            Run, RunResult.run_id == Run.id
        ).where(*run_base)
    )).scalar_one()

    missing_sell_price = (await db.execute(
        select(
            func.count(func.distinct(Run.id)).label("run_count"),
            func.coalesce(func.sum(RunAttempt.provider_cost), 0).label("provider_cost"),
        )
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunAttempt, RunAttempt.run_id == Run.id, isouter=True)
        .where(
            *run_base,
            Run.status == "success",
            RunAttempt.mode == "platform",
            RunAttempt.provider_cost.is_not(None),
            RunAttempt.provider_cost > 0,
            RunResult.sell_price.is_(None),
        )
    )).one()
    estimated_missing_sell_price = float(missing_sell_price.provider_cost or 0) * get_settings().markup_multiplier

    chat_filter = [CmoTokenUsage.workspace_id == ws.id]
    if target_brand_id:
        chat_filter.append(CmoTokenUsage.brand_id == target_brand_id)

    chat_agg = (await db.execute(
        select(
            func.coalesce(func.sum(CmoTokenUsage.provider_cost), 0).label("total_cost"),
            func.coalesce(func.sum(CmoTokenUsage.tokens_input + CmoTokenUsage.tokens_output), 0).label("total_tokens"),
        ).where(*chat_filter)
    )).one()

    async def _attempt_mode_agg(mode: str):
        return (await db.execute(
            select(
                func.coalesce(func.sum(RunAttempt.provider_cost), 0).label("total_cost"),
                func.coalesce(func.sum(func.coalesce(RunAttempt.tokens_input, 0) + func.coalesce(RunAttempt.tokens_output, 0)), 0).label("total_tokens"),
            ).join(Run, RunAttempt.run_id == Run.id).where(*run_base, RunAttempt.mode == mode)
        )).one()

    async def _chat_mode_agg(mode: str):
        return (await db.execute(
            select(
                func.coalesce(func.sum(CmoTokenUsage.provider_cost), 0).label("total_cost"),
                func.coalesce(func.sum(CmoTokenUsage.tokens_input + CmoTokenUsage.tokens_output), 0).label("total_tokens"),
            ).where(*chat_filter, CmoTokenUsage.mode == mode)
        )).one()

    mode_totals: dict[str, dict[str, float | int]] = {}
    for mode in ("platform", "byok", "oauth"):
        run_mode = await _attempt_mode_agg(mode)
        chat_mode = await _chat_mode_agg(mode)
        mode_totals[mode] = {
            "cost": round(float(run_mode.total_cost) + float(chat_mode.total_cost), 6),
            "tokens": int(run_mode.total_tokens) + int(chat_mode.total_tokens),
        }

    total_provider_cost = round(float(attempt_agg.total_cost) + float(chat_agg.total_cost), 6)
    total_sell_price = round(float(sell_agg) + estimated_missing_sell_price, 6)
    platform_provider_cost = float(mode_totals["platform"]["cost"])
    byok_provider_cost = float(mode_totals["byok"]["cost"])
    oauth_provider_cost = float(mode_totals["oauth"]["cost"])

    return BillingSummary(
        total_runs=total_runs,
        successful_runs=successful_runs,
        total_provider_cost=total_provider_cost,
        total_sell_price=total_sell_price,
        total_tokens=int(attempt_agg.total_tokens) + int(chat_agg.total_tokens),
        platform_provider_cost=platform_provider_cost,
        byok_provider_cost=byok_provider_cost,
        oauth_provider_cost=oauth_provider_cost,
        external_provider_cost=round(byok_provider_cost + oauth_provider_cost, 6),
        platform_tokens=int(mode_totals["platform"]["tokens"]),
        byok_tokens=int(mode_totals["byok"]["tokens"]),
        oauth_tokens=int(mode_totals["oauth"]["tokens"]),
        gross_margin=round(total_sell_price - platform_provider_cost, 6),
        missing_sell_price_runs=int(missing_sell_price.run_count or 0),
        missing_sell_price_provider_cost=round(float(missing_sell_price.provider_cost or 0), 6),
    )


# ── GET /billing/runs/{run_id} ─────────────────────────────────────────────────

@router.get("/runs/{run_id}", response_model=BillingRunItem, summary="Per-run billing breakdown", responses={404: {"description": "Run not found"}})
async def billing_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' not found", "details": None}},
        )

    attempt = (await db.execute(
        select(RunAttempt).where(RunAttempt.run_id == run.id).limit(1)
    )).scalar_one_or_none()

    result = (await db.execute(
        select(RunResult).where(RunResult.run_id == run.id)
    )).scalar_one_or_none()

    if not attempt:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "ATTEMPT_NOT_FOUND", "message": "No attempt record for this run", "details": None}},
        )

    return BillingRunItem(
        run_id=str(run.id),
        module_id=run.module_id,
        created_at=run.created_at,
        provider=attempt.provider,
        model_id=attempt.model_id,
        mode=attempt.mode,
        tokens_input=attempt.tokens_input or 0,
        tokens_output=attempt.tokens_output or 0,
        provider_cost=attempt.provider_cost or 0.0,
        sell_price=result.sell_price if result else None,
    )
