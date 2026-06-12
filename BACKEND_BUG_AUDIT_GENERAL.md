# General Backend Bug Audit Task List

Date: 2026-06-11
Status: in progress
Owner: Agent A (current session, 2026-06-12) — explicitly assigned by user
Related locked workstream: `BACKEND_DEBUG_TASKLIST_CMO_MEDIA_DRIVE.md` covers CMO brain, onboarding, Drive, ByteDance media, Facebook, and YouTube publishing. Do not duplicate those fixes here.

---

## P0 — Runtime / security blockers

### 1. OpenAI live execution adapter mismatch
- **Status**: `already-fixed` · Owner: Agent A
- `api/executor.py` passes `extra_body` into every adapter.
- `api/providers/openai.py` and `api/providers/openai_codex.py` do not accept `extra_body`.
- Impact: direct OpenAI/BYOK/OAuth OpenAI runs fail before provider call.

### 2. Repo-root dependency stubs shadow real packages
- **Status**: `open` · Owner: Agent A
- Local `fastapi/`, `sqlalchemy/`, and `pydantic_settings/` can shadow installed dependencies.
- `api/main.py` expects real FastAPI symbols that local stubs do not export.
- Impact: imports from repo root can fail; local test/runtime behavior differs from Docker/CI.

### 3. Deploy can accept public/default secrets
- **Status**: `fixed` · Owner: Agent A
- `deploy-staging.sh` can copy defaults from `.env.example`.
- `API_SECRET_KEY` is accepted as a live admin key by `api/auth.py`.
- Impact: staging/prod can start with known public admin/relay secrets.

### 4. ClickUp webhook fails open when secret is absent
- **Status**: `already-fixed` · Owner: Agent A
- `api/routers/webhooks.py` only validates HMAC if a secret exists.
- Public webhook route can mutate `Run.approval_status` when no secret is configured.

### 5. Migration 039 can delete legitimate data
- **Status**: `already-fixed` · Owner: Agent A
- `_BAD_TEXT = r"[[:cntrl:]]|�"` matches normal newlines/tabs.
- Migration deletes entire rows from several user tables.
- Impact: valid multiline descriptions/briefs can be destroyed during migration.

---

## P1 — Auth, tenancy, and data isolation

### 6. Brand routes are not consistently workspace-scoped
- **Status**: `fixed` · Owner: Agent A
- `GET/PUT/DELETE /brands/{brand_id}` query by brand ID only.
- Should also verify `workspace_id == current workspace`.
- Impact: in any future multi-workspace state, cross-workspace access is possible.

### 7. Agent context/execution is not fully workspace-scoped
- **Status**: `fixed` · Owner: Agent A
- `api/routers/agent.py` loads Brand/Run by ID without checking workspace ownership in several paths.
- `agent_execute` parses `brand_id` but does not verify brand exists in current workspace before execution.

### 8. `resolve_brand()` silently ignores invalid brand IDs
- **Status**: `fixed` · Owner: Agent A
- `api/routers/brands.py` returns `None` for invalid UUIDs.
- Chat may silently fall back to no active brand instead of returning a 422.
- Impact: wrong brand context or workspace fallback can be used.

### 9. Workspace singleton model is fragile
- **Status**: `fixed` · Owner: Agent A
- `get_singleton()` returns first workspace row with no deterministic ordering.
- If more than one workspace row exists, behavior is undefined.

---

## P2 — Plugin activation / manifest / readiness

### 10. Agent capabilities endpoint ignores plugin activation
- **Status**: `open` · Owner: Agent A
- `api/routers/agent.py:get_capabilities` lists allowed chat skills without brand-aware plugin activation filtering.
- Impact: agent clients may see inactive plugin capabilities.

### 11. Per-brand plugin deactivation demotes org-wide activation
- **Status**: `fixed` · Owner: Agent A
- Deactivating one brand changes the org-wide row to inactive.
- Impact: all other brands lose plugin access unexpectedly.

### 12. Plugin connection metadata creates false `CLIENT_ID`/`CLIENT_SECRET` requirements
- **Status**: `already-fixed` · Owner: Agent A
- Lightweight connection declarations inherit generic defaults.
- Impact: UI/API can claim credentials are missing when built-in OAuth should handle them.

### 13. Legacy credential conversion can quarantine plugins
- **Status**: `already-fixed` · Owner: Agent A
- Conversion from legacy credential fields creates `CredentialSlot` objects without required `key`.

### 14. Plugin version comparison is string-based
- **Status**: `already-fixed` · Owner: Agent A
- Versions like `3.10` compare incorrectly against `3.5`.

### 15. Plugin activation endpoints do not validate brand existence before commit
- **Status**: `already-fixed` · Owner: Agent A
- Valid-but-nonexistent UUID can trigger FK commit errors.

