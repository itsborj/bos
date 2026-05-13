"""execution backend overrides

Revision ID: 017_execution_backend_overrides
Revises: 016_workspace_documents
Create Date: 2026-05-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "017_execution_backend_overrides"
down_revision: Union[str, None] = "016_workspace_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "execution_backend_overrides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=True),
        sa.Column("tool_id", sa.String(255), nullable=True),
        sa.Column("modality", sa.String(50), nullable=False, server_default="text"),
        sa.Column("strict", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "target", name="uq_backend_override_workspace_target"),
    )
    op.create_index("ix_execution_backend_overrides_workspace_id", "execution_backend_overrides", ["workspace_id"])
    op.create_index("ix_execution_backend_overrides_target", "execution_backend_overrides", ["target"])


def downgrade() -> None:
    op.drop_index("ix_execution_backend_overrides_target", table_name="execution_backend_overrides")
    op.drop_index("ix_execution_backend_overrides_workspace_id", table_name="execution_backend_overrides")
    op.drop_table("execution_backend_overrides")
