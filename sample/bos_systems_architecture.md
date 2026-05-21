# BOS Systems Architecture

Status: working document  
Date: 2026-05-20  
Authors: synthesized from planning session — multiple contributors  

## Source documents

- `sample/bos_cmo_objective_runtime_market_model.md` — CMO operating model, pre-AI team compression, Watchpoints specification, crisis-day scenario
- `memory/project_admin_usecases.md` — admin build state audit, agency owner and ecom store owner persona analyses, priority gaps

---

## What BOS is

BOS is a synthetic marketing department that runs continuously. It is not a tool the operator uses. It is an operator that escalates to the human only when human judgment is required.

The human's job is three actions: **steer, judge, approve.** Everything else belongs to the system.

The competitive advantage AI creates in marketing is no longer production speed — content generation is now cheap. The advantage is **judgment**: knowing what deserves to be made, what signal is credible, what the market is actually saying, what should be ignored, and what decision should be made next.

BOS is a judgment system. Not a content production system.

---

## The three layers

Every architectural decision maps back to one of three layers. Each has a single job and a clear ownership boundary.

**Attention layer — the system's eyes**

Continuously watches every connected surface. Cross-references incoming signals against active objectives. Decides what matters and what is noise. Most signals never reach the operator. The ones that do arrive already interpreted, already ranked, already paired with a recommended action. The attention layer is always running. It does not wait to be asked.

**Memory layer — the system's intelligence**

Not a log. A living knowledge base that accumulates everything: decisions and why they were made, what was tested and what happened, what the client was told, which channels performed under which conditions, which creative angles are fatigued, what objections keep appearing. Every run through the attention loop makes the memory layer richer. The longer the system runs, the more valuable it becomes. Memory is what separates a judgment system from a content API.

**Execution layer — the system's hands**

Acts within approved boundaries. Never touches the outside world without human sign-off. But everything up to that boundary — reasoning, drafting, interpreting, investigating — it does autonomously and continuously. The execution layer is where capabilities and plugins live. It is called by the attention loop, not by the operator directly.

---

## The three surfaces

The operator interacts with BOS through three surfaces only. Minimal by design.

**Stream — where the system pushes what needs human attention**

Not a feed of outputs. A ranked attention queue. The most urgent item leads. The operator makes decisions, not observations. Stream is the product's daily value delivery. If the operator opens Stream and has nothing actionable, the system is working correctly. If the operator opens Stream and finds ten things they didn't know about, the system is also working correctly. What it must never do is bury the important signal under noise.

**CMO — where the operator steers**

Sets direction, changes objectives, asks questions, requests investigations. The CMO opens already holding context from what Stream surfaced. It is never a blank chat box. The operator speaks to one entity — the CMO — not to a roster of specialists. The CMO coordinates the execution layer behind the interface.

**Admin — configuration, not operations**

Brand context, connector setup, team and brand management, institutional memory surfaces. The operator visits Admin to configure and set up, not to work daily. Admin is where the system's capabilities are defined. Stream and CMO are where those capabilities are used.

---

## The morning

The system has been running since yesterday. When the operator opens BOS, the attention layer has already read every connected signal, cross-referenced against active objectives, detected what changed and what it means, ranked hypotheses where there is ambiguity, prepared decision briefs where human judgment is required, and queued artifacts generated overnight.

The operator sees one screen. It tells them what changed, what the risk is, what the recommended decision is, and what they need to approve before the system can continue.

They handle it in fifteen minutes. They walk into the client meeting with a complete, defensible narrative already assembled. The work was done while they were sleeping.

That is the product. That is the experience every architectural decision must protect.

---

## The core loop

```
Active objective
→ system watches what that objective requires watching
→ signals arrive from connected surfaces
→ cross-referenced against memory: what do we already know?
→ interpretation: what does this signal mean in this context?
→ ranking: if multiple explanations exist, which is most likely and why?
→ threshold: does this cross into human attention or stay in memory?
→ if yes: decision brief surfaces in Stream
→ operator judges: approve action, revise, investigate, dismiss
→ if external action: execution layer acts
→ outcome: measured or registered
→ memory updates
→ loop continues
```

The loop never stops. It runs at the cadence the connected signals produce. The operator is not in the loop continuously. They are called into the loop only when their judgment is required.

---

## The six primitives — reframed

These are not API design choices. They are the fundamental operations of any intelligent system.

```
read_signal             → perception
write_memory            → learning
create_artifact         → production
request_approval        → judgment escalation
execute_approved_action → action
evaluate_outcome        → feedback
```

This is how intelligence works. BOS is an implementation of this loop applied to marketing operations. Every capability, every plugin, every module is a composition of these six operations. Nothing in the system exists outside them.

### Layer-to-primitive mapping

The three layers and six primitives are the same system described at two different levels. Primitives are operations. Layers are structural components. Every capability declares which layer it belongs to and which primitives it composes.

```
Attention layer    → read_signal, write_memory (perception and interpretation)
Memory layer       → write_memory, evaluate_outcome (learning and feedback)
Execution layer    → create_artifact, request_approval, execute_approved_action, evaluate_outcome (production and action)
```

