---
id: marketing.channel.gmail_auth.email.inbox_intelligence
name: Email Inbox Intelligence
description: Use when the user asks to check, classify, or review email replies, inbox signals, or response patterns from Gmail. Fetches recent replies and classifies each as interested, objection, pricing concern, not now, wrong person, unsubscribe, or booked. Do not use for capability questions, email drafting, or planning.
scope: module
status: active
version: 1.0.0
allowed_from_chat: true
module_id: marketing.channel.gmail_auth.email.inbox_intelligence
requires_intent:
  - discussion
  - diagnostic
triggers:
  - any replies
  - any email replies
  - check replies
  - classify inbox
  - check inbox
  - did anyone reply
  - inbox intelligence
  - reply signals
  - check my email replies
  - how are replies looking
  - what are people saying
  - reply analysis
  - inbox analysis
  - classify my replies
  - review replies
  - check inbox signals
  - what replies came in
excluded_triggers:
  - what can you do
  - what can you do with email
  - can you help with email
  - email capabilities
  - write email copy
  - draft gmail outreach
  - send email
  - plan email
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.gmail_auth.email.receive
  - marketing.channel.gmail_auth.email.send
quality_gates:
  - gmail_oauth_token_present
  - classified_signals_present
metadata:
  version: 1.0.0
  author: klaroha
  plugin_id: channel.gmail_auth
  implements: marketing.optimize
  artifact_type: inbox_intelligence_artifact
  platform: gmail
  output_contract: inbox_intelligence_result
  risk_policy: read_only
---

## Inbox Intelligence

This module fetches recent Gmail replies and classifies each reply signal into one of seven categories. It returns a classification summary artifact in Workspace — never raw email content inline in chat.

### When to activate

- User asks to check replies, review inbox signals, or analyse response patterns from an active outreach or campaign
- User asks "any replies?", "how are people responding?", "classify my inbox", or similar

### Do not activate for

- Capability questions → answer conversationally with no RUN line
- Email drafting or campaign planning
- Sending email
- Reading individual full email bodies (use receive for raw access)

### CMO response behaviour

When activated, append:

```text
RUN: marketing.channel.gmail_auth.email.inbox_intelligence
```

Keep the visible CMO reply brief — one line confirming the inbox check. The classification summary appears as a Workspace artifact.

### Connector requirement

Requires Gmail OAuth connector on the active brand (Admin → Brands → Connect Gmail).

### Output contract

Artifact type: `inbox_intelligence_artifact`
Block type: `inbox_intelligence_result`
Risk policy: `read_only`

The module returns:
1. `signals` — list of classified replies, each with sender, subject snippet, category, and recommended action
2. `summary` — counts by category
3. `top_action` — the highest-priority recommended next action
4. No raw email body text in the output block

### Reply signal categories

| Category | Recommended action |
|---|---|
| interested | Book call or move to warm sequence |
| objection | Send objection-handling reply |
| pricing_concern | Share pricing page + ROI framing |
| not_now | Archive + set follow-up reminder |
| wrong_person | Re-route to named contact |
| unsubscribe | Remove immediately, no reply |
| booked | Move to CRM, send confirmation email |
