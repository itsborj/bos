"""add brand_id to cmo_token_usage for per-brand cost attribution

Revision ID: 042_cmo_token_usage_brand_id
Revises: 041_cmo_token_usage
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "042_cmo_token_usage_brand_id"
down_revision = "041_cmo_token_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cmo_token_usage",
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_cmo_token_usage_brand_id", "cmo_token_usage", ["brand_id"])


def downgrade() -> None:
    op.drop_index("ix_cmo_token_usage_brand_id", table_name="cmo_token_usage")
    op.drop_column("cmo_token_usage", "brand_id")
