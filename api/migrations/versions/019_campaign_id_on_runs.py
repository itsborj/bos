"""campaign_id FK on runs

Revision ID: 019_campaign_id_on_runs
Revises: 018_brands_and_intent_hooks
Create Date: 2026-05-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "019_campaign_id_on_runs"
down_revision: Union[str, None] = "018_brands_and_intent_hooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_runs_campaign_id", "runs", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_campaign_id", table_name="runs")
    op.drop_column("runs", "campaign_id")
