"""calendar_pages and calendar_bookings tables

Revision ID: 022_calendar_booking
Revises: 021_provider_keys_brand_scope
Create Date: 2026-05-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "022_calendar_booking"
down_revision: Union[str, None] = "021_provider_keys_brand_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_pages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=True),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("social_connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("working_hours_json", sa.JSON(), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("max_days_ahead", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_calendar_pages_workspace_id", "calendar_pages", ["workspace_id"])
    op.create_index("ix_calendar_pages_brand_id", "calendar_pages", ["brand_id"])
    op.create_index("ix_calendar_pages_slug", "calendar_pages", ["slug"])

    op.create_table(
        "calendar_bookings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("page_id", UUID(as_uuid=True), sa.ForeignKey("calendar_pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("google_event_id", sa.String(255), nullable=True),
        sa.Column("attendee_name", sa.String(255), nullable=False),
        sa.Column("attendee_email", sa.String(255), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="confirmed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_calendar_bookings_page_id", "calendar_bookings", ["page_id"])
    op.create_index("ix_calendar_bookings_start_at", "calendar_bookings", ["start_at"])


def downgrade() -> None:
    op.drop_table("calendar_bookings")
    op.drop_table("calendar_pages")
