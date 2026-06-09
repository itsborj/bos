# BOS — Prototype to Local: Implementation Coordination

Status: Engineering implementation track open  
Date: 2026-05-21  
Design reference: `wireframes/bos-stream-first.html` (frozen — do not modify)  
Target: `web/src/` React app  
Backend: all Gate 2 primitives live (2.1–2.6)

---

## What this file is

The HTML prototype is the agreed design spec. This file translates it into an ordered engineering implementation queue for the local React app.

For each item: what file to touch, what API is needed, what the wireframe shows, and any dependencies.

Do not start any item marked PARKED. Do not modify `wireframes/bos-stream-first.html`.

---

## Already live — do not rebuild

| Item | File | Notes |
|------|------|-------|
| A1 · AdminObjectiveLoop | `web/src/pages/AdminObjectiveLoop.tsx` | Objective detail, decision briefs, pending decisions, outcome records, memory ledger. Complete. |
| Gate 2 backend 2.1–2.6 | `api/` | All endpoints live. See `bos_gate2_ux_ui_coordination.md` §Engineering status. |

---

## Implementation queue — dependency order

Build in this order. Items earlier in the list unblock items below them.

```
1.  S1    [x] agent-a  Objective anchor on Stream             — ObjectiveAnchor component, GET /objectives/active
2.  S5    [x] agent-b  Add pending_artifact to type filter    — one-line fix
3.  S6    [x] agent-a  Gate 2 empty state copy               — no deps, copy change
4.  S4/C6 [x] agent-a  Card context handoff event            — navigateToCMO() + bos:stream-card-context + CMO listener
5.  S2    [x] agent-a  Decision-first artifact card layout   — decision fields lead, preview collapsible
6.  S3    [x] agent-a  Full allowed_actions on StreamDataCard — no deps (S4 now wires revise/ask-cmo)
7.  A2    [x] agent-a  Parked nav treatment in Admin          — no deps, CSS only
8.  C5    [x] agent-a  CMO context bar: objective-first       — objective + card context badge live
9.  C1    [x] agent-a  CMO split-pane layout                  — CardDetailPanel + .bos-cmo-split grid
10. C2    [x] agent-a  Gate 2 quick-reply chips               — context-sensitive + always-available set live
11. C3    [x] agent-a  Outcome recording inline form          — inline form → POST /outcomes/evaluate → confirm block
12. C4    [x] agent-a  Handoff brief structured card          — GET /handoff/brief → structured in-chat card + copy
13. QA1   [x] agent-a  Fix local TypeScript compile blockers — CmoChat in-progress C1 cleanup
14. QA2   [x] agent-a  CMO default visual parity on /cmo — direct route now uses Gate 2 split shell + context panel
15. QA3   [-] agent-a  Reverted static prototype iframe route — wrong approach because it removed live localhost functionality
16. L1    [x] agent-a  Functional shell visual parity — React/API live with prototype topbar + bottom tabs; static iframe removed
17. L2    [x] agent-a  Stream visual parity pass — prototype header/objective/card density while keeping live data
18. L3    [x] agent-a  Remove non-prototype topbar controls — topbar now matches prototype logo/brand/date
```

---

## Per-item specs

---

### S1 · Objective anchor on Stream

**File:** `web/src/pages/Stream.tsx`  
**API:** `GET /objectives/active`  
**Wireframe reference:** top of Stream view, above card feed  

What to build:
- Fetch active objective on mount (alongside existing `getRuns` + `getStream` calls)
- Render a compact anchor block above the stream feed showing:
  - Objective title
  - Status badge (active / paused / complete)
  - Link to `/admin/objective-loop`
- If no active objective: show a `setup_blocker`-style prompt pointing to `/admin/objective-loop`

CSS class: `.obj-anchor` — already defined in wireframe; port to `index.css`

---

### S5 · Add pending_artifact to Stream type filter

**File:** `web/src/pages/Stream.tsx` line 281  
**API:** none — type filter only  

