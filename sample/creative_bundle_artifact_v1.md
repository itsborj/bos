# Creative Bundle + CMO Execution Loop v1 — Stage 2 Sample

Status: Stage 2 sample — approved for Path A synthesis-after-results build
Date: 2026-05-22
Scope: fast CMO execution loop; paired copy + image artifact for ads/social execution
BITE stage: Sample

---

## What this sample proves

The operator should experience Klaroha as a CMO with specialists, not as a single-pass chat bot.

The CMO receives business intent, creates one shared campaign brief, runs copy and visual specialists in parallel, waits for their results, then writes the final reply after seeing specialist summaries.

Chat remains the short control surface. Stream/Workspace own native artifact detail, previews, approval, revision, dismissal, and system metadata.

---

## Starting state

```text
Org: Klaroha Agency
Active Brand: Klaroha
Operator: Business leader / marketing operator
Objective: Generate qualified demo requests from dormant prospects
Approved source memory:
- Campaign Brand Kit: ivory, racing green, warm neutral; calm executive tone
- Banned motifs: robot mascot, neon cyberpunk, busy analytics dashboard
- Positioning: marketing clarity, signal collapse, decision queue
Connector readiness:
- Image generation: ready
- Organic social: draft-only, publishing requires later explicit approval
- Paid ads: draft-only, spend/publish not connected for this sample
```

---

## Operator message

```text
Create a campaign direction for dormant prospects.
I want the angle to be that Klaroha gives them clarity without another dashboard.
Give me copy and a visual direction together so I can decide if the idea is worth turning into channel assets.
```

---

## Visible CMO + Stream experience

### CMO message 1 — acknowledgement before work

```text
I’ll turn that into one reviewable creative bundle.

Copy and visual will use the same brief.
I’ll bring back the bundle in Stream before any channel execution.
```

Hidden directives, not visible to operator:

```text
SCOPE:
conversation_brand: Klaroha
execution_brand: Klaroha
mode: single_brand_execution
confidence: high

RUN: marketing.execute.copy_draft
RUN: media.image.generate
```

### Step trace while specialists run

```text
✓ Scope locked to Klaroha
✓ Built shared campaign brief
↻ Copy specialist drafting campaign message
↻ Visual specialist generating image direction
✓ Copy specialist returned draft summary
✓ Visual specialist returned image summary
↻ CMO checking bundle coherence
✓ Creative bundle created in Stream
```

### Specialist result summaries available to CMO synthesis

The CMO synthesis turn sees only decision-useful metadata, not full native artifact content.

```json
[
  {
    "run_id": "run_copy_123",
    "artifact_ref": "artifact_copy_123",
    "artifact_type": "draft_artifact",
    "status": "completed",
    "summary": "Campaign message draft created around clarity without another dashboard.",
    "self_check": "passed",
    "recommended_decision": "review",
    "objective_ref": "obj_demo_requests_q2",
    "brand_ref": "klaroha",
    "allowed_actions": ["revise", "include_in_bundle", "dismiss"]
  },
  {
    "run_id": "run_image_456",
    "artifact_ref": "artifact_image_456",
    "artifact_type": "draft_artifact",
    "status": "completed",
    "summary": "Square visual direction generated with brand palette and banned motifs avoided.",
    "self_check": "passed",
    "recommended_decision": "review",
    "objective_ref": "obj_demo_requests_q2",
    "brand_ref": "klaroha",
    "allowed_actions": ["revise", "include_in_bundle", "dismiss"]
  }
]
```

### Final CMO reply — after specialist results

```text
Creative bundle is ready in Stream.

Lead angle passed: clarity without another dashboard.
Visual fit passed brand check.

Approve the bundle only if the direction feels right — publishing and spend stay separate.
```

Forbidden final reply:

```text
Headline: Marketing clarity without another dashboard
Primary copy: Most marketing teams do not need more content...
Image prompt: A calm executive command center...
```

The native copy and image prompt belong in the Stream/Workspace artifact, not in chat.

---

## Steering / follow-up queue sample

If the operator sends a follow-up while specialists are still running, it is queued for the synthesis turn rather than interrupting running specialists.

