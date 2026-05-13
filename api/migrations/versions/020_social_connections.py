"""social_connections table for per-brand social page OAuth tokens

Revision ID: 020_social_connections
Revises: 019_campaign_id_on_runs
Create Date: 2026-05-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "020_social_connections"
down_revision: Union[str, None] = "019_campaign_id_on_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "social_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("page_id", sa.String(255), nullable=False),
        sa.Column("page_name", sa.String(255), nullable=True),
        sa.Column("page_handle", sa.String(255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_meta_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="connected"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_social_connections_brand_id", "social_connections", ["brand_id"])
    op.create_index("ix_social_connections_workspace_id", "social_connections", ["workspace_id"])
    op.create_unique_constraint(
        "uq_social_brand_platform_page",
        "social_connections",
        ["brand_id", "platform", "page_id"],
    )


def downgrade() -> None:
    op.drop_table("social_connections")