One-line change:
```ts
// before
.filter(update => ['outcome', 'decision_brief', 'setup_blocker'].includes(update.type))

// after
.filter(update => ['outcome', 'decision_brief', 'setup_blocker', 'pending_artifact'].includes(update.type))
```

`pending_artifact` cards carry the Gmail draft awaiting operator approval. Without this they never surface in Stream.

---

### S6 · Gate 2 empty state copy

**File:** `web/src/pages/Stream.tsx`  
**API:** none  

Replace current empty state text:

```
Current: "Chat artifacts will appear here as timestamped native previews,
          even if chat history is cleared."

Replace with:
"BOS is watching — objective loop is quiet.
 Monitoring: active objective · Gmail replies · pending outcomes · setup readiness.
 Setup blockers will appear here if Gmail, prospect list, brand kit, or objective
 setup breaks the loop."
```

Link text: "Set up the objective loop →" pointing to `/admin/objective-loop`

---

### S4 / C6 · Card context handoff (Stream → CMO)

**Files:** `web/src/pages/Stream.tsx`, `web/src/pages/CmoChat.tsx`  
**API:** none — custom event  

Stream side (S4):
- Replace `window.location.assign('/cmo')` with a function that:
  1. Emits `bos:stream-card-context` custom event with full card data
  2. Then navigates to `/cmo`
- Apply to: Ask CMO, Record outcome, Revise actions on all card types

CMO side (C6):
- On mount, listen for `bos:stream-card-context`
- Store card data in local state: `selectedCard`
- `selectedCard` drives: context bar badge, right panel (C1), chip visibility (C2)

Event payload shape:
```ts
{
  id: string,
  type: string,           // 'decision_brief' | 'pending_artifact' | 'outcome' | 'setup_blocker'
  actionLabel: string,    // 'ask CMO' | 'record outcome' | 'revise'
  data_json: object,      // card body: why_now, evidence, recommended_next, approval_boundary, etc.
  priority?: string,
  source_key?: string,
}
```

---

### S2 · Decision-first artifact card layout

**File:** `web/src/pages/Stream.tsx` → `StreamArtifactCard`  
**API:** none — layout change  

Current: `renderNativePreview()` is the dominant element.  
Required: decision readiness fields lead, platform preview is secondary.

Card structure (top to bottom):
1. Chrome row: title + status badge (keep as-is)
2. Why drafted: `run.result?.recommended_next` or `run.result?.why_now`
3. Evidence: `run.result?.primary_evidence` (if present)
4. Approval boundary: `run.result?.approval_boundary` (what BOS will do after approval)
5. Platform preview: `renderNativePreview()` — secondary, collapsible or visually de-emphasised

No platform preview should appear above the decision context.

---

### S3 · Full allowed_actions on StreamDataCard

**File:** `web/src/pages/Stream.tsx` → `StreamDataCard`  
**API:** none for revise/investigate/configure routing  

Current actions: Ask CMO, Record outcome, Dismiss  
Required full set: approve, revise, dismiss, ask CMO, investigate, record outcome, configure

Add:
- `revise` — call `openCMOFromCard(card, 'revise')` (depends on S4)
- `investigate` — opens detail overlay or navigates to card detail route
- `configure` — only on `setup_blocker` type; routes to `/admin/modules` for specialist connector setup or `/admin/objective-loop` based on `data_json.config_target`

Render only actions present in `update.data_json.allowed_actions`. Do not show all actions on every card.

---

### A2 · Post-Gate-2 parked nav treatment

**File:** `web/src/pages/Admin.tsx` (or nav component)  
**API:** none — CSS + conditional rendering  

In Admin nav, group items tagged as post-Gate-2 under a "Post-Gate 2" section heading.  
Apply parked styling to the group and its items:
- Group label: `opacity: 0.55`
- Nav items: `opacity: 0.7`, italic, `cursor: default`, no hover state
- Tooltip on hover: "Post-Gate 2 — not active in current build"

Items to park: Council Seats, and any other nav entries not part of the Gate 2 core loop.

CSS classes already defined in wireframe (`.admin-nav-item.parked`); port to `index.css`.

---

### C5 · CMO context bar: objective-first framing

