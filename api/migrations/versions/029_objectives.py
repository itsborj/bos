"""Create objectives table."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "029_objectives"
down_revision = "028_council_session"
branch_labels = None
depends_on = None


_OBJECTIVE_STATUSES = ("draft", "active", "paused", "completed", "archived")


def upgrade():
    op.create_table(
        "objectives",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("success_metric", sa.Text(), nullable=False),
        sa.Column("horizon", sa.String(120), nullable=False),
        sa.Column("created_from", sa.String(120), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"status IN {_OBJECTIVE_STATUSES}", name="ck_objectives_status"),
    )
    op.create_index("ix_objectives_workspace_id", "objectives", ["workspace_id"])
    op.create_index("ix_objectives_brand_id", "objectives", ["brand_id"])
    op.create_index("ix_objectives_status", "objectives", ["status"])
    op.create_index("ix_objectives_workspace_status", "objectives", ["workspace_id", "status"])


def downgrade():
    op.drop_index("ix_objectives_workspace_status", table_name="objectives")
    op.drop_index("ix_objectives_status", table_name="objectives")
    op.drop_index("ix_objectives_brand_id", table_name="objectives")
    op.drop_index("ix_objectives_workspace_id", table_name="objectives")
    op.drop_table("objectives")
