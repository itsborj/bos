"""Drop abandoned creative_assets table.

The Postcraft/Brand Kit template redesign will use Brand Kit document metadata as
its resource manifest. The old CreativeAsset ORM/table path was abandoned and
must not be a candidate template source.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "055_drop_creative_assets"
down_revision = "054_retire_legacy_campaign_truth"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP INDEX IF EXISTS ix_creative_assets_approval_status")
    op.execute("DROP INDEX IF EXISTS ix_creative_assets_asset_type")
    op.execute("DROP INDEX IF EXISTS ix_creative_assets_job_id")
    op.execute("DROP INDEX IF EXISTS ix_creative_assets_campaign_id")
    op.execute("DROP INDEX IF EXISTS ix_creative_assets_brand_id")
    op.execute("DROP INDEX IF EXISTS ix_creative_assets_workspace_id")
    op.execute("DROP TABLE IF EXISTS creative_assets")


def downgrade():
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
