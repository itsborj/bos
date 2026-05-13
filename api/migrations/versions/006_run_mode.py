"""Add mode column to run_attempts; unique constraint on provider_keys(workspace_id, provider)

Revision ID: 006_run_mode
Revises: 005_runs
Create Date: 2026-05-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_run_mode"
down_revision: Union[str, None] = "005_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "run_attempts",
        sa.Column("mode", sa.String(50), nullable=False, server_default="mock"),
    )
    op.create_unique_constraint(
        "uq_provider_keys_workspace_provider",
        "provider_keys",
        ["workspace_id", "provider"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_provider_keys_workspace_provider", "provider_keys", type_="unique"
    )
    op.drop_column("run_attempts", "mode")
