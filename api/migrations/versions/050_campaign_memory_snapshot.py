"""Add memory_snapshot and memory_snapshot_at columns to campaigns

Revision ID: 050_campaign_memory_snapshot
Revises: 049_campaign_memory_event_type
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "050_campaign_memory_snapshot"
down_revision: Union[str, None] = "049_campaign_memory_event_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("memory_snapshot", postgresql.JSONB, nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "memory_snapshot_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "memory_snapshot_at")
    op.drop_column("campaigns", "memory_snapshot")
