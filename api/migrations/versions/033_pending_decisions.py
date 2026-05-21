"""Create pending_decisions table."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "033_pending_decisions"
down_revision = "032_decision_briefs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pending_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("objective_id", UUID(as_uuid=True), sa.ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("what_is_deferred", sa.Text(), nullable=False),
        sa.Column("waiting_for", sa.Text(), nullable=False),
        sa.Column("leading_hypothesis", sa.Text(), nullable=True),
        sa.Column("action_blocked", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("full_record", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pending_decisions_workspace_id", "pending_decisions", ["workspace_id"])
    op.create_index("ix_pending_decisions_brand_id", "pending_decisions", ["brand_id"])
    op.create_index("ix_pending_decisions_objective_id", "pending_decisions", ["objective_id"])
    op.create_index("ix_pending_decisions_status", "pending_decisions", ["status"])


def downgrade():
    op.drop_index("ix_pending_decisions_status", table_name="pending_decisions")
    op.drop_index("ix_pending_decisions_objective_id", table_name="pending_decisions")
    op.drop_index("ix_pending_decisions_brand_id", table_name="pending_decisions")
    op.drop_index("ix_pending_decisions_workspace_id", table_name="pending_decisions")
    op.drop_table("pending_decisions")
