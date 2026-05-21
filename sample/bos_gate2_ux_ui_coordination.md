# BOS Gate 2 UX/UI Coordination — Stream, CMO, Admin

Status: UX prototype active — engineering track open  
Date: 2026-05-20  
Scope: UX/UI alignment for Gate 2 only — Gmail-only objective loop  
Prototype: `wireframes/bos-stream-first.html` ← canonical  
Archived: `wireframes/bos-gate2-prototype.html`, `wireframes/bos-gate2-prototype-agent-a.html` — superseded, do not use  
Council UX sample: `wireframes/bos-council-prototype.html` — post-Gate 2 scope only  

---

## Source references

Use this file as the working coordination brief. The deeper docs are reference only; do not reload them for every discussion unless a decision below is challenged.

- `PROJECT_BRIEF.md` — official project direction, v3.30
- `sample/bos_systems_architecture.md` — full architecture rationale and Gate 2/Gate 3 split
- `sample/bos_stream_sample.md` — approved Stream card semantic contract
- `sample/bos_cmo_objective_runtime_market_model.md` — long-form operating model and Watchpoints thinking
- `memory/project_admin_usecases.md` — admin/persona use-case audit

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

# Prototype state — bos-stream-first.html

All three surfaces are merged into one file. The lane split is complete and retired.

## Stream tab

```text
Card types live in prototype:
  decision_brief      — featured, full body + evidence + watchpoint bar
  pending_artifact    — approve / revise / dismiss / view full
  outcome             — stats, memory tags, sources
  setup_blocker       — configure action deep-links to Admin
  signal_update       — watchpoint progress bar, watching state
  council_brief       — 5-voice panel, synthesis, direct questions, do-not list
  council_session     — settled transcript, marching orders, parked decisions

Active objective anchor shown at top of every Stream view.
Card selection drives right-panel detail in CMO tab.
```

## CMO tab

```text
Split-pane layout: chat (left) + card detail panel (right).
Context bar pre-loads: brand, objective, card type badge.

Quick-reply chips (Gate 2 standard):
  Why this angle? / What happens after approval? / Record an outcome / Generate handoff brief

Outcome recording (C3):
  "Record an outcome" chip opens inline outcome form in CMO chat.
  Fields: what happened (select) + metric/value + notes for memory.
  Submit → outcome confirm block with memory tags visible.

Handoff brief (C4):
  "Generate handoff brief" chip → structured .cmo-hb card.
  Sections: Active state / Recent performance / Pending decisions /
            Committed actions / Known risks / Decided against / Recommended first action.
  Footer: pass-condition note + "Copy brief" button.

council_brief routes to council CMO view:
  Amber notice bar: contested confidence + open question count.
  CMO pre-loads synthesis of all 5 council positions.
  Chips: What are the 4 questions? / Who dissented and why? / What should I not do? / Generate handoff brief.

council_session routes to council CMO view:
  Dark terminal transcript block (settled council record).
  Chips: What were the marching orders? / What's parked? / Was there dissent? / Generate handoff brief.
```

## Admin tab — 7 sections

```text
Gate 2:
  Loop Setup         — Gmail, Brand, Prospect List, Objective status
  Connectors         — Gmail live; 6 available/dormant connectors
  Memory & Audit     — outcome log, handoff brief entry point
  Watchpoints        — metric/threshold config, status list [placeholder — needs design revision]

Council (post-Gate 2 scope):
  Council Seats      — seat roles, model slot, ideology editor

Investigate:
  Loop Flow          — 8-step annotated Gate 2 path
  Parked · Gate 3    — disabled/planned future features
```

## Open design questions in this prototype

```text
All three questions resolved (2026-05-21):

1. [x] Council card color — amber (#b45309) confirmed canonical.
        council-prototype purple (#6b21a8) was design exploration only; retired.
        Engineering: use amber for all council card types.

2. [x] Watchpoints admin — design pass complete (D2/A3).
        Framed as objective-bound attention rules, not analytics dashboards.
        Admin screen explains operator promise, use/anti-use cases, Stream surface rule.
        Treat wireframe as UX direction; do not expand into a dashboard at Gate 2.

3. [x] Council Seats nav placement — moved to Post-Gate 2 group in Admin nav (A2).
        CSS treatment: parked items dimmed (opacity .7, italic, no hover state).
        Tooltip: "Post-Gate 2 — not active in current build".
```

