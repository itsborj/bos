"""provider_keys table

Revision ID: 003_provider_keys
Revises: 002_core_workspace
Create Date: 2026-05-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003_provider_keys"
down_revision: Union[str, None] = "002_core_workspace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("key_encrypted", sa.String(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_provider_keys_workspace_provider",
        "provider_keys",
        ["workspace_id", "provider"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_keys_workspace_provider", table_name="provider_keys")
    op.drop_table("provider_keys")
