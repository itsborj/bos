"""Tests for marketing.channel.email.outreach.sequence module."""
from __future__ import annotations

import pytest

from capabilities.marketing.channel.email.outreach.sequence.module import EmailSequenceModule


@pytest.fixture
def module():
    return EmailSequenceModule()


@pytest.fixture
def sample_brief():
    return {
        "brand_name": "BOS",
        "product_name": "Notion",
        "tagline": "Your connected workspace",
        "audience": "remote teams",
        "tone": "professional",
        "key_benefit": "everything in one place",
    }


class TestSelfCheck:
    def test_pass_valid_sequence(self, module, sample_brief):
        content = """## Sequence Overview
Sequence Name: Trial Welcome Sequence
Trigger: New trial signup
Goal: Activate Notion trial users
Length: 3 emails
Timing: 7 days
Exit Conditions: User upgrades

## Email-by-email Plan

Email 1: Welcome
Send: Immediately
Subject: Welcome to Notion
Preview: Start with one clean workspace.
Body:
Hi there,

Welcome to Notion. Start by creating your first team workspace.
CTA: Create workspace → App
Segment/Conditions: All new trials

Email 2: Quick Win
Send: Day 2
Subject: Your first team hub
Preview: Bring docs and tasks together.
Body:
Notion helps remote teams keep docs, projects, and decisions in one place.
CTA: Build your hub → Template
Segment/Conditions: Has not created workspace

Email 3: Convert
Send: Day 7
Subject: Keep your team aligned
Preview: Upgrade when your workspace is ready.
Body:
Your team can keep using Notion to manage work after the trial.
CTA: Upgrade Notion → Billing
Segment/Conditions: Active trial users

## Metrics Plan
- Primary conversion metric: trial-to-paid conversion
- Supporting metrics: opens, clicks, activation, unsubscribes
- Optimization notes: test quick-win CTA
"""
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "pass"
        assert failures == []

    def test_fail_too_few_emails(self, module, sample_brief):
        content = """## Sequence Overview
Trigger: Signup
Goal: Activate Notion users

Email 1: Welcome
Subject: Welcome
Preview: Start here
CTA: Start → App

## Metrics Plan
Metrics: conversion
"""
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert "too_few_emails" in failures

    def test_fail_missing_subject_lines(self, module, sample_brief):
        content = """## Sequence Overview
Trigger: Signup
Goal: Activate Notion users

Email 1: Welcome
Preview: Start here
CTA: Start → App

Email 2: Value
Preview: Keep going
CTA: Continue → App

Email 3: Convert
Preview: Upgrade
CTA: Upgrade → Billing

## Metrics Plan
Metrics: conversion
"""
        verdict, failures = module.self_check(content, sample_brief)
        assert verdict == "fail"
        assert "missing_subject_lines" in failures


class TestBuildPrompt:
    def test_template_renders_with_brief(self, module, sample_brief):
        result = module.build_prompt(sample_brief)
        assert "Notion" in result
        assert "remote teams" in result
        assert "Email Sequence" in result
        assert "Sequence Overview" in result

    def test_template_handles_missing_fields(self, module):
        result = module.build_prompt({"product_name": "Test Product"})
        assert "Test Product" in result


class TestModuleInfo:
    def test_returns_correct_info(self, module):
        info = module.module_info()
        assert info["id"] == "marketing.channel.email.outreach.sequence"
        assert info["vertical"] == "marketing"
        assert info["capability"] == "marketing.copywriting"
        assert info["platform_hint"] == "email_sequence"
        assert info["constraints"]["max_chars"] == 12000
