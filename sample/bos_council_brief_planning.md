# BOS Council — Mini Project Brief

Status: active · in design  
Date updated: 2026-06-02  
Scope: CMO Council — live boardroom deliberation layer for marketing decisions  
Supersedes: original planning doc dated 2026-05-20 (fixed-role, static synthesis model)

---

## What the Council Is

A live boardroom of senior Chief Marketing Officers deliberating together on a marketing question. Every active seat is a full-stack CMO backed by a different LLM. The only guaranteed difference between seats is the AI model — that alone produces genuine divergence in strategic reasoning.

The council is not a polling system and not a synthesis pipeline. It is a sequential, visible debate that ends when the business leader and the council reach a final decision together.

**The business leader is Council #6.** Not an observer — a full participant who can inject at any point, steer the direction, or call the question.

---

## Seat Model

### Default — CMO with no bias

Every seat is a Chief Marketing Officer caliber participant. No role assignment, no fixed ideology. The LLM backing the seat is the source of differentiation. A Gemini-backed CMO and a Llama-backed CMO will genuinely reason differently on the same marketing problem. That divergence is the council's value.

### Optional — named identity and bias

The operator can optionally give a seat a name and an ideology statement in Admin → Council Seats. Examples:

```
display_name: "Sarah"
ideology: "Growth-first. Revenue and market movement above all else. Dismissive of brand-first arguments unless backed by conversion data."
```

If these fields are left empty, the seat runs as a pure unbiased CMO. Ideology is additive, not required.

### Variable seat count

