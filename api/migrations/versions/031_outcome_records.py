"""Create outcome_records table."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "031_outcome_records"
down_revision = "030_memory_events"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outcome_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("objective_id", UUID(as_uuid=True), sa.ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metrics_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("confidence_source", sa.String(64), nullable=False, server_default="manually_reported"),
        sa.Column("full_record", JSONB(), nullable=False, server_default="{}"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_outcome_records_workspace_id", "outcome_records", ["workspace_id"])
    op.create_index("ix_outcome_records_brand_id", "outcome_records", ["brand_id"])
    op.create_index("ix_outcome_records_objective_id", "outcome_records", ["objective_id"])
    op.create_index("ix_outcome_records_recorded_at", "outcome_records", ["recorded_at"])


def downgrade():
    op.drop_index("ix_outcome_records_recorded_at", table_name="outcome_records")
    op.drop_index("ix_outcome_records_objective_id", table_name="outcome_records")
    op.drop_index("ix_outcome_records_brand_id", table_name="outcome_records")
    op.drop_index("ix_outcome_records_workspace_id", table_name="outcome_records")
    op.drop_table("outcome_records")
