"""Add daily_briefs table for the CMO daily brief contract (cmo_daily_brief@v1)

Revision ID: 051_daily_briefs
Revises: 050_campaign_memory_snapshot
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "051_daily_briefs"
down_revision: Union[str, None] = "050_campaign_memory_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_briefs",
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
        sa.Column("payload_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_daily_briefs_brand_generated",
        "daily_briefs",
        ["brand_id", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_briefs_brand_generated", table_name="daily_briefs")
    op.drop_table("daily_briefs")
