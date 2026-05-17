"""Add clickup_task_id to runs

Revision ID: 024_run_clickup_task_id
Revises: 023_workspace_booking_url
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024_run_clickup_task_id"
down_revision: Union[str, None] = "023_workspace_booking_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("clickup_task_id", sa.String(50), nullable=True))
    op.create_index("ix_runs_clickup_task_id", "runs", ["clickup_task_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_clickup_task_id", table_name="runs")
    op.drop_column("runs", "clickup_task_id")
