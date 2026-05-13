# Google Ads Channel Plugin

Third-party Google Ads plugin for BOS/Klaroha. This plugin lives entirely under:

```text
api/plugins/google-ads/
```

Current installed capabilities are still no-mutation:

1. a read-only account discovery artifact that returns `google_ads_account_inventory`
2. a read-only campaign report artifact that returns `google_ads_campaign_report`
3. a read-only performance data pull that returns a `google_ads_data_pull` intelligence artifact
4. a Google Search text ad copy drafter that returns a `google_search_ad_draft` draft artifact

Approved product direction is full Google Ads control through plugin-owned, approval-gated capabilities. The current package does **not** yet create campaigns, edit campaigns, pause/enable campaigns, change budgets, publish ads, or optimize automatically. Those actions must be added as separate capabilities with approved source artifacts, selected change IDs, mutation audit, and second confirmation for destructive/high-risk actions.

Additional plugin docs:

- `FULL_CONTROL_SPEC.md` — approved full-control reverse-spec from `sample/google_ads_full_control_v1.md`.
- `MUTATION_INVENTORY.md` — inventory of existing Google Ads connector methods and migration plan behind approval-gated plugin capabilities.
- `sample/full_control_capability_outputs_v1.md` — concrete output samples for future read/write/edit/delete/optimization capabilities.
- `CAPABILITY_CONTRACTS.md` — detailed contracts for currently shipped capabilities and full-control boundaries.
- `TESTING.md` — plugin-focused test commands and manual smoke-test expectations.
- `CHANGELOG.md` — version history.

## Reference inspiration