The council runs with however many seats are set to active — could be 2, could be all 5. Vacant seats are skipped entirely. No minimum quorum enforced at the system level (that is the operator's configuration responsibility).

### Council #6 — Business Leader

The operator is always Council #6. They are not a moderator or a passive reader. They are a participant in the boardroom. Their voice is treated the same as any CMO seat when the next round is assembled — it becomes part of the transcript that all active seats consume.

---

## Deliberation Structure

### Round 1 — Independent positions

All active seats fire in parallel. Each seat receives only:
- The original question
- Active brand context (brand brief, campaign history, approved learnings)

No seat sees any other seat's response yet. This prevents Round 1 from being contaminated by whoever spoke first.

Positions stream into the Stream card as they complete — the operator watches them land one by one.

Round 1 closes with a **simple hardcoded prompt to C6**. Not AI-generated. Not leading. One of a small rotating set:

```
"What do you think?"
"Any comments before we continue?"
"Anything to add or redirect?"
"Do you want the council to continue?"
```

The purpose of this prompt is to give C6 a natural moment to inject — not to force a response. C6 can respond or pass.

### C6 injection (optional at any round boundary)

If C6 responds to the round-end prompt, their input is appended to the transcript as a C6 entry. No special handling. The next round's context simply includes what C6 said alongside all CMO positions. The council reads it as they would read any peer's contribution and factors it into their next round.

If C6 passes, the next round starts immediately with no C6 entry.

There is no concept of "redirecting" the council in code. C6's words do the redirecting. The LLMs read it and respond accordingly.

### Round 2+ — Cross-examination

Each active seat now receives the full transcript of all prior rounds. They:
- Align with positions they agree with (naming the seat)
- Push back on positions they disagree with (naming the seat, stating the reason)
- Adjust their own prior position if peer arguments changed their view (stating why)

Responses are sequential within the round — each seat sees all seats that spoke before it in the same round. This produces genuine dialogue: C3 can respond to what C2 just said in the same round, not just what C2 said in Round 1.

Round N closes with the same simple hardcoded C6 prompt.

### Finalization

The session ends when:
- **C6 calls it** — types any variant of "let's close," "I'm aligned," "that's enough," "wrap it up," or hits a Finalize button in the UI
- **Natural convergence** — all active seats signal alignment in a round and C6 confirms at the round-end prompt

There is no enforced maximum round count at the system level. A configurable safety ceiling exists in the session config (default: 10 rounds) to prevent runaway sessions, but it is not a design constraint — the council runs until the decision is reached.

### Final output — council brief artifact

When the session closes, the transcript is used to produce a `council_brief` artifact in Stream. This is the board minutes, not the meeting itself.

```
Settlement           — what the council agreed (or where it remains split)
Marching orders      — numbered, concrete, actionable
Parked decisions     — open items explicitly deferred
C6 injections        — what the business leader contributed, clearly attributed
Expandable transcript — full round-by-round exchange, collapsed by default
```

---

## Stream Representation

The council session has a dedicated Stream card that evolves live throughout the session.

### Active session card

```
┌─────────────────────────────────────────────────────────┐
│ ⬡ COUNCIL IN SESSION                       Round 1 of ? │
│ "Should we reposition Klaroha for the next launch?"     │
├─────────────────────────────────────────────────────────┤
│  C1  [streaming response...]                            │
│  C2  ✓ done                                             │
│  C3  [waiting]                                          │
│  C4  [waiting]                                          │
├─────────────────────────────────────────────────────────┤
│  C6  What do you think?                                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [Your response or pass...]             [Pass]   │   │
│  └─────────────────────────────────────────────────┘   │
│                                    [Finalize session]   │
└─────────────────────────────────────────────────────────┘
```

### Round expansion

As rounds complete, each round collapses into an expandable section. The operator can expand any prior round to read the full exchange. The active round is always shown open.

```
▶ Round 1  (4 positions)
▶ C6 injection — Round 1 boundary
▼ Round 2  (active)
  C1: I want to push back on what C3 said about cold traffic...
  C2: [streaming...]
```

### Finalized session card

When the session closes, the card transitions to the council brief artifact view:

```
┌─────────────────────────────────────────────────────────┐
│ ⬡ COUNCIL BRIEF                              ✓ Settled  │
│ "Should we reposition Klaroha for the next launch?"     │
├─────────────────────────────────────────────────────────┤
│ Settlement                                              │
│ Adopt "CMO operating system" as the lead frame.         │
│ Retain "command center" as supporting product language. │
├─────────────────────────────────────────────────────────┤
│ Marching orders                                         │
│ 1. Lead launch messaging with: "Your CMO operating..."  │
│ 2. Update campaign briefs toward executive leverage.    │
│ 3. Run a two-message test before replacing assets.      │
├─────────────────────────────────────────────────────────┤
│ Parked decisions                                        │
│ · Whether to mention "AI" in the homepage hero          │
│ · Agency buyer role: CMO vs. marketing operator         │
├─────────────────────────────────────────────────────────┤
│ ▶ Full transcript (3 rounds · 4 seats · 2 C6 inputs)   │
├─────────────────────────────────────────────────────────┤
│ [Approve settlement]  [Ask follow-up]  [Dismiss]        │
└─────────────────────────────────────────────────────────┘
```

---

## What Does Not Change From the Prior Model

- `@council <question>` is still the invocation command in CMO chat
- CMO chat returns a short acknowledgement only — never dumps the transcript into chat
- The `council_brief` artifact is the canonical output — Stream/Workspace own it
- Approved settlement writes a MemoryEvent so future CMO planning uses the decision
- Council may not execute, publish, spend, or create campaign artifacts without separate operator approval
- Dissent is preserved in the brief — never suppressed
- Brand scope is locked at session start — council cannot create NULL-brand artifacts

---

## What Changed From the Prior Model

| Old model | New model |
|---|---|
| 5 fixed roles: Strategist, Analyst, Creative, Channel Spec, Devil's Advocate | No fixed roles — all CMO caliber by default; optional named identity + ideology |
| Single pass: all seats → synthesis → brief | Live rounds: independent → cross-examine → repeat until done |
| Static one-shot output | Streaming transcript that evolves round by round |
| No operator participation during deliberation | C6 is Council #6 — full participant at every round boundary |
| AI-generated synthesis step | Settlement extracted from final round transcript; no separate synthesis model |
| Fixed 5 seats always | Variable — 2 to 5 active seats, whatever the operator configured |
| Round-end question was AI-generated (complexity risk) | Round-end question is hardcoded and simple ("What do you think?") |
| Automatic trigger on persistent deferral | Manual only — explicit @council invocation |

---

## Engineering Contracts (not yet specced — design is locked, build is next)

### Session lifecycle

```
created         — @council received, brand context loaded
round_1_active  — all seats firing in parallel
awaiting_c6     — round complete, simple prompt displayed to C6
round_N_active  — C6 response (or pass) consumed, next round firing
finalizing      — C6 called close or natural convergence detected
settled         — council_brief artifact written, session closed
```

### Data shape (CouncilSession — extends existing model)

```python
status: Literal["round_1_active", "awaiting_c6", "round_N_active", "finalizing", "settled"]
current_round: int
rounds: list[list[dict]]      # rounds[n] = list of {seat_id, content, timestamp}
c6_injections: list[dict]     # {round_boundary, content, timestamp}
pending_c6_prompt: str | None # the hardcoded question currently shown to C6
safety_ceiling: int           # default 10 — stops runaway sessions, not a design limit
```

### Round-end C6 prompts (hardcoded pool, rotate or randomize)

```python
C6_PROMPTS = [
    "What do you think?",
    "Any comments before we continue?",
    "Anything to add or redirect?",
    "Do you want the council to keep going?",
    "Any thoughts?",
]
```

### Seat prompt contracts

**Round 1 system addendum:**
```
This is Round 1. Present your independent position. Do not reference other council members
— you have not heard them yet. Speak as a senior CMO addressing the question directly.
```

**Round 2+ system addendum:**
```
This is Round {N}. You have now heard your peers. Address their positions directly —
name who you agree with and why, name who you disagree with and why.
If your view has changed from Round 1, say so and state what changed it.
```

**C6 injection addendum (appended when C6 responded):**
```
The business leader has added: "{c6_input}"
Factor this into your position.
```

### Endpoints needed

```
POST /council/convene              — start session, run Round 1, return session + first C6 prompt
POST /council/{id}/c6-respond      — C6 injects or passes, trigger next round
POST /council/{id}/finalize        — C6 closes session, produce council_brief artifact
GET  /council/{id}/stream          — SSE stream of live seat responses
GET  /council/sessions             — existing
GET  /council/sessions/{id}        — existing
GET  /council/seats                — existing
PUT  /council/seats/{seat_id}      — existing
```

---

## Approved sample

`sample/council_brief_artifact_v1.md` remains valid as the target output artifact shape (the finalized Stream card). The deliberation transcript format is captured in this document.

The boardroom exchange sample agreed in session (2026-06-02) shows the expected dialogue format:
- Seats named and attributed per contribution
- Each seat directly addresses peers by name
- C6 injection appears inline as a natural contribution
- Convergence happens through the dialogue, not through a vote or synthesis model
- Final decision emerges as a table of marching orders + parked items

---

## Build sequence (when approved)

```
1. Rewrite council module.py orchestrator
   — parallel Round 1, sequential within Round 2+
   — hardcoded C6 prompt pool
   — SSE streaming of seat responses
   — C6 inject/pass handling
   — finalize → council_brief artifact write

2. Update CouncilSession model + migration
   — status enum, current_round, c6_injections, pending_c6_prompt, safety_ceiling

3. Update council router
   — /c6-respond endpoint
   — /finalize endpoint
   — /stream SSE endpoint

4. Stream card — council session
   — live deliberation card (rounds, seat streaming, C6 input area)
   — finalized card (settlement, marching orders, parked, expandable transcript)

5. CMO chat — @council handling
   — short acknowledgement only
   — link to Stream card

6. Memory
   — approved settlement → MemoryEvent
   — dismissed → decision_not_to_act event
```
