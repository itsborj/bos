"""Add Gemini and NVIDIA model options for copywriting and analysis capabilities

Revision ID: 007_gemini_nvidia_models
Revises: 006_run_mode
Create Date: 2026-05-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_gemini_nvidia_models"
down_revision: Union[str, None] = "006_run_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Costs are in the same demo-scale unit as the original seed data (~1000x real pricing).
# Real pricing reference:
#   Gemini 2.0 Flash:        $0.10/$0.40 per 1M tokens
#   Gemini 1.5 Pro:          $1.25/$5.00 per 1M tokens
#   NVIDIA Llama 3.1 8B:     $0.10/$0.10 per 1M tokens
#   NVIDIA Llama 3.3 70B:    $0.12/$0.12 per 1M tokens


def upgrade() -> None:
    # ── Gemini — copywriting ───────────────────────────────────────────────────
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'gemini', 'gemini-2.0-flash',
               0.000100, 0.000400, 'medium', 1500, 0.97, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.copywriting'
    """))
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'gemini', 'gemini-1.5-pro',
               0.001250, 0.005000, 'high', 3000, 0.96, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.copywriting'
    """))

    # ── NVIDIA — copywriting ───────────────────────────────────────────────────
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'nvidia', 'meta/llama-3.1-8b-instruct',
               0.000100, 0.000100, 'low', 1200, 0.95, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.copywriting'
    """))
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'nvidia', 'meta/llama-3.3-70b-instruct',
               0.000120, 0.000120, 'high', 2800, 0.96, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.copywriting'
    """))

    # ── Gemini — analysis ─────────────────────────────────────────────────────
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'gemini', 'gemini-2.0-flash',
               0.000100, 0.000400, 'medium', 1500, 0.97, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.analysis'
    """))
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'gemini', 'gemini-1.5-pro',
               0.001250, 0.005000, 'high', 3000, 0.96, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.analysis'
    """))

    # ── NVIDIA — analysis ─────────────────────────────────────────────────────
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'nvidia', 'meta/llama-3.3-70b-instruct',
               0.000120, 0.000120, 'high', 2800, 0.96, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.analysis'
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM model_options WHERE provider IN ('gemini', 'nvidia')
    """))
