# Google Ads Provider Inventory + Plugin Migration Plan

**Date:** 2026-05-13  
**Related spec:** `FULL_CONTROL_SPEC.md`  
**Approved sample:** `sample/google_ads_full_control_v1.md`  
**Purpose:** identify existing Google Ads connector surfaces early and plan how full-control behavior moves behind plugin-owned, approval-gated capabilities.

## Current source files

| File | Role | Boundary concern |
|---|---|---|
| `api/plugins/google-ads/capabilities/.../performance/read/module.py` | Active plugin read-only REST data pull | OK: plugin-owned, no mutation. |
| `api/plugins/google-ads/capabilities/.../search_text/draft/module.py` | Active plugin deterministic RSA draft | OK: plugin-owned, no mutation. |
| `api/providers/google_ads.py` | Core Google Ads connector using official client library | Contains both reads and mutations; should not become the product capability boundary. |
| `api/providers/google_ads_mock.py` | Fixture-backed mock connector | Contains mock read and mock mutation surfaces; useful for tests but must mirror approval-gated plugin behavior. |
| `api/providers/fixtures/google_ads_demo.json` | Mock campaign/search-term/keyword fixture data | Useful for read/optimization tests. |

## Inventory: `api/providers/google_ads.py`

| Method | Type | Current risk | Plugin migration target |
|---|---:|---|---|
| `GoogleAdsConfig.from_env()` | credential setup | Global env-based only; not brand-scoped | Keep for single-brand plugin MVP, then replace/augment with plugin-declared brand-scoped connection. |
| `LiveGoogleAdsConnector.__init__()` | connector setup | Core imports official Google Ads SDK | Move connector implementation into plugin or expose only a generic host connector hook. |
| `list_accessible_customers()` | read | Safe read | `marketing.channel.google_ads.account.discover` → `google_ads_account_inventory`. |
| `list_manager_clients(customer_id)` | read | Safe read; MCC-sensitive | `marketing.channel.google_ads.account.discover` with manager/client account selection artifact. |
| `weekly_performance_summary(customer_id)` | read | Safe read but narrow date range | Replace with plugin read capabilities: campaigns/read and campaign report. |
| `search_terms(customer_id, campaign_id=None)` | read/optimization input | Safe read; feeds negative keyword plans | `marketing.channel.google_ads.search_terms.read` and `negative_keywords.draft`. |
| `keyword_performance(customer_id, campaign_id=None)` | read/optimization input | Safe read | `marketing.channel.google_ads.keywords.read` and optimization plan. |
| `optimization_suggestions(customer_id)` | read/recommendation input | Safe read from Google recommendations | `marketing.channel.google_ads.recommendations.read`; no auto-apply. |
| `budget_health(customer_id)` | read/optimization input | Safe read; recommendations imply spend changes | `marketing.channel.google_ads.budget_health.read`; proposed budget changes only in draft/plan artifact. |
| `list_campaigns(customer_id)` | read | Safe read | `marketing.channel.google_ads.campaigns.read`. |
| `update_campaign_status(customer_id, campaign_id, status)` | mutation | Can pause/enable campaigns | `marketing.channel.google_ads.campaign_status.update`, Tier 3, approved selected change only. |
| `update_campaign_budget(customer_id, campaign_id, daily_budget_usd)` | mutation | Spend-affecting; must enforce caps | `marketing.channel.google_ads.budget.update`, Tier 3 or Tier 4 depending delta/cap. |
| `live_google_ads_available()` | readiness | Env-based readiness only | Plugin readiness/capability card should report connector readiness and missing setup. |

## Inventory: `api/providers/google_ads_mock.py`

| Method/function | Type | Plugin migration target |
|---|---:|---|
| `list_accessible_customers()` | read | account discovery tests. |
| `search()` | read | campaign report tests. |
| `get_resource_metadata()` | read/debug | admin/debug only if kept. |
| `search_terms()` | read | search-term report and negative keyword plan tests. |
| `keyword_performance()` | read | keyword report tests. |
| `optimization_suggestions()` | read | recommendations digest tests. |
| `budget_health()` | read | budget health report tests. |
| `list_campaigns()` | read | campaign inventory tests. |
| `update_campaign_status()` | mock mutation | approved status update action tests only; should reject direct/vague mutation in plugin wrapper. |
| `update_campaign_budget()` | mock mutation | approved budget update action tests only; should enforce caps in plugin wrapper. |

