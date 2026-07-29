# CMO v2 — Production Architecture

**Status:** Active direction, but Campaign truth notes below are superseded by `docs/campaign_v2.md` and `docs/campaign_v2_cutover_hit_list.md` when they disagree.

**Maintenance rule:** update this document before code when changing ChatV2 architecture, endpoint contracts, context injection, tool execution, artifact persistence, revision, publishing, or Stream behavior. Small bug fixes that do not change behavior may update code only.

`chat_v2.py` is the CMO agent endpoint. Its job is not to replicate
`chat.py`. Its job is to provide one stable loop that can:

1. answer clearly,
2. call native tools,
3. create persisted artifacts,
4. revise those artifacts through chat,
5. publish approved artifacts to connected channels.

Everything else is secondary.

Inspired by Smith (`~/smith`): **the loop never changes; tools and artifacts do.**

---

## Product Stance

The product is **chat-native creative operations**:

```
create artifact → review/edit through chat → save durable asset → publish to channel
```

For the first production cut, v2 should be smaller than `chat.py`, not equal to
it. We explicitly defer broad assistant features so the artifact loop can become
reliable earlier.

### Core for production

- Native chat + native tool calls
- Brand-scoped artifact creation
- Durable Drive-backed images/videos
- Artifact revision by `source_run_id` + feedback
- Approval-gated publish actions to connected channels
- Stream/non-stream endpoint parity
- Simple brand guard for multi-brand workspaces

### Deferred


- hidden text protocols
- full skill routing and memory hydration
- reference patch editing
- provider billing/cost polish
- complex cross-brand switching


---

## System Architecture

The CMO is a thin AI agent loop bounded by a goal:

```text
LOOP(Goal: Read(State): Eval(against goal): Act)
```

It reads current state — brand context, Campaign V2 prompt context, conversation history,
artifact state, tool results. It evaluates the gap against the user's goal. It
acts by either responding or calling tools. Tool results are appended to state
and the loop repeats until done, blocked, or budget exhausted.

### What the loop IS

A thin harness that:

- Reads state
- Sends state to an LLM
- Dispatches native tool calls
- Feeds tool results back into state
- Repeats until completion or block

### What the loop IS NOT

The loop never:

- Parses text directives
- Knows module-specific artifact shapes
- Branches on module IDs
- Builds revision briefs per module
- Knows provider HTTP details
- Knows how Drive, Meta, LinkedIn, YouTube, or Postcraft work
- Emits frontend command-bus events like `KlarAction`

### The hardline

The loop calls tools. It does not integrate tools.

Integration means: knowing a module ID, building a module-specific brief,
patching a module-specific field, handling a module-specific publish path, or
branching on an artifact type. That belongs outside the loop — in tools,
artifact-action primitives, or the module itself.

```python
tools = build_tools(...)
decision = call_cmo(state, provider_config, tools)
results = execute_all(decision.tool_calls, ...)
state.extend(results)
```

---

## Why v2 Exists

`chat.py` is powerful but overloaded. It combines:

- provider selection,
- prompt assembly,
- text directive parsing,
- module dispatch,
- artifact action handling,
- revision branching,
- brand switching,
- council routing,
- streaming event shaping.

v2 exists to split those concerns.

| `chat.py` behavior | v2 replacement |
|---|---|
| `RUN:` text directives | native tool calls |
| `ACTION:` text directives | artifact action tool / endpoint |
| `SCOPE:` text directives | explicit brand context + simple brand guard |
| `PATCH_REFERENCE:` text directives | deferred; later native `patch_reference` tool |
| module-specific revision router | generic `revise_artifact` primitive + module-owned revision |
| direct provider logic in router | `cmo_providers.py` |
| direct module dispatch in router | `cmo_tools.py` + `runs.py` artifact execution |
| `KlarAction` command bus | explicit boring response fields |
| council session routing | deferred |

---

## Production MVP

The production MVP is intentionally narrow:

```text
CMO v2 = chat + native tools + persisted artifacts + revision + publish
```

### Must have

1. **Provider works reliably**
   - configured provider resolution
   - streaming-first, non-streaming fallback
   - useful error when no provider is configured

2. **Tool calls are native**
   - no `RUN:` parsing
   - no `ACTION:` parsing
   - no inline param regexes

3. **Tools create real BOS artifacts**
   - tool execution must persist `Run`, `RunResult`, `RunTrace`
   - responses must expose artifact refs / run IDs
   - generated media must appear in Workspace/Stream

