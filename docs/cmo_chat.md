# CMO Chat Architecture

## What `chat.py` is supposed to own

From `PROJECT_BRIEF.md` (Key File Ownership table):

> `api/routers/chat.py` — **7-step pipeline only:** receive → context → LLM → strip directives → dispatch → persist → return

Target architecture (`api/routers/chat_notes.md` § Architecture Direction — Pi-Pattern Target):

> `chat.py` should be a fixed 7-step contract (~100 lines); all cross-cutting concerns (brand-scoping, memory hydration, connector context, `@klar` commands) move into packages subscribing to `bridge.before_transform` and other lifecycle hooks.

Current reality: **2,355 lines.**

SDK-008 (BACKLOG.md) confirmed the gap: line count target blocked — chat.py rewrite deferred per spec.

---

## What the thin promise looks like

Smith (`~/smith/agent.py`) is a 413-line agent built from scratch with a clean loop. The comparison exposes exactly where `chat.py` lost its shape.

**Smith's loop:**
```
for step in range(max_steps):
    call_llm(state, config, tools, on_text)
    → text → done
    → tool_calls → execute → append results → repeat
```

One function. One path. State is a flat message list.

**BOS chat.py:** 2,355 lines. The loop is split across `_generate_chat_stream` (220 lines) and `_continue_cmo_loop_after_results` (120 lines). Neither reads like a loop.

---

## The four places where BOS chat lost the thin shape

### 1. The loop is not a loop — it's a pipeline with forks

Smith has one path through the loop. No branches.

BOS: LLM call → regex parse SCOPE → regex parse RUN → regex parse ACTION → regex parse PATCH_REFERENCE → regex strip orphan params → brand guard → brief build → module dispatch → synthesis turn → loop again. Each fork is a separate function. The loop shape is invisible.

### 2. Text parsing instead of native tool calls

This is the deepest structural difference.

Smith uses OpenAI tool calls — the LLM returns structured JSON with function name and args. Zero parsing needed.

BOS invented a text protocol: `RUN: module.id`, `SCOPE: execution_brand: X`, `ACTION: uuid action`, `PATCH_REFERENCE: {...}`. Five regexes, three parsers, one orphan-param stripper — all to recover structure the LLM already knows how to emit natively. That is 260 lines of parsing that would not exist with native tool calls.

This text protocol has accumulated bugs. STRAT-BUG-001 (2026-06-11): `_ORPHAN_PARAM_BLOCK_RE` used `[^\n]+` (required 1+ chars), silently missing empty-value param lines like `video_prompt:`, leaking them into visible CMO replies. SDK-038 (2026-06-09): orphan RUN params leaked into visible reply — required adding `_ORPHAN_PARAM_BLOCK_RE` as a second-pass stripper.

### 3. Two endpoints duplicating the same logic

Smith has one `agent()` with an `on_text` callback. Pass `_print_delta` for streaming, pass `None` for library use. One path.

BOS has `/chat` and `/chat/stream`. Both contain: @council routing, brand resolution, skill routing, prompt building, directive parsing, module dispatch. The stream version calls `_generate_chat_stream`. The non-stream version duplicates most of it inline. The revision endpoint (`/chat/runs/{run_id}/revise`) is another 280 lines of module-specific branching for storyboard text vs storyboard image vs postcraft vs previs motion.

### 4. `_complete_cmo_messages` does five jobs

Smith's `call_llm` does one thing: send messages, return `{type, text|tool_calls}`.

BOS's `_complete_cmo_messages` builds a candidate list across BYOK + OAuth + platform providers, fetches live model catalogs, resolves credentials, upgrades models for plan-mode thinking, tracks token usage, and records `CmoTokenUsage` rows. 150 lines. Five jobs. None of them is "send messages and return response."

---

## Root cause (from PROJECT_BRIEF.md)

The brief names this directly:

> `chat.py` has grown past 1,000 lines despite the stated target of a fixed 7-step, ~100-line contract. Locked Rule #1 — no capability logic in CMO chat — is violated repeatedly, not through carelessness but because the structural alternative does not yet exist. Cross-cutting plugin behaviors (credential injection, brand scoping, memory hydration, directive parsing) have nowhere else to live, so each new plugin need forces a new branch into core.

