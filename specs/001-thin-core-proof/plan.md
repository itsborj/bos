# Implementation Plan: Plugin Host MVP — WordPress / VS Code Model

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08 | **Spec**: [spec.md](spec.md)

---

## Summary

Make BOS core behave like a **WordPress / VS Code style plugin host**.

**The one rule** (from `api/plugins/PLUGIN_ARCHITECTURE_RECOMMENDATION.md`):

```text
If a plugin is not installed and activated, BOS should act like it does not exist.
```

This means no CMO manifest entry, no Specialist card, no connector warning, no
readiness debt, and no RUN-able capability for uninstalled or inactive plugins.

The governing document for this feature is `api/plugins/PLUGIN_ARCHITECTURE_RECOMMENDATION.md`.
That document defines 8 deliverables (D1–D8). D1–D3 and D7 are done and verified.
D8 is implemented but requires end-to-end verification. D4, D5, and D6 are the
remaining build work.

**Explicitly out of scope for this feature** (deferred per recommendation):
- `chat.py` 7-step rewrite
- Hook subscription system
- Full migration of existing plugins (Meta, TikTok, LinkedIn, YouTube)
- Marketplace / Available UI
- Full installed-state lockfile with source hashes
- SDK ABI compatibility adapters
- Plugin-owned migrations, hot reload, subprocess sandbox

The in-process hook infrastructure (A2/A3) and `klaroha_sdk` package (A1) were
built as supporting infrastructure and are complete. They are not themselves the
deliverable — they exist to support the plugin boundary. The primary deliverable
is the WordPress/VS Code lifecycle model.

> **Decision 2026-06-08**: `gbp-completeness` replaces `gmail` as the second proof
> plugin. GBP is already written, lives in `bos-plugins/`, exercises the full OAuth
> credential path, approval_bundle renderer, and pending_review status — without
> adding SMTP send complexity. Gmail migration remains a follow-on validation step.
> See research.md Decision 9.

---

## Technical Context

**Language/Version**: Python 3.11, TypeScript (React/Vite for any Admin UI changes)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x async, Alembic, Pydantic v2,
Docker Compose (volume mount for external plugins)

**Storage**: PostgreSQL — one new table (`plugin_activations`, migration 038)

**Testing**: pytest (existing), manual quickstart validation per `quickstart.md`

**Target Platform**: Linux server (Docker Compose, same stack as current production)

**Project Type**: Architectural extraction + new Python package

**Performance Goals**: No regression on CMO chat response time. Hook fire overhead
must be < 5ms per subscriber (in-process async, no I/O in brand/memory hooks).

**Constraints**: Zero downtime on hq.klaroha.com during deploy. All existing
Gmail functionality must survive migration to `~/bos-plugins/`. `api/plugins/`
internal directories are not deleted — scanner continues to find them but marks
them as deprecated source.

**Scale/Scope**: Single operator deployment. Plugin count at launch: 2 external
(`hello`, `gmail`). All other current plugins stay in `api/plugins/` (deprecated,
not loaded externally) until migrated in a follow-on pass.

---

## Constitution Check

| Principle | Check | Status |
|-----------|-------|--------|
| I. Minimal Core | This work REMOVES logic from `chat.py` and `runs.py`. New pipeline helpers go to `api/pipeline/` (not routers). Net result: core shrinks. | ✅ Pass |
| II. Capability-as-Package | `klaroha_sdk` goes to `packages/klaroha_sdk/`. External plugins go to `~/bos-plugins/` (outside this repo). No new capabilities added to `api/capabilities/marketing/channel/`. | ✅ Pass |
| III. SKILL.md as Contract | Existing SKILL.md contract preserved unchanged. External plugins must include SKILL.md — scanner validates. | ✅ Pass |
| IV. CMO Integrity | `chat.py` rewrite removes all phrase-matching, platform detection, and canned reply logic that was accumulating. Result is strictly less routing logic. | ✅ Pass |
| V. Brand Isolation | Brand scoping moves to a hook subscriber that produces identical output to current `_brand_scoped_brief()`. Behavior preserved, location changed. | ✅ Pass |
| VI. Channel Agnosticism | No creative module changes. Distribution logic unaffected. | ✅ Pass |
| VII. Spec-First | `spec.md` agreed before this plan. | ✅ Pass |
| VIII. Persistence | New `plugin_activations` table uses SQLAlchemy ORM + Alembic migration 038. No SQLite. No inline SQL. | ✅ Pass |

