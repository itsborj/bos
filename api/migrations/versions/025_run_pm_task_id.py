"""Rename clickup_task_id → pm_task_id on runs (generic PM plugin field)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "025_run_pm_task_id"
down_revision = "024_run_clickup_task_id"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("runs", "clickup_task_id", new_column_name="pm_task_id")
    op.drop_index("ix_runs_clickup_task_id", table_name="runs")
    op.create_index("ix_runs_pm_task_id", "runs", ["pm_task_id"])


def downgrade():
    op.drop_index("ix_runs_pm_task_id", table_name="runs")
    op.create_index("ix_runs_clickup_task_id", "runs", ["pm_task_id"])
    op.alter_column("runs", "pm_task_id", new_column_name="clickup_task_id")
