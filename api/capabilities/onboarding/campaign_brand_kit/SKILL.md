---
id: onboarding.campaign_brand_kit
name: generating-brand-creative-brief
description: Use during explicit onboarding/workspace flows to generate or revise the Brand Creative Brief from approved workspace context and supplied brand evidence.
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

# Brand Creative Brief Generation Skill

## Purpose

Generate or revise the durable Brand Creative Brief from approved workspace context and supplied brand materials.

## Operating rules

- This skill is not normal CMO chat-dispatchable.
- The output is a durable workspace document, not casual chat copy.
- Capture identity, visual language, creative boundaries, and factual asset requirements without prescribing fixed layouts.
- Drafts require human approval before becoming authoritative context.

## Quality gate

Before creating the document, verify it includes brand foundation, visual identity, creative assets, creative latitude and boundaries, campaign truth, and governance.
