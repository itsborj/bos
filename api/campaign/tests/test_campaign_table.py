from campaign.table import CampaignRow


def test_campaign_row_is_dated_operating_table():
    columns = CampaignRow.__table__.columns
    for name in (
        "brand_id",
        "campaign_id",
        "objective_id",
        "period_type",
        "period_start",
        "period_end",
        "distribution_channel",
        "market",
        "primary_kpi",
        "actual",
        "reach_metric",
        "engagement_metric",
        "action_metric",
        "efficiency_metric",
        "value_metric",
        "top_learning",
        "recommended_action",
        "note",
        "source_health",
        "verification_status",
        "objective_verdict",
        "evidence_refs",
    ):
        assert name in columns


def test_metrics_are_nullable_not_fake_zero():
    columns = CampaignRow.__table__.columns
    for name in ("reach", "clicks", "leads", "calls", "qualified_calls", "conversions", "spend", "revenue"):
        assert columns[name].nullable is True
