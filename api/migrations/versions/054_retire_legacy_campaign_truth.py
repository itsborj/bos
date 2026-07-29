"""Retire legacy Campaign truth stores

Revision ID: 054_retire_legacy_campaign_truth
Revises: 053_campaign_snapshots
Create Date: 2026-07-15
"""

from typing import Union

from alembic import op

revision: str = "054_retire_legacy_campaign_truth"
down_revision: Union[str, None] = "053_campaign_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Campaign V2 is database-first. Create the canonical operating table in the
    # Alembic chain before migrating legacy snapshots into it.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_rows (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          workspace_id UUID CONSTRAINT fk_campaign_rows_workspace REFERENCES workspaces(id) ON DELETE CASCADE,
          brand_id UUID CONSTRAINT fk_campaign_rows_brand REFERENCES brands(id) ON DELETE SET NULL,
          brand VARCHAR(255),
          campaign_id UUID CONSTRAINT fk_campaign_rows_campaign REFERENCES campaigns(id) ON DELETE CASCADE,
          campaign VARCHAR(255),
          status VARCHAR(50) NOT NULL DEFAULT 'active',
          objective_id UUID CONSTRAINT fk_campaign_rows_objective REFERENCES objectives(id) ON DELETE SET NULL,
          business_objective TEXT,
          success_metric TEXT,
          target TEXT,
          baseline TEXT,
          current_value TEXT,
          primary_kpi TEXT,
          actual TEXT,
          period_type VARCHAR(32),
          time_period VARCHAR(64),
          period_start TIMESTAMPTZ,
          period_end TIMESTAMPTZ,
          distribution_channel VARCHAR(128),
          channel_role VARCHAR(128),
          market TEXT,
          planned_activity TEXT,
          actual_activity TEXT,
          reach INTEGER,
          impressions INTEGER,
          engagement INTEGER,
          engagement_rate DOUBLE PRECISION,
          reach_metric TEXT,
          engagement_metric TEXT,
          action_metric TEXT,
          efficiency_metric TEXT,
          value_metric TEXT,
          clicks INTEGER,
          leads INTEGER,
          calls INTEGER,
          qualified_calls INTEGER,
          conversions INTEGER,
          spend NUMERIC(12, 2),
          budget NUMERIC(12, 2),
          revenue NUMERIC(12, 2),
          source_health VARCHAR(32) NOT NULL DEFAULT 'reported',
          freshness VARCHAR(32),
          verification_status VARCHAR(32) NOT NULL DEFAULT 'producer_reported',
          objective_verdict VARCHAR(32) NOT NULL DEFAULT 'inconclusive',
          confidence VARCHAR(32),
          what_changed TEXT,
          top_learning TEXT,
          recommended_action TEXT,
          note TEXT,
          blocker TEXT,
          decision_needed TEXT,
          owner VARCHAR(255),
          next_action TEXT,
          due_date TIMESTAMPTZ,
          source_type VARCHAR(64),
          source_ref VARCHAR(255),
          producer VARCHAR(255),
          evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          superseded_at TIMESTAMPTZ,
          superseded_by_id UUID CONSTRAINT fk_campaign_rows_superseded_by REFERENCES campaign_rows(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    for sql in (
        "CREATE INDEX IF NOT EXISTS ix_campaign_rows_brand_date ON campaign_rows (brand_id, period_start DESC)",
        "CREATE INDEX IF NOT EXISTS ix_campaign_rows_campaign_date ON campaign_rows (campaign_id, period_start DESC)",
        "CREATE INDEX IF NOT EXISTS ix_campaign_rows_objective_date ON campaign_rows (objective_id, period_start DESC)",
        "CREATE INDEX IF NOT EXISTS ix_campaign_rows_channel_date ON campaign_rows (distribution_channel, period_start DESC)",
        "CREATE INDEX IF NOT EXISTS ix_campaign_rows_period_type ON campaign_rows (period_type)",
        "CREATE INDEX IF NOT EXISTS ix_campaign_rows_verification ON campaign_rows (verification_status)",
        "CREATE INDEX IF NOT EXISTS ix_campaign_rows_verdict ON campaign_rows (objective_verdict)",
    ):
        op.execute(sql)
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.campaign_snapshots') IS NOT NULL THEN
            INSERT INTO campaign_rows (
              workspace_id, brand_id, brand, campaign_id, campaign, objective_id,
              period_type, time_period, period_start, period_end,
              distribution_channel, channel_role, planned_activity, actual_activity,
              reach, impressions, engagement, engagement_rate, clicks, leads, calls,
              qualified_calls, conversions, spend, revenue,
              source_health, freshness, verification_status, objective_verdict,
              confidence, what_changed, blocker, decision_needed, owner, next_action,
              source_type, source_ref, producer, evidence_refs, raw_payload,
              created_at, updated_at, status
            )
            SELECT
              s.workspace_id, s.brand_id, b.name, s.campaign_id, c.name, s.objective_id,
              'legacy_snapshot', s.time_period, s.period_start, s.period_end,
              s.distribution_channel, s.channel_role, s.planned_activity, s.actual_activity,
              s.reach, s.impressions, s.engagement, s.engagement_rate, s.clicks, s.leads, s.calls,
              s.qualified_calls, s.conversions, s.spend, s.revenue,
              s.source_health, s.freshness, s.verification_status, s.objective_verdict,
              s.confidence, COALESCE(s.what_changed, 'Migrated from retired campaign_snapshots table.'),
              s.blocker, s.decision_needed, s.owner, s.next_action,
              COALESCE(s.source_type, 'legacy.campaign_snapshots'), s.source_ref,
              COALESCE(s.producer, 'legacy_migration'),
              COALESCE(s.evidence_refs, '[]'::jsonb) || jsonb_build_array(jsonb_build_object('kind', 'legacy_campaign_snapshot', 'id', s.id::text)),
              COALESCE(s.raw_payload, '{}'::jsonb) || jsonb_build_object('legacy_snapshot_id', s.id::text),
              s.created_at, s.updated_at, COALESCE(c.status, 'active')
            FROM campaign_snapshots s
            LEFT JOIN brands b ON b.id = s.brand_id
            LEFT JOIN campaigns c ON c.id = s.campaign_id
            WHERE NOT EXISTS (
              SELECT 1 FROM campaign_rows r
              WHERE r.raw_payload->>'legacy_snapshot_id' = s.id::text
                 OR r.evidence_refs::text LIKE '%' || s.id::text || '%'
            );
          END IF;
        END $$;
        """
    )
    # Preserve legacy result rows as dated Campaign evidence before removing the
    # competing result table.
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.campaign_results') IS NOT NULL THEN
            INSERT INTO campaign_rows (
              workspace_id, brand_id, campaign_id, campaign, status,
              period_type, time_period, distribution_channel, channel_role,
              impressions, engagement_rate, clicks, conversions,
              efficiency_metric, source_health, verification_status,
              objective_verdict, source_type, source_ref, producer,
              evidence_refs, raw_payload, created_at, updated_at
            )
            SELECT
              c.workspace_id, c.brand_id, c.id, c.name, c.status,
              'legacy_result', COALESCE(cr.week, cr.quarter, 'legacy'),
              'legacy_campaign_result', 'performance_evidence',
              cr.impressions, cr.engagement_rate, cr.clicks, cr.conversions,
              CASE WHEN cr.cpa IS NOT NULL THEN 'CPA ' || cr.cpa::text ELSE NULL END,
              'reported', 'producer_reported',
              CASE WHEN cr.impressions IS NULL AND cr.clicks IS NULL AND cr.conversions IS NULL
                   THEN 'needs_data' ELSE 'inconclusive' END,
              'legacy.campaign_results', 'campaign_result:' || cr.id::text,
              'legacy_migration',
              jsonb_build_array(jsonb_build_object('kind', 'legacy_campaign_result', 'id', cr.id::text)),
              jsonb_strip_nulls(jsonb_build_object(
                'legacy_campaign_result_id', cr.id::text,
                'week', cr.week,
                'quarter', cr.quarter,
                'message_angle', cr.message_angle,
                'cpa', cr.cpa
              )),
              cr.created_at, cr.created_at
            FROM campaign_results cr
            JOIN campaigns c ON c.id = cr.campaign_id
            WHERE NOT EXISTS (
              SELECT 1 FROM campaign_rows r
              WHERE r.raw_payload->>'legacy_campaign_result_id' = cr.id::text
            );
          END IF;
        END $$;
        """
    )

    # Preserve activation windows, channel declarations, and run lineage as
    # Campaign evidence rows before deleting the old activation layer.
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.campaign_activations') IS NOT NULL THEN
            INSERT INTO campaign_rows (
              workspace_id, brand_id, campaign_id, campaign, status,
              period_type, time_period, period_start, period_end,
              distribution_channel, channel_role, planned_activity,
              source_health, verification_status, objective_verdict,
              source_type, source_ref, producer, evidence_refs, raw_payload,
              created_at, updated_at
            )
            SELECT
              a.workspace_id, a.brand_id, a.campaign_id, c.name, c.status,
              'legacy_activation', a.name, a.starts_at, a.ends_at,
              'multi_channel', 'activation_evidence', a.name,
              'reported', 'producer_reported', 'needs_data',
              'legacy.campaign_activations', 'campaign_activation:' || a.id::text,
              'legacy_migration',
              jsonb_build_array(jsonb_build_object('kind', 'legacy_campaign_activation', 'id', a.id::text)),
              jsonb_strip_nulls(jsonb_build_object(
                'legacy_campaign_activation_id', a.id::text,
                'channels', a.channels,
                'run_ids', (
                  SELECT COALESCE(jsonb_agg(r.id::text), '[]'::jsonb)
                  FROM runs r WHERE r.activation_id = a.id
                )
              )),
              a.created_at, a.updated_at
            FROM campaign_activations a
            JOIN campaigns c ON c.id = a.campaign_id
            WHERE NOT EXISTS (
              SELECT 1 FROM campaign_rows r
              WHERE r.raw_payload->>'legacy_campaign_activation_id' = a.id::text
            );
          END IF;
        END $$;
        """
    )

    # Preserve the removed Campaign memory snapshot as historical evidence, not
    # as controlling current truth.
    op.execute(
        """
        INSERT INTO campaign_rows (
          workspace_id, brand_id, campaign_id, campaign, status,
          period_type, time_period, period_start, distribution_channel,
          channel_role, source_health, verification_status, objective_verdict,
          source_type, source_ref, producer, evidence_refs, raw_payload
        )
        SELECT
          c.workspace_id, c.brand_id, c.id, c.name, c.status,
          'legacy_memory', 'legacy_memory_snapshot', c.memory_snapshot_at,
          'legacy_memory', 'historical_evidence',
          'reported', 'unverified', 'needs_data',
          'legacy.campaign_memory_snapshot', 'campaign_memory_snapshot:' || c.id::text,
          'legacy_migration',
          jsonb_build_array(jsonb_build_object('kind', 'legacy_campaign_memory_snapshot', 'campaign_id', c.id::text)),
          jsonb_build_object('legacy_memory_snapshot', c.memory_snapshot)
        FROM campaigns c
        WHERE c.memory_snapshot IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM campaign_rows r
            WHERE r.raw_payload ? 'legacy_memory_snapshot'
              AND r.campaign_id = c.id
          );
        """
    )

    # Daily briefs had no reliable campaign binding. Preserve them as brand-level
    # audit evidence rather than assigning them to a Campaign or retaining them
    # as a truth surface.
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.daily_briefs') IS NOT NULL THEN
            INSERT INTO memory_events (
              id, workspace_id, brand_id, event_type, topic_tags, summary,
              source_ref, full_record, timestamp
            )
            SELECT
              gen_random_uuid(), d.workspace_id, d.brand_id, 'artifact_created',
              '["legacy_daily_brief"]'::jsonb,
              'Historical daily brief preserved during Campaign V2 cutover.',
              'legacy_daily_brief:' || d.id::text,
              jsonb_build_object(
                'legacy_daily_brief_id', d.id::text,
                'payload_type', d.payload_type,
                'payload', d.payload
              ),
              d.generated_at
            FROM daily_briefs d
            WHERE NOT EXISTS (
              SELECT 1 FROM memory_events m
              WHERE m.source_ref = 'legacy_daily_brief:' || d.id::text
            );
          END IF;
        END $$;
        """
    )

    op.execute("DROP TABLE IF EXISTS campaign_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS campaign_activations CASCADE")
    op.execute("DROP TABLE IF EXISTS daily_briefs CASCADE")
    op.execute("DROP TABLE IF EXISTS campaign_results CASCADE")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS memory_snapshot")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS memory_snapshot_at")
    op.execute("ALTER TABLE runs DROP COLUMN IF EXISTS activation_id")


def downgrade() -> None:
    # Irreversible cleanup. Historical data is retained in campaign_rows before drop.
    pass
