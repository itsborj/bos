"""Create council_sessions table."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "028_council_session"
down_revision = "027_marketing_channel_capability"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "council_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("brand_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("rounds_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rounds", JSONB(), nullable=False, server_default="[]"),
        sa.Column("marching_orders", JSONB(), nullable=False, server_default="[]"),
        sa.Column("parked_decisions", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("council_sessions")
