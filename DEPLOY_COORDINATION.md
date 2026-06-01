# DEPLOY_COORDINATION.md

> Active execution tracker for deploy product work and AI handoff.
> `DEPLOY.md` is the durable runbook and incident log — update it for any confirmed finding.
> `DEPLOY_TODO.md` is the prioritized task list — this file has the detailed specs.

---

## The Frame

Every staging incident that required manual SSH to fix is a **first-boot init failure in disguise**. But there is a second, equally important gap: **there is currently no way to tell whether staging behavior matches localhost behavior** — for any feature, at any time.

Localhost and staging diverge at three layers:

| Layer | Question | Current state |
|---|---|---|
| **Code** | Is the same commit running? | `git_sha` in health endpoint — solved |
| **State** | Is the same data present? (brands, docs, providers, objectives) | **No mechanism** — staging DB is always emptier than localhost after any recovery |
| **Behavior** | Does the same prompt/feature produce the same output? | **No mechanism** — nothing compares CMO dispatch, media runs, or artifact output across envs |

The current plan addresses only the code layer. Behavioral parity failures look like bugs to agents and developers because there is no signal distinguishing "the code is different" from "the state is different" from "the behavior is different."

First-boot init fixes fresh deploys. It does not fix the accumulated state gap: localhost has months of brands, documents, provider keys, and objectives that staging loses on every recovery. That state difference produces different behavior even when the code is identical.

**The work has two parts:**
1. Build the product so it self-configures correctly (Track F)
2. Build the feedback loop so agents and developers can verify behavioral parity after any deploy (Track P — Parity)

**Working order:** Track F (product build) → Track P (parity feedback) → Track I (internal ops, only as needed). Never let Track I block Track F or Track P.

---

## Scale Rules (read before working any item)

| Rule | What it means for every task |
|---|---|
| No per-org SSH | A fix requiring SSH into a customer server is a product gap, not a closed issue |
| No Klaroha data access | Operators must self-diagnose from admin UI or health endpoint |
| Zero-touch new org deploys | Every manual post-boot step must become automated first-boot behavior |
| Operator-resolvable | Org admin resolves via admin panel or one documented command |
| Automated verification | Health, migration status, version, env validity — all machine-readable |

Full directive: `DEPLOY.md §Scale Directive`

---

## Quick Start for the Next AI

1. Read `DEPLOY_TODO.md` — find the first open item in Priority 1
2. Read `DEPLOY.md §Scale Directive` — frame every decision against 10K orgs
3. Read `PROJECT_BRIEF.md §10` — production model and build order
4. Key files for Priority 1 (first-boot init):
   - `api/main.py` — startup sequence
   - `api/config.py` — settings and env validation
   - `docker-compose.yml` + `docker-compose.override.yml`
   - `.env.example` — env var inventory

Do not start Track I items until Priority 1 (F1) is underway. Track I is temporary scaffolding.

---

## Item Template

```md
## F<n>/I<n> — <title>
- Status: open | in_progress | done | blocked
- Owner:
- Goal:
- Completion check: (what does done look like — observable behavior, not code merged)
- Files involved:
- Actual result:
- Next action:

Evidence log
- Commands run:
- Observed behavior:
- Notes:
```

---

# Track F — Product Build

## F1 — First-boot init: `docker compose up` self-configures without manual steps

- Status: in_progress
- Owner: `[claude-code]`
- Goal: on a fresh server with only `KLAROHA_DEPLOYMENT_KEY` + `FRONTEND_URL` set, `docker compose up` produces a working BOS instance — no SSH, no manual env editing, no post-boot shell commands.
- Why this is Priority 1: every staging incident requiring manual SSH (INC-004, INC-005, INC-006, C10, C11) would not have occurred if this existed. We are manually compensating for its absence in every recovery session.
- Completion check:
  1. Fresh server, only `KLAROHA_DEPLOYMENT_KEY` + `FRONTEND_URL` in env
  2. `docker compose up` — no errors
  3. `GET /api/` returns `{ "first_boot_complete": true, "migration_status": "head", "env_valid": true, "git_sha": "<sha>" }`
  4. Admin login works — default credentials or setup prompt
  5. No SSH required at any point
