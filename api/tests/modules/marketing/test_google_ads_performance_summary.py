from __future__ import annotations

from capabilities.marketing.channel.google.paid_search.analytics.performance_summary.module import (
    GooglePaidSearchPerformanceSummaryModule,
)
from providers.google_ads_mock import MockGoogleAdsConnector, weekly_performance_summary


def test_mock_connector_lists_accessible_customers() -> None:
    connector = MockGoogleAdsConnector()

    customers = connector.list_accessible_customers()

    assert customers[0]["customer_id"] == "1234567890"
    assert customers[0]["name"] == "Klaroha Demo Ads"


def test_weekly_performance_summary_totals_fixture_data() -> None:
    summary = weekly_performance_summary()

    assert summary["metrics"]["spend"] == 842.38
    assert summary["metrics"]["clicks"] == 2711
    assert summary["metrics"]["conversions"] == 61
    assert summary["metrics"]["cpa"] == 13.81
    assert len(summary["campaigns"]) == 2


def test_tool_module_outputs_performance_report_block() -> None:
    module = GooglePaidSearchPerformanceSummaryModule()

    attempt, result = module.execute_tool_result({})
    verdict, failures = module.self_check(result["content"], {})

    assert attempt["provider"] == "google_ads_mcp"
    assert attempt["mode"] == "mock"
    assert result["block"]["type"] == "performance_report"
    assert result["block"]["title"] == "Google Ads Performance — Last 7 Days"
    assert result["block"]["source"]["connector"] == "mock_google_ads_mcp"
    assert verdict == "pass"
    assert failures == []