```text
Operator follow-up while running:
Also make sure it does not sound like another analytics dashboard.

Step trace update:
✓ Steering note queued for synthesis

CMO synthesis uses queued note:
- Check whether copy implies dashboard/tooling too strongly
- Check whether image implies analytics overload
```

Final reply may mention the steering note was applied:

```text
I also checked the dashboard concern.

The bundle avoids analytics-tool framing;
it leans on decision clarity instead.
```

---

## Branchable session ledger sample

This is the target persistence shape for reconstructing the turn later. It is not a requirement for the first synthesis-after-results code slice, but the sample shows the artifact trail the UX should eventually support.

```json
{
  "session_id": "cmo_sess_20260522_klaroha_launch",
  "active_leaf_id": "entry_0008",
  "entries": [
    {
      "id": "entry_0001",
      "parent_id": null,
      "entry_type": "user_message",
      "summary": "Operator requested a dormant-prospect creative bundle."
    },
    {
      "id": "entry_0002",
      "parent_id": "entry_0001",
      "entry_type": "llm_turn",
      "summary": "CMO scoped to Klaroha and requested copy + image specialists."
    },
    {
      "id": "entry_0003",
      "parent_id": "entry_0002",
      "entry_type": "specialist_dispatch",
      "summary": "Copy specialist dispatched from shared campaign brief."
    },
    {
      "id": "entry_0004",
      "parent_id": "entry_0002",
      "entry_type": "specialist_dispatch",
      "summary": "Image specialist dispatched from shared campaign brief."
    },
    {
      "id": "entry_0005",
      "parent_id": "entry_0004",
      "entry_type": "steering_note",
      "summary": "Operator asked to avoid analytics-dashboard framing."
    },
    {
      "id": "entry_0006",
      "parent_id": "entry_0005",
      "entry_type": "specialist_result",
      "summary": "Copy and image summaries returned; native fields withheld from synthesis context."
    },
    {
      "id": "entry_0007",
      "parent_id": "entry_0006",
      "entry_type": "artifact_created",
      "summary": "creative_bundle artifact created in Stream."
    },
    {
      "id": "entry_0008",
      "parent_id": "entry_0007",
      "entry_type": "turn_complete",
      "summary": "CMO final reply sent after seeing specialist results."
    }
  ]
}
```

### Branch example

If the operator later says `try a bolder direction instead`, BOS can branch from the approved turn without overwriting the original artifact trail.

```text
entry_0008 original leaf: calm executive clarity bundle
entry_0011 branch leaf: bolder/direct-response clarity bundle
```

### Handoff / compaction summary sample

```text
Session handoff summary:
- Brand: Klaroha
- Objective: dormant prospects → qualified demo requests
- Current artifact: creative_bundle artifact_cb_8f34, pending_review
- Direction: clarity without another dashboard
- Steering applied: avoid analytics-dashboard framing
- Approval boundary: bundle approval only; no publish/spend/send authority
- Next best action: review Stream card; approve bundle or request copy/image revision
```

---

## Sample Stream card

```text
Card type: pending_artifact
Artifact type: creative_bundle
Priority: high
Objective: Generate qualified demo requests from dormant prospects
Brand: Klaroha
Source state: generated from approved Campaign Brand Kit + shared campaign brief
Confidence: directional · 0.66
```

### Why now

```text
The campaign plan needs one reviewable creative direction before channel execution.
The copy and image were generated from the same offer angle, so they should be approved or revised together.
```

### Preview

```text
Headline:
Marketing clarity without another dashboard

Primary copy:
Most marketing teams do not need more content.
They need to know what deserves action.

Klaroha turns scattered signals into one decision queue — so the next move is clear before the day starts.

CTA:
See the operating loop

Image:
/asset/image_8f34.png

Image prompt used:
A calm executive command center for a marketing operator, ivory and racing green palette,
soft morning light, decision cards arranged on one clear workspace, no charts overload,
no generic robot imagery.
```

### Brand compliance

```text
checked: true
method: prompt_constraints_v0
passed: true
constraints_applied: true
notes:
- used Campaign Brand Kit palette: ivory, racing green, warm neutral
- avoided banned motifs: robot mascot, neon cyberpunk, busy analytics dashboard
- kept tone: calm, clear, executive
```

### Recommended next

```text
Approve the bundle as one creative direction, or revise the copy/image pairing together.
```

