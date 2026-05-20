# BOS Gate 2 UX/UI Coordination — Stream, CMO, Admin

Status: UX prototype complete — engineering track open  
Date: 2026-05-20  
Scope: UX/UI alignment for Gate 2 only — Gmail-only objective loop  
Prototype: `wireframes/bos-gate2-prototype.html`  

---

## Source references

Use this file as the working coordination brief. The deeper docs are reference only; do not reload them for every discussion unless a decision below is challenged.

- `PROJECT_BRIEF.md` — official project direction, v3.30
- `sample/bos_systems_architecture.md` — full architecture rationale and Gate 2/Gate 3 split
- `sample/bos_stream_sample.md` — approved Stream card semantic contract
- `sample/bos_cmo_objective_runtime_market_model.md` — long-form operating model and Watchpoints thinking
- `memory/project_admin_usecases.md` — admin/persona use-case audit
- `wireframes/bos-stream-first.html` — current prototype to optimize after this coordination pass

---

## Current agreement

BOS is a judgment system, not a content factory.

The human operator should only need to:

```text
steer → judge → approve
```

The system should handle:

```text
observe → interpret → remember → recommend → prepare → escalate when needed
```

Gate 2 proves this with one channel: **Gmail**.

If BOS cannot create economic movement with Gmail alone, more connectors will only create noise.

---

## Gate 2 north-star loop

```text
Objective
→ read Gmail context / signal
→ create approved outreach artifact
→ execute approved Gmail action or register manual send
→ read or manually register replies/outcome
→ evaluate outcome
→ write memory
→ produce a better next recommendation
```

Gate 2 passes only when memory makes the next recommendation better than the first one.

---

## UX/UI goal before code

Before backend refactor or system implementation, produce an updated UX/UI prototype for three surfaces:

```text
Stream = attention and decisions
CMO    = steering, explanation, handoff
Admin  = setup and configuration
```

This is not the full Gate 3 redesign. It is the Gate 2 operator experience needed to prove the Gmail-only loop.

---

# Surface 1 — Stream

## Job

Stream is the operator’s attention queue. It should show what needs judgment, what was learned, and what is blocked.

## Gate 2 minimum Stream cards

Gate 2 must visibly support:

```text
1. Objective summary / active objective anchor
2. pending_artifact — Gmail outreach draft or sequence
3. decision_brief — analyst recommendation
4. outcome — manual or Gmail-read result + memory update confirmation
5. setup_blocker — only when Gmail/brand/list/objective setup blocks the loop
```

`signal_update` and `council_brief` may appear as planned/disabled sample states, but they are not live Gate 2 requirements.

## Required card fields

Every card should visibly answer:

```text
objective_ref
why_now
confidence
primary_evidence
recommended_next
approval_boundary
allowed_actions
source_state
```

## Stream actions in Gate 2

Allowed actions:

```text
approve
revise
dismiss
ask CMO
investigate
record outcome
configure
```

Not all actions appear on every card.

## Stream design principle

Do not lead with platform previews. Lead with decision readiness.

A Gmail draft can show a subject-line preview, but the core card should answer:

```text
Why was this drafted?
What evidence supports it?
What should I do next?
What will BOS do after approval?
```

---

# Surface 2 — CMO

## Job

CMO is the steering and explanation surface. It should not behave like a blank chatbot.

In Gate 2, CMO should open with context from:

```text
active objective
selected Stream card
recent MemoryEvents
OutcomeRecords
DecisionBriefs
```

## Gate 2 CMO moments

The prototype should show:

```text
1. Ask CMO about this Stream card
2. Ask why the recommendation was made
3. Revise a Gmail artifact
4. Record rationale / decision memory
5. Record manual outcome
6. Generate handoff brief on demand
```

## Handoff brief behavior

The CMO can generate a current-state handoff brief:

```text
active objectives + state
recent performance narrative
pending decisions
committed actions / deadlines
known risks
what was decided against and why
recommended first action
```

Pass condition:

```text
A new CMO, human or AI, can become operational in under 15 minutes from this brief alone.
```

---

# Surface 3 — Admin

## Job

Admin is configuration, not daily operations.

Admin should support the Gmail-only loop by making setup state obvious and fixable.

## Gate 2 Admin scope

Show only setup/config needed for the loop:

```text
Brand context status
Gmail connection status
Dormant prospect/list source status
Objective setup/status
Memory/handoff audit visibility
Provider/model/system settings only where needed
```

Admin should not become a campaign dashboard in Gate 2.

## Admin design principle

If a user goes to Admin during Gate 2, it should be because Stream told them something is blocked.

Example:

```text
Stream setup_blocker → Configure Gmail / list / brand context in Admin
```

---

# UX deliverables to split

## Deliverable A — Stream Gate 2 screen

Owner: UX/prototype  
Output: `wireframes/bos-gate2-prototype.html` — Stream tab  
Status: **complete**  
Shows: decision_brief (featured), pending_artifact, outcome, setup_blocker — full card contract fields on each

## Deliverable B — CMO contextual screen

Owner: UX/prototype  
Output: `wireframes/bos-gate2-prototype.html` — CMO tab  
Status: **complete**  
Shows: loaded context bar, pre-loaded CMO opening, quick-reply chips, handoff brief collapsible

