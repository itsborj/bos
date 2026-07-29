"""Update Claude model catalog: add Sonnet 4.6, Opus 4.8, Haiku 4.5, Fable 5; deprecate Sonnet 4.5

Revision ID: 046_update_claude_models
Revises: 045_chat_references
Create Date: 2026-06-18

Pricing reference (per 1M tokens, via OpenRouter):
  anthropic/claude-sonnet-4-6:          $3.00 in / $15.00 out
  anthropic/claude-opus-4-8:            $15.00 in / $75.00 out
  anthropic/claude-haiku-4-5-20251001:  $0.80 in / $4.00 out
  anthropic/claude-fable-5:             $3.00 in / $15.00 out
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046_update_claude_models"
down_revision: Union[str, None] = "045_chat_references"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CAPS = ["marketing.copywriting", "marketing.analysis", "onboarding.brand_profiling"]


def _insert(capability_key: str, provider: str, model_id: str,
            input_cost: float, output_cost: float,
            quality_tier: str, latency_ms: int,
            availability_score: float, supports_json: bool) -> None:
    op.execute(sa.text(f"""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id,
               '{provider}', '{model_id}',
               {input_cost}, {output_cost},
               '{quality_tier}', {latency_ms}, {availability_score}, {'true' if supports_json else 'false'}, 'healthy'
        FROM capabilities
        WHERE key = '{capability_key}'
          AND NOT EXISTS (
              SELECT 1 FROM model_options mo
              JOIN capabilities c ON c.id = mo.capability_id
              WHERE c.key = '{capability_key}'
                AND mo.provider = '{provider}'
                AND mo.model_id = '{model_id}'
          )
    """))


def upgrade() -> None:
    # ── Claude Sonnet 4.6 — current default Sonnet ────────────────────────────
    for cap in _CAPS:
        _insert(cap, "openrouter", "anthropic/claude-sonnet-4-6",
                0.003000, 0.015000, "high", 2200, 0.98, True)

    # ── Claude Opus 4.8 — most capable, highest quality ───────────────────────
    for cap in _CAPS:
        _insert(cap, "openrouter", "anthropic/claude-opus-4-8",
                0.015000, 0.075000, "high", 4000, 0.97, True)

    # ── Claude Haiku 4.5 — fastest, most cost-efficient ───────────────────────
    for cap in _CAPS:
        _insert(cap, "openrouter", "anthropic/claude-haiku-4-5-20251001",
                0.000800, 0.004000, "medium", 1200, 0.99, True)

    # ── Claude Fable 5 — fast Opus-class reasoning ────────────────────────────
    for cap in _CAPS:
        _insert(cap, "openrouter", "anthropic/claude-fable-5",
                0.003000, 0.015000, "high", 2500, 0.97, True)

    # ── Deprecate Sonnet 4.5 ─────────────────────────────────────────────────
    op.execute(sa.text("""
        UPDATE model_options SET status = 'deprecated'
        WHERE provider = 'openrouter' AND model_id = 'anthropic/claude-sonnet-4-5'
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM model_options
        WHERE (provider, model_id) IN (
            ('openrouter', 'anthropic/claude-sonnet-4-6'),
            ('openrouter', 'anthropic/claude-opus-4-8'),
            ('openrouter', 'anthropic/claude-haiku-4-5-20251001'),
            ('openrouter', 'anthropic/claude-fable-5')
        )
    """))
    op.execute(sa.text("""
        UPDATE model_options SET status = 'healthy'
        WHERE provider = 'openrouter' AND model_id = 'anthropic/claude-sonnet-4-5'
    """))
