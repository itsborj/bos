# Strategy Workflow — Component Map

**Status:** v1 production prototype live; v2 modular architecture reset drafted.  
**Prototype routes:** `/prototype/strategy-draft`, `/prototype/golden-gate-plan`, `/prototype/motormoto`  
**Production route shape:** `/strategy-workflows/:workflowId`  
**BITE v2 sample:** `sample/strategy_workflow_modular_v2.md` — awaiting approval before reverse-spec/build.  
**Last updated:** 2026-06-05

---

## What this is

The Strategy Workflow is the modular big-brother of `marketing.planning.gtm_plan`. Where the GTM plan is a single-shot document, the Strategy Workflow decomposes every section into independently persisted component cards with typed JSON output contracts. CMO chat links to the workflow page — it does not dump the strategy body.

**Architecture reset (2026-06-05):** the first live implementation proved the UX but is drifting toward a black-box monolith: one large module prompt, markdown parsing, router-owned component prompts, and capability-specific persistence hooks. Treat the current implementation as a production prototype, not the final architecture. Before adding more components, refactor toward the BITE v2 sample in `sample/strategy_workflow_modular_v2.md`.

The v2 target is: a thin workflow shell creates the workflow, discovers/calls independent optional enhancer modules, persists each result, and synthesizes from whatever succeeded. A failed optional enhancer creates a failed/skipped component card and evidence gap; it must not fail the whole workflow.

---

## v2 Architecture Guardrails

1. **Workflow shell stays thin.** It owns workflow creation, component discovery, component execution orchestration, persistence, and artifact linking — not every prompt/parser.
2. **Mini-modules are real capabilities.** Each enhancer owns its `SKILL.md`, `module.py`, `template.j2`, output contract, and quality gates.
3. **Default failure policy is non-blocking.** Components are optional unless their contract explicitly says `required: true`.
4. **No markdown-as-source-of-truth.** Components return typed JSON. Markdown is only display rendering.
5. **Synthesis is another component.** `strategy_synthesis` consumes available component outputs and records missing/failed enhancers as evidence gaps.
6. **No hidden cascade failure.** A stale/failed upstream component becomes a missing input; downstream components may still run with lower confidence unless their own contract forbids it.
7. **No capability-specific core branches.** Strategy Workflow persistence/orchestration should move behind generic capability contracts or lifecycle hooks, not hardcoded `runs.py` / router logic.
8. **Status is not binary.** Workflow status can be `complete`, `usable_with_gaps`, `failed_core`, or `in_progress`; components can be `complete`, `failed`, `skipped`, `stale`, or `not_wired`.

---

## Dependency DAG

```
Brand Brief (injected, always available)
        │
        ▼
  Market Context ─────────────────────────┐
        │                                 │
        ▼                                 │
    Buyer Map ◄──────────────────────────-┘
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
  Strategic Thesis           [Framework Lenses] (optional overlay)
        │                                  │
        ├────────────────┐                 │ (no downstream cascade — read-only)
        ▼                ▼                 │
  Offer Architecture  Channel Stack ◄──────┘
        │                  │
        └────────┬──────────┘
                 ▼
          Tactical Funnel
                 │
        ┌────────┴──────────┐
        ▼                   ▼
  Measurement Model   Channel/Content Matrix
        │
        └──────────────────────┐
                               ▼
                           Work Orders
```

**Rules:**
- Buyer Map is the only mandatory substrate. Market Context enriches but does not block.
- Framework Lenses are read-only overlays — they consume fields but produce no fields that cascade downstream.
- Work Orders are the terminal node — they consume everything above them.
- If a component re-runs, every component that lists one of its `output_fields` in `input_fields_consumed` goes `stale`.

---

## Brand Brief *(injected, not a component)*

```
brand_name, voice, tone, values[], domain, archetype
```

Always available. Injected into every component prompt.

---

## Component Field Contracts

### 1. Market Context

```yaml
component_type: market_context
status: optional

input_fields_consumed:
  - brand_brief.*

output_fields:
  - market_facts[]          # what is demonstrably true about this market
  - demand_signal           # evidence that demand already exists
  - competitor_contrast     # how existing options fail this buyer
  - evidence_gaps[]         # what market data is missing
  - archetype_modifier      # hint to downstream: which archetype weight to apply
```

---

### 2. Buyer Map *(mandatory substrate)*

```yaml
component_type: buyer_map
status: mandatory

input_fields_consumed:
  - brand_brief.*
  - market_context.market_facts
  - market_context.demand_signal

output_fields:
  - awareness_level         # unaware | problem_aware | solution_aware | product_aware
  - buyer_type              # earlyvangelists | early_majority | late_majority
  - adoption_stage
  - push_forces[]
  - pull_forces[]
  - blocking_forces[]       # anxiety | habit | low_perceived_likelihood | switching_cost
  - anxiety_sources[]       # specific fears, named
  - habit_forces[]
  - trust_gap               # single most important proof deficit
  - buyer_language[]        # exact phrases buyers use
  - decision_roles:
      champion:
      economic_buyer:
      veto:
  - confidence              # inferred | partial | validated
```

