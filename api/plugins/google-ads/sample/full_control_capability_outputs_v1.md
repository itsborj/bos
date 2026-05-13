# Google Ads Full Control — Plugin Capability Output Samples v1

**Date:** 2026-05-13  
**BITE stage:** Sample outputs before implementation  
**Parent approved sample:** `sample/google_ads_full_control_v1.md`  
**Purpose:** concrete output shapes for future Google Ads read/write/edit/delete/optimization capabilities.

These are sample outputs, not implementation. They define the artifact boundaries future plugin capabilities must satisfy.

---

## 1. Capability / Readiness Card

User intent:

```text
what can you do with google ads?
```

Tool action: none, unless the user explicitly asks to check connection readiness.

Expected artifact/card:

```json
{
  "artifact_type": "capability_card",
  "block_type": "google_ads_capability_card",
  "status": "limited",
  "title": "Google Ads Specialist",
  "summary": "I can inspect Google Ads performance, draft optimization plans, and apply selected approved changes when mutation capabilities are enabled.",
  "jobs_supported": [
    "marketing.optimize",
    "marketing.execute",
    "approved_action"
  ],
  "current_access_levels": {
    "read_campaign_metrics": true,
    "draft_search_ads": true,
    "draft_optimization_plan": false,
    "apply_approved_budget_changes": false,
    "apply_approved_status_changes": false,
    "delete_or_remove_resources": false
  },
  "allowed_next_steps": [
    "Pull a read-only campaign report",
    "Draft Google search ad copy",
    "Prepare an optimization plan once the optimization capability is installed"
  ],
  "forbidden_outcomes": [
    "No account changes from a capability question",
    "No budget changes without an approved source artifact",
    "No delete/remove action without second confirmation"
  ]
}
```

---

## 2. Read Sample — Account Discovery

Capability ID target:

```text
marketing.channel.google_ads.account.discover
```

User intent:

```text
check which google ads accounts are available
```

Expected artifact:

```json
{
  "artifact_type": "intelligence_artifact",
  "block_type": "google_ads_account_inventory",
  "status": "succeeded",
  "read_only": true,
  "changed_resources": [],
  "accounts": [
    {
      "customer_id": "1234567890",
      "descriptive_name": "MotorMoto Search Account",
      "manager": false,
      "currency_code": "USD",
      "time_zone": "America/New_York",
      "status": "ENABLED",
      "test_account": false
    },
    {
      "customer_id": "0987654321",
      "descriptive_name": "Agency MCC",
      "manager": true,
      "currency_code": "USD",
      "time_zone": "America/New_York",
      "status": "ENABLED",
      "test_account": false
    }
  ],
  "recommended_setup_action": "Use customer 1234567890 for this brand unless the operator selects a different managed account.",
  "forbidden_outcomes": [
    "Do not auto-select a different brand's account",
    "Do not mutate account settings",
    "Do not reveal OAuth tokens or developer tokens"
  ]
}
```

---

## 3. Read Sample — Campaign Report

Capability ID target:

```text
marketing.channel.google_ads.campaigns.read
```

User intent:

```text
show me google ads campaign performance for the last 30 days
```

Expected artifact:

```json
{
  "artifact_type": "intelligence_artifact",
  "block_type": "google_ads_campaign_report",
  "status": "succeeded",
  "customer_id": "1234567890",
  "date_range": "LAST_30_DAYS",
  "read_only": true,
  "changed_resources": [],
  "totals": {
    "impressions": 18240,
    "clicks": 913,
    "cost": 2142.31,
    "conversions": 38,
    "ctr": 5.01,
    "cpa": 56.38
  },
  "campaigns": [
    {
      "campaign_id": "111",
      "name": "Brand Search",
      "status": "ENABLED",
      "daily_budget": 50.0,
      "cost": 448.21,
      "clicks": 212,
      "conversions": 21,
      "cpa": 21.34,
      "flag": "efficient"
    },
    {
      "campaign_id": "222",
      "name": "Generic Motorcycle Leads",
      "status": "ENABLED",
      "daily_budget": 75.0,
      "cost": 1238.66,
      "clicks": 501,
      "conversions": 7,
      "cpa": 176.95,
      "flag": "needs_review"
    }
  ],
  "allowed_actions": [
    "create_optimization_plan",
    "dismiss"
  ],
  "forbidden_outcomes": [
    "Do not pause or change campaigns from a read report",
    "Do not fabricate conversion values if unavailable",
    "Do not apply Google recommendations automatically"
  ]
}
```

