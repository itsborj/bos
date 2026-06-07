# Tasks: Thin Core + SDK Plugin Architecture

**Branch**: `001-thin-core-proof` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

> Tasks already completed are marked `[x]`. Pending tasks start with `[ ]`.
> Only pending tasks need implementation. Completed tasks are recorded for traceability.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: User story this task belongs to (US1–US5)
- Exact file paths required in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: SDK package, hook registry, plugin scanner, volume mount — foundation for all stories.

- [x] T001 Create `packages/klaroha_sdk/` pip package with `pyproject.toml`, `types.py`, `channel.py`, `hooks.py`, `__init__.py` in `~/bos/packages/klaroha_sdk/`
- [x] T002 Create `api/pipeline/hooks.py` — `HookRegistry` singleton with `subscribe(event, handler)` and `async fire(event, payload)`
- [x] T003 Create `api/pipeline/system_hooks.py` — brand scope + memory hydration subscribers on `brief.before_dispatch`
- [x] T004 Add Alembic migration `api/migrations/versions/038_plugin_activations.py` — `plugin_activations` table per `data-model.md`
- [x] T005 Extend `api/plugin_loader.py` — scan `EXTERNAL_PLUGINS_DIR` first, then `api/plugins/`; check `plugin_activations` activation state; mark `source: "external" | "internal"`
- [x] T006 Update `docker-compose.yml` — `EXTERNAL_PLUGINS_PATH` volume mount to `api` service with `EXTERNAL_PLUGINS_DIR=/external_plugins` env var
- [x] T007 Fix `EXTERNAL_PLUGINS_PATH` tilde expansion bug — change default from `~/bos-plugins` to `/home/ubu/bos-plugins` in `docker-compose.yml` and `.env.example`; set absolute path in `.env`
- [x] T008 Init `~/bos-plugins/` as separate git repo on `master` branch
- [x] T009 Migrate `hello` plugin to `~/bos-plugins/hello/` with only `klaroha_sdk` imports; confirm loads as `[external]`

**Checkpoint**: Foundation complete. External plugin volume mounts. hello loads from bos-plugins. V1 ✓, V3 ✓.

---

## Phase 2: Foundational (Second Proof Plugin Ready)

**Purpose**: `gbp-completeness` committed and SKILL.md hardened — required before US2 and US4 validation.

**⚠️ CRITICAL**: US2, US3, US4 validation depends on gbp-completeness being correctly wired.

- [x] T010 Commit `gbp-completeness` to `~/bos-plugins/` repo — `cd ~/bos-plugins && git add gbp-completeness && git commit -m "add: gbp-completeness plugin v0.1.0"`
- [x] T011 Strengthen `~/bos-plugins/gbp-completeness/capabilities/marketing/intelligence/gbp/completeness_score/SKILL.md` — add `excluded_triggers` list: `google analytics`, `ga4`, `analytics report`, `traffic data`, `search console`, `search performance`, `google ads`, `paid search`, `tag manager`, `on-page seo`, `meta tags`, `schema markup`, `page speed` (per research.md Decision 11)
- [x] T012 [P] Verify `~/bos-plugins/gbp-completeness/capabilities/marketing/intelligence/gbp/completeness_score/module.py` has only `klaroha_sdk` and `httpx` imports — `grep "^from\|^import" module.py` must show zero `api.*` lines

**Checkpoint**: gbp-completeness committed, SKILL.md differentiated from GA triggers, SDK boundary confirmed.

---

## Phase 3: User Story 1 — Thin Core (Priority: P1) 🎯 MVP

**Goal**: `chat.py` under 200 lines with exactly 7 steps and zero plugin/channel/platform logic.

**Independent Test**: `wc -l ~/bos/api/routers/chat.py` → under 200. `grep -c "hello\|gmail\|google\|meta\|clickup\|tiktok\|gbp" ~/bos/api/routers/chat.py` → `0`.

- [x] T013 Validate BOS starts cleanly with empty `~/bos-plugins/` directory (V2) — confirmed: `GET /api/` returns `{"status":"ok"}` with `EXTERNAL_PLUGINS_PATH=/tmp/empty-plugins`
- [-] T014 Rewrite `api/routers/chat.py` from scratch — DEFERRED per plan.md note (A6): "not needed for validation; existing chat.py dispatches correctly." Plugin names in chat.py are in a display-name dict, not routing logic. `pipeline/context.py` and `pipeline/llm.py` must be created first as extraction targets. Schedule as a dedicated follow-on task after V5/V7 delete stability is proven.
- [-] T015 [US1] Verify `chat.py` line count — blocked on T014 (deferred)
- [-] T016 [US1] Verify zero plugin routing names in `chat.py` — blocked on T014 (deferred)
- [ ] T017 [US1] Verify `hello` dispatches via CMO — send `"run a pipeline test"` via CMO chat; confirm `pipeline_test_result` artifact appears in Stream (does NOT require chat.py rewrite)

**Checkpoint**: US1 complete. Thin core proven. Adding any new plugin to `~/bos-plugins/` requires zero edits to `api/routers/chat.py`.

