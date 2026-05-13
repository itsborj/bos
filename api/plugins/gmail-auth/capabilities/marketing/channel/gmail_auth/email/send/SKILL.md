---
id: marketing.channel.gmail_auth.email.send
name: Gmail Send Email
description: Approval-gated Gmail send tool. Not directly CMO-runnable from ordinary chat. Use only after an approved email artifact exists, required recipient/subject/body fields are present, and the owner explicitly approves sending.
scope: module
status: active
version: 1.0.1
allowed_from_chat: false
module_id: marketing.channel.gmail_auth.email.send
triggers:
  - send an email
  - send email
  - email to
  - send it
  - send this email
  - send the email
  - send the draft
  - gmail send email
  - send email through gmail
  - send mail with gmail
  - authenticated gmail send
  - gmail auth send email
excluded_triggers:
  - what can you do
  - what can you do with email
  - can you help with email
  - email capabilities
  - draft gmail outreach
  - write email copy only
  - create email content without sending
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.gmail_auth.email.send
quality_gates:
  - gmail_send_fields_present
  - gmail_oauth_token_present
metadata:
  version: 1.0.0
  author: klaroha
  plugin_id: channel.gmail_auth
---

## Activation

Activate this tool only from an approval-gated send flow after the owner has approved a specific email artifact and explicitly approved sending. Ordinary CMO chat should not dispatch this module directly.

## Do not activate

Do not activate this skill for copywriting-only requests, draft-only requests, or non-Gmail channels.

## Required brief fields

The brief must contain: `to` (recipient address), `subject`, and `body`. The CMO must collect these from the user before dispatching.

## Output contract

The module returns a `gmail_send_result` block with `status`, Gmail `message_id`, Gmail `thread_id`, recipients, and subject. Failures return a `reason_code` and diagnostic details without raising exceptions.
