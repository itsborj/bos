from __future__ import annotations

import json

from capabilities.marketing.channel.google.paid_search.write.campaign_draft.module import (
    GooglePaidSearchCampaignDraftModule,
)


def test_campaign_draft_uses_user_requested_entities_without_hardcoding() -> None:
    module = GooglePaidSearchCampaignDraftModule()
    _, result = module.execute_tool_result({
        "brand_name": "Example Brand",
        "conversation_context": "USER: lets create two new campaigns for plumbers and another one for accountants\nUSER: google ads",
    })
    payload = json.loads(result["content"][result["content"].index("{"):])

    names = [campaign["name"] for campaign in payload["campaigns"]]
    assert "Search | Plumbers | Lead Gen" in names
    assert "Search | Accountants | Lead Gen" in names
    assert all(campaign["status"] == "PAUSED" for campaign in payload["campaigns"])
    assert payload["cep_required_for_live_push"] is True


def test_campaign_draft_validates_rsa_limits() -> None:
    module = GooglePaidSearchCampaignDraftModule()
    _, result = module.execute_tool_result({"conversation_context": "USER: create google ads campaigns for local dentists"})

    verdict, failures = module.self_check(result["content"], {})

    assert verdict == "pass"
    assert failures == []
