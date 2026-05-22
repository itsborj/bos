# chat.py — Dev Notes

Covers: `api/routers/chat.py`
Related: `api/skills/memory.py`, `api/routers/brands.py`, `api/routers/runs.py`

---

## CMO Chat Coordination Hub

Use this file as the shared discussion and handoff surface for CMO chat work across AI agents.

**Status:** coordination notes only — not an approved spec. Follow BITE stages before behavior changes: Discuss → Sample → Agree → Reverse-spec → Build.

**How agents should use this file**
- Add dated notes under the relevant section before touching CMO chat behavior.
- Record bad sample / fixed sample pairs for regressions.
- Link approved samples in `sample/` before writing implementation specs.
- Keep decisions traceable to `PROJECT_BRIEF.md`, `BITE.md`, and `BACKLOG.md`.
- Never use this file to justify hardcoded routing in `chat.py` or `skills/router.py`.

---

## Marching Orders — CMO Agentic Loop (2026-05-22)

> Produced after reading PROJECT_BRIEF.md, BACKLOG.md, chat.py (full), and pi agent docs. Agents: read this section before touching CMO chat. If you disagree with the ordering, add a dated counter-note below — do not silently deviate.

### The situation in one paragraph

Gate 2 is passed. The streaming pipeline is live (v3.28 — SSE, step events, module trace, artifact refs). The current CMO chat still behaves too much like single-pass dispatch: it calls the LLM, dispatches specialists, then returns reply text that was written before the CMO saw specialist results. Phase 6 must upgrade this into a shallow supervisory loop modeled from pi.dev mechanics but optimized for Klaroha's actual user: an overloaded business leader / marketing operator managing multi-brand, omni-channel direct-response and long-sales-cycle campaigns. The goal is not to expose more agent machinery; it is to shorten idea → execution → signal → optimization while preserving Stream approval boundaries and brand-scoped memory.

### Current model — two loops, not one

Klaroha needs two distinct agentic loops.

#### 1. CMO execution loop

Fast, operator-facing, artifact-producing.

```text
business intent
→ CMO selects job: marketing.plan / marketing.execute / marketing.optimize
→ specialists run
→ Stream artifacts appear
→ specialist results return to CMO as tool-result-style summaries
→ CMO writes final concise synthesis after seeing results
→ operator approves / revises / dismisses
→ outcome and memory close the optimization loop
```

Use for:
- campaign artifacts and creative bundles
- revisions
- simple planning
- optimization recommendations
- low/medium-risk execution prep
- day-to-day operator steering

#### 2. Council deliberation loop

High-stakes, slower, multi-perspective judgment.

```text
@council strategic question
→ 5 CMO-level strategist seats deliberate, each with its own model + ideology
→ full debate transcript is captured as supporting artifact detail
→ council_brief becomes the final product
→ marching orders + parked decisions surface in Stream
```

Use for:
- GTM strategy
- brand redesign
- quarterly budget/resource allocation
- major positioning shifts
- high-risk/high-reward campaign bets
- persistent strategic disagreement or repeated dismissal

CMO may recommend Council, but must not auto-run it:

> "This is Council-grade: brand risk + resource tradeoff. Want me to convene the Council?"

### Council + agency context (do not omit)

**Council:** `@council` is not a mechanical shortcut like `@klar`; it is an explicit invocation of a separate deliberation engine. Current backend has Council seats, session persistence, and `@council` routing, but the product target is artifact-first: chat returns a short summary + artifact ref, while Stream/Workspace owns the `council_brief` and expandable transcript. Do not thread Council into normal CMO synthesis until an approved `council_brief` Stage 2 sample exists.

**Agencies:** The agency model is a scope invariant for every Phase 6 build. Org = agency/operator control plane; Brand = client/business; Market Unit = optional location/agent/territory/service/SKU scope. All CMO loop work, connector readiness, OAuth credentials, artifacts, memory, and approvals must remain Brand-scoped. No feature should assume a single in-house brand, and no artifacts should be created with `brand_id=NULL` in multi-brand/agency workspaces.

**Agency operating model:** The business process to compress is:

```text
client docs / website / offer
→ brand memory + Campaign Brand Kit
→ industry buying-model analysis
→ competitor + value-proposition adjacency
→ low-hanging-fruit opportunity analysis
→ plan approval
→ connector/readiness work by integrators
→ coordinated creative/channel/web execution
→ week-1 data feedback
→ optimization recommendation
→ next production loop
```

Pi supplies loop mechanics; the agency process supplies the business workflow.

---

## Code-Dev Marching Orders — Current Stack

### Order 0 — Samples before code

Two Stage 2 samples are needed before implementation specs/builds that change behavior.

#### 0A. `creative_bundle` sample
Purpose: prove the fast CMO execution loop.

File target: `sample/creative_bundle_artifact_v1.md` (already started).

Must show:
- operator gives campaign idea in normal language
- active Brand / agency scope is clear
- copy + visual specialists run from one shared campaign brief
- artifacts appear in Stream
- CMO final reply happens after seeing specialist summaries
- chat contains artifact refs only, no inline native copy or image prompt
- approval boundary: bundle approval ≠ publish/spend/send approval

Default for v1: **Path A — parallel + synthesis reply.**

```text
campaign brief
→ copy specialist + image specialist in parallel
→ CMO synthesis checks coherence after both complete
→ final short reply points to Stream
```

Escalate to sequential only when needed:
- brand redesign
- high-ticket / long-sales-cycle asset
- visual depends on exact headline/CTA
- compliance or brand-risk concern
- failed self-check
- Council recommends tighter sequencing

