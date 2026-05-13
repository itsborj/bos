---
id: marketing.channel.google_ads.performance.read
name: Google Ads Read-Only Data Pull
description: Read-only Google Ads data access MVP. Use only when the user explicitly asks to check, pull, fetch, read, or show Google Ads account/campaign performance data. This plugin pulls data and summarizes what is available; it does not draft copy, generate ads, optimize, create, edit, pause, publish, or change budgets. Requests for Google Ads copy belong to the Google Ads Search Text Draft capability, not this data-pull capability.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.google_ads.performance.read
requires_intent:
  - diagnostic
  - generation
  - discussion
triggers:
  - check google ads
  - pull google ads data
  - fetch google ads data
  - read google ads
  - show google ads data
  - show me google ads
  - show me google ads data
  - let me see google ads
  - let me see google ads data
  - google ads data
  - google ads performance
  - google ads report
  - google ads metrics
excluded_triggers:
  - what can you do
  - what can you do with google ads
  - can you help with google ads
  - google ads capabilities
  - google ads accounts
  - google ads account discovery
  - google ads customer id
  - list google ads campaigns
  - show google ads campaigns
  - google ads copy
  - google ad copy
  - google search ad copy
  - generate google ads copy
  - generate google ad copy
  - write google ads copy
  - write google ad copy
  - draft google ads
  - draft google ad
  - create google ads copy
  - create google ad copy
  - create google ads campaign
  - edit google ads campaign
  - change google ads budget
  - pause google ads campaign
  - launch google ads campaign
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.google_ads.performance.read
output_contract:
  - google_ads_data_pull
quality_gates:
  - read_only_only
  - no_budget_or_campaign_mutation
  - google_ads_credentials_present
  - campaign_metrics_returned_or_clear_failure
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.google_ads
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_ads
  output_contract: google_ads_data_pull
  risk_policy: read_only_no_mutation
---

# Google Ads Read-Only Data Pull

## Purpose

Pull Google Ads account/campaign performance data for the connected/customer account and return a plain read-only report artifact.

## Activation

Use this only when the user explicitly asks to read Google Ads data, for example:

- "check google ads"
- "pull google ads data"
- "show google ads performance"
- "fetch google ads campaigns"
- "read google ads metrics"

## Hard boundaries

This MVP is data access only. It is not the Google Ads copy drafting capability.

Never claim to:

- draft or generate Google Ads copy
- create campaigns
- edit campaigns
- pause/enable campaigns
- change budgets
- publish ads
- optimize automatically
- make strategic recommendations beyond describing the pulled data

## CMO response behavior

If running this capability, keep the visible reply short, such as:

```text
I’ll pull the latest read-only Google Ads campaign data and summarize what is available.
RUN: marketing.channel.google_ads.performance.read
```

Do not expose credentials, developer tokens, access tokens, backend logs, or provider details.

## Outcome contract

Artifact type: `intelligence_artifact`
Block/output contract: `google_ads_data_pull`
Platform: `google_ads`
Risk policy: `read_only_no_mutation`

The module returns a `google_ads_data_pull` block and markdown content containing:

- customer/account identifier
- date range
- campaign rows
- total impressions, clicks, cost, and conversions
- read-only note confirming no changes were made
- `read_only: true`
- `changed_resources: []`

This contract must never return ad copy, campaign drafts, publish results, budget changes, campaign status changes, or optimization actions. Google Ads copy requests route to `marketing.channel.google_ads.search_text.draft`; other actions require separate capabilities with their own approval/risk contracts.

## Credential contract

This third-party plugin uses host-injected environment values from `channel.json`:

- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_DEFAULT_CUSTOMER_ID`

Optional request/brief fields for advanced tests:

- `google_ads_login_customer_id`
- `google_ads_api_version` default `v21`
