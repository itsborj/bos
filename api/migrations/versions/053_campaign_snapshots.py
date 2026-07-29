"""Add campaign_snapshots as Campaign V2 operating sheet

Revision ID: 053_campaign_snapshots
Revises: 052_campaign_activations
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "053_campaign_snapshots"
down_revision: Union[str, None] = "052_campaign_activations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaign_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("objective_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("activation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign_activations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("distribution_channel", sa.String(64), nullable=True),
        sa.Column("channel_role", sa.String(128), nullable=True),
        sa.Column("time_period", sa.String(64), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("producer", sa.String(255), nullable=True),
        sa.Column("planned_activity", sa.Text(), nullable=True),
        sa.Column("actual_activity", sa.Text(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("engagement", sa.Integer(), nullable=True),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("leads", sa.Integer(), nullable=True),
        sa.Column("calls", sa.Integer(), nullable=True),
        sa.Column("qualified_calls", sa.Integer(), nullable=True),
        sa.Column("conversions", sa.Integer(), nullable=True),
        sa.Column("spend", sa.Numeric(12, 2), nullable=True),
        sa.Column("revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column("source_health", sa.String(32), nullable=False, server_default="reported"),
        sa.Column("freshness", sa.String(32), nullable=True),
        sa.Column("verification_status", sa.String(32), nullable=False, server_default="producer_reported"),
        sa.Column("objective_verdict", sa.String(32), nullable=False, server_default="inconclusive"),
        sa.Column("confidence", sa.String(32), nullable=True),
        sa.Column("what_changed", sa.Text(), nullable=True),
        sa.Column("blocker", sa.Text(), nullable=True),
        sa.Column("decision_needed", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(255), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence_refs", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_snapshots_campaign_period", "campaign_snapshots", ["campaign_id", "time_period", "distribution_channel"])
    op.create_index("ix_campaign_snapshots_brand_campaign", "campaign_snapshots", ["brand_id", "campaign_id"])
    op.create_index("ix_campaign_snapshots_verdict", "campaign_snapshots", ["objective_verdict", "source_health", "verification_status"])


def downgrade() -> None:
    op.drop_index("ix_campaign_snapshots_verdict", table_name="campaign_snapshots")
    op.drop_index("ix_campaign_snapshots_brand_campaign", table_name="campaign_snapshots")
    op.drop_index("ix_campaign_snapshots_campaign_period", table_name="campaign_snapshots")
    op.drop_table("campaign_snapshots")
