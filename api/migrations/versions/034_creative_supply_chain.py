"""Create creative supply chain tables: creative_jobs, creative_assets, creative_blueprints."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "034_creative_supply_chain"
down_revision = "033_pending_decisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "creative_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("concept_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.String(64), nullable=False, server_default="creative_pack"),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("primitive_requirements", JSONB(), nullable=False, server_default="{}"),
        sa.Column("progress_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("bundle_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_creative_jobs_workspace_id", "creative_jobs", ["workspace_id"])
    op.create_index("ix_creative_jobs_brand_id", "creative_jobs", ["brand_id"])
    op.create_index("ix_creative_jobs_campaign_id", "creative_jobs", ["campaign_id"])
    op.create_index("ix_creative_jobs_status", "creative_jobs", ["status"])

    op.create_table(
        "creative_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("drive_file_id", sa.String(255), nullable=True),
        sa.Column("drive_folder_id", sa.String(255), nullable=True),
        sa.Column("asset_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("modality", sa.String(16), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("tags_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("approval_status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("usage_rights", sa.String(16), nullable=False, server_default="campaign_only"),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("generation_prompt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_creative_assets_workspace_id", "creative_assets", ["workspace_id"])
    op.create_index("ix_creative_assets_brand_id", "creative_assets", ["brand_id"])
    op.create_index("ix_creative_assets_campaign_id", "creative_assets", ["campaign_id"])
    op.create_index("ix_creative_assets_job_id", "creative_assets", ["job_id"])
    op.create_index("ix_creative_assets_asset_type", "creative_assets", ["asset_type"])
    op.create_index("ix_creative_assets_approval_status", "creative_assets", ["approval_status"])

    op.create_table(
        "creative_blueprints",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("concept_ref", sa.String(255), nullable=True),
        sa.Column("spec_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("composition_spec", JSONB(), nullable=False, server_default="{}"),
        sa.Column("drive_file_id", sa.String(255), nullable=True),
        sa.Column("validation_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("validation_report", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_creative_blueprints_workspace_id", "creative_blueprints", ["workspace_id"])
    op.create_index("ix_creative_blueprints_brand_id", "creative_blueprints", ["brand_id"])
    op.create_index("ix_creative_blueprints_campaign_id", "creative_blueprints", ["campaign_id"])
    op.create_index("ix_creative_blueprints_job_id", "creative_blueprints", ["job_id"])


def downgrade():
    op.drop_index("ix_creative_blueprints_job_id", table_name="creative_blueprints")
    op.drop_index("ix_creative_blueprints_campaign_id", table_name="creative_blueprints")
    op.drop_index("ix_creative_blueprints_brand_id", table_name="creative_blueprints")
    op.drop_index("ix_creative_blueprints_workspace_id", table_name="creative_blueprints")
    op.drop_table("creative_blueprints")

    op.drop_index("ix_creative_assets_approval_status", table_name="creative_assets")
    op.drop_index("ix_creative_assets_asset_type", table_name="creative_assets")
    op.drop_index("ix_creative_assets_job_id", table_name="creative_assets")
    op.drop_index("ix_creative_assets_campaign_id", table_name="creative_assets")
    op.drop_index("ix_creative_assets_brand_id", table_name="creative_assets")
    op.drop_index("ix_creative_assets_workspace_id", table_name="creative_assets")
    op.drop_table("creative_assets")

    op.drop_index("ix_creative_jobs_status", table_name="creative_jobs")
    op.drop_index("ix_creative_jobs_campaign_id", table_name="creative_jobs")
    op.drop_index("ix_creative_jobs_brand_id", table_name="creative_jobs")
    op.drop_index("ix_creative_jobs_workspace_id", table_name="creative_jobs")
    op.drop_table("creative_jobs")
