"""Upgrade gemini-2.0-flash quality_tier to 'high'

gemini-2.0-flash is comparable to gpt-4o-mini in benchmark performance.
'medium' tier caused it to never win routing when OpenRouter/NVIDIA were available.

Revision ID: 008_gemini_flash_quality
Revises: 007_gemini_nvidia_models
Create Date: 2026-05-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_gemini_flash_quality"
down_revision: Union[str, None] = "007_gemini_nvidia_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        UPDATE model_options
        SET quality_tier = 'high'
        WHERE provider = 'gemini' AND model_id = 'gemini-2.0-flash'
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        UPDATE model_options
        SET quality_tier = 'medium'
        WHERE provider = 'gemini' AND model_id = 'gemini-2.0-flash'
    """))
