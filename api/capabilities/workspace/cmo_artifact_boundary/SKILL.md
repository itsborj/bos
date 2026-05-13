---
id: workspace.cmo_artifact_boundary
name: cmo-artifact-boundary
description: Enforces the CMO artifact surface boundary. Use when the user asks for samples, let me see, show me, examples, or any broad request that could produce inline platform-native content. Intercepts before the CMO generates email copy, ad headlines, or product descriptions inline.
version: 1.0.0
status: active
license: proprietary
compatibility:
  bos: ">=3.0.0"
metadata:
  author: BOS Core
  updated: "2026-05-13"
scope: workspace
allowed_from_chat: true
module_id: null
requires_intent:
  - discussion
  - generation
triggers:
  - samples
  - show me
  - let me see
  - examples
  - what would this look like
  - let me see samples
  - show me examples
  - give me an example
  - sample email
  - sample ad
  - sample post
  - draft something
  - write something
  - create something
  - make something
excluded_triggers:
  - approve
  - reject
  - send
  - publish
  - @klar
memory_slots:
  - brand_profile
quality_gates:
  - no_inline_native_content
  - no_subject_body_inline
  - no_headline_description_inline
  - no_fake_proof
  - no_invented_budgets
  - no_ad_copy_inline
  - no_email_copy_inline
output_contract:
  - reply_asks_or_dispatches_never_both
  - ambiguous_request_asks_one_clarifying_question
  - named_artifact_type_dispatches_via_run_directive
---

# CMO Artifact Boundary

## Purpose

Enforce the contract that the CMO chat surface **never renders platform-native content inline**. This skill activates on broad sample/example requests and ensures the CMO either:

1. **Dispatches** an installed capability via a `RUN:` line and announces that the artifact will appear in Workspace.
2. **Asks** one clarifying question to identify which artifact type to create — then waits.

It never does both in the same turn. It never generates the artifact itself.

---

## The Hard Line

These content types must **never** appear in a visible CMO chat reply:

| Content type | Examples of what is banned inline |
|---|---|
| Email copy | Subject lines, preheaders, full email bodies, CTAs, PS lines |
| Ad copy | Google Ads headlines/descriptions, Facebook copy, Instagram captions |
| Social posts | Twitter/X threads, LinkedIn posts with hashtags, GBP posts |
| Product descriptions | Taglines, benefit bullets, feature lists written as final copy |
| SEO content | Meta descriptions, title tags, blog intros |
| Proof/social proof | Invented testimonials, made-up results, fake budgets |
| Targeting specs | Audience definitions, keyword lists, bid strategies |

---

## Decision Logic

When a sample/example/show-me request arrives:

### Step 1 — Is an installed capability named?

If the user names a **specific artifact type** that maps to an installed module in the capability manifest:

→ Dispatch it: write a brief 1–2 line reply and append the RUN: directive.

Example triggers that dispatch:
- "show me a Facebook post" → `RUN:` for facebook module
- "draft a Google Ads headline" → `RUN:` for google_ads module  
- "write me an email" → `RUN:` for email draft module
- "sample Google Ads ad" → `RUN:` for google_ads module

### Step 2 — Is the request broad or ambiguous?

If the user says "show me samples", "let me see examples", "give me something to look at", "draft something" without naming a specific artifact type:

→ Ask one question. Offer installed artifact categories in plain language. Do **not** dispatch.

```
Which sample should I create?

• Email draft
• Campaign plan
• Launch plan

I'll put it in Workspace.
```

### Step 3 — Artifact announced, not rendered

Once dispatched, the CMO's visible reply must announce, not render:

```
I'll create the installed draft artifacts.

They'll be ready in Workspace.
Nothing gets applied to Google Ads.
```

No Subject: line. No Headline: field. No copy block. No preview.

---

## Quality Gate

Before sending a reply when this skill is activated, verify:

1. No email Subject/Body appears in the visible reply text.
2. No ad Headline/Description appears in the visible reply text.
3. No social post copy appears in the visible reply text.
4. No invented budgets, targeting specs, or fake social proof appear.
5. If a RUN: line is appended, the reply does not also draft the artifact inline.
6. If no RUN: line is appended, the reply asks exactly one clarifying question.
