---
id: marketing.channel.gmail_auth.email.receive
name: Gmail Receive Email
description: Low-level Gmail inbox retrieval tool. Returns raw message metadata and body. Use only when raw message data is needed. For reply classification and signal analysis, use inbox_intelligence instead. Do not use for capability questions, email planning, or drafting.
scope: module
status: active
version: 1.0.1
allowed_from_chat: false
module_id: marketing.channel.gmail_auth.email.receive
triggers:
  - any replies
  - any email replies
  - check email replies
  - check my email
  - check emails
  - any responses
  - did anyone reply
  - replies from email
  - gmail receive emails
  - read gmail inbox
  - search gmail messages
  - get gmail emails
  - authenticated gmail receive
  - check my gmail
  - show gmail
  - check inbox
  - read inbox
excluded_triggers:
  - what can you do
  - what can you do with email
  - can you help with email
  - email capabilities
  - write email copy
  - draft gmail outreach
  - summarize pasted emails
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.gmail_auth.email.inbox_intelligence
  - marketing.channel.gmail_auth.email.send
quality_gates:
  - gmail_receive_query_valid
  - gmail_oauth_token_present
metadata:
  version: 1.0.0
  author: klaroha
  plugin_id: channel.gmail_auth
---

## Activation

Activate this tool only when the user explicitly asks to check, read, search, or retrieve Gmail inbox/reply data. Do not activate it for capability questions or general email strategy questions.

## Do not activate

Do not activate this skill when the user only provides pasted email text, asks for email copywriting, or asks for a non-Gmail mailbox.

## Output contract

The module returns a `gmail_receive_result` block with `emails`, `result_size_estimate`, `next_page_token`, and the query metadata. Each email contains Gmail IDs, headers, labels, snippet, and optionally a decoded text body.
