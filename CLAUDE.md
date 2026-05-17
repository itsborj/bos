# CLAUDE.md — BOS Project

> Agent instructions. Edit when rules change. Never edit mid-build for a single feature.

---

## What This Project Is

A ground-up rebuild of the Business Operating System (BOS). The POC lives at `~/cl_dm_os/` and is frozen — do not modify it. This directory is the production build.

Read `PROJECT_BRIEF.md` before starting any work session. Read `BACKLOG.md` to find the current phase and the next actionable task.

---

## The One Rule (from BITE SOP)

**Generate a sample output before generating a spec.**

The output is the requirement. If asked to write a PRD or architecture doc before a sample exists and has been agreed on, stop and produce the sample first.

The five stages: Discuss → Sample → Agree → Reverse-spec → Build.

Do not advance to stage 4 without explicit approval from the human on the stage 2 sample.

For CMO behavior, skill activation, plugin contracts, artifact UX, or capability manifest changes, the sample must include both allowed and forbidden outcomes. A capability question may produce a capability artifact/card, but it must not trigger unrequested tool execution. Do not "fix" auto-execution bugs by banning artifacts; fix the skill/manifest contract so the right artifact type appears at the right time.

`BITE.md` is also the BOS architecture constitution. Its policies on minimal core, package/plugin extensibility, SKILL.md ownership, live manifests, artifact taxonomy, MCP boundaries, lifecycle hooks, and command registration override conflicting implementation habits or stale docs.

---

## CMO Chat — Non-Negotiable Rules

These rules apply to `api/routers/chat.py` and `api/skills/router.py`. Violating them requires a full architectural review before merging.

**1. Never hardcode capability logic in CMO chat.**

Do not add platform-specific routing, phrase-matching rules, module dispatch conditions, or channel detection to `routers/chat.py` or `skills/router.py`. No `if "facebook" in message`, no `_explicit_platforms()`, no `_is_broad_sample_ads_request()`, no manual module ID lists. These are the patterns that were removed — do not reintroduce them.

**2. All capability activation logic lives in SKILL.md.**

Each module's `SKILL.md` declares when it should be invoked (`description`, `triggers`, `excluded_triggers`, `requires_intent`). The CMO LLM reads the capability manifest and uses its own judgment. The CMO router does not second-guess the LLM.

**3. The capability manifest is the single source of truth.**

`api/capability_manifest.py` generates the CMO's deployable capability list from installed SKILL.md files at runtime. Adding a capability = adding a plugin or capability directory with a valid SKILL.md. The CMO chat requires no changes.

**4. The only allowed gate in CMO dispatch is the security boundary.**

After the LLM outputs `RUN:` directives, the only check is: is this module_id in `allowed_module_ids` (the set of `allowed_from_chat` modules)? If yes, dispatch. If no, log and skip. No intent re-checking, no phrase re-matching, no platform re-filtering.

**5. The CMO router may not replace LLM output with canned replies.**

Deterministic code may route `@klar` commands, strip hidden `RUN:` directives from visible replies, and reject invalid module IDs. It must not generate CMO reply text except for provider failure/error handling.

**6. CMO chat may not render platform-native artifacts inline.**

Workspace Artifacts are the canonical artifact plane. Chat should return concise narrative plus artifact references/links. Native previews, approval/revision/dismissal, and system details belong in Workspace and Stream. Broad requests like "let me see samples" must not be answered with pasted Subject/Body, Headline/Description, product-card copy, targeting, budgets, or fake proof. If the artifact type is ambiguous, ask which reviewable Workspace artifact to create; if a matching capability is installed, dispatch it and let Workspace render it.

**7. Module dispatch briefs must be brand-scoped when an active Brand is set.**

