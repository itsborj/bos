from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from models.run import Run, RunAttempt, RunResult
from routers.workspace import get_singleton
from schemas.billing import BillingRunItem, BillingSummary

router = APIRouter(prefix="/billing", tags=["billing"])


# ── GET /billing/summary ───────────────────────────────────────────────────────

@router.get("/summary", response_model=BillingSummary, summary="Aggregated cost and revenue summary")
async def billing_summary(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    ws = await get_singleton(db)
    if not ws:
        return BillingSummary(
            total_runs=0, successful_runs=0,
            total_provider_cost=0.0, total_sell_price=0.0, total_tokens=0,
        )

    total_runs = (await db.execute(
        select(func.count()).select_from(Run).where(Run.workspace_id == ws.id)
    )).scalar_one()

    successful_runs = (await db.execute(
        select(func.count()).select_from(Run).where(
            Run.workspace_id == ws.id, Run.status == "success"
        )
    )).scalar_one()

    attempt_agg = (await db.execute(
        select(
            func.coalesce(func.sum(RunAttempt.provider_cost), 0).label("total_cost"),
            func.coalesce(func.sum(RunAttempt.tokens_input + RunAttempt.tokens_output), 0).label("total_tokens"),
        ).join(Run, RunAttempt.run_id == Run.id).where(Run.workspace_id == ws.id)
    )).one()

    sell_agg = (await db.execute(
        select(func.coalesce(func.sum(RunResult.sell_price), 0)).join(
            Run, RunResult.run_id == Run.id
        ).where(Run.workspace_id == ws.id)
    )).scalar_one()

    return BillingSummary(
        total_runs=total_runs,
        successful_runs=successful_runs,
        total_provider_cost=round(float(attempt_agg.total_cost), 6),
        total_sell_price=round(float(sell_agg), 6),
        total_tokens=int(attempt_agg.total_tokens),
    )


# ── GET /billing/runs/{run_id} ─────────────────────────────────────────────────

@router.get("/runs/{run_id}", response_model=BillingRunItem, summary="Per-run billing breakdown")
async def billing_run(
    run_id: str,
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