---

## Phase 4: User Story 2 — SDK Boundary (Priority: P1)

**Goal**: Plugin written with only `from klaroha_sdk import ...` dispatches, produces an artifact, and completes the approval loop.

**Independent Test**: `grep -r "from api\|import api\|from config\|from db" ~/bos-plugins/` → no output. CMO dispatches `gbp-completeness` → artifact appears.

- [x] T018 [US2] Activate `gbp-completeness` plugin — formal `/activate` endpoint deferred (plugin_activations table not yet wired to manifest); GBP appears in CMO dispatchable manifest implicitly when loaded. BUG fixed: SKILL.md `requires_intent: research` rejected by SkillManifest validator — changed to `diagnostic`; GBP now confirmed in manifest.
- [x] T019 [US2] Trigger GBP via CMO chat — send `"gbp audit"` with `brand_id=Klaroha`; CMO dispatched `marketing.intelligence.gbp.completeness_score` correctly (not Google Analytics). BUG fixed: SKILL.md `requires_intent: research` → `diagnostic` (SkillManifest rejected 'research'; GBP was silently absent from manifest until fixed).
- [x] T020 [US2] Verify artifact appears — `gbp_completeness_result` block with `renderer_hint: setup_blocker`, `status: failed/partial` (GBP OAuth not connected for Klaroha brand as expected); artifact carries correct brand scoping.
- [x] T021 [US2] SDK boundary check across all bos-plugins — confirmed CLEAN: zero `api.*`, `config`, `db`, `models`, `routers`, or `skills` imports across `~/bos-plugins/`

**Checkpoint**: US2 complete. SDK boundary is structural. Plugin in separate repo cannot reach BOS internals.

---

## Phase 5: User Story 3 — Delete Stability (Priority: P1)

**Goal**: Deleting any plugin folder from `~/bos-plugins/` leaves BOS completely stable.

**Independent Test**: Delete hello → BOS starts, manifest empty, no errors. Delete gbp-completeness → hello still dispatches correctly.

