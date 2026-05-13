---
id: marketing.channel.google_ads.campaigns.read
name: Google Ads Campaign Report
description: Read-only Google Ads campaign performance report. Use only when the user explicitly asks to read, show, list, check, pull, or report Google Ads campaign performance, campaign list, campaign metrics, spend, CPA, CTR, conversions, or budget/campaign status. This capability returns campaign metrics and never creates, edits, pauses, enables, deletes, optimizes, or changes budgets.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.google_ads.campaigns.read
requires_intent:
  - diagnostic
  - discussion
triggers:
  - google ads campaign report
  - google ads campaigns
  - google ads campaign performance
  - google ads campaign metrics
  - list google ads campaigns
  - show google ads campaigns
  - check google ads campaigns
  - pull google ads campaigns
  - google ads spend
  - google ads cpa
  - google ads ctr
  - google ads conversions
excluded_triggers:
  - what can you do
  - what can you do with google ads
  - google ads capabilities
  - google ads accounts
  - google ads account discovery
  - google ads customer id
  - google ads copy
  - google ad copy
  - generate google ads copy
  - write google ad copy
  - change google ads budget
  - pause google ads campaign
  - enable google ads campaign
  - delete google ads campaign
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.google_ads.campaigns.read
output_contract:
  - google_ads_campaign_report
quality_gates:
  - read_only_only
  - no_budget_or_campaign_mutation
  - google_ads_credentials_present
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.google_ads
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_ads
  output_contract: google_ads_campaign_report
  risk_policy: read_only_no_mutation
---

# Google Ads Campaign Report

## Purpose

Return a read-only report of Google Ads campaign performance and budget/campaign status fields.

## Hard boundaries

Never:

- draft ad copy
- create campaigns
- edit campaigns
- pause/enable campaigns
- change budgets
- change keywords, bids, ads, assets, or targeting
- apply optimization recommendations automatically

## CMO response behavior

If running this capability, keep the visible reply short and append the hidden directive:

```text
I’ll pull a read-only Google Ads campaign report for Workspace review.
RUN: marketing.channel.google_ads.campaigns.read
```

## Outcome contract

Artifact type: `intelligence_artifact`
Block/output contract: `google_ads_campaign_report`
Platform: `google_ads`
Risk policy: `read_only_no_mutation`

The module returns:

- campaign rows
- totals for impressions, clicks, cost, conversions, CTR, and CPA
- date range
- `read_only: true`
- `changed_resources: []`
- allowed next action: create an optimization plan, not mutate directly
