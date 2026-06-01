"""Update model catalog: add free OpenRouter models + top paid models per provider; deprecate outdated entries

Revision ID: 035_update_model_catalog
Revises: 034_creative_supply_chain
Create Date: 2026-06-01

Pricing reference (per 1M tokens):
  FREE via OpenRouter (input = output = $0.00):
    meta-llama/llama-3.3-70b-instruct:free  — Llama 3.3 70B, latest, high quality
    meta-llama/llama-3.1-70b-instruct:free  — Llama 3.1 70B, previous generation
    meta-llama/llama-3.1-8b-instruct:free   — Llama 3.1 8B, fastest free option
    deepseek/deepseek-r1:free               — DeepSeek R1, reasoning-capable
    qwen/qwen-2.5-72b-instruct:free         — Qwen 2.5 72B
    google/gemma-2-27b-it:free              — Gemma 2 27B
    google/gemma-2-9b-it:free               — Gemma 2 9B, faster
    mistralai/mistral-7b-instruct:free      — Mistral 7B

  PAID via OpenRouter:
    anthropic/claude-sonnet-4-5:  $3.00 in / $15.00 out
    openai/gpt-4o:                $5.00 in / $15.00 out
    google/gemini-2.5-pro:        $1.25 in / $10.00 out

  PAID direct providers:
    gemini-2.5-pro:               $1.25 in / $10.00 out
    gemini-2.5-flash:             $0.15 in / $0.60 out
    gemini-2.0-flash:             $0.10 in / $0.40 out  (existing, kept)
    gpt-4o (OpenAI):              $5.00 in / $15.00 out
    gpt-4o-mini (OpenAI):         $0.15 in / $0.60 out
    nvidia/llama-3.1-nemotron-70b: $0.20 in / $0.20 out
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035_update_model_catalog"
down_revision: Union[str, None] = "034_creative_supply_chain"
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
    # ── FREE OpenRouter models (input_cost = output_cost = 0) ─────────────────
    # DeepSeek R1 — reasoning-capable, latest, recommended free choice
    for cap in _CAPS:
        _insert(cap, "openrouter", "deepseek/deepseek-r1:free",
                0.0, 0.0, "high", 4500, 0.92, True)

    # Llama 3.3 70B — latest Llama, high quality
    for cap in _CAPS:
        _insert(cap, "openrouter", "meta-llama/llama-3.3-70b-instruct:free",
                0.0, 0.0, "high", 3500, 0.94, True)

    # Llama 3.1 70B — previous version
    for cap in _CAPS:
        _insert(cap, "openrouter", "meta-llama/llama-3.1-70b-instruct:free",
                0.0, 0.0, "high", 3800, 0.93, True)

    # Llama 3.1 8B — fast, lighter
    for cap in _CAPS:
        _insert(cap, "openrouter", "meta-llama/llama-3.1-8b-instruct:free",
                0.0, 0.0, "medium", 1800, 0.95, True)

    # Qwen 2.5 72B
    for cap in _CAPS:
        _insert(cap, "openrouter", "qwen/qwen-2.5-72b-instruct:free",
                0.0, 0.0, "high", 3200, 0.91, True)

    # Gemma 2 27B — Google's open model, larger
    for cap in _CAPS:
        _insert(cap, "openrouter", "google/gemma-2-27b-it:free",
                0.0, 0.0, "medium", 2800, 0.92, True)

    # Gemma 2 9B — Google's open model, faster
    for cap in _CAPS:
        _insert(cap, "openrouter", "google/gemma-2-9b-it:free",
                0.0, 0.0, "medium", 1900, 0.93, True)

    # Mistral 7B
    for cap in _CAPS:
        _insert(cap, "openrouter", "mistralai/mistral-7b-instruct:free",
                0.0, 0.0, "medium", 1600, 0.94, True)

    # ── Gemini 2.5 Pro (flagship, thinking-capable) ───────────────────────────
    for cap in _CAPS:
        _insert(cap, "gemini", "gemini-2.5-pro",
                0.001250, 0.010000, "high", 4000, 0.96, True)

    # ── Gemini 2.5 Flash (fast + efficient) ──────────────────────────────────
    for cap in _CAPS:
        _insert(cap, "gemini", "gemini-2.5-flash",
                0.000150, 0.000600, "medium", 2000, 0.97, True)

    # ── OpenRouter: Claude Sonnet 4.5 (latest Anthropic via proxy) ────────────
    for cap in _CAPS:
        _insert(cap, "openrouter", "anthropic/claude-sonnet-4-5",
                0.003000, 0.015000, "high", 2500, 0.97, True)

    # ── OpenRouter: GPT-4o (latest OpenAI via proxy) ─────────────────────────
    for cap in _CAPS:
        _insert(cap, "openrouter", "openai/gpt-4o",
                0.005000, 0.015000, "high", 2800, 0.98, True)

    # ── OpenRouter: Google Gemini 2.5 Pro via proxy ───────────────────────────
    for cap in _CAPS:
        _insert(cap, "openrouter", "google/gemini-2.5-pro",
                0.001250, 0.010000, "high", 3500, 0.96, True)

    # ── OpenAI direct: GPT-4o ─────────────────────────────────────────────────
    for cap in _CAPS:
        _insert(cap, "openai", "gpt-4o",
                0.005000, 0.015000, "high", 2800, 0.98, True)

    # ── OpenAI direct: GPT-4o Mini ────────────────────────────────────────────
    for cap in _CAPS:
        _insert(cap, "openai", "gpt-4o-mini",
                0.000150, 0.000600, "medium", 1800, 0.98, True)

    # ── NVIDIA: Llama 3.1 Nemotron 70B (reasoning-focused) ───────────────────
    for cap in _CAPS:
        _insert(cap, "nvidia", "nvidia/llama-3.1-nemotron-70b-instruct",
                0.000200, 0.000200, "high", 2500, 0.95, True)

    # ── Deprecate outdated entries ────────────────────────────────────────────
    op.execute(sa.text("""
        UPDATE model_options SET status = 'deprecated'
        WHERE provider = 'gemini' AND model_id = 'gemini-1.5-pro'
    """))
    op.execute(sa.text("""
        UPDATE model_options SET status = 'deprecated'
        WHERE provider = 'openrouter' AND model_id = 'anthropic/claude-3-haiku'
    """))
    op.execute(sa.text("""
        UPDATE model_options SET status = 'deprecated'
        WHERE provider = 'openrouter' AND model_id = 'mistralai/mistral-small'
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM model_options
        WHERE (provider, model_id) IN (
            ('openrouter', 'deepseek/deepseek-r1:free'),
            ('openrouter', 'meta-llama/llama-3.3-70b-instruct:free'),
            ('openrouter', 'meta-llama/llama-3.1-70b-instruct:free'),
            ('openrouter', 'meta-llama/llama-3.1-8b-instruct:free'),
            ('openrouter', 'qwen/qwen-2.5-72b-instruct:free'),
            ('openrouter', 'google/gemma-2-27b-it:free'),
            ('openrouter', 'google/gemma-2-9b-it:free'),
            ('openrouter', 'mistralai/mistral-7b-instruct:free'),
            ('gemini',      'gemini-2.5-pro'),
            ('gemini',      'gemini-2.5-flash'),
            ('openrouter',  'anthropic/claude-sonnet-4-5'),
            ('openrouter',  'openai/gpt-4o'),
            ('openrouter',  'google/gemini-2.5-pro'),
            ('openai',      'gpt-4o'),
            ('openai',      'gpt-4o-mini'),
            ('nvidia',      'nvidia/llama-3.1-nemotron-70b-instruct')
        )
    """))
    op.execute(sa.text("""
        UPDATE model_options SET status = 'healthy'
        WHERE provider = 'gemini' AND model_id = 'gemini-1.5-pro'
    """))
    op.execute(sa.text("""
        UPDATE model_options SET status = 'healthy'
        WHERE provider = 'openrouter' AND model_id IN ('anthropic/claude-3-haiku', 'mistralai/mistral-small')
    """))
