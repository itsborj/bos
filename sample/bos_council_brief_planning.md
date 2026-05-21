# BOS Council Brief — Implementation Planning

Status: planning · not yet designed  
Date: 2026-05-20  
Scope: CMO Council — deliberation layer for contested or persistently deferred decisions  
Depends on: DecisionBrief v0 (build item 2.5), MemoryEvent ledger (build item 2.2)

---

## What we know (from agreed docs)

From `sample/bos_stream_sample.md` and `BACKLOG.md`:

### The card contract (agreed)
```text
type: council_brief
topic_tags: budget | creative_fatigue | tracking | attribution | offer | objection | commitment | outcome
triggered_by: persistent dismissal of same topic_tag (2× in N days)
confidence: Contested · low score (e.g. 0.54)
```

Fields on the card:
```text
objective_ref
brand_ref
why_now            — e.g. "budget dismissed 2× in 5 days"
evidence[]         — facts that led to convening
voices[]           — 5 council members with position + confidence + dissent flag
synthesis          — 3-of-5 summary with dissent noted
questions[]        — 4 direct questions for the operator to answer
do_not_list[]      — explicit constraints BOS must not cross without decision
constraint_flags[] — escalation conditions
recommended_next   — "answer the 4 questions, record your decision"
approval_boundary  — "BOS cannot act without operator decision"
allowed_actions    — record decision | ask CMO | dismiss
```

### The 5 fixed voices (agreed in stream sample)
```text
Strategist      — timeline and risk framing
Analyst         — data-backed position
Creative        — execution quality and fatigue risk
Channel Spec    — platform-specific constraints and capacity
Devil's Advocate — challenges the premise of the objective or channel fit
```

---

## Open design questions

Three decisions need operator input before UX/UI can be built.

---

### Question 1 — Triggering model

**What causes the council to convene?**

#### Option A · Automatic only (persistent deferral)
Council fires when the same `topic_tag` appears in a dismissed card N times within a time window (current prototype: 2× in 5 days).

```text
Pros: no operator action required, catches blind spots
Cons: may feel presumptuous — operator may have good reasons to defer
```

#### Option B · Manual convening only
Operator explicitly asks: "convene council on this" from a `decision_brief` or CMO. No automatic fire.

```text
Pros: operator retains full control, council feels like a tool not a judgment
Cons: requires operator to recognise when deliberation is needed
```

#### Option C · Both (recommended starting point)
Automatic trigger on persistent deferral (same topic_tag, N dismissals). Operator can also convene manually from any `decision_brief` card or from CMO ("get a second opinion on this").

Manual convening would produce the same council_brief card type — just without the "dismissed N×" framing in `why_now`.

```text
Open: what is N? 2 dismissals? 3? Over what window — 5 days? 7?
Open: should the operator be able to dismiss a council brief and still have it re-fire?
```

---

### Question 2 — CMO interaction model

**What does the operator actually do with the council brief in CMO?**

#### Option A · One-shot decision recording
Operator reads the brief in Stream or full-window, then goes to CMO and records a single decision covering all 4 questions. CMO writes one `decision_made` MemoryEvent with the full rationale.

```text
Fast. Matches how a senior operator would actually work.
Risk: questions may not all be answered — partial decisions get recorded as complete.
```

#### Option B · Facilitated Q&A (guided mode)
CMO walks the operator through each question one by one. Each answer is acknowledged before the next question is presented. At the end, CMO produces a decision summary for confirmation.

```text
More thorough. Better for high-stakes contested decisions.
Risk: feels slow and patronising for an experienced operator.
Adds UX complexity: CMO needs a "guided mode" state.
```

#### Option C · Hybrid — open input with structured summary
CMO opens with all 4 questions visible. Operator responds in freeform. CMO extracts answers from the response and produces a structured summary: "Here is what I heard — [answer 1], [answer 2]... confirm?" Operator confirms or corrects. MemoryEvent is written from the confirmed summary.

```text
Feels natural. Preserves operator speed. Adds extraction step.
This is the most aligned with how BOS should work — LLM doing the heavy lifting.
Engineering note: requires a structured extraction pass before writing MemoryEvent.
```

**Recommendation: Option C.** Discuss before building.

---

### Question 3 — Council composition

**Are the 5 roles always the same, or topic-adaptive?**

#### Option A · Fixed 5 roles (current prototype)
Always: Strategist, Analyst, Creative, Channel Spec, Devil's Advocate.

```text
Simple. Consistent. The Devil's Advocate role always challenges the premise regardless of topic.
Risk: for a budget question, Creative may have little to add. For a creative fatigue question,
      the Analyst voice may be the most important. Fixed roles may produce noise.
```

#### Option B · Topic-adaptive roles
The `topic_tag` determines which 3–5 voices are most relevant. A budget question pulls Strategist + Analyst + Finance lens. A creative fatigue question pulls Creative + Channel Spec + Analyst.