### Approval boundary

```text
BOS may generate and revise this creative bundle.
Bundle approval means: "this creative direction is approved for reuse."
Bundle approval does not mean: publish, schedule, send, spend, or create platform-native ads.
```

### Allowed actions

```text
approve bundle
revise copy
revise image
revise both
ask CMO
split into channel artifacts
dismiss
```

---

## Workspace artifact detail

```json
{
  "artifact_type": "creative_bundle",
  "status": "pending_review",
  "objective_ref": "obj_demo_requests_q2",
  "brand_ref": "klaroha",
  "campaign_ref": "campaign_dormant_demo_requests",
  "source_context": {
    "campaign_brand_kit_doc_id": "doc_cbk_123",
    "campaign_plan_id": "plan_456",
    "memory_event_ids": ["mem_offer_clarity", "mem_no_dashboard_overload"]
  },
  "copy": {
    "headline": "Marketing clarity without another dashboard",
    "primary_text": "Most marketing teams do not need more content. They need to know what deserves action. Klaroha turns scattered signals into one decision queue — so the next move is clear before the day starts.",
    "cta": "See the operating loop"
  },
  "image": {
    "asset_id": "image_8f34",
    "mime_type": "image/png",
    "width": 1024,
    "height": 1024,
    "prompt": "A calm executive command center...",
    "brand_compliance": {
      "checked": true,
      "method": "prompt_constraints_v0",
      "passed": true,
      "constraints_applied": true
    }
  },
  "bundle_self_check": {
    "copy_matches_image": true,
    "offer_consistent": true,
    "brand_constraints_applied": true,
    "platform_ready": false,
    "reason_not_platform_ready": "No channel-specific dimensions, placement, or policy validation yet."
  },
  "allowed_actions": [
    "approve_bundle",
    "revise_copy",
    "revise_image",
    "revise_both",
    "ask_cmo",
    "split_into_channel_artifacts",
    "dismiss"
  ],
  "risk_policy": "approval_required_before_channel_execution"
}
```

---

## Allowed outcomes

```text
1. Operator approves the bundle as a reusable creative direction.
2. Operator asks for copy-only revision while preserving image direction.
3. Operator asks for image-only revision while preserving copy direction.
4. Operator asks to revise both because the concept is wrong.
5. Operator splits the approved bundle into channel-specific artifacts later.
6. BOS records approval/rejection rationale into MemoryEvent.
7. CMO runs synthesis after specialist results and summarizes artifact readiness in chat.
8. If one specialist fails, CMO reports partial completion and points only to artifacts that exist.
```

---

## Forbidden outcomes

```text
1. BOS must not publish this bundle directly to any channel.
2. BOS must not treat bundle approval as ad/spend/publish approval.
3. BOS must not create fake placement metrics or predicted ROAS.
4. BOS must not skip brand compliance metadata.
5. BOS must not show copy and image as unrelated cards if they were generated from the same creative concept.
6. BOS must not create Meta/Google/LinkedIn native fields until a platform-specific artifact is requested.
7. BOS must not use a Campaign Brand Kit from another Brand.
8. CMO chat must not paste the full native copy or image prompt inline.
9. CMO must not speak final success text before specialist results return.
10. Chat/router code must not choose specialists with platform phrase matching or hardcoded module lists.
11. The synthesis loop must not run indefinitely; v1 max depth is 3.
```

---

## Build implications if approved

```text
Loop primitive: after RUN dispatch, convert specialist results into summary context and call CMO synthesis before final reply.
Default execution: shared campaign brief → copy + image specialists in parallel → synthesis → creative_bundle artifact.
New/confirmed artifact block type: creative_bundle.
Renderer: paired copy + image preview in Stream/Workspace.
Inputs: campaign brief, Campaign Brand Kit excerpt, objective, memory.
Outputs: copy block, image_asset block, bundle_self_check, allowed_actions.
Approval: bundle approval only; channel execution remains separate.
Memory: approval/rejection/revision rationale writes MemoryEvent.
```

---

## Open approval question

```text
Should creative_bundle be approved as a reusable campaign direction first,
or should approval immediately create channel-specific child artifacts?
```

Recommended v1 answer:

```text
Approve as reusable direction first. Channel-specific child artifacts come after explicit operator action.
```