Three recurring patterns trace to the absence of a hook system:

- **The `chat.py` monolith accumulation** — every new plugin that needs context in its brief or needs to react to pipeline events ends up as new logic in `chat.py` or `runs.py`. The 7-step contract target is unreachable until each of these concerns has a hook to live in instead.
- **`inject_channel_credentials()` in `runs.py` as a manually-maintained list** — grows with every new plugin that needs credentials. A hook-based credential injection would make this plugin-declared, not host-maintained.
- **Brand scoping and memory hydration hardcoded in `chat.py`** — cross-cutting concerns that belong to the pipeline, not to individual route handlers.

Smith stayed thin because it has no domain. BOS lost its shape because the chat handler became the domain.

---

## Locked architecture rules for CMO chat

These are locked and non-negotiable. Source: BACKLOG.md Locked Architecture + CLAUDE.md CMO Chat section.

| # | Rule | Violation signal |
|---|---|---|
| 1 | LLM reads `capability_manifest.py`; zero routing logic in `chat.py` | Any `if "facebook" in message`, platform-matching function, or hardcoded module ID in router files |
| 2 | Brand active → `_brand_scoped_brief()`, never `_resolve_brief()`. Must build from overrides + Brand rows only. | Cross-brand context bleed |
| 3 | `hydrate_memory_slots(brand=active_brand)` when brand is active. No workspace fallback inside active-brand turns. | Wrong brand products/docs in CMO replies |
| 4 | Brand switching via hidden `SCOPE:` directive and `workspace.scope_resolution` SKILL.md. No phrase-matching in `chat.py`. | Brand-name detection in `routers/chat.py` |
| 5 | CMO chat returns artifact refs only. No inline copy, Subject/Body, Headline/Description, budgets, targeting, or fake proof. | Inline platform-native content in CMO reply text |
| 6 | Mobile-first CMO replies: 1–4 lines, one idea per line, bullets for choices, max one question. | Long dense CMO paragraphs |
| 7 | Plugin credentials via `inject_channel_credentials()` only. Plugins read `brief["_channel_credentials"]`. Never call `get_settings()` or query DB. | Plugin `module.py` querying `social_connections` or env vars directly |
| 8 | `capability_manifest.py` is the CMO capability single source of truth. Adding a capability = add `SKILL.md` with `allowed_from_chat: true` + `module_id:`. No manifest code edits needed. | Manual edits to capability_manifest.py |
| 9 | Revise endpoint resolves Brand from `original_run.brand_id` before building execution brief. Same `_brand_scoped_brief()` path as dispatch. | Revision runs receiving workspace context |
| 10 | Artifact dispatch blocked when no Brand resolved in multi-brand workspace. Returns brand clarification instead. | `brand_id=NULL` artifact creation in multi-brand workspaces |
| 11 | Stream artifact cards are inline approval surfaces. `StreamArtifactCard` embeds `ApprovalBundle` directly. No `StreamRunPanel`. `bos:focus-artifact` injects runs into feed; does NOT call `setPanelItem` with a run. | Re-added `StreamRunPanel`; `onOpenPanel` prop; `bos:focus-artifact` opening side panel |
| 12 | Creative assets are channel-agnostic. Distribution is never hardwired. A generated image or video is a Drive artifact. Channel distribution = separate CMO dispatch. | Hardwired `allowed_actions` coupling creative type to specific channels |
| 13 | Full media generation is brand-locked. CMO brain generates all downstream provider prompts from active Brand guidelines. Every primitive and final CompositionSpec must pass brand gates before render/review. | Generic prompts without brand slots; off-brand audio/video |

**CMO copy vs. visual direction boundary (from CLAUDE.md):**

CMO **may** pass as inline RUN params: `caption`, `subject_line`, `headline`, `cta_text`, `post_copy`, `hook_text` — messaging and copy.

CMO **must not** pass: `image_prompt`, `video_prompt`, `background_color`, `aspect_ratio`, or any visual/scene/layout direction. Visual direction requires exact typed brand data (hex values, font names, logo Drive file IDs) that only exists in structured brand kit fields, not the prose excerpt the CMO reads.

