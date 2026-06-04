# Strategy Draft Artifact v1 — Shadow Prototype Sample

Status: draft prototype 2026-06-03  
Purpose: prove a leaner marketing-plan workflow without touching the existing GTM pipeline.

## Prototype workflow

```text
User request
→ buyer_map.v1 remains mandatory
→ Strategy Draft combines message architecture + plan
→ optional downstream artifact brief
```

This prototype intentionally does **not** change:

- `api/capabilities/marketing/planning/gtm_plan/`
- `api/routers/chat.py`
- `api/routers/runs.py`
- Stream approval behavior
- production upstream hydration

## User request

```text
Generate pipeline from dormant prospects through Gmail.
```

## Allowed output shape

```text
# Strategy Draft — Klaroha

## Buyer map consumed
Concise statement of the buyer model used.

## Strategic decision
One clear decision about the path to pipeline.

## Message architecture
Core message, positioning, proof arc, objections, CTA.

## Channel workflow
Do now / Hold / Avoid.

## Gmail pipeline brief
What the downstream Gmail specialist should build.

## Assumptions to validate
Only assumptions that could change the plan.

## Approval note
Draft only. No sending, publishing, spend, or external action without approval.
```

## Forbidden outcomes

### Forbidden 1 — no buyer map

```text
Let's create a general email campaign for your audience.
```

Why forbidden: the buyer map is mandatory substrate. The strategy must state which buyer signals determined the plan.

### Forbidden 2 — bloated three-artifact ceremony

```text
First I need to generate buyer intelligence, then message architecture, then a GTM plan, then a channel plan, then an email plan.
```

Why forbidden for this prototype: buyer mapping stays, but message architecture and planning are collapsed into one reviewable Strategy Draft.

### Forbidden 3 — fake proof or metrics

```text
This will recover 20% of dormant prospects and book 50 demos.
```

Why forbidden: no performance baseline was loaded.

### Forbidden 4 — brand bleed

```text
MotorMoto should invite first-time motorcycle buyers to the showroom.
```

Why forbidden: the active prototype brand is Klaroha. Cross-brand content fails the prototype.

## Actual prototype outputs

See:

```text
sample/prototypes/strategy_draft/klaroha_dormant_gmail/01_buyer_map.md
sample/prototypes/strategy_draft/klaroha_dormant_gmail/02_strategy_draft.md
sample/prototypes/strategy_draft/klaroha_dormant_gmail/03_downstream_gmail_pipeline.md
sample/prototypes/strategy_draft/klaroha_dormant_gmail/04_review_rubric.md
```