When `body.brand_id` is present, `active_brand` is resolved and module execution briefs must be built with `_brand_scoped_brief(db, ws, active_brand, overrides)`, not `_resolve_brief(db, ws, overrides)`. `_resolve_brief` is always workspace-scoped — it reads `ws.name`, `ws.brand_json`, and queries `Product`/`Audience` by `workspace_id`. Using it when a brand is active causes brand context bleed (e.g., Motormoto data appearing in a Klaroha session). `_brand_scoped_brief()` must not call `_resolve_brief()` first; it must build from overrides + active Brand rows only. The same applies to the revise endpoint, which must resolve `Brand` from `original_run.brand_id` before building the execution brief. Active-brand skill memory hydration must also pass `brand=active_brand` to `hydrate_memory_slots()` so products, audiences, docs, and run memory are filtered by `brand_id`. When no Brand is active but Brand rows exist, CMO chat must not load workspace `brand_json`, products, audiences, or documents as brand facts. Brand switching/artifact ownership is governed by `workspace.scope_resolution` SKILL.md and the hidden `SCOPE:` directive; do not add phrase-based brand switching in chat.py. Artifact dispatch must have a resolved `execution_brand`; never create `brand_id=NULL` artifacts in a multi-brand workspace.

---

## How to Work in This Repo

### Starting a session
1. Read `BACKLOG.md` — find the active phase and the first `[ ]` item.
2. Mark it `[~]` before starting.
3. Work the task. Mark `[x]` when done.
4. Move to the next `[ ]` item.

### When adding tasks
- Add to the bottom of the correct phase section.
- Never reorder done items.
- If a task is deferred from scope, mark `[-]` and move it to the Parking Lot section.

### When a bug is found
- Add it to `BACKLOG.md` under the active phase **before** fixing it.
- Mark `[x]` when fixed. Never fix silently without a backlog entry.

### When making architectural decisions
- Add a row to the Decisions Log in `BACKLOG.md` with date, decision, and rationale.
- Never make a silent architectural assumption. Label inline: `[ASSUMING: ...]`

---

## Key Architectural Decisions

| Decision | What it means in code |
|---|---|
| PostgreSQL from day one | No SQLite anywhere. All persistence via SQLAlchemy + Alembic migrations. |
| BYOK + Platform routing | Executor has two paths. Keys stored AES-256 encrypted. Key values never logged or returned via API. |
| Capability = directory, not split across trees | Each capability lives in `api/capabilities/{vertical}/{domain}/{task}/` with `SKILL.md` + `module.py` + `template.j2` co-located. Discovery scans for `module.py` (modules) and `SKILL.md` (skills) — same root, one scan each. Adding a capability = one new directory. |
| Channel capabilities are plugins only | `api/capabilities/marketing/channel/` is deleted and must never be recreated. All channel Transform nodes live in `api/plugins/{channel}/`. No exceptions. |
| CMO reads a capability manifest, not hardcoded rules | `api/capability_manifest.py` generates the CMO's deployable capability list from installed SKILL.md files. The CMO LLM decides when to invoke each capability — no mechanical routing in chat.py. |
| Chat agent is a client | No agent framework inside BOS. The API is the interface. Agents call it like any other HTTP client. |
| Frontend is first-class | `web/` is React + Vite (decided 2026-05-02). Component tests required before Phase 3 is complete. |
| One workspace per deployment | No tenant_id columns yet. The workspace table has one row. SaaS tenancy is a later addition. |
| FastAPI for BOS core | Async, typed, OpenAPI spec generated automatically at `/docs`. |

---

## Directory Layout

```
cl_bos/
├── PROJECT_BRIEF.md      source of truth — read first
├── BACKLOG.md            kanban — what to work next
├── CLAUDE.md             this file
├── sample/               agreed shape samples (T2/T3 artifacts)
├── api/                  BOS core (FastAPI)
│   ├── capabilities/     unified capability tree — each dir has SKILL.md + module.py + template.j2
│   │   ├── marketing/
│   │   │   ├── channel/email/outreach/cold/     ← email outreach (copywriting)
│   │   │   ├── channel/email/outreach/sequence/
│   │   │   └── ... (seo, analytics, launch, etc.)
│   │   ├── onboarding/   brand_setup/, campaign_brand_kit/, brand_guidelines/
│   │   ├── copywriting/  copywriting_30_second_milo_frank/
│   │   ├── workspace/    cmo_context/, approval_review/, plan_mode/
│   │   └── workflows/    client_onboarding/ — checklist templates, not modules
│   ├── plugins/          channel plugins — each is a self-contained package
│   │   ├── gmail/        ← Gmail outreach draft (BYOK SMTP path)
│   │   ├── gmail-auth/   ← Gmail send + receive (OAuth per brand)
│   │   └── test_stub/    ← test harness
│   ├── capability_manifest.py   ← CMO capability registry (generated from SKILL.md)
│   ├── skills/           loader.py, router.py, memory.py
│   ├── providers/        one adapter file per provider (shared infrastructure)
│   ├── migrations/       Alembic migrations
│   └── main.py           FastAPI entry point
├── web/                  frontend (React + Vite)
├── docker-compose.yml
├── nginx.conf
└── .env.example
```

