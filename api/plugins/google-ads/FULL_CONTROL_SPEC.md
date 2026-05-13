# Google Ads Full Control — Reverse Spec v1

**Date:** 2026-05-13  
**BITE source sample:** `sample/google_ads_full_control_v1.md`  
**Status:** Reverse-spec from approved sample  
**Scope:** Google Ads plugin only. No CMO chat/router hardcoding.

## 1. Target Outcome

Google Ads becomes a full-control paid-search specialist behind the BOS/Klaroha plugin boundary.

The user-facing promise is not “a Google Ads dashboard.” It is:

```text
The CMO identifies issues, creates reviewable recommendations, applies only approved changes, and audits exactly what changed.
```

The specialist supports:

- `marketing.optimize` — diagnose performance and waste.
- `marketing.execute` — draft new campaign/ad/keyword/budget work.
- `approved_action` — apply selected, approved external mutations.

## 2. Non-Negotiable Boundaries

1. Google Ads behavior stays in `api/plugins/google-ads/`.
2. `routers/chat.py` and `skills/router.py` must not gain Google Ads-specific phrase logic.
3. CMO chat may explain and link artifacts, but native Google Ads output belongs in Workspace/Stream artifacts.
4. Every mutation must be approval-gated.
5. Destructive actions require second confirmation.
6. Broad/vague prompts must not mutate the account.
7. Every external mutation must return `changed_resources` and audit metadata.
8. Full-control does not mean autonomous spend changes.

## 3. Control Ladder

### Tier 0 — Capability / Readiness

Purpose: answer what the Google Ads specialist can do and whether it is ready.

Artifact:

```json
{
  "artifact_type": "capability_card",
  "block_type": "google_ads_capability_card",
  "status": "connected|needs_setup|limited",
  "supported_jobs": ["marketing.optimize", "marketing.execute", "approved_action"],
  "access_levels": {
    "read": true,
    "draft": true,
    "approved_write": true,
    "destructive_second_confirm": true,
    "automatic_spend_changes": false
  },
  "missing_setup": []
}
```

Tool action: none unless readiness checks are implemented as explicit read-only connector checks.

### Tier 1 — Read / Diagnose

Purpose: inspect account state and performance without changing anything.

Capabilities to expose as plugin-local SKILL/module packages:

- `marketing.channel.google_ads.account.discover`
- `marketing.channel.google_ads.campaigns.read`
- `marketing.channel.google_ads.search_terms.read`
- `marketing.channel.google_ads.keywords.read`
- `marketing.channel.google_ads.ads.read`
- `marketing.channel.google_ads.budget_health.read`
- `marketing.channel.google_ads.recommendations.read`

Artifacts:

- `google_ads_account_inventory`
- `google_ads_campaign_report`
- `google_ads_search_terms_report`
- `google_ads_keyword_report`
- `google_ads_ad_performance_report`
- `google_ads_budget_health_report`
- `google_ads_recommendations_digest`

Required output fields:

```json
{
  "artifact_type": "intelligence_artifact",
  "block_type": "google_ads_*_report",
  "status": "succeeded|failed|partial",
  "customer_id": "1234567890",
  "date_range": "LAST_30_DAYS",
  "read_only": true,
  "changed_resources": [],
  "rows": [],
  "totals": {},
  "source": "google_ads_api"
}
```

Forbidden:

- Create/update/remove resources.
- Return proposed mutation payloads as if they have already been applied.
- Claim recommendations are approved actions.

### Tier 2 — Draft / Recommend

Purpose: turn diagnostics into reviewable proposed changes.

Capabilities:

- `marketing.channel.google_ads.optimization.plan`
- `marketing.channel.google_ads.negative_keywords.draft`
- `marketing.channel.google_ads.budget_changes.draft`
- `marketing.channel.google_ads.campaign.draft`
- `marketing.channel.google_ads.search_text.draft` existing capability should remain draft-only.
- `marketing.channel.google_ads.assets.draft`

Primary artifact:

```json
{
  "artifact_type": "decision_artifact",
  "block_type": "google_ads_optimization_plan",
  "status": "pending_review",
  "risk_level": "approval_required",
  "customer_id": "1234567890",
  "summary": "Found 4 issues that may be wasting spend.",
  "findings": [],
  "proposed_changes": [],
  "allowed_actions": ["approve_selected_changes", "revise_plan", "dismiss"],
  "forbidden_actions": [
    "auto_apply_all",
    "change_unlisted_campaigns",
    "increase_total_daily_budget_without_budget_cap",
    "delete_campaign_without_second_confirmation"
  ]
}
```