This mapping makes the architecture navigable. Any new capability or plugin can be placed unambiguously in the system by identifying its layer and its primitive composition.

### Current build state

| Primitive | Status |
|---|---|
| `create_artifact` | Built — content modules produce artifacts, Stream shows them |
| `request_approval` | Built — Stream approval cards, approve/dismiss/revise |
| `execute_approved_action` | Partially built — Gmail send, some plugin execution |
| `read_signal` | Partially built — connectors exist, scheduled reads not yet running |
| `write_memory` | Not built — no structured memory store, no taxonomy, no queryable layer |
| `evaluate_outcome` | Not built — loop does not close, system cannot learn from approved actions |

The loop does not close. `write_memory` and `evaluate_outcome` are the Gate 2 build targets.

---

## The product across operator types

The loop is identical across all three operator types. The clock and memory content change. The architecture does not.

**Ecom operator**
Watches conversion rate, creative fatigue, offer performance, channel efficiency across one or multiple owned brands. Signals arrive daily. Outcomes measured in purchases, ROAS, CPA, AOV. The system surfaces problems before the morning coffee. Creative fatigue detected before it kills ROAS. Tracking integrity verified before budget decisions are made. The operator focuses on offer strategy and creative direction. The system handles signal monitoring and decision preparation.

**Agency operator**
Watches the same signals across multiple client brands simultaneously. Memory includes client commitments, approved creative directions, and what was promised in the last meeting. The system assembles the client meeting brief the night before. The manager stops spending his day reconstructing context from scattered dashboards, ad platform notes, and Slack threads. Every client review starts from a prepared, defensible narrative rather than from scratch.

**B2B operator**
Watches pipeline movement, stakeholder engagement patterns, objection themes, and proof assets that landed. Signals arrive over weeks, not days. Outcomes registered at deal stage transitions and stakeholder decisions, not at checkout. Memory holds the full relationship context for every prospect — what was said, what objected, what convinced, what is still unresolved. The system surfaces the right action at the right moment in a long sales cycle, not just when the operator remembers to check.

One architecture. Three contexts. The clock and memory content vary. The loop does not.

---

## The pre-AI team as a system model

A marketing team is a data routing and transformation system. Each role owns inputs and produces outputs that feed other roles.

| Role | Inputs | Outputs |
|---|---|---|
| Strategist / CMO | Business goals, market context, stakeholder commitments | Decisions, briefs, approved direction |
| Creatives | Strategic briefs, brand guidelines, offer logic | Ad copy, email drafts, landing page content, campaign angles |
| Channel Specialists | Budgets, creative assets, audience segments | Campaign execution, bid management, optimization |
| Marketing Analyst | Platform data, backend revenue, GA4, UTMs | Performance narrative, attribution caveats, discrepancy flags, recommendations |
| Developer / Integration | Tracking specs, conversion events, CRM requirements | Pixels, GTM tags, API integrations, data reliability |

BOS compresses all five into one CMO-led system. Four roles have partial or full coverage in the current build. **The Marketing Analyst function is not built.** This is the highest-value missing component.

The operator should not experience a simulated org chart of AI specialists. They should experience one strategic CMO that coordinates the equivalent of a full department through capabilities, plugins, memory, and approval gates.

Source: §8, §8.6 of `bos_cmo_objective_runtime_market_model.md`

---

## The analyst function — what is missing

The analyst function owns:

- Cross-signal interpretation (Meta ROAS up, Shopify revenue down — what does that mean?)
- Discrepancy detection (GA4 vs backend vs platform numbers disagree — which is truth?)
- Attribution caveat awareness (platform self-attribution vs blended MER vs backend revenue)
- Hypothesis ranking (ranked list of explanations for a signal, not a single confident answer)
- The "do not" list (protecting the business from wrong reactions is as important as the recommendation)
- Performance narrative (not raw numbers — the story with confidence levels and caveats)

The crisis-day scenario in §10–17 of `bos_cmo_objective_runtime_market_model.md` is entirely an analyst function failure. The manager spends the day manually performing data routing and transformation that a functioning analyst layer would have already completed.

**A CMO without the analyst function can produce content but cannot produce judgment. That distinction is the entire product proposition.**

---

## Structured memory — the foundation

Every higher-order function in the system depends on memory being structured and persistent. Without it, every session starts from zero and the value proposition does not accumulate over time.

### Required memory taxonomy

| Memory type | What it stores |
|---|---|
| Campaign decisions | What was decided, why, by whom, when |
| Test results | What was tested, what the outcome was, what was concluded |
| Stakeholder commitments | What was told to the client or stakeholder, what was approved or rejected |
| Channel performance history | Which channels performed, under what conditions, at what cost |
| Creative fatigue markers | Which angles, hooks, and formats are exhausted for which audience |
| Objection inventory | What objections buyers or clients keep raising |
| Attribution caveats | What the data is and is not telling us, and why |
| Deferred decisions | What was explicitly decided to revisit later |
| Budget pacing state | Where spend is relative to plan and period |
| Tracking integrity state | Known instrumentation dependencies and last-verified status |

