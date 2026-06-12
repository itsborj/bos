"""track CMO usage billing mode

Revision ID: 043_cmo_usage_mode
Revises: 042_cmo_token_usage_brand_id
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "043_cmo_usage_mode"
down_revision = "042_cmo_token_usage_brand_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cmo_token_usage",
        sa.Column("mode", sa.String(50), nullable=False, server_default="platform"),
    )
    op.create_index("ix_cmo_token_usage_mode", "cmo_token_usage", ["mode"])


def downgrade() -> None:
    op.drop_index("ix_cmo_token_usage_mode", table_name="cmo_token_usage")
    op.drop_column("cmo_token_usage", "mode")