4. **Revision is first-class**
   - user can say “change the background” / “make this shorter” / “replace X”
   - backend binds the request to a `source_run_id`
   - module receives previous artifact state + `edit_instruction` / feedback
   - child run is persisted with lineage

5. **Publishing is approval-gated**
   - user can publish an approved/current artifact to a connected channel
   - backend executes the artifact's declared action module
   - publish result is persisted as another artifact

6. **Drive-backed assets are durable**
   - images/videos save to Google Drive when connected
   - publishing can rehydrate image/video bytes from `drive_file_id`
   - base64 is preview-only, not the durable asset identity

---

## Artifact Execution Is the Backbone

The biggest difference between a demo loop and production v2 is artifact
persistence.

Directly calling a module like this is not enough for production:

```python
attempt, result = module.execute_tool_result(brief)
```

That skips the mature BOS artifact lifecycle. Production v2 tool execution should
route through the existing run/action system, especially `_execute_module()` and
`execute_declared_run_action()` in `api/routers/runs.py`.

Those paths already handle:

- plugin active checks
- credential injection
- Drive attachment resolution
- Drive video re-download
- upstream context hydration
- `brief.before_dispatch` hooks
- `Run` / `RunAttempt` / `RunResult` / `RunTrace` persistence
- artifact block scoping
- approval status
- parent/child lineage
- memory/audit events
- `run.after_complete` hooks
- `RunResponse` output

### Rule

`cmo_tools.execute_one()` should be a thin adapter from native tool call → BOS
artifact execution, not a parallel execution engine.

---

## Revision Is Core

Revision is not a deferred feature. It is the product.

The user should be able to say:

- “make the logo bigger”
- “replace the pipes with a vase”
- “make the video faster”
- “keep everything else the same”
- “change the CTA and publish it”

v2 should not recreate the 280-line module-specific revision endpoint in
`chat.py`. Instead, revision must be generic at the router/tool layer and
specific inside modules.

### Generic revision primitive

```json
{
  "source_run_id": "...",
  "feedback": "replace the background with a lighter cream color",
  "references": []
}
```

Backend behavior:

1. Load source `Run`, `RunResult`, and `RunTrace`.
2. Read the persisted artifact block.
3. Resolve `action_modules["revise"]` from the block.
4. Build a brief from the block plus feedback.
5. Preserve source fields: `drive_file_id`, `image_data_b64`, `video_path`,
   `brand_kit`, `copy`, `template_type`, `post_format`, `storyboard_spec`, etc.
6. Pass feedback as `edit_instruction`, `revision_prompt`, or module-declared
   equivalent.
7. Call `_execute_module()` for the revision module.
8. Set `parent_run_id` to the source run.
9. Return the new artifact ref / run response.

The generic layer knows only that the artifact declares a `revise` action. The
module owns how to apply the revision.

### Postcraft example

`plugins/postcraft` already follows the desired shape:

- `postcraft.create` has an `actions` declaration.
- It accepts `edit_instruction`.
- It restores prior `brand_kit`, `copy`, `template_type`, `post_format`, and
  `vision_intake` from previous artifact data.
- It uses the previous image as edit source when available.
- It uploads the result to Drive.
- It returns an `image_asset` / `post_image` artifact with:

```json
{
  "allowed_actions": ["approve", "revise", "dismiss"],
  "action_modules": {"revise": "postcraft.create"},
  "drive_file_id": "...",
  "drive_web_view_link": "..."
}
```

That is the model to standardize.

---

## Publishing Is an Artifact Action

Publishing should not be hardcoded in chat. Publishing should use the artifact's
own declared action metadata.

### Generic action primitive

```json
{
  "source_run_id": "...",
  "action": "publish_facebook",
  "confirm": true,
  "overrides": {
    "message": "Final approved caption"
  }
}
```

Backend behavior:

```python
execute_declared_run_action(db, source_run_id, action, settings, overrides)
```

That function already:

1. Loads the source artifact block.
2. Confirms the action is in `allowed_actions`.
3. Resolves `action_modules[action]`.
4. Builds an action brief from persisted block metadata.
5. Carries source `drive_file_id`, `video_path`, image/video data, copy, caption,
   and campaign/brand scope.
6. Rehydrates Drive images/videos when needed.
7. Injects channel credentials.
8. Executes the publish module through `_execute_module()`.
9. Persists the publish result artifact.

