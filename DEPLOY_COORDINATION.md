# DEPLOY_COORDINATION.md

> Active execution tracker for deploy work and AI handoff.
> `DEPLOY.md` = durable runbook + incident log. `DEPLOY_TODO.md` = task list. This file = detailed specs.

---

## The Actual Problem

Localhost works. Staging crashes or behaves differently after a push. Four confirmed root causes, in order of frequency:

| # | Root cause | Confirmed by | Fix |
|---|---|---|---|
| 1 | **Env misconfiguration** — wrong ENCRYPTION_KEY format, missing port vars, containers reading wrong .env | INC-004, INC-006, C10, C11 | F1: first-boot init |
| 2 | **State drift** — staging DB has 0 brands/objectives after recovery; identical code, different behavior | INC-005, C7 | P1: seed-baseline.py |
| 3 | **Wrong image deployed** — manual deploy uses mutable `:staging` tag; if CI hasn't finished, yesterday's image loads | C5a validated | D1: always SHA-pin |
| 4 | **Missing env keys** — vars in `.env` not in `.env.staging` silently break features on staging | C4 | D2: env-parity check |

Everything else (hypothesis lists, agent protocol debates, CI gate decisions) is secondary. Fix these four and the problem stops.

---

## Scale Rules

| Rule | Implication |
|---|---|
| No per-org SSH | Every fix requiring SSH is a product gap |
| Operator-resolvable | Org admin fixes via admin panel or one command |
| Automated verification | Health, migrations, env validity — machine-readable |

Full directive: `DEPLOY.md §Scale Directive`

---

## Quick Start for the Next AI

1. Check `DEPLOY_TODO.md` — find the first open item
2. Highest current priority: **I-1** (human must update GitHub secret) → **F1-3** → **D1**
3. Key files: `api/main.py`, `api/config.py`, `api/first_boot.py`, `deploy-staging.sh`, `api/Dockerfile`
4. Do not invent new investigation items. If staging breaks, map it to one of the four root causes above first.

---

## Item Template

```
## <id> — <title>
- Status: open | in_progress | done | blocked
- Owner:
- Completion check: (observable behavior, not "code merged")
- Files:
- Result:
- Next action:
```

---

# Track F — First-Boot Init

## F1 — `docker compose up` self-configures on a fresh server

- Status: in_progress
- Owner: `[claude-code]`
- Completion check: fresh server + only `KLAROHA_DEPLOYMENT_KEY` + `FRONTEND_URL` → `docker compose up` → `GET /api/` returns `first_boot_complete: true, migration_status: head, env_valid: true` — no SSH at any point
- Files: `api/first_boot.py`, `api/main.py`, `api/config.py`, `docker-compose.yml`
- Remaining sub-items:
  - [ ] F1-6: expose `first_boot_complete`, `migration_status`, `env_valid` in `GET /api/`
- Done: F1-1, F1-2, F1-3, F1-4 (`ensure_workspace()` in `lifespan()`), F1-5
- Next action: F1-6

---

# Track D — Deploy Reliability

## D1 — Every deploy uses an immutable image SHA, never a mutable tag

- Status: open
- Owner: `[claude-code]`
- Why: C5a confirmed — manual deploys without `DEPLOY_SHA` pull mutable `:staging` tag. If CI is mid-build, the previous image deploys. Industry standard: every deploy pins to an immutable digest.
- Completion check: `deploy-staging.sh` run manually with no `DEPLOY_SHA` set → derives SHA from `git rev-parse HEAD` → pulls `ghcr.io/itsborj/bos-api:sha-<commit>`, not `:staging`
- Files: `deploy-staging.sh`
- Next action: update tag resolution logic — if `DEPLOY_SHA` unset, set it from `git rev-parse HEAD`

---

## D2 — Env parity check before every staging deploy

- Status: open
- Owner: `[claude-code]`
- Why: C4 — keys in `.env` but not `.env.staging` silently break features. No tool exists to catch this before deploy.
- Completion check: `bash scripts/check-env-parity.sh` — diffs required keys between `.env` and `.env.staging`, lists any missing from staging, exits non-zero if any are missing. Runs as a step in `deploy-staging.sh`.
- Files: new `scripts/check-env-parity.sh`, `deploy-staging.sh`
- Next action: write the script — compare keys in both files, ignore values

