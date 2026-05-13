"""add openai model options for copywriting and onboarding

Revision ID: 013_openai_provider
Revises: 012_provider_auth
Create Date: 2026-05-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_openai_provider"
down_revision: Union[str, None] = "012_provider_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openai', 'gpt-5.1',
               0.001250, 0.010000, 'high', 2200, 0.97, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.copywriting'
    """))

    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openai', 'gpt-5.1',
               0.001250, 0.010000, 'high', 2200, 0.97, true, 'healthy'
        FROM capabilities WHERE key = 'onboarding.brand_profiling'
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM model_options WHERE provider = 'openai'
    """))