### Channel examples

Existing channel modules already fit this pattern:

- Facebook image/copy publish: `marketing.channel.meta.posts.publish`
- Facebook video publish: `marketing.channel.meta.video.publish`
- YouTube video publish: `marketing.channel.youtube.video.publish`
- LinkedIn publish: `marketing.channel.linkedin.organic.publish`

### Postcraft publish requirement

Postcraft final image artifacts should declare publish actions when the relevant
channel plugin/connection is active, for example:

```json
{
  "allowed_actions": [
    "approve",
    "revise",
    "publish_facebook",
    "publish_instagram",
    "publish_linkedin",
    "dismiss"
  ],
  "action_modules": {
    "revise": "postcraft.create",
    "publish_facebook": "marketing.channel.meta.posts.publish",
    "publish_linkedin": "marketing.channel.linkedin.organic.publish"
  }
}
```

The CMO then calls the generic artifact action. It does not know Meta, LinkedIn,
YouTube, or Drive implementation details.

---

## Drive-Backed Media Contract

Drive is important because chat sessions and temp files are not durable.

### Images

Image artifacts should prefer:

```json
{
  "type": "image_asset",
  "drive_file_id": "...",
  "drive_web_view_link": "...",
  "asset_omitted": true
}
```

A small thumbnail may be included for preview, but the full asset should not rely
on large base64 in the artifact block.

### Videos

Video artifacts should carry:

```json
{
  "type": "video_asset",
  "video_path": "/tmp/...mp4",
  "video_url": "...",
  "drive_file_id": "...",
  "drive_web_view_link": "..."
}
```

Publishing modules should receive a valid local `video_path`; if temp storage is
stale, the backend should re-download from Drive before execution.

### Rule

`drive_file_id` is durable identity. `image_data_b64`, `video_path`, and provider
URLs are transport/cache details.

---

## Specialist Model

Every module still follows the stable execution contract:

```python
execute_tool_result(brief: dict) -> tuple[dict, dict]
```

But the router should not call it directly for production chat. `_execute_module()`
wraps it with the BOS artifact lifecycle.

### One tool per module

`postcraft_create`, `postcraft_revise`, and `postcraft_publish` as separate CMO
loop concepts is the wrong unit. The right unit is:

- one module tool for creation/revision where the module owns lifecycle, and
- generic artifact action tools for persisted actions like publish/render/revise.

Module-declared `actions` still matter because they give the LLM typed parameters
for first-pass creation and module-owned revision. Persisted artifact
`action_modules` matter because they give the backend safe, approval-gated action
execution after an artifact exists.

### Two action layers

| Layer | Purpose | Example |
|---|---|---|
| `ModuleBase.actions` | LLM-facing typed parameters for a module | `postcraft.create` accepts `headline`, `cta_text`, `edit_instruction` |
| artifact `action_modules` | persisted artifact lifecycle actions | `revise`, `publish_facebook`, `publish_youtube` |

Do not confuse them. `ModuleBase.actions` helps the LLM call a capability.
`action_modules` tells BOS how to continue from a saved artifact.

---

## File Map

```text
chat_v2.py              — loop, endpoint wiring, simple response/stream shaping
cmo_providers.py        — LLM I/O and provider fallback
cmo_tools.py            — tool registry, prompt/context assembly, tool execution adapter
runs.py                 — canonical artifact execution and declared artifact actions
capability_manifest.py  — capability catalog from SKILL.md / plugins
plugins/*               — capability-owned create/revise/publish behavior
```

### `chat_v2.py` owns

- Pydantic request/response models
- `_cmo_loop`
- endpoint wiring
- fuzzer protection
- simple brand guard
- stream event shaping

It should not own module-specific revision or publish logic.

### `cmo_tools.py` owns

- `build_tools()`
- tool schema construction from module `actions`
- built-in native tools that are not module capabilities: artifact lifecycle plus Campaign V2 primitives (`campaign_read`, `campaign_create`, `campaign_append`, `campaign_patch`, `campaign_act`)
- prompt/context assembly
- execution adapter from native tool calls to BOS artifact runs/actions and Campaign V2 writes

### `runs.py` owns

- `_execute_module()`
- `_brief_from_action_artifact()`
- `execute_declared_run_action()`
- approval state
- artifact lineage
- Drive rehydration for image/video publish

---

## Response Contract

Do not expand `KlarAction`. Remove it from the v2 mental model.

