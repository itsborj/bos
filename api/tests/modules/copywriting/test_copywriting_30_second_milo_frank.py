"""Tests for copywriting.copywriting_30_second_milo_frank module."""
from __future__ import annotations

from capabilities.copywriting.copywriting_30_second_milo_frank.module import Copywriting30SecondMiloFrankModule
from capabilities.marketing.channel.facebook.paid.ads.copy.module import FacebookAdCopyModule


def test_skill_module_metadata():
    module = Copywriting30SecondMiloFrankModule()
    info = module.module_info()

    assert info["id"] == "copywriting.copywriting_30_second_milo_frank"
    assert info["name"] == "copywriting_30_second_milo_frank"
    assert info["vertical"] == "copywriting"
    assert info["internal"] is True
    assert info["capability"] == "marketing.copywriting"


def test_skill_prompt_section_contains_framework():
    guidance = Copywriting30SecondMiloFrankModule().as_prompt_section()

    assert "The 30-Second Message" in guidance
    assert "Objective" in guidance
    assert "Audience" in guidance
    assert "Hook" in guidance
    assert "Ask" in guidance
    assert "Hook: [Earn attention" in guidance


def test_marketing_module_calls_copywriting_skill_in_prompt():
    prompt = FacebookAdCopyModule().build_prompt({
        "product_name": "Notion",
        "audience": "remote teams",
        "tone": "conversational",
    })

    assert "## Copywriting Skill Stack" in prompt
    assert "copywriting_30_second_milo_frank" in prompt
    assert "The 30-Second Message" in prompt
    assert "Hook: [Earn attention" in prompt


def test_self_check_flags_missing_product_for_direct_skill_run():
    module = Copywriting30SecondMiloFrankModule()
    verdict, failures = module.self_check("Clear copy for teams.", {"product_name": "Notion"})

    assert verdict == "fail"
    assert any("must_mention_missing:Notion" == failure for failure in failures)
