from __future__ import annotations

from pathlib import Path

from capabilities.marketing.plan.campaign_strategy.module import MarketingCampaignStrategyPlanModule
from skills.loader import list_skill_manifests


SAMPLE_CONTENT = """# MotorMoto Plan

## Campaign theme
Dependable mobility for everyday riders.

## Mission
Become the trusted choice for everyday riders who need practical, reliable mobility.

## Focus
1. Demand capture
2. Trust proof
3. Local search readiness

## Recommended channels
- Email — Active — nurture warm leads — existing contacts can convert before paid spend
- GBP — Active — local proof + discovery — useful for branded and local intent
- Google Ads — Hold — capture demand — budget is not loaded yet

## Not recommended yet
- X/Twitter — no clear demand signal
- LinkedIn — only if B2B partnerships matter

## Missing inputs
- Monthly budget — unlocks paid channel activation
- Current lead source — unlocks channel prioritization
- Top offer — unlocks sharper draft artifacts

## Next artifacts
- Email campaign plan — nurture sequence
- GBP post draft — local proof

## Approval note
This is a draft plan for review; execution artifacts and external actions require separate approval.
"""


def test_campaign_strategy_retired_not_in_active_manifests() -> None:
    # campaign_strategy retired in favour of marketing.planning.gtm_plan.
    # Must be absent from both the skill loader and the dispatchable manifest.
    from capability_manifest import build_dispatchable_manifest
    manifest_ids = {e.module_id for e in build_dispatchable_manifest()}
    skill_ids = {s.id for s in list_skill_manifests()}
    assert "marketing.plan.campaign_strategy" not in manifest_ids
    assert "marketing.plan.campaign_strategy" not in skill_ids


def test_marketing_planning_module_self_check_and_block() -> None:
    module = MarketingCampaignStrategyPlanModule()

    verdict, failures = module.self_check(SAMPLE_CONTENT, {"brand_name": "MotorMoto"})
    block = module._build_block(SAMPLE_CONTENT)

    assert verdict == "pass"
    assert failures == []
    assert block["type"] == "marketing_plan"
    assert block["artifact_type"] == "plan_artifact"
    assert block["title"] == "MotorMoto Plan"
    assert block["mission"].startswith("Become the trusted choice")
    assert block["focus"] == ["Demand capture", "Trust proof", "Local search readiness"]
    assert block["recommended_channels"][0]["channel"] == "Email"
    assert block["recommended_channels"][2]["status"] == "hold"
    assert "approve" in block["allowed_actions"]


def test_marketing_planning_module_rejects_ungrounded_targets_and_channels() -> None:
    module = MarketingCampaignStrategyPlanModule()
    bad = SAMPLE_CONTENT.replace(
        "Become the trusted choice for everyday riders who need practical, reliable mobility.",
        "Increase sales by 15% in 6 months for everyday riders."
    ).replace(
        "- Email — Active — nurture warm leads — existing contacts can convert before paid spend",
        "- Influencer Marketing — Active — brand promotion — creator reach will drive demand"
    )

    verdict, failures = module.self_check(bad, {"brand_name": "MotorMoto"})

    assert verdict == "fail"
    assert "invented_percentage_target" in failures
    assert "unsupported_recommended_channel_without_context:influencer" in failures


def test_marketing_planning_module_does_not_mark_loaded_brand_kit_missing() -> None:
    module = MarketingCampaignStrategyPlanModule()
    bad = SAMPLE_CONTENT.replace(
        "- Monthly budget — unlocks paid channel activation",
        "- Brand guidelines — unlocks consistent branding and messaging"
    )

    verdict, failures = module.self_check(bad, {"campaign_brand_kit_excerpt": "Approved brand voice and offer rules."})

    assert verdict == "fail"
    assert "incorrectly_marks_brand_guidelines_missing" in failures


def test_cmo_prompt_keeps_plans_out_of_inline_chat() -> None:
    prompt = (Path(__file__).resolve().parents[1] / "capabilities/workspace/cmo_context/SYSTEM_PROMPT.md").read_text()

    assert "Artifact surface boundary" in prompt
    assert "do not write full platform-native artifacts inline" in prompt
    assert "Never promise that you will create" in prompt
    assert "another one" in prompt
