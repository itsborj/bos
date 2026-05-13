# BOS — Backlog

**Last updated:** 2026-05-04
**Active phase:** Phase 3 — Frontend

---

## How to Use This

- Pick the topmost `[ ]` item in the current phase and work it.
- Mark `[~]` when started, `[x]` when done.
- Move to the next phase only when all items in the current phase are `[x]`.
- Add new items at the bottom of the relevant phase. Never reorder done items.
- `[!]` = blocked — note the blocker inline.

---

## Legend

```
[ ]  Todo
[~]  In Progress
[x]  Done
[!]  Blocked (note reason)
[-]  Deferred (moved out of scope for this phase)
```

---

## Phase 0 — Foundation

**Goal:** empty repo → runnable skeleton with one endpoint and a connected database.

### Reference & Planning
- [x] POC learnings extracted from cl_dm_os
- [x] Unified project brief written (PROJECT_BRIEF.md)
- [x] System shape sample agreed (sample/bos_v1.md)
- [x] BACKLOG.md initialized
- [x] CLAUDE.md written

### Repo Structure
- [x] Create folder skeleton (api/, web/, migrations/, templates/, providers/)
- [x] .env.example with all required vars documented
- [x] .gitignore

### Docker + Infrastructure
- [x] docker-compose.yml — services: api, db (postgres:16), web, nginx
- [x] nginx.conf — proxy api:8000, web:3000
- [x] Verify `docker compose up` starts all services

### Database
- [x] PostgreSQL connection confirmed from api container
- [x] Migration tooling chosen (Alembic)
- [x] Migration 0001: workspaces table
- [x] Migration 0002: core tables (products, audiences, campaigns)
- [x] Migration 0003: provider_keys table
- [x] Migration 0004: capabilities + model_options tables
- [x] Migration 0005: runs, run_attempts, run_results, run_traces tables

### API Skeleton
- [x] FastAPI project initialized
- [x] GET / returns version + health + db status
- [x] Basic API key auth middleware (header: X-API-Key)
- [x] Error response shape standardized (code, message, details)
- [x] Request/response logging middleware

---

## Phase 1 — Core API + Data Layer

**Goal:** full workspace CRUD + mock module run stored in PostgreSQL with trace.

### Workspace
- [x] GET /workspace
- [x] PUT /workspace/brand
- [x] PUT /workspace/products (create + update)
- [x] PUT /workspace/audiences (create + update)
- [x] Workspace context auto-resolves on run (brief inherits from workspace)

### Module Registry
- [x] Module discovery via directory scan (modules/marketing/)
- [x] GET /verticals
- [x] GET /verticals/marketing/modules
- [x] GET /modules/{module_id}
- [x] First module file: marketing.ad_copy.facebook (mock)
- [x] Second module file: marketing.ad_copy.twitter (mock)
- [x] Third module file: marketing.ad_copy.google (mock)

### Capabilities
- [x] Capability profiles loaded from DB (seeded via migration)
- [x] GET /capabilities
- [x] Router: filter eligible candidates, rank by policy weights (cheap/balanced/premium)

### Runs — Mock Mode
- [x] POST /runs — triggers module, runs mock executor, stores result
- [x] Run stored in PostgreSQL with full BITE envelope
- [x] GET /runs — list with filters (module_id, status, date range)
- [x] GET /runs/{run_id} — full trace (routing decisions, attempts, result)
- [x] run_summary equivalent in run trace (which modules passed/failed)

### Auth
- [x] API key generation endpoint (POST /auth/keys)
- [x] API key validated on all protected endpoints
- [x] Keys stored hashed in PostgreSQL

---

## Phase 2 — Provider Layer + BYOK

**Goal:** real ad copy generated via OpenRouter (platform mode) and via user's own key (BYOK).

### Platform Mode — OpenRouter Adapter
- [x] Provider adapter interface defined (base class / protocol)
- [x] OpenRouter adapter implemented
- [x] Live execution wired into executor (replaces mock stub)
- [x] Response normalized to same shape as mock
- [ ] Real run: brief → OpenRouter → ad copy stored in PostgreSQL (needs PLATFORM_OPENROUTER_KEY in .env)

