# DEPLOY_TODO.md — Prioritized Task List

> One question orders everything: **what prevents localhost → staging sync from breaking?**
>
> Owner tags: `[claude-code]` = code, `[human]` = operator action, `[decision]` = human decision needed.

---

## Staging Drift Hypotheses

> Testing methodology: **behavioral first** — hit real endpoints and compare outputs, not just read files.
> File reads tell you what should happen. Endpoint calls tell you what is happening.
> Status: `[untested]` `[confirmed]` `[ruled out]`

### META_APP_ID failure (observed: `⚠️ Could not start Facebook connect — META_APP_ID not configured`)

Traced full execution path (2026-06-13):
1. `POST /social/connect/start` → `FacebookOAuthHandler._app_id()` (`provider_auth.py:735`)
2. Checks three fallbacks in order: `overrides.get("meta_app_id")` → `overrides.get("META_APP_ID")` → `settings.meta_app_id` (env var)
3. `overrides` comes from `get_plugin_vars("channel.meta", db, settings)` → `_load_db_plugin_vars()` (`plugin_loader.py:492`)
4. All three are empty → raises `ValueError`

| # | Hypothesis | Test | Status |
|---|---|---|---|
| H1 | `META_APP_ID` is empty in `STAGING_ENV_FILE` GitHub secret | Read secret in GitHub → check `META_APP_ID=` line | `[confirmed — .env.staging has META_APP_ID= empty, and secret is written from this file]` |
| H2 | `channel.meta` not installed on staging → Admin UI never showed credentials form → no DB row → all three fallbacks empty | `GET /admin/plugins` on staging — does `channel.meta` appear? | `[untested — blocked mid-session]` |
| H3 | `channel.meta` IS installed but credentials never entered via Admin UI on staging | `GET /admin/plugins/channel.meta` — is there a `ProviderKey` row? | `[untested]` |
| H4 | `_load_db_plugin_vars` silently swallows a real DB exception and returns `{}` — actual error hidden | Check staging API logs for exceptions during `/social/connect/start` | `[untested — bare except at plugin_loader.py:518 is the risk]` |
| H5 | Staging DB has multiple workspace rows; `_load_db_plugin_vars` picks wrong one | Count workspace rows on staging: `SELECT count(*) FROM workspace` | `[untested — code comment at plugin_loader.py:503 explicitly warns this can happen after staging restores]` |

### Systemic staging drift (why staging keeps breaking in ways I can't see)

| # | Hypothesis | Test | Status |
|---|---|---|---|
| S1 | `STAGING_ENV_FILE` secret is stale — missing vars added to `.env.example` after last manual update | Diff secret content against current `.env.example` keys | `[confirmed — META_APP_ID, PLATFORM_ANTHROPIC_KEY, PLATFORM_BYTEDANCE_KEY, GOOGLE_PICKER_APP_ID absent or empty]` |
| S2 | CI env guard only validates 5 keys — everything else can be missing silently | Read `ci.yml:183` — guard checks only `ENV_FILE API_SECRET_KEY ENCRYPTION_KEY DATABASE_URL FRONTEND_URL` | `[confirmed — guard is insufficient by design]` |
| S3 | `EXTERNAL_PLUGINS_PATH` not set in staging → defaults to `/home/ubu/bos-plugins` — does that path exist on the staging VDS? | SSH and check `ls /home/ubu/bos-plugins` | `[untested]` |
| S4 | Plugin activation state in staging DB differs from localhost — different plugins active, different brands | Compare `GET /admin/plugins` between localhost and staging | `[untested — blocked mid-session]` |
| S5 | Staging relay mode changes OAuth behavior for some flows vs localhost | localhost uses `KLAROHA_RELAY_URL=http://relay:8100`; staging uses `https://staging.klaroha.com` — different relay paths | `[untested]` |

### Unknown — other things that may be broken but haven't surfaced yet

| # | Hypothesis | Why suspected |
|---|---|---|
| U1 | TikTok connect is broken the same way as Facebook | `TIKTOK_CLIENT_KEY=` empty in `.env.staging`; same plugin_vars fallback pattern |
| U2 | Any Anthropic-backed capability silently fails on staging | `PLATFORM_ANTHROPIC_KEY` not in `.env.staging` at all |
| U3 | Video generation broken on staging | `PLATFORM_BYTEDANCE_KEY` not in `.env.staging` at all |
| U4 | Google Picker broken on staging | `GOOGLE_PICKER_APP_ID` not in `.env.staging` at all |

### Root cause pattern

The real problem isn't any single missing var. It's that:
- **The running system on staging is invisible from this repo.** The only source of truth is the `STAGING_ENV_FILE` GitHub secret, which cannot be read without SSH or GitHub UI access.
- **File reads lie.** `.env.staging` in the repo is overwritten on every deploy by whatever is in the secret. Reading it locally tells you what was intended, not what's running.
- **The CI guard has a 5-key blind spot.** Any new var added to `.env.example` that isn't in the secret will silently fail — no deploy error, no log, no warning.
- **Silent exceptions make it worse.** `_load_db_plugin_vars` at `plugin_loader.py:518` does `except Exception: return {}` — a DB error is indistinguishable from "credentials not configured."

**Correct testing methodology going forward:** probe real endpoints and compare localhost vs staging outputs before declaring anything "looks fine."

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
| ~~F1-3~~ | ~~Auto-run `alembic upgrade head` at container start — fail loudly on error~~ | done — Dockerfile CMD | Manual migration step, migration drift |
| ~~F1-4~~ | ~~Bootstrap default workspace if table is empty — name from `FRONTEND_URL` domain~~ | done 2026-06-02 | Manual `PUT /workspace/brand` after fresh deploy |
| F1-6 | Add to `GET /api/`: `first_boot_complete`, `migration_status`, `env_valid` | `[claude-code]` | Makes any env diagnosable without SSH |

---

## Priority 2 — Deploy Reliability (eliminates the wrong-image and wrong-env classes)

Confirmed cause C5a: manual deploys use mutable `:staging` tag — if you deploy before CI finishes, you get yesterday's image. Industry standard fix: every deploy uses an immutable SHA tag.

Confirmed cause C4: keys in `.env` that aren't in `.env.staging` silently break features on staging.

| # | Task | Owner | Crash class eliminated |
|---|---|---|---|
| ~~D1~~ | ~~`deploy-staging.sh` — when `DEPLOY_SHA` is unset, derive from `git rev-parse HEAD`; never deploy mutable `:staging` tag~~ | done 2026-06-02 | C5a — wrong image on manual deploy |
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