---

## D3 — API container has a Docker HEALTHCHECK

- Status: open
- Owner: `[claude-code]`
- Why: currently `api` has no `HEALTHCHECK` in Dockerfile. `docker compose` marks it running as soon as the process starts — even if uvicorn hasn't finished loading or migrations failed. Other services and load balancers can't detect an unhealthy API.
- Completion check: `docker inspect bos-api-1 | jq '.[0].State.Health'` returns `healthy` after startup and `unhealthy` if the API stops responding
- Files: `api/Dockerfile`
- Next action: add `HEALTHCHECK CMD curl -f http://localhost:8000/ || exit 1 --interval=10s --timeout=5s --retries=3`

---

# Track P — Behavioral Parity

## P1 — Version-controlled seed baseline

- Status: open
- Owner: `[claude-code]`
- Why: C7 — staging DB loses all brands/objectives/docs on every recovery. Behavior diverges from localhost despite identical code. Exporting localhost state is fragile (it drifts). Industry standard: committed, deterministic seed data runnable against any env.
- Completion check: `python3 scripts/seed-baseline.py --env staging` → staging has the same workspace, brands (Klaroha, Mactan Group, MotorMoto), products, audiences, docs as the development baseline. CMO dispatch returns brand-scoped output, not "My Workspace" generics.
- Files: new `scripts/seed-baseline.py`
- Next action: define the minimum baseline — what rows constitute a testable staging environment?

---

## P2 — Smoke parity check

- Status: open
- Owner: `[claude-code]`
- Why: `check-staging.sh` checks structural health. Nothing checks whether staging *behaves* the same as localhost. INC-005: 13/13 structural checks passed while CMO output was completely wrong.
- Completion check: `bash scripts/smoke-parity.sh` — compares `GET /workspace`, `/brands`, `/providers` between localhost and staging; outputs PASS or FAIL with a diff. Runs in under 30 seconds.
- Files: new `scripts/smoke-parity.sh`
- Next action: write the script — curl both envs, diff key fields

---

# Track I — Internal Ops (temporary)

## I-1 — Fix `STAGING_ENV_FILE` GitHub secret

- Status: open
- Owner: `[human]`
- Why immediate: next push triggers CI which overwrites `/root/bos/.env.staging` from this secret. If the secret is still missing the 6 port vars, staging crashes again (INC-006 replay).
- Required additions: `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001`, `ENV_FILE=.env.staging`
- Becomes irrelevant when: F1 complete — env self-manages, no GitHub secret needed for runtime config
- Next action: human updates GitHub Actions secret

---

# Validated / Done

| Item | Result | Date |
|---|---|---|
| F1-1: auto-generate `API_SECRET_KEY` | done — `first_boot.py` + `bos_secrets` volume | 2026-06-02 |
| F1-2: auto-generate `ENCRYPTION_KEY` (Fernet) | done — same `first_boot.py` | 2026-06-02 |
| F1-3: auto-run migrations at container start | done — Dockerfile CMD `alembic upgrade head && uvicorn ...` | 2026-06-02 |
| F1-5: startup env validation | done — `validate_settings()` blocks on malformed vars | 2026-06-02 |
| D1: always deploy immutable SHA tag | done — `deploy-staging.sh` derives `git rev-parse HEAD` on manual runs | 2026-06-02 |
| F1-4: bootstrap default workspace | done — `ensure_workspace()` in `lifespan()`; name from `FRONTEND_URL` hostname | 2026-06-02 |
| git_sha in health endpoint | done | 2026-06-02 |
| uptime_seconds in deploy banner | done | 2026-06-02 |
| H2: push=deploy | falsified — CI deploy job is active | 2026-06-02 |
| H3: stale browser brand state | falsified + fixed — Layout.tsx evicts stale brand_id | 2026-06-02 |
| pre-push hook: replaced smoke-local.sh with pytest+tsc against local containers | done — tests actual local code before push; `BOS_SKIP_PUSH=1` to bypass | 2026-06-02 |
| deploy-staging CI: changed from push-triggered to workflow_dispatch (manual only) | done — push builds image, deploy is a separate explicit trigger | 2026-06-02 |
| C5a: manual deploy uses mutable `:staging` tag | validated — confirmed by script inspection | 2026-06-02 |
