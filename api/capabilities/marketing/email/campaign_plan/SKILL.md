---
id: marketing.email.campaign_plan
name: email-campaign-planner
description: Use only when the CMO needs to plan an email campaign, outreach sequence, newsletter campaign, reactivation sequence, launch sequence, nurture sequence, or follow-up cadence before drafting or sending. Do not use for capability questions such as "what can you do with email"; answer those conversationally with no RUN line. This implements marketing.plan for the Email Specialist and never sends email.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.email.campaign_plan
requires_intent:
  - discussion
  - generation
triggers:
  - plan an email campaign
  - email campaign plan
  - plan outreach
  - plan a sequence
  - reactivation sequence
  - nurture sequence
  - follow-up cadence
  - newsletter plan
  - launch email sequence
  - email strategy
excluded_triggers:
  - what can you do
  - what can you do with email
  - can you help with email
  - email capabilities
  - send the email now
  - check inbox
  - read gmail
  - show replies
memory_slots:
  - brand_profile
  - campaign_brand_kit
  - approved_learnings
related_modules:
  - marketing.channel.gmail.outreach.draft
  - marketing.channel.gmail_auth.email.send
  - marketing.channel.gmail_auth.email.receive
quality_gates:
  - goal_present
  - audience_present
  - sequence_present
  - approval_policy_present
metadata:
  version: 0.1.0
  author: bos-core
  implements: marketing.plan
  specialist: email
  risk_policy: draft_only
  artifact_type: plan_artifact
  output_contract: email_campaign_plan
  platform: email
---

# Email Campaign Planner

This `SKILL.md` is an activation contract for the CMO, not a prompt for the CMO to write the plan inline. The module produces an Email Campaign Plan artifact for owner approval after the CMO dispatches it.

## When to activate
- User asks the CMO to plan email marketing, an email campaign, a sequence, a reactivation motion, a nurture motion, or outreach cadence.
- User needs strategy before individual drafts.
- User asks what emails should be sent and when.

## Do not activate for
- Capability/overview questions such as "what can you do with email".
- Reading Gmail replies or checking inbox state.
- Sending email.
- Writing a single email draft when no plan is requested.

## Outcome contract

Artifact type: `plan_artifact`
Block/output contract: `email_campaign_plan`
Risk policy: `draft_only`

The module artifact must include:
1. Goal
2. Audience
3. Offer
4. Sequence table
5. Success metric
6. Draft artifacts needed
7. Inbox intelligence to watch
8. Optimization loop
9. Risk and approval

## Safety
Never send email. State that real sends require explicit owner approval and opt-out/do-not-contact rules must be respected.
