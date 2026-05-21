"""Add marketing.channel capability and model options for channel plugins

Revision ID: 027_marketing_channel_capability
Revises: 026_meta_oauth
Create Date: 2026-05-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027_marketing_channel_capability"
down_revision: Union[str, None] = "026_meta_oauth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO capabilities (key, modality, budget_ceiling, latency_target_ms)
        VALUES ('marketing.channel', 'text', 0.10, 8000)
        ON CONFLICT (key) DO NOTHING
    """))

    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openrouter', 'openai/gpt-4o-mini',
               0.00015, 0.00180, 'high', 2500, 0.98, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.channel'
    """))

    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openrouter', 'anthropic/claude-3-haiku',
               0.00025, 0.00125, 'medium', 2200, 0.97, false, 'healthy'
        FROM capabilities WHERE key = 'marketing.channel'
    """))

    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'gemini', 'gemini-2.0-flash',
               0.00010, 0.00040, 'high', 1500, 0.97, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.channel'
    """))

    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'nvidia', 'meta/llama-3.3-70b-instruct',
               0.00012, 0.00012, 'high', 2000, 0.95, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.channel'
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM model_options
        WHERE capability_id = (SELECT id FROM capabilities WHERE key = 'marketing.channel')
    """))
    op.execute(sa.text("DELETE FROM capabilities WHERE key = 'marketing.channel'"))
