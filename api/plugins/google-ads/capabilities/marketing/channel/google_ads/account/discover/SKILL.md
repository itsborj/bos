---
id: marketing.channel.google_ads.account.discover
name: Google Ads Account Discovery
description: Read-only Google Ads account discovery. Use only when the user explicitly asks to check, list, discover, or verify accessible Google Ads accounts, customer IDs, MCC/client accounts, or connector readiness. This capability returns an account inventory artifact and never changes account settings, campaigns, budgets, ads, keywords, bids, or targeting.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.google_ads.account.discover
requires_intent:
  - diagnostic
  - discussion
triggers:
  - google ads accounts
  - google ads account discovery
  - discover google ads accounts
  - list google ads accounts
  - check google ads accounts
  - verify google ads account
  - google ads customer id
  - google ads customer ids
  - google ads mcc
  - google ads manager account
excluded_triggers:
  - what can you do
  - what can you do with google ads
  - google ads capabilities
  - google ads copy
  - google ad copy
  - google ads performance
  - google ads report
  - change google ads budget
  - pause google ads campaign
  - delete google ads campaign
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.google_ads.account.discover
output_contract:
  - google_ads_account_inventory
quality_gates:
  - read_only_only
  - no_account_or_campaign_mutation
  - google_ads_credentials_present
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.google_ads
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_ads
  output_contract: google_ads_account_inventory
  risk_policy: read_only_no_mutation
---

# Google Ads Account Discovery

## Purpose

Return a read-only inventory of accessible Google Ads customer accounts so setup and brand/account mapping issues are visible before optimization or mutation work.

## Hard boundaries

Never:

- change account settings
- create/edit/pause/delete campaigns
- change budgets, bids, keywords, ads, assets, or targeting
- expose OAuth tokens, refresh tokens, developer tokens, or raw secrets

## CMO response behavior

If running this capability, keep the visible reply short and append the hidden directive:

```text
I’ll check which Google Ads accounts are accessible and return a read-only account inventory.
RUN: marketing.channel.google_ads.account.discover
```

## Outcome contract

Artifact type: `intelligence_artifact`
Block/output contract: `google_ads_account_inventory`
Platform: `google_ads`
Risk policy: `read_only_no_mutation`

The module returns:

- accessible customer IDs
- account names when available
- manager/test/status/currency/time zone when available
- `read_only: true`
- `changed_resources: []`
