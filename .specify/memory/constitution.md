<!--
SYNC IMPACT REPORT
==================
Version change: (none) → 1.0.0 (initial ratification)
Added sections:
  - Core Principles (I–VIII)
  - Architectural Constraints
  - Development Workflow
  - Governance
Modified principles: n/a (new)
Removed principles: n/a (new)
Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check gates now derivable from principles I–VIII
  ✅ .specify/templates/spec-template.md — no structural changes needed; scope/FR format compatible
  ✅ .specify/templates/tasks-template.md — phase structure compatible; no changes needed
Deferred TODOs: none
-->

# BOS (Business Operating System) Constitution

> This document is constitutional policy. BITE.md and this file together override all other project
> documents, backlog items, implementation shortcuts, and local conventions. If any conflict exists,
> this wins — until the human explicitly amends it.

## Core Principles

### I. Minimal Core

BOS core is a BITE harness. It is not a channel platform and not an agent framework.

Core MUST own only:
1. Capability discovery
2. Memory/resource hydration from declared contracts
3. Bridge envelope creation and persistence
4. Transform execution orchestration
5. Security, credential, and approval boundaries
6. Evaluate gates and run trace/audit persistence
7. Live capability/readiness manifest generation

Core MUST NOT own: channel behavior, platform routing, provider-specific workflow logic,
prompt examples for specific channels, MCP tool semantics, or UI assumptions scoped to one
capability. Any PR adding channel logic to `routers/chat.py`, `skills/router.py`, or
`routers/runs.py` MUST be rejected unless it introduces a generic extension point.

### II. Capability-as-Package

Every workflow-specific feature ships as a capability package — a self-contained directory.

A capability package MUST contain `SKILL.md` and `module.py`. It MAY contain `template.j2`,
`resources/`, a connector manifest, quality gates, an output contract, and a `sample/` directory.

**Canonical paths:**
- Core capabilities: `api/capabilities/{vertical}/{domain}/{task}/`
- Channel capabilities: `api/plugins/{channel}/` (ONLY — never under `api/capabilities/marketing/channel/`)

Adding or removing a capability MUST NOT require edits to `routers/chat.py`, `skills/router.py`,
`routers/runs.py`, or any other core pipeline file. If a capability requires a core edit, the
correct fix is a generic extension point, not capability-specific logic.

### III. SKILL.md as Contract

`SKILL.md` is Documentation-as-Code and the single source of truth for CMO activation behavior.

A dispatchable skill MUST declare: what it does, when to use it, when NOT to use it,
required intent class, required memory slots, and required inputs.

The CMO LLM reads the live capability manifest (generated from SKILL.md files at runtime by
`api/capability_manifest.py`) and uses its own judgment to decide dispatch. The CMO router
MUST NOT second-guess the LLM with phrase-matching, platform detection, or intent re-checking.

After the LLM outputs `RUN:` directives, the only permitted gate is: is this `module_id` in
`allowed_module_ids`? If yes — dispatch. If no — log and skip. Nothing else.

### IV. CMO Integrity

The CMO router MUST NOT contain hardcoded capability logic.

Prohibited patterns (these were removed and MUST NOT return):
- `if "facebook" in message`
- `_explicit_platforms()`
- `_is_broad_sample_ads_request()`
- Manual module ID lists
- Platform-native artifact rendering inline in chat
- Canned reply generation (except provider failure/error handling)

Deterministic code MAY: route `@klar` commands, strip hidden `RUN:` directives from visible
replies, and reject invalid module IDs. It MUST NOT generate CMO reply text in any other case.

### V. Brand Isolation

Module dispatch MUST be brand-scoped whenever an active Brand is set (`body.brand_id` present).

When a brand is active:
- Use `_brand_scoped_brief(db, ws, active_brand, overrides)` — NEVER `_resolve_brief()`
- `_brand_scoped_brief()` MUST NOT call `_resolve_brief()` first; build from overrides + Brand rows only
- `hydrate_memory_slots()` MUST receive `brand=active_brand` so products, audiences, docs,
  and run memory are filtered by `brand_id`
- Artifact dispatch MUST have a resolved `execution_brand`; `brand_id=NULL` artifacts are
  forbidden in a multi-brand workspace

When no Brand is active but Brand rows exist, CMO MUST NOT load workspace `brand_json`,
products, audiences, or documents as brand facts.

### VI. Channel Agnosticism

Creative assets are channel-agnostic Drive artifacts. Distribution is never hardwired.

A generated image or video is a Drive asset — not a Facebook post, not a YouTube video.
Creative modules MUST NOT contain channel publish logic. Channel distribution = CMO dispatches
the appropriate channel plugin with the asset reference (`drive_file_id` / `run_id`).

