from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .table import Campaign, CampaignRow

ROW_FIELDS = [c.name for c in CampaignRow.__table__.columns]
WRITABLE_FIELDS = {
    f for f in ROW_FIELDS
    if f not in {"id", "created_at", "updated_at", "superseded_at", "superseded_by_id"}
}
EDITABLE_FIELDS = WRITABLE_FIELDS - {
    "workspace_id", "brand_id", "brand", "campaign_id", "campaign",
    "status", "objective_id",
}
METRIC_FIELDS = {
    "reach", "impressions", "engagement", "clicks", "leads", "calls",
    "qualified_calls", "conversions", "engagement_rate", "spend", "budget", "revenue",
}
SOURCE_HEALTH = {"reported", "fresh", "stale", "blocked", "not_connected", "connected_no_data", "unknown"}
VERIFICATION = {"producer_reported", "producer_verified", "unverified", "verified", "rejected", "needs_review"}
VERDICTS = {"true", "false", "inconclusive", "needs_data"}
CAMPAIGN_STATUSES = {"draft", "active", "complete", "archived"}
GUARDED_STATUS_TRANSITIONS = {("active", "complete"), ("complete", "archived")}


def clean_enum(value: str | None, allowed: set[str], default: str) -> str:
    val = str(value or "").strip().lower()
    return val if val in allowed else default


def row_dict(row: CampaignRow) -> dict[str, Any]:
    return {field: getattr(row, field) for field in ROW_FIELDS}


def supporting_campaign_json(raw: dict[str, Any]) -> dict[str, Any] | None:
    value = raw.get("campaign_json") if isinstance(raw, dict) else None
    if not isinstance(value, dict):
        return None
    legacy_truth_keys = {
        "memory_snapshot", "daily_brief", "daily_brief_payload",
        "campaign_overview", "campaign_alignment", "activation", "snapshot",
    }
    clean = {key: item for key, item in value.items() if key not in legacy_truth_keys}
    return clean or None


def campaign_key(row: CampaignRow | Campaign) -> UUID:
    if isinstance(row, Campaign):
        return row.id
    return row.campaign_id or row.id


def campaign_out(campaign: Campaign | CampaignRow, row: CampaignRow | None = None) -> dict[str, Any]:
    if isinstance(campaign, CampaignRow):
        row = campaign
        raw = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        return {
            "id": campaign_key(row),
            "name": row.campaign or "Untitled Campaign",
            "status": row.status or "active",
            "brand_id": row.brand_id,
            "objective_id": row.objective_id,
            "audience": raw.get("audience"),
            "message_angle": raw.get("message_angle"),
            "campaign_json": supporting_campaign_json(raw),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "signal": None,
        }

    raw = row.raw_payload if row and isinstance(row.raw_payload, dict) else {}
    return {
        "id": campaign.id,
        "name": campaign.name,
        "status": campaign.status,
        "brand_id": campaign.brand_id,
        "objective_id": campaign.objective_id,
        "audience": raw.get("audience"),
        "message_angle": raw.get("message_angle"),
        "campaign_json": supporting_campaign_json(raw),
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
        "signal": None,
    }


def normalize_row_data(data: dict[str, Any]) -> dict[str, Any]:
    clean = {key: value for key, value in (data or {}).items() if key in WRITABLE_FIELDS}
    present_metrics = [key for key in METRIC_FIELDS if clean.get(key) is not None]
    clean["source_health"] = clean_enum(clean.get("source_health"), SOURCE_HEALTH, "reported")
    clean["verification_status"] = clean_enum(clean.get("verification_status"), VERIFICATION, "producer_reported")
    clean["objective_verdict"] = clean_enum(
        clean.get("objective_verdict"),
        VERDICTS,
        "needs_data" if not present_metrics else "inconclusive",
    )
    clean["status"] = clean_enum(clean.get("status"), CAMPAIGN_STATUSES, "active")
    if clean.get("evidence_refs") is None:
        clean["evidence_refs"] = []
    if clean.get("raw_payload") is None:
        clean["raw_payload"] = {}
    return clean