#### 0B. `council_brief` sample
Purpose: prove the high-stakes deliberation loop.

Must show:
- user invokes `@council` for a Council-grade decision
- 5 strategist seats deliberate
- final `council_brief` artifact is created
- transcript is stored as expandable supporting detail, not dumped as primary chat output
- chat returns short settlement summary + artifact ref only
- allowed/forbidden outcomes are explicit

### Order 1 — Define loop boundaries

Before code, keep the boundaries explicit:

| Loop | Owns | Does not own |
|---|---|---|
| CMO execution loop | fast plan/execute/optimize steering, artifact production, result synthesis | high-stakes multi-perspective settlement, external actions without approval |
| Council deliberation loop | strategic judgment, tradeoff debate, marching orders, parked decisions | routine creative production, channel execution, publishing/spend/actions |
| Specialist/plugin loop | native artifacts, read/diagnostic outputs, approved channel actions | business strategy, brand scope switching, CMO reply text |

### Order 2 — Fix CMO synthesis after specialist results

This is the first code slice after the relevant Stage 2 sample is approved.

Current flaw:

```text
CMO speaks before specialists finish.
```

Target:

```text
specialists finish
→ CMO sees result summaries
→ CMO gives final concise operator reply
```

Final reply should be business-oriented:

> "Campaign bundle is ready in Stream. Review the lead angle first; visual fit passed brand check."

Not:

> "I ran module X and module Y."

Implementation constraint: if this lands in `chat.py` first, keep it generic and isolated as a loop primitive. Do not add platform-specific branches, hardcoded module IDs, or phrase routing.

### Order 3 — Specialist result summary contract

CMO synthesis may see decision-useful metadata only:

```json
{
  "run_id": "...",
  "artifact_ref": "...",
  "artifact_type": "draft_artifact | plan_artifact | intelligence_artifact | creative_bundle | council_brief",
  "status": "pending_review | completed | failed",
  "summary": "Lead magnet creative bundle created",
  "self_check": "passed | warnings | failed",
  "recommended_decision": "review | approve | revise | dismiss | connect_account",
  "objective_ref": "...",
  "brand_ref": "...",
  "allowed_actions": ["approve", "revise", "dismiss", "ask_cmo"]
}
```

Forbidden in synthesis context unless a future sample explicitly permits it:
- full native email/ad/post body
- image prompts
- targeting/budget fields
- provider/model/backend details
- raw module IDs in visible reply

### Order 4 — Council output artifact-first

Long-term target:

```text
Chat:
"Council settled on 4 marching orders and parked 2 decisions. Brief is in Stream."

Stream artifact:
- council_brief
- final recommendation / settlement
- marching orders
- parked decisions
- confidence / alignment
- full round transcript as expandable detail
```

This aligns Council with the Workspace/Stream artifact plane. The transcript is allowed as detail, but the `council_brief` is the final product.

### Order 5 — Creative production policy

For the overloaded operator, optimize speed to decision.

Default:

```text
shared campaign brief
→ parallel copy + visual + channel prep where safe
→ CMO synthesis after results
→ one decision-ready Stream artifact/card
```

Sequential chaining is a capability, not the default product posture. Use it only when dependency, risk, or failed quality gates justify the extra latency.

### Order 6 — Connector/readiness context

Business operators hate failed execution. Before dispatch, the CMO should know which specialists are ready for the active Brand.

Target prompt input is registry-generated, e.g.:

```text
Connector readiness:
- Gmail: connected
- Google Ads: not connected
- Search Console: connected
- Meta: missing permissions
```

This must come from connector registry / plugin manifests. No `if gmail`, `if google_ads`, platform phrase matching, or hardcoded chat routing.

### Order 7 — Thin session correlation now; real session ledger later

Add `session_id` only as correlation/run grouping once the synthesis path is approved.

Do not confuse this with pi's session architecture. Park full session tree until after loop proof:
- branchable entries
- compaction summaries
- steering queue
- handoff reconstruction
- deterministic replay from DB

### Order 8 — Deferred refactor track

Do not block Phase 6 loop proof on these:
- full hook system
- `chat.py` shrink to ~100 lines
- branch/tree UI
- compaction UX
- server-side steering queue
- deep multi-agent background loops

Keep them as the target architecture once samples and loop proof are done.

### One-line summary

> CMO loop shortens idea → artifact. Council loop improves high-stakes judgment. Stream carries decisions. Memory closes optimization.

---

**Current focus (2026-05-22)**
- Improve the CMO agentic loop by replicating the pi.dev agent experience in BOS terms.
- Preserve CMO chat as a short control/narrative surface.
- Push native previews, approval, revision, dismissal, and system details to Workspace/Stream artifacts.
- Continue shrinking `chat.py` toward the fixed 7-step loop described below.
- Treat capability activation as SKILL.md + manifest-owned, with chat code enforcing only safety/security boundaries.

**Pi → Klaroha UX translation target**
- Pi's session JSONL tree → BOS CMO session ledger with branchable turns, run/artifact links, compaction summaries, and handoff briefs.
- Pi's tool calls/results → BOS specialist/capability executions with visible step events and human approval boundaries.
- Pi's extension hooks → BOS lifecycle hooks (`bridge.before_transform`, `transform.after_execute`, `run.persisted`, `approval.resolved`).
- Pi's skills/resources → BOS `SKILL.md` + live capability/readiness manifest.
- Pi's steering/follow-up queue → BOS operator steering while specialists are running, plus after-run follow-up queue.
- Pi's compact terminal UX → Klaroha mobile-first CMO + Stream split: chat narrates, Stream renders artifacts.