- Files involved:
  - `api/main.py` — startup hook
  - `api/config.py` — env validation, secret generation
  - `api/migrations/` — must run automatically
  - `docker-compose.yml`
  - `.env.example`
- Sub-items (ref DEPLOY_TODO F1-1 through F1-6):
  - [ ] Auto-generate `API_SECRET_KEY` (persistent volume, not env) — F1-1
  - [ ] Auto-generate `ENCRYPTION_KEY` as valid Fernet key (`base64.urlsafe_b64encode(secrets.token_bytes(32))`) — F1-2
  - [ ] Auto-run `alembic upgrade head` at startup — F1-3
  - [ ] Bootstrap default workspace row if empty — F1-4
  - [x] Startup validation: refuse to start if critical vars missing or malformed — F1-5 (done 2026-06-02)
  - [ ] Expose `first_boot_complete`, `migration_status`, `env_valid` in `GET /api/` — F1-6
- Actual result: F1-5 done — `validate_settings()` in `api/config.py` checks ENCRYPTION_KEY format (fails startup if set but malformed), warns on default API_SECRET_KEY, warns if no LLM provider key set. Called from `lifespan()` in `api/main.py`.
- Next action: F1-1 — auto-generate API_SECRET_KEY to persistent volume at first boot

Evidence log
- Commands run: `python3 unit tests against validate_settings()`
- Observed behavior: malformed/wrong-length ENCRYPTION_KEY raises RuntimeError and blocks startup; warnings fire for empty key / default secret / no LLM provider. Both .env and .env.staging pass without errors.
- Notes: validate_settings() does not use a logger from main — it has its own module-level logger so it logs before the app is fully initialized.

---

## F2 — Operator self-diagnosis: no SSH required to understand what's wrong

- Status: in_progress
- Owner: `[claude-code]`
- Goal: an org admin with no CLI access can determine what is wrong with their deployment from the admin panel or a single curl.
- Completion check: `GET /api/` returns enough information to diagnose any deployment issue; in-app admin panel shows the same information visually.
- Files involved: `api/routers/health.py`, `api/config.py`, `web/src/` (admin panel)
- Sub-items (ref DEPLOY_TODO F2-1 through F2-3):
  - ~~`git_sha` in health endpoint~~ — done 2026-06-02
  - In-app admin diagnostic panel (version, migration, env completeness, provider health)
  - Rollback procedure — documented one-command revert, no data loss
- Actual result: `git_sha` done. In-app panel and rollback doc still open.
- Next action: in-app admin diagnostic panel (F2-2)

Evidence log
- Commands run:
- Observed behavior: `GET /api/` now returns `git_sha` + `uptime_seconds`
- Notes:

---

## F3 — OAuth relay: zero-setup for Google + Meta integrations

- Status: open
- Owner: `[decision]` → `[claude-code]`
- Goal: a new org gets full Google and Meta OAuth without creating a Google Cloud project or Meta developer app.
- Why this matters: without the relay, every org needs manual OAuth setup. That's incompatible with any self-service deployment model.
- Completion check: a fresh org deployment connects Gmail, Google Calendar, and Meta from the admin panel with no external app registration.
- Files involved: `api/provider_auth.py`, new relay service
- Blocked by: relay architecture design decision
- Actual result:
- Next action: design decision on relay architecture (signed token handoff vs. proxy model)

Evidence log
- Notes: DEPLOY.md Build Order #1 — relay is the dependency for zero-setup deploys.

---

## F4 — Minimal env: two vars to deploy