---

## Environment Variables

Document new vars in `.env.example` the same day they're introduced. Never hardcode secrets. Never log key values.

Required vars (at minimum):
```
DATABASE_URL=postgresql://bos:bos@db:5432/bos
API_SECRET_KEY=          # for signing / encryption
PLATFORM_OPENROUTER_KEY= # platform-mode provider key
ENCRYPTION_KEY=          # for BYOK key encryption at rest
```

---

## OAuth / Social Connections Architecture

Per-brand OAuth connections are stored in the `social_connections` table. Each brand can have independent accounts per platform (Gmail, Google Calendar, etc.).

**Flow:** `POST /social/connect/start` → Google consent → callback → `social_connections` row.

**Key files:**
- `api/provider_auth.py` — `GmailOAuthHandler`, `GoogleCalendarOAuthHandler` (PKCE, scopes, token refresh)
- `api/routers/social.py` — OAuth callbacks, `get_page_token()` helper for token resolution + auto-refresh
- `api/models/social.py` — `SocialConnection` model
- `api/models/provider.py` — `ProviderLoginSession` (ephemeral, deleted after callback)

**Scopes — critical constraint:** Each handler must request only scopes that match its redirect URI. Gmail scopes through a Calendar redirect URI causes Google to silently reject the authorization (returns no `code`, no `error`). Keep scopes minimal and platform-matched.

**Nginx routing:** `/social/` and `/calendar/` are proxied directly to `bos_api` (no prefix strip). OAuth callbacks must use the nginx URL (`http://localhost/social/...`) not the direct API URL (`http://localhost:8000/...`) so Google redirects land at the right host.

**Redirect URIs to register in Google Cloud Console** (add all that apply):
```
http://localhost/social/gmail/callback
http://localhost/social/google-calendar/callback
https://hq.klaroha.com/social/gmail/callback
https://hq.klaroha.com/social/google-calendar/callback
```

**After OAuth changes:** `api/` hot-reloads via Watchfiles. `web/` is a static build — run `docker compose build web && docker compose up -d web` after any frontend change.

**Connectors page** (`/admin/connectors`) — read-only overview of all connections. **Brands page** (`/admin/brands`) — per-brand connect/disconnect. Never put per-brand connect buttons on Connectors.

---

## Running the Stack

```bash
docker compose up          # start all services
docker compose up api      # api only (requires db running)

# Rebuild frontend after any web/ changes
docker compose build web && docker compose up -d web

# Migrations
cd api && alembic upgrade head

# API docs (once api is running)
open http://localhost:8000/docs
```

---

## Code Standards

- Python 3.11+. Type hints on all function signatures.
- FastAPI with Pydantic v2 models for all request/response schemas.
- SQLAlchemy 2.x with async sessions.
- Alembic for all schema changes. Never mutate the DB directly.
- No inline SQL strings. Use SQLAlchemy ORM or Core.
- Every module's `execute()` call is wrapped in try/except at the orchestrator level. No exception from a module ever propagates to the orchestrator.
- BITE envelope structure for all handoffs between system layers.
- No direct provider SDK imports in module files. Modules call the executor interface only.
- Organize capabilities by business operating function, not artifact format. Internal client onboarding is a workflow checklist under `api/capabilities/workflows/client_onboarding/`, not a module.
- Every capability is a directory: `api/capabilities/{vertical}/{domain}/{task}/`. The directory holds `SKILL.md` (Claude skill + BOS contract), `module.py` (executable Transform node), `template.j2` (Jinja2 prompt), and optional resources. Adding a capability = one new directory with these files. No registry edits needed.
- Every channel capability lives in `api/plugins/{channel}/`. Never add channel Transform nodes to `api/capabilities/marketing/channel/`.

---

## Reference

- POC (frozen, read-only reference): `~/cl_dm_os/`
- System shape sample: `./sample/bos_v1.md`
- Project brief: `./PROJECT_BRIEF.md`
