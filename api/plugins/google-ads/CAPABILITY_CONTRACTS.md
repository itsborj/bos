# Google Ads Plugin Capability Contracts

This document is plugin-owned. It describes only capabilities shipped by `api/plugins/google-ads/` and the safety boundary for the approved full-control direction. See `FULL_CONTROL_SPEC.md` for the reverse-spec from `sample/google_ads_full_control_v1.md`.

## Non-negotiable plugin boundary

This plugin is a third-party channel plugin. It must not require changes to BOS core, BOS routers, BOS skill-loader internals, MCP runtime, or global prompt hardcoding.

Allowed plugin-owned surfaces:

- `channel.json`
- plugin-local `SKILL.md`
- plugin-local `module.py`
- plugin-local templates
- plugin-local tests/docs

## Current shipped capabilities

The currently installed capabilities are read/draft only. They must not mutate Google Ads.

## `marketing.channel.google_ads.account.discover`

Purpose: discover accessible Google Ads accounts/customer IDs and return an account inventory artifact.

Must return:

```json
{
  "type": "google_ads_account_inventory",
  "status": "succeeded",
  "accounts": [],
  "account_count": 0,
  "read_only": true,
  "changed_resources": []
}
```

Must not:

- change account settings
- select or remap a brand account automatically
- create/edit/pause/delete campaigns
- expose tokens or developer credentials

## `marketing.channel.google_ads.campaigns.read`

Purpose: read Google Ads campaign metrics and return a campaign report artifact.

Must return:

```json
{
  "type": "google_ads_campaign_report",
  "status": "succeeded",
  "customer_id": "1234567890",
  "date_range": "LAST_30_DAYS",
  "campaigns": [],
  "totals": {},
  "read_only": true,
  "changed_resources": []
}
```

Must not:

- create/edit/pause/enable/remove campaigns
- change budgets, bids, keywords, ads, assets, or targeting
- apply optimization recommendations automatically

## `marketing.channel.google_ads.performance.read`

Purpose: read Google Ads account/campaign metrics and return an intelligence artifact.

Activation examples:

```text
show me google ads
check google ads performance
pull google ads data
read google ads metrics
```

Must return:

```json
{
  "type": "google_ads_data_pull",
  "status": "succeeded",
  "customer_id": "1234567890",
  "date_range": "LAST_30_DAYS",
  "campaigns": [],
  "campaign_count": 0,
  "read_only": true,
  "changed_resources": []
}
```

Must not:

- draft Google Ads copy
- generate campaign drafts
- publish ads
- create/edit/pause/enable campaigns
- change budgets, bids, keywords, assets, or targeting

## `marketing.channel.google_ads.search_text.draft`

Purpose: generate Google Ads responsive search ad copy as a draft artifact.

Activation examples:

```text
can you generate a google ads copy
write google ad copy
draft google ads copy
show me sample google ads copy
```

Must return:

```json
{
  "type": "google_search_ad_draft",
  "status": "draft",
  "platform": "google_ads",
  "channel": "search",
  "format": "responsive_search_ad",
  "display_url": "example.com",
  "headlines": [{ "text": "Headline", "pinned": false }],
  "descriptions": [{ "text": "Description", "pinned": false }],
  "read_only": true,
  "changed_resources": [],
  "allowed_actions": ["approve", "request_changes", "dismiss"],
  "risk_level": "requires_approval"
}
```

Quality gates:

- at least 10 unique headlines
- at least 4 unique descriptions
- headlines <= 30 characters
- descriptions <= 90 characters
- no unsupported proof, fake discounts, or mutation claims
- explicit not-published/no-mutation boundary in content

Must not:

- call Google Ads APIs
- claim the ad is live
- create or edit any campaign/ad/keyword/budget
- return a performance/intelligence artifact

## Full-control direction

Approved direction: Google Ads becomes a full-control specialist through plugin-owned, approval-gated capabilities.

Future mutation-capable capabilities must:

- require an approved source artifact/run
- apply only selected `change_id` values
- return `changed_resources`, `unchanged_resources`, and `failed_changes`
- include audit metadata and before/after snapshots where available
- block customer/account mismatches
- require second confirmation for destructive or high-risk actions
- never mutate from vague prompts such as "fix my Google Ads"

The existing read/draft capabilities remain no-mutation. Do not add Google Ads-specific routing or safety logic to BOS chat/router code.

## Issue fixed by v0.2.0

Before v0.2.0, a prompt such as:

```text
can you generate a google ads copy
```

could be answered conversationally while still dispatching the read-only performance capability, causing a Marketing Intelligence artifact to appear.

The fix is plugin-local:

1. Add a dedicated Google Ads copy draft capability.
2. Exclude copy/draft triggers from the read-only capability.
3. Exclude performance/read/report triggers from the draft capability.
4. Register both capability IDs in `channel.json`.