This plugin may use implementation lessons from [`cohnen/mcp-google-ads`](https://github.com/cohnen/mcp-google-ads) for Google Ads API ergonomics only. That project is MIT licensed and is useful as a reference for customer ID normalization, token refresh flow, account discovery, GAQL examples, and practical reporting surfaces.

BOS does **not** adopt its MCP server shape here. Do not add MCP tools, MCP runtime dependencies, or BOS router/skill-loader changes for this plugin track. Plugin-local `SKILL.md` activation contracts are allowed because they are part of the plugin capability package. The BOS plugin remains a host-injected channel plugin that returns structured Workspace artifacts.

Adopted hardening from that review:

- Robust customer ID normalization for common copy/paste shapes such as `123-456-7890`, `customers/1234567890`, and quoted IDs.
- Explicit no-mutation reporting/drafting boundary stays intact for current capabilities.
- GAQL/query ideas are treated as future plugin report expansions, not permission to mutate campaigns.
- Google Ads copy requests now route to a draft artifact capability instead of the read-only data-pull capability.
- Full-control actions must be implemented as approval-gated plugin capabilities, not router/core shortcuts.

## Capabilities

| Capability ID | Job | Artifact type | Output contract | Mutates Google Ads? |
|---|---|---|---|---|
| `marketing.channel.google_ads.account.discover` | `marketing.optimize` | `intelligence_artifact` | `google_ads_account_inventory` | No |
| `marketing.channel.google_ads.campaigns.read` | `marketing.optimize` | `intelligence_artifact` | `google_ads_campaign_report` | No |
| `marketing.channel.google_ads.performance.read` | `marketing.optimize` | `intelligence_artifact` | `google_ads_data_pull` | No |
| `marketing.channel.google_ads.search_text.draft` | `marketing.execute` | `draft_artifact` | `google_search_ad_draft` | No |

Full-control roadmap capability families are defined in `FULL_CONTROL_SPEC.md`: account discovery, campaign reads, search-term/keyword reads, budget health, optimization plans, approved apply-selected mutations, and high-risk/destructive actions with second confirmation.

CMO-facing jobs:

```text
marketing.optimize
marketing.execute
```

## Routing contract

The plugin owns its routing through plugin-local `SKILL.md` files only. Do not change BOS routers, BOS skill loader code, or BOS hardcoded phrase logic to support this plugin.

| User asks | Expected capability | Expected artifact | Notes |
|---|---|---|---|
| `list google ads accounts` | `marketing.channel.google_ads.account.discover` | Account Inventory / `google_ads_account_inventory` | Read-only accessible customer/account inventory. |
| `list google ads campaigns` | `marketing.channel.google_ads.campaigns.read` | Campaign Report / `google_ads_campaign_report` | Read-only campaign metrics and status report. |
| `show me google ads` | `marketing.channel.google_ads.performance.read` | Marketing Intelligence / `google_ads_data_pull` | Read-only account/campaign data pull. |
| `check google ads performance` | `marketing.channel.google_ads.performance.read` | Marketing Intelligence / `google_ads_data_pull` | Read-only account/campaign data pull. |
| `can you generate a google ads copy` | `marketing.channel.google_ads.search_text.draft` | Google Ad Draft / `google_search_ad_draft` | Draft copy artifact only; no API mutation. |
| `write google ad copy` | `marketing.channel.google_ads.search_text.draft` | Google Ad Draft / `google_search_ad_draft` | Draft copy artifact only; no API mutation. |
| `change google ads budget` | none in the current shipped capabilities | none | Full-control direction requires a separate approval-gated action capability. |
| `pause google ads campaign` | none in the current shipped capabilities | none | Full-control direction requires a separate approval-gated action capability. |

Regression fixed in v0.2.0: Google Ads copy-generation requests must not route to the read-only performance capability, because that produces a Marketing Intelligence artifact instead of a draft ad copy artifact.

## Required environment variables

Declared in `channel.json` as plugin-local platform vars:

```text
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_DEFAULT_CUSTOMER_ID=
```

Optional environment/request/brief fields for MCC or advanced tests:

```text
GOOGLE_ADS_LOGIN_CUSTOMER_ID=
google_ads_login_customer_id=
google_ads_api_version=v21
```

Notes:

- `GOOGLE_ADS_DEFAULT_CUSTOMER_ID` may include or omit dashes.
- Customer IDs are normalized from common copy/paste formats like `123-456-7890`, `customers/1234567890`, quoted IDs, and shorter numeric strings that need left-padding.
- The performance read capability exchanges `GOOGLE_ADS_REFRESH_TOKEN` for a short-lived access token at execution time.
- The copy draft capability does not need Google Ads credentials because it creates a draft artifact only and does not call Google Ads APIs.
- This plugin does not add core OAuth UI/support for Google Ads. That is deliberate: the test is whether a plugin can be discovered and execute without changing BOS core.

## Example CMO requests

Read-only data pull:

```text
check google ads performance
```

Expected behavior:

```text
I’ll pull the latest read-only Google Ads campaign data and summarize what is available.
```

Internal dispatch:

```text
RUN: marketing.channel.google_ads.performance.read
```

Draft copy:

```text
can you generate a google ads copy
```

Expected behavior:

```text
I’ll create a Google Ads copy draft as a reviewable Workspace artifact. It will not be published or applied to the account.
```

Internal dispatch:

```text
RUN: marketing.channel.google_ads.search_text.draft
```

The read-only data-pull capability explicitly excludes Google Ads copy/draft requests so this request does not create a Marketing Intelligence artifact by mistake. The draft capability explicitly excludes performance/read/report requests so `show me google ads` continues to produce a data-pull artifact.

## Improvement backlog inspired by the reference

Keep these plugin-only and artifact-returning:

1. Account discovery artifact: list accessible customer IDs/names so setup can verify the chosen account.
2. Ad creative performance artifact: RSA/ad-group-ad rows with impressions, clicks, conversions, CTR, and cost.
3. Keyword/search-term intelligence artifact: terms, match types, quality score, impression share, and wasted-spend candidates.
4. Budget/bid health artifact: read-only budget utilization and bidding-strategy diagnostics.
5. Optional raw GAQL diagnostic artifact for admin/debug users only, with allowlisted query templates and no mutation endpoints.
6. Optimization plan artifact with proposed changes and selected-change approval.
7. Approval-gated mutation result artifact with changed resources, failures, before/after snapshots, and rollback notes.

Do not add mutation behavior to the existing read/draft capabilities. Campaign create/edit/pause/budget mutations must be separate approval-gated action capabilities with risk contracts, as specified in `FULL_CONTROL_SPEC.md`.

## Output shape — Google Ads copy draft

```text
# Google Ads Search Text Draft

Status: draft for review — not published
Display URL: motormoto.example

## Responsive search ad headlines
1. MotorMoto Official
2. Bikes For Riders
3. Find Your Next Bike
...

## Descriptions
1. Explore motorcycles from MotorMoto. Get clear options and helpful next steps today.
...

Read-only/draft note: this artifact is copy only. No campaigns, ads, keywords, bids, or budgets were changed.
```

Structured block:

```json
{
  "type": "google_search_ad_draft",
  "status": "draft",
  "platform": "google_ads",
  "channel": "search",
  "format": "responsive_search_ad",
  "headlines": [{ "text": "MotorMoto Official", "pinned": false }],
  "descriptions": [{ "text": "Explore motorcycles from MotorMoto.", "pinned": false }],
  "read_only": true,
  "changed_resources": [],
  "allowed_actions": ["approve", "request_changes", "dismiss"],
  "risk_level": "requires_approval"
}
```

## Output shape — performance read

```text
# Google Ads Data Pull

Customer: 1234567890
Date range: LAST_30_DAYS
Campaigns returned: 2

| Campaign | Status | Impressions | Clicks | Cost | Conversions |
|---|---:|---:|---:|---:|---:|
| Brand Search | ENABLED | 1,240 | 92 | $188.44 | 6 |
| Demand Capture | ENABLED | 4,810 | 231 | $742.10 | 18 |

Totals:
- Impressions: 6,050
- Clicks: 323
- Cost: $930.54
- Conversions: 24

Read-only note: no campaigns, ads, keywords, bids, or budgets were changed.
```
