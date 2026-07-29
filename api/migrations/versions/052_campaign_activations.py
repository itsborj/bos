"""Add campaign_activations and run activation binding

Revision ID: 052_campaign_activations
Revises: 051_daily_briefs
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "052_campaign_activations"
down_revision: Union[str, None] = "051_daily_briefs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaign_activations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channels", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_campaign_activations_campaign_window",
        "campaign_activations",
        ["campaign_id", "starts_at", "ends_at"],
    )
    op.create_index(
        "ix_campaign_activations_brand_campaign",
        "campaign_activations",
        ["brand_id", "campaign_id"],
    )
    op.add_column(
        "runs",
        sa.Column(
            "activation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_activations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_runs_activation_id", "runs", ["activation_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_activation_id", table_name="runs")
    op.drop_column("runs", "activation_id")
    op.drop_index("ix_campaign_activations_brand_campaign", table_name="campaign_activations")
    op.drop_index("ix_campaign_activations_campaign_window", table_name="campaign_activations")
    op.drop_table("campaign_activations")