async def get_campaign_record(
    db: AsyncSession,
    campaign_id: UUID,
    *,
    workspace_id: UUID | None = None,
    brand_id: UUID | None = None,
) -> Campaign | None:
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    if workspace_id:
        stmt = stmt.where(Campaign.workspace_id == workspace_id)
    if brand_id:
        stmt = stmt.where(Campaign.brand_id == brand_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def active_campaigns(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    brand_id: UUID,
    limit: int = 12,
) -> list[Campaign]:
    stmt = (
        select(Campaign)
        .where(
            Campaign.workspace_id == workspace_id,
            Campaign.brand_id == brand_id,
            Campaign.status == "active",
        )
        .order_by(Campaign.updated_at.desc())
        .limit(min(max(limit, 1), 100))
    )
    return list((await db.execute(stmt)).scalars().all())


async def campaign_names(db: AsyncSession, campaign_ids: list[UUID]) -> dict[UUID, str]:
    if not campaign_ids:
        return {}
    rows = (await db.execute(select(Campaign).where(Campaign.id.in_(campaign_ids)))).scalars().all()
    return {row.id: row.name for row in rows}


async def campaign_index(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    brand_id: UUID,
    limit: int = 12,
) -> list[dict[str, Any]]:
    campaigns = await active_campaigns(
        db, workspace_id=workspace_id, brand_id=brand_id, limit=limit
    )
    out: list[dict[str, Any]] = []
    for campaign in campaigns:
        rows = await rows_for_campaign(db, campaign.id, limit=100)
        row = next(
            (
                item for item in rows
                if item.distribution_channel == "campaign"
                or item.channel_role == "operating_record"
            ),
            rows[0] if rows else None,
        )
        raw = row.raw_payload if row and isinstance(row.raw_payload, dict) else {}
        campaign_json = raw.get("campaign_json") if isinstance(raw.get("campaign_json"), dict) else raw
        out.append({
            "campaign_id": str(campaign.id),
            "name": campaign.name,
            "audience": raw.get("audience") or campaign_json.get("audience"),
            "message_focus": raw.get("message_angle") or campaign_json.get("message_focus") or campaign_json.get("goal"),
            "activations": [],
        })
    return out


async def get_row(
    db: AsyncSession,
    row_id: UUID,
    *,
    workspace_id: UUID | None = None,
    brand_id: UUID | None = None,
    for_update: bool = False,
) -> CampaignRow | None:
    stmt = select(CampaignRow).where(CampaignRow.id == row_id)
    if workspace_id:
        stmt = stmt.where(CampaignRow.workspace_id == workspace_id)
    if brand_id:
        stmt = stmt.where(CampaignRow.brand_id == brand_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def read_rows(
    db: AsyncSession,
    *,
    workspace_id: UUID | None = None,
    brand_id: UUID | None = None,
    campaign_id: UUID | None = None,
    objective_id: UUID | None = None,
    distribution_channel: str | None = None,
    period_type: str | None = None,
    start: Any = None,
    end: Any = None,
    source_health: str | None = None,
    verification_status: str | None = None,
    objective_verdict: str | None = None,
    owner: str | None = None,
    status: str | None = None,
    include_superseded: bool = False,
    limit: int = 100,
) -> list[CampaignRow]:
    stmt = select(CampaignRow)
    if workspace_id:
        stmt = stmt.where(CampaignRow.workspace_id == workspace_id)
    if brand_id:
        stmt = stmt.where(CampaignRow.brand_id == brand_id)
    if campaign_id:
        stmt = stmt.where(CampaignRow.campaign_id == campaign_id)
    if objective_id:
        stmt = stmt.where(CampaignRow.objective_id == objective_id)
    if distribution_channel:
        stmt = stmt.where(CampaignRow.distribution_channel == distribution_channel)
    if period_type:
        stmt = stmt.where(CampaignRow.period_type == period_type)
    if start:
        stmt = stmt.where(CampaignRow.period_start >= start)
    if end:
        stmt = stmt.where(CampaignRow.period_end <= end)
    if source_health:
        stmt = stmt.where(CampaignRow.source_health == source_health)
    if verification_status:
        stmt = stmt.where(CampaignRow.verification_status == verification_status)
    if objective_verdict:
        stmt = stmt.where(CampaignRow.objective_verdict == objective_verdict)
    if owner:
        stmt = stmt.where(CampaignRow.owner == owner)
    if status:
        stmt = stmt.where(CampaignRow.status == status)
    if not include_superseded:
        stmt = stmt.where(CampaignRow.superseded_at.is_(None))
    stmt = stmt.order_by(
        CampaignRow.period_start.desc().nullslast(), CampaignRow.created_at.desc()
    ).limit(min(max(limit, 1), 500))
    return list((await db.execute(stmt)).scalars().all())


async def write_row(db: AsyncSession, data: dict[str, Any]) -> CampaignRow:
    clean = normalize_row_data(data)
    campaign_id = clean.get("campaign_id")
    if not campaign_id:
        raise ValueError("campaign_id is required for Campaign truth rows")
    if campaign_id:
        campaign = await get_campaign_record(
            db,
            campaign_id,
            workspace_id=clean.get("workspace_id"),
            brand_id=clean.get("brand_id"),
        )
        if not campaign:
            raise ValueError("Campaign does not exist in the requested workspace/brand")
        # Campaign identity/lifecycle is server-owned; callers cannot attach a
        # row to one Campaign while supplying another brand, name, or status.
        clean["workspace_id"] = campaign.workspace_id
        clean["brand_id"] = campaign.brand_id
        clean["campaign"] = campaign.name
        clean["status"] = campaign.status
        clean["objective_id"] = campaign.objective_id
    row = CampaignRow(**clean)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def edit_row(
    db: AsyncSession,
    row_id: UUID,
    updates: dict[str, Any],
    *,
    workspace_id: UUID | None = None,
    brand_id: UUID | None = None,
) -> CampaignRow | None:
    row = await get_row(
        db,
        row_id,
        workspace_id=workspace_id,
        brand_id=brand_id,
        for_update=True,
    )
    if not row or row.superseded_at is not None:
        return None

    replacement_data = {
        key: value
        for key, value in row_dict(row).items()
        if key in WRITABLE_FIELDS
    }
    replacement_data.update({
        key: value for key, value in (updates or {}).items() if key in EDITABLE_FIELDS
    })
    replacement = CampaignRow(**normalize_row_data(replacement_data))
    db.add(replacement)
    await db.flush()
    row.superseded_at = datetime.now(timezone.utc)
    row.superseded_by_id = replacement.id
    await db.commit()
    await db.refresh(replacement)
    return replacement


async def rows_for_campaign(
    db: AsyncSession,
    campaign_id: UUID,
    *,
    workspace_id: UUID | None = None,
    brand_id: UUID | None = None,
    include_superseded: bool = False,
    limit: int = 100,
) -> list[CampaignRow]:
    return await read_rows(
        db,
        workspace_id=workspace_id,
        brand_id=brand_id,
        campaign_id=campaign_id,
        include_superseded=include_superseded,
        limit=limit,
    )


async def list_campaigns(
    db: AsyncSession,
    *,
    workspace_id: UUID | None = None,
    brand_id: UUID | None = None,
) -> list[dict[str, Any]]:
    stmt = select(Campaign)
    if workspace_id:
        stmt = stmt.where(Campaign.workspace_id == workspace_id)
    if brand_id:
        stmt = stmt.where(Campaign.brand_id == brand_id)
    stmt = stmt.order_by(Campaign.updated_at.desc())
    campaigns = list((await db.execute(stmt)).scalars().all())
    out: list[dict[str, Any]] = []
    for campaign in campaigns:
        rows = await rows_for_campaign(db, campaign.id, limit=100)
        context_row = next(
            (
                row for row in rows
                if row.distribution_channel == "campaign"
                or row.channel_role == "operating_record"
            ),
            rows[0] if rows else None,
        )
        out.append(campaign_out(campaign, context_row))
    return out


async def create_campaign_record(db: AsyncSession, data: dict[str, Any]) -> CampaignRow:
    campaign_id = data.get("campaign_id") or uuid.uuid4()
    status = clean_enum(data.get("status"), CAMPAIGN_STATUSES, "active")
    campaign = Campaign(
        id=campaign_id,
        workspace_id=data.get("workspace_id"),
        brand_id=data.get("brand_id"),
        name=data.get("name") or data.get("campaign") or "Untitled Campaign",
        status=status,
        objective_id=data.get("objective_id"),
    )
    db.add(campaign)
    await db.flush()

    raw_payload = dict(data.get("campaign_json") or {}) if isinstance(data.get("campaign_json"), dict) else {}
    if data.get("audience") is not None:
        raw_payload["audience"] = data.get("audience")
    if data.get("message_angle") is not None:
        raw_payload["message_angle"] = data.get("message_angle")
    if data.get("campaign_json") is not None:
        raw_payload["campaign_json"] = data.get("campaign_json") or {}

    row = CampaignRow(**normalize_row_data({
        "workspace_id": campaign.workspace_id,
        "brand_id": campaign.brand_id,
        "campaign_id": campaign.id,
        "campaign": campaign.name,
        "status": campaign.status,
        "objective_id": campaign.objective_id,
        "business_objective": raw_payload.get("business_objective") or raw_payload.get("objective"),
        "success_metric": raw_payload.get("success_metric"),
        "target": raw_payload.get("target"),
        "period_type": "current",
        "time_period": "current",
        "distribution_channel": "campaign",
        "channel_role": "operating_record",
        "primary_kpi": data.get("primary_kpi") or raw_payload.get("primary_kpi"),
        "actual": data.get("actual") or raw_payload.get("actual"),
        "market": data.get("market") or raw_payload.get("market"),
        "planned_activity": raw_payload.get("initial_intent") or campaign.name,
        "source_health": "reported",
        "verification_status": "producer_reported",
        "objective_verdict": "needs_data",
        "raw_payload": raw_payload,
    }))
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_campaign_record(
    db: AsyncSession,
    campaign_id: UUID,
    data: dict[str, Any],
    *,
    workspace_id: UUID | None = None,
    brand_id: UUID | None = None,
) -> CampaignRow | None:
    campaign = await get_campaign_record(
        db, campaign_id, workspace_id=workspace_id, brand_id=brand_id
    )
    if not campaign:
        return None

    next_status = clean_enum(data.get("status"), CAMPAIGN_STATUSES, campaign.status)
    if (
        next_status != campaign.status
        and (campaign.status, next_status) in GUARDED_STATUS_TRANSITIONS
        and data.get("confirm_status_change") is not True
    ):
        raise ValueError(f"Campaign status transition {campaign.status} -> {next_status} requires confirmation")

    if data.get("name") is not None:
        campaign.name = str(data.get("name"))
    if data.get("status") is not None:
        campaign.status = next_status
    if data.get("objective_id") is not None:
        campaign.objective_id = data.get("objective_id")

    rows = await rows_for_campaign(db, campaign_id, limit=1)
    if not rows:
        return None
    row = rows[0]
    raw = dict(row.raw_payload or {}) if isinstance(row.raw_payload, dict) else {}
    if data.get("audience") is not None:
        raw["audience"] = data.get("audience")
    if data.get("message_angle") is not None:
        raw["message_angle"] = data.get("message_angle")
    if data.get("campaign_json") is not None:
        raw["campaign_json"] = data.get("campaign_json") or {}

    updates: dict[str, Any] = {
        "campaign": campaign.name,
        "status": campaign.status,
        "objective_id": campaign.objective_id,
        "raw_payload": raw,
    }
    replacement = await edit_row(db, row.id, updates)
    await db.execute(
        update(CampaignRow)
        .where(CampaignRow.campaign_id == campaign_id, CampaignRow.superseded_at.is_(None))
        .values(campaign=campaign.name, status=campaign.status, objective_id=campaign.objective_id)
    )
    await db.commit()
    if replacement:
        await db.refresh(replacement)
    return replacement


async def delete_campaign_record(
    db: AsyncSession,
    campaign_id: UUID,
    *,
    workspace_id: UUID | None = None,
    brand_id: UUID | None = None,
) -> bool:
    campaign = await get_campaign_record(
        db, campaign_id, workspace_id=workspace_id, brand_id=brand_id
    )
    if not campaign:
        return False
    rows = await rows_for_campaign(db, campaign_id, include_superseded=True, limit=500)
    for row in rows:
        await db.delete(row)
    await db.delete(campaign)
    await db.commit()
    return True


async def campaign_sheet(
    db: AsyncSession,
    campaign_id: UUID,
    *,
    workspace_id: UUID | None = None,
    brand_id: UUID | None = None,
    limit: int = 100,
) -> dict[str, Any] | None:
    campaign = await get_campaign_record(
        db, campaign_id, workspace_id=workspace_id, brand_id=brand_id
    )
    if not campaign:
        return None
    rows = await rows_for_campaign(
        db, campaign_id, workspace_id=workspace_id, brand_id=brand_id, limit=limit
    )
    return {
        "payload_type": "campaign_table@v2",
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "objective_id": campaign.objective_id,
        "rows": [row_dict(row) for row in rows],
    }


async def append_campaign_row(db: AsyncSession, campaign_id: UUID, data: dict[str, Any]) -> CampaignRow:
    data = dict(data or {})
    campaign = await get_campaign_record(
        db,
        campaign_id,
        workspace_id=data.get("workspace_id"),
        brand_id=data.get("brand_id"),
    )
    if not campaign:
        raise ValueError("Campaign does not exist in the requested workspace/brand")

    existing = await rows_for_campaign(db, campaign_id, limit=1)
    base = existing[0] if existing else None
    inherited = {
        "workspace_id": campaign.workspace_id,
        "brand_id": campaign.brand_id,
        "brand": base.brand if base else None,
        "campaign": campaign.name,
        "status": campaign.status,
        "objective_id": campaign.objective_id,
        "business_objective": base.business_objective if base else None,
        "success_metric": base.success_metric if base else None,
        "target": base.target if base else None,
        "baseline": base.baseline if base else None,
        "primary_kpi": base.primary_kpi if base else None,
        "market": base.market if base else None,
    }
    for key, value in inherited.items():
        if data.get(key) in (None, "", [], {}):
            data[key] = value
    data["campaign_id"] = campaign.id
    return await write_row(db, data)


async def claim_unassigned_campaigns(db: AsyncSession, *, workspace_id: UUID, brand_id: UUID) -> int:
    result = await db.execute(
        update(Campaign)
        .where(Campaign.workspace_id == workspace_id, Campaign.brand_id.is_(None))
        .values(brand_id=brand_id)
    )
    await db.execute(
        update(CampaignRow)
        .where(CampaignRow.workspace_id == workspace_id, CampaignRow.brand_id.is_(None))
        .values(brand_id=brand_id)
    )
    return int(result.rowcount or 0)