Memory is not a chat log. It is a structured store that the CMO reasons against on every run.

Source: §7.7, §17 of `bos_cmo_objective_runtime_market_model.md`

---

## The Watchpoints runtime

Watchpoints are the objective-aware attention layer. They make the system non-brittle and extensible.

### Why not command routing

Command routing is brittle. Every new capability or plugin requires a new branch. Intent matching is hardcoded. It cannot scale.

### The Watchpoints model

```
Active objective
→ Watchpoints (scoped to that objective)
→ Scheduled specialist loops (plugins declare read-only schedules)
→ Signal memory (structured, timestamped, cross-referenceable)
→ New signal arrives
→ Cross-signal interpretation (analyst function)
→ Hypothesis ranking
→ Decision artifact or silence (surfacing threshold filter)
→ Human approval if external action is needed
→ Memory update
→ Continue / pause / complete
```

A Watchpoint is not just a monitoring rule. It contains:

```
Objective
Signal source
Context (what else is known that makes this signal meaningful)
Interpretation logic
Confidence threshold
Decision threshold (when does this cross into Stream?)
Recommended next step
Approval boundary (what can the system do autonomously vs what needs human sign-off)
Memory update rule
```

A new plugin expands what the system can observe or do. It does not require touching the runtime.

Source: §9, §9.1–9.6 of `bos_cmo_objective_runtime_market_model.md`

---

## The surfacing rule — Stream as filtered intelligence surface

Not every signal becomes a card in Stream.

A signal surfaces only when it meets one of these conditions:
- Affects an active objective
- Changes a decision that was previously made
- Crosses a defined threshold
- Reveals risk
- Requires human approval before the system can continue

Everything else stays in memory. Stream is not a feed of everything — it is the output of the CMO's attention filter.

### Two card types — not variations of the same object

**Content artifact card**
- What: creative output (ad draft, email, campaign plan, sequence)
- Operator task: evaluate the copy/creative, approve or revise
- Semantics: is this good enough to go out?

**Decision brief card**
- What: intelligence output (cross-signal interpretation, risk alert, tracking issue, budget recommendation)
- Operator task: evaluate the reasoning and evidence, approve action or investigate further
- Semantics: is this analysis correct and should I act on it?
- Required fields: evidence list, hypothesis ranking with confidence levels, recommended next step, "do not" list

These require different information architecture because the operator is doing a fundamentally different cognitive task in each.

Source: §9.7 of `bos_cmo_objective_runtime_market_model.md`

---

## The morning orientation brief

This is the product's primary daily value proof.

When the operator opens BOS, the system should already have:
- What changed since last session
- What the current risk is
- What the recommended decision is
- What requires approval before the system can continue

This is not a notification. It is a synthesized brief produced by the Watchpoints runtime running against overnight signals and cross-referencing active objectives and memory.

The pre-AI equivalent is the manager arriving to find his analyst and media buyer have already compiled everything and left him a decision-ready brief on his desk. That is the experience BOS must deliver.

It requires: structured memory + analyst function + Watchpoints runtime all operational.

Source: §7.9 of `bos_cmo_objective_runtime_market_model.md`

---

## The two cycle lengths — one architecture, different clocks

The system must serve both short-cycle and long-cycle marketing without different operating modes.

| Type | Cycle | Outcome measurement | Memory criticality |
|---|---|---|---|
| Ecom / direct response | Days to weeks | Purchase, ROAS, CPA, conversion rate | Creative fatigue, offer performance, channel efficiency |
| B2B / high-consideration | Weeks to months | MQL, pipeline, stakeholder movement, deal stage | Stakeholder commitments, objection history, proof that landed |
| High-consideration ecom | Weeks (supplements, furniture, medical aesthetics) | Purchase after nurture sequence | Trust-building sequence, objection handling, proof sequence |

The same loop serves all three. The clock changes, not the architecture. `evaluate_outcome` must handle both same-day feedback (Shopify revenue moved) and multi-week feedback (prospect moved to next stage).

Source: §6 of `bos_cmo_objective_runtime_market_model.md`

---

## Autonomous zone vs approval-gated zone

The system has two operating zones. This is the trust architecture.

**Autonomous zone — system acts without asking:**
- Reading signals from connected surfaces
- Updating memory with new information
- Cross-signal interpretation
- Hypothesis ranking
- Drafting artifacts for review
- Producing decision briefs

**Approval-gated zone — system pauses and waits:**
- Publishing content to any channel
- Sending emails or messages
- Changing budgets or bids
- Pausing or modifying live campaigns
- Contacting customers or prospects
- Any mutation to a live external system

The agentic loop is fully autonomous in reasoning, observation, investigation, and preparation. It is gated at the boundary of external action.

Source: §9.10 of `bos_cmo_objective_runtime_market_model.md`

---

## Minimum viable runtime — single channel

The system delivers value from day one with one connector installed.

Example: Gmail only.