**File:** `web/src/pages/CmoChat.tsx`  
**Depends on:** S4/C6 (selectedCard state)  

Current context bar shows: Brand / Campaign / pending items count  
Required: Brand / Active Objective / (selected card type badge when active)

Change `contextParts` to:
```ts
const contextParts = [
  activeBrand?.name ?? 'No brand',
  activeObjective?.title ?? 'No objective',
  selectedCard ? cardTypeLabel(selectedCard.type) : null,
].filter(Boolean);
```

`activeObjective` comes from `GET /objectives/active` (already needed for S1).  
`selectedCard` comes from C6 event listener.

---

### C1 · CMO split-pane layout

**File:** `web/src/pages/CmoChat.tsx`  
**Depends on:** S4/C6 (selectedCard state)  

When `selectedCard` is set, switch CMO to split-pane:
- Left: chat (existing)
- Right: card detail panel — shows `selectedCard` full body:
  - `why_now`, `confidence`, `primary_evidence`
  - `recommended_next`, `approval_boundary`
  - `allowed_actions`, `source_state`

When no card is selected: single-column chat (current behaviour).

Mobile / narrow: stacked — chat first, card detail below.

---

### C2 · Gate 2 quick-reply chips

**File:** `web/src/pages/CmoChat.tsx`  
**Depends on:** C1 (split-pane, so context is clear)  

Replace current chips with Gate 2 set:

Context-sensitive (show only when `selectedCard` is set):
- "Why this angle?"
- "What happens after approval?"

Always available:
- "Record an outcome"
- "Generate handoff brief"

"Record an outcome" triggers C3 (outcome form).  
"Generate handoff brief" triggers C4 (handoff brief card).

---

### C3 · Outcome recording inline form

**File:** `web/src/pages/CmoChat.tsx`  
**API:** `POST /outcomes/evaluate`  
**Depends on:** C2 ("Record an outcome" chip)  

"Record an outcome" chip appends an inline form to the chat:
- Objective anchor row (title of active objective)
- Outcome type: `reply_received` / `meeting_booked` / `deal_opened` / `no_response` / `unsubscribed` / `other`
- Metric / value: free text
- Notes for memory: optional textarea
- "Record & update memory" button → `POST /outcomes/evaluate`
- Cancel button → removes form

On submit success: replace form with a memory confirmation block showing:
- Outcome type tag
- Objective ref tag
- Value entered
- "Next recommendation will incorporate this result."

Must not paste platform-native artifacts inline in this flow.

API payload:
```ts
{
  objective_id: activeObjective.id,
  outcome_type: selectedType,
  value: metricValue,
  notes: notes,
  confidence_source: 'manually_reported',
}
```

---

### C4 · Handoff brief structured card

**File:** `web/src/pages/CmoChat.tsx`  
**API:** `GET /handoff/brief`  
**Depends on:** C2 ("Generate handoff brief" chip)  

"Generate handoff brief" chip calls `GET /handoff/brief` and renders the response as a structured in-chat card:

Card sections (in order):
1. Header (green): brief title · objective name · brand · horizon · timestamp
2. Active state
3. Recent performance
4. Pending decisions
5. Committed actions
6. Known risks
7. Decided against
8. Recommended first action — highlighted (`.cmo-hb-action`)
9. Footer: pass-condition note · "Copy brief" button

"Copy brief" copies plain text to clipboard.  
Pass condition: "A new CMO should be operational from this brief alone."

Must not paste platform-native artifacts inline.

---

## Parked — do not build at Gate 2

| Item | Reason |
|------|--------|
| A3 · Watchpoints config UI | Design pass done in wireframe; engineering deferred until Gate 2 core loop proves out |
| D3 · Council CMO views | CMO council_brief + council_session views designed in wireframe; parked until post-Gate 2 |
| Council Seats admin | Post-Gate 2 scope; nav entry parked with dimmed treatment (A2) |

---

## Gate 2 pass condition (reminder)

```text
Memory makes the next recommendation better than the first one.
```

Every item in this file serves that loop. If a feature doesn't help prove it, defer it.
