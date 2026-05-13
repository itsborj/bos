"""stream_updates table

Revision ID: 010_stream_updates
Revises: 009_intent_contracts
Create Date: 2026-05-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "010_stream_updates"
down_revision: Union[str, None] = "009_intent_contracts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stream_updates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("layout_hint", sa.String(50), nullable=False, server_default="narrative"),
        sa.Column("interaction", sa.String(50), nullable=False, server_default="passive"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("data_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_key", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_stream_updates_workspace_id", "stream_updates", ["workspace_id"])
    op.create_index("ix_stream_updates_dismissed_at", "stream_updates", ["dismissed_at"])
    op.create_index("ix_stream_updates_priority", "stream_updates", ["priority"])
    # Deduplication: one active block per workspace + source_key
    op.create_index(
        "ix_stream_updates_workspace_source_key",
        "stream_updates",
        ["workspace_id", "source_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_stream_updates_workspace_source_key", table_name="stream_updates")
    op.drop_index("ix_stream_updates_priority", table_name="stream_updates")
    op.drop_index("ix_stream_updates_dismissed_at", table_name="stream_updates")
    op.drop_index("ix_stream_updates_workspace_id", table_name="stream_updates")
    op.drop_table("stream_updates")
