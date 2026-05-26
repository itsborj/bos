# Direct Action Payload Handoff v1 — Stage 2 Sample

Status: Stage 2 sample — approved and implemented for generic ACTION handoff v1  
Date: 2026-05-22  
Scope: generic CMO direct-action handoff for publish/send/upload/schedule modules  
BITE stage: Sample

---

## What this sample proves

When the operator gives a clear external-action instruction, the CMO must preserve the actionable payload and hand it to the specialist module.

This is not a Facebook-only rule. The same pattern applies to:

```text
publish a Facebook post
send an email
upload a YouTube Short
schedule a post
send a Slack digest
publish a CMS page
```

The CMO core owns action intent + payload handoff. Plugins own platform execution and validation.

---

## Core distinction

### Direct approved action

```text
Post this to the Klaroha Facebook page:
Test post from BOS.
```

Meaning:

```text
The operator has supplied both approval and payload.
BOS may call the publish module directly.
```

### Draft/review workflow

```text
Draft a Facebook post about our new offer.
```

Meaning:

```text
The operator asked BOS to generate content.
Generated content requires review before external action.
BOS must create a draft artifact first.
```

---

## Sample A — direct Facebook text publish

### Operator message

```text
Post this to the Klaroha Facebook page:
Test post from BOS.
```

### Hidden CMO directive

```text
SCOPE:
conversation_brand: Klaroha
execution_brand: Klaroha
mode: single_brand_action
confidence: high

RUN: marketing.channel.meta.posts.publish
message: Test post from BOS.
```

### Step trace

```text
✓ Scope locked to Klaroha
✓ Direct action payload captured
↻ Running Facebook Post Publish
✓ Facebook publish result returned
↻ CMO synthesizing result
```

### Final CMO reply

```text
Posted to the Klaroha Facebook page.

Result is in Stream with the Facebook post ID.
```

### Action result artifact

```json
{
  "artifact_type": "action_result",
  "status": "succeeded",
  "platform": "facebook",
  "action_type": "publish",
  "message_preview": "Test post from BOS.",
  "changed_resources": ["1172728675913055_122..."],
  "allowed_actions": ["view_on_facebook", "dismiss"]
}
```

---

## Sample B — direct low-risk test post

### Operator message

```text
Let's do a test post on the Klaroha FB page. Text only is fine, just testing.
```

### CMO behavior

The CMO may create a short transparent test payload because the operator explicitly authorized a text-only test post.

```text
RUN: marketing.channel.meta.posts.publish
message: Test post from Klaroha BOS.
```

### Final CMO reply

```text
Test post published.

The result artifact includes the Facebook post ID.
```

---

## Sample C — generated creative must not publish directly

### Operator message

```text
Write a strong Facebook post for dormant prospects.
```

### Correct behavior

```text
RUN: marketing.channel.meta.posts.draft
```

Final reply:

```text
Facebook draft is ready in Stream.

Review it before publishing.
```

### Forbidden behavior

```text
RUN: marketing.channel.meta.posts.publish
message: <newly generated copy>
```

Why forbidden: the operator asked BOS to create copy, not to publish generated copy.

---

## Generic plugin contract

A direct-action skill may declare:

```yaml
metadata:
  action_type: publish | send | upload | schedule | apply
  direct_action_allowed: true | false
  payload_text_field: message | body | video_url | html | subject_body
  generated_content_requires_review: true
  exact_payload_required: true | false
```

The CMO core should use this metadata to build action payloads without platform-specific branches.

---

## Allowed outcomes

```text
1. Exact operator-supplied payload is passed to the action module.
2. Low-risk explicitly-authorized test action may use a short transparent test payload.
3. Generated copy/image/audio/video routes to draft/review artifact first.
4. Action result artifact records changed_resources, platform ID, URL/permalink where available, and status.
5. CMO final reply happens after the action result returns.
6. Missing payload is blocked or surfaced as a failed setup/action artifact, not hidden.
```

---

## Forbidden outcomes

```text
1. CMO claims something was posted/sent/uploaded before the action result returns.
2. Generated creative is published without review just because a publish module exists.
3. Chat.py adds platform phrase routing such as if "facebook" in message.
4. A plugin publishes with an empty payload.
5. A failed action disappears from Stream.
6. Raw provider tokens, page tokens, API errors with secrets, or backend model IDs appear in chat.
7. Brand-scoped action runs without a resolved execution_brand in multi-brand workspaces.
```

---

## Build target if approved

```text
CMO core:
- reads actionable artifact metadata from persisted artifact blocks
- exposes available artifact actions to the CMO prompt
- accepts hidden `ACTION: <run_id> <action>` directives
- executes through the generic `execute_declared_run_action()` primitive
- preserves CMO directive text in module briefs for direct-action modules
- returns action result artifacts and synthesis reply

Plugins:
- declare action modules in artifact blocks
- validate required payload fields
- execute external action
- return action_result artifact with changed_resources
```
