from __future__ import annotations

import decimal
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Campaign(Base):
    """Durable Campaign identity and lifecycle record.

    Dated operating truth belongs to :class:`CampaignRow`. This table contains
    identity and lifecycle only; it is not an alternative fact or JSON store.
    """

    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CampaignRow(Base):
    """Canonical Campaign V2 dated operating row.

    This table is the Campaign source of truth. Daily, weekly, monthly,
    quarterly, and client-meeting views are filters over these dated rows.
    The table stores facts and evidence refs only; LLM/CMO synthesis is not
    Campaign code.
    """

    __tablename__ = "campaign_rows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True
    )
    campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True
    )
    business_objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success_metric: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    baseline: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_kpi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    period_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    time_period: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    distribution_channel: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    channel_role: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    market: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    planned_activity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_activity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reach: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    impressions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    engagement: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reach_metric: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    engagement_metric: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_metric: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    efficiency_metric: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_metric: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clicks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    leads: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calls: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    qualified_calls: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    conversions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spend: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    budget: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    revenue: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    source_health: Mapped[str] = mapped_column(String(32), nullable=False, default="reported")
    freshness: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="producer_reported")
    objective_verdict: Mapped[str] = mapped_column(String(32), nullable=False, default="inconclusive")
    confidence: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    what_changed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    top_learning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blocker: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_needed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    source_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    producer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    evidence_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_rows.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
