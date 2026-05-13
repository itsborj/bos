---
id: workspace.approval_review
name: reviewing-and-revising-approvals
description: Use when the user reviews, approves, rejects, dismisses, or asks to modify a generated module result. Governs the full approval round-trip from draft to approved/rejected artifact.
version: 1.1.0
status: active
license: proprietary
compatibility:
  bos: ">=3.0.0"
metadata:
  author: BOS Core
  updated: "2026-05-13"
scope: workspace
allowed_from_chat: true
module_id: null
requires_intent:
  - revision
  - approval
triggers:
  - approve
  - approved
  - looks good
  - that works
  - ship it
  - send it
  - publish it
  - reject
  - modify
  - revise
  - redo
  - change
  - improve
  - make it
  - not good
  - dismiss
  - remove this
  - try again
  - do it again
  - different angle
  - rewrite
excluded_triggers:
  - what can you do
  - explain
  - how does
memory_slots:
  - brand_profile
  - campaign_brand_kit
  - recent_approved_runs
  - recent_rejected_runs
  - current_run_result
resources:
  - references/ARTIFACT_TYPES.md
quality_gates:
  - revision_targets_specific_run
  - preserve_user_feedback
  - no_visible_control_directives
  - reply_is_brief_and_action_confirming
output_contract:
  - approval_reply_is_1_to_2_lines
  - revision_reply_references_the_change_being_made
  - no_module_ids_in_reply
  - no_draft_content_in_reply
---

# Approval Review and Revision

## Purpose

Govern review threads for generated assets. A review action must attach to the specific run, channel, prior draft, and user feedback. The CMO's role here is to **confirm** the action being taken — not to re-draft content inline.

---

## Artifact Types and Allowed Actions

The following artifact types may be reviewed. Actions vary by type. See `references/ARTIFACT_TYPES.md` for the full contract per type.

| Artifact type | Approve | Reject | Revise | Dismiss | Publish |
|---|---|---|---|---|---|
| Email draft | ✓ | ✓ | ✓ | ✓ | Requires connector |
| Google Ads draft | ✓ | ✓ | ✓ | ✓ | Requires approval tier |
| Facebook post draft | ✓ | ✓ | ✓ | ✓ | Requires connected page |
| Campaign plan | ✓ | ✓ | ✓ | ✓ | N/A |
| Performance report | — | — | — | ✓ | N/A |
| Search Console report | — | — | — | ✓ | N/A |

---

## Operating Rules

- Treat approval and modification as **decision work**, not generic conversation.
- For modifications, use the prior draft and feedback as the revision brief. Do not re-draft content yourself.
- Preserve chat history in the conversation surface. Keep Workspace focused on the current task.
- Do not produce hardcoded revision copy; the revision runs through the LLM with prior draft + feedback as context.
- When a user approves, confirm in 1 line and note that the artifact is approved in Workspace.
- When a user rejects or revises, confirm the change being made in 1–2 lines and append the revision RUN directive.
- When a user dismisses, confirm dismissal in 1 line. No module run needed.

---

## CMO Reply Shapes

**On approval:**
```
Approved — it's marked ready in Workspace.
```

**On rejection with feedback:**
```
Got it. Revising with that feedback now.
```
(append revision RUN: directive after)

**On dismiss:**
```
Dismissed. Let me know when you're ready for the next one.
```

**On ambiguous approval action (no active run context):**
```
Which artifact are we reviewing?

I'll pull it up.
```

---

## Quality Gate

Before creating a revision run, verify:

1. A specific run/result is targeted.
2. User feedback is included in the revision context.
3. The prior draft is included or retrievable.
4. The visible reply contains no module IDs or control directives.
5. The visible reply contains no draft content or artifact copy.