## Deliverable C — Admin setup screen

Owner: UX/prototype  
Output: setup/config view only  
Status: **pending**  
Must show:

```text
Gmail connected / missing
brand context ready / missing
list source ready / missing
objective status
memory/handoff audit entry point
```

## Deliverable D — Interaction path

Owner: UX/prototype  
Output: `wireframes/bos-gate2-prototype.html` — Flow tab  
Status: **complete**  
Shows: 8-step annotated flow, operator vs system roles, state-change at each step

---

# Final simultaneous UX task split

The UX work can proceed in parallel because each lane owns a separate surface and shares a fixed handoff contract. No lane should invent new Gate 2 product scope.

## Lane 1 — Stream attention surface

Primary owner: Agent A  
Scope: Deliverable A, plus the Stream portions of Deliverable D  
Output: Gate 2 Stream screen/prototype section

Must define:

```text
active objective header
card priority order
pending_artifact card state
decision_brief card state
outcome / memory update card state
setup_blocker card state
card actions and empty/disabled states
```

Interface contract with other lanes:

```text
ask CMO action → opens Lane 2 CMO context
configure action → opens Lane 3 Admin setup target
record outcome action → can be shown either inline or via Lane 2 CMO, but must end in outcome card
```

Do not own:

```text
full CMO chat design
Admin settings IA
Gate 3 Stream redesign
Watchpoints / Council UI
```

## Lane 2 — CMO contextual steering surface

Primary owner: Agent B  
Scope: Deliverable B, plus handoff-brief moment  
Output: contextual CMO screen opened from a Stream card

Must define:

```text
selected card context loaded into CMO
short mobile-first response style
why this recommendation explanation
Gmail artifact revision interaction
manual outcome recording interaction
handoff brief request and result state
```

Interface contract with other lanes:

```text
receives selected Stream card from Lane 1
can return revised artifact / recorded outcome / decision rationale back to Stream
uses Admin only when setup is missing, via Lane 3 configure target
```

Do not own:

```text
Stream card ranking
Admin configuration layout
long-form planning artifacts
Council deliberation UI
```

## Lane 3 — Admin setup/configuration surface

Primary owner: Agent C  
Scope: Deliverable C  
Output: Admin setup/config screen for Gate 2 loop readiness

Must define:

```text
Gmail connection status
brand context readiness
prospect/list source readiness
active objective setup/status
memory/handoff audit entry point
blocked vs ready states
```

Interface contract with other lanes:

```text
receives configure intent from Stream setup_blocker
returns setup readiness state back to Stream
exposes only configuration, not daily operations
```

Do not own:

```text
campaign dashboard
analytics cockpit
multi-connector settings expansion
operator daily decision flow
```

## Lane 4 — End-to-end flow stitch

Primary owner: Coordinator / final pass  
Scope: Deliverable D after Lanes 1–3 produce drafts  
Output: one annotated or clickable Gate 2 loop

Must stitch:

```text
Stream decision
→ CMO explanation
→ Gmail artifact approval/revision
→ send or registered manual send
→ outcome recording
→ memory update confirmation
→ next decision_brief shows improved recommendation
→ Admin only if setup is blocked
```

This lane should not create new UI patterns. It reconciles the three lanes and removes drift.

## Parallel work rules

```text
1. All lanes use the same objective example: generate pipeline/revenue from dormant prospects through Gmail.
2. All lanes keep the same surface roles: Stream decides attention, CMO explains/steers, Admin configures.
3. All lanes must show allowed and forbidden behavior where relevant.
4. No lane introduces another connector, Watchpoints, Council, campaign board, or analytics dashboard.
5. If a UX element does not help prove the Gmail-only objective loop, it is parked.
```

## Merge criteria

The UX split is complete when the combined prototype can answer:

```text
What objective is active?
What needs operator attention right now?
Why is BOS recommending this?
What evidence and memory support it?
What can BOS do only after approval?
How does the operator record an outcome?
Where does the memory update appear?
How is the next recommendation better?
Where does setup happen if blocked?
```

---

# Engineering deliverables after UX sign-off

UX gate: A, B, D complete. C pending (Admin). Engineering tracks 2.1–2.3 unblocked (no UX dependency). Tracks 2.4–2.8 open on Admin UX sign-off.

Selected Gate 2 build order:

```text
1. Minimal Objective anchor
2. MemoryEvent ledger
3. Manual evaluate_outcome v0
4. Minimal outcome Stream card
5. DecisionBrief v0
6. Minimal decision_brief Stream card
7. Handoff brief on demand
8. Gmail loop proof
```

---

# Parked until after Gate 2

These are valid, but not part of the immediate UX build:

```text
Full Stream redesign
Watchpoints automation
CMO Council implementation
Second connector
Cross-brand command center
Campaign status board
Full analytics unification
Multi-connector attribution
Automated digest notifications
Omnichannel fan-out
```

They can appear only as disabled/planned labels if useful for orientation.

---

# Decision rule

For every proposed UX element, ask:

```text
Does this help prove the Gmail-only objective loop?
```

If yes: include it.  
If no: park it.
