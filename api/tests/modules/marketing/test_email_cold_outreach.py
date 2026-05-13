"""Tests for marketing.channel.email.outreach.cold module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from capabilities.marketing.channel.email.outreach.cold.module import ColdOutreachEmailModule


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def module():
    """Return an instance of ColdOutreachEmailModule."""
    return ColdOutreachEmailModule()


@pytest.fixture
def sample_brief():
    """Return a sample brief for testing."""
    return {
        "brand_name": "BOS",
        "product_name": "Notion",
        "tagline": "Your connected workspace",
        "audience": "remote teams",
        "tone": "professional",
        "key_benefit": "everything in one place",
    }


# ── Test self_check ─────────────────────────────────────────────

class TestSelfCheck:
    """Tests for the self_check method."""

    def test_pass_valid_email(self, module, sample_brief):
        """self_check passes for valid email with all required elements."""
        content = (
            "Subject: Boost Your Team's Productivity with Notion\n\n"
            "Hi John,\n\n"
            "I noticed that many remote teams struggle with disconnected tools.\n\n"
            "Notion helps remote teams work smarter by bringing everything in one place.\n"
            "Thousands of teams already run on Notion and see productivity gains.\n\n"
            "Try Notion free for 14 days — no credit card required.\n\n"
            "Best regards,\nThe BOS Team"
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "pass"
        assert failures == []

    def test_fail_exceeds_max_chars(self, module, sample_brief):
        """self_check fails when content exceeds 2000 characters."""
        content = "Subject: Test\n\n" + "x" * 2000
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any("exceeds_max_chars" in f for f in failures)

    def test_fail_missing_product_name(self, module, sample_brief):
        """self_check fails when product_name is not mentioned."""
        content = (
            "Subject: Great Product\n\n"
            "Hi there,\n\n"
            "This tool is amazing for remote teams.\n\n"
            "Try it today!"
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any("must_mention_missing" in f for f in failures)

    def test_fail_spam_phrase_dear_sir(self, module, sample_brief):
        """self_check fails when spam phrase 'Dear Sir/Madam' is used."""
        content = (
            "Subject: Hello\n\n"
            "Dear Sir/Madam,\n\n"
            "Notion is great for remote teams.\n\n"
            "Try it today!"
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert any("banned_phrase_found" in f for f in failures)

    def test_fail_missing_subject_line(self, module, sample_brief):
        """self_check fails when no subject line is present."""
        content = (
            "Hi there,\n\n"
            "Notion is great for remote teams.\n\n"
            "Try it today!"
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert "missing_subject_line" in failures

    def test_fail_missing_greeting(self, module, sample_brief):
        """self_check fails when no greeting is present."""
        content = (
            "Subject: Notion\n\n"
            "Notion is great for remote teams.\n\n"
            "Try it today!"
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert "missing_greeting" in failures

    def test_fail_missing_call_to_action(self, module, sample_brief):
        """self_check fails when no call to action is present."""
        content = (
            "Subject: Notion\n\n"
            "Hi,\n\n"
            "Notion is great for remote teams.\n\n"
            "It brings everything together."
        )
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert "missing_call_to_action" in failures


# ── Test build_prompt ─────────────────────────────────────────────

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


# ── Test module_info ─────────────────────────────────────────────

class TestModuleInfo:
    """Tests for the module_info method."""

    def test_returns_correct_info(self, module):
        """module_info returns correct module metadata."""
        info = module.module_info()
        assert info["id"] == "marketing.channel.email.outreach.cold"
        assert info["vertical"] == "marketing"
        assert info["capability"] == "marketing.copywriting"
        assert info["platform_hint"] == "email"
        assert info["constraints"]["max_chars"] == 2000


# ── Test full execution (mocked provider) ──────────────────────

class TestFullExecution:
    """Tests for full module execution with mocked provider."""

    def test_module_attributes(self, module):
        """Module has correct attributes."""
        assert module.id == "marketing.channel.email.outreach.cold"
        assert module.template == "marketing/email_cold_outreach.j2"
        assert module.max_chars == 2000
