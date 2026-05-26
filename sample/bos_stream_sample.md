# BOS Stream Sample — Gate 1 Deliverable

Status: sample only — for contract agreement, not implementation  
Date: 2026-05-20  
Brand context: Klaroha (agency operator, multi-brand)  
Active operator: agency owner, managing 3 client brands  

This document is the UX and data-contract target. Every card type, every field, and every build-state label shown here must be agreed before Gate 2 begins. This is not a wireframe. It is the semantic contract in written form.

---

## Context at the time of opening

Operator opens BOS at 8:47 AM. Two active brands with live campaigns: **Motormoto** (direct response, Meta + Google) and **Klaroha** (B2B pipeline, Gmail outreach). One brand in onboarding: **Halo Wellness** (ecom, supplement, not live yet).

The system has been running overnight. Stream shows 6 cards ranked by urgency across 2 brands, covering all six card families.

---

## Stream card order (ranked by urgency)

```
1. DECISION BRIEF     — Motormoto — ROAS anomaly requires judgment before budget decision
2. SETUP BLOCKER      — Halo Wellness — onboarding blocked, tracking unverifiable
3. PENDING ARTIFACT   — Klaroha — outreach sequence ready for approval
4. SIGNAL UPDATE      — Motormoto — creative fatigue detected, watching
5. OUTCOME / LEARNING — Klaroha — reactivation campaign closed, memory updated
6. COUNCIL BRIEF      — Motormoto — persistent budget dismissal, deliberation pending
```

---

## Card 1 — Decision Brief

**SOURCE STATE:** requires setup (GA4 connector live, Shopify manual, Meta live)

```
objective_ref:      Motormoto — hit $80k/month revenue, ROAS ≥ 3.2 by June 30
card_type:          decision_brief
why_now:            Meta ROAS up 18% over 7 days. Shopify revenue flat. Discrepancy requires
                    decision before Thursday budget review — if revenue is actually up, we
                    increase budget; if ROAS is inflated from attribution, we do not.
confidence:         directional (score: 0.52)
  staleness_score:  GA4 2 days old, Meta live, Shopify manually entered 3 days ago
  corroboration:    low — Meta and GA4 directionally consistent, Shopify not corroborating
  instrumentation:  flagged — checkout pixel last verified 11 days ago, status unknown
primary_evidence:
  - Meta Ads: ROAS 3.8 (7-day), up from 3.2 baseline (live connector)
  - GA4: purchase events +14% week-over-week (2 days old)
  - Shopify: revenue flat at $62k, unchanged from last manual entry (3 days ago, manually reported)
  - Tracking integrity: checkout pixel dependency unverified since May 9
hypothesis_ranking:
  1. Meta self-attribution inflation (confidence: high) — platform counting view-through
     conversions not represented in Shopify backend. Classic Meta vs backend discrepancy pattern.
     Memory: same pattern observed in March campaign, resolved by switching to 7-day click only.
  2. Shopify data is stale (confidence: medium) — manual entry 3 days old, actual revenue
     may have moved. Cannot corroborate without a fresh Shopify read.
  3. ROAS genuinely improved (confidence: low) — possible but unsupported until tracking
     integrity confirmed and Shopify data refreshed.
recommended_next:   Before any budget change — verify Shopify revenue manually and check
                    checkout pixel status. Do not increase budget on Meta ROAS alone when
                    backend revenue does not corroborate.
do_not_list:
  - Do not increase Meta budget until Shopify revenue confirms the move
  - Do not assume ROAS improvement is real without resolving the tracking integrity flag
  - Do not switch attribution windows without logging the decision in memory
approval_boundary:  BOS can investigate further (pull GA4, draft pixel audit checklist).
                    BOS cannot change budgets or attribution settings without approval.
allowed_actions:    [ investigate ] [ configure ] [ ask CMO ] [ dismiss ]
source_state:       Meta — live connector | GA4 — live connector | Shopify — manual (stale)
                    | Tracking — requires setup
```

