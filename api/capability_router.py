from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.capability import Capability, ModelOption

QUALITY_SCORES: dict[str, float] = {"high": 1.0, "medium": 0.6, "low": 0.3}

POLICY_WEIGHTS: dict[str, dict[str, float]] = {
    "cheap":    {"cost": 0.70, "quality": 0.10, "latency": 0.20},
    "balanced": {"cost": 0.35, "quality": 0.35, "latency": 0.30},
    "premium":  {"cost": 0.10, "quality": 0.70, "latency": 0.20},
}


async def route(
    db: AsyncSession,
    capability_key: str,
    policy: str,
) -> tuple[list[dict], dict]:
    """
    Returns (ranked_candidates, routing_metadata).
    Candidates are sorted best-first. routing_metadata is stored in RunTrace.
    """
    cap_row = await db.execute(select(Capability).where(Capability.key == capability_key))
    capability = cap_row.scalar_one_or_none()
    if not capability:
        return [], {"error": f"capability '{capability_key}' not found in database"}

    opts_rows = await db.execute(
        select(ModelOption)
        .where(ModelOption.capability_id == capability.id)
        .where(ModelOption.status == "healthy")
    )
    options = opts_rows.scalars().all()

    if not options:
        return [], {"error": "no healthy model options for capability"}

    weights = POLICY_WEIGHTS.get(policy, POLICY_WEIGHTS["balanced"])
    candidates: list[dict] = []
    filtered = 0

    for opt in options:
        total_cost = opt.input_cost_per_token + opt.output_cost_per_token
        if total_cost > capability.budget_ceiling:
            filtered += 1
            continue

        cost_score = max(0.0, 1.0 - total_cost / max(capability.budget_ceiling, 1e-9))
        quality_score = QUALITY_SCORES.get(opt.quality_tier, 0.5)
        latency_score = max(0.0, 1.0 - opt.latency_ms / max(capability.latency_target_ms, 1))

        score = (
            weights["cost"] * cost_score
            + weights["quality"] * quality_score
            + weights["latency"] * latency_score
        )

        candidates.append({
            "model_id": opt.model_id,
            "provider": opt.provider,
            "quality_tier": opt.quality_tier,
            "input_cost_per_token": opt.input_cost_per_token,
            "output_cost_per_token": opt.output_cost_per_token,
            "latency_ms": opt.latency_ms,
            "supports_json": opt.supports_json,
            "score": round(score, 4),
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    winner = candidates[0] if candidates else None
    routing_meta = {
        "capability": capability_key,
        "policy": policy,
        "candidates_considered": len(candidates) + filtered,
        "candidates_filtered": filtered,
        "winner": f"{winner['provider']}/{winner['model_id']}" if winner else None,
        "routing_reason": (
            "weighted score: cost {:.0f}% + quality {:.0f}% + latency {:.0f}%".format(
                weights["cost"] * 100,
                weights["quality"] * 100,
                weights["latency"] * 100,
            )
        ) if winner else "no eligible candidates",
    }

    return candidates, routing_meta