- [x] T022 [US3] V5 — Delete `hello` from bos-plugins and restart: `rm -rf ~/bos-plugins/hello && docker compose restart api`; verify `GET /api/` returns `{"status":"ok"}`; verify manifest returns 0 capabilities (only gbp-completeness remains if it wasn't deleted)
- [x] T023 [US3] V5 — Restore hello: `cd ~/bos-plugins && git checkout hello`; restart api; verify hello loads again as `[external]`
- [x] T024 [US3] V7 — Delete `gbp-completeness` from bos-plugins: `rm -rf ~/bos-plugins/gbp-completeness && docker compose restart api`; verify `GET /api/` returns `{"status":"ok"}`; verify hello still dispatches `pipeline_test_result` artifact
- [x] T025 [US3] V7 — Restore gbp-completeness: `cd ~/bos-plugins && git checkout gbp-completeness`; restart api; verify both plugins load as `[external]`
- [x] T026 [US3] Verify broken plugin quarantine — create `~/bos-plugins/bad-plugin/` with invalid `channel.json`; restart api; confirm BOS starts cleanly, bad-plugin logged as warning only, hello + gbp-completeness unaffected; remove `bad-plugin/` after test

**Checkpoint**: US3 complete. Delete stability proven. Any plugin can be removed without crashing core or affecting other plugins.

---

## Phase 6: User Story 4 — GBP End-to-End (Priority: P2)

**Goal**: Full `gbp_completeness_result` artifact with `approval_bundle` renderer — CMO dispatch → artifact → Stream → Approve/Dismiss.

**Independent Test**: Connect Google Business Profile in Admin → Brands → Integrations. Send `"gbp audit"` in CMO. Confirm scored result artifact appears in Stream with field-level gap data and Approve/Dismiss controls.

- [ ] T027 [US4] Connect Google Business Profile OAuth for active brand — navigate to Admin → Brands → active brand → Integrations tab → connect Google Business Profile account; confirm `social_connections` row created for `platform: "google_business"`
- [ ] T028 [US4] Trigger full GBP completeness score — send `"how complete is my google business profile"` in CMO with GBP-connected brand active; confirm `marketing.intelligence.gbp.completeness_score` dispatched; verify `gbp_completeness_result` artifact in Stream with `score`, `rating`, `fields` data
- [ ] T029 [US4] Verify approval flow — confirm `approval_bundle` renderer shows Approve and Dismiss controls; click Dismiss; confirm artifact status updates to dismissed in Stream

**Checkpoint**: US4 complete. Full plugin lifecycle proven with real OAuth credentials and approval flow.

---

## Phase 7: User Story 5 — Live Deploy (Priority: P2)

**Goal**: hq.klaroha.com running new architecture with plugins from `~/bos-plugins/`. Stable, no regressions.

**Independent Test**: `curl https://hq.klaroha.com/api/` → `{"status":"ok"}`. Manifest shows only external plugins. CMO chat + GBP audit loop works on live system.

- [ ] T030 [US5] [P] On server: clone or pull `~/bos-plugins/` repo — `git clone <bos-plugins-remote> ~/bos-plugins` (or `git pull` if already present); confirm `hello/` and `gbp-completeness/` directories exist
- [ ] T031 [US5] [P] Verify server `.env` has `EXTERNAL_PLUGINS_PATH=/home/<user>/bos-plugins` (absolute path) — `grep EXTERNAL_PLUGINS_PATH ~/bos/.env`
- [ ] T032 [US5] Merge `001-thin-core-proof` to `main` — `git checkout main && git merge 001-thin-core-proof`
- [ ] T033 [US5] Deploy to hq.klaroha.com via existing runbook — trigger deploy; confirm `GET https://hq.klaroha.com/api/` returns `{"status":"ok"}`
- [ ] T034 [US5] V8 live verification — check server logs: confirm `Plugin loaded [external]: channel.hello` and `Plugin loaded [external]: channel.gbp-completeness`; confirm `No external plugin root found` does NOT appear
- [ ] T035 [US5] Repeat V4 on live — trigger hello via CMO chat on hq.klaroha.com; confirm `pipeline_test_result` artifact
- [ ] T036 [US5] Repeat V6 on live — trigger GBP audit via CMO chat on hq.klaroha.com; confirm `setup_blocker` or `gbp_completeness_result` artifact depending on GBP connection state

**Checkpoint**: US5 complete. Live system runs new architecture. Plugin deletion proven on server.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T037 [P] Update `~/bos-plugins/README.md` — added Known Constraints section: absolute path requirement, `requires_intent` canonical values, CMO fallback dispatch guidance
- [ ] T038 [P] Update `specs/001-thin-core-proof/plugin-dev-onboarding.md` — add volume mount absolute path requirement and CMO dispatch accuracy guidance (SKILL.md `excluded_triggers` best practices)
- [ ] T039 [P] Update `api/plugins/PLUGIN_SDK.md` — note `api/plugins/` is deprecated; direct new plugin authors to `~/bos-plugins/` and `bos-plugins/README.md`
- [ ] T040 Run full `quickstart.md` V1–V8 sequence as final proof — record pass/fail for each validation step; all must pass before marking feature complete

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)          → No dependencies — start immediately [COMPLETE]
Phase 2 (Foundational)   → Depends on Phase 1 [COMPLETE except T010–T012]
Phase 3 (US1 Thin Core)  → Depends on Phase 2 — T013 can run independently; T014 is the core rewrite
Phase 4 (US2 SDK Bound.) → Depends on Phase 2 (T010–T012) + Phase 3 (T014 preferred but not blocking)
Phase 5 (US3 Delete)     → Depends on Phase 3 + Phase 4
Phase 6 (US4 GBP E2E)   → Depends on Phase 4 (T018–T020)
Phase 7 (US5 Deploy)     → Depends on Phase 5 + Phase 6
Phase 8 (Polish)         → Depends on Phase 7
```

### User Story Dependencies

- **US1 (P1) Thin Core**: Blocked only on Phase 2 completion (T010)
- **US2 (P1) SDK Boundary**: Blocked on T010–T012 (gbp-completeness committed + SKILL.md fixed)
- **US3 (P1) Delete Stability**: Blocked on US1 + US2 (need both plugins active to test deletion)
- **US4 (P2) GBP End-to-End**: Blocked on US2 (need dispatch working) + GBP OAuth connection
- **US5 (P2) Live Deploy**: Blocked on US3 + US4 (must prove local before deploying)

### Parallel Opportunities

- T010, T011, T012 can run in parallel (separate files)
- T015, T016 can run in parallel after T014
- T030, T031 can run in parallel (server prep)
- T037, T038, T039 can all run in parallel

---

## Implementation Strategy

### MVP Scope (P1 Stories Only — US1, US2, US3)

1. Complete Phase 2 (T010–T012) — commit gbp-completeness, fix SKILL.md
2. Complete Phase 3 (T013–T017) — rewrite chat.py, verify thin core
3. Complete Phase 4 (T018–T021) — GBP dispatch, SDK boundary check
4. Complete Phase 5 (T022–T026) — delete stability proven
5. **STOP and VALIDATE**: Run quickstart V2–V7 in sequence — all must pass
6. Merge and proceed to P2 stories

### Full Proof (All Stories)

After MVP validation:
1. Phase 6: GBP end-to-end with real OAuth (if available)
2. Phase 7: Live deploy to hq.klaroha.com
3. Phase 8: Polish docs

---

## Notes

- `[x]` tasks = already implemented and verified — do not re-implement
- `[P]` tasks = safe to run in parallel (different files, no shared state)
- T014 (chat.py rewrite) is the highest-risk task — largest blast radius; test immediately after
- T013 (V2 empty dir) can be done before T014 as a quick sanity check
- Commit after each phase checkpoint using `/speckit-git-commit`
- Do not advance to Phase 7 (deploy) until Phase 5 (delete stability) is fully green
