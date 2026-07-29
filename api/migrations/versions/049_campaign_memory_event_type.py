"""Allow campaign_memory memory event type

Revision ID: 049_campaign_memory_event_type
Revises: 048_campaign_living_memory
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "049_campaign_memory_event_type"
down_revision: Union[str, None] = "048_campaign_living_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BASE_TYPES = (
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


def _in_list(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(repr(v) for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint("ck_memory_events_event_type", "memory_events", type_="check")
    op.create_check_constraint(
        "ck_memory_events_event_type",
        "memory_events",
        f"event_type IN {_in_list(_BASE_TYPES + ('campaign_memory',))}",
    )


def downgrade() -> None:
    op.drop_constraint("ck_memory_events_event_type", "memory_events", type_="check")
    op.create_check_constraint(
        "ck_memory_events_event_type",
        "memory_events",
        f"event_type IN {_in_list(_BASE_TYPES)}",
    )