### BYOK
- [x] POST /providers/keys — register key (encrypted at rest, AES-256)
- [x] DELETE /providers/keys/{provider} — remove key
- [x] GET /providers/keys — list registered providers (key value never returned)
- [x] BYOK execution path in executor (uses user's key, skips platform keys)
- [x] POST /providers/check — verify key + connectivity
- [ ] Real BYOK run: user's own OpenRouter key → ad copy stored (needs real key)

### Billing
- [x] Billing ledger tables confirmed (run_attempts has provider_cost + mode)
- [x] sell_price computed (provider_cost × MARKUP) for platform mode
- [x] BYOK runs: provider_cost tracked, sell_price = null
- [x] GET /billing/summary
- [x] GET /billing/runs/{run_id}

### Additional Adapters
- [x] Gemini adapter (gemini-2.0-flash, gemini-1.5-pro) — add PLATFORM_GEMINI_KEY to .env to activate
- [x] NVIDIA adapter (llama-3.1-8b, llama-3.3-70b) — add PLATFORM_NVIDIA_KEY to .env to activate
- [-] Anthropic adapter — deferred; user routes Anthropic models via OpenRouter already

### Bug Fixes (found during Phase 2 smoke testing — 2026-05-02)
- [x] BUG: failed run `mode` always stored as "mock" — mode not passed to RunAttempt in exception block (runs.py)
- [x] BUG: POST /providers/check returns false positive — OpenRouter /models is public; swap to /auth/key endpoint (providers/openrouter.py)
- [x] BUG: GET /runs date-range filter not implemented — backlog item marked done prematurely; add created_after/created_before Query params (routers/runs.py)
- [x] BUG: POST /providers/check returns "unknown" for gemini and nvidia — _CHECK_ADAPTERS only had openrouter; added gemini and nvidia (providers/routers/providers.py)
- [x] BUG: twitter template doesn't enforce product_name in output — added must-mention instruction matching facebook template pattern (templates/marketing/twitter_ad.j2)
- [x] QUALITY: gemini-2.0-flash quality_tier upgraded to "high" (migration 008)
- [x] BUG: no fallback to next candidate on provider error — executor now tries all candidates in score order; failed attempts stored individually; falls back to mock only when no live keys exist (runs.py)
- [x] MISSING: GET /providers — returns all providers with model count, health, platform key presence, byok key presence (routers/providers.py)

---

## Phase 3 — Frontend

**Goal:** non-technical user can configure workspace + run a module + see results in browser. Same run triggerable via API.

### Pre-work (API gaps to close before building UI)
- [x] Workspace name: PUT /workspace endpoint to rename the workspace (currently hardcoded "My Workspace")
- [x] Auth bootstrap: POST /auth/bootstrap — create first API key without needing an existing key (blocks fresh-install onboarding flow)
- [x] Pagination metadata: GET /runs should return total count alongside results (needed for UI pagination controls)

### Stack Decision
- [x] Frontend framework chosen — React + Vite (decided 2026-05-02)
- [x] Document decision + rationale in CLAUDE.md
- [x] Frontend project initialized in web/
- [x] Dev server wired into docker-compose (hot reload in development)

### Pages / Views
- [x] Dashboard / home — summary: workspace name, recent runs count, billing total
- [x] Workspace setup — brand (voice, tone, values), products (name, tagline, benefits), audiences
- [x] Provider status — list from GET /providers; show which keys are active; link to register BYOK
- [x] Module browser — list modules by vertical with capability + policy info
- [x] Run a module — pick module, policy selector, brief overrides, submit; show loading state
- [x] Run result — content output, self_check badge, execution details (provider, mode, latency, cost)
- [x] Run history — filterable list (module, status, date range); click through to result

### API keys the UI needs
All endpoints require X-API-Key. The UI needs to:
- [x] Store the key in localStorage (decision: localStorage key `bos_api_key`; bootstrap screen on first visit)
- [x] Show an "unauthorized" state cleanly if key is missing or wrong (redirects to /auth; 401/403 clears key)

### UI Rebuild (wireframe → production)
Design source of truth: `sample/DON'T_USE_ui_wireframe.html` (mobile) and `sample/DONT_USE_ui_wireframe_web.html` (web).
One responsive React app: desktop (≥900px) replicates web wireframe; mobile (<900px) replicates mobile wireframe.
Color palettes stripped from wireframes; neutral/minimal colors used.

**Desktop shell — complete**
- [x] 3-column layout: sidebar (200px) + main + CMO rail (260px)
- [x] Sidebar: logo, nav (Ops/Intelligence/Workspace/History/Settings), footer with workspace name
- [x] Topbar: page title, subtitle, CTA button
- [x] CMO rail: always-visible on desktop, insight cards + textarea input
- [x] Mobile breakpoint (≤899px): sidebar/cmo-rail hidden, topbar hidden, bottom nav shown

**Mobile shell — complete**
- [x] Bottom tab nav: Stream / CMO / Workspace
- [x] Full-width main content with bottom padding for nav

**Ops screen — partial**
- [x] Live bar (run count, error count, provider cost)
- [x] Module health table (Module, Status, Last Run, Self-Check)
- [x] Recent runs list
- [ ] Module health table: add Provider·Model and Latency columns — requires RunListItem extension in API

**Intelligence screen — partial**
- [x] 4 bento tiles (Total Runs, Success Rate, Provider Cost, Avg Cost/Run)
- [x] Module performance table
- [x] Products and audiences tables (from workspace data)
- [ ] Channel performance and product comparison tables — requires campaign/ad metrics data (Phase 4)

**Workspace screen — complete**
- [x] 2-column layout: Brand + Audiences left, Products right
- [x] Inline edit forms for brand, products, audiences
- [x] "What CMO draws from here" info card

**History screen — partial**
- [x] Filter chips: All / Passed / Failed
- [x] Table: Time, Module, Vertical, Status, Self-Check, trace link
- [x] Pagination
- [ ] Table: add Provider, Tokens, Cost columns — requires RunListItem extension in API
- [ ] Table: add Campaign column — requires campaigns feature (Phase 4)

**Settings screen — partial**
- [x] Provider health cards
- [x] BYOK key management (list, add, remove)
- [x] API key display + copy
- [x] Billing summary
- [ ] Provider latency display — GET /providers must return latency_ms (requires backend: measure + cache last check latency per provider in DB)

**Stream (mobile) — complete**
- [x] Date header
- [x] Metrics summary block
- [x] Error alert block with "Tell CMO →" link
- [x] Recent run blocks
- [x] Empty state / "You're all caught up" terminus

**CMO chat (mobile) — complete**
- [x] Chat interface: CMO messages (left), user messages (right)
- [x] Quick command chips (Facebook Ad / Twitter Ad / Google Ad)
- [x] Dispatches to POST /runs via intent parsing
- [x] Link previews for run results

### Bug Fixes (found during Phase 3 build — 2026-05-02)
- [x] BUG: CmoChat.tsx link preview navigated to `/settings/history/:runId` — correct route is `/history/:runId` (CmoChat.tsx:189)
- [x] BUG: Auth connect button interfered with navigation — handleEnterKey was async (validateKey + navigate); React StrictMode double-mount caused setLoading(false) on unmounted component after navigate(); fixed by making handler synchronous: setApiKey() then navigate(), no pre-validation
- [x] BUG: Error messages showed generic fallback — client.ts parsed body.error.message directly; FastAPI wraps HTTPException detail under detail.error.message nested structure; fixed by adding extractMessage() that walks the full nesting

### Stream + Intent (from updated brief v1.1)
- [x] Intent contract storage (tables + API) — migration 009, models, CRUD, `/intents` router
- [x] Stream generation (block generators) — briefing block types, generators, builder
- [ ] Chat agent integration (thin caller using the API) — `clients/claude/` scaffold

### Testing
Deferred to Phase 4. See Phase 4 Testing section.

### Bridge Clients
Thin callers that live in `clients/` outside BOS core. No business logic inside — Intent, Transform, and Evaluate all stay in BOS.

- [-] `clients/claude/` scaffold — Python script: receives prompt, calls POST /runs, formats result
- [-] Verified: Claude-triggered run appears in run history same as web-triggered run
- [-] `clients/whatsapp/` scaffold (optional) — Node.js + Baileys: WA message → POST /runs → reply; decision to build deferred until claude/ client is validated

---

## Admin Web Dashboard

**Goal:** power-user dashboard for monitoring and managing the BOS deployment. Separate from the 3-tab mobile UI.

- [x] Route `/admin` — standalone dashboard shell (not part of the 3-tab Layout)
- [x] Overview: workspace name, billing summary (total runs, success rate, cost), provider health at a glance
- [x] Run table: full filterable run history with pagination (module, status, date range)
- [x] Workspace editor: brand, products, audiences — inline edit forms
- [x] Provider management: list providers, register/remove BYOK keys, run connectivity checks
- [x] Module browser: list all registered modules by vertical with capability + policy info

---

## Phase 4 — Marketing Vertical Complete

**Goal:** full marketing workflow against a real workspace. Brief auto-resolves from workspace context.

### Modules
- [ ] All planned marketing modules implemented with real prompt templates
- [ ] Prompt templates draw from workspace (brand voice, product name, audience)
- [ ] Per-platform self_check (char limits, must-mention, banned phrases)
- [ ] Module fan-out: run all marketing modules from one brief

### Campaigns
- [ ] Campaign model (groups runs under a named campaign)
- [ ] POST /campaigns — create campaign with brief
- [ ] POST /campaigns/{id}/run — trigger all modules
- [ ] GET /campaigns/{id} — view all runs + outputs for a campaign

### Testing
Module tests mirror the `modules/` directory structure exactly. Each test file is independent — a failure in one cannot affect another. Mocking boundary is the provider adapter, not the module and not the executor. The module runs its full logic (brief resolution, template render, self_check); only the provider HTTP call is faked.

- [ ] `api/tests/modules/marketing/test_ad_copy_facebook.py` — brief→prompt→output→self_check; provider mocked
- [ ] `api/tests/modules/marketing/test_ad_copy_twitter.py` — same pattern
- [ ] `api/tests/modules/marketing/test_ad_copy_google.py` — same pattern
- [ ] `web/src/tests/RunModule.test.tsx` — component test: form submit → POST /runs called
- [ ] `web/src/tests/RunResult.test.tsx` — component test: renders content + self_check badge
- [ ] Integration: submit run from browser, verify record appears in GET /runs
- [ ] Contract: same run via curl and via UI produces identical DB record

### Output
- [ ] Output export: copy-paste ready text per platform
- [ ] Campaign summary: which modules passed, which failed, costs

---

## Phase 5 — Hardening + Second Vertical

**Goal:** production-ready single-user deployment. Second vertical added to prove extensibility.

### Hardening
- [ ] Retry with structured feedback (BITE failure-feedback loop)
- [ ] Rate limiting (per API key)
- [ ] Cost quotas (configurable per workspace)
- [ ] Provider circuit breaker (stops routing to unhealthy provider)
- [ ] Structured logging (all runs, errors, provider calls)

### Second Vertical
- [ ] Vertical chosen (finance or hr — document decision)
- [ ] 2-3 modules implemented in new vertical
- [ ] Proves: adding a vertical = adding files, no core changes

### Deployment Docs
- [ ] One-command VPS setup documented (Ubuntu 22.04 + Docker)
- [ ] .env.example fully documented
- [ ] SSL setup via nginx + certbot documented
- [ ] Backup strategy for PostgreSQL documented

---

## Parking Lot (Deferred, Not Forgotten)

These are real but explicitly out of scope until Phase 5+:

- Multi-tenancy (SaaS mode — one deployment, many workspaces)
- Workflow chaining between modules
- Agentic orchestration inside the BOS
- A/B variant generation per module
- Fine-tuning infrastructure
- Mobile app
- Enterprise billing and reporting
- Automated provider model catalog refresh

---

## Decisions Log

Track architectural decisions here so context isn't lost between sessions.

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-01 | PostgreSQL from day one, no SQLite | Avoid migration cost; per-VPS deployment makes this feasible from the start |
| 2026-05-01 | Frontend is first-class, not a dashboard HTML file | User needs to test the product, not just the API |
| 2026-05-01 | BYOK alongside platform routing | Lowers barrier to entry; users who have their own keys shouldn't pay markup |
| 2026-05-01 | Chat agent is a client, not a BOS service | Keeps interface layer decoupled; BOS is agnostic to caller identity |
| 2026-05-01 | One workspace per deployment (no multi-tenancy yet) | Simplifies auth, data model, and deployment; SaaS tenancy is a later addition |
| 2026-05-01 | FastAPI for BOS core | Async, typed, OpenAPI generation built-in; fits the team's Python context |
| 2026-05-01 | Alembic for migrations, manual version files | Autogenerate requires a running DB; hand-written files are portable and explicit |
| 2026-05-01 | Seed capabilities + model_options in migration 004 | Capabilities are config, not user data; seeding in migration keeps the DB self-contained on first boot |
| 2026-05-01 | Module registry via directory scan (importlib) | File = module; no registry file to edit when adding modules; vertical isolation is directory-level |
| 2026-05-01 | Brief resolution: workspace fills gaps, run payload overrides | Matches the "diff not repeat yourself" thesis; brief becomes sparse for known products/audiences |
| 2026-05-01 | Mock executor generates realistic content, correct cost math | Phase 1 gate test (curl → stored run + trace) passes without a live API key |
| 2026-05-02 | OpenAICompatAdapter base class; Gemini + NVIDIA are thin subclasses | All three providers speak the same OpenAI chat completions protocol; avoids code duplication |
| 2026-05-02 | No-key fallback to mock rather than error | When no live keys exist for any candidate, run succeeds in mock mode; dev experience stays clean |
| 2026-05-02 | Candidate waterfall: try in score order, store failed attempts, succeed on first live response | Handles provider rate limits (e.g. Gemini free tier 429) without surfacing errors to the caller |
| 2026-05-02 | React + Vite for frontend; Vite dev server in Docker (node:20-alpine) | Broad ecosystem; hot reload via Docker volume mount; nginx proxies / to web:5173 with WebSocket upgrade for HMR |
| 2026-05-02 | GET /runs returns RunListResponse envelope (runs + total + limit + offset) | Pagination controls need total count; breaking change accepted since no frontend consumers yet |
| 2026-05-02 | Auth connect is synchronous: setApiKey() then navigate() with no pre-validation | Async validation + navigate() caused state update on unmounted component in React StrictMode; key validity is implicitly confirmed on first protected API call |
| 2026-05-02 | 401/403 redirects to /auth?error=1; error read from URL query param on mount | Full-page redirect clears React state; URL param carries error feedback across the redirect without sessionStorage or other side channels |
| 2026-05-02 | extractMessage() in client.ts unwraps FastAPI detail.error.message nesting | FastAPI wraps HTTPException detail as { detail: { error: { message } } }, not a flat string; all catch handlers receive a proper Error with .message set |
| 2026-05-02 | BITE layers explicitly separated: Bridge (contract), Intent (BOS orchestrates), Transform (modules execute), Evaluate (self_check gate) | BOS thinks, modules execute, bridge clients translate — no layer crosses into another's responsibility |
| 2026-05-02 | Module tests mock at the provider adapter boundary only | Module runs full logic (brief resolution, template render, self_check); only provider HTTP call is faked; ensures test covers real behaviour without external dependency |
| 2026-05-02 | Bridge clients live in clients/ outside BOS core | Intent, Transform, Evaluate all stay in BOS; a bridge that grows business logic has failed its job; adding a new bridge = new directory, zero BOS changes |
| 2026-05-02 | Evaluate layer embedded in modules for now; dedicated api/evaluate/ deferred to Phase 4 | Shared validators (char limits, must-mention, banned phrases) should not be re-implemented per module; separation deferred until module count justifies it |
| 2026-05-02 | Baileys (WhatsApp Web WebSocket, Node.js) is a valid bridge client option | No browser/Selenium required; connects to existing WhatsApp Web infrastructure; fits bridge-stays-small rule; deferred until claude/ client is validated |
| 2026-05-03 | UI rebuilt as 3-tab mobile-first shell (Stream / CMO / Workspace); admin pages nested under Settings | Aligns with agreed wireframe v0.4; admin power-user flows (run module, providers, history) remain accessible under Settings without cluttering primary 3-tab experience |
| 2026-05-04 | UI wireframe files renamed with DON'T_USE prefix; wireframes remain the design source of truth | Files renamed by user to distinguish from alternative designs; prefix does not mean "don't use" — these ARE the intended wireframes |
| 2026-05-04 | UI objective: replicate wireframes as single responsive React app; strip dark color palette, keep all structure/layout/components | User confirmed: one responsive web app; web wireframe → desktop layout; mobile wireframe → mobile layout; neutral/minimal colors only |
| 2026-05-03 | CMO tab implements intent-parse dispatch: user message → module_id → POST /runs | No dedicated /chat endpoint exists yet; parsing FB/Twitter/Google keywords covers Phase 3 scope; full LLM chat routing deferred to bridge client work in Phase 3 tail |