## Merge criteria met

```text
✓ What objective is active?
✓ What needs operator attention right now?
✓ Why is BOS recommending this?
✓ What evidence and memory support it?
✓ What can BOS do only after approval?
✓ How does the operator record an outcome?
✓ Where does the memory update appear?
✓ How is the next recommendation better?
✓ Where does setup happen if blocked?
```

---

# Engineering deliverables after UX sign-off

UX gate: A, B, C, D complete. All engineering tracks unblocked. Prototype frozen at commit ee661c5 on staging branch.

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

## Engineering status — 2026-05-20

Built backend primitives:

```text
GATE 2.1 Objective anchor
- GET /objectives
- GET /objectives/active
- POST /objectives
- GET /objectives/{objective_id}
- PATCH /objectives/{objective_id}

GATE 2.2 MemoryEvent ledger
- GET /memory/events
- POST /memory/events
- passive lifecycle writes from run/artifact approval paths

GATE 2.3 Manual evaluate_outcome v0
- GET /outcomes
- POST /outcomes/evaluate
- creates OutcomeRecord + MemoryEvent(type=outcome_recorded)
- confidence_source defaults to manually_reported

GATE 2.4 Outcome + DecisionBrief Stream surface
- OutcomeRecord stream generator emits type=outcome cards
- DecisionBrief model/router/generator emits type=decision_brief cards
- GET /decision-briefs
- POST /decision-briefs
- POST /decision-briefs/generate
- web Stream renders backend outcome / decision_brief / setup_blocker StreamUpdate cards
```

GATE 2.5 Handoff Brief + PendingDecision
- GET /pending-decisions
- POST /pending-decisions
- POST /pending-decisions/{pending_id}/resolve
- GET /handoff/brief
- PendingDecision writes MemoryEvent decision_not_to_act / decision_made entries
```

Gate 2.6 Gmail loop proof
- `api/scripts/prove_gate2_gmail_loop.py` passed full path on 2026-05-20
- proof objective: `0feb55a6-e430-420f-baa6-4d8bde820015`
- Gmail draft run: `5508783c-5835-49e3-bb08-a370562554ca`
- OutcomeRecord: `b0f17311-2309-4dba-a84b-47ae76a4b124`
- MemoryEvent: `415caee9-46b3-4955-be3a-3054045e5881`
- DecisionBrief: `b6f78179-cf24-457f-936f-683281e2e28c`
- Stream verified visible cards for proof objective: `outcome`, `decision_brief`
```

Still pending:

```text
None for Gate 2 core loop. Gate 3 / next Phase 6 backlog items remain.
```

## Backend shipped — 2026-05-20

All Gate 2 backend primitives complete. Lane assignments retired.

```text
GATE 2.1  Objective anchor          — GET/POST/PATCH /objectives
GATE 2.2  MemoryEvent ledger        — GET/POST /memory/events + passive lifecycle writes
GATE 2.3  evaluate_outcome v0       — POST /outcomes/evaluate → OutcomeRecord + MemoryEvent
GATE 2.4  Stream surface            — outcome + decision_brief cards live in web Stream
GATE 2.5  Handoff Brief + Pending   — GET /handoff/brief, POST /pending-decisions
GATE 2.6  Gmail loop proof          — api/scripts/prove_gate2_gmail_loop.py → PASS
```

Proof run IDs (2026-05-20):

```text
objective:      0feb55a6-e430-420f-baa6-4d8bde820015
gmail draft:    5508783c-5835-49e3-bb08-a370562554ca
OutcomeRecord:  b0f17311-2309-4dba-a84b-47ae76a4b124
MemoryEvent:    415caee9-46b3-4955-be3a-3054045e5881
DecisionBrief:  b6f78179-cf24-457f-936f-683281e2e28c
```

## Open frontend tracks

```text
Admin loop readiness UI:
  [x] AdminObjectiveLoop.tsx — /admin/objective-loop
      Active objective + readiness (Gmail/brand kit/objective status), decision briefs,
      pending decisions, outcome records, memory ledger. Generate Decision Brief button.
      Gate 2 API client methods all wired.

CMO outcome recording:
  [~] agent-a  web/src/pages/CmoChat.tsx — manual outcome affordance → POST /outcomes/evaluate
      wireframe design complete (C3 [x]); engineering implementation pending
      must not paste platform-native artifacts inline
```

