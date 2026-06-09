---
id: marketing.planning.strategy_workflow
name: strategy-workflow
version: 1.0.0
description: >
  Generate a modular Strategy Workflow from the brand brief. Use for GTM planning,
  marketing plans, launch strategy, go-to-market, market entry, demand generation
  strategy, and shorthand requests like "GTM", "another GTM", "new GTM",
  "launch plan", or "strategy". Produces a multi-component workflow with buyer map, strategic thesis,
  offer architecture, channel stack, tactical funnel, and work orders — each
  independently revisable. CMO chat returns a short confirmation and a link to the
  workflow page. The workflow is NOT an execution order; all outreach, publishing,
  and spend require separate approval.
scope: module
status: active
allowed_from_chat: true
module_id: marketing.planning.strategy_workflow
requires_intent:
  - discussion
  - generation
triggers:
  - gtm
  - gtm strategy
  - gtm plan
  - launch strategy
  - plan a launch
  - market entry
  - another gtm
  - new gtm
  - do another gtm
  - go to market
  - go-to-market
  - launch plan
  - new product launch
  - new service launch
  - first channels
  - first users strategy
  - demand capture strategy
  - launch motion
  - product launch strategy
  - service launch strategy
  - strategy workflow
  - build a strategy
  - marketing strategy
  - marketing plan
  - create a marketing plan
  - build a marketing plan
  - full strategy
excluded_triggers:
  - draft email
  - write email
  - write ad
  - draft facebook post
  - create a facebook post
  - social post
  - generate image
  - publish
  - send email
  - check performance
  - check inbox
  - capability question
  - what can you do
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
outputs:
  - strategy_workflow.v1
quality_gates:
  - buyer_map_present
  - strategic_thesis_present
  - motion_named
  - wedge_present
  - work_orders_present
  - no_execution_without_approval
metadata:
  version: 1.0.0
  author: bos-core
  implements: marketing.plan
  specialist: gtm_planning
  risk_policy: draft_only
  artifact_type: plan_artifact
  output_contract: strategy_workflow
  platform: planning
---

# Strategy Workflow Skill

## Purpose

Replaces the single-shot GTM plan artifact with a modular Strategy Workflow.
Each component is independently stored and revisable. CMO chat returns one short
message and a link — it does not dump the strategy body.

## Component map

See `STRATEGY_WORKFLOW.md` at the project root for the full dependency DAG,
field contracts, archetype weight table, and cascade rules.

## Chat behavior

Correct visible reply:

```
Building the Strategy Workflow for [Brand].

Buyer map → strategic thesis → offer architecture → channel stack → funnel → work orders.

[Open Strategy Workflow]
```

## Forbidden behaviors

1. Do not paste strategy content into chat.
2. Do not set numeric targets without loaded baseline data.
3. Do not recommend more than 3 do-now channels.
4. Do not execute outreach, publishing, spend, or platform actions as part of generation.
5. Do not skip the wedge — it is the single most important output.
