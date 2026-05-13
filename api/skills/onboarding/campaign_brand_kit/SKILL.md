---
id: onboarding.campaign_brand_kit
name: Campaign Brand Kit Generation
description: Use during explicit onboarding/workspace flows to generate or revise the Campaign Brand Kit document from approved workspace context.
scope: onboarding
allowed_from_chat: false
module_id: onboarding.brand_guidelines
requires_intent:
  - onboarding
  - generation
  - revision
triggers:
  - campaign brand kit
  - brand kit
  - brand guidelines
memory_slots:
  - brand_profile
  - product_catalog
  - audience_profiles
  - supplied_brand_materials
quality_gates:
  - explicit_onboarding_flow
  - complete_brand_kit_sections
  - human_approval_required
  - no_normal_chat_dispatch
---

# Campaign Brand Kit Generation Skill

## Purpose

Generate or revise the required Campaign Brand Kit document from approved workspace context and supplied brand materials.

## Operating rules

- This skill is not normal CMO chat-dispatchable.
- The output is a durable workspace document, not casual chat copy.
- Include practical voice/design rules that can guide future multi-channel campaign assets.
- Drafts require human approval before becoming authoritative context.

## Quality gate

Before creating the document, verify it includes voice, tone, values, CTA style, platform consistency rules, and basic campaign component guidance.
