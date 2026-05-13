"""Add approval tracking fields to runs table.

Revision ID: 015
Revises: 014_provider_oauth_token_text
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "015_add_approval_tracking"
down_revision = "014_provider_oauth_token_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add approval_status column to runs table
    op.add_column(
        "runs",
        sa.Column("approval_status", sa.String(50), nullable=True, default="pending")
    )
    
    # Add feedback column to runs table
    op.add_column(
        "runs",
        sa.Column("feedback", sa.Text(), nullable=True)
    )
    
    # Add parent_run_id column to runs table (for revision tracking)
    op.add_column(
        "runs",
        sa.Column("parent_run_id", UUID(as_uuid=True), nullable=True)
    )
    
    # Add foreign key constraint for parent_run_id
    op.create_foreign_key(
        "fk_runs_parent_run_id",
        "runs", "runs",
        ["parent_run_id"], ["id"],
        ondelete="SET NULL"
    )
    
    # Create index on approval_status for faster queries
    op.create_index("ix_runs_approval_status", "runs", ["approval_status"])
    
    # Set default value for existing rows
    op.execute("UPDATE runs SET approval_status = 'pending' WHERE approval_status IS NULL")


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint("fk_runs_parent_run_id", "runs", type_="foreignkey")
    
    # Drop index
    op.drop_index("ix_runs_approval_status", table_name="runs")
    
    # Drop columns
    op.drop_column("runs", "parent_run_id")
    op.drop_column("runs", "feedback")
    op.drop_column("runs", "approval_status")