```text
More realistic. Less noise.
Adds complexity: role-to-topic mapping needs to be defined and maintained.
```

#### Option C · Fixed core + adaptive specialist (recommended)
3 fixed roles always present: Strategist, Analyst, Devil's Advocate.
2 specialist slots filled based on `topic_tag`.

```text
topic_tag: budget          → Finance, Channel Spec
topic_tag: creative_fatigue → Creative, Channel Spec
topic_tag: tracking        → Analyst (2nd lens), Technical
topic_tag: attribution     → Analyst (2nd lens), Channel Spec
topic_tag: offer           → Creative, Strategist (2nd lens)
topic_tag: objection       → Creative, Channel Spec
topic_tag: commitment      → Strategist (2nd lens), Finance
```

**Recommendation: Option C.** Discuss before building.

---

## Engineering implications

These are assumptions about how this builds on top of the Gate 2 schema. Not finalised — depends on design decisions above.

### New model: CouncilBrief
Produced by a council module when triggering condition is met.

```python
class CouncilBrief:
    id: UUID
    workspace_id: UUID
    brand_id: UUID
    objective_id: UUID
    topic_tag: str               # budget | creative_fatigue | ...
    triggered_by: str            # "dismissed 2× in 5 days" | "operator request"
    evidence: list[str]
    voices: list[CouncilVoice]
    synthesis: str
    questions: list[str]         # 4 direct questions for operator
    do_not_list: list[str]
    constraint_flags: list[str]
    confidence: float
    status: str                  # pending | decided | dismissed
    created_at: datetime
    decided_at: datetime | None
    decision_rationale: str | None  # written after operator records decision
```

### New model: CouncilVoice
```python
class CouncilVoice:
    role: str        # Strategist | Analyst | Creative | Channel Spec | Devil's Advocate
    position: str
    confidence: str  # High | Medium | Low
    dissent: bool
```

### MemoryEvent types triggered by council
```text
artifact_created        → when council_brief is generated
decision_made           → when operator records decision after council
decision_not_to_act     → when operator dismisses council brief with rationale
constraint_flag         → when a do_not_list item would be violated by a proposed action
```

### Triggering logic (to implement in DecisionBrief v0 or separate watcher)
```text
On every dismiss of a card with topic_tags:
  - Query recent dismissed cards for same topic_tag + brand_id + objective_id
  - If count >= N within window:
    - Check if a pending council_brief already exists for this topic_tag
    - If not: generate council_brief, create stream card
```

### CMO interaction (Option C hybrid — if agreed)
```text
1. Operator sends message about council card (or taps "record decision")
2. CMO responds with 4 questions visible, invites freeform answer
3. Operator responds in any form
4. CMO runs extraction pass: identify which questions were answered and how
5. CMO produces structured summary: "Here is what I heard — confirm?"
6. Operator confirms or corrects
7. On confirmation: write decision_made MemoryEvent with extracted answers as rationale
8. council_brief.status → decided
9. Stream: council_brief card updates / dismisses
```

---

## UX/UI implications

Not designing yet — depends on Q1–Q3 answers above. Notes for when design begins:

### Stream card
- Current prototype shows voices, synthesis, questions, do_not_list — agreed shape
- Missing: constraint_flags display, `triggered_by` context line, status update after decision recorded

### CMO surface
- Needs a new "council mode" context bar — shows which council_brief is active
- If Option C (hybrid), CMO needs to surface questions as a structured block, not just conversation
- After decision recorded: CMO should show confirmation + what was written to memory

### Admin
- Council history could live in Memory & Audit — not a separate admin section
- No operator-facing council configuration needed for Gate 2 (composition is system-determined)

---

## Decision checklist before building

```text
[ ] Q1: Triggering model — automatic only / manual only / both?
[ ] Q1a: If automatic, what is N (dismissal count) and window (days)?
[ ] Q1b: Can a council_brief itself be dismissed and re-trigger?
[ ] Q2: CMO interaction model — one-shot / guided / hybrid extraction?
[ ] Q3: Council composition — fixed 5 / adaptive / fixed core + adaptive specialist?
[ ] Q3a: If adaptive, confirm role-to-topic_tag mapping
[ ] Confirm: does council_brief need its own database table, or is it a variant of DecisionBrief?
[ ] Confirm: where does council history live in the UI?
```

---

## Related files

- `sample/bos_stream_sample.md` — agreed card contract with council_brief spec
- `BACKLOG.md` — build items 2.4 (DecisionBrief), 2.5 (PendingDecision), 2.2 (MemoryEvent)
- `wireframes/bos-stream-first.html` — council_brief card prototype (card id:6, Motormoto)
- `sample/bos_gate2_ux_ui_coordination.md` — notes watchpoints and council as elevated from parked
