"""provider auth support: oauth credentials + login sessions

Revision ID: 012_provider_auth
Revises: 011_onboarding_capability
Create Date: 2026-05-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "012_provider_auth"
down_revision: Union[str, None] = "011_onboarding_capability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "provider_keys",
        sa.Column("auth_mode", sa.String(length=50), nullable=False, server_default="api_key"),
    )
    op.add_column(
        "provider_keys",
        sa.Column("refresh_token_encrypted", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "provider_keys",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "provider_keys",
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "provider_keys",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "provider_login_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("login_type", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=255), nullable=False),
        sa.Column("verifier_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("redirect_uri", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_provider_login_sessions_workspace_provider",
        "provider_login_sessions",
        ["workspace_id", "provider"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_login_sessions_workspace_provider", table_name="provider_login_sessions")
    op.drop_table("provider_login_sessions")
    op.drop_column("provider_keys", "updated_at")
    op.drop_column("provider_keys", "metadata_json")
    op.drop_column("provider_keys", "expires_at")
    op.drop_column("provider_keys", "refresh_token_encrypted")
    op.drop_column("provider_keys", "auth_mode")