```
Objective: generate $20k pipeline from dormant prospects
→ read_signal: Gmail history, past replies, prospect list
→ write_memory: warm conversations, objection patterns, reply rates
→ create_artifact: reactivation sequence draft
→ request_approval: human approves sequence and send list
→ execute_approved_action: Gmail sends approved emails
→ read_signal: monitor replies
→ create_artifact: follow-up drafts for high-intent replies
→ evaluate_outcome: booked calls, pipeline created
→ write_memory: which angle worked, which objection appeared
→ continue
```

Full omnichannel connectivity is not required to start. This has direct build-order implications.

**The single-channel loop is a build gate, not an illustration.** The full primitive loop — read_signal through evaluate_outcome — must be proven working end-to-end on one connector before expanding to additional connectors. Fan-out before the loop is proven produces a faster content factory, not a judgment system. No second connector gets built until the first connector completes a full loop cycle and memory has been updated from an outcome.

Source: §9.9 of `bos_cmo_objective_runtime_market_model.md`

---

## UX architecture implication — Stream is not an inbox

The current Stream-first direction should not be understood as "put generated artifacts in a feed." That makes BOS feel like an ad generator with approvals.

The stronger product metaphor is:

```text
Stream = business attention layer
CMO = objective-setting, interpretation, and judgment interface
Admin = configuration, institutional memory, and setup surfaces
```

Stream should answer four questions immediately:

```text
1. What objective is currently being protected or advanced?
2. What changed?
3. Why does it matter?
4. What decision is needed from me?
```

Artifacts are only one kind of Stream item. A mature Stream contains six card families:

| Card family | `card_type` value | Meaning | Built state |
|---|---|---|---|
| Pending artifact | `pending_artifact` | Draft output needs approve / revise / dismiss | Built pattern exists |
| Decision brief | `decision_brief` | Interpretation or recommendation needs judgment | Not built |
| Setup blocker | `setup_blocker` | A connector, credential, task, or missing input blocks progress | Partially built in Admin, not Stream-native |
| Signal update | `signal_update` | Something changed but no action is required yet | Not built |
| Outcome / learning | `outcome` | Approved action produced a measurable result or memory update | Not built |
| Council brief | `council_brief` | Multi-agent deliberation output — questions or ranked options from CMO Council | Not built (Gate 3) |

The visual priority should shift from native platform preview density to decision readiness. A card should lead with objective, why-now, evidence, confidence, recommendation, and action boundary. Native previews belong inside artifact cards when the user is evaluating a concrete piece of work; they should not dominate the whole product metaphor.

### Required Stream card contract

Every non-trivial Stream card should carry:

```text
objective_ref       # what business objective this card affects
card_type           # pending_artifact | decision_brief | setup_blocker | signal_update | outcome | council_brief
why_now             # what changed or why this needs attention
confidence          # known | directional | unverified, optionally with score
primary_evidence    # short evidence list, source-linked where possible
recommended_next    # one safe next step
approval_boundary   # what BOS can do autonomously vs what needs approval
allowed_actions     # approve, revise, dismiss, investigate, configure, ask CMO
source_state        # live connector | manual note | planned automation | requires setup
```

This also solves the "some points discussed do not exist in the system" problem. The UX can show future-facing concepts honestly through `source_state` and disabled/educational states rather than pretending the runtime already exists.

---

## The CMO Council — multi-agent strategic deliberation

### What it is

The CMO Council is a multi-agent capability the CMO invokes when a single reasoning pass is insufficient. It is not a user-facing roster of specialists. The operator still speaks to one CMO. The council is internal deliberation that produces a more defensible output than the CMO reasoning alone.

It models how real C-suite decisions work: through structured challenge, not single-point recommendation.

### Two activation triggers

**Strategic complexity** — fires when the CMO detects: confidence below threshold across three or more active signals simultaneously, or cross-signal conflict where two corroborated signals point to contradictory recommended actions, or operator explicitly invokes `COUNCIL:` prefix in CMO chat. The last path is always available. The first two fire autonomously when the attention layer cannot resolve a hypothesis with acceptable confidence.

**Persistent dismissal** — fires when the operator dismisses two or more `DecisionBrief` or `decision_not_to_act` artifacts sharing the same primary `topic_tag` within the same objective scope, without providing a reason or setting a revised objective. The `topic_tag` is the category. Budget recommendations dismissed twice = persistent dismissal on `budget` tag. Creative recommendations dismissed twice = persistent dismissal on `creative` tag. The CMO does not generate a third recommendation of the same type. It convenes the council instead.

Persistent dismissal is architecturally significant. It is the system detecting that something is wrong with its own recommendations, not just that the human disagrees. The council's job in this mode shifts from "what should we do" to "why does the operator keep declining and what are we missing."

### Council composition

Drawn from the five pre-AI roles, each member holds one perspective:

| Member | Perspective | Primary question |
|---|---|---|
| Strategist | Long-term positioning, offer logic, market thesis | Is this the right objective? |
| Analyst | Signal confidence, attribution integrity, data quality | What does the evidence actually support? |
| Creative | Message resonance, creative fatigue, buyer psychology | Will this land with the buyer? |
| Channel Specialist | Platform mechanics, achievability, technical constraints | Can this be executed in this channel at this scale? |
| Devil's Advocate | Risk, blind spots, what the plan is missing | What are we wrong about? |

