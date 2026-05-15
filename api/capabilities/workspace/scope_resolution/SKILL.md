---
id: workspace.scope_resolution
name: brand-scope-resolution
description: Use on every CMO chat turn in a multi-brand workspace. Resolve conversation scope separately from artifact execution scope when a user mentions, compares, switches, or creates work for a Brand.
version: 1.0.0
status: active
scope: workspace
allowed_from_chat: true
module_id: null
requires_intent:
  - discussion
  - generation
  - diagnostic
  - revision
triggers:
  - brand
  - for
  - how about
  - compare
  - switch
  - shift
  - same for
  - them too
  - another one
memory_slots:
  - brand_roster
resources:
  - NOTE.md
quality_gates:
  - never_generate_artifact_without_execution_brand
  - brand_mentions_do_not_always_switch_conversation_scope
  - artifact_output_must_match_execution_brand
metadata:
  type: scope_policy
  owner: cmo_chat
---

# Brand Scope Resolution

This skill is the CMO chat note for multi-brand scope.

Separate three scopes:

1. **Conversation scope** — the Brand currently being discussed.
2. **Execution scope** — the Brand an artifact/run belongs to.
3. **Comparison scope** — Brands mentioned only for contrast or reference.

## Rules

- A Brand mention is not automatically a switch.
- If the user asks to create, draft, run, build, make, or check work **for Brand X**, set `execution_brand: Brand X`.
- If the user says “how about Brand X”, “same for Brand X”, or “them too” after an artifact request, treat it as an equivalent artifact for Brand X only when the prior turn created or requested an artifact.
- If the user asks “what does Brand X do differently?” while another Brand is active, keep the current conversation Brand unless the user explicitly asks to switch.
- If the user asks to switch, shift, change to, or work on Brand X, set `conversation_brand: Brand X`.
- If execution scope is clear and the user is asking for a new/equivalent artifact, append the matching RUN line. Do not ask for Brand profile details; BOS will hydrate the execution Brand's profile, products, audiences, docs, and Brand Kit for the module.
- If execution scope is unclear and a RUN would be needed, ask one question and append no RUN line.
- Never create an artifact without one execution Brand.
- Never use one Brand’s products, audience, docs, or Brand Kit in another Brand’s artifact.

## Required hidden output

Every CMO reply must include this hidden block before the visible reply:

```text
SCOPE:
conversation_brand: <Brand name or none>
execution_brand: <Brand name or none>
mode: <discussion|switch|comparison|new_artifact|equivalent_artifact|clarify>
confidence: <high|medium|low>
```

Examples:

```text
SCOPE:
conversation_brand: Klaroha
execution_brand: MotorMoto
mode: equivalent_artifact
confidence: high

I’ll make the MotorMoto version with its motorcycle-buyer profile.
RUN: marketing.channel.google_ads.search_text.draft
```

```text
SCOPE:
conversation_brand: Klaroha
execution_brand: none
mode: comparison
confidence: high

MotorMoto is a different business type, so I’d compare it separately from Klaroha’s demand-capture positioning.
```