**What the operator sees:** A card leading with the objective, the discrepancy in plain language, the top hypothesis, and one safe next step. No raw numbers pasted without interpretation. No recommendation to act when the data is unresolved.

---

## Card 2 — Setup Blocker

**SOURCE STATE:** requires setup (all Halo Wellness connectors pending)

```
objective_ref:      Halo Wellness — launch first paid campaign by June 15
card_type:          setup_blocker
why_now:            Campaign launch is 26 days away. No connector is installed. Without tracking,
                    BOS cannot read signals, cannot validate performance, and cannot close the
                    loop. Launch without instrumentation produces uninterpretable data.
confidence:         known (this is a state check, not an inference)
primary_evidence:
  - Halo Wellness workspace created May 12
  - 0 of 4 required connectors installed (Meta, Shopify, GA4, GTM)
  - Checkout pixel: not created
  - Brand context: incomplete (no product, no audience defined)
recommended_next:   Install Shopify connector first — it is the revenue source of truth. Then
                    Meta pixel. Then GA4. Brand context (product, audience) can be completed
                    in parallel by the operator while connectors are being configured.
approval_boundary:  BOS can generate the GTM/pixel spec and onboarding checklist. BOS cannot
                    install pixels or access platforms without connector authorization.
allowed_actions:    [ configure ] [ ask CMO ] [ dismiss ]
source_state:       all — requires setup
```

**What the operator sees:** A specific count of what is missing, a clear launch deadline, a prioritized setup sequence. Not a generic "complete your setup" banner. Actionable enough to forward to a developer or complete directly.

---

## Card 3 — Pending Artifact

**SOURCE STATE:** live connector (Gmail auth active, Klaroha)

```
objective_ref:      Klaroha — generate $40k pipeline from dormant prospects, Q2
card_type:          pending_artifact
why_now:            Reactivation sequence v2 drafted based on reply patterns from the April
                    campaign. Updated angle: case study lead (replaced feature-benefit lead
                    which had 8% reply rate vs 21% for case study angle in April).
confidence:         known (sequence uses validated angle from memory)
primary_evidence:
  - April campaign memory: case study angle 21% reply rate vs feature-benefit 8%
  - 47 dormant contacts identified (no reply in 90+ days, previously engaged)
  - Sequence: 3 emails over 9 days, case study lead, objection handling email 3
artifact_preview:
  Email 1 — Subject: "How [Client Name] cut their CAC by 34% in 6 weeks"
  Email 2 (Day 4) — Subject: "Quick follow-up — still relevant for you?"
  Email 3 (Day 9) — "One last thought before I move on"
  [View full sequence →]
recommended_next:   Review and approve or revise. If approved, BOS sends via Gmail connector
                    on operator-confirmed schedule. Default: Tuesday 9 AM.
approval_boundary:  BOS cannot send without approval. Once approved, BOS sends and monitors
                    replies autonomously. New high-intent replies surface as pending artifacts
                    for follow-up drafts.
allowed_actions:    [ approve ] [ revise ] [ dismiss ] [ ask CMO ]
source_state:       Gmail — live connector
```

**What the operator sees:** Why this sequence was built this way (memory-backed), what the angle is, a preview of the subject lines, and one clear action. No pasted full body copy in the card — that lives inside the artifact view.

---

## Card 4 — Signal Update

**SOURCE STATE:** live connector (Meta live, Motormoto)

```
objective_ref:      Motormoto — hit $80k/month revenue, ROAS ≥ 3.2 by June 30
card_type:          signal_update
why_now:            Creative set "summer_launch_v3" frequency crossed 4.2 over the last
                    5 days. No action required today. Watching. If frequency hits 5.0 before
                    new creative is ready, ROAS will likely follow the March fatigue pattern.
confidence:         directional (score: 0.71)
  corroboration:    medium — CTR down 6% on same creative set, directionally consistent
  instrumentation:  partially verified (Meta live, backend unconfirmed)
primary_evidence:
  - summer_launch_v3 frequency: 4.2 (Meta, live)
  - CTR trend: -6% over 5 days on same creative set
  - Memory: March fatigue event — frequency 5.1 preceded ROAS drop of 0.8 over 12 days
recommended_next:   No action needed today. BOS will surface a decision brief if frequency
                    reaches 4.8 and new creative is not approved. Operator can pre-approve
                    creative refresh now to prevent reactive decisions later.
approval_boundary:  BOS is watching autonomously. No approval needed until threshold crossed.
allowed_actions:    [ investigate ] [ ask CMO ] [ dismiss ]
source_state:       Meta — live connector
```