Use explicit fields instead of a command bus.

```python
class ChatV2Response(BaseModel):
    reply: str
    runs: list[RunResponse] = []
    artifact_refs: list[ArtifactRef] = []
    tool_calls: list[dict] = []
    needs_brand: bool = False
    provider: str | None = None
    model: str | None = None
    latency_ms: int = 0
    steps: int = 0
```

Streaming event types should stay boring:

- `text_delta`
- `step`
- `artifact`
- `reply`
- `done`
- `error`

No `klar_action`. No `brand_switch`. No `council_session`.

---

## Brand Scope

Keep brand behavior simple for production:

1. Explicit `brand_id` wins.
2. Single-brand workspace auto-selects that brand.
3. Multi-brand workspace with no active brand can answer general questions.
4. Multi-brand workspace with artifact creation/revision/publish intent and no
   brand must ask which brand.
5. Campaign selection is explicit for agency/multi-campaign workspaces. Auto-select
   a campaign only when the active brand has exactly one active campaign; otherwise
   ask the operator to select/name the campaign before using Campaign V2 tools.
6. Plural inventory questions are not continuation questions. If the operator asks
   "what/list/show campaigns" or similar, the CMO should call `campaign_read`
   with the appropriate scope and synthesize the answer; selected/stale
   `campaign_id` must not hijack inventory semantics. "Running" inventory means
   active campaigns only; completed campaigns are history/templates, not live
   execution context.
7. Campaign questions go through the CMO loop. `cmo_working_context@v2_campaign_view`
   is prompt-only context; current campaign truth still comes from `campaign_read`.
   If the model fails to ground itself or invents missing performance, that is a
   CMO tool/context bug, not a reason to reintroduce deterministic prose.
8. Onboarding now creates a live campaign from the imported brand profile.
   Creative execution should bind to that live campaign (or an explicitly
   selected active campaign). If no active campaign can be resolved, fix
   onboarding/campaign state instead of rendering from a parallel context.
9. Durable campaign updates use Campaign V2 tools, not legacy memory tools. When
   the operator states a durable campaign fact/correction/decision, the CMO may
   call `campaign_append`, `campaign_patch`, or `campaign_act` against the
   canonical Campaign rows.

Do not reintroduce `SCOPE:`. Do not add clever automatic cross-brand switching in
v2 MVP.

---

## Context Layer

Context is strings. The loop does not know ORM shapes.

Production MVP needs only enough context to create/edit/publish safely:

- active brand profile
- products/offers
- audience
- approved brand kit / guidelines excerpts
- selected Campaign V2 prompt context
- newest Campaign V2 rows plus supporting artifact/workflow context when needed
- capability list
- channel readiness
- actionable artifact state
- references/attachments

Campaign context is **recency-first**. The latest Campaign V2 rows are the
default truth. Older Brand Kit seed assumptions, static campaign fields, old
runs, and linked objective history are supporting context only and must not
override newer Campaign rows unless
the operator explicitly asks for history, comparison, audit trail, or why a prior
decision was made.

Skill routing and broader memory hydration can improve quality later, but they
are not a blocker for the narrow production loop.

---

## Tool Layer

### Registry

`build_tools()` reads the capability manifest and modules with
`execute_tool_result`. It should be brand/plugin aware so inactive or unavailable
capabilities are not exposed for the active brand.

Tool schemas should be native function-calling schemas. The LLM should fill typed
arguments, not produce hidden text blocks.

### Execution

`execute_one()` should handle three classes of calls:

1. **Create module artifact** — call `_execute_module()` with the module ID and
   tool args.
2. **Revise artifact** — load source run, resolve artifact `action_modules.revise`,
   call `_execute_module()` with source block + feedback.
3. **Run artifact action** — call `execute_declared_run_action()` for publish,
   render, regenerate, etc.

The loop sees only tool results. It never branches on these classes.

---

## Provider Layer

`cmo_providers.py` is an anti-corruption layer. The loop never sees HTTP.

- Input: messages, config, tools
- Output: `text`, `tool_calls`, or `error`
- Streaming-first
- Silent non-streaming fallback
- Provider swappable by config

**Streaming provider error rule — fixed 2026-06-27:** if a provider returns an HTTP error from the streaming path, do not access `e.response.text` unless the streamed response has been read. The observed failure was `Attempted to access streaming response content, without having called read().`, followed by the frontend's incomplete-stream message. `cmo_providers.py` now buffers streaming error bodies before raising and uses safe error-body previews so `/cmo_v2/chat/stream` can still emit a terminal error/reply + `done` event instead of crashing mid-stream.