Available channels = installed plugins × connected brand accounts. Native channel settings
(page, ad account, playlist, recipient list) stay inside each channel plugin — never
cross-injected into creative modules.

### VII. Spec-First Workflow (Spec-Driven Development)

All new features MUST follow the SDD pipeline stages in order:

**Specify → Clarify (optional) → Plan → Tasks → Implement**

- A feature MUST NOT be implemented before its `spec.md` is written and agreed.
- A plan MUST NOT be generated before the spec is complete.
- Tasks MUST NOT be generated before the plan is complete.
- Implementation MUST NOT begin before tasks are generated.

Stage advancement is user-controlled (explicit `/speckit-*` command invocation). Agents
MUST execute each stage well when invoked; they MUST NOT skip stages on the user's behalf.

Specs live in `specs/{###-feature-name}/spec.md`. Plans, tasks, and supporting artifacts
live in the same directory. Branch naming follows spec-kit sequential numbering convention.

### VIII. Persistence Contract

All persistence MUST use PostgreSQL via SQLAlchemy 2.x async sessions and Alembic migrations.

- SQLite: FORBIDDEN anywhere in the stack
- Inline SQL strings: FORBIDDEN — use SQLAlchemy ORM or Core only
- Direct DB mutations outside Alembic: FORBIDDEN
- Schema changes without a migration: FORBIDDEN
- Provider key values in logs or API responses: FORBIDDEN — keys stored AES-256 encrypted

## Architectural Constraints

**Language & Runtime**: Python 3.11+. Type hints required on all function signatures.
FastAPI with Pydantic v2 for all request/response schemas.

**Security**: BYOK keys stored AES-256 encrypted. No key values ever logged or returned via API.
OAuth connections are per-brand, stored in `social_connections` table. Each OAuth handler
requests only scopes matching its redirect URI — never cross-scope.

**Module Execution**: Every `execute()` call is wrapped in try/except at the orchestrator level.
No exception from a module ever propagates to the orchestrator. Modules call the executor
interface only — no direct provider SDK imports inside module files.

**Frontend**: React + Vite (`web/`). Component tests required before Phase 3 is complete.
Stream artifact cards embed `ApprovalBundle` directly — `StreamRunPanel`, `onOpenPanel`, and
`requiresReview → panel` patterns are permanently removed and MUST NOT return.

**Tenancy**: One workspace per deployment. No `tenant_id` columns until SaaS tenancy phase.

**Deploy**: Never push to `staging` to trigger a deploy. Staging deploys are manual only via
`deploy-staging.sh` on the server. Local dev validation uses `localhost:8090`.

## Development Workflow

**Starting a feature:**
1. Run `/speckit-specify` — creates spec branch + `specs/{###}/spec.md`
2. Run `/speckit-clarify` (optional) — resolve ambiguities before planning
3. Run `/speckit-plan` — generates `plan.md`, `research.md`, `data-model.md`, contracts
4. Run `/speckit-tasks` — generates `tasks.md`
5. Run `/speckit-implement` — executes tasks

**Backlog protocol:**
- Read `BACKLOG.md` at session start. Mark active task `[~]` before starting, `[x]` when done.
- Add bugs to `BACKLOG.md` before fixing — never fix silently.
- Add a Decisions Log row in `BACKLOG.md` for every architectural decision.
- Run ClickUp sync after every BACKLOG.md change (idempotent, required).

**Architectural decisions:** Never make silent assumptions. Label inline: `[ASSUMING: ...]`.
All decisions logged in `BACKLOG.md` Decisions Log with date, decision, and rationale.

**New environment variables:** Document in `.env.example` the same day they're introduced.

## Governance

This constitution and `BITE.md` supersede all other project documents, README files,
BACKLOG entries, implementation habits, and stale docs. In any conflict, the constitution wins.

**Amendment procedure:**
1. Add a Decisions Log row in `BACKLOG.md` with date, decision, and rationale.
2. Run `/speckit-constitution` to produce an updated version with incremented version number.
3. MAJOR bump: backward-incompatible removal or redefinition of a principle.
4. MINOR bump: new principle or section added.
5. PATCH bump: clarification, wording, or typo fix.

**Compliance:** All PRs and implementation tasks MUST pass the Constitution Check gate in
`plan.md` before Phase 0 research. Violations require documented justification in the
Complexity Tracking table. No undocumented exceptions.

**Version**: 1.0.0 | **Ratified**: 2026-06-08 | **Last Amended**: 2026-06-08