### 2026-05-22 — CMO agentic loop objective
- Goal: replicate the pi.dev agent loop UX for Klaroha BOS, not by embedding pi, but by copying its durable mechanics: fixed loop, streamed tool/specialist events, session tree, steering queue, hooks, progressive skills, compaction, and reloadable resources.
- Files touched: `api/routers/chat_notes.md`, `BACKLOG.md`.
- Sample used/needed: needs Stage 2 sample showing one owner request → streamed CMO/specialist loop → artifact in Stream → steering/follow-up → persisted session/handoff.
- Invariants checked: no platform routing in chat; no inline native artifacts; SKILL.md/manifest owns activation; chat code remains safety boundary only.
- Open questions / next agent handoff: define the Stage 2 sample first, then reverse-spec the smallest implementation slice.

**Agent handoff template**
```md
### YYYY-MM-DD — <agent/task>
- Goal:
- Files touched:
- Sample used/needed:
- Invariants checked:
- Open questions / next agent handoff:
```

### 2026-05-22 — Pi pattern discovery: agentic loop gaps and implementation targets

**Goal:** Study pi agent source docs, map mechanics to BOS, identify what's missing, and define the smallest implementation slice to replicate the pi UX.

**Files read:** `api/routers/chat.py` (full, 1,616 lines), `api/routers/chat_notes.md`, pi docs: extensions.md, skills.md, session-format.md, index.md.

---

#### What pi actually does (concrete mechanics)

**The loop (from extensions.md + session-format.md):**
```
receive input
→ build context from session JSONL tree (buildSessionContext() walks id/parentId chain)
→ LLM turn (skills manifest in system prompt as XML descriptions only)
→ execute tool calls (registered via pi.registerTool())
→ tool results injected back as messages
→ repeat from LLM turn until no more tool calls
→ append typed JSONL entry to session file
→ return final reply to user
```

**Three primitive tools:** `read`, `write`, `edit` (plus bash/grep/find/ls). Every capability is composed from these. The loop never changes to accommodate a new tool; tools register themselves via `pi.registerTool()`. The LLM decides when to call each.

**Extension hooks (pi.on events):**
- `session_start` — before first turn
- `tool_call` — before a tool fires (can block/modify)
- `tool_result` — after a tool returns
- `agent_start`, `agent_stop` — loop boundaries
- `model_change`, `compaction` — infra events
Extensions subscribe; the main loop never references them by name. A broken extension can only break itself.

**Session JSONL entry types:**
| Type | Purpose |
|---|---|
| `session` | File header (no id/parentId) |
| `message` | Conversation entries with typed content blocks (text, toolCall, toolResult, thinking) |
| `compaction` | Context summary with `firstKeptEntryId` — loop walks to this boundary on replay |
| `branch_summary` | Context from abandoned/forked paths via `fromId` |
| `custom` | Extension state (not injected into LLM context) |
| `custom_message` | Extension content that IS injected into LLM context |
| `label` | User bookmark on an entry |
| `model_change`, `thinking_level_change` | Infra state changes |

All entries (except header) have `id` (8-char hex) and `parentId`. `buildSessionContext()` walks from current leaf to root, collecting entries. Hitting a `compaction` entry emits the summary then skips to `firstKeptEntryId` — conversation continuity survives compression.

**Skills (progressive disclosure):**
- Only `name` + `description` are always in the LLM context (as XML)
- Full `SKILL.md` content loads on-demand when the agent calls `/skill:name`
- This keeps the base system prompt small regardless of how many skills are installed

---

#### What BOS already has (correctly matching pi)

| Pi concept | BOS current state |
|---|---|
| Skills as SKILL.md files | ✅ `api/capabilities/*/SKILL.md` with `description`, `triggers`, `module_id` |
| Capability manifest → system prompt | ✅ `format_manifest_for_prompt()` in `_build_system_prompt()` |
| SSE streaming with step events | ✅ `POST /chat/stream` — `step`, `module_result`, `reply`, `done` events |
| Extension isolation principle | ✅ Architectural target in chat_notes.md (hook model section) |
| Security boundary as the only gate | ✅ `allowed_module_ids` check after LLM output |

---

#### The core gap: BOS is single-pass; pi loops

**This is the biggest UX difference.**

Pi's loop repeats `LLM turn → tool results → LLM turn` until no more tool calls. The LLM sees every tool result and can dispatch more tools, synthesize, ask for clarification, then return a final reply. The user sees the whole trace live.

BOS `_generate_chat_stream` today:
1. Single LLM call → parses `RUN:` directives from reply text
2. Dispatches modules → collects `run_results`
3. Returns the **original reply text** as the final message

The CMO LLM **never sees what the specialists produced**. It can't synthesize results, can't chain dispatches, can't confirm to the user what was actually created. The reply is written before execution. This is why it feels mechanical.

---

#### Three gaps, in priority order

**Gap 1 — Multi-turn synthesis loop (highest UX impact)**

After specialists complete, their results must feed back into a second CMO LLM turn. The CMO reads the run summaries/artifact refs and writes the final reply _after_ seeing what was produced. It can optionally fire more specialists in that second turn.

Target SSE trace for a "create launch campaign" request:
```
step: Thinking...
step: Running Planning Specialist...
module_result: {artifact_ref: marketing.plan}
step: Synthesizing results...          ← second LLM turn starts here
step: Running Email Outreach...        ← CMO dispatched this in synthesis turn
step: Running Social Copy...
module_result: {artifact_ref: email.outreach}
module_result: {artifact_ref: social.post}
reply: "Launch package ready. Plan, email sequence, and social posts are in Stream."
done
```

