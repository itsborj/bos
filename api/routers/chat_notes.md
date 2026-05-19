# chat.py — Dev Notes

Covers: `api/routers/chat.py`
Related: `api/skills/memory.py`, `api/routers/brands.py`, `api/routers/runs.py`

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
