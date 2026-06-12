import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from intent.contracts import (
    create_contract,
    get_campaign_intent,
    get_contract,
    list_contracts,
    set_campaign_intent,
)
from intent.evaluator import evaluate
from models.workspace import Campaign
from schemas.intent import (
    CampaignIntentIn,
    CampaignIntentOut,
    EvaluateIn,
    EvaluateOut,
    IntentContractIn,
    IntentContractOut,
)

router = APIRouter(tags=["intents"])


@router.get("/intents", response_model=list[IntentContractOut], summary="List intent contract templates")
async def list_intent_contracts(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    return await list_contracts(db)


@router.post("/intents", response_model=IntentContractOut, status_code=201, summary="Create intent contract")
async def create_intent_contract(
    body: IntentContractIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    data = {
        "contract_type": body.contract_type,
        "version": body.version,
        "description": body.description,
        "evaluator": body.evaluator,
        "criteria_json": [c.model_dump() for c in body.criteria],
        "scoring_json": body.scoring.model_dump(),
        "on_pass": body.on_pass,
        "on_fail": body.on_fail,
        "on_escalate": body.on_escalate,
        "max_attempts": body.max_attempts,
    }
    return await create_contract(db, data)


@router.get("/intents/{intent_id}", response_model=IntentContractOut, summary="Get intent contract detail", responses={404: {"description": "Intent not found"}})
async def get_intent_contract(
    intent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    contract = await get_contract(db, intent_id)
    if not contract:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "INTENT_NOT_FOUND", "message": f"Intent '{intent_id}' not found", "details": None}},
        )
    return contract


@router.post(
    "/intents/{intent_id}/evaluate",
    response_model=EvaluateOut,
    summary="Evaluate output against an intent contract",
)
async def evaluate_against_contract(
    intent_id: uuid.UUID,
    body: EvaluateIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    contract = await get_contract(db, intent_id)
    if not contract:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "INTENT_NOT_FOUND", "message": f"Intent '{intent_id}' not found", "details": None}},
        )
    result = evaluate(
        {"criteria_json": contract.criteria_json, "scoring_json": contract.scoring_json},
        body.payload,
        body.overrides,
    )
    return EvaluateOut(**result)


@router.put(
    "/campaigns/{campaign_id}/intent",
    response_model=CampaignIntentOut,
    summary="Assign or override campaign intent",
)
async def set_intent_for_campaign(
    campaign_id: uuid.UUID,
    body: CampaignIntentIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    campaign_row = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    if not campaign_row.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "CAMPAIGN_NOT_FOUND", "message": f"Campaign '{campaign_id}' not found", "details": None}},
        )
    contract = await get_contract(db, body.intent_contract_id)
    if not contract:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "INTENT_NOT_FOUND", "message": f"Intent '{body.intent_contract_id}' not found", "details": None}},
        )
    return await set_campaign_intent(db, campaign_id, body.intent_contract_id, body.overrides)


@router.get(
    "/campaigns/{campaign_id}/intent",
    response_model=CampaignIntentOut,
    summary="Get active campaign intent",
    responses={404: {"description": "Campaign or intent not found"}},
)
async def get_intent_for_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    campaign_row = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    if not campaign_row.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "CAMPAIGN_NOT_FOUND", "message": f"Campaign '{campaign_id}' not found", "details": None}},
        )
    ci = await get_campaign_intent(db, campaign_id)
    if not ci:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NO_ACTIVE_INTENT", "message": f"No active intent for campaign '{campaign_id}'", "details": None}},
        )
    return ci