---

## The two loops that must stay distinct

**CMO execution loop** — fast plan/execute/optimize steering:
- Specialists create Stream artifacts
- CMO synthesizes only after specialist results return
- Operator approves/revises/dismisses
- Memory closes the optimization loop

**Council deliberation loop** — explicit `@council <question>` invocation:
- High-stakes judgment: GTM strategy, brand redesign, quarterly budget allocation
- Deliberation runs as a live boardroom in CMO chat
- Seats backed by different LLMs; the divergence is the value
- Settled brief is the canonical output
- Lives in CMO chat, not a Stream card — chat is already a conversation

These are routed separately. `@council` hits `api/capabilities/workspace/council/` directly via `api/council.py` (core service), not through the capability manifest. `council/module.py` is a clean stub with `allowed_from_chat: false` — the CMO must not dispatch council as a capability.

---

## What a thin CMO chat would look like

The 7-step contract the brief targets:

```
receive → context → LLM → strip directives → dispatch → persist → return
```

In code, the loop should be recognizable:

```python
async def cmo_turn(message, brand, history):
    context = await build_context(brand)       # brand scaffold, skills, memory
    messages = build_messages(history, context, message)
    reply = await call_cmo(messages)            # one interface, one job
    directives = extract_directives(reply)      # one parser, typed output
    results = await dispatch(directives, brand) # executor's job
    return synthesize(reply, results)
```

Each step is a named thing. The router owns none of the domain. The loop is visible.

The path to get there is not a rewrite — it is progressive extraction of cross-cutting concerns into hook subscriptions declared in `channel.json`. First-party behaviors currently hardcoded in `chat.py` and `runs.py` (credential injection, brand scoping, memory hydration) are migration targets, each moving to a first-party system plugin that subscribes to the appropriate hook.

Natural hook fire points that map directly to the 7-step contract:

```
run.before_execute      → enrich the brief before dispatch
run.after_complete      → trigger notifications, logging, or downstream actions
brief.before_dispatch   → plugin injects its own context fields
artifact.before_persist → validate or annotate before storage
```

No implementation begins until a BITE sample of the hook contract is approved.

---

## CMO v2 Prototype — Findings (2026-06-25)

**Reference implementation:** `api/routers/chat_v2.py` — 7-step loop, native tool calls, no text protocol.  
**Test surface:** `GET /cmo_v2/test` (served inline by the API, no build step).

### What was built

A standalone endpoint (`POST /cmo_v2/chat`) that uses native LLM tool calls instead of the `RUN:` / `SCOPE:` text protocol. One tool defined: `json_imagen` — generates an image from a structured JSON spec. The CMO describes `scene`, `style`, `copy_intent`, and `aspect_ratio` as discrete typed fields; the backend assembles a prompt from those fields and calls `gpt-image-2` directly.

### What actually happened (live test)

```
Operator: "generate a product image for our summer launch"

CMO called json_imagen with:
  scene:       "A vibrant summer picnic scene featuring our latest product in use..."
  style:       "Bright and cheerful lighting, warm color tones..."
  copy_intent: "Discover our new summer collection — available now!"
  aspect_ratio: 1:1

Prompt assembled from spec:
  "[scene]. Visual style: [style]. Brand context: Klaroha. This image
   will support the message: '[copy_intent]'. Do NOT bake any text..."

Result: 2MB PNG generated via gpt-image-2. Total latency: 73s.
```

### Key findings

**1. The LLM naturally produces semantic fields, not raw prompts.**
When given a tool that accepts `scene`/`style`/`copy_intent`, GPT-4o-mini produced a scene description that reads like a creative director's brief — not a prompt string. The scene was visually specific ("vibrant summer picnic scene", "decorated tablecloths", "colorful plates"). Without the tool schema forcing the separation, that specificity would have been compressed into a single paragraph appended to a `RUN:` block.

**2. The CMO/visual boundary was preserved by the tool schema.**
The tool definition has no `image_prompt` field. The CMO could not pass visual direction as a free-text prompt; it had to use the typed fields. This enforces the Rule #8 boundary architecturally — not through system prompt instructions that can be violated.

