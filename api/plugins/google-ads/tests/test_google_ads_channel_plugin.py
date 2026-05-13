from __future__ import annotations

import importlib.util
from pathlib import Path

from registry import list_all
from skills.router import route_chat_skills


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DRAFT_MODULE_PATH = PLUGIN_ROOT / "capabilities/marketing/channel/google_ads/search_text/draft/module.py"

READ_CAPABILITY = "marketing.channel.google_ads.performance.read"
DRAFT_CAPABILITY = "marketing.channel.google_ads.search_text.draft"


def _draft_module_class():
    spec = importlib.util.spec_from_file_location("google_ads_search_text_draft_module", DRAFT_MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GoogleAdsSearchTextDraftModule


def test_google_ads_copy_request_routes_to_draft_not_data_pull():
    list_all()

    routed = route_chat_skills("can you generate a google ads copy")

    assert DRAFT_CAPABILITY in routed.module_ids
    assert READ_CAPABILITY not in routed.module_ids


def test_show_google_ads_still_routes_to_read_only_data_pull():
    list_all()

    routed = route_chat_skills("show me google ads")

    assert READ_CAPABILITY in routed.module_ids
    assert DRAFT_CAPABILITY not in routed.module_ids


def test_google_ads_draft_module_returns_native_artifact_block():
    module = _draft_module_class()()

    attempt, result = module.execute_tool_result({
        "brand_name": "MotorMoto",
        "product_name": "Motorcycles",
        "audience": "everyday riders",
        "key_benefit": "dependable mobility",
        "domain": "motormoto.example",
    })
    verdict, failures = module.self_check(result["content"], {})

    assert attempt["provider"] == "google_ads_plugin"
    assert result["block"]["type"] == "google_search_ad_draft"
    assert result["block"]["format"] == "responsive_search_ad"
    assert result["block"]["changed_resources"] == []
    assert result["block"]["risk_level"] == "requires_approval"
    assert len(result["block"]["headlines"]) >= 10
    assert len(result["block"]["descriptions"]) >= 4
    assert all(len(item["text"]) <= 30 for item in result["block"]["headlines"])
    assert all(len(item["text"]) <= 90 for item in result["block"]["descriptions"])
    assert verdict == "pass"
    assert failures == []