- Status: open
- Owner: `[claude-code]`
- Goal: operators set `KLAROHA_DEPLOYMENT_KEY` and `FRONTEND_URL`. Everything else is auto-generated or relay-provided.
- Completion check: `.env.example` has exactly 2 required vars at deploy time; all others have auto-generated or relay defaults.
- Files involved: `.env.example`, `api/config.py`, first-boot init (F1 dependency)
- Blocked by: F1 (secrets must be auto-generated first), F3 (OAuth credentials must come from relay)
- Actual result:
- Next action: audit `.env.example` — classify every var as auto/relay/required

Evidence log
- Notes:

---

## F5 — Deployment key system

- Status: open
- Owner: `[claude-code]`
- Goal: each org receives a `KLAROHA_DEPLOYMENT_KEY` at purchase; this key gates relay access and enables usage metering.
- Completion check: relay rejects requests without a valid deployment key; key is issued and validated without manual Klaroha intervention.
- Blocked by: F3 (relay must exist first)
- Actual result:
- Next action: design key issuance and validation mechanism

Evidence log
- Notes:

---

## F6 — Installer + setup wizard

- Status: open
- Owner: `[claude-code]`
- Goal: `curl install.klaroha.com | bash` produces a working BOS instance; first login reaches CMO-operational state with no additional documentation.
- Completion check: a non-technical operator follows the install script, completes the setup wizard, and sends their first CMO message — no Klaroha support.
- Blocked by: F1, F3, F4, F5
- Sub-items: one-command installer; setup wizard (org name → brand brief → CMO open)
- Actual result:
- Next action: after F1-F5 are complete

Evidence log
- Notes:

---

# Track P — Behavioral Parity

> These items close the feedback loop: after any deploy, agents and developers can verify that staging behaves the same as localhost for the feature they built — not just that staging is alive.
>
> **This track is not optional.** Without it, every feature built on localhost is unverifiable on staging. Agents will keep reporting false success because they have no signal for behavioral divergence.

## P1 — State bootstrap: seed staging with the same baseline state as localhost

- Status: open
- Owner: `[claude-code]`
- Goal: after any staging recovery or fresh deploy, one script seeds staging with the same baseline state used for development — workspace, brands, products, audiences, documents. No manual data entry.
- Why this matters: first-boot init handles a fresh org's first deployment. This handles parity between Klaroha's development environment and staging. Both are needed. INC-005 confirmed the gap: structural checks passed 13/13 while behavioral output was completely wrong because staging had 0 brands.
- Completion check:
  1. `bash scripts/seed-staging-baseline.sh` after a fresh staging deploy
  2. `GET /api/brands` on staging returns the same brands as localhost
  3. CMO dispatch on staging returns brand-scoped artifacts for the same prompt — not "My Workspace" generics
  4. No manual DB manipulation required
- Files involved:
  - New `scripts/seed-staging-baseline.sh`
  - Existing brand/workspace API endpoints for import
- Relation to product: the setup wizard (F5-2) is the org-facing equivalent. The seed script is Klaroha's version of the wizard for our own staging.
- Actual result:
- Next action: define the minimum baseline state — what brands/docs/providers constitute a testable staging environment?

Evidence log
- Notes: INC-005 — staging had 0 brands after recovery; `block_brand_name = "My Workspace"` on all runs; behavioral divergence despite identical code.

---

## P2 — Behavioral smoke test: does the feature work on staging the same as localhost?

- Status: open
- Owner: `[claude-code]`
- Goal: after deploying a feature, one command tells an agent whether staging behavior matches localhost — a pass/fail result, not a health check.
- Why this matters: `check-staging.sh` checks structural health. Behavioral tests check whether the feature the agent just built actually works end-to-end in the deployed environment. Without this, agents have no signal for behavioral divergence.
- Completion check: `bash scripts/smoke-parity.sh [feature]` runs against both localhost and staging and outputs PASS or FAIL with a diff on divergence.
- Starting scope (implement in order):
  - `workspace` — compare `GET /workspace`, `GET /brands`, `GET /providers` between envs. Catches C7 state drift immediately.
  - `cmo` — send a test prompt to both envs, verify a run was dispatched to the same module (not content comparison)
  - `media` — verify media dispatch routes to the same capability on both envs