**3. The prompt assembly layer (backend) has a clear single job.**
`_build_image_prompt_from_spec()` in `chat_v2.py` is 20 lines. It takes the structured spec and assembles a generation prompt. This is separable from the LLM turn — it can be improved, extended with brand kit fields, or replaced without touching the CMO loop.

**4. The loop shape is visible.**
The `cmo_v2_chat` function is the full loop: receive → context → LLM with tools → extract tool uses → execute → synthesis → return. Each step is named. No forked regex parsers. The synthesis turn fires once after all tool results are collected, mirroring what Smith does.

**5. Two LLM calls for one tool use.**
Turn 1: CMO reasons and calls `json_imagen`. Turn 2: CMO synthesizes after seeing the result summary. This is 2 calls vs 1 in the text protocol. The tradeoff: the synthesis turn gives the CMO a chance to narrate the result ("Here's your summer image"), comment on the spec choice, or ask a follow-up. In practice the synthesis reply is minimal ("Image generated.") — suggesting the synthesis turn may only be needed when the tool result contains information the CMO needs to relay (e.g. failures, multi-image choices).

**6. Provider resolution works cleanly.**
The v2 loop tries Anthropic → OpenAI → OpenRouter in priority order. When OpenRouter had no credits (402), it fell through to OpenAI transparently. The old `_complete_cmo_messages` in `chat.py` does the same but across 150 lines; v2 does it in 25 lines because provider candidates are typed tuples, not a candidate list built across 5 accumulation passes.

**7. The image generation path surfaced an activation gap.**
When `media.image.generate` isn't in the active plugin set, the v2 loop fell back to a direct `gpt-image-2` call using the platform key. This worked. The finding: for primitive generators (image, video), the plugin activation check is a useful gate for production but an obstacle for test iteration. The v2 architecture separates these: Path A uses the registered module; Path B calls the provider directly. This dual-path pattern is worth carrying into the full CMO v2 design.

### What this tells us about the rebuild plan

**The text protocol's only advantage is backward compatibility** — all existing artifacts, frontend cards, and persisted runs assume the `RUN:` / `ACTION:` / `SCOPE:` directives. A native tool call rebuild is a clean break, not an in-place refactor.

**The `revise_artifact(run_id, feedback)` tool is the critical missing piece** — not identified in the v2 prototype because we only tested image generation. But the same architecture that makes `json_imagen` work as a tool makes `revise_artifact` possible: the CMO receives `_actionable_artifacts_context`, sees pending run IDs, and calls `revise_artifact(run_id="...", feedback="make scene 2 golden hour")`. The backend routes to the same module-specific revision logic as `chat_revise_run`. This closes the chat-native editing gap identified in the previs motion workflow analysis.

**The synthesis turn needs a decision rule.** Currently it always fires when tools were called. It should fire only when: (a) the tool result failed and the CMO needs to explain, (b) the operator's message was a question that the tool result answers, or (c) multiple tools ran and their results need to be narrated together. Silent success cases ("image generated, here it is") do not need a synthesis turn — the frontend can show the image directly from the `tool_calls` response field.

### Remaining unknowns for the full rebuild

- How does the `SCOPE:` brand-switching directive map to a tool call? `switch_scope(brand_id)` is the obvious answer but needs to be tested with multi-brand workspaces.
- Does the two-call pattern (tool use + synthesis) cause latency problems at scale? The first call (CMO reasoning + tool use) is fast (~3–5s). The synthesis call adds another ~3s. The image generation dominates at 60–70s, so synthesis latency is noise for image workflows. For pure-text capability dispatches (strategy, email) where the module result returns in <1s, the synthesis call would be noticeable.
- The `PATCH_REFERENCE:` directive has no tool equivalent yet — it mutates attachment context inline. This needs a `patch_reference(reference_id, field, value)` tool definition before chat-native attachment editing works.

### Files

- `api/routers/chat_v2.py` — prototype implementation (do not merge to production)
- `docs/cmo_chat.md` — this file (findings accumulated here)
