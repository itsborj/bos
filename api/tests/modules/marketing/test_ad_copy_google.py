"""Tests for marketing.channel.google.paid_search.ads.text module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from capabilities.marketing.channel.google.paid_search.ads.text.module import GoogleAdCopyModule


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def module():
    """Return an instance of GoogleAdCopyModule."""
    return GoogleAdCopyModule()


@pytest.fixture
def sample_brief():
    """Return a sample brief for testing."""
    return {
        "product_name": "Notion",
        "tagline": "Your connected workspace",
        "audience": "remote teams",
        "tone": "professional",
        "key_benefit": "everything in one place",
    }


# ── Test self_check ─────────────────────────────────────────────────

class TestSelfCheck:
    """Tests for the self_check method."""

    def test_pass_valid_content(self, module, sample_brief):
        """self_check passes for valid RSA content."""
        content = (
            "Headline 1: Notion\n"
            "Headline 2: Your Workspace\n"
            "Headline 3: Try Free Today\n"
            "Headline 4: Team Collaboration\n"
            "Headline 5: All-in-One Tool\n"
            "Headline 6: Remote Work Made Easy\n"
            "Headline 7: 100k+ Teams Trust Us\n"
            "Headline 8: Rated #1 for Remote\n"
            "Headline 9: 5 Years Serving Teams\n"
            "Headline 10: Start Free Trial\n"
            "Headline 11: Join Today Free\n"
            "Headline 12: Get Started Now\n"
            "Headline 13: Notion Workspace\n"
            "Headline 14: Notion For Teams\n"
            "Headline 15: Summer Remote Work\n"
            "Description 1: Notion helps remote teams work smarter. Start free today.\n"
            "Description 2: No setup fees. Cancel anytime. Join thousands of teams.\n"
            "Description 3: Try free for 14 days. No credit card required to start.\n"
            "Description 4: Limited time: Free trial + setup support included."
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "pass"
        assert failures == []

    def test_fail_missing_headlines(self, module, sample_brief):
        """self_check fails when fewer than 15 headlines."""
        content = "Headline 1: Notion\n" * 10 + "Description 1: Test desc.\n"
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any("missing_headlines" in f for f in failures)

    def test_fail_missing_descriptions(self, module, sample_brief):
        """self_check fails when fewer than 4 descriptions."""
        content = "Headline 1: Test\n" * 15 + "Description 1: One desc.\n"
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any("missing_descriptions" in f for f in failures)

    def test_fail_headline_too_long(self, module, sample_brief):
        """self_check fails when headline exceeds 30 chars."""
        long_headline = "x" * 31
        content = (
            f"Headline 1: {long_headline}\n" + "Headline 2: Short\n" * 14 +
            "Description 1: Test.\n" * 4
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any("too_long" in f for f in failures)

    def test_fail_description_too_long(self, module, sample_brief):
        """self_check fails when description exceeds 90 chars."""
        long_desc = "x" * 91
        content = (
            "Headline 1: Short\n" * 15 +
            f"Description 1: {long_desc}\n" + "Description 2: Short\n" * 3
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any("too_long" in f for f in failures)

    def test_fail_exclamation_mark_in_headline(self, module, sample_brief):
        """self_check fails when headline contains exclamation mark."""
        content = (
            "Headline 1: Great Deal!\n" + "Headline 2: Normal\n" * 14 +
            "Description 1: Test.\n" * 4
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any("exclamation_mark_not_allowed" in f for f in failures)

    def test_fail_missing_product_name(self, module, sample_brief):
        """self_check fails when product_name is not mentioned."""
        content = (
            "Headline 1: Great Product\n" * 15 +
            "Description 1: This is a great tool for teams.\n" * 4
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any("must_mention_missing" in f for f in failures)


# ── Test build_prompt ──────────────────────────────────────────────

class TestBuildPrompt:
    """Tests for the build_prompt method."""

    def test_template_renders_with_brief(self, module, sample_brief):
        """Template renders successfully with provided brief."""
        result = module.build_prompt(sample_brief)
        assert "Notion" in result
        assert "remote teams" in result
        assert "professional" in result

    def test_template_handles_missing_fields(self, module):
        """Template renders even with minimal brief."""
        minimal_brief = {"product_name": "Test Product"}
        result = module.build_prompt(minimal_brief)
        assert "Test Product" in result


# ── Test module_info ───────────────────────────────────────────────

class TestModuleInfo:
    """Tests for the module_info method."""

    def test_returns_correct_info(self, module):
        """module_info returns correct module metadata."""
        info = module.module_info()
        assert info["id"] == "marketing.channel.google.paid_search.ads.text"
        assert info["vertical"] == "marketing"
        assert info["capability"] == "marketing.copywriting"
        assert info["platform_hint"] == "google"


# ── Test full execution (mocked provider) ────────────────────────

class TestFullExecution:
    """Tests for full module execution with mocked provider."""

    def test_module_attributes(self, module):
        """Module has correct attributes."""
        assert module.id == "marketing.channel.google.paid_search.ads.text"
        assert module.template == "marketing/google_ad.j2"
        assert module.max_chars == 0  # Uses component-level limits
