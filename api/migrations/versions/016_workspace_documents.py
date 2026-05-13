"""Add tagged workspace documents.

Revision ID: 016_workspace_documents
Revises: 015_add_approval_tracking
Create Date: 2026-05-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "016_workspace_documents"
down_revision: Union[str, None] = "015_add_approval_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("tags_json", JSONB(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("source_run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workspace_documents_workspace_id", "workspace_documents", ["workspace_id"])
    op.create_index("ix_workspace_documents_doc_type", "workspace_documents", ["doc_type"])
    op.create_index("ix_workspace_documents_status", "workspace_documents", ["status"])
    op.create_index("ix_workspace_documents_workspace_doc_status", "workspace_documents", ["workspace_id", "doc_type", "status"])


def downgrade() -> None:
    op.drop_index("ix_workspace_documents_workspace_doc_status", table_name="workspace_documents")
    op.drop_index("ix_workspace_documents_status", table_name="workspace_documents")
    op.drop_index("ix_workspace_documents_doc_type", table_name="workspace_documents")
    op.drop_index("ix_workspace_documents_workspace_id", table_name="workspace_documents")
    op.drop_table("workspace_documents")