---

### 3. Strategic Thesis

```yaml
component_type: strategic_thesis
status: active

input_fields_consumed:
  - buyer_map.awareness_level
  - buyer_map.buyer_type
  - buyer_map.blocking_forces
  - buyer_map.trust_gap
  - buyer_map.decision_roles
  - brand_brief.values

output_fields:
  - archetype               # golden_gate | gold_smelting | teko | direct_sales | ...
  - primary_motion          # founder-led | sales-led | product-led | content-led | partner-led | community-led
  - secondary_motion        # nullable
  - secondary_unlock        # condition string, nullable
  - wedge                   # one sentence: the strategic entry point
  - decision                # what we are choosing to do
  - not_doing[]             # explicit strategic no-list
  - motion_rationale
  - failure_mode            # first thing that breaks if the motion is wrong
  - confidence
```

---

### 4. Framework Lenses *(optional, no downstream cascade)*

```yaml
component_type: framework_lens
status: optional overlay

input_fields_consumed:
  - buyer_map.*
  - strategic_thesis.wedge
  - strategic_thesis.primary_motion

# Lenses produce display output only. No field cascades downstream.
output_fields_by_lens:
  storybrand:
    - character
    - problem
    - guide
    - plan
    - cta
    - success_stakes
  jtbd:
    - job_statement
    - progress_barriers[]
    - hire_context
  forces:
    - push
    - pull
    - anxiety
    - habit
  value_equation:
    - dream_outcome
    - perceived_likelihood
    - time_delay
    - effort_sacrifice
  category:
    - villain
    - new_category
    - strategic_contrast
  reap:
    - reach_metric
    - engagement_metric
    - action_metric
    - patronage_metric
```

---

### 5. Offer Architecture

```yaml
component_type: offer_architecture
status: active

input_fields_consumed:
  - buyer_map.blocking_forces
  - buyer_map.trust_gap
  - buyer_map.buyer_language
  - strategic_thesis.primary_motion
  - strategic_thesis.wedge

output_fields:
  - audience_need
  - resource                # the lead magnet / diagnostic / entry asset
  - micro_commitment        # lowest-friction first step
  - macro_activation        # the actual commercial goal
  - offer_ladder[]          # ordered steps from zero-commitment to full
  - anxiety_treatment       # how each rung handles the dominant anxiety
  - proof_required          # what proof must exist before the offer is credible
```

---

### 6. Channel Stack

```yaml
component_type: channel_stack
status: active

input_fields_consumed:
  - buyer_map.awareness_level
  - buyer_map.buyer_type
  - buyer_map.blocking_forces
  - strategic_thesis.primary_motion
  - offer_architecture.micro_commitment

output_fields:
  - do_now[]:               # max 3 channels
      channel
      role
      rationale
      buyer_map_signal
      proof_required
  - hold[]:
      channel
      hold_reason
      unlock_condition      # must be specific enough to act on
  - avoid[]:
      channel
      avoid_reason
      buyer_map_signal
```

---

### 7. Tactical Funnel

```yaml
component_type: tactical_funnel
status: active

input_fields_consumed:
  - channel_stack.do_now
  - offer_architecture.offer_ladder
  - offer_architecture.micro_commitment
  - strategic_thesis.primary_motion

output_fields:
  - reach:
      tactic
      channel
      parallel_track
  - engage:
      resource
      sequence
      objection_surface
  - action:
      cta
      commitment_level
      next_step_after
  - patronage:
      response_categories[]
      proof_capture
      learning_loop
```

---

### 8. Channel / Content Matrix

```yaml
component_type: channel_content_matrix
status: not_wired

input_fields_consumed:
  - strategic_thesis.wedge
  - channel_stack.do_now
  - channel_stack.hold
  - tactical_funnel.reach

output_fields:
  - core_concept            # the one idea repurposed across channels
  - channel_variants[]:
      channel
      format
      content_type
      repurpose_from
  - assets_needed[]
```

---

### 9. Measurement Model

```yaml
component_type: measurement_model
status: not_wired

input_fields_consumed:
  - tactical_funnel.*
  - channel_stack.do_now
  - strategic_thesis.primary_motion

output_fields:
  - reach_metrics[]
  - engagement_metrics[]
  - action_metrics[]
  - patronage_metrics[]
  - stage_gates[]:
      stage
      gate_condition
      if_not_met
      unlock
```

---

### 10. Work Orders *(terminal node)*

```yaml
component_type: work_orders
status: active

input_fields_consumed:
  - strategic_thesis.wedge
  - strategic_thesis.primary_motion
  - offer_architecture.offer_ladder
  - offer_architecture.resource
  - channel_stack.do_now
  - tactical_funnel.*
  - measurement_model.stage_gates

output_fields:
  - briefs[]:
      order
      title
      purpose
      contents[]
      gate
      owner_type
```

---

## Archetype Weight Table