### 16. Invalid `GET /plugins?brand_id=` falls back to global readiness
- **Status**: `already-fixed` · Owner: Agent A
- Invalid UUID is swallowed, then all connected social platforms are considered.

### 17. Multi-social-token readiness checks any token instead of all required tokens
- **Status**: `already-fixed` · Owner: Agent A
- A plugin can appear ready with only one of several required social connections.

---

## P3 — Provider/model routing

### 18. Workspace-level AI BYOK can be ignored for brand-scoped runs
- **Status**: `already-fixed` · Owner: Agent A
- `resolve_stored_provider_credential()` blocks workspace-level `api_key` fallback when `brand_id` exists.
- Impact: saved AI keys may not work for brand-scoped CMO/runs.

### 19. Provider list can misrepresent brand-scoped availability
- **Status**: `already-fixed` · Owner: Agent A
- `/providers?brand_id=...` follows brand-scope rules that can hide workspace-level AI keys.

### 20. Provider health can be stale or contradictory
- **Status**: `open` · Owner: Agent A
- Provider status combines last checks, last run attempts, platform keys, and catalog health.
- Need audit for precedence and expiry behavior.

---

## P4 — Runs, actions, artifacts

### 21. Failed tool/provider attempts can be persisted as partial/success inconsistently
- **Status**: `open` · Owner: Agent A
- Tool modules rely on block status, attempt status, and self-check.
- DB evidence (read-only inspection on `bos-db-1`, 2026-06-11): 11 runs have latest `run_attempts.status='failed'` while `runs.status` is `success` or `partial`; examples include onboarding runs marked `success` after NVIDIA 404 provider failures and media runs marked `partial` after `missing_credentials` attempts.
- Need audit for all provider/tool module result shapes and one canonical rule for `runs.status`, `run_attempts.status`, and `run_results.self_check_verdict`.

### 22. Action execution auto-approves source run
- **Status**: `open` · Owner: Agent A
- `execute_declared_run_action()` sets source run approved if action is executed.
- Good for explicit confirm, but needs audit with CMO ACTION directives and UI confirm semantics.

### 23. Action brief construction may use unsafe/default message content
- **Status**: `fixed` · Owner: Agent A
- `_brief_from_action_artifact()` falls back to full result content as `message`.
- Impact: publish actions can use artifact summary/provider text instead of approved copy if block lacks message.

### 24. Local `/tmp` artifact paths are fragile
- **Status**: `open` · Owner: Agent A
- Video/image workflows can depend on temporary files.
- Need ensure Drive reload path covers all publish/review flows.

---

## P5 — Workspace/brand CRUD correctness

### 25. Workspace product/audience PUT endpoints only upsert, never remove omitted rows
- **Status**: `fixed` · Owner: Agent A
- `PUT /workspace/products` and `PUT /workspace/audiences` append/update but do not delete rows missing from payload.
- Impact: stale products/audiences remain after user edits catalog.

### 26. Workspace product/audience legacy endpoints do not support brand_id
- **Status**: `open` · Owner: Agent A
- They create brandless rows only.
- DB evidence (read-only inspection on `bos-db-1`, 2026-06-11): workspace has 8 brands but 91/92 products, 55/58 audiences, and 76/81 workspace documents are brandless.
- Impact: multi-brand users can accidentally add workspace-level data that bleeds into fallback contexts.

### 27. Brand update does not pre-check duplicate names
- **Status**: `fixed` · Owner: Agent A
- `PUT /brands/{brand_id}` can set name to an existing brand name and rely on DB/error behavior.
- Impact: inconsistent 422/500 vs clean 409.

### 28. Delete brand may orphan or null important records
- **Status**: `open` · Owner: Agent A
- DB FK behavior sets/clears brand references depending on model.
- Need verify expected behavior for runs, docs, provider keys, social connections, plugin activations.

---

## P6 — Calendar/public endpoints

### 29. Booking creation does not validate slot is actually offered
- **Status**: `already-fixed` · Owner: Agent A
- It checks conflicts but not working hours, max-days-ahead, or generated availability.
- Impact: callers can book arbitrary non-working times.
- Debug pass 1: working-tree patch now rejects booking times outside generated availability/date window before insert; needs full calendar regression tests.

### 30. Booking endpoints have no abuse controls
- **Status**: `open` · Owner: Agent A
- Public booking route has no rate limit/captcha noted.
- Impact: spam bookings possible if slug is known.

