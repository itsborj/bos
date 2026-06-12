"""add cmo_token_usage table for tracking CMO chat LLM calls

Revision ID: 041_cmo_token_usage
Revises: 040_add_fallbacks_routing_hints
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "041_cmo_token_usage"
down_revision = "040_add_fallbacks_routing_hints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cmo_token_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("tokens_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cmo_token_usage_workspace_id", "cmo_token_usage", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_cmo_token_usage_workspace_id", table_name="cmo_token_usage")
    op.drop_table("cmo_token_usage")