| Component | Golden Gate | Gold Smelting | Teko | Direct Sales |
|---|---|---|---|---|
| Market Context | **primary** | secondary | **primary** | optional |
| Buyer Map | **primary** | secondary | **primary** | **primary** |
| Strategic Thesis | secondary | **primary** | secondary | **primary** |
| Framework Lenses | StoryBrand | Category Design | REAP | JTBD / Forces |
| Offer Architecture | **primary** | secondary | not applicable | **primary** |
| Channel Stack | secondary | not applicable | **primary** | secondary |
| Tactical Funnel | **primary** | not applicable | **primary** | secondary |
| Channel Matrix | not applicable | not applicable | **primary** | optional |
| Measurement Model | secondary | not applicable | **primary** | secondary |
| Work Orders | **primary** (30-day) | investor narrative | channel briefs | sales briefs |

**Primary** = rendered expanded by default.  
**Secondary** = rendered collapsed, expandable.  
**Not applicable** = hidden unless explicitly requested.

### Archetype signals

**Golden Gate:** local market + emotional urgency + broker/partner distribution + 30-day activation window  
**Gold Smelting:** venture / trading / infrastructure + product proof + monetization thesis + fundraising narrative  
**Teko:** performance-led brand demand creation / channel economics arbitrage  
**Direct Sales:** single-motion sales-led or founder-led, trust gap as primary blocker, no broker layer

Archetype is detected at workflow creation time from the brand brief and request context. It sets component weights and injects archetype-specific context into each component prompt.

---

## Cascade Rules

When a component re-runs, mark stale everything that lists any of its `output_fields` in `input_fields_consumed`:

| Component re-runs | Goes stale |
|---|---|
| Market Context | Buyer Map |
| Buyer Map | Strategic Thesis, Offer Architecture, Channel Stack, Framework Lenses |
| Strategic Thesis | Offer Architecture, Channel Stack |
| Offer Architecture | Tactical Funnel |
| Channel Stack | Tactical Funnel, Channel/Content Matrix |
| Tactical Funnel | Measurement Model, Work Orders |
| Measurement Model | Work Orders |
| Framework Lenses | nothing (overlay only) |

CMO chat cascade behavior:

```
User: "Revise the strategic thesis."
CMO: "Strategic thesis revised.
      Offer architecture and channel stack depend on it —
      want me to update those too, or review the thesis first?
      [Open Strategy Workflow]"
```

Auto-cascade vs gated-cascade is a UI policy decision, not an architecture decision. The stale marking is always deterministic.

---

## Workflow Record Schema (production target)

```json
{
  "workflow_id": "wf_abc123",
  "brand_id": "...",
  "brand_name": "Brand Name",
  "archetype": "golden_gate",
  "request": "the original user request",
  "status": "in_progress | complete | stale",
  "components": [
    {
      "component_type": "buyer_map",
      "status": "complete | stale | not_wired | pending",
      "version": 1,
      "data": { "awareness_level": "solution_aware", "..." : "..." },
      "input_fields_consumed": [],
      "output_fields": ["awareness_level", "buyer_type", "blocking_forces", "trust_gap"],
      "run_id": "...",
      "updated_at": "..."
    }
  ]
}
```

---

## Chat Re-Entry Endpoint (production target)

```
PATCH /strategy-workflows/{id}/components/{type}
Body: { "override": "string instruction", "cascade": true | false }
```

Re-runs the target component, marks stale dependents, returns a summary diff. CMO chat consumes the diff to compose its reply.

---

## Render Density by Surface

Each component exposes two render densities from the same JSON data:

| Surface | Density | What renders |
|---|---|---|
| Full workflow page | detail | all sections expanded |
| Stream artifact card | compact | component title + 2–3 key fields + status badge |
| CMO chat reply | summary | one sentence + link |
| Mobile card | summary | wedge / primary motion / CTA to open |

The `summary` field on each component output is a one-sentence distillation computed by the generating module. Chat and mobile render the summary. The page renders the full `data` object.

Production API note: persisted workflow components returned by `GET /strategy-workflows/{id}` use `component_type`; the module artifact block stored on the run uses `components[].type`. Frontend remaps `component_type` to the view model.

Header UX note: the production workflow page dark header renders a small white kicker (`Strategy Workflow · {archetype}`) and the main white headline `{BrandName} Marketing Strategy`. Do not reintroduce a green-on-green headline or the duplicate `Strategy Workflow — Direct Sales` title.

---

## Build Prerequisites

Before coding individual component modules:

1. The workflow record model (`WorkflowRun`, `WorkflowComponent`) must be migrated.
2. `PATCH /strategy-workflows/{id}/components/{type}` endpoint must exist before any frontend wiring.
3. Each component needs its own `SKILL.md` declaring `input_fields_consumed` and `output_fields` in frontmatter — this is what makes the cascade deterministic at runtime.
4. The sandbox runner (accepts brand/request → generates chain → returns workflow link) is the first end-to-end proof, not the full production UI.
5. Do not wire CMO chat to the workflow until the sandbox runner produces a valid `workflow_id`.
