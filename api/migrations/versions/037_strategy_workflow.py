"""strategy_workflow — WorkflowRun + WorkflowComponent tables

Revision ID: 037_strategy_workflow
Revises: 036_council_session_v2
Create Date: 2026-06-04

Adds workflow_runs and workflow_components tables for the modular Strategy
Workflow system. Each strategy_workflow module execution creates one
WorkflowRun and N WorkflowComponent rows (one per component type).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "037_strategy_workflow"
down_revision = "036_council_session_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("archetype", sa.String(64), nullable=False, server_default="direct_sales"),
        sa.Column("request", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_workflow_runs_brand_id", "workflow_runs", ["brand_id"])

    op.create_table(
        "workflow_components",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_run_id", UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("data", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_workflow_components_workflow_run_id", "workflow_components", ["workflow_run_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_components_workflow_run_id", "workflow_components")
    op.drop_table("workflow_components")
    op.drop_index("ix_workflow_runs_brand_id", "workflow_runs")
    op.drop_table("workflow_runs")