---

## Project Structure

```text
~/bos/                                    ← BOS core repo (this repo)
├── api/
│   ├── routers/
│   │   └── chat.py                       REWRITTEN — 7 steps, ~150 lines
│   ├── pipeline/                          NEW directory
│   │   ├── __init__.py
│   │   ├── hooks.py                       NEW — HookRegistry
│   │   ├── system_hooks.py                NEW — brand scope + memory hydration subscribers
│   │   ├── context.py                     NEW — _load_turn_context() extracted from chat.py
│   │   └── llm.py                         NEW — _cmo_llm_call() extracted from chat.py
│   ├── plugin_loader.py                   MODIFIED — add external dir scan + activation check
│   ├── plugins/                           DEPRECATED — no new work, not deleted
│   └── migrations/versions/
│       └── 038_plugin_activations.py      NEW migration
├── packages/
│   └── klaroha_sdk/                       NEW pip package
│       ├── pyproject.toml
│       └── klaroha_sdk/
│           ├── __init__.py
│           ├── channel.py                  ChannelModule base class
│           ├── types.py                    BridgeEnvelope, RunResult, ArtifactBlock, HookPayload
│           └── hooks.py                    hook_subscriber decorator
├── docker-compose.yml                     MODIFIED — add external plugin volume mount
└── Dockerfile.api                         MODIFIED — pip install klaroha_sdk

~/bos-plugins/                             SEPARATE git repo (new)
├── README.md                              "Install: pip install klaroha-sdk"
├── hello/
│   ├── channel.json                       v2 (adds sdk_version, hook_subscriptions)
│   ├── SKILL.md
│   └── capabilities/marketing/channel/hello/pipeline_test/
│       └── module.py                      from klaroha_sdk import ChannelModule only
└── gmail/
    ├── channel.json                       v2 (adds credential_injectors)
    ├── SKILL.md
    └── capabilities/marketing/channel/gmail/outreach/draft/
        └── module.py                      from klaroha_sdk import ChannelModule only
```

---

## Complexity Tracking

No constitution violations. No complexity justification needed.

---

## Phase 0: Research Summary

All decisions resolved. See `research.md` for full rationale.

| Question | Decision |
|---|---|
| Hook system design | In-process async HookRegistry — no external dependency |
| SDK distribution | `packages/klaroha_sdk/` local pip package; PyPI later |
| External plugin loading | Docker volume mount — `EXTERNAL_PLUGINS_PATH` must be absolute path (tilde not expanded by Docker) |
| Activation persistence | PostgreSQL `plugin_activations` table (migration 038) |
| First-party hooks | `system_hooks.py` — brand scope + memory hydration as hook subscribers |
| channel.json evolution | Additive v2 fields — v1 plugins unaffected |
| chat.py rewrite boundary | 7 steps; @klar and @council parsers stay as deterministic utilities |
| runs.py scope | Only `inject_channel_credentials` call site removed; replaced with hook fire |
| Second proof plugin | `gbp-completeness` replaces `gmail` — simpler, already written, exercises OAuth + approval flow |
| CMO dispatch accuracy | Degrades on fallback models; GBP SKILL.md needs stronger `excluded_triggers` vs Google Analytics |

---

## Phase 1: Design Artifacts

All Phase 1 artifacts generated. See:
- `data-model.md` — PluginActivation entity, HookRegistry, SDK types, channel.json v2
- `contracts/hook-events.md` — all v1 hook event payload schemas
- `contracts/klaroha-sdk-api.md` — full public SDK API contract
- `quickstart.md` — 8-step validation sequence from empty to live deploy

---

## Implementation Sequence

### Stream A — BOS Core (`~/bos/`)

