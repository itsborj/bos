"""Add onboarding.brand_profiling capability with model options

Revision ID: 011_onboarding_capability
Revises: 010_stream_updates
Create Date: 2026-05-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_onboarding_capability"
down_revision: Union[str, None] = "010_stream_updates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO capabilities (key, modality, budget_ceiling, latency_target_ms) VALUES
        ('onboarding.brand_profiling', 'text', 0.10, 10000)
    """))

    # Gemini — brand profiling (prefers JSON-capable models for structured output)
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'gemini', 'gemini-2.0-flash',
               0.000100, 0.000400, 'medium', 1500, 0.97, true, 'healthy'
        FROM capabilities WHERE key = 'onboarding.brand_profiling'
    """))
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'gemini', 'gemini-1.5-pro',
               0.001250, 0.005000, 'high', 3000, 0.96, true, 'healthy'
        FROM capabilities WHERE key = 'onboarding.brand_profiling'
    """))

    # NVIDIA — brand profiling
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'nvidia', 'meta/llama-3.3-70b-instruct',
               0.000120, 0.000120, 'high', 2800, 0.96, true, 'healthy'
        FROM capabilities WHERE key = 'onboarding.brand_profiling'
    """))
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'nvidia', 'meta/llama-3.1-8b-instruct',
               0.000100, 0.000100, 'low', 1200, 0.95, true, 'healthy'
        FROM capabilities WHERE key = 'onboarding.brand_profiling'
    """))

    # OpenRouter fallback — brand profiling
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openrouter', 'openai/gpt-4o-mini',
               0.00015, 0.00180, 'high', 2500, 0.98, true, 'healthy'
        FROM capabilities WHERE key = 'onboarding.brand_profiling'
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM model_options
        WHERE capability_id = (SELECT id FROM capabilities WHERE key = 'onboarding.brand_profiling')
    """))
    op.execute(sa.text("""
        DELETE FROM capabilities WHERE key = 'onboarding.brand_profiling'
    """))
