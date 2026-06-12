"""add fallbacks_json and routing_hints_json to execution_backend_overrides

Revision ID: 040_add_fallbacks_routing_hints
Revises: 039_cleanup_fuzzer_data_stream_dedupe
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "040_add_fallbacks_routing_hints"
down_revision = "039_cleanup_fuzzer_data_stream_dedupe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_backend_overrides",
        sa.Column("fallbacks_json", JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "execution_backend_overrides",
        sa.Column("routing_hints_json", JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("execution_backend_overrides", "routing_hints_json")
    op.drop_column("execution_backend_overrides", "fallbacks_json")
