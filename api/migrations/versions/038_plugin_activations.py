"""plugin_activations — track plugin active/inactive state per brand

Revision ID: 038_plugin_activations
Revises: 037_strategy_workflow
Create Date: 2026-06-08

A plugin directory being present does not mean it is active.
This table is the source of truth for what is loaded into the CMO manifest.

  status: 'active' | 'inactive' | 'error'
  brand_id = NULL  → org-level activation (all brands)
  brand_id = UUID  → per-brand activation; overrides org-level row for that brand
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "038_plugin_activations"
down_revision = "037_strategy_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_activations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("plugin_id", sa.Text, nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="inactive"),
        sa.Column("error_reason", sa.Text, nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_unique_constraint(
        "uq_plugin_activations_plugin_brand",
        "plugin_activations",
        ["plugin_id", "brand_id"],
    )
    # PostgreSQL treats NULL values as distinct in normal unique constraints;
    # this partial index enforces one org-level row per plugin.
    op.create_index(
        "uq_plugin_activations_plugin_org",
        "plugin_activations",
        ["plugin_id"],
        unique=True,
        postgresql_where=sa.text("brand_id IS NULL"),
    )
    op.create_index("ix_plugin_activations_status", "plugin_activations", ["status"])
    op.create_index("ix_plugin_activations_brand", "plugin_activations", ["brand_id"])


def downgrade() -> None:
    op.drop_index("uq_plugin_activations_plugin_org", table_name="plugin_activations")
    op.drop_table("plugin_activations")