---

## 4. Optimization Sample — Proposed Changes Only

Capability ID target:

```text
marketing.channel.google_ads.optimization.plan
```

User intent:

```text
find waste and tell me what to change
```

Expected artifact:

```json
{
  "artifact_type": "decision_artifact",
  "block_type": "google_ads_optimization_plan",
  "status": "pending_review",
  "risk_level": "approval_required",
  "customer_id": "1234567890",
  "summary": "Found 3 optimization opportunities: wasted search-term spend, one budget-capped efficient campaign, and one low-quality keyword cluster.",
  "findings": [
    {
      "finding_id": "fnd_001",
      "severity": "high",
      "issue": "Search terms with spend and zero conversions",
      "evidence": "$218.42 spend, 0 conversions across 14 terms in LAST_30_DAYS",
      "recommended_action": "Add selected terms as negative keywords",
      "proposed_change_ids": ["chg_001", "chg_002"]
    },
    {
      "finding_id": "fnd_002",
      "severity": "medium",
      "issue": "Efficient campaign capped by budget",
      "evidence": "Brand Search CPA is $21.34 and budget utilization is 98% before noon",
      "recommended_action": "Increase daily budget from $50 to $65",
      "proposed_change_ids": ["chg_003"]
    }
  ],
  "proposed_changes": [
    {
      "change_id": "chg_001",
      "action": "add_negative_keyword",
      "risk_tier": 3,
      "customer_id": "1234567890",
      "resource_scope": {
        "campaign_id": "222",
        "ad_group_id": "333"
      },
      "before": {
        "negative_keyword_exists": false
      },
      "after": {
        "keyword": "free motorcycle parts",
        "match_type": "PHRASE"
      },
      "evidence": "$74.10 spend, 0 conversions",
      "requires_second_confirmation": false
    },
    {
      "change_id": "chg_003",
      "action": "update_campaign_budget",
      "risk_tier": 3,
      "customer_id": "1234567890",
      "resource_scope": {
        "campaign_id": "111"
      },
      "before": {
        "daily_budget": 50.0
      },
      "after": {
        "daily_budget": 65.0
      },
      "evidence": "Efficient CPA and budget capped",
      "requires_second_confirmation": false
    }
  ],
  "allowed_actions": [
    "approve_selected_changes",
    "revise_plan",
    "dismiss"
  ],
  "forbidden_outcomes": [
    "Do not apply all changes automatically",
    "Do not change campaigns outside listed resource_scope",
    "Do not exceed budget cap without second confirmation"
  ]
}
```

---

## 5. Write/Edit Sample — Apply Selected Approved Changes

Capability ID target:

```text
marketing.channel.google_ads.actions.apply_selected
```

User intent after reviewing the plan:

```text
approve chg_001 and chg_003 only
```

Expected action request envelope:

```json
{
  "source_artifact_id": "run_abc123",
  "approved_change_ids": ["chg_001", "chg_003"],
  "approval_record_id": "approval_789",
  "operator_note": "Apply the negative keyword and budget increase only."
}
```

Expected action-result artifact:

```json
{
  "artifact_type": "action_result",
  "block_type": "google_ads_mutation_result",
  "status": "succeeded",
  "approved_by": "operator",
  "source_artifact_id": "run_abc123",
  "applied_change_ids": ["chg_001", "chg_003"],
  "changed_resources": [
    {
      "change_id": "chg_001",
      "resource_type": "negative_keyword",
      "resource_name": "customers/1234567890/adGroupCriteria/333~9001",
      "action": "created",
      "keyword": "free motorcycle parts",
      "match_type": "PHRASE"
    },
    {
      "change_id": "chg_003",
      "resource_type": "campaign_budget",
      "resource_name": "customers/1234567890/campaignBudgets/777",
      "campaign_id": "111",
      "action": "updated",
      "old_daily_budget": 50.0,
      "new_daily_budget": 65.0
    }
  ],
  "unchanged_resources": [],
  "failed_changes": [],
  "audit": {
    "customer_id": "1234567890",
    "api_version": "v21",
    "approval_record_id": "approval_789",
    "submitted_operations_count": 2,
    "rollback_plan": {
      "available": true,
      "notes": "Remove the created negative keyword and restore campaign budget to $50/day."
    }
  },
  "audit_note": "Only chg_001 and chg_003 were applied. No other campaigns, ads, keywords, bids, targeting, or budgets were changed."
}
```

