import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.intent import IntentContract


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

