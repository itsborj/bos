# Creative Bundle Artifact v1 — Sample

Status: sample for approval before build  
Date: 2026-05-20  
Scope: paired copy + image artifact for future ads/social execution  
BITE stage: Sample

---

## Why this exists

The operator should review one creative unit, not separate copy and image cards that may drift.

A `creative_bundle` pairs:

```text
message/copy
image asset or image prompt
platform usage intent
brand compliance check
approval boundary
```

This is not part of Gate 2 Gmail proof. It belongs to image/social/ads execution after the primitive loop is proven.

---

## Sample Stream card

```text
Card type: pending_artifact
Artifact type: creative_bundle
Priority: high
Objective: Generate qualified demo requests from dormant prospects
Brand: Klaroha
Source state: generated from approved Campaign Brand Kit + campaign brief
Confidence: directional · 0.66
```

### Why now

```text
The campaign plan needs one reviewable creative unit before channel execution.
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
BOS may not publish, spend, or schedule it until the operator approves a platform-specific execution artifact.
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
```

---

## Build implications if approved

```text
New artifact block type: creative_bundle
Renderer: paired copy + image preview
Inputs: campaign brief, Campaign Brand Kit excerpt, objective, memory
Outputs: copy block, image_asset block, bundle_self_check, allowed_actions
Approval: bundle approval only; channel execution remains separate
Memory: approval/rejection/revision rationale writes MemoryEvent
```

---

## Open approval question

```text
Should `creative_bundle` be approved as a reusable campaign direction first,
or should approval immediately create channel-specific child artifacts?
```

Recommended answer for v1:

```text
Approve as reusable direction first. Channel-specific child artifacts come after explicit operator action.
```
