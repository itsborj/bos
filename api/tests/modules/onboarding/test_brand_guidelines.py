"""Tests for onboarding.brand_guidelines module."""
from __future__ import annotations

import pytest

from capabilities.onboarding.brand_guidelines.module import BrandGuidelinesModule


@pytest.fixture
def module():
    return BrandGuidelinesModule()


@pytest.fixture
def sample_brief():
    return {
        "brand_name": "Klaroha",
        "tagline": "Systems for clarity",
        "product_name": "Klaroha OS",
        "business_type": "B2B SaaS",
        "primary_industry": "business operations software",
        "audience": "ops-focused founders",
        "tone": "professional",
        "voice": "precise, calm, and practical",
        "values": ["clarity", "trust", "operational excellence"],
        "color_palette": {"racing green": "#0b3d2e", "amber": "#fcc167"},
        "visual_language": ["editorial restraint", "high contrast", "precise geometry"],
    }


def valid_guidelines_content() -> str:
    return """
# Klaroha — Brand Creative Brief

## 1. Brand Foundation
Klaroha is precise, calm, practical, and built for ops-focused founders.

## 2. Visual Identity
Use Racing Green and Amber with restrained editorial typography.

## 3. Creative Assets
The official logo is the identity anchor. Product and aesthetic references are used when relevant.

## 4. Creative Latitude and Boundaries
The agency has creative latitude for composition and imagery. Never distort the official logo or invent product facts.

## 5. Campaign Truth
Offers, claims, audiences, and immutable assets come from the active campaign.

## 6. Governance
Folder assets are authorized for production use. Templates are optional. Approve campaign direction and finished creative.
""".strip()


class TestModuleInfo:
    def test_returns_correct_info(self, module):
        info = module.module_info()
        assert info["id"] == "onboarding.brand_guidelines"
        assert info["vertical"] == "onboarding"
        assert info["capability"] == "onboarding.brand_profiling"
        assert info["constraints"]["must_mention"] == ["brand_name"]

    def test_module_attributes(self, module):
        assert module.id == "onboarding.brand_guidelines"
        assert module.template == "onboarding/brand_guidelines/template.j2"
        assert module.policy_default == "balanced"


class TestBuildPrompt:
    def test_template_renders_with_brief(self, module, sample_brief):
        prompt = module.build_prompt(sample_brief)
        assert "Klaroha" in prompt
        assert "Klaroha OS" in prompt
        assert "ops-focused founders" in prompt
        assert "Brand Creative Brief" in prompt
        assert "Return Markdown only" in prompt
        assert "#0b3d2e" in prompt

    def test_template_handles_minimal_brief(self, module):
        prompt = module.build_prompt({"brand_name": "Acme"})
        assert "Acme" in prompt
        assert "without prescribing fixed layouts" in prompt


class TestSelfCheck:
    def test_passes_complete_brief(self, module, sample_brief):
        verdict, failures = module.self_check(valid_guidelines_content(), sample_brief)
        assert verdict == "pass"
        assert failures == []

    def test_fails_missing_required_section(self, module, sample_brief):
        content = valid_guidelines_content().replace("## 2. Visual Identity", "## 2. Style")
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert "missing_section:Visual Identity" in failures

    def test_fails_unresolved_placeholders(self, module, sample_brief):
        content = valid_guidelines_content() + "\n\n[PLACEHOLDER]"
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any(f.startswith("unresolved_placeholder") for f in failures)

    def test_fails_missing_optional_template_policy(self, module, sample_brief):
        content = valid_guidelines_content().replace("Templates are optional.", "Layouts are managed elsewhere.")
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert "missing_creative_brief_item:templates are optional" in failures
