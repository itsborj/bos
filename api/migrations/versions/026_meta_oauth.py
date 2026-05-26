"""Widen verifier_encrypted to Text for multi-page Facebook OAuth page selection."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "026_meta_oauth"
down_revision = "025_run_pm_task_id"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "provider_login_sessions",
        "verifier_encrypted",
        type_=sa.Text(),
        existing_type=sa.String(1024),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "provider_login_sessions",
        "verifier_encrypted",
        type_=sa.String(1024),
        existing_type=sa.Text(),
        existing_nullable=False,
    )
