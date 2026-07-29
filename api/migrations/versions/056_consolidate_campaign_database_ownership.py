"""Consolidate Campaign identity and operating-row database ownership.

Revision ID: 056_consolidate_campaign_database_ownership
Revises: 055_drop_creative_assets
"""
from __future__ import annotations

from alembic import op

revision = "056_consolidate_campaign_database_ownership"
down_revision = "055_drop_creative_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve legacy Campaign container fields in a canonical operating row
    # before deleting those competing truth columns from campaigns.
    op.execute(
        """
        INSERT INTO campaign_rows (
          workspace_id, brand_id, campaign_id, campaign, status, objective_id,
          business_objective, period_type, time_period, distribution_channel,
          channel_role, planned_activity, source_health, verification_status,
          objective_verdict, raw_payload
        )
        SELECT
          c.workspace_id, c.brand_id, c.id, c.name, c.status, c.objective_id,
          COALESCE(c.campaign_json->>'business_objective', c.campaign_json->>'objective', c.campaign_json->>'goal'),
          'current', 'current', 'campaign', 'operating_record',
          COALESCE(c.campaign_json->>'initial_intent', c.name),
          'reported', 'producer_reported', 'needs_data',
          jsonb_strip_nulls(jsonb_build_object(
            'audience', c.audience,
            'message_angle', c.message_angle,
            'campaign_json', c.campaign_json
          ))
        FROM campaigns c
        WHERE NOT EXISTS (
          SELECT 1 FROM campaign_rows r
          WHERE r.campaign_id = c.id
            AND (r.distribution_channel = 'campaign' OR r.channel_role = 'operating_record')
        );
        """
    )
    op.execute(
        """
        WITH canonical AS (
          SELECT DISTINCT ON (r.campaign_id) r.id, r.campaign_id
          FROM campaign_rows r
          WHERE r.campaign_id IS NOT NULL
          ORDER BY r.campaign_id,
                   (r.distribution_channel = 'campaign') DESC,
                   r.created_at ASC
        )
        UPDATE campaign_rows r
        SET raw_payload = COALESCE(r.raw_payload, '{}'::jsonb) ||
          jsonb_strip_nulls(jsonb_build_object(
            'audience', c.audience,
            'message_angle', c.message_angle,
            'campaign_json', c.campaign_json
          ))
        FROM canonical x
        JOIN campaigns c ON c.id = x.campaign_id
        WHERE r.id = x.id;
        """
    )

    # Repair any rows created before relational constraints were attached. Keep
    # the evidence row even if its old identity cannot be recovered.
    op.execute(
        """
        INSERT INTO campaigns (id, workspace_id, brand_id, name, status, objective_id)
        SELECT DISTINCT ON (r.campaign_id)
          r.campaign_id,
          r.workspace_id,
          CASE WHEN b.id IS NOT NULL THEN r.brand_id ELSE NULL END,
          COALESCE(NULLIF(r.campaign, ''), 'Recovered Campaign'),
          CASE WHEN r.status IN ('draft', 'active', 'complete', 'archived') THEN r.status ELSE 'active' END,
          CASE WHEN o.id IS NOT NULL THEN r.objective_id ELSE NULL END
        FROM campaign_rows r
        JOIN workspaces w ON w.id = r.workspace_id
        LEFT JOIN brands b ON b.id = r.brand_id
        LEFT JOIN objectives o ON o.id = r.objective_id
        LEFT JOIN campaigns c ON c.id = r.campaign_id
        WHERE r.campaign_id IS NOT NULL AND c.id IS NULL
        ORDER BY r.campaign_id, r.created_at ASC
        ON CONFLICT (id) DO NOTHING;
        """
    )
    op.execute(
        """
        UPDATE campaign_rows r
        SET raw_payload = COALESCE(r.raw_payload, '{}'::jsonb) ||
              jsonb_build_object('orphaned_campaign_id', r.campaign_id::text),
            campaign_id = NULL
        WHERE r.campaign_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM campaigns c WHERE c.id = r.campaign_id);
        """
    )
    op.execute(
        """
        UPDATE campaign_rows r SET workspace_id = NULL
        WHERE r.workspace_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM workspaces w WHERE w.id = r.workspace_id);
        """
    )
    op.execute(
        """
        UPDATE campaign_rows r SET brand_id = NULL
        WHERE r.brand_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM brands b WHERE b.id = r.brand_id);
        """
    )
    op.execute(
        """
        UPDATE campaign_rows r SET objective_id = NULL
        WHERE r.objective_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM objectives o WHERE o.id = r.objective_id);
        """
    )
    op.execute(
        """
        UPDATE campaign_rows r SET superseded_by_id = NULL
        WHERE r.superseded_by_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM campaign_rows n WHERE n.id = r.superseded_by_id);
        """
    )

    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS audience")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS message_angle")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS campaign_json")

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_campaign_rows_workspace') THEN
            ALTER TABLE campaign_rows ADD CONSTRAINT fk_campaign_rows_workspace
              FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_campaign_rows_brand') THEN
            ALTER TABLE campaign_rows ADD CONSTRAINT fk_campaign_rows_brand
              FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_campaign_rows_campaign') THEN
            ALTER TABLE campaign_rows ADD CONSTRAINT fk_campaign_rows_campaign
              FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_campaign_rows_objective') THEN
            ALTER TABLE campaign_rows ADD CONSTRAINT fk_campaign_rows_objective
              FOREIGN KEY (objective_id) REFERENCES objectives(id) ON DELETE SET NULL;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_campaign_rows_superseded_by') THEN
            ALTER TABLE campaign_rows ADD CONSTRAINT fk_campaign_rows_superseded_by
              FOREIGN KEY (superseded_by_id) REFERENCES campaign_rows(id) ON DELETE SET NULL;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE campaign_rows DROP CONSTRAINT IF EXISTS fk_campaign_rows_superseded_by")
    op.execute("ALTER TABLE campaign_rows DROP CONSTRAINT IF EXISTS fk_campaign_rows_objective")
    op.execute("ALTER TABLE campaign_rows DROP CONSTRAINT IF EXISTS fk_campaign_rows_campaign")
    op.execute("ALTER TABLE campaign_rows DROP CONSTRAINT IF EXISTS fk_campaign_rows_brand")
    op.execute("ALTER TABLE campaign_rows DROP CONSTRAINT IF EXISTS fk_campaign_rows_workspace")
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS audience VARCHAR(255)")
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS message_angle VARCHAR(255)")
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS campaign_json JSONB")