**A1: `packages/klaroha_sdk/`** — build SDK package
- `pyproject.toml` with `name = "klaroha-sdk"`, `version = "1.0.0"`
- `types.py` — `BridgeEnvelope`, `RunResult`, `ArtifactBlock`, `HookPayload`, `CredentialPayload`
- `channel.py` — `ChannelModule` base class with abstract `execute()`
- `hooks.py` — `hook_subscriber` decorator (stores metadata on method, read at activation)
- `__init__.py` — exports all public symbols
- Install into Dockerfile.api: `RUN pip install -e packages/klaroha_sdk`

**A2: `api/pipeline/hooks.py`** — hook registry
- `HookRegistry` class with `subscribe(event, handler)` and `async fire(event, payload)`
- Module-level singleton `hooks = HookRegistry()`
- Handlers run in registration order; exceptions are caught per-handler, logged, payload passed through

**A3: `api/pipeline/system_hooks.py`** — first-party subscribers
- `brand_scope_subscriber` — extracted from `_brand_scoped_brief()` in chat.py
  - Subscribes to `brief.before_dispatch`
  - Resolves active brand, loads brand_json, products, audiences
  - Injects into `payload.brief` identically to current behavior
- `memory_hydration_subscriber` — extracted from `hydrate_memory_slots()` call in chat.py
  - Subscribes to `brief.before_dispatch`
  - Loads declared memory slots for the active skill
  - Injects into `payload.brief`
- Both registered at app startup via `hooks.subscribe()`

**A4: `api/migrations/versions/038_plugin_activations.py`** — new table
- `plugin_activations` table per `data-model.md`
- `alembic upgrade head` in Dockerfile entrypoint (already wired)

**A5: `api/plugin_loader.py`** — extend scanner
- Add `EXTERNAL_PLUGINS_DIR` env var (default: `/external_plugins/`)
- Scan `EXTERNAL_PLUGINS_DIR` first, then `api/plugins/` (deprecated)
- Check `plugin_activations` table — skip plugins with no active row
- Mark loaded state with `source: "external" | "internal"`
- Quarantine: invalid manifest → log warning, skip, do not raise

**A6: `api/routers/chat.py`** — rewrite
- Delete file, write from scratch to ~150 lines
- 7 steps only (per research.md Decision 7)
- `@klar` and `@council` parsers kept as small inline helpers
- All brand/memory logic removed — handled by `brief.before_dispatch` hook
- `inject_channel_credentials` call removed from dispatch path — hook handles it

**A7: `api/routers/runs.py`** — targeted edit
- Remove `inject_channel_credentials(...)` call from `_execute_module()`
- Replace with `await hooks.fire("brief.before_dispatch", payload)`
- No other changes to runs.py in this phase

**A8: `docker-compose.yml`** — volume mount
- Add `~/bos-plugins:/external_plugins` volume to `api` service
- Add `EXTERNAL_PLUGINS_DIR=/external_plugins` env var

---

### Stream B — External Plugins (`~/bos-plugins/`)

**B1: Init repo**
```bash
mkdir ~/bos-plugins && cd ~/bos-plugins && git init
echo "pip install klaroha-sdk" > README.md
```

**B2: `hello` plugin — SDK proof**
- Copy structure from `api/plugins/hello/`
- Rewrite `module.py` to extend `ChannelModule` using only `from klaroha_sdk import ...`
- Update `channel.json` to v2 format (add `sdk_version: "1.0"`)
- No credentials needed — simplest possible proof

**B3: `gbp-completeness` plugin — full OAuth + approval flow proof**
- Already written and in `~/bos-plugins/gbp-completeness/` — uses only `klaroha_sdk` imports ✓
- Commit to bos-plugins repo (`git add gbp-completeness && git commit`)
- Strengthen SKILL.md `excluded_triggers` to differentiate from Google Analytics triggers
  (add: `google analytics`, `ga4`, `search console`, `on-page seo`, `google ads`, `tag manager`)
