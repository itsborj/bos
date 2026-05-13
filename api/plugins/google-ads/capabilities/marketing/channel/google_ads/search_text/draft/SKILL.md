---
id: marketing.channel.google_ads.search_text.draft
name: Google Ads Search Text Draft
description: Draft Google Ads responsive search ad copy as a reviewable Workspace artifact. Use when the user explicitly asks to generate, draft, write, create, or see Google Ads copy/ad copy/search ad copy. This capability creates copy only; it does not publish ads, create campaigns, change budgets, edit keywords, or call the Google Ads API.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.google_ads.search_text.draft
requires_intent:
  - generation
triggers:
  - google ads copy
  - google ad copy
  - google search ad copy
  - google search ads copy
  - google ads draft
  - google ad draft
  - draft google ads
  - draft a google ad
  - draft google ad
  - generate google ads copy
  - generate google ad copy
  - write google ads copy
  - write google ad copy
  - create google ads copy
  - create google ad copy
  - sample google ads copy
  - sample google ad copy
excluded_triggers:
  - check google ads performance
  - pull google ads data
  - fetch google ads data
  - read google ads
  - google ads performance
  - google ads report
  - google ads metrics
  - change google ads budget
  - pause google ads campaign
  - enable google ads campaign
  - launch google ads campaign
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.google_ads.search_text.draft
output_contract:
  - google_search_ad_draft
quality_gates:
  - responsive_search_ad_fields_present
  - headlines_within_30_chars
  - descriptions_within_90_chars
  - no_mutation_claims
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.google_ads
  implements: marketing.execute
  artifact_type: draft_artifact
  platform: google_ads
  output_contract: google_search_ad_draft
  risk_policy: draft_only_until_approved
---

# Google Ads Search Text Draft

## Purpose

Create a reviewable Google Ads responsive search ad copy draft. The module returns native ad fields for Workspace/Stream preview:

- headlines
- descriptions
- display URL
- approval/risk metadata

## Activation

Use this when the user explicitly asks for Google Ads copy, for example:

- "can you generate a google ads copy"
- "draft google ads copy"
- "write google ad copy"
- "show me sample google ads copy"
- "create a google search ad"

## Hard boundaries

This capability drafts copy only. It never:

- pulls performance data
- creates a campaign
- publishes an ad
- changes a budget
- pauses/enables a campaign
- edits keywords or bids
- claims the ad is live

Performance/data questions belong to `marketing.channel.google_ads.performance.read`. Mutation requests require a separate approval-gated action capability.

## CMO response behavior

When activated, keep the visible reply short and append the hidden directive:

```text
I’ll create a Google Ads copy draft as a reviewable Workspace artifact. It will not be published or applied to the account.
RUN: marketing.channel.google_ads.search_text.draft
```

Do not paste the headlines/descriptions inline in CMO chat. Workspace renders the native preview.

## Outcome contract

Artifact type: `draft_artifact`
Block/output contract: `google_search_ad_draft`
Platform: `google_ads`
Risk policy: `draft_only_until_approved`

The module result contains:

- `type: google_search_ad_draft`
- `format: responsive_search_ad`
- `headlines[]` with text fields, max 30 characters each
- `descriptions[]` with text fields, max 90 characters each
- `display_url`
- `read_only: true`
- `changed_resources: []`
- `allowed_actions: [approve, request_changes, dismiss]`
- `risk_level: requires_approval`
