"""council_session_v2 — live boardroom model fields

Revision ID: 036_council_session_v2
Revises: 035_update_model_catalog
Create Date: 2026-06-02

Adds: current_round, c6_injections, pending_c6_prompt, safety_ceiling, settlement
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text

revision = "036_council_session_v2"
down_revision = "035_update_model_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("council_sessions", sa.Column("current_round", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("council_sessions", sa.Column("c6_injections", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("council_sessions", sa.Column("pending_c6_prompt", sa.Text(), nullable=True))
    op.add_column("council_sessions", sa.Column("safety_ceiling", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("council_sessions", sa.Column("settlement", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("council_sessions", "settlement")
    op.drop_column("council_sessions", "safety_ceiling")
    op.drop_column("council_sessions", "pending_c6_prompt")
    op.drop_column("council_sessions", "c6_injections")
    op.drop_column("council_sessions", "current_round")