## Migration principles

1. **Do not expose `api/providers/google_ads.py` directly as a CMO capability.**
   It is connector plumbing, not the SKILL/module contract.

2. **Plugin modules own behavior and safety.**
   Each plugin capability must declare activation, output contract, risk policy, required approvals, and quality gates in local `SKILL.md`.

3. **Connector code can be reused only behind the plugin boundary.**
   Acceptable options:
   - move Google Ads connector classes into `api/plugins/google-ads/lib/`, or
   - keep temporary core connector code as an internal implementation detail while plugin modules are the only dispatchable mutation surface.

4. **All mutation methods need plugin wrappers that enforce source artifact approval.**
   `update_campaign_status()` and `update_campaign_budget()` must never be callable from a natural-language run payload alone.

5. **Read expansion comes before write expansion.**
   Build read artifacts first so optimization plans have evidence.

6. **Mutation allowlist starts small.**
   Initial approved actions should be:
   - add negative keyword
   - update campaign budget
   - pause/enable campaign

7. **Destructive actions are not v1.**
   Remove/delete actions wait until second-confirmation UI and audit/rollback contracts are validated.

## Proposed plugin capability mapping

### Read / Diagnose

| Capability ID | Uses existing method(s) | Artifact |
|---|---|---|
| `marketing.channel.google_ads.account.discover` | `list_accessible_customers`, `list_manager_clients` | `google_ads_account_inventory` |
| `marketing.channel.google_ads.campaigns.read` | `list_campaigns`, campaign GAQL | `google_ads_campaign_report` |
| `marketing.channel.google_ads.search_terms.read` | `search_terms` | `google_ads_search_terms_report` |
| `marketing.channel.google_ads.keywords.read` | `keyword_performance` | `google_ads_keyword_report` |
| `marketing.channel.google_ads.budget_health.read` | `budget_health` | `google_ads_budget_health_report` |
| `marketing.channel.google_ads.recommendations.read` | `optimization_suggestions` | `google_ads_recommendations_digest` |

### Draft / Recommend

| Capability ID | Inputs | Artifact |
|---|---|---|
| `marketing.channel.google_ads.optimization.plan` | campaign report, search terms, keywords, budget health, recommendations | `google_ads_optimization_plan` |
| `marketing.channel.google_ads.negative_keywords.draft` | search terms | `google_ads_negative_keyword_plan` |
| `marketing.channel.google_ads.budget_changes.draft` | budget health + campaign performance | `google_ads_budget_change_plan` |
| `marketing.channel.google_ads.campaign.draft` | CMO campaign intent + brand memory | `google_ads_campaign_draft` |

### Approved Write / Edit

| Capability ID | Underlying operation | Approval tier |
|---|---|---:|
| `marketing.channel.google_ads.actions.apply_selected` | dispatch selected approved changes by action allowlist | Tier 3 |
| `marketing.channel.google_ads.campaign_status.update` | `update_campaign_status` | Tier 3 |
| `marketing.channel.google_ads.budget.update` | `update_campaign_budget` | Tier 3/Tier 4 depending cap |
| `marketing.channel.google_ads.negative_keywords.create` | new plugin connector method needed | Tier 3 |

## Required safeguards before any mutation capability ships

- Approved source artifact/run exists.
- Approved `change_id` exists in that artifact.
- Active brand/customer matches the source artifact customer.
- Action is in the mutation allowlist.
- Proposed `before`/`after` values are present for editable resources.
- Budget delta passes cap policy or second confirmation.
- Destructive actions require second confirmation and are disabled until UI exists.
- Result artifact separates `changed_resources`, `unchanged_resources`, and `failed_changes`.
- Audit block stores request metadata and rollback notes.

## Early implementation note

The current plugin read module uses REST/urllib and host-injected env vars. The core provider uses the official `google-ads` Python client. For full control, prefer one plugin-local connector abstraction so all read/write modules share:

- customer ID normalization
- optional login customer ID handling
- token refresh
- API request ID capture where available
- partial failure parsing
- safe error messages with no credentials

Do not add Google Ads-specific FastAPI routes or CMO router rules for these capabilities.