Implementation: after `_run_modules_streaming` completes, build a synthesis message containing run summaries and artifact refs, append to `messages`, call `_complete_cmo_messages` again, parse for more `RUN:` directives (with a depth limit of 3 to prevent runaway loops), yield final reply.

Max loop depth: 3 turns. If depth exceeded, return whatever is in progress.

**Gap 2 — Session ledger (enables handoff briefs, compaction, branch traces)**

No equivalent of pi's JSONL session file. Each request is assembled fresh from `body.history` (frontend-provided strings). State reconstruction is not deterministic — it depends on what the frontend sent.

Target schema (DB table `cmo_session_entries`):
```
id           UUID PK
session_id   UUID FK → cmo_sessions.id
parent_id    UUID FK self-ref (nullable for root)
entry_type   VARCHAR  (turn_start | specialist_dispatch | specialist_result | synthesis_turn | turn_complete | compaction | branch_summary | custom)
payload      JSONB
created_at   TIMESTAMPTZ
```

`buildSessionContext()` equivalent: walk from leaf to root, stop at compaction entries and emit summary + `firstKeptEntryId` forward. Frontend sends `session_id` instead of full `history` array.

This is Phase 4+ scope — must define schema before building.

**Gap 3 — Steering queue (low-effort, high feel)**

User sends a follow-up message while specialists are running. It gets queued server-side and injected at the start of the synthesis turn. Frontend sends a `POST /chat/stream/steer` with the session_id; backend holds it in a per-session `asyncio.Queue`. The synthesis turn drains the queue and prepends it to the next LLM message.

Requires session ledger (Gap 2) to be meaningful — without a session ID there's no queue to target.

---

#### Recommended implementation sequence

1. **Gap 1 first** — multi-turn synthesis loop in `_generate_chat_stream`. No schema changes. ~80 lines of new code inside the existing generator. Delivers the pi UX feel immediately.
2. **Gap 2 second** — session ledger schema + migration. Migrate `body.history` to `session_id` in the request model. `buildSessionContext()` replaces the inline history assembly.
3. **Gap 3 third** — steering queue as a thin `asyncio.Queue` per session_id after the ledger exists.

Hook system and chat.py reduction (~100 lines target) can proceed in parallel with Gap 2/3 as a refactor track.

---

**Sample needed:** Stage 2 sample showing Gap 1 UX — one owner request → multi-turn CMO/specialist loop → artifact in Stream → synthesized reply. Must include allowed outcomes (specialist results read back, chained dispatch) and forbidden outcomes (infinite loop, inline artifact copy in reply). Pending user agreement before implementation begins.

**Open questions / next agent handoff:**
- Confirm max loop depth (currently proposing 3)
- Should synthesis turn always happen even when there's only one module result? (Proposed: yes, for consistency — the CMO always writes the reply after seeing results)
- Does the frontend need a new SSE event type for synthesis turns? (Proposed: reuse `step` with label "Synthesizing results...")
- Session ledger: new DB table or extend existing `Run`/`RunResult` schema?

---

### 2026-05-22 — Pi pattern perspective: copy the interaction contract, not the implementation surface

**Goal:** Add a second-agent perspective after reading pi `index.md` and related docs (`usage`, `sessions`, `session-format`, `extensions`, `skills`, `compaction`, `rpc/json`, `sdk`, `tui`, settings/keybindings/provider docs).

**Agreement with prior note:** Gap 1 is the fastest way to make BOS feel less mechanical. The CMO should not speak final user-facing text until it has seen specialist/tool results.

**Important refinement:** The thing to copy from pi is not “make another LLM call after modules.” The thing to copy is the **interaction contract**:

```text
user intent
→ streamed agent thinking/step trace
→ visible tool/specialist calls
→ tool/specialist results become context
→ agent may continue or stop
→ final concise reply references persisted artifacts
→ full turn is reconstructible later
```

If we implement Gap 1 as an ad hoc second completion inside `chat.py`, we improve feel but risk extending the monolith. The smallest safe slice should still look like a generic loop helper, not module-specific chat code.

**Recommended framing for Gap 1:** introduce a generic internal loop primitive even if it initially lives near `chat.py`:

```text
run_cmo_turn(max_depth=3):
  build prompt/context
  call CMO LLM
  extract hidden directives
  security-check directives
  execute specialists
  convert specialist results into tool_result-style context blocks
  repeat until no directives or depth limit
  return final visible reply + artifact refs + trace events
```

The loop primitive should be platform-agnostic and should only know:
- `directive` = requested transform/module id + params
- `tool_result` = run id, artifact refs, status, self-check summary, failure summary
- `visible_reply` = final CMO text after directives are stripped

**Key design cautions:**
1. **Do not let synthesis re-open hardcoded routing.** Second-turn dispatch must use the same manifest + allowed-module security boundary. No phrase matching, no channel filters.
2. **Do not let synthesis paste artifact contents.** The synthesis context may include summaries and refs, not full native copy fields. Final chat reply still links/references Stream artifacts only.
3. **Depth limit is mandatory.** Max 3 is reasonable for sample/build. If exceeded, stop dispatching, persist trace, and return a short safe message with existing artifact refs.
4. **Failure is a first-class tool result.** If one specialist fails and another succeeds, the CMO should synthesize partial success and point to created artifacts; failed runs should not crash the loop.
5. **A synthesis turn should run whenever directives executed.** Otherwise the final reply is still pre-execution text. For pure discussion/no directives, no extra call is needed.
6. **Use new SSE event names only if the UI needs semantics.** `step` is enough for now, but the trace payload should internally distinguish `llm_turn`, `specialist_start`, `specialist_result`, `synthesis_start`, `loop_stop` so a future session ledger can persist it cleanly.