**What the operator sees:** What changed, why it might matter, what the precedent is, and what the system is doing about it. No decision required yet — but no surprises either when the next card surfaces at 4.8.

---

## Card 5 — Outcome / Learning

**SOURCE STATE:** manual (operator-registered outcome)

```
objective_ref:      Klaroha — generate $40k pipeline from dormant prospects, Q2
card_type:          outcome
why_now:            Reactivation campaign (April batch) closed. Operator registered outcome
                    May 18. Memory has been updated with results. This card confirms what
                    the system learned and how it will affect future runs.
confidence:         known (manually reported by operator)
primary_evidence:
  - 47 emails sent (April 15–24)
  - 10 replies (21% reply rate)
  - 4 calls booked
  - 1 deal in proposal stage ($18k)
  - 2 no-shows (memory: flag these contacts for different sequence timing)
  - Average reply: Day 2 (Email 2 drove most responses)
memory_updates_written:
  - case_study_angle: 21% reply rate, Klaroha cold reactivation context [topic: offer]
  - feature_benefit_angle: 8% reply rate same list [topic: offer]  
  - email_2 high_response: day 4 follow-up outperformed day 2 [topic: creative_fatigue]
  - no_show_pattern: 2 contacts flagged for timing variant [topic: commitment]
  - pipeline_created: $18k at proposal stage against $40k objective [topic: outcome]
recommended_next:   None — memory updated. Sequence v2 (Card 3) already incorporates these
                    learnings. System is ready for the next send batch.
allowed_actions:    [ dismiss ] [ ask CMO ]
source_state:       manual (operator-registered)
```

**What the operator sees:** What happened, what the system concluded from it, and what it changed in memory. Not just a result — a learning confirmation. The operator knows the system updated itself and why the next recommendation will be different.

---

## Card 6 — Council Brief

**SOURCE STATE:** planned automation (council capability not yet built)

```
objective_ref:      Motormoto — hit $80k/month revenue, ROAS ≥ 3.2 by June 30
card_type:          council_brief
trigger:            persistent_dismissal
why_now:            Operator dismissed Meta budget increase recommendations twice (May 14,
                    May 17) without providing a reason. Both briefs shared topic_tag: budget.
                    CMO did not generate a third recommendation. Council was convened instead
                    to investigate what the CMO is missing.
confidence:         directional — council deliberation, not signal analysis
perspectives:
  Strategist:       "The ROAS target of 3.2 was set against a different Shopify tracking
                    baseline. If the May 9 pixel regression is real, the historical ROAS
                    we are trying to match may itself be inflated. The objective may need
                    recalibration, not a budget increase."
                    confidence: medium | dissent: disagrees with Analyst on pixel severity

  Analyst:          "Two budget dismissals without explanation, combined with the tracking
                    gap, suggests the operator has information the system does not. Shopify
                    backend is the truth signal. Without it, any budget recommendation is
                    built on unresolvable uncertainty."
                    confidence: high | dissent: none on core diagnosis

  Creative:         "The creative signal (Card 4) is relevant here. Increasing budget on
                    a fatiguing creative set accelerates spend waste. Budget increase only
                    makes sense after creative refresh, regardless of ROAS reading."
                    confidence: high | dissent: none

  Channel Spec:     "Meta algorithmic phase — the account has been optimizing for 11 days.
                    Budget change in this window resets learning. Even if ROAS is real,
                    timing is wrong. Recommendation: hold until day 14 minimum."
                    confidence: high | dissent: none

  Devil's Advocate: "What if the operator knows the Shopify numbers are wrong and is waiting
                    for the correct data before acting? The dismissals may not be disagreement
                    with the logic — they may be disagreement with acting on bad data."
                    confidence: medium | dissent: reframes the entire premise

synthesis:          The council cannot unify on the root cause of the dismissals. All members
                    agree: budget increase is wrong right now. Reasons differ.
dissent_summary:    Strategist believes objective needs recalibration. Devil's Advocate
                    believes operator has information the system lacks. These are not
                    reconcilable without operator input.
recommended_next:   CMO poses four direct questions to the operator:
                    1. Is Shopify revenue data you are seeing different from what BOS has access to?
                    2. Is there a budget constraint (cash flow, client approval, seasonality)
                       you have not set in the system?
                    3. Do you believe the ROAS target of 3.2 needs to be revisited given
                       the tracking uncertainty?
                    4. Are you waiting for something specific before making a budget decision?
                    System will not generate another budget recommendation until one of these
                    is answered.
do_not_list:
  - Do not increase Meta budget until tracking integrity confirmed
  - Do not increase budget during algorithmic learning phase (before day 14)
  - Do not increase budget on fatiguing creative set without parallel refresh
constraint_flags:
  - suspected: operator has Shopify data not connected to BOS
  - suspected: unstated budget ceiling or client approval requirement
allowed_actions:    [ respond to CMO ] [ configure ] [ dismiss ]
source_state:       planned automation (CMO Council not yet built — this card generated manually
                    for sample purposes; capability scheduled for Gate 3)
```

