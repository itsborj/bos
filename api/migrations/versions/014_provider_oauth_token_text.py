"""widen provider oauth token columns to text

Revision ID: 014_provider_oauth_token_text
Revises: 013_openai_provider
Create Date: 2026-05-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_provider_oauth_token_text"
down_revision: Union[str, None] = "013_openai_provider"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "provider_keys",
        "key_encrypted",
        existing_type=sa.String(length=1024),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "provider_keys",
        "refresh_token_encrypted",
        existing_type=sa.String(length=1024),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "provider_keys",
        "refresh_token_encrypted",
        existing_type=sa.Text(),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )
    op.alter_column(
        "provider_keys",
        "key_encrypted",
        existing_type=sa.Text(),
        type_=sa.String(length=1024),
        existing_nullable=False,
    )
