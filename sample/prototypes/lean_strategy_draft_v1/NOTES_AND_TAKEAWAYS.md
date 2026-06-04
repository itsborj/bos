# Notes & Takeaways — Lean Strategy Workflow Prototype

Date: 2026-06-03  
Location: `sample/prototypes/lean_strategy_draft_v1/`  
Prototype route: `/prototype/strategy-draft`

## Why this exists

The original GTM/marketing-plan workflow was too artifact-heavy and overloaded CMO chat/Stream. The useful strategic thinking should live on a dedicated workflow page, while CMO chat should remain a short control surface that creates or links to that page.

Correct high-level behavior:

```text
CMO chat
→ short confirmation + link
→ external Strategy Workflow page
```

Not:

```text
CMO chat or Stream
→ huge pasted plan
→ overloaded single artifact card
```

## Core workflow hypothesis

Buyer mapping should remain mandatory.

The leaner move is not to remove buyer intelligence. The move is to collapse the separate message-architecture + GTM-plan ceremony into a modular Strategy Workflow page.

Working shape:

```text
Market Context / Evidence
→ Buyer Map
→ Strategy Draft
→ Framework Lenses
→ Offer / Resource Architecture
→ Tactical Funnel
→ Channel / Content Matrix
→ Measurement Model
→ Work Orders
```

## Important correction from failed attempts

Do not prototype this by reusing existing production piping.

Bad approach that failed:

```text
marketing.planning.gtm_plan
+ gtm_strategy block type
+ Stream card
```

Why it failed:

- rendered as the existing GTM Strategy surface
- confused prototype with production GTM
- made Gmail look like the strategy when it was only a channel
- polluted Stream with seeded prototype runs

Correct prototype boundary:

```text
standalone page only
no /chat call
no /runs call
no production module IDs
no Stream artifacts
no gtm_strategy block
```

## Current prototype page behavior

Route:

```text
/prototype/strategy-draft
```

The page now shows:

- active modules as selectable
- non-wired modules visibly disabled/greyed out
- framework lenses marked `not wired`
- explanation that locked modules are planned structure only

Currently active prototype path:

```text
Buyer Map
→ Strategy Draft / Strategic Thesis
→ Offer / Resource Architecture
→ Tactical Funnel
→ Work Orders
```

Currently disabled / not wired:

```text
Market Context
Channel Economics
StoryBrand Lens
Channel / Content Matrix
Measurement Model
Framework lens execution
```

The disabled modules are intentionally visible because they define the future architecture, but they should not imply working functionality.

## CMO chat behavior takeaway

CMO chat should not dump the strategy body.

Target reply pattern:

```text
I built the Strategy Workflow.

It starts with the buyer map, then turns that into the strategy draft and work orders.

[Open Strategy Workflow]
```

The page owns the full work. Chat only controls and links.

## Component model takeaway

Each workflow component can become an independent skill/component later.

Potential component skills:

| Component | Purpose |
|---|---|
| Market Context | Ground strategy in facts, local data, channel economics, or market thesis |
| Buyer Map | Mandatory buyer substrate: awareness, blockers, trust gap, buyer language |
| Strategy Draft | Main management-alignment decision and GTM thesis |
| StoryBrand Lens | Narrative/message lens, not the whole workflow |
| JTBD Lens | Buyer progress and job-to-be-done clarity |
| Forces Lens | Push, pull, anxiety, habit |
| Value Equation Lens | Offer strength and weakness |
| Category Design Lens | Villain, new category, strategic contrast |
| Offer Architecture | Resource/lead magnet/micro-goal/macro-activation ladder |
| Tactical Funnel | Reach → Engage → Action → Patronage |
| Channel Matrix | Repurpose one concept across channels/formats |
| Measurement Model | Reach, engagement, action, patronage metrics and learning loop |
| Work Orders | Specialist-ready downstream briefs |

## GTM archetype takeaway

The Strategy Workflow should not use one fixed template for all businesses.

It needs an archetype detector that changes which modules matter most.

### Golden Gate archetype

```text
Local market + emotional urgency + broker distribution + 30-day activation
```

Important modules:

- local market context
- buyer hunger map
- offer ladder
- lead magnet strategy
- broker/partner distribution
- tech/ops readiness
- 30-day activation work orders

### Gold Smelting archetype

```text
Venture / trading infrastructure + product proof + monetization thesis + fundraising
```

Important modules:

- market thesis
- product proof
- monetization ladder
- investor narrative
- legal/risk structure
- demo/productization roadmap

### Teko archetype

```text
Performance-led brand demand creation / channel economics arbitrage
```

Important modules:

- channel economics read
- branded vs generic CPA analysis
- paid search as demand harvesting
- organic/content/social as branded-demand manufacturing
- retention/advocacy loop
- REAP measurement

## Teko insight to preserve

Teko showed the strongest channel-economics pattern:

```text
Do not scale the expensive channel blindly.
Use paid search data to identify demand.
Use organic/content/social to manufacture future lower-cost branded demand.
```

This created the need for a `Channel Economics` module.

## Golden Gate insight to preserve

Golden Gate showed that a strategy workflow can be a full operating model:

```text
Market context
→ problem
→ hungry segments
→ offer ladder
→ lead magnets
→ broker program
→ tech stack
→ decision roles
→ 30-day activation
```

This created the need for modular workflow sections instead of one plan card.

## Framework lens takeaway

Frameworks should be optional lenses, not hardcoded whole workflows.

Examples:

- StoryBrand: character, problem, guide, plan, CTA, stakes
- JTBD: progress the buyer is trying to make
- Forces of Progress: push, pull, anxiety, habit
- Value Equation: dream outcome, perceived likelihood, time, effort
- Category Design: villain and new category
- REAP: Reach, Engagement, Action, Patronage measurement

## Design caveat

The current page is structurally useful but visually rough. It should be redesigned later as a proper workflow/workbench, not a static card dump.

Desired future UX:

```text
left rail: modules + status
main panel: selected module result
right rail: inputs, assumptions, actions, revisions
bottom: next work orders / approval gate
```

## Next prototype step

Before production implementation, build a dynamic sandbox runner that:

1. Accepts a brand/request.
2. Generates Buyer Map.
3. Generates Strategy Draft from Buyer Map.
4. Applies selected lenses.
5. Generates Work Orders.
6. Saves to a strategy-workflow record/page.
7. Returns a link to CMO chat.

Still avoid the existing production GTM module until the shape is approved.

## Production direction if approved

Future route shape:

```text
/strategy-workflows/:workflowId
```

Future state model:

```json
{
  "workflow_type": "strategy_workflow",
  "brand_id": "...",
  "request": "...",
  "archetype": "performance_led_brand_demand_creation",
  "components": [
    {"type": "buyer_map", "status": "complete", "artifact_id": "..."},
    {"type": "strategy_draft", "status": "complete", "artifact_id": "..."},
    {"type": "storybrand_lens", "status": "not_wired"},
    {"type": "work_orders", "status": "draft", "artifact_id": "..."}
  ]
}
```

Approval should happen at the workflow/component level, not inside a giant chat response.