- Confirm `requires_social_connection: ["google_business"]` credential injection works via hook (host-managed OAuth path)
- Note: `requires_social_connection` is only valid for platforms the host already has an OAuth handler for. 3rd party plugins on new platforms must use `requires_platform_vars` instead — host reads env vars and injects them; plugin owns validation via its declared `connection.validate` capability.
- Prove end-to-end: CMO dispatch → `setup_blocker` artifact (no account connected) or
  full `gbp_completeness_result` with `approval_bundle` renderer when GBP is connected

**B4: `gmail` plugin — follow-on validation (post GBP)**
- Migrate from `api/plugins/gmail/` to `~/bos-plugins/gmail/`
- Rewrite `module.py` to extend `ChannelModule`, add `@hook_subscriber("brief.before_dispatch")` for credential injection
- Prove end-to-end: CMO chat → draft artifact → Stream → approve

---

### Stream C — Validation

Run `quickstart.md` V1 through V8 in sequence.
Gate to merge: V5 (delete stability) and V6 (gmail SDK-only) both pass.
Gate to deploy: V8 live deploy passes.

---

## Implementation Status (as of 2026-06-08)

### D-Deliverable Status (governing: `api/plugins/PLUGIN_ARCHITECTURE_RECOMMENDATION.md`)

| Deliverable | Status | Notes |
|---|---|---|
| D1 — External plugin root is runtime source | ✅ Done | `EXTERNAL_PLUGINS_DIR` + `KLAROHA_LOAD_INTERNAL_PLUGINS` wired; V2 confirmed (T013) |
| D2 — Installed plugins API: installed packages only | ✅ Done | `GET /plugins` from external-root scan; bundled api/plugins excluded unless flag set |
| D3 — Basic quarantine | ✅ Done | Invalid plugin reported as `status=error`; valid plugins unaffected (T026) |
| D4 — Per-brand activation (build) | ⏳ Pending | `plugin_activations` table live (migration 038); ORM model + API endpoints missing (T041–T043) |
| D5 — CMO manifest filtered by brand activation (build) | ⏳ Pending | Currently global manifest; `brand_id` filter missing (T044) |
| D6 — Specialists UI activation toggle (build/patch) | ⏳ Pending | Hardcoded platform cards present; manifest-driven render + toggle missing (T045–T046) |
| D7 — Generic credential injection only | ✅ Done | SDK boundary verified clean; zero `api.*` imports across bos-plugins (T021) |
| D8 — Generic plugin-declared OAuth | ⚠️ Verify | Partial implementation exists; end-to-end verification of new-platform flow required (T047) |

### Supporting Infrastructure Status

| Item | Status | Notes |
|---|---|---|
| `packages/klaroha_sdk/` package | ✅ Done | Installs clean; `ChannelModule`, types, hook decorator |
| `api/pipeline/hooks.py` HookRegistry | ✅ Done | In-process async; brand scope + memory hydration subscribers registered |
| `api/migrations/versions/038_plugin_activations.py` | ✅ Done | `plugin_activations` table live |
| `~/bos-plugins/hello` | ✅ Done | Loads `[external]`; SDK boundary clean |
| `~/bos-plugins/gbp-completeness` | ✅ Done | Loads `[external]`; dispatches via CMO; `setup_blocker` artifact confirmed |
| `chat.py` rewrite (A6) | ⏳ Deferred | Out of scope per recommendation; follow-on feature |
| Gmail migration to bos-plugins (B4) | ⏳ Deferred | Follow-on after D4–D6 complete |
| V2 — empty dir start | ⏳ Pending | quickstart step |
| V4 — hello dispatches via CMO | ⏳ Pending | Requires UI test |
| V8 — live deploy | ⏳ Pending | Gate: D4–D6 + V2/V4 complete |

---

## Agent Assignment

Stream A (core) and Stream B (plugins) can run in parallel once the SDK package
(A1) is complete — B2 and B3 depend on A1 being installable.

**For the validation agent on Stream B:**
- Install `klaroha_sdk` from `~/bos/packages/klaroha_sdk` (editable)
- Work only in `~/bos-plugins/`
- Write plugins with zero BOS internal imports
- The SDK contract is in `contracts/klaroha-sdk-api.md`
- The hook event payloads are in `contracts/hook-events.md`
- Validation steps are in `quickstart.md`
