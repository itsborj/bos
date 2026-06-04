# Strategy Workflow Modular v2 — BITE Stage 2 Sample

Status: draft sample — awaiting human approval before reverse-spec/build  
Date: 2026-06-05  
Purpose: reset Strategy Workflow away from a black-box monolith and toward a thin workflow shell that calls independent optional mini-modules.

---

## User request

```text
Build a marketing plan for dormant prospects.
```

## Correct CMO chat output

```text
Building the Strategy Workflow for Klaroha.

I’ll create the core strategy, then attach any enhancer modules that complete.
If one enhancer fails, the workflow still opens with the data that succeeded.

[Open Strategy Workflow]
```

---

## Correct Strategy Workflow artifact output

```md
# Strategy Workflow — Klaroha

Status: usable_with_gaps
Request: Build a marketing plan for dormant prospects.

## Strategy summary
Wedge: Find the marketing-to-pipeline leakage point before adding more campaigns.
Primary motion: founder-led
Decision: Start with a low-risk diagnostic motion for known dormant demand.
Confidence: partial

Used inputs:
- brand_brief: complete
- buyer_map: complete
- offer_architecture: complete
- channel_stack: complete
- market_context: unavailable
- channel_economics: failed safely
- measurement_model: skipped, no baseline data

## Enhancer cards

### Buyer Map
Status: complete
Required: no
Confidence: inferred
Inputs used:
- brand_brief
Missing inputs:
- market_context

Output:
- awareness_level: problem_aware
- buyer_type: early_majority
- trust_gap: proof that Klaroha keeps approval control before execution
- buyer_language:
  - "I need control without becoming the bottleneck."
  - "I don’t want another tool that creates more follow-up work."

### Market Context
Status: failed
Required: no
Impact: not included in synthesis
Reason: provider timeout
Retry available: yes

Output:
- evidence_gap: no live market context was available for this run

### Offer Architecture
Status: complete
Required: no
Confidence: partial
Inputs used:
- brand_brief
- buyer_map

Output:
- resource: One-Leakage-Point Diagnostic
- micro_commitment: reply with the least-clear part of the current marketing flow
- macro_activation: approve a scoped implementation sprint
- proof_required: visible artifact trail from plan → approval → execution

### Channel Stack
Status: complete
Required: no
Confidence: partial
Inputs used:
- brand_brief
- buyer_map
- offer_architecture
Missing inputs:
- market_context
- channel_economics

Do now:
1. Founder email — direct trust-building against a high-anxiety buyer
2. Diagnostic landing page — conversion hub for the one-leakage-point offer
3. LinkedIn proof posts — show approval-gated operating-loop examples

Hold:
- Paid social — unlock after proof story exists

Avoid:
- Broad automation messaging — avoid because anxiety is high

### Measurement Model
Status: skipped
Required: no
Reason: no baseline performance data loaded

Output:
- no numeric targets generated
- evidence_gap: baseline reply rate, diagnostic booking rate, and source quality are missing
```

---

## Required behavior

1. The workflow shell is thin: create workflow, call enhancer modules, persist component results, synthesize from available data, return artifact link.
2. Each enhancer is independently callable and independently persisted.
3. Every enhancer declares whether it is required. Default is optional.
4. Failed optional enhancers become component cards with `status: failed`; they do not fail the workflow.
5. Skipped enhancers become component cards with `status: skipped` and a reason.
6. Synthesis uses only successful component outputs and lists missing inputs as evidence gaps.
7. The artifact can be `complete`, `usable_with_gaps`, or `failed_core`; it is not binary success/failure.
8. The source of truth is typed component JSON, not markdown parsing.
9. Chat returns a short confirmation and link only. Workspace/Stream render the workflow.

---

## Forbidden outcomes

### Forbidden 1 — black-box monolith

```md
A single giant strategy document is generated in one LLM call, then parsed into fake components.
```

Why forbidden: component boundaries are not real; one prompt or parser bug can corrupt the whole artifact.

### Forbidden 2 — optional enhancer blocks the plan

```md
The workflow failed because market_context failed.
```

Why forbidden: `market_context` is an optional data point. Its failure should create an evidence gap, not block planning.

### Forbidden 3 — hidden cascade failure

```md
buyer_map is empty but marked complete because a parser returned empty fields.
```

Why forbidden: component quality gates must validate typed fields before a component can be marked complete.

### Forbidden 4 — chat becomes the artifact plane

```text
Here is the full marketing plan:
[entire strategy pasted into CMO chat]
```

Why forbidden: CMO chat is the narrative/control surface; Workspace/Stream own native artifact rendering.

### Forbidden 5 — workflow-specific logic in core

```py
if module_id == "marketing.planning.strategy_workflow":
    persist_special_rows()
```

Why forbidden: capability-specific persistence/orchestration should move behind generic capability contracts or lifecycle hooks, not hardcoded core branches.