Each member receives the same brief — active objective, relevant memory, current signals — and produces their perspective independently before synthesis. Disagreement between members is a feature, not a failure. Unresolved disagreement surfaces explicitly in the output.

### Council output contract

```
trigger              # strategic_complexity | persistent_dismissal | operator_requested
objective_ref        # what objective this deliberation concerns
perspectives[]       # one per member: role, assessment, recommendation, confidence, key dissent
synthesis            # CMO integrated recommendation from deliberation
dissent_summary      # what the council could not unify on, and why
recommended_next     # unified next step if achieved, ranked options if not
do_not_list          # what all members collectively agree to avoid
constraint_flags     # suspected hidden constraints if triggered by persistent dismissal
```

### The persistent dismissal investigation

When the council is triggered by persistent dismissal, the output shifts. Instead of another action plan the operator will dismiss again, the council produces a `constraint_investigation` — a structured attempt to surface the hidden blocker.

The council investigates four hypotheses in order:

1. **Capability gap** — is the recommended action outside the operator's actual capacity? Budget, team size, tools, time.
2. **Unstated constraint** — is there a stakeholder, risk tolerance, or timeline constraint the operator hasn't voiced?
3. **Wrong hypothesis** — does the operator know something the system doesn't? Is the CMO's reading of the situation incorrect?
4. **Trust deficit** — is the operator not trusting the system's confidence level? Does the evidence need to be stronger before they will act?

The output is not another recommendation. It is a set of direct questions the CMO puts to the operator to surface which hypothesis is true. The system stops recommending until the constraint is understood.

### Architectural placement

The council sits in the execution layer. It is a composed capability — each member is a sub-agent invoked by the CMO orchestrator with a scoped brief. The council is not a scheduled loop. It is invoked on demand by trigger condition.

Council sessions produce two memory events:
- `council_session` — the full deliberation record, stored against the objective
- `constraint_flag` if persistent dismissal — the identified or suspected blocker, stored as a `PendingDecision` until resolved

The council deliberation surfaces in Stream as a sixth card type: `council_brief`. Same card contract as `decision_brief` with the addition of `perspectives[]` and `dissent_summary`. The operator sees the deliberation, not just the conclusion.

### What this changes in the architecture

The six primitives are unchanged. The council is a composition pattern inside `create_artifact` — multiple agents composing toward one artifact using the same primitives.

The Stream card contract gains one card type. The `MemoryEvent` taxonomy gains two event types. The CMO gains a trigger condition for invocation. No other system components change.

The operator's three actions — steer, judge, approve — remain the same. The council makes the thing being judged more defensible.

---

## Resolved design conflicts

Three genuine architectural disagreements existed in this document. They are now resolved.

---

### 1. Analyst function — visible artifact vs embedded reasoning

**Resolved: both, in sequence. The output contract must be trigger-agnostic from day one.**

In v0 the analyst function is a visible capability that produces a `DecisionBrief` artifact on operator or scheduled trigger. This is correct sequencing because you cannot automate reasoning you have not yet validated. Making it visible first lets the output contract be tested and refined before the trigger changes.

The key constraint: the output contract — evidence, hypothesis ranking, confidence, recommended next step, do-not list — must be identical whether the brief is triggered manually, by schedule, or by a Watchpoint crossing a threshold. The trigger changes across build stages. The contract never changes.

By the time the analyst function runs autonomously in the attention layer, it is producing the same object it produced in v0. Nothing is rewired. The trigger is just automated.

---

### 2. Memory — event-sourced lifecycle vs institutional continuity

**Resolved: two write paths into the same store, both active from day one.**

These were never in conflict. They are different write mechanisms for the same `MemoryEvent` table.

**Passive path** — lifecycle events automatically write memory. Artifact approved, dismissed, revised, run failed. No operator action required. This starts on day one and produces the event foundation.

**Active path** — CMO conversation writes intentional memory. When the operator says "we decided not to run Meta ads because the attribution model was unreliable," the CMO writes a `decision_not_to_act` MemoryEvent with rationale. This does not require a separate UI or a separate build step. It emerges naturally from CMO chat and the CMO's instruction to record decisions explicitly.

The active path is what closes the gap between event-sourced memory and institutional continuity. Pending decisions, rejected options, and rationale are written through CMO conversation, not through lifecycle hooks. Both paths populate the same store. Both start at Gate 2.

---

### 3. Handoff brief — manual trigger vs automatic session hydration

**Resolved: manual first, automatic by design. Transparency solves the trust problem.**

v0: The operator asks the CMO for the current state. The CMO generates the handoff brief from memory on demand. This proves retrieval works and validates what context the system surfaces.

v1: Session start automatically triggers brief generation. The CMO opens already oriented — active objectives, pending decisions, recent outcomes, known risks loaded into context.

v2: The brief is a live object in Stream, updated continuously as MemoryEvents arrive. Always current. The operator never sees a stale state.

The trust concern — that the system is making invisible retrieval decisions — is resolved by making the brief visible as a Stream card. The operator sees exactly what context the CMO loaded for this session. Transparent, not invisible. Controllable: the operator can add, remove, or correct context before the CMO acts on it.