### 31. Booking page slugs may collide or error inconsistently
- **Status**: `already-fixed` · Owner: Agent A
- DB evidence (read-only inspection on `bos-db-1`, 2026-06-11): `calendar_pages` contains duplicate active public slugs (`''` x8, `0` x6, `m¬` x5).
- `GET /calendar/availability/{slug}` uses the first matching page, while `POST /calendar/book/{slug}` uses `scalar_one_or_none()` and can 500 when duplicates exist.
- Need slug validation (`min_length`, safe pattern), a unique constraint for active/public slugs, and clean 409 handling.
- Debug pass 1: working-tree patch validates new slugs, hides invalid/fuzzer public slugs, makes public lookup deterministic, and returns 409 instead of 500 for duplicate valid slugs. Existing duplicate DB rows were not deleted.

---

## P7 — Local/CI/runtime hygiene

### 32. Local Python is 3.8 while project targets 3.11
- **Status**: `open` · Owner: Agent A
- Local `python3` collection fails on modern typing.
- Need explicit dev command/environment guard.

### 33. Compile/test attempts can fail due to root-owned `__pycache__`
- **Status**: `open` · Owner: Agent A
- `python3 -m compileall api` hit permission errors writing pycache files.
- Need cleanup/ignore strategy for local validation.

### 34. OpenAPI auth docs may miss some routes
- **Status**: `already-fixed` · Owner: Agent A
- Custom OpenAPI walks dependencies to add 401 docs.
- Need verify routes using router-level dependencies or `dependencies=[Depends(...)]` are detected.

---

## P8 — Database-derived findings from read-only inspection

### 35. Plugin lifecycle state has stale activation rows for uninstalled plugins
- **Status**: `open` · Owner: Agent A
- DB evidence: `plugin_activations` contains inactive org rows for 10 plugin IDs not present in `~/bos-plugins` (`channel.clickup`, `channel.gmail`, `channel.gmail_auth`, `channel.google_ads`, `channel.google_analytics`, `channel.google_calendar`, `channel.linkedin`, `channel.search_console`, `channel.test_stub`, `channel.tiktok`).
- Current code now treats `GET /plugins` as read-only, but existing DBs still need a safe cleanup/audit path so historical read-side activation rows do not confuse lifecycle state or Admin UX.
- Related: `api/plugins/PLUGIN_LIFECYCLE_GAPS.md` C1/C2.

### 36. Backend override identifiers are not constrained enough
- **Status**: `already-fixed` · Owner: Agent A
- DB evidence: `execution_backend_overrides` contains one non-identifier/fuzzer row with invalid `target`, `provider`, `model_id`, and `modality` values.
- `BackendOverrideIn` only requires a provider and model/tool; it does not validate provider IDs, target shape, model ID shape, modality enum, or catalog existence.
- Impact: Admin backend settings can persist garbage rows; bad rows may appear in settings responses and can break routing if their target collides with real modules.
- Debug pass 1: working-tree patch validates backend override target/provider/model/tool/modality on write and filters invalid historical rows from the settings response without deleting them.

### 37. Fuzzer cleanup migration does not cover all operator-visible tables
- **Status**: `open` · Owner: Agent A
- Migration 039 cleaned obvious garbage from brands/campaigns/calendar/objectives/council rows, but DB still contains fuzzer-created calendar slugs and a backend override row.
- Need non-destructive audit first, then targeted cleanup migrations that avoid deleting legitimate multiline text.

### 38. Provider catalog health does not match live provider failures
- **Status**: `open` · Owner: Agent A
- DB evidence: `model_options` marks NVIDIA models as `healthy`, while recent onboarding attempts failed with NVIDIA 404 responses from `https://integrate.api.nvidia.com/v1/chat/completions`.
- Impact: routing can keep selecting a catalog-healthy provider/model that the live adapter rejects.
- Need health checks to expire/degrade catalog entries based on recent live failures and/or validate model IDs against current provider catalogs.

### 39. Public calendar endpoints expose hidden fuzzer rows
- **Status**: `open` · Owner: Agent A
- Admin list filters rows with `contains_fuzzer_garbage`, but public availability/booking lookups query by slug directly.
- Impact: rows hidden from Admin can still be publicly addressable, and duplicate hidden slugs can trigger booking 500s.
- Fix with write-time validation + DB constraints; list-time filtering is not a safety boundary.
- Debug pass 1: working-tree patch applies public lookup validation/filtering; still needs DB cleanup/constraint follow-up after a non-destructive migration plan.

---

## Suggested general-agent split

### Agent 1 — Runtime/security
- Tasks: 1, 2, 3, 4, 5, 32, 33.

### Agent 2 — Auth/tenancy/data isolation
- Tasks: 6, 7, 8, 9, 27, 28.

### Agent 3 — Plugin/provider routing
- Tasks: 10–20, 35, 36, 38.

### Agent 4 — Runs/actions/artifacts
- Tasks: 21–24.

### Agent 5 — Workspace/calendar CRUD
- Tasks: 25, 26, 29, 30, 31, 34, 37, 39.