Forbidden action-result examples:

```json
{
  "status": "blocked",
  "reason_code": "unapproved_change_id",
  "message": "Change chg_999 was not present in the approved source artifact. No Google Ads changes were made.",
  "changed_resources": []
}
```

```json
{
  "status": "blocked",
  "reason_code": "customer_mismatch",
  "message": "The approved plan belongs to customer 1234567890, but the active connection points to 5555555555. No Google Ads changes were made.",
  "changed_resources": []
}
```

---

## 6. Delete/Remove Sample — Second Confirmation Required

Capability ID target:

```text
marketing.channel.google_ads.resources.remove
```

User intent:

```text
delete that underperforming campaign
```

Expected decision artifact, not a mutation:

```json
{
  "artifact_type": "decision_artifact",
  "block_type": "google_ads_destructive_action_confirmation",
  "status": "needs_second_confirmation",
  "risk_level": "high_destructive",
  "customer_id": "1234567890",
  "requested_action": {
    "action": "remove_campaign",
    "campaign_id": "222",
    "campaign_name": "Generic Motorcycle Leads"
  },
  "warning": "Removing a Google Ads campaign may not be cleanly reversible. Pausing is safer and recommended first.",
  "safer_alternative": {
    "action": "pause_campaign",
    "campaign_id": "222"
  },
  "required_confirmation_phrase": "CONFIRM GOOGLE ADS CHANGE",
  "allowed_actions": [
    "pause_instead",
    "confirm_destructive_action",
    "dismiss"
  ],
  "forbidden_outcomes": [
    "Do not remove/delete from the first request",
    "Do not delete multiple resources from a vague prompt",
    "Do not hide safer alternatives"
  ]
}
```

If second confirmation is missing:

```json
{
  "artifact_type": "action_result",
  "block_type": "google_ads_mutation_result",
  "status": "blocked",
  "reason_code": "second_confirmation_required",
  "changed_resources": [],
  "message": "This destructive Google Ads action requires the exact confirmation phrase before anything is removed."
}
```

---

## 7. Partial Failure Sample

Expected action-result artifact when Google Ads applies one operation and rejects another:

```json
{
  "artifact_type": "action_result",
  "block_type": "google_ads_mutation_result",
  "status": "partial",
  "approved_by": "operator",
  "source_artifact_id": "run_abc123",
  "applied_change_ids": ["chg_001"],
  "changed_resources": [
    {
      "change_id": "chg_001",
      "resource_type": "negative_keyword",
      "resource_name": "customers/1234567890/adGroupCriteria/333~9001",
      "action": "created"
    }
  ],
  "failed_changes": [
    {
      "change_id": "chg_003",
      "action": "update_campaign_budget",
      "reason_code": "google_ads_policy_or_permission_error",
      "message": "Google Ads rejected the budget update. The negative keyword was created successfully."
    }
  ],
  "unchanged_resources": [
    {
      "change_id": "chg_003",
      "resource_type": "campaign_budget",
      "campaign_id": "111",
      "old_daily_budget": 50.0,
      "new_daily_budget": 50.0
    }
  ],
  "audit_note": "Partial success: one selected change was applied and one selected change failed. No unselected changes were attempted."
}
```

---

## 8. Global Forbidden Outcomes

Future Google Ads full-control capabilities must never produce these outcomes:

```json
[
  "A capability question mutates or reads the account without explicit request",
  "A vague request like 'fix my ads' directly changes budgets or statuses",
  "A read/report artifact has non-empty changed_resources",
  "A draft/optimization artifact claims changes were applied",
  "An apply action changes resources not listed in approved_change_ids",
  "A budget change is applied without before/after values",
  "A destructive action runs without second confirmation",
  "A mutation occurs against a different customer_id than the source artifact",
  "CMO chat pastes native ad headlines/descriptions instead of creating Workspace artifacts",
  "Credentials, developer tokens, access tokens, or refresh tokens are exposed"
]
```