---

## Held — aligned and closed

These points are agreed and no longer need refinement:

1. BOS is an objective-achievement runtime. Chat is one steering surface, not the runtime.
2. The analyst function is the highest-value missing component. Without it BOS is a content API.
3. Memory is continuity infrastructure, not a feature. The new CMO test is the validity check.
4. Stream is a filtered intelligence surface. Six card families (pending_artifact, decision_brief, setup_blocker, signal_update, outcome, council_brief), ranked by urgency, grouped by objective.
5. Approval boundaries are the trust architecture. Autonomous in reasoning, gated at external action.
6. Single-channel loop is a build gate. Proven end-to-end on one connector before expansion.
7. Watchpoints are system machinery, not a user dashboard. They feed Stream cards.
8. Admin is configuration. Daily attention lives in Stream. Strategic steering lives in CMO.
9. Morning brief is assembled from objects that exist — not built as a foundation layer.
10. Wireframes label build state honestly. No fake maturity.

---

## Agreed deliverables and selected marching order

This section is the current build alignment. Broader architecture debates are parked unless they block these deliverables.

### North-star build gate

BOS must prove it can create economic movement with Gmail as the only active marketing channel.

If the system is properly constructed, it should still be able to print money with one channel by completing the full loop:

```text
objective → read Gmail signal/context → create approved outreach artifact
→ execute approved Gmail action or register send → read replies/outcomes
→ evaluate outcome → write memory → make a better next decision
```

If this loop does not work with Gmail, adding Meta, Google Ads, TikTok, LinkedIn, Shopify, or GA4 only adds noise and dashboard sprawl.

---

### Gate 1 — Sample contract

**Deliverable:** `sample/bos_stream_sample.md`

Status: complete / selected as the contract target.

Purpose: freeze the Stream attention-card shape before build. The sample shows all six Stream card families with real Klaroha context, build-state labels, allowed/forbidden behavior, and the fields every card must carry.

Card families in scope:

```text
pending_artifact
decision_brief
setup_blocker
signal_update
outcome
council_brief
```

No new schema, UI, Watchpoint, connector, or Council implementation should contradict this sample.

---

### Gate 2 — Gmail-only revenue loop closes end-to-end

This is the selected implementation sequence. It is intentionally smaller than the full architecture and larger than a content-generation demo.

#### 2.1 Minimal Objective anchor

Create or reuse a minimal `Objective` object so every memory event, artifact, outcome, and brief can answer: what business goal does this affect?

Required v0 fields:

```text
objective_id
brand_ref
status              # draft | active | paused | completed | archived
summary             # e.g. Generate $20k pipeline from dormant prospects this month
success_metric      # e.g. replies, booked calls, pipeline value
horizon             # e.g. this month
created_from        # chat | plan | admin | import
```

#### 2.2 MemoryEvent ledger

Build the append-only memory substrate first. Two write paths start here:

```text
Passive path: lifecycle events write memory automatically.
Active path: CMO conversation writes intentional decisions/rationale.
```

Required v0 event types:

```text
artifact_created
artifact_approved
artifact_dismissed
artifact_revised
run_failed
decision_made
decision_not_to_act
outcome_recorded
constraint_flag
```

Required v0 fields:

```text
brand_ref
objective_ref
topic_tags
summary
rationale          # required on: decision_made, decision_not_to_act
                   # optional on: passive lifecycle events (artifact_approved, dismissed, etc.)
source_ref
timestamp
full_record
```

#### 2.3 Manual `evaluate_outcome` v0

Close the feedback loop before analytics automation.

The operator can register simple outcomes such as:

```text
3 replies
1 booked call
no positive replies
client approved
prospect moved to proposal
```

This creates:

```text
OutcomeRecord
MemoryEvent(type=outcome_recorded)
```

Confidence source starts as `manually_reported`. Connector-measured outcomes come later.

#### 2.4 DecisionBrief capability v0

Build the first analyst artifact using only available data:

```text
active objective
brand context
run/artifact history
MemoryEvents
manual OutcomeRecords
Gmail context/signals if available
```

Output contract:

```text
summary
objective affected
evidence
hypothesis ranking
confidence
recommended next step
do-not list
allowed actions
```

**Stream surface requirement (Gate 2 minimum):** `DecisionBrief` must be visible and actionable in Stream as a `decision_brief` card. This is not the full Stream redesign (Gate 3) — it is the minimum required for the operator to interact with the output. The card carries the fields above. Allowed actions: investigate, ask CMO, dismiss. A `DecisionBrief` the operator cannot see in Stream is not a Gate 2 deliverable — it is a backend object with no pass condition.

Similarly, `OutcomeRecord` from step 2.3 must surface as an `outcome` card in Stream. Same minimum bar: visible, dismissable, carries the memory update confirmation.

This is the first real movement from content tool to judgment system.

#### 2.5 Handoff brief on demand

Build the new-CMO continuity test before automated morning brief.

This step also introduces `PendingDecision` as a first-class object — the mechanism for carrying deferred decisions across sessions:

