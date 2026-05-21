"""Create memory_events table."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "030_memory_events"
down_revision = "029_objectives"
branch_labels = None
depends_on = None

_EVENT_TYPES = (
    "artifact_created",
    "artifact_approved",
    "artifact_dismissed",
    "artifact_revised",
    "run_failed",
    "decision_made",
    "decision_not_to_act",
    "outcome_recorded",
    "constraint_flag",
)


def upgrade():
    op.create_table(
        "memory_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("objective_id", UUID(as_uuid=True), sa.ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("topic_tags", JSONB(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("full_record", JSONB(), nullable=False, server_default="{}"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"event_type IN {_EVENT_TYPES}", name="ck_memory_events_event_type"),
        sa.CheckConstraint(
            "event_type NOT IN ('decision_made', 'decision_not_to_act') OR "
            "(rationale IS NOT NULL AND length(trim(rationale)) > 0)",
            name="ck_memory_events_decision_rationale",
        ),
    )
    op.create_index("ix_memory_events_workspace_id", "memory_events", ["workspace_id"])
    op.create_index("ix_memory_events_brand_id", "memory_events", ["brand_id"])
    op.create_index("ix_memory_events_objective_id", "memory_events", ["objective_id"])
    op.create_index("ix_memory_events_event_type", "memory_events", ["event_type"])
    op.create_index("ix_memory_events_timestamp", "memory_events", ["timestamp"])


def downgrade():
    op.drop_index("ix_memory_events_timestamp", table_name="memory_events")
    op.drop_index("ix_memory_events_event_type", table_name="memory_events")
    op.drop_index("ix_memory_events_objective_id", table_name="memory_events")
    op.drop_index("ix_memory_events_brand_id", table_name="memory_events")
    op.drop_index("ix_memory_events_workspace_id", table_name="memory_events")
    op.drop_table("memory_events")
