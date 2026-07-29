"""Campaign living memory fields

Revision ID: 048_campaign_living_memory
Revises: 047_add_campaign_primitives
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by alembic.
revision: str = "048_campaign_living_memory"
down_revision: Union[str, None] = "047_add_campaign_primitives"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("memory_events", sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_memory_events_campaign",
        "memory_events",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("memory_events", sa.Column("primitive_type", sa.String(length=64), nullable=True))
    op.add_column("memory_events", sa.Column("primitive_status", sa.String(length=32), nullable=True))
    op.add_column("memory_events", sa.Column("confidence", sa.String(length=32), nullable=True))
    op.add_column("memory_events", sa.Column("source_type", sa.String(length=64), nullable=True))
    op.create_index("ix_memory_events_campaign_id", "memory_events", ["campaign_id"])
    op.create_index("ix_memory_events_primitive_type", "memory_events", ["primitive_type"])


def downgrade() -> None:
    op.drop_index("ix_memory_events_primitive_type", table_name="memory_events")
    op.drop_index("ix_memory_events_campaign_id", table_name="memory_events")
    op.drop_column("memory_events", "source_type")
    op.drop_column("memory_events", "confidence")
    op.drop_column("memory_events", "primitive_status")
    op.drop_column("memory_events", "primitive_type")
    op.drop_constraint("fk_memory_events_campaign", "memory_events", type_="foreignkey")
    op.drop_column("memory_events", "campaign_id")