**My priority order:**
1. Stage 2 sample for the loop UX, including allowed + forbidden outcomes.
2. Gap 1 as a generic loop helper with depth limit and tool-result context.
3. Persist the loop trace into a real CMO session ledger.
4. Add steering/follow-up queue once session identity is stable.
5. Move loop-adjacent concerns into hooks after the ledger exists.

**Deliberation points for the human + agents:**
- Should CMO final replies be allowed to summarize artifact intent/outcome in one line, or only say “ready in Stream”? Proposed: one-line outcome summary is allowed; native fields are forbidden.
- Is max depth 3 enough for owner-facing marketing loops? Proposed: yes for interactive chat; deeper work should become background objective-loop jobs.
- Should the first implementation persist trace in existing run traces before adding `cmo_session_entries`? Proposed: acceptable for Gap 1 sample proof, but not a substitute for the session ledger.
- Should steering exist before a DB session ledger? Proposed: no, except local frontend queue UI; server-side steering needs stable `session_id`.

**Sample needed:** A Stage 2 sample should show the exact visible stream: CMO message, step trace, specialist cards/artifacts, synthesis step, final reply, plus forbidden examples (inline native copy, infinite loop, unscoped brand dispatch, rerouting by phrase matching).

---

### 2026-05-22 — Synthesis-after-results Path A implementation note

- Goal: implement the first approved CMO execution-loop slice from `sample/creative_bundle_artifact_v1.md`.
- Files touched: `api/routers/chat.py`, `sample/creative_bundle_artifact_v1.md`, `sample/council_brief_artifact_v1.md`, `BACKLOG.md`.
- Sample used: `sample/creative_bundle_artifact_v1.md` for fast execution loop; `sample/council_brief_artifact_v1.md` remains artifact-first Council boundary reference.
- Implementation: added generic `_continue_cmo_loop_after_results()` primitive. After specialists return, CMO sees safe artifact summaries only, emits a synthesis reply, and may request additional allowed `RUN:` directives up to max depth 3.
- Invariants checked: no platform routing, no hardcoded module IDs, allowed-module security boundary retained, active-brand brief path retained, synthesis context excludes native artifact content.
- Tests: `docker compose exec -T -e PYTHONPATH=/app api pytest -q tests/test_cmo_artifact_boundary_prompt.py tests/test_artifact_refs.py tests/test_brand_context_isolation.py` passed 10 tests. Full suite currently hits an existing import-shape issue in `tests/test_youtube_plugin_smoke.py` (`from api.plugins...` inside `/app`).

### 2026-05-22 — Fixed sample: Facebook post + visual should not route to plan

- Bad sample: "For Klaroha, draft a Facebook post for dormant prospects and generate a matching visual direction..." produced Image Generation + Campaign Plan.
- Root cause: planning SKILL.md was too broad around campaign/launch wording and did not explicitly exclude specific execution artifacts; Meta post draft SKILL.md did not explicitly say paired Facebook post + visual requests should dispatch both post draft and image generation.
- Fix: tightened `marketing.plan.campaign_strategy` frontmatter/exclusions and expanded `marketing.channel.meta.posts.draft` activation contract. No `chat.py` routing change.
- Fixed sample target: Facebook Post Draft + Image Generation artifacts, then synthesis reply with Stream/Workspace refs only.

### 2026-05-22 — Failed specialist results must not disappear

- Bad sample: CMO step trace showed "Running Facebook Post Draft..." but no artifact appeared when execution failed.
- Root cause: `_execute_module()` persists failed Run rows before raising, but `_run_modules_streaming()` caught the exception and yielded nothing to chat/Stream.
- Fix: `_run_modules_streaming()` now looks up the latest matching failed Run and yields it as a `module_result`, so the UI can show a failed artifact/setup blocker instead of silently disappearing.
- Boundary unchanged: this does not make publishing automatic. Facebook publish still requires an explicit approved action or exact approved post text per the Meta publish SKILL.

### 2026-05-22 — Direct action payload handoff principle

- Sample: `sample/direct_action_payload_handoff_v1.md`.
- Principle: if the operator gives a clear direct external-action instruction and supplies exact text, or explicitly authorizes a low-risk text-only test, that instruction is the approval/payload source. The CMO core must preserve and pass the payload to the action module.
- Counter-principle: if BOS generates copy/image/audio/video, that generated artifact requires review before publish/send/upload unless a future sample explicitly approves an exception.
- Generic contract target: direct-action skills declare metadata such as `action_type`, `direct_action_allowed`, `payload_text_field`, and `generated_content_requires_review`. CMO core uses metadata; plugins validate and execute.
- Do not solve this with Facebook phrase branches in `chat.py`. The same action handoff pattern must work for Meta publish, Gmail send, YouTube upload, CMS publish, notifications, and future audio/video workflows.

### 2026-05-22 — Generic ACTION directive for approved artifact deployment

- Built generic `ACTION: <run_id> <action>` directive support in CMO chat.
- `_build_system_prompt()` now lists recent brand-scoped actionable artifacts from persisted block metadata (`allowed_actions` + `action_modules`).
- Chat/stream parse ACTION directives, call `execute_declared_run_action()`, surface the resulting action artifact, and synthesize after the action result.
- `execute_declared_run_action()` is the shared core primitive behind both `POST /runs/{run_id}/actions/{action}` and CMO chat ACTION execution.
- This keeps the channel-specific deploy target in plugin block metadata; CMO core only handles artifact action handoff.