Proposed change schema:

```json
{
  "change_id": "chg_001",
  "action": "add_negative_keyword|update_campaign_budget|pause_campaign|enable_campaign|create_ad|update_ad|create_campaign",
  "risk_tier": 2,
  "customer_id": "1234567890",
  "resource_scope": {
    "campaign_id": "789",
    "ad_group_id": "456"
  },
  "before": {},
  "after": {},
  "evidence": "Why this is recommended",
  "requires_second_confirmation": false
}
```

Forbidden:

- Calling mutate APIs.
- Expanding scope after user approval.
- Hiding budget/spend implications.

### Tier 3 — Approved Write / Edit

Purpose: apply selected proposed changes exactly as approved.

Capabilities:

- `marketing.channel.google_ads.actions.apply_selected`
- `marketing.channel.google_ads.campaign_status.update`
- `marketing.channel.google_ads.budget.update`
- `marketing.channel.google_ads.negative_keywords.create`
- `marketing.channel.google_ads.keywords.update`
- `marketing.channel.google_ads.ads.update`
- `marketing.channel.google_ads.campaign.create`

All Tier 3 capabilities must require an approved source artifact/run and selected `change_id` values. They must not accept vague natural language as the mutation payload.

Approved action request shape:

```json
{
  "source_artifact_id": "run_or_artifact_id",
  "approved_change_ids": ["chg_001", "chg_002"],
  "approval_token": "server_generated_or_approval_record_ref",
  "operator_note": "Apply these two only."
}
```

Action result artifact:

```json
{
  "artifact_type": "action_result",
  "block_type": "google_ads_mutation_result",
  "status": "succeeded|partial|failed",
  "approved_by": "operator",
  "source_artifact_id": "run_or_artifact_id",
  "applied_change_ids": [],
  "changed_resources": [],
  "unchanged_resources": [],
  "failed_changes": [],
  "audit_note": "Only approved selected changes were applied."
}
```

Forbidden:

- Apply changes not present in the approved plan.
- Apply all by default when user only approves some.
- Increase budget without explicit before/after values and budget cap context.
- Mutate a different customer/account than the source artifact customer.

### Tier 4 — Destructive / High-Risk

Purpose: handle removals and broad/high-spend actions with extra friction.

Actions in this tier include:

- remove/delete campaign
- remove/delete ad group
- remove/delete keyword/ad/asset
- bulk status changes
- budget increases above configured threshold
- cross-campaign bid strategy changes
- conversion action changes
- account-level settings changes

Requirements:

```json
{
  "requires_second_confirmation": true,
  "confirmation_phrase": "CONFIRM GOOGLE ADS CHANGE",
  "risk_tier": 4,
  "rollback_available": false,
  "human_readable_warning": "This may not be cleanly reversible."
}
```

Forbidden:

- Destructive mutation from chat-only approval.
- Deleting/removing resources from a broad prompt.
- Hiding irreversibility.

## 4. Credential and Account Safety

Full control requires a brand-scoped Google Ads connection model.

Minimum required fields:

```json
{
  "brand_id": "uuid",
  "platform": "google_ads",
  "customer_id": "1234567890",
  "login_customer_id": "0987654321|null",
  "account_name": "Client Account Name",
  "currency_code": "USD",
  "time_zone": "America/New_York",
  "status": "connected|needs_reauth|disabled",
  "access_level": "read|write|manager"
}
```

Early issue: current Google Ads plugin uses env vars via `channel.json`; this is acceptable for plugin MVP, but full control should not rely only on global env vars when managing multiple brands/clients.

Safety checks before mutation:

1. Source artifact customer ID matches active connection customer ID.
2. Brand ID matches source artifact/run brand ID.
3. Approved change IDs exist in source artifact.
4. Requested action risk tier is allowed by connection/policy.
5. Budget deltas respect configured caps.
6. Destructive actions include second confirmation.

## 5. Mutation Audit Contract

Every write/edit/delete attempt must persist enough data to answer:

- Who approved it?
- What exact change was approved?
- What API request was sent?
- What resource changed?
- What was the before/after state?
- Did any partial failure occur?
- Can it be reversed?

Required audit block fields:

```json
{
  "audit": {
    "source_artifact_id": "id",
    "approval_record_id": "id",
    "operator_id": "optional",
    "customer_id": "1234567890",
    "login_customer_id": "0987654321|null",
    "request_id": "google_ads_request_id_if_available",
    "api_version": "v21",
    "mutation_type": "campaign_budget|campaign|ad_group_criterion|ad|asset",
    "submitted_operations": [],
    "changed_resources": [],
    "before_snapshot": {},
    "after_snapshot": {},
    "rollback_plan": {
      "available": true,
      "notes": "Set budget back to previous amount."
    }
  }
}
```