```text
PendingDecision fields:
  objective_ref         # which objective this decision affects
  brand_ref
  what_is_deferred      # the decision being held
  waiting_for           # what information or event resolves it
  leading_hypothesis    # current best guess
  action_blocked        # what cannot proceed until this resolves
  created_at
  resolved_at           # null until resolved
```

`PendingDecision` rows surface immediately as priority context in the handoff brief and are closed (resolved_at set) when the operator makes the deferred decision via CMO conversation.

The CMO can generate the brief on demand:

```text
active objectives + current state
recent performance narrative with confidence levels
pending decisions and what they are waiting for
committed actions and deadlines
known risks and what is being watched
what is working and what is not
what was decided against and why
recommended first action
```

Pass condition: a new CMO — human or AI — can become operational in under 15 minutes from the brief alone.

#### 2.6 Gmail loop proof

Run one real or operator-reported Gmail objective loop:

```text
Objective: generate pipeline/revenue from dormant prospects
Artifact: approved Gmail reactivation/follow-up sequence
Action: approved send or registered manual send
Signal: replies / no replies / booked call / objection pattern
Outcome: manually recorded or connector-read
Memory: updated with what worked, what failed, what to avoid
Next brief: recommends a better next action than the first one
```

**Gate 2 pass condition:** one objective completes a full primitive loop, the `decision_brief` and `outcome` cards are visible and actionable in Stream, and memory demonstrably improves the next recommendation.

No second connector, Watchpoints implementation, Council implementation, cross-brand command center, or campaign board until this pass condition is met.

---

### Gate 3 — Productize the proven loop

Only after Gate 2 passes. Sequence matters — each item depends on the one before it.

1. **Stream full redesign** — six card families, ranked by urgency, grouped by objective. Replaces the Gate 2 minimal card rendering. This is the full attention surface from the sample.
2. **CMO contextual opening** — CMO opens from a selected Stream card with context pre-loaded. Requires Stream redesign to exist.
3. **Objective lifecycle formalization** — `draft → active → paused → completed → archived` enforced, cross-brand objective view. Requires Stream redesign to display objective state.
4. **Watchpoints v0** — objective-bound scheduled signal checks. Each Watchpoint declares source, cadence, threshold, and surface rule. Feeds `signal_update` and `decision_brief` cards into Stream. Requires Objective lifecycle.
5. **Automated morning brief** — assembled from Watchpoints output: surfaced cards, pending decisions, known risks, recent outcomes. Requires Watchpoints to exist.
6. **CMO Council v0** — sub-agent deliberation for strategic complexity and persistent dismissal. Requires `MemoryEvent` and `DecisionBrief` (Gate 2 deliverables) to brief members meaningfully. Surfaces as `council_brief` card in Stream.
7. **Second connector** — after Gmail loop has proven economic movement and Gate 3 items 1–4 are live. Connector selection driven by operator's next highest-priority signal source.

---

### Parked for later discussion

Parked items are valid and will be built — they are deferred because they do not block Gate 2 and expanding scope before the loop is proven produces a faster content factory, not a judgment system.

**Deferred to Gate 3 or later (features):**
- Cross-brand command center — requires Objective/card contracts from Gate 3
- Campaign status board — same dependency
- Automated digest notifications — requires Watchpoints (Gate 3)
- Full analytics unification — multi-connector, post Gate 3
- Multi-connector attribution model — post Gate 3, requires 2+ connectors live
- Omnichannel connector fan-out — second connector only after Gate 3 items 1–4

**Open architecture questions (do not resolve before Gate 2 produces evidence):**
- Whether `council_brief` remains a separate card family or becomes a `decision_brief` reasoning mode — answer this after seeing how operators actually interact with council output
- Exact Watchpoints dashboard UX — design after operators have live Watchpoints to react to
- Council member count and roster composition — v0 ships with five members; adjust after first real deliberation session

The rule: if a proposed item does not help close the Gmail-only objective loop, park it.

---

## Resolved architectural decisions

These were open questions. They are now answered and closed.

**Where does an objective get declared?**
Multiple origins — campaign plan approval, CMO conversation, admin creation, imported brief — all converge to the same `Objective` object. The origin is recorded but the object is identical regardless of how it was created. The CMO does not behave differently based on how an objective entered the system.

**What is the minimum Watchpoint schema?**
Gate 3 item 4. Minimum v0 fields: `objective_ref`, `signal_type`, `source_plugin`, `cadence`, `threshold`, `last_checked_at`, `last_snapshot_ref`, `surface_rule`, `approval_boundary`. No fields are added until a specific signal type or plugin requires them.

**What is `SignalSnapshot` and when does it get built?**
`SignalSnapshot` is a structured read result produced by a Watchpoint completing a scheduled check — it carries the raw data, source, timestamp, staleness_score, and instrumentation state. It does not exist in Gate 2. For Gate 2, `DecisionBrief` evidence comes directly from Gmail connector context and MemoryEvents. `SignalSnapshot` is a Gate 3 object, created when Watchpoints begin producing scheduled reads. The confidence model section describes its eventual shape but it is explicitly parked until Gate 3 item 4.