---

## Invariants (must always be true)

1. **Active brand = brand-scoped everything.** When `body.brand_id` is set and resolves to a Brand row, every downstream call — brief, memory, system prompt, module dispatch — must be scoped to that brand only. No workspace fallback is allowed inside an active-brand turn.

2. **`_brand_scoped_brief()` never calls `_resolve_brief()`.** `_resolve_brief()` is workspace-only. Calling it from inside `_brand_scoped_brief()` — even as a pre-fill step — was the source of cross-brand bleed (v3.16). The only call to `_resolve_brief()` in chat.py is when `brand is None` (line 189).

3. **`hydrate_memory_slots()` must always receive `brand=active_brand`.** Without the `brand` kwarg, products, audiences, docs, and run memory are workspace-scoped, which bleeds MotorMoto facts into a Klaroha CMO turn (v3.17).

4. **Org-level prompt must not load workspace brand facts when Brand rows exist.** When `brand=None` but brands are present, the system prompt lists available brands and includes an explicit isolation rule. It must not load `ws.brand_json`, products, audiences, or documents as facts (v3.17, v3.18).

5. **Unscoped artifact dispatch is blocked.** If `triggered_modules` fires and no active brand is resolved, the response asks which brand before dispatch. Artifacts must never run with `brand_id=NULL` in a multi-brand workspace (v3.18).

6. **Brand scope is skill-owned, not hardlocked.** `workspace.scope_resolution` owns the distinction between conversation scope, execution scope, and comparison scope. Chat code may parse/validate the hidden `SCOPE:` directive, resolve Brand names to IDs, block unowned artifact runs, and pass `brand_id` into execution. Chat code must not decide cross-brand intent with phrase matching.

---

## Fixed Bugs

### v3.16 — Module dispatch used workspace-scoped brief when brand was active
**Pattern:** `_resolve_brief(db, ws)` was called in the chat dispatch path regardless of whether a brand was active. This always loads workspace-level products/audiences.
**Fix:** Chat dispatch and revise endpoint now call `_brand_scoped_brief(db, ws, active_brand, overrides)`.
**Rule:** Search for `_resolve_brief` in `chat.py`. There should be zero direct calls. Only `_brand_scoped_brief` is called from chat dispatch; `_brand_scoped_brief` internally calls `_resolve_brief` only when `brand is None`.

### v3.17 — `hydrate_memory_slots()` loaded workspace memory into active-brand turns
**Pattern:** `hydrate_memory_slots(db, ws, memory_slots)` — missing `brand=` kwarg. Products and docs were workspace-scoped, injecting MotorMoto data into a Klaroha prompt.
**Fix:** Call is now `hydrate_memory_slots(db, ws, memory_slots, brand=active_brand)`.
**Rule:** The call on line 872 must always pass `brand=active_brand`. If adding a new memory hydration call anywhere in this file, always pass the brand.

### v3.17 — `_brand_scoped_brief()` called workspace resolver before building brand brief
**Pattern:** An earlier version called `_resolve_brief()` first, then overlaid brand rows. The resolver could inject workspace product before brand rows were available.
**Fix:** `_brand_scoped_brief()` builds from overrides + Brand rows directly. No workspace resolver call when `brand` is not None.

### v3.18 — Frontend lost activeBrand on reload; backend fell back to workspace context
**Pattern:** Frontend didn't persist activeBrand to localStorage. After reload, `body.brand_id` was null. Org-level prompt loaded `ws.brand_json` (MotorMoto's context) even though Klaroha was the intended scope.
**Fix:** Frontend persists activeBrand. Backend recovers brand from named message text. Org-level prompt isolation rule added to system prompt. Artifact dispatch blocked when brand is unresolved.

---

## Do Not

- **Do not call `_resolve_brief()` directly in chat.py dispatch paths.** Only `_brand_scoped_brief()` is safe here.
- **Do not add platform-specific routing, phrase-matching, or module dispatch conditions.** No `if "facebook" in message`, no `_explicit_platforms()`. The LLM reads the capability manifest and decides.
- **Do not generate CMO reply text in deterministic code** except for provider failure and error paths. Normal chat replies must come from the LLM.
- **Do not render platform-native artifact content inline in the chat reply.** Chat returns `artifact_refs`. Workspace/Stream render the artifact.
- **Do not use `ws.brand_json`, workspace products, or workspace docs as brand facts when Brand rows exist.** Even at org level (no active brand), these must be suppressed when Brands are present.
- **Do not hardcode module IDs anywhere in this file.** All capability dispatch flows through `_chat_modules()` and the capability manifest.

---

## Fixed Bugs (continued)

### 2026-05-15 — Replaced mechanical brand hardlock with SKILL.md-owned scope resolution
**Observed:** Phrase-based switching fixed leaks but felt mechanical and still mixed conversation switching with artifact ownership.
**Root cause:** Brand scope was being inferred deterministically from message text before the CMO had a chance to decide whether the mention was a switch, comparison, or artifact owner.
**Fix:** Added `api/capabilities/workspace/scope_resolution/SKILL.md` + `NOTE.md`. CMO now emits a hidden `SCOPE:` block with `conversation_brand`, `execution_brand`, `mode`, and `confidence`. Chat code strips the block from visible replies, resolves Brand names, blocks RUNs with no `execution_brand` in multi-brand workspaces, and executes artifacts under the resolved Brand ID.
**Rule:** Do not reintroduce brand-switch phrase routing. Scope policy belongs in `workspace.scope_resolution`; code is only the safety/validation boundary.

