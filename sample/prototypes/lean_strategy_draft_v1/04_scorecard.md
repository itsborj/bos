# 04 — Prototype Scorecard

## What counts as a win

The prototype is successful only if the Strategy Draft is recognizably go-to-market strategy and is specific enough to brief execution specialists.

## Rubric

| Criterion | Pass signal | Score |
|---|---|---|
| Buyer-map fidelity | Uses awareness, buyer type, blocking forces, trust gap, and perceived likelihood. | 1–5 |
| GTM clarity | The artifact is a market-entry/reactivation strategy, not an email plan. | 1–5 |
| Message quality | Core message, positioning, proof arc, CTA, and objections are present inside the Strategy Draft. | 1–5 |
| Channel discipline | Gmail is a channel within the GTM motion, not the strategy itself. | 1–5 |
| Downstream readiness | The work orders are clear enough to execute. | 1–5 |
| Proof discipline | No invented metrics, case studies, or ROI. | 1–5 |
| Brand isolation | Klaroha only. | 1–5 |
| Lean workflow value | Fewer artifacts without losing buyer-map rigor. | 1–5 |

## Known failure from previous attempt

The previous seeded Stream artifact failed because it reused the existing BOS pipe:

```text
marketing.planning.gtm_plan + gtm_strategy block type
```

That made the prototype render as the current GTM Strategy surface, which invalidated the test.

This version avoids that by existing only as standalone files.
