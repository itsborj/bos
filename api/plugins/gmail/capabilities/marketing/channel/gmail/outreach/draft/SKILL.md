---
id: marketing.channel.gmail.outreach.draft
name: gmail-outreach-draft
description: Use only when the CMO asks to write, draft, generate, create, or show a sample single outreach email/cold email/introduction email. Do not use for capability questions such as "what can you do with email"; answer those conversationally with no RUN line. For email sequences, use planning first.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.gmail.outreach.draft
requires_intent:
  - generation
triggers:
  - gmail
  - write an email
  - draft an email
  - outreach email
  - cold email
  - email to
  - email sample
  - sample email
  - show me an email
  - let me see an email
  - email example
excluded_triggers:
  - what can you do
  - what can you do with email
  - can you help with email
  - email capabilities
  - email sequence
  - drip campaign
  - newsletter
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.gmail.outreach.draft
quality_gates:
  - subject_line_present
  - content_within_char_limit
  - no_banned_phrases
metadata:
  version: 0.1.0
  author: third-party
  plugin_id: channel.gmail
  implements: marketing.execute
  artifact_type: draft_artifact
  platform: gmail
  output_contract: email_draft
  risk_policy: draft_only_until_approved
---

## Gmail Outreach Draft

This `SKILL.md` is an activation contract for the CMO, not a prompt for the CMO to write the email inline. The module generates a single cold outreach email (subject + body) on behalf of a brand after the CMO dispatches it.

### When to activate
- CMO asks to write or draft an outreach email, introduction email, or cold email
- CMO mentions "gmail" as the channel
- CMO asks to "send an email" to a specific audience or lead

### Do not activate for
- Capability/overview questions such as "what can you do with email" → answer conversationally, no RUN line
- Multi-step email sequences → plan first
- Newsletter campaigns → plan first
- Internal operational emails

### CMO response behavior

When this capability is activated by a user request, the CMO must append:

```text
RUN: marketing.channel.gmail.outreach.draft
```

The visible CMO reply should be brief and should not include the full email inline. The email content belongs in the returned artifact/block for review.

If the user mixes this request with unsupported platform generation/control, draft the supported email artifact and explain the unsupported part. Do not invent unsupported platform artifacts.

### Outcome contract

Artifact type: `draft_artifact`
Block/output contract: `email_draft`
Platform: `gmail`
Risk policy: `draft_only_until_approved`

The module result must contain exactly:
1. `Subject:` line on the first line (max 60 chars)
2. `---` separator
3. Body (3–5 paragraphs, max 400 words)
4. Clear call-to-action
5. Sign-off
6. No unsupported proof/statistics/customer claims unless supplied by approved context

### Quality gates
- `subject_line_present` — module output must start with `Subject:`
- `content_within_char_limit` — total content under 4000 chars
- `no_banned_phrases` — "guaranteed", "100% free", "act now" are blocked
