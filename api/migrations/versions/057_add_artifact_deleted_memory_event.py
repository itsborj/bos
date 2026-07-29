"""Add artifact_deleted memory event type

Revision ID: 057_add_artifact_deleted_memory_event
Revises: 056_consolidate_campaign_database_ownership
Create Date: 2026-07-23

"""
from typing import Sequence, Union

from alembic import op

revision: str = "057_add_artifact_deleted_memory_event"
down_revision: Union[str, None] = "056_consolidate_campaign_database_ownership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TYPES_WITH_DELETE = (
    "artifact_created",
    "artifact_approved",
    "artifact_deleted",
    "artifact_dismissed",  # legacy rows only
    "artifact_revised",
    "run_failed",
    "decision_made",
    "decision_not_to_act",
    "outcome_recorded",
    "constraint_flag",
    "campaign_memory",
)

_TYPES_WITHOUT_DELETE = tuple(t for t in _TYPES_WITH_DELETE if t != "artifact_deleted")


def _in_list(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(repr(v) for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint("ck_memory_events_event_type", "memory_events", type_="check")
    op.create_check_constraint(
        "ck_memory_events_event_type",
        "memory_events",
        f"event_type IN {_in_list(_TYPES_WITH_DELETE)}",
    )


def downgrade() -> None:
    op.drop_constraint("ck_memory_events_event_type", "memory_events", type_="check")
    op.create_check_constraint(
        "ck_memory_events_event_type",
        "memory_events",
        f"event_type IN {_in_list(_TYPES_WITHOUT_DELETE)}",
    )