---

# UX/UI Marching Orders — Live App vs Wireframe Gap

Audit date: 2026-05-21  
Reference: `wireframes/bos-stream-first.html` (canonical)  
Scope: gaps between current `web/src/` React app and the approved wireframe design  
Rule: no engineering starts on any item below until design questions in each item are resolved

## Local app status — what shows in local vs wireframe-only

Items marked NOT LIVE will not appear when running the local React app today.
Items marked LIVE are already implemented and visible.
Items marked PARKED should not be built at Gate 2.

| ID  | Surface | What it is                              | Wireframe  | Local app       |
|-----|---------|-----------------------------------------|------------|-----------------|
| S1  | Stream  | Active objective anchor                 | designed   | **NOT LIVE**    |
| S2  | Stream  | Decision-first artifact card layout     | designed   | **NOT LIVE**    |
| S3  | Stream  | Full allowed_actions (revise/investigate/configure) | designed | **NOT LIVE** |
| S4  | Stream  | Card context handoff to CMO             | designed   | **NOT LIVE**    |
| S5  | Stream  | pending_artifact card type in feed      | designed   | **NOT LIVE**    |
| S6  | Stream  | Gate 2 empty state copy                 | designed   | **NOT LIVE**    |
| C1  | CMO     | Split-pane layout (card detail panel)   | designed   | **NOT LIVE**    |
| C2  | CMO     | Gate 2 quick-reply chips                | designed   | **NOT LIVE**    |
| C3  | CMO     | Outcome recording inline form           | designed   | **NOT LIVE**    |
| C4  | CMO     | Handoff brief structured card           | designed   | **NOT LIVE**    |
| C5  | CMO     | Context bar: objective-first framing    | designed   | **NOT LIVE**    |
| C6  | CMO     | Stream card context receive (event)     | designed   | **NOT LIVE**    |
| A1  | Admin   | AdminObjectiveLoop page                 | designed   | **LIVE** ✓      |
| A2  | Admin   | Post-Gate-2 parked nav treatment        | designed   | **NOT LIVE**    |
| A3  | Admin   | Watchpoints config UI                   | designed   | **PARKED**      |

---

## Stream gaps

### S1 · Active objective anchor — MISSING (build first)

Live `Stream.tsx` has a date label + item-count header. No objective data is loaded or shown.

Wireframe: objective anchor block at the top of every Stream view.

Required fields: objective title, status, and a link to `/admin/objective-loop`.  
Backend ready: `GET /objectives/active`.

---

### S2 · Artifact cards lead with platform preview instead of decision readiness

`StreamArtifactCard` renders `renderNativePreview()` as the dominant element.  
Wireframe principle: **"Do not lead with platform previews. Lead with decision readiness."**

Each artifact card must answer first:
```
Why was this drafted?
What evidence supports it?
What should I do next?       ← recommended_next
What will BOS do after approval?  ← approval_boundary
```

Platform preview (Gmail preview etc.) appears below these fields, secondary or collapsible.

UX wireframe decision — 2026-05-20:
```text
S2 wireframe pass complete in wireframes/bos-stream-first.html.
Pending artifact evidence now describes decision support/memory first.
Gmail subject-line preview is separated into a secondary collapsible block.
Full artifact detail may open the preview expanded, but Stream card keeps it secondary.
No production files touched.
```

---

### S3 · StreamDataCard — full allowed_actions set designed in wireframe ✓

Current actions rendered: Ask CMO, Record outcome, Dismiss.  
Wireframe allowed actions: approve, revise, dismiss, ask CMO, investigate, record outcome, configure.

Missing:
- `revise` — opens revision flow
- `investigate` — opens deeper analysis path
- `configure` — for `setup_blocker` type only, deep-links to Admin

UX wireframe decision — 2026-05-20:
```text
S3 wireframe pass complete in wireframes/bos-stream-first.html.
Stream card samples now represent the full allowed-action vocabulary:
approve, revise, dismiss, ask CMO, investigate, record outcome, configure.
Action behavior in the prototype:
- approve/dismiss clears card from Stream
- revise / ask CMO / record decision hand off card context to CMO
- record outcome opens CMO with the outcome form already visible
- investigate opens the full detail overlay
- configure routes to Admin
No production files touched.
```

