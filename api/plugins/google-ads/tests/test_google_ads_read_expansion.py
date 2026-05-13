from __future__ import annotations

import importlib.util
from pathlib import Path

from registry import list_all
from skills.router import route_chat_skills


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_MODULE_PATH = PLUGIN_ROOT / "capabilities/marketing/channel/google_ads/account/discover/module.py"
CAMPAIGNS_MODULE_PATH = PLUGIN_ROOT / "capabilities/marketing/channel/google_ads/campaigns/read/module.py"

ACCOUNT_CAPABILITY = "marketing.channel.google_ads.account.discover"
CAMPAIGNS_CAPABILITY = "marketing.channel.google_ads.campaigns.read"
PERFORMANCE_CAPABILITY = "marketing.channel.google_ads.performance.read"


def _module_class(path: Path, module_name: str, class_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def _account_module():
    return _module_class(ACCOUNT_MODULE_PATH, "google_ads_account_discover_module", "GoogleAdsAccountDiscoverModule")()


def _campaigns_module():
    return _module_class(CAMPAIGNS_MODULE_PATH, "google_ads_campaigns_read_module", "GoogleAdsCampaignsReadModule")()


def test_google_ads_account_discovery_routes_without_campaign_or_performance_read():
    list_all()

    routed = route_chat_skills("list google ads accounts")

    assert ACCOUNT_CAPABILITY in routed.module_ids
    assert CAMPAIGNS_CAPABILITY not in routed.module_ids
    assert PERFORMANCE_CAPABILITY not in routed.module_ids


def test_google_ads_campaign_list_routes_to_campaign_report_not_generic_performance():
    list_all()

    routed = route_chat_skills("list google ads campaigns")

    assert CAMPAIGNS_CAPABILITY in routed.module_ids
    assert ACCOUNT_CAPABILITY not in routed.module_ids
    assert PERFORMANCE_CAPABILITY not in routed.module_ids


def test_account_inventory_parser_returns_read_only_account_rows():
    module = _account_module()

    accounts = module._accessible_accounts({"resourceNames": ["customers/123-456-7890", "customers/987318670"]})
    content = module._content(accounts, "1234567890")
    verdict, failures = module.self_check(content, {})

    assert accounts[0]["customer_id"] == "1234567890"
    assert accounts[1]["customer_id"] == "0987318670"
    assert "Read-only note" in content
    assert verdict == "pass"
    assert failures == []


def test_campaign_report_parser_returns_totals_and_no_changed_resources_shape():
    module = _campaigns_module()
    response = [
        {
            "results": [
                {
                    "campaign": {"id": "111", "name": "Brand Search", "status": "ENABLED", "advertisingChannelType": "SEARCH"},
                    "campaignBudget": {"amountMicros": "50000000"},
                    "metrics": {
                        "impressions": "1000",
                        "clicks": "100",
                        "costMicros": "200000000",
                        "conversions": "10",
                        "averageCpc": "2000000",
                    },
                },
                {
                    "campaign": {"id": "222", "name": "Generic Search", "status": "ENABLED", "advertisingChannelType": "SEARCH"},
                    "campaignBudget": {"amountMicros": "75000000"},
                    "metrics": {
                        "impressions": "500",
                        "clicks": "25",
                        "costMicros": "75000000",
                        "conversions": "0",
                        "averageCpc": "3000000",
                    },
                },
            ]
        }
    ]

    rows = module._campaign_rows(response)
    totals = module._totals(rows)
    content = module._content("1234567890", "LAST_30_DAYS", rows, totals)
    verdict, failures = module.self_check(content, {})

    assert rows[0]["campaign_id"] == "111"
    assert rows[0]["daily_budget"] == 50.0
    assert rows[0]["cpa"] == 20.0
    assert rows[0]["flag"] == "efficient"
    assert rows[1]["flag"] == "waste_risk"
    assert totals == {
        "impressions": 1500,
        "clicks": 125,
        "cost": 275.0,
        "conversions": 10.0,
        "ctr": 8.33,
        "cpa": 27.5,
    }
    assert "Read-only note" in content
    assert verdict == "pass"
    assert failures == []