- Files involved: new `scripts/smoke-parity.sh`
- Actual result:
- Next action: implement `workspace` check first — fastest to write, catches the most common divergence

Evidence log
- Notes: INC-005 demonstrated that 13/13 structural checks pass while workspace/brand behavioral output is completely wrong. `smoke-parity.sh workspace` would have caught this immediately.

---

## P3 — Health endpoint: state readiness signals alongside code readiness

- Status: open
- Owner: `[claude-code]`
- Goal: `GET /api/` tells an agent whether the deployment has the state required for meaningful behavioral testing — not just that it is alive and on the right commit.
- Completion check: health response includes `workspace_configured`, `brands_count`, `providers_ready` — an agent reading this knows immediately whether the environment is in a testable state before running any behavioral tests.
- Relation to F1-6: F1-6 adds `first_boot_complete`, `migration_status`, `env_valid`. P3 adds the state readiness layer on top.
- Files involved: `api/routers/health.py`
- Actual result:
- Next action: implement after F1-6

---

# Track I — Internal Ops (Klaroha Staging Only)

> These exist because F1 doesn't exist yet. We are manually compensating for the absence of first-boot init.
> Do not let these block Track F. Each one becomes irrelevant once the corresponding product feature ships.

## I1 — Fix `STAGING_ENV_FILE` GitHub secret

- Status: open
- Owner: `[human]`
- Goal: add the 6 missing staging-only vars so the next CI deploy doesn't overwrite `.env.staging` with broken values.
- Required values to add: `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001`, `ENV_FILE=.env.staging`
- Becomes irrelevant when: F1 ships — each org's env is self-managed, no GitHub secret needed
- Actual result:
- Next action: human updates GitHub Actions secret

---

## I2 — CI staging gate decision

- Status: open
- Owner: `[decision]`
- Goal: decide what gate prevents unfinished features from auto-deploying to staging.klaroha.com.
- Options: protected branch + PR checks / manual CI approval / staging-ready label
- Becomes irrelevant when: F1 + F3 make staging a real org deployment; the gate becomes part of the product release process, not internal ops.
- Actual result:
- Next action: human decision

---

## I3 — Agent Deploy Protocol in CLAUDE.md

- Status: open
- Owner: `[claude-code]`
- Goal: document that push ≠ deploy and that `git_sha` + `uptime_seconds` are the verification signals.
- Becomes irrelevant when: F1-6 + F2-2 make verification automatic — health endpoint tells you everything.
- Actual result:
- Next action: write the protocol section

---

# Validated / Falsified / Done

| Item | Result | Date |
|---|---|---|
| C8 — provider/plugin/social readiness differs across envs | **validated** — Gemini + OpenRouter degraded on staging; Google Ads + Analytics missing vars; social connections at parity. Root cause: `STAGING_ENV_FILE` secret incomplete (missing `PLATFORM_GEMINI_KEY`, `PLATFORM_OPENROUTER_KEY`, `GOOGLE_ADS_*`, `GOOGLE_ANALYTICS_*`). Fix: human updates secret (I-1). | 2026-06-02 |
| H2 — push to staging does not auto-deploy | **falsified** — CI `deploy-staging` job is active | 2026-06-02 |
| H3 — stale browser brand state causing drift | **falsified** + fixed — `Layout.tsx` evicts stale localStorage brand_id | 2026-06-02 |
| C4 — smoke-local.sh tests GHCR, not local code | **validated** — correct by design | 2026-06-02 |
| C5a — manual deploy uses mutable `:staging` tag | **validated** — script inspection confirmed | 2026-06-02 |
| F2-1 — `git_sha` in health endpoint | **done** | 2026-06-02 |
| O2 — `uptime_seconds` in deploy banner | **done** | 2026-06-02 |
