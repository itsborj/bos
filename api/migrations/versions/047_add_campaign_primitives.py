"""Add campaign primitives and results table

Revision ID: 047_add_campaign_primitives
Revises: 046_update_claude_models
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by alembic.
revision: str = '047_add_campaign_primitives'
down_revision: Union[str, None] = '046_update_claude_models'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add objective_id to campaigns
    op.add_column('campaigns', sa.Column('objective_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_campaigns_objective',
        'campaigns', 'objectives',
        ['objective_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add campaign primitives to campaigns table
    op.add_column('campaigns', sa.Column('audience', sa.String(255), nullable=True))
    op.add_column('campaigns', sa.Column('message_angle', sa.String(255), nullable=True))
    op.add_column('campaigns', sa.Column('campaign_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Create campaign_results table
    op.create_table(
        'campaign_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('week', sa.String(7), nullable=True),  # "2024-W02"
        sa.Column('quarter', sa.String(7), nullable=True),  # "2024-Q1"
        sa.Column('message_angle', sa.String(255), nullable=True),
        sa.Column('impressions', sa.Integer(), nullable=True),
        sa.Column('engagement_rate', sa.Float(), nullable=True),
        sa.Column('clicks', sa.Integer(), nullable=True),
        sa.Column('conversions', sa.Integer(), nullable=True),
        sa.Column('cpa', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_campaign_results_campaign_id', 'campaign_results', ['campaign_id'])
    op.create_index('ix_campaign_results_week', 'campaign_results', ['week'])
    op.create_index('ix_campaign_results_quarter', 'campaign_results', ['quarter'])


def downgrade() -> None:
    op.drop_index('ix_campaign_results_quarter', table_name='campaign_results')
    op.drop_index('ix_campaign_results_week', table_name='campaign_results')
    op.drop_index('ix_campaign_results_campaign_id', table_name='campaign_results')
    op.drop_table('campaign_results')

    op.drop_column('campaigns', 'campaign_json')
    op.drop_column('campaigns', 'message_angle')
    op.drop_column('campaigns', 'audience')
    op.drop_column('campaigns', 'objective_id')
    op.drop_constraint('fk_campaigns_objective', 'campaigns')
