# Sample — SOP Ingestion Change Proposal

**Purpose:** agreed sample output before any SOP-ingestion spec or implementation.

---

## User action

User uploads: `Twitter Paid Social Copy SOP.md`

---

## BOS response

```text
SOP analyzed: Twitter Paid Social Copy SOP

Recommended action: Update existing atomic skill

Primary target:
- marketing.twitter.ad_copy

Why:
- The SOP governs a repeatable Twitter/X paid social copy workflow.
- Existing skill coverage is strong.
- The SOP changes instructions and quality gates, not API behavior.

No module change recommended.
```

---

## Structured proposal

```json
{
  "proposal_id": "sop_prop_01H_SAMPLE",
  "status": "draft",
  "sop": {
    "title": "Twitter Paid Social Copy SOP",
    "source_type": "uploaded_markdown",
    "sop_type": "channel_workflow",
    "scope_width": "atomic_task",
    "domains": ["marketing", "twitter", "paid_social", "ad_copy"],
    "criticality": "medium"
  },
  "matches": {
    "skills": [
      {
        "skill_id": "marketing.twitter.ad_copy",
        "similarity": 0.89,
        "reason": "Same channel, asset type, and workflow."
      },
      {
        "skill_id": "marketing.compliance.claims",
        "similarity": 0.51,
        "reason": "SOP references claim checks but does not redefine claims policy."
      }
    ],
    "modules": [
      {
        "module_id": "marketing.ad_copy.twitter",
        "similarity": 0.82,
        "reason": "Module executes Twitter/X ad copy generation."
      }
    ]
  },
  "recommended_plan": [
    {
      "surface": "skill",
      "action": "update",
      "target": "marketing.twitter.ad_copy",
      "confidence": 0.88,
      "requires_approval": true,
      "reason": "SOP adds reusable copy rules, workflow steps, and quality gates."
    },
    {
      "surface": "resource",
      "action": "attach_resource",
      "target": "marketing.twitter.ad_copy",
      "resource_type": "source_sop",
      "filename": "twitter_paid_social_copy_sop.md",
      "requires_approval": false,
      "reason": "Keep original SOP linked as authoritative source."
    },
    {
      "surface": "module",
      "action": "no_change",
      "target": "marketing.ad_copy.twitter",
      "requires_approval": false,
      "reason": "No new API schema, persistence, provider behavior, or executable capability detected."
    },
    {
      "surface": "memory",
      "action": "memory_candidate",
      "target": "workspace",
      "fact": "Marketing prefers five Twitter ad variants by default.",
      "requires_approval": true,
      "reason": "Durable team preference extracted from SOP."
    }
  ],
  "proposed_skill_diff": [
    {
      "type": "new",
      "section": "Rules",
      "content": "Each ad variant must include exactly one practitioner pain point."
    },
    {
      "type": "new",
      "section": "Quality Gates",
      "content": "Flag unsupported quantitative or comparative claims before returning output."
    },
    {
      "type": "refinement",
      "section": "Voice Rules",
      "old": "Use direct, concise language.",
      "new": "Use direct, concise language. Avoid rhetorical questions in opening hooks."
    },
    {
      "type": "conflict",
      "section": "Default Output",
      "old": "Generate 3 ad variants by default.",
      "new": "Generate 5 ad variants by default.",
      "requires_human_review": true
    }
  ],
  "approval": {
    "required": true,
    "reasons": [
      "Default output behavior changes from 3 to 5 variants.",
      "SOP adds quality gates involving claim risk."
    ],
    "safe_to_auto_apply": [
      "Attach SOP as source resource"
    ]
  },
  "versioning": {
    "current_skill_version": 3,
    "proposed_skill_version": 4,
    "activation": "after_approval",
    "rollback_available": true
  }
}
```

---

## Human-facing approval prompt

```text
I found that this SOP should update the Twitter/X Ad Copy skill, not create a new skill.

I recommend:
1. Update marketing.twitter.ad_copy with 2 new rules and 1 refined voice rule.
2. Add 1 quality gate for unsupported claims.
3. Attach the SOP as the source reference.
4. Do not change the Twitter ad copy module.

Approval needed:
- Existing skill defaults to 3 variants.
- SOP says default should be 5 variants.

Approve the proposed skill update, approve only the safe resource attachment, or request edits?
```
