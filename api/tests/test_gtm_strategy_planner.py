from __future__ import annotations

from pathlib import Path

import pytest

from capabilities.marketing.planning.gtm_plan.module import MarketingGtmStrategyPlanModule
from skills.loader import list_skill_manifests


SAMPLE_CONTENT = """# GTM Launch Strategy — Klaroha

## Best current motion
Founder-led demand capture + proof-building launch.

## Why this motion
The Brand Brief points to a high-trust B2B service where buyers need confidence before they act.

## Primary audience
Small agency owners and overloaded business leaders who need a clearer marketing operating loop.

## Positioning angle
Launch your marketing operating system without becoming the integrator.

## Core promise
Klaroha turns scattered marketing tools, specialists, approvals, and performance signals into one operating loop.

## Launch sequence
1. Proof setup — collect screenshots, examples, and customer language
2. Demand-capture page — publish one focused landing page
3. Founder-led outreach — start qualified conversations
4. Post-launch learning — capture objections and outcomes into memory

## Channel stack
### Do now
- Website / Landing Page — conversion hub — needed before sending traffic anywhere
- Founder Email / Direct Outreach — first qualified conversations — best fit for a trust-heavy offer with limited proof

### Hold
- Paid social — no proof or winning message yet
- Affiliate program — useful after first happy customers exist

### Avoid for now
- Large ad budget — premature without proof, customer language, and tracking

## Conversion path
Landing page → Diagnostic call → Problem summary and recommendation → Approved onboarding package → Outcome memory

## First proof assets needed
- Before/after workflow example
- One operator pain quote or testimonial

## Measurement frame
- Stage 0 — conversion asset live, CTA functional, tracking functional — numeric targets: requires baseline — review before Stage 1 — gate: asset live and tracked
- Stage 1 — qualified conversations, buyer language captured, objections documented — numeric targets: requires baseline — weekly — gate: 3+ qualified conversations completed

## Assumptions I made
- Trust-heavy B2B service launch
- Qualified conversations over self-serve signup
- Lean budget until proof exists

## Critical gaps
- Customer proof — unlocks landing page, outreach, and objection handling
- Primary conversion action — unlocks CTA and page structure

## Useful later
- Monthly budget
- Target launch date
- Current traffic baseline

## Next artifacts
- Landing page copy — convert launch interest into calls
- Founder outreach sequence — start qualified conversations
- Sales one-pager — explain the offer quickly

## Approval note
This is a draft strategy for review; execution artifacts and external actions require separate approval.
"""


def test_gtm_strategy_skill_is_retired_from_dispatchable_manifests() -> None:
    # The module file remains for historical/parser regression coverage below,
    # but CMO chat must dispatch marketing.planning.strategy_workflow instead.
    skill_ids = {s.id for s in list_skill_manifests()}

    assert "marketing.planning.gtm_plan" not in skill_ids


def test_gtm_strategy_module_self_check_and_block() -> None:
    module = MarketingGtmStrategyPlanModule()

    verdict, failures = module.self_check(SAMPLE_CONTENT, {"brand_name": "Klaroha"})
    block = module._build_block(SAMPLE_CONTENT)

    assert verdict == "pass"
    assert failures == []
    assert block["type"] == "gtm_strategy"
    assert block["artifact_type"] == "plan_artifact"
    assert block["best_current_motion"].startswith("Founder-led")
    assert block["channel_stack"]["do_now"][0]["channel"] == "Website / Landing Page"
    assert block["launch_sequence"][0]["step"] == "Proof setup"
    assert block["critical_gaps"][0]["gap"] == "Customer proof"
    assert block["measurement_frame"][0].startswith("Stage 0")
    assert "approve" in block["allowed_actions"]


def test_gtm_strategy_accepts_rich_do_now_reasoning_blocks() -> None:
    module = MarketingGtmStrategyPlanModule()
    rich = SAMPLE_CONTENT.replace(
        "### Do now\n"
        "- Website / Landing Page — conversion hub — needed before sending traffic anywhere\n"
        "- Founder Email / Direct Outreach — first qualified conversations — best fit for a trust-heavy offer with limited proof",
        "### Do now\n"
        "**Website / Landing Page**\n"
        "Decision: conversion hub — problem-aware buyer needs a trust-building page — proof arc and CTA clarity\n"
        "Rationale: This gives founder-led outreach somewhere credible to point. It fits a high-anxiety buyer because the page can show the proof arc before asking for commitment.\n\n"
        "**Founder Email / Direct Outreach**\n"
        "Decision: first qualified conversations — early-majority buyer with high trust barrier — process transparency\n"
        "Rationale: This creates buyer-language and objection signal before volume. It keeps the motion human-touch while proof is still thin."
    )

    verdict, failures = module.self_check(rich, {"brand_name": "Klaroha"})
    block = module._build_block(rich)

    assert verdict == "pass"
    assert "too_many_do_now_channels" not in failures
    assert len(block["channel_stack"]["do_now"]) == 2
    assert block["channel_stack"]["do_now"][0]["buyer_map_signal"] == "problem-aware buyer needs a trust-building page"