**Runtime rate-limit fallback rule — 2026-06-27:** a configured CMO Brain provider can still fail at runtime with `429`. When the configured backend is not strict, `resolve_provider()` should attach usable provider fallbacks, and `call_cmo()` should retry the turn against the next configured fallback before surfacing an operator-facing rate-limit error. If all providers are rate-limited or no fallback credentials exist, return a clear rate-limit message instead of generic `Provider error (429)`.

Token/cost persistence belongs here eventually, but it is not part of the first
production cut unless needed for billing launch.

---

## Endpoint Surface

Current endpoints remain:

```text
GET  /cmo_v2/test
POST /cmo_v2/chat
POST /cmo_v2/chat/stream
```

Add or expose generic artifact continuation only if needed by the frontend/chat
contract:

```text
POST /cmo_v2/artifacts/{run_id}/revise
POST /cmo_v2/artifacts/{run_id}/actions/{action}
```

These endpoints should be thin wrappers around the same primitives used by CMO
native tools. They should not contain module-specific branches.

---

## Stance: What to Build, Defer, Eliminate

### Build for production

| Feature | Owner |
|---|---|
| Native tool loop | `chat_v2.py` |
| Persisted artifact creation | `cmo_tools.py` → `_execute_module()` |
| Generic artifact revision | `cmo_tools.py` / thin endpoint → artifact `action_modules.revise` |
| Generic artifact publish/action | `execute_declared_run_action()` |
| Drive-backed media handoff | modules + `runs.py` rehydration |
| Artifact refs in response/stream | endpoints |
| Simple brand guard | endpoint/context prep |

### Defer

| Feature | Reason |
|---|---|
| `@council` | not required for creative edit/publish MVP |
| skill routing + memory hydration | quality improvement, not core loop blocker |
| token usage logging | provider concern; can follow |
| reference patch editing | separate tool later |
| complex brand switching | avoid `KlarAction` replacement bloat |

### Eliminate permanently

| Artifact | Replacement |
|---|---|
| `RUN:` | native tool calls |
| `ACTION:` | artifact action tool / endpoint |
| `SCOPE:` | explicit brand context + guard |
| `PATCH_REFERENCE:` | future native patch tool |
| regex param parsing | typed tool args |
| `KlarAction` / `@klar` | explicit response fields |
| module-specific router revision branches | module-owned revision + generic artifact primitive |

---

## Migration From `chat.py`

`chat.py` is frozen legacy code. Do not add new product behavior there. New CMO chat behavior belongs in ChatV2.

Do not migrate by copying functions. Migrate by preserving contracts.

### Preserve

- attachment enrichment
- Drive persistence and rehydration
- `_execute_module()` artifact lifecycle
- `execute_declared_run_action()` action lifecycle
- artifact refs
- approval-gated publish behavior
- module-owned revision

### Do not preserve

- hidden text directives
- `KlarAction`
- council for MVP
- giant prompt monolith
- duplicated stream/non-stream logic
- module-specific revision branches in router

---

## Implementation Order

### Recommended Debug List — Current Migration

Debug v2 in the same order as the production contract. Do not start by adding more prompt rules.

1. **Confirm frontend routing**
   - `/cmo` must call `/api/cmo_v2/chat/stream`, not legacy `/api/chat/stream`.
   - Text streaming must render from `text_delta` events.

2. **Confirm provider routing**
   - ChatV2 must use Admin → AI Providers → CMO Brain (`cmo.main`).
   - The response footer/provider label should match the configured CMO Brain model.

3. **Confirm brand scope**
   - Explicit `brand_id` wins.
   - Single-brand workspace auto-selects.
   - Multi-brand no active brand should ask for brand before artifact creation.
   - Simple named-brand follow-up like “for Golden Gate” should resolve only when unambiguous.

4. **Confirm campaign context injection**
   - When `campaign_id` is present, compact selected-campaign prompt context may be injected before the LLM turn.
   - That prompt context is secondary; current campaign truth still comes from `campaign_read` over Campaign V2 rows.
   - The CMO should answer “where are we?” from Campaign state without re-briefing.
   - If older prompt context conflicts with newer Campaign V2 rows, the CMO should use the newer Campaign rows and mention that the campaign state changed.

