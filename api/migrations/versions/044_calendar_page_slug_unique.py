"""add partial unique index on calendar_pages.slug where is_active

Revision ID: 044_calendar_page_slug_unique
Revises: 043_cmo_usage_mode
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = "044_calendar_page_slug_unique"
down_revision = "043_cmo_usage_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deactivate calendar pages with invalid slugs (fuzzer artifacts).
    # Valid slugs match ^[a-z0-9][a-z0-9_-]{1,79}$ — anything else is garbage.
    op.execute(
        "UPDATE calendar_pages SET is_active = FALSE "
        "WHERE is_active = TRUE "
        "AND (slug IS NULL OR slug = '' OR slug !~ '^[a-z0-9][a-z0-9_-]{1,79}$')"
    )
    op.create_index(
        "uq_calendar_pages_active_slug",
        "calendar_pages",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    op.drop_index("uq_calendar_pages_active_slug", table_name="calendar_pages")