---

### S4 · "Ask CMO" on StreamDataCard drops card context — designed in wireframe ✓

`window.location.assign('/cmo')` navigates to CMO with no context passed.  
CMO opens blank — no selected card, no pre-loaded why_now or evidence.

Required: emit a `bos:stream-card-context` custom event carrying the card data before navigating. CmoChat must listen and pre-load it.

UX wireframe decision — 2026-05-20:
```text
S4 wireframe pass complete in wireframes/bos-stream-first.html.
Stream actions now route through an explicit openCMOFromCard(card, actionLabel) handoff.
CMO renders a visible context-handoff confirmation above the first answer.
The confirmation states that why_now, evidence, recommended_next, approval boundary,
actions, and source state are loaded from the selected Stream card.
No production files touched.
```

---

### S5 · pending_artifact card type not rendered in Stream feed — validated in wireframe ✓

`Stream.tsx` line 281 filters to `['outcome', 'decision_brief', 'setup_blocker']` only.  
A `pending_artifact` (Gmail draft awaiting approval) is a Gate 2 card type — never surfaces here.

Required: add `pending_artifact` to the allowed types filter.

UX wireframe validation — 2026-05-20:
```text
S5 canonical wireframe state confirmed in wireframes/bos-stream-first.html.
Stream feed includes a visible pending_artifact card for the Gmail sequence awaiting approval.
The card has decision-readiness fields, secondary Gmail subject preview, approval boundary,
and approve/revise/dismiss/view full actions.
Engineering pickup remains: add pending_artifact to the live Stream feed type filter.
No production files touched.
```

---

### S6 · Empty state copy is pre-Gate-2 messaging — designed in wireframe ✓

Current: "Chat artifacts will appear here as timestamped native previews..."  
This describes the old artifact-factory model.

Gate 2 empty state should orient the operator to the objective loop — or surface a `setup_blocker` if setup is incomplete.

UX wireframe decision — 2026-05-20:
```text
S6 wireframe pass complete in wireframes/bos-stream-first.html.
Empty Stream state now says the objective loop is quiet, not that chat artifacts are missing.
It tells the operator BOS is watching objective, Gmail replies, pending outcomes, and setup readiness.
It explicitly says setup blockers will appear here if Gmail/list/brand/objective setup breaks the loop.
No production files touched.
```

---

## CMO gaps

### C1 · No split-pane layout when card selected from Stream — designed in wireframe ✓

Live `CmoChat.tsx` is single-column chat only.  
Wireframe: chat (left) + card detail panel (right) when a Stream card context is active.

Right panel shows selected card's full body: objective_ref, why_now, confidence, primary_evidence, recommended_next, approval_boundary, allowed_actions, source_state.

Depends on S4 (card context handoff mechanism) being agreed first.

UX wireframe decision — 2026-05-20:
```text
C1 wireframe pass complete in wireframes/bos-stream-first.html.
CMO remains split-pane when opened from a Stream card.
Right panel shows selected card details and now explicitly includes Allowed actions and Source state.
Mobile/narrow behavior remains stacked: chat first, card detail below.
No production files touched.
```

---

### C2 · Quick-reply chips do not match Gate 2 operator moments — designed in wireframe ✓

Current chips: New Chat · What can you do? · Plan a campaign  
Wireframe Gate 2 chips: Why this angle? · What happens after approval? · Record an outcome · Generate handoff brief

"Why this angle?" and "What happens after approval?" are context-sensitive — appear only when a Stream card is loaded in the right panel.  
"Record an outcome" and "Generate handoff brief" are always available.

UX wireframe decision — 2026-05-20:
```text
C2 wireframe pass complete in wireframes/bos-stream-first.html.
CMO chips are grouped into Context actions and Always available actions.
Context actions: Why this angle? / What happens after I approve?
Always available: Record an outcome / Generate handoff brief
No production files touched.
```

---

### C3 · Outcome recording affordance — designed in wireframe ✓

Designed in `wireframes/bos-stream-first.html` (2026-05-21).

