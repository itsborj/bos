---
id: onboarding.brand_setup
name: extracting-brand-profile
description: Use during explicit onboarding flows to extract brand profile, products, and audiences from supplied brand materials. Use when onboarding a new brand, importing a brand brief, or setting up brand profile, products, and audiences for the first time.
scope: onboarding
allowed_from_chat: false
module_id: onboarding.brand_setup
requires_intent:
  - onboarding
triggers:
  - brand setup
  - import brand brief
  - onboard brand
memory_slots:
  - supplied_brand_materials
quality_gates:
  - explicit_onboarding_flow
  - structured_workspace_output
  - no_normal_chat_dispatch
---

# Brand Setup Extraction Skill

## Purpose

Guide explicit onboarding extraction of brand profile, product catalog, and audience profiles from user-supplied materials.

## Operating rules

- This skill is not normal CMO chat-dispatchable.
- Run only from onboarding/admin workspace flows.
- Preserve source material references where possible.
- Produce structured workspace data suitable for human review before approval.

## Quality gate

Before persistence, verify that extracted voice, tone, values, products, and audiences are present or clearly marked as missing.
