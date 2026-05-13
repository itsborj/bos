"""brands table, brand_id FKs, intent_ref on runs

Revision ID: 018_brands_and_intent_hooks
Revises: 017_execution_backend_overrides
Create Date: 2026-05-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "018_brands_and_intent_hooks"
down_revision: Union[str, None] = "017_execution_backend_overrides"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── brands table ──────────────────────────────────────────────────────────
    op.create_table(
        "brands",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("brand_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_brand_workspace_name"),
    )
    op.create_index("ix_brands_workspace_id", "brands", ["workspace_id"])

    # ── brand_id (nullable) on existing tables ────────────────────────────────
    for table in ("products", "audiences", "workspace_documents", "campaigns"):
        op.add_column(table, sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True))
        op.create_index(f"ix_{table}_brand_id", table, ["brand_id"])

    op.add_column("runs", sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_runs_brand_id", "runs", ["brand_id"])

    # ── intent_ref (nullable) on runs — BITE plan hook ────────────────────────
    op.add_column("runs", sa.Column(
        "intent_ref",
        UUID(as_uuid=True),
        sa.ForeignKey("intent_contracts.id", ondelete="SET NULL"),
        nullable=True,
    ))
    op.create_index("ix_runs_intent_ref", "runs", ["intent_ref"])


def downgrade() -> None:
    op.drop_index("ix_runs_intent_ref", table_name="runs")
    op.drop_column("runs", "intent_ref")
    op.drop_index("ix_runs_brand_id", table_name="runs")
    op.drop_column("runs", "brand_id")

    for table in ("products", "audiences", "workspace_documents", "campaigns"):
        op.drop_index(f"ix_{table}_brand_id", table_name=table)
        op.drop_column(table, "brand_id")

    op.drop_index("ix_brands_workspace_id", table_name="brands")
    op.drop_table("brands")