"Record an outcome" chip now renders an inline form in the CMO chat:
- Objective anchor row (which objective this outcome is for)
- Outcome type selector: reply_received / meeting_booked / deal_opened / no_response / unsubscribed / other
- Metric / value text field
- Notes for memory (optional textarea)
- "Record & update memory" submit button

On submit: form is replaced inline with a memory confirmation block showing outcome type tag, objective ref tag, value, and source angle tags. CMO message: "Next recommendation will incorporate this result."

Engineering pickup: wire submit button to `POST /outcomes/evaluate`. Must not paste platform-native artifacts inline.

---

### C4 · Handoff brief — designed in wireframe ✓

Designed in `wireframes/bos-stream-first.html` (2026-05-21, upgraded from prior monospace draft).

"Generate handoff brief" chip renders a structured in-chat document with:
- Green header: brief title, objective name, brand, horizon, live timestamp
- Sections: Active state / Recent performance / Pending decisions / Committed actions / Known risks / Decided against
- Recommended first action — highlighted green (`.cmo-hb-action`) so it reads first on scan
- Footer: pass-condition note + "Copy brief" button (copies plain text to clipboard)

Pass condition visible in the footer: "A new CMO should be operational from this brief alone."

Engineering pickup: wire "Generate handoff brief" chip to `GET /handoff/brief` and render the structured response using the same `.cmo-hb` layout. Must not paste platform-native artifacts inline.

---

### C5 · Context bar shows campaign, not objective — designed in wireframe ✓

`contextParts` in CmoChat: Brand / Campaign / pending items count.  
Gate 2 is objective-first, not campaign-first.

Context bar should show: Brand / Active Objective / (selected card type when active).

UX wireframe decision — 2026-05-20:
```text
C5 wireframe pass complete in wireframes/bos-stream-first.html.
CMO context bar now renders from selectedCard:
- Brand · {brand}
- Active Objective · {objective}
- Selected Card · {card type label}
This keeps CMO anchored to objective + Stream card rather than campaign-first chat context.
No production files touched.
```

---

### C6 · No stream card context injection from Stream navigation — designed in wireframe ✓

Covered by S4. Listed here as the CMO receive side.  
CmoChat must: (a) listen for `bos:stream-card-context`, (b) load card data into the right panel, (c) inject a context note into the status bar, (d) optionally pre-fill the input with a suggested question matching the card type.

UX wireframe decision — 2026-05-20:
```text
C6 receive-side wireframe pass complete.
CMO context bar and handoff note are driven by selectedCard.
Right panel remains the selected card detail view.
Engineering pickup should replace wireframe state with the agreed custom event/local state handoff.
No production files touched.
```

---

## Admin gaps

### A1 · AdminObjectiveLoop — complete ✓

`/admin/objective-loop` — live. Loop readiness, active objective detail, decision briefs, pending decisions, outcome records, memory ledger, Generate Decision Brief.

### A2 · Council Seats nav placement — designed in wireframe ✓

In the wireframe, Council Seats appears under the Gate 2 nav group.  
It must move to a clearly post-Gate-2 / parked section before any admin nav is finalized.  
No engineering until placement is decided.

UX wireframe decision — 2026-05-21:
```text
A2 wireframe pass complete in wireframes/bos-stream-first.html.
Council Seats in "Post-Gate 2 · parked" nav group — visually muted: italic text,
opacity .7, non-interactive cursor, tooltip on hover.
Group label is also dimmed (opacity .55) to signal the entire section is parked.
Engineering: apply .admin-nav-item.parked style + dimmed group label to Post-Gate 2 nav group.
```

### A3 · Watchpoints — design pass complete in wireframe ✓

Current state: placeholder form in wireframe (metric/threshold config + state badges).  
Do not build until a design pass is completed.  
Do not carry current placeholder forward as a build spec.

UX wireframe decision — 2026-05-20:
```text
A3 wireframe design pass complete in wireframes/bos-stream-first.html.
Watchpoints are framed as objective-bound attention rules, not an analytics dashboard.
Admin now states the operator promise: watch silently while safe, interrupt Stream only when judgment may be needed.
Added Use watchpoints for / Do not use for guidance.
Form copy now requires signal + safe range + Stream surface rule + objective attachment.
No production files touched.
```

---

