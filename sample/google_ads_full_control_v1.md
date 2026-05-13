# Google Ads Full Control — Approved Direction Sample v1

**Date:** 2026-05-13  
**Status:** Approved by human for reverse-spec  
**BITE stage:** Stage 3 complete → ready for Stage 4 reverse-spec

## Sample: Google Ads Full Control Capability Card

```text
Google Ads Specialist

Status: Connected / Needs Review
Jobs supported:
- marketing.optimize — find waste, diagnose performance, recommend changes
- marketing.execute — draft new campaigns, ads, keywords, budgets
- approved_action — apply selected changes after explicit approval

Current access levels:
✅ Read account/campaign/ad group/ad/keyword/search-term metrics
✅ Draft proposed changes
✅ Apply approved campaign status changes
✅ Apply approved budget changes
✅ Apply approved keyword / negative keyword changes
✅ Apply approved ad copy / asset changes
⚠️ Delete/remove actions require second confirmation
❌ No automatic spend changes without approval
❌ No broad account mutation from a vague prompt
```

## Sample: Optimization Artifact

```json
{
  "artifact_type": "decision_artifact",
  "block_type": "google_ads_optimization_plan",
  "status": "pending_review",
  "risk_level": "approval_required",
  "summary": "Found 4 issues that may be wasting spend.",
  "findings": [
    {
      "severity": "high",
      "issue": "Search terms spending with zero conversions",
      "evidence": "$218.42 spend, 0 conversions across 14 terms",
      "recommended_action": "Add 9 negative keywords",
      "proposed_changes": [
        {
          "action": "add_negative_keyword",
          "campaign_id": "123",
          "ad_group_id": "456",
          "keyword": "free motorcycle parts",
          "match_type": "PHRASE"
        }
      ]
    },
    {
      "severity": "medium",
      "issue": "Campaign hitting daily budget early",
      "evidence": "98% budget utilization by 11:20 AM",
      "recommended_action": "Increase budget from $50/day to $75/day or lower bids",
      "proposed_changes": [
        {
          "action": "update_campaign_budget",
          "campaign_id": "789",
          "from_daily_budget": 50,
          "to_daily_budget": 75
        }
      ]
    }
  ],
  "allowed_actions": [
    "approve_selected_changes",
    "revise_plan",
    "dismiss"
  ],
  "forbidden_actions": [
    "auto_apply_all",
    "change_unlisted_campaigns",
    "increase_total_daily_budget_without_budget_cap",
    "delete_campaign_without_second_confirmation"
  ]
}
```

## Sample: Approved Action Result

```json
{
  "artifact_type": "action_result",
  "block_type": "google_ads_mutation_result",
  "status": "succeeded",
  "approved_by": "operator",
  "changed_resources": [
    {
      "resource_type": "negative_keyword",
      "resource_name": "customers/123/adGroupCriteria/456~789",
      "action": "created",
      "keyword": "free motorcycle parts"
    },
    {
      "resource_type": "campaign_budget",
      "campaign_id": "789",
      "action": "updated",
      "old_daily_budget": 50,
      "new_daily_budget": 75
    }
  ],
  "unchanged_resources": [],
  "audit_note": "Only approved selected changes were applied. No campaigns, ads, or targeting outside the approved set were changed."
}
```

## Early issue list

1. Current plugin is not full-control: read and draft-only are installed; real edit/write/delete is not exposed.
2. Mutation code exists in `api/providers/google_ads.py`; future full-control mutations should move behind plugin-owned, approval-gated capabilities rather than BOS core behavior.
3. Approval tiers are required: read-only, draft/recommend, reversible edit, destructive/remove with second confirmation.
4. Account/customer safety is required: MCC/client selection, login customer ID handling, brand-to-customer mapping, and prevention of broad account mutations.
5. Every mutation needs audit storage: approved plan, exact proposed change, request payload, changed resource names, before/after values, failures, and partial-success details.
6. Rollback/reversal policy must be explicit because some Google Ads changes are reversible and some are not.
