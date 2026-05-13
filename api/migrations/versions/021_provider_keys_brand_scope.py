"""scope provider BYOK credentials per brand

Revision ID: 021_provider_keys_brand_scope
Revises: 020_social_connections
Create Date: 2026-05-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "021_provider_keys_brand_scope"
down_revision: Union[str, None] = "020_social_connections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("provider_keys", sa.Column("brand_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_provider_keys_brand_id_brands",
        "provider_keys",
        "brands",
        ["brand_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("uq_provider_keys_workspace_provider", "provider_keys", type_="unique")
    op.create_index(
        "uq_provider_keys_workspace_provider_global",
        "provider_keys",
        ["workspace_id", "provider"],
        unique=True,
        postgresql_where=sa.text("brand_id IS NULL"),
    )
    op.create_index(
        "uq_provider_keys_workspace_brand_provider",
        "provider_keys",
        ["workspace_id", "brand_id", "provider"],
        unique=True,
        postgresql_where=sa.text("brand_id IS NOT NULL"),
    )
    op.create_index("ix_provider_keys_brand_id", "provider_keys", ["brand_id"])


def downgrade() -> None:
    op.drop_index("ix_provider_keys_brand_id", table_name="provider_keys")
    op.drop_index("uq_provider_keys_workspace_brand_provider", table_name="provider_keys")
    op.drop_index("uq_provider_keys_workspace_provider_global", table_name="provider_keys")
    op.create_unique_constraint(
        "uq_provider_keys_workspace_provider",
        "provider_keys",
        ["workspace_id", "provider"],
    )
    op.drop_constraint("fk_provider_keys_brand_id_brands", "provider_keys", type_="foreignkey")
    op.drop_column("provider_keys", "brand_id")