## Open design decisions — must resolve before engineering

### D1 · Council card color — DECIDED: amber ✓

- `bos-stream-first.html` (canonical): amber `#b45309` / dark bg — **confirmed**
- `bos-council-prototype.html`: purple `#6b21a8` — superseded for production

Decision (2026-05-21): amber is canonical. `bos-council-prototype.html` was a design exploration only. Engineering uses amber (`#b45309`, dark bg `#1c0f00`) for all council card CSS. No purple in production.

### D2 · Watchpoints admin UX — RESOLVED in wireframe ✓

Decision (2026-05-20): Watchpoints are objective-bound attention rules, not a dashboard. Admin config explains when BOS may interrupt Stream and requires every Watchpoint to attach to an objective and a Stream surface rule. Engineering should not build a general analytics cockpit from this UI.

### D3 · Council CMO interaction model — designed in wireframe ✓

Designed in `wireframes/bos-stream-first.html` (2026-05-21).

**council_brief → `renderCouncilBriefCMO()`**
- Context bar: brand / objective / council_brief badge (purple tone to match card type)
- Amber notice: contested confidence count + questions count needing operator decision
- CMO pre-loads the council synthesis
- Chips: "What are the 4 questions?" / "Who dissented and why?" / "What should I not do?" / "Generate handoff brief"
- Input placeholder: "Ask about the council brief, or record your decision..."

**council_session → `renderCouncilCMO()` (chips added)**
- Chips appear below the settled transcript: "What were the marching orders?" / "What's parked?" / "Was there dissent?" / "Generate handoff brief"
- All chips wired with contextual replies drawn from session data (orders, parked, voice dissent)

---

## Build sequence — UX/UI implementation order

```text
1.  S1   [x] agent-a  Objective anchor on Stream        (backend ready)
2.  C3   [x] agent-a  CMO outcome recording affordance  (backend ready)
3.  S2   [x] agent-a  Artifact card: decision readiness leads, preview secondary — UX wireframe pass complete
4.  S4/C6[x] agent-a  Stream→CMO card context handoff  (enables C1 + C2) — UX wireframe pass complete
5.  C1   [x] agent-a  CMO split-pane layout             (depends on S4) — UX wireframe pass complete
6.  C2   [x] agent-a  Gate 2 CMO quick-reply chips      (depends on C1 for context-sensitive chips) — UX wireframe pass complete
7.  C4   [x] agent-a  Handoff brief chip                (backend ready) — UX wireframe pass complete
8.  C5   [x] agent-a  Context bar: objective-first framing — UX wireframe pass complete
9.  S3   [x] agent-b  Full allowed_actions set on StreamDataCard — UX wireframe pass complete
10. S5   [x] agent-a  pending_artifact card type in Stream feed — UX wireframe validated; engineering pickup remains
11. S6   [x] agent-a  Empty state copy — UX wireframe pass complete
12. A2   [x] agent-a  Council Seats nav placement       (design decision first) — UX wireframe pass complete
13. D1   [x] agent-a  Council card color decision        — amber confirmed, purple retired
14. D3   [x] agent-a  Council CMO interaction model      — council_brief + council_session CMO views designed
```

**Wireframe design complete.** All listed UX/UI marching-order items are now [x].  
Engineering pickup is unblocked for the coordinated items, subject to Gate 2/Gate 3 scope discipline.

---

# Elevated from Parked — needs design revision

These items were moved up in priority but the current UX implementation is a placeholder only. Do not treat as final.

## Watchpoints (Admin config UI)
Status: design pass complete in `wireframes/bos-stream-first.html` Admin → Watchpoints  
Resolution: Watchpoints are framed as objective-bound attention rules, not analytics dashboards. The Admin screen now explains the operator promise, appropriate use cases, anti-use cases, and Stream surface rule.  
Action: engineering may use this wireframe as UX direction only after Gate 2 priorities allow; do not expand into a dashboard.

## CMO Council brief
Status: CMO interaction model designed in `wireframes/bos-stream-first.html` for both `council_brief` and `council_session`.  
Action: keep parked until after Gate 2 engineering priorities; use the designed CMO moments when council work resumes.

---

# Parked until after Gate 2

These are valid, but not part of the immediate UX build:

```text
Full Stream redesign
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
