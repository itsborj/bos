"""capabilities and model_options tables with seed data

Revision ID: 004_capabilities
Revises: 003_provider_keys
Create Date: 2026-05-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004_capabilities"
down_revision: Union[str, None] = "003_provider_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "capabilities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(255), nullable=False, unique=True),
        sa.Column("modality", sa.String(50), nullable=False),
        sa.Column("budget_ceiling", sa.Float, nullable=False),
        sa.Column("latency_target_ms", sa.Integer, nullable=False),
    )
    op.create_index("ix_capabilities_key", "capabilities", ["key"], unique=True)

    op.create_table(
        "model_options",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "capability_id",
            UUID(as_uuid=True),
            sa.ForeignKey("capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("input_cost_per_token", sa.Float, nullable=False),
        sa.Column("output_cost_per_token", sa.Float, nullable=False),
        sa.Column("quality_tier", sa.String(50), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("availability_score", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("supports_json", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("status", sa.String(50), nullable=False, server_default="healthy"),
    )
    op.create_index("ix_model_options_capability_id", "model_options", ["capability_id"])

    # Seed capabilities
    op.execute(sa.text("""
        INSERT INTO capabilities (key, modality, budget_ceiling, latency_target_ms) VALUES
        ('marketing.copywriting',      'text',  0.10, 8000),
        ('marketing.analysis',         'text',  0.12, 9000),
        ('marketing.image_generation', 'image', 0.25, 12000),
        ('marketing.text_to_speech',   'audio', 0.15, 10000),
        ('marketing.video_editing',    'text',  0.12, 9000)
    """))

    # Seed model options — openrouter text models for copywriting
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openrouter', 'anthropic/claude-3-haiku',
               0.00025, 0.00125, 'medium', 2200, 0.97, false, 'healthy'
        FROM capabilities WHERE key = 'marketing.copywriting'
    """))
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openrouter', 'openai/gpt-4o-mini',
               0.00015, 0.00180, 'high', 2500, 0.98, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.copywriting'
    """))
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openrouter', 'mistralai/mistral-small',
               0.00020, 0.00060, 'low', 1800, 0.95, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.copywriting'
    """))

    # Seed model options — analysis capability
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openrouter', 'anthropic/claude-3-haiku',
               0.00025, 0.00125, 'medium', 2200, 0.97, false, 'healthy'
        FROM capabilities WHERE key = 'marketing.analysis'
    """))
    op.execute(sa.text("""
        INSERT INTO model_options
            (capability_id, provider, model_id, input_cost_per_token, output_cost_per_token,
             quality_tier, latency_ms, availability_score, supports_json, status)
        SELECT id, 'openrouter', 'openai/gpt-4o-mini',
               0.00015, 0.00180, 'high', 2500, 0.98, true, 'healthy'
        FROM capabilities WHERE key = 'marketing.analysis'
    """))


def downgrade() -> None:
    op.drop_index("ix_model_options_capability_id", table_name="model_options")
    op.drop_table("model_options")
    op.drop_index("ix_capabilities_key", table_name="capabilities")
    op.drop_table("capabilities")