5. **Confirm native tool selection**
   - “Need new image” with an active brand should call the image/post tool, not ask for generic themes.
   - The LLM should infer a first draft from brand/campaign context unless a truly required fact is missing.

6. **Make artifact execution canonical**
   - `cmo_tools.execute_one()` should route module tool calls through `_execute_module()` in `runs.py`.
   - Do not maintain a parallel Run/RunResult/RunTrace persistence path in `cmo_tools.py` except as a temporary debugging bridge.
   - Verify plugin activation, credentials, hooks, Drive, memory events, and approval status are handled by the canonical run path.

7. **Confirm Stream artifact event**
   - Tool-created artifacts must return a run/artifact ref.
   - Streaming should emit an artifact/module-result event.
   - Frontend should add the artifact to Stream immediately.

8. **Confirm attachment-to-tool handoff**
   - Attached images become `reference_images` with `vision_b64` for tools.
   - Attached JSON becomes structured spec/reference context.
   - For image edits, attached/source image can become `source_image_data_b64` instead of asking the operator to describe it again.

9. **Add generic revision**
   - Implement `revise_artifact` via source run + feedback.
   - Resolve `action_modules["revise"]` from the persisted block.
   - Call `_execute_module()` with source block + `edit_instruction` and set parent lineage.

10. **Add generic publish/action**
    - Implement `run_artifact_action` via `execute_declared_run_action()`.
    - Publishing must be approval-gated and Drive-backed.

11. **Tighten Postcraft/channel contracts**
    - Postcraft image blocks should expose `approve`, `revise`, `dismiss`, and publish actions when channels are active.
    - Prefer Drive identity (`drive_file_id`) over full base64 for durable assets.

### Phase 1 — Make v2 artifacts real

- Change `cmo_tools.execute_one()` to use `_execute_module()` for module tools. **Implemented:** module tools now route through canonical `runs.py` execution instead of a parallel `Run` / `RunResult` / `RunTrace` persistence bridge.
- Return `RunResponse` / artifact ref summaries from tool results. **Implemented:** tool results are converted from canonical `RunResponse` into compact loop state and streamable artifact refs.
- Stream artifact events from v2 endpoints. **Implemented:** v2 stream returns `module_result` artifact refs for the frontend Stream path; nginx disables buffering for `/api/cmo_v2/chat/stream`.

### Phase 2 — Add generic revision

- Add a native `revise_artifact` tool or endpoint. **Implemented as native tool.**
- Bind feedback to `source_run_id`. **Implemented.**
- Resolve `action_modules["revise"]` from the artifact block. **Implemented, gated by declared `revise` action.**
- Call `_execute_module()` and set parent lineage. **Implemented.**
- Normalize direct module revise calls back through the generic primitive. **Implemented:** if the model calls `postcraft_render` with `source_run_id` + `revision_prompt`, `cmo_tools.execute_one()` routes it through the generic revision path so source Run/RunTrace state, previous image, parent linkage, and module-specific updated fields are preserved.

### Phase 3 — Add generic publish/action

- Add a native `run_artifact_action` tool or endpoint. **Implemented as native tool.**
- Delegate to `execute_declared_run_action()`. **Implemented.**
- Support overrides for captions/titles/privacy. **Implemented via `overrides` object.**
- Ensure Drive image/video rehydration works for channel modules. **Delegated to existing `runs.py` action path.**

### Phase 4 — Tighten Postcraft/channel contracts

- Ensure Postcraft final image blocks expose publish actions when channels are active.
- Prefer `image_asset` + Drive metadata over full base64.
- Verify Facebook/Instagram/LinkedIn image publishing from Drive-backed artifacts.

### Phase 5 — Polish later

- Skill routing/memory hydration
- token usage logging
- reference patch tool
- council

---

## Smith Reference

| Smith | CMO v2 |
|---|---|
| one loop | `_cmo_loop` |
| provider boundary | `cmo_providers.py` |
| tool boundary | `cmo_tools.py` |
| external tools | BOS capabilities/plugins |
| state is a list | `state: list[dict]` |
| tool results re-enter state | `state.extend(results)` |
| core never integrates tools | CMO loop never branches on module IDs |

The graph stays simple:

```text
chat_v2 loop
  → cmo_providers for LLM I/O
  → cmo_tools for native tool dispatch
  → runs.py for persisted artifact/action execution
  → plugins own creation, revision, publishing details
```