**How does `evaluate_outcome` handle long-cycle feedback?**
Two paths, same object. For ecom: connector-detected from backend revenue movement. For B2B: operator-registered manually — "call happened, moved to contract." Both produce an `OutcomeRecord`. The `confidence_source` field distinguishes them: `measured` (connector-detected) vs `manually_reported` (operator-entered). Both update memory. Both close the loop.

**What is the surfacing threshold?**
A signal crosses the surfacing threshold when it changes the recommended action for an active objective. Not magnitude of change. Not absolute value. Whether acting on this signal would produce a different operator decision than what the current memory already supports. Signals that confirm existing direction stay silent. Signals that change direction surface.

---

## The confidence model

"Known / directional / unverified" are labels. The system needs to compute confidence, not just name it. Confidence is derived from three inputs:

**Source freshness** — how recent is the signal? A GA4 snapshot from three days ago has degraded confidence. Every `SignalSnapshot` carries a timestamp and a `staleness_score` that increases with age relative to the expected cadence of that source.

**Corroboration** — does a second independent signal point the same direction? A conversion rate drop in GA4 that is not reflected in backend revenue is low corroboration. The same drop confirmed by Shopify checkout data is high corroboration. The analyst function checks for corroborating signals before assigning confidence.

**Instrumentation state** — is the tracking known clean? If the last tracking integrity check flagged a dependency as unverified, every signal that flows through that dependency inherits a confidence penalty. Tracking state is a first-class confidence modifier.

Confidence propagates from `SignalSnapshot` into `DecisionBrief` and is carried on every `Stream` card as a visible field. The operator always sees what the system's confidence is based on, not just what the conclusion is.

---

## Memory retrieval design

The memory layer stores everything. The CMO cannot reason over everything simultaneously. The retrieval design determines whether memory makes the system smarter or just larger.

Every `MemoryEvent` carries:
```
objective_ref     # which objective this event is relevant to
brand_ref         # which brand
timestamp         # when it occurred
topic_tags        # indexed topics: creative_fatigue | tracking | attribution | offer | objection | commitment | outcome
summary           # one-sentence LLM-readable summary of the event
full_record       # complete structured data
```

At reasoning time — when the attention layer is interpreting a signal against an active objective — the CMO receives:

```
active objective
+ current signal snapshot
+ memory chunks selected by: matching topic_tags + same brand + same objective + recency weighting
```

Not all memory. The contextually relevant slice. The `topic_tags` field is the retrieval index. Without it, memory is a database the LLM cannot query efficiently. With it, the CMO gets the right context for the decision at hand without the prompt becoming incoherent.

---

## Analyst function error handling

When the analyst function produces a wrong hypothesis and the operator follows it and takes a bad action, the system needs an explicit correction path.

The correction path:
1. Operator flags a `DecisionBrief` as incorrect after acting on it
2. The flag creates a negative `MemoryEvent` with the original brief reference, the incorrect hypothesis, what actually happened, and the operator's correction
3. The `topic_tags` from the original brief are inherited by the negative event
4. Future signals with matching topic_tags retrieve both the original brief and the negative event as context
5. The analyst function reasons against the correction when forming new hypotheses for similar signals

The analyst function learns from being wrong. Error correction is not exception handling. It is a first-class learning mechanism and a required feature of the memory layer, not an afterthought.

---

## Institutional continuity — the new CMO on Monday

Every AI conversation today is already that Monday. The AI CMO starts each session with zero context. The operator re-briefs it every time. That is the current broken state — not a future risk.

The memory architecture must pass one test: can a new CMO — human or AI — become fully operational from memory alone in under fifteen minutes, without asking anyone anything?

### Four requirements this surfaces

**Decision rationale is a required field.** Every `MemoryEvent` of type `decision` must carry why this option over the alternatives, what evidence supported it, what risk was accepted. Without rationale the new CMO contradicts previous logic without knowing it.

**"Why not" records are first-class objects.** What was explicitly decided NOT to do is as important as what was done. A `MemoryEvent` of type `decision_not_to_act` carries the option considered, the rationale for rejecting it, and the conditions that would change the decision. Prevents re-evaluation of closed questions.

**Pending decision state must be explicit.** The outgoing CMO was waiting for something — data, a client response, a signal confirmation. A `PendingDecision` object records: what decision is deferred, what information is needed to resolve it, what the leading hypothesis is, what action is blocked. Surfaces immediately as priority context for the new CMO.

**The CMO handoff brief is a generatable artifact.** At any point the system produces a coherent narrative briefing — not a database dump — assembling from memory:

```
active objectives + current state
recent performance narrative with confidence levels
pending decisions and what they are waiting for
committed actions and deadlines
known risks and what is being watched
what is working and what is not
what was decided against and why
```

This brief is both human-readable and the context hydration package for the AI CMO at session start. The system loads the relevant slice of this brief into context at the beginning of every session — not all memory, the right memory for the current moment and active objectives.

### Architectural implication

Memory is not stored so the system can remember things. Memory is stored so the system can reconstitute a complete operating picture at any moment for any authorized agent. That is continuity infrastructure, not a feature.