**What the operator sees:** The full council deliberation — not just the conclusion. Four specific questions, not another recommendation. The system stopped recommending and started investigating. This is a fundamentally different interaction mode from the default decision brief.

---

## Allowed vs forbidden behavior — contract

| Situation | Allowed | Forbidden |
|---|---|---|
| ROAS signal arrives | BOS interprets it against memory, surfaces if it changes recommended action | BOS increases or changes budget automatically |
| Artifact is approved | BOS executes the approved action via plugin | BOS modifies the artifact content post-approval |
| Operator dismisses a card without reason | BOS writes `decision_not_to_act` to memory, continues watching | BOS re-surfaces the same card with different framing |
| Operator dismisses same topic_tag twice without reason | BOS convenes CMO Council instead of third recommendation | BOS generates third recommendation of same type |
| Setup blocker exists | BOS surfaces it in Stream with prioritized resolution steps | BOS silently skips that connector in signal reads |
| Tracking integrity is unverified | BOS attaches confidence penalty to all signals through that dependency | BOS treats unverified tracking as verified |
| Council produces questions | BOS poses questions, waits for operator response | BOS acts on hypotheses before constraints are resolved |
| Morning session starts | BOS hydrates CMO context from memory (active objectives, pending decisions, known risks) | BOS starts with zero context and waits to be asked |

---

## Build state labels — definitions

| Label | Meaning |
|---|---|
| `live connector` | Active authenticated integration, reads running on schedule |
| `manual` | Operator-entered data; accuracy depends on operator diligence |
| `manual (stale)` | Manual entry older than expected cadence — confidence degraded |
| `planned automation` | Capability specified, not yet built; card type shown for contract agreement |
| `requires setup` | Connector not authorized or configured; data unavailable |
| `partially built` | Core function works, edge cases or full lifecycle not yet implemented |

---

## What this sample does not show (and why)

- **Omnichannel signal synthesis** — Gate 3. Single connector loop not yet proven.
- **Automated morning brief** — Gate 3. Requires Watchpoints runtime operational.
- **Automated council trigger** — Gate 3. Requires memory and decision briefs to brief members meaningfully.
- **Cross-brand command center** — Gate 3. Objective/card contracts must exist first.
- **Real-time signal streaming** — not in scope. Scheduled reads at connector-declared cadence.

These absences are not gaps in the product vision. They are build sequencing decisions. The Gate 1 sample establishes the contract for what does get built, in the order it gets built.