## 6. Plugin Capability Layout Target

Target plugin-local tree:

```text
api/plugins/google-ads/
  channel.json
  FULL_CONTROL_SPEC.md
  capabilities/
    marketing/channel/google_ads/
      account/discover/
        SKILL.md
        module.py
        template.j2
      campaigns/read/
      campaigns/draft/
      campaign_status/update/
      budget_health/read/
      budget/update/
      search_terms/read/
      negative_keywords/draft/
      negative_keywords/create/
      keywords/read/
      keywords/update/
      ads/read/
      search_text/draft/          # existing draft-only capability
      ads/update/
      optimization/plan/
      actions/apply_selected/
```

Implementation can be incremental, but all new Google Ads behavior belongs under this plugin tree.

## 7. Existing Code Inventory and Issues

### Active plugin capabilities today

- `marketing.channel.google_ads.performance.read`
- `marketing.channel.google_ads.search_text.draft`

Current status:

- Read-only performance pull exists.
- Search ad copy draft exists.
- No active write/edit/delete plugin capability exists.

### Low-level methods already present in core provider

`api/providers/google_ads.py` currently contains methods for:

- `list_accessible_customers`
- `list_manager_clients`
- `weekly_performance_summary`
- `search_terms`
- `keyword_performance`
- `optimization_suggestions`
- `budget_health`
- `list_campaigns`
- `update_campaign_status`
- `update_campaign_budget`

Issue: mutation-capable methods exist in core provider code. Full-control direction should either:

1. move Google Ads connector logic into the plugin, or
2. expose a generic host connector hook and let the plugin own the mutation capability contract.

Do not add Google Ads-specific router/core branching.

### Manifest/docs alignment

`channel.json` now treats `GOOGLE_ADS_LOGIN_CUSTOMER_ID` as optional, matching README/module behavior:

- required: developer token, client ID, client secret, refresh token, customer ID
- optional: login customer ID unless MCC/manager access is required

### Architecture/docs alignment

Project docs now state the approved direction:

```text
Active channel plugins may include Gmail and Google Ads. Google Ads is plugin-owned and approval-gated; BOS core remains channel-agnostic.
```

## 8. Minimal Incremental Build Plan

### Step A — Documentation/manifest alignment

- Update Google Ads plugin README/contracts with full-control roadmap.
- Keep `GOOGLE_ADS_LOGIN_CUSTOMER_ID` documented as optional unless MCC/manager-account access is required.
- Update project docs/decision log to remove stale “Google Ads removed forever” interpretation.

### Step B — Read expansion

Build plugin-local read artifacts first:

1. account discovery
2. campaign list/read
3. search terms
4. keyword performance
5. budget health

No mutations.

### Step C — Optimization plan artifact

Build `marketing.channel.google_ads.optimization.plan` that returns proposed changes only.

No mutations.

### Step D — Approved apply-selected action

Build a generic `actions/apply_selected` module that only applies proposed changes from an approved artifact.

Initial mutation allowlist:

- add negative keyword
- update campaign budget
- pause/enable campaign

### Step E — Destructive actions

Add remove/delete only after second-confirmation UX and audit/rollback contracts are validated.

## 9. Test Requirements

Plugin tests must cover:

1. Capability questions do not mutate or read unless readiness check is explicit.
2. Read requests return `read_only: true` and `changed_resources: []`.
3. Draft/recommend requests return proposed changes but perform no API mutation.
4. Approved apply-selected only applies selected `change_id` values.
5. Vague requests like “fix my Google Ads” create a plan, not mutations.
6. Budget changes enforce before/after and cap policy.
7. Destructive actions fail without second confirmation.
8. Customer/account mismatch blocks mutation.
9. Partial API failures return `status: partial` with failed and changed resources separated.
10. No Google Ads-specific logic is added to CMO chat/router code.

## 10. Open Questions Before Build

1. Should full-control credentials stay env-based for single-brand deployments, or move immediately to brand-scoped OAuth/connection storage?
2. What is the default budget-change cap before second confirmation? Suggested: any increase over 20% or $25/day, whichever is larger.
3. Should `remove` actions be allowed at all in v1, or should v1 only pause/disable?
4. Should Google Ads API client usage remain via REST/urllib inside plugin modules, or use the official client library inside the plugin package?
5. What Workspace UI component will render proposed change selection and second confirmation?
