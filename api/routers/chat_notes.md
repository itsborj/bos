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

## Current State (2026-05-15)

- Brand isolation for main chat dispatch: correct — `_brand_scoped_brief` + `hydrate_memory_slots(brand=active_brand)` + system prompt scoping
- Org-level isolation: correct — no workspace brand facts when Brand rows exist
- Artifact dispatch guard: correct — RUNs are blocked unless hidden `SCOPE.execution_brand` resolves to a Brand in multi-brand workspaces
- Frontend activeBrand persistence: correct — localStorage still preserves the user's working Brand
- Revise endpoint brief: correct — `_brand_scoped_brief(revise_brand)` used
- Revise endpoint run record: correct — `brand_id` now passed to `_execute_module()` in revise path (fixed 2026-05-15)
- Brand switching/comparison: correct — CMO decides via `workspace.scope_resolution` hidden `SCOPE:` block; code validates, does not phrase-route
