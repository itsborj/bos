---
id: marketing.channel.google_analytics.performance.read
name: Google Analytics Read-Only Data Pull
description: Read-only GA4 data access MVP. Use only when the user explicitly asks to check, pull, fetch, read, show, compare, or summarize Google Analytics or GA4 traffic, acquisition, landing-page, engagement, or conversion performance data. This plugin does not create audiences, edit properties, change conversions, alter tags, optimize campaigns, or mutate any external resource.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.google_analytics.performance.read
requires_intent:
  - diagnostic
  - generation
  - discussion
triggers:
  - check google analytics
  - check ga4
  - pull google analytics data
  - pull ga4 data
  - fetch google analytics data
  - fetch ga4 data
  - read google analytics
  - read ga4
  - show google analytics data
  - show ga4 data
  - show google analytics performance
  - show ga4 performance
  - google analytics report
  - ga4 report
  - google analytics traffic
  - ga4 traffic
  - landing page performance
  - traffic sources
  - acquisition performance
  - conversion performance
excluded_triggers:
  - what can you do
  - what can you do with google analytics
  - can you help with google analytics
  - google analytics capabilities
  - ga4 capabilities
  - create google analytics audience
  - create ga4 audience
  - edit google analytics property
  - change google analytics conversion
  - configure google analytics
  - setup google analytics
  - install google analytics
  - setup tag manager
  - change campaign budget
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.google_analytics.performance.read
output_contract:
  - google_analytics_data_pull
quality_gates:
  - read_only_only
  - no_property_audience_tag_or_conversion_mutation
  - google_analytics_credentials_present
  - metrics_returned_or_clear_failure
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.google_analytics
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_analytics
  output_contract: google_analytics_data_pull
  risk_policy: read_only_no_mutation
---

# Google Analytics Read-Only Data Pull

## Purpose

Pull GA4 performance data for the configured property and return a read-only Analytics Intelligence artifact.

## Activation

Use this only when the user explicitly asks to read Google Analytics or GA4 data, for example:

- "check Google Analytics"
- "pull GA4 data"
- "show Google Analytics performance"
- "compare GA traffic for the last 30 days"
- "show landing page performance"
- "what traffic sources drove conversions"

## Hard boundaries

This MVP is data access only.

Never claim to:

- create audiences
- edit GA properties
- alter conversion/key-event settings
- configure tags or triggers
- change campaign budgets
- publish, pause, or enable campaigns
- mutate any Google Analytics, Google Ads, GTM, site, or campaign resource
- make recommendations unsupported by pulled data

## CMO response behavior

If running this capability, keep the visible reply short, such as:

```text
I’ll pull a read-only GA4 performance snapshot and create an Analytics Intelligence artifact for review.
RUN: marketing.channel.google_analytics.performance.read
```

Do not expose credentials, refresh tokens, access tokens, backend logs, property admin details, or provider internals.

## Outcome contract

Artifact type: `intelligence_artifact`
Block/output contract: `google_analytics_data_pull`
Platform: `google_analytics`
Risk policy: `read_only_no_mutation`

The module returns a `google_analytics_data_pull` block and markdown content containing:

- GA4 property identifier
- date range
- summary metrics
- traffic source rows
- landing page rows
- read-only note confirming no changes were made
- `read_only: true`
- `changed_resources: []`

This contract must never return audience creation, property edits, tag changes, conversion setting changes, campaign budget/status changes, or write-action results. Those require separate capabilities with their own approval/risk contracts.

## Credential contract

This third-party plugin uses host-injected environment values from `channel.json`:

- `GOOGLE_ANALYTICS_CLIENT_ID`
- `GOOGLE_ANALYTICS_CLIENT_SECRET`
- `GOOGLE_ANALYTICS_REFRESH_TOKEN`
- `GOOGLE_ANALYTICS_PROPERTY_ID`

Optional request/brief fields for advanced tests:

- `google_analytics_property_id`
- `google_analytics_date_range`
