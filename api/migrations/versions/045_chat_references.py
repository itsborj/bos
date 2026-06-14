"""Create durable chat references table."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "045_chat_references"
down_revision = "044_calendar_page_slug_unique"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_references",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", sa.Text(), nullable=True),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("drive_file_id", sa.Text(), nullable=True),
        sa.Column("drive_file_name", sa.Text(), nullable=True),
        sa.Column("drive_web_view_link", sa.Text(), nullable=True),
        sa.Column("thumbnail_link", sa.Text(), nullable=True),
        sa.Column("storage_url", sa.Text(), nullable=True),
        sa.Column("sha256", sa.String(128), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("text_excerpt", sa.Text(), nullable=True),
        sa.Column("extraction_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("extracted_chars", sa.Integer(), nullable=True),
        sa.Column("extraction_json", JSONB(), nullable=True),
        sa.Column("variables_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_references_workspace_id", "chat_references", ["workspace_id"])
    op.create_index("ix_chat_references_brand_id", "chat_references", ["brand_id"])
    op.create_index("ix_chat_references_conversation_id", "chat_references", ["conversation_id"])
    op.create_index("ix_chat_references_campaign_id", "chat_references", ["campaign_id"])
    op.create_index("ix_chat_references_drive_file_id", "chat_references", ["drive_file_id"])
    op.create_index("ix_chat_references_sha256", "chat_references", ["sha256"])


def downgrade():
    op.drop_index("ix_chat_references_sha256", table_name="chat_references")
    op.drop_index("ix_chat_references_drive_file_id", table_name="chat_references")
    op.drop_index("ix_chat_references_campaign_id", table_name="chat_references")
    op.drop_index("ix_chat_references_conversation_id", table_name="chat_references")
    op.drop_index("ix_chat_references_brand_id", table_name="chat_references")
    op.drop_index("ix_chat_references_workspace_id", table_name="chat_references")
    op.drop_table("chat_references")
