"""Add booking_url to workspaces

Revision ID: 023_workspace_booking_url
Revises: 022_calendar_booking
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023_workspace_booking_url"
down_revision: Union[str, None] = "022_calendar_booking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("booking_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "booking_url")