def test_gtm_strategy_parses_demoted_launch_headings_and_ignores_template_placeholders() -> None:
    module = MarketingGtmStrategyPlanModule()
    demoted = SAMPLE_CONTENT.replace("## Launch sequence", "### Launch sequence").replace(
        "1. Proof setup — collect screenshots, examples, and customer language\n"
        "2. Demand-capture page — publish one focused landing page\n"
        "3. Founder-led outreach — start qualified conversations\n"
        "4. Post-launch learning — capture objections and outcomes into memory",
        "#### Stage 0 — Foundation\n"
        "Build the landing page and tracking first. Pending gate: conversion asset live.\n\n"
        "#### Stage 1 — Proof and first conversations\n"
        "Use founder-led outreach to learn buyer language. Pending gate: buyer language captured.\n\n"
        "#### Stage 2 — Conversion path validation\n"
        "Validate the path before adding volume. Pending gate: path validated."
    ).replace(
        "- Paid social — no proof or winning message yet",
        "- Channel — hold reason — specific unlock condition\n- Paid social — no proof or winning message yet"
    )

    verdict, failures = module.self_check(demoted, {"brand_name": "Klaroha"})
    block = module._build_block(demoted)

    assert verdict == "pass"
    assert "insufficient_launch_sequence" not in failures
    assert block["launch_sequence"][0]["step"] == "Stage 0: Foundation"
    assert block["channel_stack"]["hold"][0]["name"] == "Paid social"


def test_gtm_strategy_rejects_hallucinated_numbers_and_channel_soup() -> None:
    module = MarketingGtmStrategyPlanModule()
    bad = SAMPLE_CONTENT.replace(
        "Founder-led demand capture + proof-building launch.",
        "Generate 300 leads and $50K in revenue through a full-channel launch."
    ).replace(
        "- Founder Email / Direct Outreach — first qualified conversations — best fit for a trust-heavy offer with limited proof",
        "- Founder Email / Direct Outreach — first qualified conversations — best fit for a trust-heavy offer with limited proof\n"
        "- Affiliate program — partner growth — scale referrals immediately\n"
        "- Community — audience growth — build a Discord now\n"
        "- Influencer marketing — awareness — creator reach\n"
        "- TikTok — awareness — short videos\n"
        "- Paid social — acquisition — broad reach"
    )

    verdict, failures = module.self_check(bad, {"brand_name": "Klaroha"})

    assert verdict == "fail"
    assert "invented_numeric_target_or_proof" in failures
    assert "too_many_do_now_channels" in failures
    assert "unsupported_do_now_channel_without_context:affiliate" in failures


def test_gtm_strategy_allows_late_channel_mentions_inside_rationale_only() -> None:
    module = MarketingGtmStrategyPlanModule()
    content = SAMPLE_CONTENT.replace(
        "- Founder Email / Direct Outreach — first qualified conversations — best fit for a trust-heavy offer with limited proof",
        "- Social media — reassurance surface — buyers look for peer and influencer discussion before visiting"
    )

    verdict, failures = module.self_check(content, {"brand_name": "MotorMoto"})

    assert verdict == "pass"
    assert "unsupported_do_now_channel_without_context:influencer" not in failures


def test_gtm_strategy_enforces_motion_taxonomy_and_email_list_gate() -> None:
    module = MarketingGtmStrategyPlanModule()
    bad = SAMPLE_CONTENT.replace(
        "Founder-led demand capture + proof-building launch.",
        "Human-led conversations as the primary motion."
    ).replace(
        "- Founder Email / Direct Outreach — first qualified conversations — best fit for a trust-heavy offer with limited proof",
        "- Email Marketing — nurture — useful for first-time buyers"
    )

    verdict, failures = module.self_check(bad, {"brand_name": "MotorMoto"})

    assert verdict == "fail"
    assert "invalid_motion_taxonomy" in failures
    assert "unsupported_do_now_channel_without_context:email_list" in failures


def test_gtm_sample_is_approved() -> None:
    sample_path = next(
        (
            parent / "sample/gtm_strategy_artifact_v1.md"
            for parent in Path(__file__).resolve().parents
            if (parent / "sample/gtm_strategy_artifact_v1.md").exists()
        ),
        None,
    )
    if not sample_path:
        pytest.skip("repository-level sample/ is not mounted in this test environment")
    sample = sample_path.read_text()

    assert "Status: approved" in sample
    assert "Forbidden 1 — questionnaire wall" in sample
