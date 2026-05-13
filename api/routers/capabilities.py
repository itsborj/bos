from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from models.capability import Capability, ModelOption

router = APIRouter(tags=["capabilities"])


@router.get("/capabilities", summary="List capability profiles with model options")
async def list_capabilities(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    caps = (await db.execute(select(Capability).order_by(Capability.key))).scalars().all()

    result = []
    for cap in caps:
        opts = (
            await db.execute(
                select(ModelOption)
                .where(ModelOption.capability_id == cap.id)
                .order_by(ModelOption.quality_tier)
            )
        ).scalars().all()

        result.append({
            "key": cap.key,
            "modality": cap.modality,
            "budget_ceiling": cap.budget_ceiling,
            "latency_target_ms": cap.latency_target_ms,
            "model_options": [
                {
                    "provider": o.provider,
                    "model_id": o.model_id,
                    "quality_tier": o.quality_tier,
                    "input_cost_per_token": o.input_cost_per_token,
                    "output_cost_per_token": o.output_cost_per_token,
                    "latency_ms": o.latency_ms,
                    "supports_json": o.supports_json,
                    "status": o.status,
                }
                for o in opts
            ],
        })

    return {"capabilities": result}
