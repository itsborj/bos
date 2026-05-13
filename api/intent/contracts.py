import uuid
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.intent import CampaignIntent, IntentContract


async def create_contract(db: AsyncSession, data: dict) -> IntentContract:
    contract = IntentContract(**data)
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    return contract


async def get_contract(db: AsyncSession, contract_id: uuid.UUID) -> Optional[IntentContract]:
    row = await db.execute(select(IntentContract).where(IntentContract.id == contract_id))
    return row.scalar_one_or_none()


async def list_contracts(db: AsyncSession) -> list[IntentContract]:
    rows = await db.execute(select(IntentContract).order_by(IntentContract.created_at.desc()))
    return list(rows.scalars().all())


async def set_campaign_intent(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    contract_id: uuid.UUID,
    overrides: Optional[dict] = None,
) -> CampaignIntent:
    # Deactivate any existing active intent for this campaign
    await db.execute(
        update(CampaignIntent)
        .where(CampaignIntent.campaign_id == campaign_id, CampaignIntent.active.is_(True))
        .values(active=False)
    )
    ci = CampaignIntent(
        campaign_id=campaign_id,
        intent_contract_id=contract_id,
        overrides_json=overrides,
        active=True,
    )
    db.add(ci)
    await db.commit()
    await db.refresh(ci)
    return ci


async def get_campaign_intent(
    db: AsyncSession, campaign_id: uuid.UUID
) -> Optional[CampaignIntent]:
    row = await db.execute(
        select(CampaignIntent)
        .where(CampaignIntent.campaign_id == campaign_id, CampaignIntent.active.is_(True))
        .limit(1)
    )
    return row.scalar_one_or_none()
