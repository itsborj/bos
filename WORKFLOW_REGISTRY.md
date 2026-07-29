# BOS Workflow Registry — Generic Multi-Step Artifact Pipelines

**Status:** Proposed architecture direction  
**Date:** 2026-06-19

## Problem

CMO will increasingly coordinate multi-step workflows: storyboard → image → video, strategy workflow components, email campaign sequences, ad creative sets, publishing chains, reporting loops, and many more.

Hardcoding each workflow into CMO chat creates bloatware:

- every new workflow adds prompt rules or branches to `chat.py`
- CMO starts guessing from natural language instead of reading state
- approval/revision/fresh-start behavior becomes inconsistent
- background multi-step work can appear to disappear

CMO should remain a business operator, not a workflow-specific state machine.

## Principle

**CMO reads generic workflow state. Packages declare workflow contracts. Core resolves state and executes transitions.**

CMO should not contain storyboard-specific, email-specific, ads-specific, or video-specific lifecycle logic. Instead, each package declares its stages, artifacts, actions, transitions, and fresh-start policy. The host injects a compact generic workflow-state block into CMO context.

## Contract shape

A package may declare workflow metadata in `channel.json` and/or capability `SKILL.md` frontmatter.

Example shape:

```yaml
workflow:
  id: video_storyboard_pipeline
  stage: storyboard_draft_review
  artifact_type: storyboard_json
  continuation_policy: artifact_bound_else_fresh
  actions:
    revise:
      kind: revision
      target_module: storyboard.create
    render:
      kind: transition
      target_module: storyboard.render
      creates_stage: storyboard_image_review
    dismiss:
      kind: terminal
  fresh_start:
    allowed: true
    creates_module: storyboard.create
```

For an output artifact, the block should continue to expose runtime actions in the existing artifact contract:

```json
{
  "type": "storyboard_json",
  "workflow": {
    "id": "video_storyboard_pipeline",
    "stage": "storyboard_draft_review"
  },
  "allowed_actions": ["revise", "render", "dismiss"],
  "action_modules": {
    "revise": "storyboard.create",
    "render": "storyboard.render"
  }
}
```

## Generic workflow-state injection

Before a CMO turn, BOS should resolve compact state from recent artifacts, explicit artifact context, active brand, and user turn.

Example injected state:

```text
Workflow state:
- active_workflows:
  - id: video_storyboard_pipeline
    current_artifact_id: 123
    stage: storyboard_draft_review
    available_actions: revise, render, dismiss
    continuation_policy: artifact_bound_else_fresh
- requested_fresh_start: false
- next_required_artifact: null
```

If the user requests a new video concept without referencing an existing artifact:

```text
Workflow state:
- active_workflows: []
- requested_fresh_start: true
- next_required_artifact: storyboard.create
- reason: no active artifact is bound to this request
```

CMO only needs generic behavior:

1. If `next_required_artifact` is present, create it with `RUN:`.
2. If the user references/binds to an artifact and chooses an available action, use `ACTION:`.
3. If the user revises an artifact, use the artifact revision pathway.
4. Do not invent workflow actions not declared by the artifact/workflow contract.
5. Do not paste artifact bodies in chat; artifacts stay in the approval container.

## Fresh start vs continuation

Freshness must be resolved generically, not per-workflow in CMO prompt rules.

Inputs:

- explicit artifact context from UI/revision/action buttons
- current active artifact in Stream/Workspace
- user language indicating a new concept/angle/start-over
- whether the last artifact belongs to the same brand/campaign/objective
- package-declared `continuation_policy`

Policies:

- `artifact_bound`: continue only when an artifact is explicitly referenced
- `artifact_bound_else_fresh`: continue if referenced; otherwise create fresh
- `latest_active_else_fresh`: continue latest active workflow if unambiguous
- `always_fresh`: every request starts a new workflow instance

## Background progress

Multi-step transitions must emit generic pipeline status events independent of CMO chat:

```json
{
  "workflow_id": "video_storyboard_pipeline",
  "stage": "rendering_storyboard_image",
  "source_artifact_id": "...",
  "target_module": "storyboard.render",
  "status": "running"
}
```

UI should show persistent app-level progress, not rely only on CMO thinking text. CMO may add short conversational status, but the artifact/workflow plane owns durable status.

## Non-goals

- Do not hardcode workflow-specific branches in CMO prompt text.
- Do not build one-off storyboard logic into core as the pattern.
- Do not require every package to implement workflows; single-step artifacts remain valid.
- Do not auto-advance costly stages unless a declared action and human approval require it.

## Migration path

1. Keep current artifact `allowed_actions` / `action_modules` contract as the runtime action layer.
2. Add optional `workflow` metadata to artifact blocks.
3. Add workflow declarations to package manifests/frontmatter.
4. Implement a generic workflow-state resolver for CMO context.
5. Move storyboard-specific prompt exceptions into the storyboard package workflow declaration.
6. Apply the same mechanism to email, ads, video, planning, and publishing chains.
