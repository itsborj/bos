---
id: workspace.approval_review
name: Approval Review and Revision
description: Use when the user reviews, approves, rejects, or asks to modify a generated module result.
scope: workspace
allowed_from_chat: true
module_id: null
requires_intent:
  - revision
  - approval
triggers:
  - approve
  - approved
  - modify
  - revise
  - redo
  - change
  - improve
  - reject
  - make it
memory_slots:
  - brand_profile
  - campaign_brand_kit
  - recent_approved_runs
  - recent_rejected_runs
  - current_run_result
quality_gates:
  - revision_targets_specific_run
  - preserve_user_feedback
  - no_visible_control_directives
---

# Approval Review and Revision

## Purpose

Govern review threads for generated assets. A review action must attach to the specific run, channel, prior draft, and user feedback.

## Operating rules

- Treat approval and modification as decision work, not generic conversation.
- For modifications, use the prior draft and feedback as the revision brief.
- Preserve chat history in the conversation surface, but keep Workspace focused on the current task.
- Do not produce hardcoded revision copy; generate the CMO response through the LLM.

## Quality gate

Before creating a revision run, verify:

1. A specific run/result is targeted.
2. User feedback is included in the revision context.
3. The prior draft is included or retrievable.
4. The visible reply contains no module IDs or control directives.
