"""Create decision_briefs table."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "032_decision_briefs"
down_revision = "031_outcome_records"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "decision_briefs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("objective_id", UUID(as_uuid=True), sa.ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("objective_affected", sa.Text(), nullable=True),
        sa.Column("evidence", JSONB(), nullable=False, server_default="[]"),
        sa.Column("hypothesis_ranking", JSONB(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.String(64), nullable=False, server_default="directional"),
        sa.Column("recommended_next", sa.Text(), nullable=False),
        sa.Column("do_not_list", JSONB(), nullable=False, server_default="[]"),
        sa.Column("allowed_actions", JSONB(), nullable=False, server_default="[]"),
        sa.Column("source_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("full_record", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_decision_briefs_workspace_id", "decision_briefs", ["workspace_id"])
    op.create_index("ix_decision_briefs_brand_id", "decision_briefs", ["brand_id"])
    op.create_index("ix_decision_briefs_objective_id", "decision_briefs", ["objective_id"])
    op.create_index("ix_decision_briefs_status", "decision_briefs", ["status"])
    op.create_index("ix_decision_briefs_created_at", "decision_briefs", ["created_at"])


def downgrade():
    op.drop_index("ix_decision_briefs_created_at", table_name="decision_briefs")
    op.drop_index("ix_decision_briefs_status", table_name="decision_briefs")
    op.drop_index("ix_decision_briefs_objective_id", table_name="decision_briefs")
    op.drop_index("ix_decision_briefs_brand_id", table_name="decision_briefs")
    op.drop_index("ix_decision_briefs_workspace_id", table_name="decision_briefs")
    op.drop_table("decision_briefs")