### 2026-05-15 — Revision runs created with `brand_id=NULL`
**Observed:** Approving a revision created a Run record with `brand_id=NULL` even when a brand was active.
**Root cause:** Revise endpoint called `_execute_module(db, ws, module_id, brief, settings)` without `brand_id`. The brief had brand context but the Run row did not.
**Fix:** Revise endpoint now passes `brand_id=revise_brand.id if revise_brand else None` to `_execute_module()` (line ~1061).
**Rule:** Every `_execute_module()` call in chat.py must pass `brand_id` when a brand is active. Search all call sites before adding new ones.

---

## Backlog

- [x] BUG: Named brand in message causes unintended switch during normal conversation — fixed 2026-05-15
- [x] BUG: Revision runs get `brand_id=NULL` — fixed 2026-05-15
- [x] FEATURE: Model Brand scope as `workspace.scope_resolution` SKILL.md instead of hardlocked phrase routing — implemented 2026-05-15

---

## Architecture Direction — Pi-Pattern Target

**Insight source:** Study of [pi.dev](https://pi.dev/docs/latest) — a minimal terminal coding harness.

### Why pi doesn't face the regression problem

Pi's core loop is ~50 lines and never changes. It does one thing: receive input → build context from disk → call LLM → execute tool results → persist to session file. That loop is a fixed contract.

`chat.py` is the anti-pattern: 1,144 lines that own routing, prompt-building, brand-scoping, directive parsing, dispatch, error handling, and `@klar` command logic all in one place. Every bug fix lands there. Every fix can break the previous one.

Three specific mechanisms give pi regression immunity:

**1. State lives in the session file, not in code.**
Pi stores every turn, tool call, result, and extension state as a typed JSONL entry with `id`/`parentId`. State reconstruction is deterministic from the file — `buildSessionContext()` walks the tree from any leaf back to root. A code change cannot corrupt past session state. BOS assembles state fresh in `chat.py` on every request — brand resolution, active_brand, conversation history are all in-flight variables that can drift when logic changes.

**2. Capabilities are filesystem objects, not code branches.**
A pi skill is a `SKILL.md` file. The core loop never reads it directly — it reads the name and description at startup (progressive disclosure), then loads full content on demand. Adding, fixing, or removing a skill means editing a markdown file. The dispatch mechanism is the LLM reading the manifest, not a conditional branch in the router. BOS has SKILL.md design right, but the manifest feeds into `chat.py` which adds phrase-matching, brand re-filtering, and dispatch overrides on top.

**3. Extensions subscribe to hooks — they never touch the pipeline.**
In pi, if you want to add behavior before a tool runs, you subscribe to `before_agent_start` or `tool_call`. You don't modify the main loop. Fix an extension → edit the extension file → main loop unchanged → nothing else regresses. BOS has no hook system. A fix in brand-scoping is a diff inside `chat.py` next to the LLM call, next to the directive parser, next to the run dispatch.

### The pi-equivalent target for chat.py

The chat endpoint should be a fixed 7-step contract:

```
1. Receive message
2. Load session context  (from DB, not assembled inline)
3. Call LLM with manifest + session context
4. Strip SCOPE:/RUN: directives  (security boundary only)
5. Dispatch approved module_ids
6. Persist results to session
7. Return reply + artifact refs
```

Every line in `chat.py` that isn't one of those 7 steps belongs in a package subscribing to a hook.

### Hook model (target)

| Current location in chat.py | Target hook | Target package |
|---|---|---|
| Brand-scoping logic | `bridge.before_transform` | `workspace/scope_resolution` |
| Memory hydration | `bridge.before_transform` | `skills/memory` |
| Connector context injection | `bridge.before_transform` | `providers/connector_registry` |
| `@klar` command routing | command registry handler | `workspace/commands` |

When a fix belongs to a package instead of `chat.py`, it can only break itself — not the CMO loop, not brand-scoping, not another plugin. The goal is: `chat.py` stays at ~100 lines and never changes. Behavior changes happen in packages.

### BITE mapping of pi concepts

| Pi concept | BITE stage | BOS correct mapping |
|---|---|---|
| Session file (JSONL tree, `id`/`parentId`) | **Bridge** — input envelope | Persistent session record with typed entries linked to Run rows |
| Skill manifest (progressive disclosure) | **Bridge** — context declaration | `format_manifest_for_prompt()` called via hook, not inline in chat.py |
| SKILL.md activation | **Intent** | LLM reads manifest, outputs `RUN:`; router only security-checks |
| Extension tools (registered via hook) | **Transform** | Each plugin registers a Transform node via `bridge.before_transform` |
| `tool_result` event | **Evaluate** | Evaluate hook subscribed per capability package, not inline in chat.py |
| Session persistence (JSONL append) | **Bridge → out** | Session entry + Run row linked by session id |

### The Agentic Loop — How Pi's Simplicity Works

Pi's agent has four things: a fixed loop, three primitive tools, extensions, and skills. That's it.

**Fixed loop:**
```
receive input
→ LLM turn  (tools + skills are in context)
→ execute tool calls
→ results back to LLM
→ repeat until no more tool calls
→ persist session entry
→ return to user
```

**Three primitive tools:** `read`, `write`, `edit` (plus `bash`, `grep`, `find`, `ls`). Every capability the agent has — writing code, researching a problem, debugging — is built from combinations of these. The LLM decides how to compose them. The loop never changes to accommodate a new capability; the LLM just uses the tools differently.

**Extensions** register additional tools into the same loop and subscribe to lifecycle events. A new capability = a new tool registration. The loop is unchanged.

**Skills** are SKILL.md files loaded into context when relevant. The LLM reads them and adapts behavior. No routing logic. No conditional branches.

**Why this prevents regressions:** The loop is the same every time. You cannot break the loop by adding a new tool or skill because the loop doesn't reference them by name. You can only break the tool itself, which is isolated.

---

### How This Maps to BOS

| Pi concept | BOS current (wrong) | BOS target (right) |
|---|---|---|
| Fixed loop | 1,144-line `chat.py` with inline logic | 7-step contract, ~100 lines |
| Primitive tools (read/write/edit) | `_brand_scoped_brief()`, `hydrate_memory_slots()`, `_execute_module()` called inline | Discrete operations invoked by the pipeline at defined hook points |
| Extension tool registration | Hardcoded module dispatch in `chat.py` | Each plugin registers its Transform via `bridge.before_transform` |
| Skill context loading | `format_manifest_for_prompt()` called inline in `_build_system_prompt()` | Manifest loader invoked as a `bridge.before_transform` hook |
| Lifecycle events | None — everything is procedural in one function | `bridge.before_transform`, `transform.after_execute`, `evaluate.before`, `run.persisted` |
| Session persistence | Run stored in DB, not linked to conversation turn | Session entry + Run row linked by id; full turn reconstructible |

The key analogy: pi's `read`/`write`/`edit` are the primitives the LLM composes freely. BOS's equivalent primitives are **brief resolution**, **memory hydration**, and **module execution**. In pi, the LLM decides when to call each. In BOS, the pipeline decides — but right now all three are hardwired together inside `chat.py`'s single dispatch function instead of being composable operations the pipeline can invoke independently at the right hook point.

---

### Status

This is the target architecture, not the current state. The current `chat.py` is the POC-style monolith that pi was designed to avoid. Refactoring to this model is Phase 4+ scope — the hook system and session record layer must be defined first. Do not add new behavior to `chat.py` that belongs in a hook. When a new cross-cutting concern arises (connector context, a new memory scope, a new command), add it as a hook stub even if the full hook system isn't built yet.

---

## Fixed Bugs (continued)

### 2026-05-19 — Nginx buffered the entire SSE stream; all events arrived simultaneously
**Observed:** User saw reply text first, both artifact cards at once, zero step visibility. Curl through port 8000 (direct API) showed progressive events; curl through port 8090 (nginx) delivered a single flush.
**Root cause:** The nginx `/api/` location block had no `proxy_buffering off`. Default nginx buffers all proxy responses. `X-Accel-Buffering: no` on the FastAPI response is necessary but not sufficient — it can be overridden by a nginx-wide `proxy_buffering on` directive.
**Fix:** Added dedicated `location /api/chat/stream` block before `/api/` with `proxy_buffering off`, `proxy_cache off`, `proxy_set_header Connection ''`, `chunked_transfer_encoding on`. Also kept `X-Accel-Buffering: no` on the StreamingResponse headers (belt + suspenders).
**Rule:** Every SSE endpoint needs both: the nginx location block AND the response header. Config alone doesn't survive container restarts that pick up a stale image; header alone can be overridden by global buffering settings.

### 2026-05-19 — Step log disappeared when reply arrived; made pipeline look like old single-response pattern
**Observed:** Steps were visible during execution, then vanished the moment the reply text appeared — exactly the old mechanical pattern.
**Root cause:** The `reply` event handler did `m.filter(x => x.id !== typingId).concat([reply_msg])` — this removed the typing bubble (which was carrying the step log) entirely.
**Fix:** `reply` handler now marks the typing message as `stepsComplete: true` instead of removing it, then appends the reply as a new separate message. Typing bubble is only removed if it accumulated zero steps (plain dots case). `stepsComplete` triggers `.bos-cmo-steps-done` CSS (opacity 0.6) so the log is visible but clearly finished.
**Rule:** The step log is the agentic loop trace. It must outlive the reply. Never filter the typing bubble if it has steps. See `CmoChat.tsx` `reply` event handler.

---

## Current State (2026-05-19)

- Brand isolation for main chat dispatch: correct — `_brand_scoped_brief` + `hydrate_memory_slots(brand=active_brand)` + system prompt scoping
- Org-level isolation: correct — no workspace brand facts when Brand rows exist
- Artifact dispatch guard: correct — RUNs are blocked unless hidden `SCOPE.execution_brand` resolves to a Brand in multi-brand workspaces
- Frontend activeBrand persistence: correct — localStorage still preserves the user's working Brand
- Revise endpoint brief: correct — `_brand_scoped_brief(revise_brand)` used
- Revise endpoint run record: correct — `brand_id` now passed to `_execute_module()` in revise path (fixed 2026-05-15)
- Brand switching/comparison: correct — CMO decides via `workspace.scope_resolution` hidden `SCOPE:` block; code validates, does not phrase-route
- Streaming pipeline: correct — `POST /chat/stream` streams SSE; steps visible live with pulse animation; step log persists as completed (greyed ✓) after modules finish; artifact refs arrive before reply; reply is the final message. Nginx SSE location block + `X-Accel-Buffering: no` header both in place.
- Module dispatch: correct — `_run_modules_streaming()` is the single source of truth used by both `/chat` and `/chat/stream`; no duplicate dispatch logic
