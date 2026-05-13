"""intent_contracts, campaign_intents, module_criteria tables

Revision ID: 009_intent_contracts
Revises: 008_gemini_flash_quality
Create Date: 2026-05-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "009_intent_contracts"
down_revision: Union[str, None] = "008_gemini_flash_quality"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "intent_contracts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("contract_type", sa.String(100), nullable=False, server_default="campaign"),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0.0"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("evaluator", sa.String(100), nullable=True),
        sa.Column("criteria_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("scoring_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("on_pass", sa.String(50), nullable=False, server_default="advance"),
        sa.Column("on_fail", sa.String(50), nullable=False, server_default="retry"),
        sa.Column("on_escalate", sa.String(100), nullable=True),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_intent_contracts_contract_type", "intent_contracts", ["contract_type"])

    op.create_table(
        "campaign_intents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "intent_contract_id",
            UUID(as_uuid=True),
            sa.ForeignKey("intent_contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overrides_json", JSONB, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaign_intents_campaign_id", "campaign_intents", ["campaign_id"])
    op.create_index("ix_campaign_intents_active", "campaign_intents", ["active"])

    op.create_table(
        "module_criteria",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("module_id", sa.String(255), nullable=False),
        sa.Column("criterion_id", sa.String(100), nullable=False),
        sa.Column("field", sa.String(255), nullable=False),
        sa.Column("rule", sa.String(100), nullable=False),
        sa.Column("threshold_json", JSONB, nullable=True),
        sa.Column("type", sa.String(20), nullable=False, server_default="soft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_module_criteria_module_id", "module_criteria", ["module_id"])


def downgrade() -> None:
    op.drop_index("ix_module_criteria_module_id", table_name="module_criteria")
    op.drop_table("module_criteria")
    op.drop_index("ix_campaign_intents_active", table_name="campaign_intents")
    op.drop_index("ix_campaign_intents_campaign_id", table_name="campaign_intents")
    op.drop_table("campaign_intents")
    op.drop_index("ix_intent_contracts_contract_type", table_name="intent_contracts")
    op.drop_table("intent_contracts")
