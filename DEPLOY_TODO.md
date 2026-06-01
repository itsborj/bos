# DEPLOY_TODO.md — Prioritized Task List

> One question orders everything: **what prevents localhost → staging sync from breaking?**
>
> Owner tags: `[claude-code]` = code, `[human]` = operator action, `[decision]` = human decision needed.

---

## Now — Fix What's Breaking Today

These are the confirmed causes of every staging crash. Nothing else gets worked until I-1 is done.

| # | Task | Owner | Incident it prevents |
|---|---|---|---|
| I-1 | Update GitHub Actions secret `STAGING_ENV_FILE` — add `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001`, `ENV_FILE=.env.staging` + any missing provider keys | `[human]` | INC-004, INC-006 — containers bind wrong ports on every push |

---

## Priority 1 — First-Boot Init (eliminates the env misconfiguration class)

The #1 confirmed crash cause: env misconfiguration (INC-004, INC-006, C10, C11). Every incident required manual SSH to fix a config that should auto-generate correctly. This track makes that class of crash impossible.

| # | Task | Owner | Crash class eliminated |
|---|---|---|---|
| ~~F1-1~~ | ~~Auto-generate `API_SECRET_KEY` to persistent volume~~ | done 2026-06-02 | Manual key bootstrap |
| ~~F1-2~~ | ~~Auto-generate `ENCRYPTION_KEY` as valid Fernet key~~ | done 2026-06-02 | C10 — wrong format |
| ~~F1-5~~ | ~~Startup validation — refuse to start on malformed vars~~ | done 2026-06-02 | C11 silent misconfiguration |
| F1-3 | Auto-run `alembic upgrade head` at container start — fail loudly on error | `[claude-code]` | Manual migration step, migration drift |
| F1-4 | Bootstrap default workspace if table is empty — name from `FRONTEND_URL` domain | `[claude-code]` | Manual `PUT /workspace/brand` after fresh deploy, C7 partial |
| F1-6 | Add to `GET /api/`: `first_boot_complete`, `migration_status`, `env_valid` | `[claude-code]` | Makes any env diagnosable without SSH |

---

## Priority 2 — Deploy Reliability (eliminates the wrong-image and wrong-env classes)

Confirmed cause C5a: manual deploys use mutable `:staging` tag — if you deploy before CI finishes, you get yesterday's image. Industry standard fix: every deploy uses an immutable SHA tag.

Confirmed cause C4: keys in `.env` that aren't in `.env.staging` silently break features on staging.

| # | Task | Owner | Crash class eliminated |
|---|---|---|---|
| D1 | `deploy-staging.sh` — when `DEPLOY_SHA` is unset, derive it from `git rev-parse HEAD` before pulling; never deploy a mutable `:staging` tag | `[claude-code]` | C5a — wrong image deployed on manual deploy |
| D2 | `scripts/check-env-parity.sh` — diff required keys between `.env` and `.env.staging`; run before every staging deploy; fail with a list of missing keys | `[claude-code]` | C4 — missing keys silently break features on staging |
| D3 | Add `HEALTHCHECK` to `api/Dockerfile` — `CMD curl -f http://localhost:8000/ \|\| exit 1`; compose marks container unhealthy until API responds | `[claude-code]` | Silent startup failures where container is "running" but API is down |

---

## Priority 3 — State + Behavioral Parity (eliminates the "works locally, breaks on staging" class)

Confirmed cause C7: staging DB state drifts from localhost after every recovery. Code is identical; behavior diverges because staging has 0 brands. No tool exists to detect or fix this.

| # | Task | Owner | What it catches |
|---|---|---|---|
| P1 | `scripts/seed-baseline.py` — version-controlled, committed seed that creates a deterministic baseline state (workspace, brands, products, audiences, documents) runnable against any env | `[claude-code]` | C7 — staging behavior diverges despite identical code |
| P2 | `scripts/smoke-parity.sh` — compare `GET /workspace`, `/brands`, `/providers` between localhost and staging; output PASS/FAIL with a diff | `[claude-code]` | Immediate divergence signal after every deploy; catches C7 before anyone notices |

---

## Priority 4 — Scale Foundation (enables 10K org deployments)

These are sequentially dependent. Do not start the next item until the previous is done.

| # | Task | Owner | Unblocks |
|---|---|---|---|
| F3-1 | Design + approve OAuth relay architecture (`connect.klaroha.com`) | `[decision]` | Every org gets Google + Meta OAuth without app registration |
| F3-2 | Build relay — token broker, signed handoff, per-org isolation | `[claude-code]` | Zero-setup OAuth for all orgs |
| F4-1 | Audit `.env.example` — classify every var: auto-generated / relay-provided / operator-required | `[claude-code]` | Produces the minimal-env target |
| F4-2 | Reduce required env to `KLAROHA_DEPLOYMENT_KEY` + `FRONTEND_URL` | `[claude-code]` | Operator sets 2 vars, nothing else |
| F4-3 | Deployment key issuance + relay access gating | `[claude-code]` | Per-org billing and access control |
| F5-1 | `curl install.klaroha.com \| bash` installer | `[claude-code]` | Single command to deploy |
| F5-2 | Setup wizard: first login → brand brief → CMO operational | `[claude-code]` | Zero-to-operational without documentation |

---

## Completed

| Date | Task | Resolution |
|---|---|---|
| 2026-06-02 | `git_sha` in health endpoint | Baked at CI build, exposed in `GET /api/` |
| 2026-06-02 | `uptime_seconds` in deploy banner | `deploy-staging.sh` final banner |
| 2026-06-02 | F1-1: auto-generate `API_SECRET_KEY` | `first_boot.py` + `bos_secrets` volume |
| 2026-06-02 | F1-2: auto-generate `ENCRYPTION_KEY` | Same `first_boot.py` — Fernet-correct |
| 2026-06-02 | F1-5: startup env validation | `validate_settings()` in `config.py` |
| 2026-06-02 | H2: push=deploy (falsified) | CI `deploy-staging` job is active |
| 2026-06-02 | H3: stale browser brand state (falsified + fixed) | `Layout.tsx` evicts stale `bos_active_brand` |
