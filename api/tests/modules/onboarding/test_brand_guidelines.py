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
        "benefits": ["clearer workflows", "less manual coordination"],
    }


def valid_guidelines_content() -> str:
    return """
# Klaroha — Campaign Brand Kit

## 1. Campaign Brand Kit Overview 🔲
Klaroha uses this kit to keep multi-platform campaigns cohesive.

## 2. Color Palette 🔲
| Token name | Hex | Usage |
|---|---|---|
| `color-primary` | `#1F2937` | Primary actions |
| `color-primary-dark` | `#111827` | Hover states |
| `color-primary-light` | `#E5E7EB` | Soft fills |
| `color-accent` | `#2563EB` | Highlights |
| `color-neutral-900` | `#111827` | Text |
| `color-neutral-700` | `#374151` | Secondary text |
| `color-neutral-400` | `#9CA3AF` | Borders |
| `color-neutral-100` | `#F3F4F6` | Subtle backgrounds |
| `color-white` | `#FFFFFF` | Surfaces |
| `color-success` | `#15803D` | Success |
| `color-warning` | `#A16207` | Warnings |
| `color-error` | `#B91C1C` | Errors |
| `bg-base` | `#FFFFFF` | Page background |
| `bg-subtle` | `#F9FAFB` | Secondary panels |
| `bg-surface` | `#FFFFFF` | Cards |

## 3. Tone of Voice 🔲
Klaroha speaks clearly and confidently. Do not use vague jargon.

## 4. Typography Basics 🔲
Use `font-heading`, `font-body`, and `font-label` with system-safe sans-serif defaults.

## 5. Campaign Components 🔲
- `component-primary-cta`: direct verb-first CTA.
- `component-secondary-cta`: lower-emphasis action.
- `component-ad-headline`: short benefit-led headline.
- `component-ad-body`: plain-language supporting copy.
- `component-badge-label`: short campaign label.
- `component-content-card`: reusable offer block.
- `component-email-subject`: specific, human subject line.
- `component-landing-hero`: campaign promise and CTA.

## 6. Platform Rules 🔲
- email: human, specific, one CTA.
- landing page: match campaign promise exactly.

## 7. Accessibility & Consistency 🔲
All campaigns must meet WCAG 2.1 AA and must not rely on color alone.

## 8. Governance 🔲
Status is draft until approved. This kit should remain stable for months or years unless the brand changes materially.

## Optional Future Expansion ⬜
Logo rules, illustration, photography, and detailed motion can be expanded later.
""".strip()


class TestModuleInfo:
    def test_returns_correct_info(self, module):
        info = module.module_info()
        assert info["id"] == "onboarding.brand_guidelines"
        assert info["vertical"] == "onboarding"
        assert info["capability"] == "onboarding.brand_profiling"
        assert info["platform_hint"] == "campaign brand kit"
        assert info["constraints"]["must_mention"] == ["brand_name"]

    def test_module_attributes(self, module):
        assert module.id == "onboarding.brand_guidelines"
        assert module.template == "onboarding/brand_guidelines.j2"
        assert module.policy_default == "balanced"


class TestBuildPrompt:
    def test_template_renders_with_brief(self, module, sample_brief):
        prompt = module.build_prompt(sample_brief)
        assert "Klaroha" in prompt
        assert "Klaroha OS" in prompt
        assert "ops-focused founders" in prompt
        assert "Campaign Brand Kit" in prompt
        assert "Output Markdown only" in prompt

    def test_template_handles_minimal_brief(self, module):
        prompt = module.build_prompt({"brand_name": "Acme"})
        assert "Acme" in prompt
        assert "Do not return a blank template" in prompt


class TestSelfCheck:
    def test_passes_complete_guidelines(self, module, sample_brief):
        verdict, failures = module.self_check(valid_guidelines_content(), sample_brief)
        assert verdict == "pass"
        assert failures == []

    def test_fails_missing_required_section(self, module, sample_brief):
        content = valid_guidelines_content().replace("## 2. Color Palette 🔲", "## 2. Palette 🔲")
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert "missing_section:Color Palette" in failures

    def test_fails_unresolved_placeholders(self, module, sample_brief):
        content = valid_guidelines_content() + "\n\n[PLACEHOLDER]"
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any(f.startswith("unresolved_placeholder") for f in failures)

    def test_fails_missing_campaign_component(self, module, sample_brief):
        content = valid_guidelines_content().replace("component-primary-cta", "component-main-action")
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert "missing_campaign_kit_item:component-primary-cta" in failures
