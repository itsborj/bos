---
id: marketing.plan.campaign_strategy
name: campaign-strategy-planner
description: Use when the CMO needs to create a native campaign or marketing plan artifact for a brand, offer, launch, quarter, month, demand-capture motion, channel mix, or go-to-market priority. This implements the CMO-facing marketing.plan job. Do not use for capability questions; answer those conversationally. Do not paste the full plan inline in chat; create a Workspace plan artifact.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.plan.campaign_strategy
requires_intent:
  - discussion
  - generation
triggers:
  - plan campaign
  - marketing plan
  - campaign plan
  - go to market plan
  - launch plan
  - plan for
  - quarterly plan
  - monthly plan
  - channel mix
  - demand capture plan
  - build another one
  - make another one
  - create another plan
  - another campaign plan
  - same plan for
  - same for
excluded_triggers:
  - what can you do
  - capabilities
  - sample ads
  - draft email
  - write ad
  - check inbox
  - check google ads performance
memory_slots:
  - brand_profile
  - product_catalog
  - audience_profiles
  - campaign_brand_kit
  - brand_guidelines
  - marketing_reports
  - campaign_reports
  - competitor_profiles
  - industry_data
quality_gates:
  - plan_artifact_created
  - mission_present
  - focus_present
  - channel_fit_reasoned
  - missing_inputs_present
  - no_inline_chat_plan
metadata:
  version: 0.1.0
  author: bos-core
  implements: marketing.plan
  specialist: planning
  risk_policy: draft_only
  artifact_type: plan_artifact
  output_contract: marketing_plan
  platform: planning
---

# Marketing Planning Specialist

This skill governs the native BOS Marketing Planning Specialist. It creates a reviewable `plan_artifact` for Workspace/Stream instead of allowing the CMO to paste a long plan into mobile chat.

## When to activate

- User asks for a marketing plan, campaign plan, launch plan, quarterly/monthly plan, channel mix, or strategic plan for a brand/offer.
- User uses `@klar plan` and brand/scope is clear.
- User asks for another/same plan in a follow-up, such as "build another one for Klaroha" after a prior campaign plan artifact.
- User needs the CMO to decide what to do before execution specialists draft, read, send, publish, or mutate anything.

## Do not activate for

- Capability questions like "what can you do?".
- A request to draft one specific channel artifact when a channel specialist owns it.
- Read-only diagnostics like checking Google Ads performance.
- Approved external actions.

## Outcome contract

Artifact type: `plan_artifact`  
Block/output contract: `marketing_plan`  
Risk policy: `draft_only`

The module artifact must include:

1. Plan title
2. Mission
3. Focus list
4. Recommended channels with status and reason
5. Not-recommended-yet channels with reason
6. Missing inputs
7. Allowed review actions

## Chat behavior

The CMO visible reply should be short and mobile-first:

```text
I’ll build the campaign plan now.

It’ll be ready in Workspace for review.
```

Do not paste the plan body into chat. Workspace owns the plan layout and review controls.
