# BOS — Deployment Reference

---

## 10K-Org Principle — First Requirement, Always

> **This is the top-level constraint. Every bug fix, workaround, and solution in this document must be evaluated against it before being accepted. A solution that fails this test is not a solution — it is a deferred incident.**
>
> Manual SSH recovery, per-org secrets reconstruction, and Klaroha-assisted debugging are tolerated **only during active development and testing** of the Klaroha-owned staging environment. They are never acceptable as a permanent fix, and never acceptable in any customer org context. Every incident resolved manually must have a corresponding automation task in `BACKLOG.md` before it is marked closed.

BOS is built to deploy to **hundreds of organizations per day** and support **10,000+ concurrent org deployments** with minimal Klaroha operational overhead. This is not a future aspiration — it shapes every bug fix, solution, and architectural choice documented here today.

### Principles

| Principle | Implication for every bug fix and solution |
|---|---|
| **No per-org SSH** | Any fix that requires Klaroha to SSH into a customer's server is a product defect at scale. The fix is not done until it is automatable or operator-self-serviceable via a documented single command. |
| **No Klaroha access to org data** | Debugging cannot rely on reading a customer's DB, container, or `.env`. Issues must be diagnosable from: in-app admin UI, the org's own logs, or deployment-key telemetry visible to the operator. |
| **Zero-touch new org deploys** | A new org deploy must complete without Klaroha intervention. Any runbook step that says "Klaroha engineer must do X" must be converted into automated first-boot behavior before it ships. |
| **Operator-resolvable issues** | When something breaks, the org admin must be able to resolve it through the admin panel or a single documented command — not a multi-step SSH session guided by Klaroha support. |
| **Automated verification** | Any check that requires a human to run and interpret is a liability. Health, migration status, version fingerprint, and env validation must be machine-readable and auto-reported. |
| **Isolated by default** | Each org has its own DB, keys, and container. Bugs in one org must not affect others. Fixes must never require cross-org operations. |

### Evaluating a proposed fix

Before accepting any fix or workaround, ask:

1. **Would this require SSH on a customer's server?** If yes — not done. Automate it.
2. **Would this require Klaroha to read a customer's DB or `.env`?** If yes — not done. Surface it in the admin UI or health endpoint.
3. **Would a new org deploying for the first time hit this same problem?** If yes — it must be handled at first boot, not post-hoc.
4. **Is the fix a one-time manual step, not codified anywhere?** If yes — it will recur. Write it into the pipeline or the deploy script.

### What this means for the incident log

Every incident marked `CONFIRMED` that was resolved via manual SSH is a **product gap** — not a closed issue. Before marking such an incident resolved, add a corresponding automation task to `BACKLOG.md`. The manual fix is a one-time exception; the automated equivalent is the real fix.

### What is not required now vs. must be right

Not every item needs to be built today. The 10K-org principle governs **direction** — each incremental solution must make the system more scalable, not less. A fix that introduces a new manual step or a new per-org secret to manage is moving in the wrong direction, even if it solves the immediate symptom.

---

> Single source of truth for all deploy operations, port topology, localhost ↔ staging breakage runbook, and the future production model.
> **git.md has been merged into this file and deleted.**
> Active execution tracker for deploy hypotheses / AI handoff: `DEPLOY_COORDINATION.md`.

---

## Server Layout

Both stacks run on the same VDS from `~/bos/` using one compose file with different env vars.

| Stack | Project | Branch | Domain | Ports |
|---|---|---|---|---|
| Production | `bos` | `main` | hq.klaroha.com | api:8000, web:5173, nginx:8090 |
| Staging | `staging` | `staging` | staging.klaroha.com | api:8001, web:5174, nginx:8091 |

Docker project names: `bos` (production), `staging` (staging).

---

## Branch Strategy

```
localhost  →  staging branch  →  main branch
                   ↓                  ↓
        staging.klaroha.com     hq.klaroha.com  ← live clients
```

- Work locally on `localhost:8090`
- Push to `staging` branch → CI tests → builds images → auto-deploys to `staging.klaroha.com`
- Verify on staging, then merge to `main`
- Deploy to production manually via GitHub Actions → Run workflow → target: `production`

**Never push to `main` expecting a production deploy.** `main` runs tests only.

---

## Production Down SOP — Read This Before Suggesting Any Fix

> **For agents and developers:** When `hq.klaroha.com` is broken, this is the only valid response tree. Stop before suggesting anything else.

**Do NOT:**
- SSH into the VDS and run `docker compose build`
- Run any `docker compose` command targeting the `bos` project on the VDS
- Suggest rebuilding production containers manually
- Suggest switching the VDS repo branch and rebuilding

**DO:**
1. Diagnose using read-only checks: `curl https://hq.klaroha.com/api/`, `GET /api/plugins`, `docker ps` read-only
2. Reproduce and verify the fix on `staging.klaroha.com` first
3. Once verified on staging: merge `staging` → `main`
4. GitHub Actions → CI → Run workflow → target: `production`

**Why this rule exists:** INC-009 (2026-06-09) was caused by running `docker compose build` on the VDS while the repo was on the `staging` branch. The production `bos` stack was silently rebuilt from wrong-branch code. `git_sha: "dev"` in `GET /api/` is the signal it happened. The pipeline is the only path that guarantees the right branch, the right image, and a verifiable deploy.

**The `git_sha: "dev"` signal:** Any time `GET /api/` returns `git_sha: "dev"` on production, the image was built locally on the VDS — not by CI. This is always wrong. CI always bakes the real SHA via `--build-arg GIT_SHA=${{ github.sha }}`. A local build means the pipeline was bypassed.

**Fixed (2026-06-09):** The production deploy in `ci.yml` previously used `docker compose up --build`, rebuilding from source on the VDS — a completely different path from staging which pulls the CI-built GHCR image with `--no-build`. This structural divergence meant staging never validated what production actually ran, and was the root cause of INC-009. Production now pulls `ghcr.io/itsborj/bos-api:sha-{SHA}` and uses `--no-build --force-recreate`, identical to the staging path.

---

## Deploy Runbook

### Deploy to staging (staging.klaroha.com)

```bash
# Push to staging branch — CI handles everything automatically
git push origin staging
# CI: tests → build images → deploy to staging.klaroha.com
```

To manually re-deploy staging without a push:
- GitHub Actions UI → CI → Run workflow → target: `staging`

### Deploy to production (hq.klaroha.com)

**Only after verifying on staging.klaroha.com.**

1. Merge `staging` → `main`
2. GitHub Actions UI → CI → Run workflow → target: `production`

CI will SSH into the server, pull `origin/main`, rebuild containers, and run migrations.

### Pre-push test (runs automatically)

`.githooks/pre-push` fires automatically on any push to `staging` or `main` — no manual step required.

The hook is activated per-clone with:
```bash
git config core.hooksPath .githooks
```

This is already set in the local repo. Any new clone needs to run this once (add to onboarding docs).

**What it does:** runs `pytest` inside the running `api` container and a TypeScript type check inside the running `web` container — against your actual local code, not a pulled image. If either fails, the push is blocked.

**Requirements:** `api` and `web` containers must be running (`docker compose up -d api web`). If a container is not running the check is skipped with a warning, not a hard block.

**Skip when needed:** `BOS_SKIP_PUSH=1 git push` (emergency escape hatch).

### Check what's running

```bash
git log --oneline -3 && git fetch origin && git status
docker ps --format "table {{.Names}}\t{{.Ports}}"
# Check staging API uptime — if unchanged after a CI run, containers aren't restarting
curl https://staging.klaroha.com/api/ | python3 -c "import json,sys; print(json.load(sys.stdin)['uptime_seconds'])"
```

---

## Host Proxy & Port Topology

> The VDS runs one host-level nginx proxy (`docker-compose.proxy.yml`) that routes public domains to the correct Docker stack. All port assignments are permanent — changing one requires updating both the Docker stack env and this proxy config.

### How it works

```
Internet → port 80 (bos-proxy-proxy-1, network_mode: host, nginx.host.conf)
  ├── klaroha.com / www.klaroha.com  → 127.0.0.1:3000  (bos-public-1 — marketing pages)
  ├── hq.klaroha.com                 → 127.0.0.1:8090  (bos-nginx-1 — local/production stack)
  └── staging.klaroha.com            → 127.0.0.1:8091  (staging-nginx-1 — staging stack)
```

### Port assignments

| Port | Service | Docker project | Notes |
|------|---------|---------------|-------|
| 80   | `bos-proxy-proxy-1` | `bos-proxy` | Host nginx, `network_mode: host`. Routes public domains. |
| 3000 | `bos-public-1` | `bos` | Klaroha marketing pages. |
| 3001 | `staging-public-1` | `staging` | Staging marketing pages (local only). |
| 5173 | `bos-web-1` | `bos` | Local dev frontend. |
| 5174 | `staging-web-1` | `staging` | Staging frontend. |
| 8000 | `bos-api-1` | `bos` | Local/production API. |
| 8001 | `staging-api-1` | `staging` | Staging API. |
| 8090 | `bos-nginx-1` | `bos` | **Local dev / production nginx.** `hq.klaroha.com` routes here. |
| 8091 | `staging-nginx-1` | `staging` | **Staging nginx.** `staging.klaroha.com` routes here. |
| **8080** | `open-webui` | — | **Unrelated container, network_mode: host. Do not assign any BOS service to this port.** |

### Key files

- `docker-compose.proxy.yml` — host proxy service definition (`network_mode: host`)
- `nginx.host.conf` — domain → port routing rules (source of truth for which port each domain hits)
- `.env.staging` — `NGINX_PORT=8091` overrides the docker-compose.yml default (`${NGINX_PORT:-8090}`)

### Rules

1. **Never use port 8080 for any BOS service.** `open-webui` runs `network_mode: host` with `PORT=8080` and will always win the bind race.
2. **Any port change requires two file updates:** `.env.staging` (or `.env`) AND `nginx.host.conf`. Changing only one will break routing silently.
3. **Reload the host proxy after changing `nginx.host.conf`:** `docker compose -p bos-proxy exec proxy nginx -s reload`
4. **`.env.staging` is gitignored.** After a port change, update it on the VDS server manually: `sed -i 's/NGINX_PORT=OLD/NGINX_PORT=NEW/' .env.staging`
5. **`STAGING_ENV_FILE` must include all five staging host-port overrides explicitly.** Do not rely on compose defaults for staging. Required entries: `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001`. If these are missing, staging falls back to production host ports (`5432/8000/5173/8090/3000`), `db/api/web/public/nginx` stay stuck in `Created`, and host nginx returns 502 because nothing binds `127.0.0.1:8091`.
6. **`STAGING_ENV_FILE` must also set `ENV_FILE=.env.staging`.** The compose file uses `env_file: ${ENV_FILE:-.env}` for `api` and `relay`. Without `ENV_FILE=.env.staging`, compose interpolation may use `.env.staging` while the running containers silently read `/root/bos/.env`, causing cross-environment secret/config drift.

### History

| Date | Change | Reason |
|------|--------|--------|
| 2026-05-22 | Staging nginx moved from 8082 → 8080 (`docker-compose.staging.yml`) | Port alignment |
| 2026-05-25 | `docker-compose.staging.yml` deleted; single `docker-compose.yml` with `NGINX_PORT` env var | One compose file for both envs |
| 2026-05-26 | Staging nginx moved from 8080 → **8091** | `open-webui` (unrelated, `network_mode: host`) was squatting on 8080, causing `staging-nginx-1` to fail on every deploy |

---

## Localhost → Staging Breakage Runbook

> Living document. When a feature works on localhost but breaks after a staging deploy, come here first.
> Work through candidate causes in order. Log findings in the Incident Log at the bottom.
> Closed causes stay in the list — mark status and move on.
>
> Goal: isolate root causes through controlled experiments and never violate the confirmed rules again.
>
> **Scale alignment:** Every confirmed cause that was resolved manually must have a corresponding BACKLOG item to automate it before it becomes a recurring support burden at 10K-org scale. Solutions that require Klaroha SSH access, per-org manual steps, or undocumented environment surgery are not acceptable long-term fixes.

---

### The Structural Root Cause (Always True)

Localhost and staging run from different sources of truth:

| | Localhost | Staging |
|---|---|---|
| Source of truth | `./api/` on disk (live volume mount) | `origin/staging` branch in git |
| Code sync | Volume mount — instant, no commit needed | `git reset --hard origin/staging` + image build |
| Uncommitted edits | **Visible to container** | **Not in image — invisible** |
| Untracked files | **Present** | **Absent** |
| Local `.env` overrides | Applied from `.env` | Only from `.env.example` defaults + `.env.staging` |
| `/tmp` video files | Survive across dev sessions | **Destroyed on every `docker compose up --build`** |

The gap between your filesystem and `origin/staging` is always the first place to look.

---

### Hypothesis Standard

Use two different buckets and do not mix them:

1. **Cause-elimination hypotheses** — for the current localhost-vs-staging debug tree
2. **Observability / process work** — version fingerprints, uptime surfacing, doc cleanup, agent protocol, CI gates

A valid **cause-elimination hypothesis** must be:
- **specific** — one clear claim
- **falsifiable** — the test can prove it wrong
- **root-cause reducing** — once tested, one branch of the current cause tree is removed or confirmed

Valid final states for a cause-elimination hypothesis are:
- `validated`
- `falsified`
- `blocked`

`partial` and `inconclusive` are not valid final outcomes. If you get one of those, the hypothesis was too broad or the experiment was incomplete — rewrite it.

Observability / process items are still important, but they do **not** belong in the current-cause hypothesis list unless testing them will directly shrink today's root-cause tree. Track those separately in `DEPLOY_COORDINATION.md` under non-hypothesis work.

### Candidate Causes

#### C1 — Uncommitted local edits not on staging branch
**Status:** `CONFIRMED 2026-05-26`

You fix something locally. It works immediately via the volume mount. You deploy without committing the fix. `deploy-staging.sh` runs `git reset --hard origin/staging`, reverting staging to the unfixed code. Feels like the deploy broke something; staging just reverted.

**Side effect:** `git reset --hard` resets the local working directory too — uncommitted local edits are wiped from your filesystem, not just from staging.

**Confirm:**
```bash
git diff origin/staging -- api/     # any local changes not on staging?
git status                          # any modified/untracked tracked files?
```

**Rule:** Always commit and push to `origin/staging` before running `deploy-staging.sh`. If you have uncommitted local changes when you deploy, you will lose them and staging will run stale code.

---

#### C2 — Untracked local ffmpeg binaries (version/codec mismatch)
**Status:** `RULED OUT (2026-05-26)`

Three untracked static ffmpeg binaries sit in the repo root (`ffmpeg`, `ffmpeg-static`, `ffprobe-static`, ~80 MB each). The video module resolves the binary via `FFMPEG_PATH` env var, defaulting to `"ffmpeg"` (system PATH). If local `.env` points `FFMPEG_PATH` to one of these static builds and `.env.staging` does not, staging uses the apt-installed system ffmpeg (Dockerfile: `apt-get install -y ffmpeg`). A version or codec difference can silently break renders that work locally.

**Confirm:**
```bash
grep FFMPEG_PATH .env .env.staging          # compare values
docker compose exec api ffmpeg -version     # localhost container version
docker compose -p staging exec api ffmpeg -version   # staging container version
```

**Rule out:** `FFMPEG_PATH` is unset or identical in both envs, and both containers report the same version.

**Findings (2026-05-26):** `FFMPEG_PATH` is not set in `.env` or `.env.staging` — both containers use system `ffmpeg`. Both localhost and staging images report identical version: `7.1.4-0+deb13u1`, same build flags, same gcc. The three untracked static binaries in the repo root (`ffmpeg`, `ffmpeg-static`, `ffprobe-static`) are unreferenced by any code. C2 is not the cause.

**Fix pattern:** rely on the apt-installed binary everywhere (unset `FFMPEG_PATH`), or commit the static binary and set `FFMPEG_PATH` consistently in `.env.example`.

---

#### C3 — `/tmp` video files destroyed on every deploy
**Status:** `CONFIRMED 2026-05-26`

Every `docker compose up --build` recreates the API container and clears `/tmp`. The DB still holds `video_path` rows pointing to those paths. The media endpoint (`/api/media/video/{filename}`) returns 404. The Drive re-download layer (`_resolve_drive_video()` in `runs.py`) should recover — but only if Drive OAuth is connected for the brand on staging, `drive_file_id` was stored in the DB during render, and the Drive token is still valid.

**Confirm:**
```bash
# Check recent runs for drive_file_id
docker compose -p staging exec db psql -U bos -c \
  "SELECT id, brief->>'drive_file_id', brief->>'video_path' FROM runs ORDER BY created_at DESC LIMIT 10;"
```
Open a video run that existed before the deploy. If it fails with 404 and `drive_file_id` is NULL, this is the cause.

**Rule out:** Drive connected, `drive_file_id` populated, re-download succeeds after deploy.

**Critical distinction — confirmed:**
- `docker compose restart api` → same container, `/tmp` survives
- `docker compose up -d --build api` → container recreated, `/tmp` wiped
- `deploy-staging.sh` always uses `up -d --build` → every deploy wipes `/tmp`

**Rule:** never treat `/tmp` as durable storage for anything the user needs to see after a deploy. Drive `drive_file_id` is the only durable reference for video assets. Any run with `video_path` set but `drive_file_id` NULL will have a dead link after the next deploy.

**Fix pattern:** ensure Drive OAuth is active on staging for every video-generating brand. Long-term: treat `/tmp` as cache only — always write to Drive first, serve from Drive URL.

---

#### C4 — Env var in local `.env` but absent from `.env.example`
**Status:** `RULED OUT for Meta + Google Drive (2026-05-26) — mechanism real, not current cause`

`deploy-staging.sh` auto-fills `.env.staging` from `.env.example` defaults. Keys that exist in local `.env` but not in `.env.example` never reach staging. The capability relies on that key and fails silently on staging.

**Confirm:**
```bash
comm -23 <(grep -oE '^[A-Z_]+' .env | sort) \
         <(grep -oE '^[A-Z_]+|^#\s*[A-Z_]+' .env.example | sed 's/^#\s*//' | sort)
```

**Rule out:** every key the affected module uses is present in `.env.example`.

**Findings (2026-05-26):** Twelve keys in local `.env` absent from `.env.example`. Checked against active feature scope (Meta + Google Drive):
- `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI` — all in `.env.example` ✓
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_PICKER_API_KEY` — all in `.env.example` ✓
- Missing keys are Google Analytics (not tested locally) and `GOOGLE_CALENDAR_REDIRECT_URI` (auto-derived from `GOOGLE_REDIRECT_URI`, empty default in `config.py` is safe)

**Rule:** any new env var introduced must be added to `.env.example` the same day (already in CLAUDE.md). Violation of this causes a C4 failure.

---

#### C5 — Untracked plugin files present locally, absent from staging image
**Status:** `RULED OUT (2026-05-26)`

The volume mount makes every file in `./api/` visible locally — including untracked files. The staging image only contains committed files. If a module depends on a file that exists locally but isn't in git, staging fails with FileNotFoundError or silent import failure.

Known untracked files at discovery (2026-05-26) — docs only, no runtime impact:
- `api/plugins/creative-factory/CREATIVE_SUPPLY_CHAIN.md`
- `api/plugins/gmail-auth/GMAIL_INTEGRATION_SPEC.md`
- `api/plugins/gmail/GMAIL_PLUGIN_V0.md`

**Confirm:**
```bash
git ls-files --others --exclude-standard api/plugins/
git ls-files --others --exclude-standard api/capabilities/
```

**Rule out:** every file the module opens or imports at runtime is tracked in git.

**Findings (2026-05-26):** Three untracked files in `api/plugins/`: `CREATIVE_SUPPLY_CHAIN.md`, `GMAIL_INTEGRATION_SPEC.md`, `GMAIL_PLUGIN_V0.md`. Searched all Python files for references — found only in code comments. None are opened or imported at runtime. C5 is not the cause.

**Rule:** if a module reads a file at runtime (config, template, credentials), that file must be committed. Docs and specs are fine untracked.

---

#### C6 — CI deploy silently succeeds while deploy script fails on VDS
**Status:** `CONFIRMED AND FIXED (2026-05-26)`

Every CI run reports green (~55s) but the VDS API container never restarts and new code never loads.

**Root causes (three compounding bugs):**

1. **Bootstrapping loop:** The CI runs `bash deploy-staging.sh` using the *existing script on the VDS*. The old script failed immediately on missing `.env.staging` keys (before reaching `git reset --hard origin/staging`). So the new version of the script — which had auto-fill — could never pull itself. Every CI run ran the same broken old script and exited early.

2. **`appleboy/ssh-action` swallows exit codes:** By default, the action reports success even when the remote script exits non-zero. CI showed green for every broken deploy. Added `script_stop: true` to the action so failures are visible. **Note (2026-06-02):** `script_stop` was removed in `appleboy/ssh-action@v1` — it is not a valid input and produces a warning. The deploy script already uses `set -euo pipefail` which aborts on error. Remove `script_stop: true` from any `appleboy/ssh-action@v1` step.

3. **`docker compose up --build` doesn't recreate containers when image hash is unchanged:** The API Dockerfile rarely changes; Python file changes via volume mount don't change the image digest. Docker Compose saw "image unchanged" and left the running container alone. New code was on disk but never loaded. Added `--force-recreate` to guarantee a fresh container on every deploy.

**Confirm:**
```bash
# Check VDS API uptime — if unchanged across multiple CI runs, containers aren't restarting
curl https://staging.klaroha.com/api/ | python3 -c "import json,sys; print(json.load(sys.stdin)['uptime_seconds'])"
# Check CI run logs — look for the deploy-staging step output, not just green/red
```

**Rule:** CI must pull the latest repo code BEFORE running deploy-staging.sh. The script cannot update itself if it errors before the git reset line. CI workflow now does `git fetch && git reset --hard origin/staging` before `bash deploy-staging.sh`.

**Fixes applied (2026-05-26):**
- `ci.yml`: added `git fetch origin && git reset --hard origin/staging` before `bash deploy-staging.sh`; added `script_stop: true` to SSH action
- `deploy-staging.sh`: added `--force-recreate` to `docker compose up`; removed redundant `docker compose restart nginx` (was causing `set -e` exit on port conflict)

---

#### C7 — Staging DB / brand / objective state differs from localhost
**Status:** `CONFIRMED (2026-06-01)`

The code and containers can be healthy while the two environments still behave differently because they do not share the same database state. This became the confirmed cause for the current localhost-vs-staging media drift after `INC-004`, because staging had been manually recovered and only minimally re-bootstrapped (`PUT /api/workspace/brand`, fresh auth key).

**Typical symptoms:**
- generic artifact titles / generic CMO confirmation text on staging
- `SCOPE brand: My Workspace` on staging while localhost is using a real Brand like `Mactan Group`
- wrong or missing active brand/objective on staging
- localhost shows richer context, products, audiences, docs, and connector state than staging

**Confirm:**
```bash
# Compare these between localhost and staging
curl -s -H "X-API-Key: $KEY" "$BASE/workspace" | jq
curl -s -H "X-API-Key: $KEY" "$BASE/brands" | jq
curl -s -H "X-API-Key: $KEY" "$BASE/objectives/active?brand_id=<brand_id>" | jq
curl -s -H "X-API-Key: $KEY" "$BASE/workspace/documents?brand_id=<brand_id>" | jq
```

**Confirmed findings (2026-06-01):**
- **localhost:** workspace `BOS`; brands `Klaroha`, `Mactan Group`, `MotorMoto`; brand-scoped products/audiences/docs present; recent media runs stored under `Mactan Group`
- **staging:** workspace `My Workspace`; **0 brands**; **0 objectives**; **0 social_connections**; **0 provider_keys**; recent media runs all stored as workspace-scoped with `block_brand_name = "My Workspace"`
- Therefore the current divergence is **state drift, not image/code drift**.

**Rule out:** same workspace name, same Brand rows, same active objective, and same brand-scoped documents/products/audiences exist in both environments.

---

#### C8 — Provider / plugin / social-connection readiness differs across environments
**Status:** `VALIDATED (2026-06-02)`

Localhost and staging keep separate provider keys, plugin vars, OAuth connections, and token refresh state. The deploy can be perfect while the behavior still diverges because the affected specialist is not equally ready in both places.

This explains failures like:
- image/video providers working locally but returning 401 / partial / fallback behavior on staging
- publish actions present locally but blocked or downgraded on staging
- Drive-backed assets or brand accounts available in one env but not the other

**Confirm:**
```bash
curl -s -H "X-API-Key: $KEY" "$BASE/providers" | jq
curl -s -H "X-API-Key: $KEY" "$BASE/plugins" | jq
curl -s -H "X-API-Key: $KEY" "$BASE/social/connections" | jq
```

**Confirmed findings (2026-06-02):**

| Check | Localhost | Staging | Delta |
|---|---|---|---|
| Social connections | 7 rows | 7 rows identical | **parity** (INC-005 restore worked) |
| Gemini provider | `platform_available` | `degraded` (platform=False) | **gap** |
| OpenRouter provider | `platform_available` | `degraded` (platform=False) | **gap** |
| Nvidia / OpenAI | `live` | `live` | parity |
| Google Ads plugin | 0 missing vars | 4 missing vars | **gap** |
| Google Analytics plugin | 0 missing vars | 4 missing vars | **gap** |
| All other plugins | same | same | parity |

All missing vars are present in the local `.env.staging`. The VDS copy was wiped when CI last overwrote it with the stale `STAGING_ENV_FILE` secret. That secret contains only the 6 port overrides + `ENV_FILE`; it is missing `PLATFORM_GEMINI_KEY`, `PLATFORM_OPENROUTER_KEY`, `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`, `GOOGLE_ANALYTICS_CLIENT_ID`, `GOOGLE_ANALYTICS_CLIENT_SECRET`, `GOOGLE_ANALYTICS_REFRESH_TOKEN`, `GOOGLE_ANALYTICS_PROPERTY_ID`.

**Effect on CMO behavior:** any module configured for OpenRouter or Gemini in platform mode fails or falls back to a different backend on staging. Google Ads and Google Analytics specialists are not executable on staging.

**Fix pattern:** update `STAGING_ENV_FILE` GitHub secret to include the full set of staging-critical vars — not just port overrides. The minimum required additions are: `PLATFORM_GEMINI_KEY`, `PLATFORM_OPENROUTER_KEY`, all `GOOGLE_ADS_*`, all `GOOGLE_ANALYTICS_*`.

**Scale alignment:** at 10K orgs, each org has their own `.env` and manages their own keys — there is no CI overwrite. The equivalent problem is an org that hasn't configured their provider keys. F2-2 (admin diagnostic panel) must surface exactly this: which providers are degraded and why, so the org admin self-diagnoses without Klaroha support.

---

#### C9 — Browser-held brand/session state is stale after staging recovery
**Status:** `HYPOTHESIS — OPEN (2026-06-01)`

The frontend stores active brand selection in localStorage (`bos_active_brand`) and keeps per-brand chat history. After a staging DB reset/recovery, the browser can still hold an old `brand_id`, old conversation history, or old pending artifact references that no longer match the recovered DB. The result can look like “deploy drift” even though the new containers are fine.

**Typical symptoms:**
- staging keeps saying `My Workspace` or shows the wrong brand after recovery
- the same prompt behaves differently in a fresh/private window
- Network tab shows `POST /api/chat` or `/api/chat/stream` carrying an unexpected `brand_id`

**Confirm:**
1. Hard refresh and/or open staging in a private window.
2. Clear site storage for `staging.klaroha.com` (especially localStorage key `bos_active_brand`).
3. Re-login and re-select the brand.
4. In DevTools Network, inspect `POST /api/chat` or `/api/chat/stream` and verify the outbound `brand_id`.
5. Compare the resulting `GET /api/runs/{run_id}` payload's `brand_id` and brief context.

**Rule out:** a fresh browser session sends the correct `brand_id` and reproduces the exact same bad behavior.

---

#### C10 — Auto-generated `ENCRYPTION_KEY` is wrong format for BOS secret storage
**Status:** `CONFIRMED AND FIXED IN REPO (2026-06-01)`

`deploy-staging.sh` auto-fills missing `.env.staging` keys from `.env.example`. When `ENCRYPTION_KEY` was missing, it generated `secrets.token_hex(32)` — a 64-character hex string. BOS secret storage uses Fernet, which requires a 32-byte URL-safe base64 key (44 chars). The stack can appear healthy until any provider/plugin/social credential must be encrypted or decrypted.

**Typical symptoms:**
- staging boots and passes smoke tests
- provider/plugin/social credentials are absent or later fail to decrypt
- recovered stacks work as blank workspaces, then secret-backed features break when reconnected/restored

**Confirm:**
```bash
grep '^ENCRYPTION_KEY=' .env.staging | cut -d= -f2 | awk '{print length}'
# 64 = wrong hex token, 44 = Fernet-compatible
```

**Confirmed findings (2026-06-01):**
- localhost `ENCRYPTION_KEY` length: **44** (valid Fernet key)
- staging `ENCRYPTION_KEY` after recovery: **64** (invalid hex token)
- direct decrypt tests against restored `provider_keys` / `social_connections` succeeded only after replacing staging with a valid 44-char Fernet key

**Fix pattern:**
- `deploy-staging.sh` now generates `base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()`
- replace any already-generated 64-char hex `ENCRYPTION_KEY` in `.env.staging` before restoring secret-backed state

---

#### C11 — Staging containers are reading `.env` instead of `.env.staging`
**Status:** `CONFIRMED AND FIXED OPERATIONALLY / FIXED IN REPO (2026-06-01)`

The compose file uses `env_file: ${ENV_FILE:-.env}` for `api` and `relay`. Passing `--env-file .env.staging` only controls compose interpolation unless `ENV_FILE=.env.staging` is also set. If `ENV_FILE` is missing from the staging environment, host ports/images can come from `.env.staging` while the containers themselves silently load secrets/config from `.env`.

**Typical symptoms:**
- `docker compose ... --env-file .env.staging ps` looks correct, but app behavior still reflects the wrong environment
- container `ENCRYPTION_KEY` / provider config hashes do not match `.env.staging`
- restored or re-encrypted credentials still fail with `DECRYPTION_FAILED`

**Confirm:**
```bash
# File value
python3 - <<'PY'
from pathlib import Path
import hashlib
for line in Path('.env.staging').read_text().splitlines():
    if line.startswith('ENCRYPTION_KEY='):
        v=line.split('=',1)[1]
        print('file', len(v), hashlib.sha256(v.encode()).hexdigest())
        break
PY

# Running container value
ENV_FILE=.env.staging docker compose -f docker-compose.yml --env-file .env.staging -p staging exec -T api python - <<'PY'
import os, hashlib
v=os.environ.get('ENCRYPTION_KEY','')
print('container', len(v), hashlib.sha256(v.encode()).hexdigest())
print('ENV_FILE', os.environ.get('ENV_FILE'))
PY
```

**Confirmed findings (2026-06-01):**
- `/root/bos/.env` and `/root/bos/.env.staging` had different `ENCRYPTION_KEY` hashes
- staging `api` container matched `/root/bos/.env`, not `.env.staging`
- after adding `ENV_FILE=.env.staging` and recreating `api`/`relay`, the container hash matched `.env.staging` and brand-scoped `/chat` worked again

**Fix pattern:**
- `deploy-staging.sh` now exports `ENV_FILE=.env.staging` before all compose commands
- add `ENV_FILE=.env.staging` to the real staging env file / GitHub secret for belt-and-suspenders
- for manual staging commands, prefix with `ENV_FILE=.env.staging`

---

#### C12 — Push/deploy trigger gap: GitHub green ≠ staging updated
**Status:** `HISTORICAL ROOT CAUSE / STILL CHECK FIRST (confirmed 2026-06-02; auto-deploy restored by 2026-06-12)`

Original failure mode: pushing to `staging` built GHCR images but did **not** update `staging.klaroha.com`; deploy was `workflow_dispatch` only. That left staging running old code indefinitely after apparently successful pushes.

Current workflow: pushes to `staging` now run `build-and-push` and then `deploy-staging-auto`. The updated failure mode is narrower but still common: **a green test/build or a completed `git push` is not proof that staging updated**. Only the deploy job plus the runtime health fingerprint prove it.

**Confirm:**
```bash
# 1) Confirm the deploy job, not just tests/build, completed for the commit
gh run list --branch staging --limit 5

# 2) Confirm runtime freshness from outside the container
curl -s https://staging.klaroha.com/api/ | jq '{git_sha, uptime_seconds}'
# git_sha must match the pushed/deployed SHA; uptime_seconds should be low after a deploy
```

**Rule:** Never report staging as reflecting a change unless `GET /api/` returns the expected `git_sha` and fresh `uptime_seconds`. If tests/build are green but `git_sha` is old, staging did not update. If `git_sha` is correct but behavior differs, move to config/state drift causes (C7/C8/C18/C19) instead of code drift.

**Scale alignment:** At 100s of org deployments/day, the equivalent gap is a new org pressing "Install" and getting an old version. The fix is automated deploy reconciliation plus runtime version fingerprinting, not manual SSH confirmation.

---

#### C13 — Runtime version fingerprint missing or wrong
**Status:** `FIXED IN REPO / STILL A DIAGNOSTIC SIGNAL (2026-06-12)`

Historical failure: `GET /api/` only returned static `version = "0.1.0"`, so old and new containers looked identical from outside.

Current expected behavior: CI bakes `GIT_SHA` into the API image and `GET /api/` returns `git_sha`. If `git_sha` is missing, `dev`, or not the expected commit, the runtime is not the CI-built artifact you think it is.

**Confirm:**
```bash
curl -s https://staging.klaroha.com/api/ | jq '{version, git_sha, uptime_seconds}'
```

**Interpretation:**
- `git_sha == expected commit` → code artifact is current; investigate config/state/session drift next.
- `git_sha == "dev"` → image was built locally on the server, bypassing CI.
- `git_sha missing` → stale image or stale health code; deploy verification is not trustworthy.
- `git_sha old` → deploy job did not update the running API image.

---

#### C14 — Uvicorn hot-reload silently dies; localhost runs stale code
**Status:** `HYPOTHESIS — OPEN (2026-06-02)`

Uvicorn `--reload` (watchfiles) monitors `.py` files. When a syntax error is introduced, the reload fails silently — the container keeps responding to HTTP using the last successfully-loaded code version. No browser error, no container crash, no alert. The API returns HTTP 200 while running old code.

New directories added to `api/capabilities/` after container start may also not be auto-detected if watchfiles has already enumerated the file tree at startup.

**Confirm:**
```bash
docker compose logs api --tail=50 | grep -E "Reload|reload|error|Error|Traceback|WARNING"
# "WatchFiles detected changes" present = reload fired
# Absence = reload silently failed or never fired
```

**Rule:** After adding new directories or suspecting a reload failure, `docker compose restart api` for a guaranteed clean module load.

**Scale alignment:** At org scale, this becomes a first-boot reliability issue — the operator's first deploy must load all modules correctly, without a silent failure requiring a restart that no documentation mentions.

---

#### C15 — Frontend web/ changes require manual container rebuild; neither env applies them automatically
**Status:** `CONFIRMED STRUCTURAL (2026-06-02)`

`web/` is a static Vite build baked into a Docker image at build time. There is no HMR through Docker to the host. Any change to `web/src/**` on localhost requires:
```bash
docker compose build web && docker compose up -d web
```

The API hot-reloads (Python watchfiles via volume mount). The frontend does not. Developers and agents assume all changes are instant because the API is instant, make frontend edits, see no change, and diagnose the wrong layer.

On staging: `deploy-staging.sh` uses `--no-build` and pulls pre-built GHCR images. If the `build-and-push` CI job has not completed when a manual deploy runs, staging pulls the old `:staging` image.

**Rule:** Any change to `web/` must be followed by the rebuild command on localhost. On staging, confirm CI `build-and-push` completed before running `deploy-staging.sh`.

---

#### C16 — `check-staging.sh` can still be a false positive if run from the wrong repo/path
**Status:** `PARTIALLY FIXED / STILL CHECK PATH (2026-06-12)`

Historical failure: `check-staging.sh` confirmed availability only, not code version. It could pass on month-old code.

Current expected behavior: `check-staging.sh` prints API `uptime_seconds` and `git_sha`, and compares `git_sha` when `DEPLOY_SHA` is provided. That closes the old verification gap **only if the script is run against the same path and env file that CI deployed**.

**Remaining false-positive mode:** local scripts still assume `~/bos/.env.staging` in places. If CI deploys to `STAGING_PATH=/root/bos-staging` but a check reads `~/bos/.env.staging`, the check can validate the wrong environment file and mislead the operator.

**Confirm:**
```bash
pwd
realpath .env.staging
DEPLOY_SHA=<expected_sha> bash check-staging.sh
curl -s https://staging.klaroha.com/api/ | jq '{git_sha, uptime_seconds}'
```

**Rule:** `check-staging.sh` output is authoritative only when it prints the expected `git_sha` and is reading the same `.env.staging` used by the deployed compose project.

---

#### C17 — Deploy freshness signal missing from the actual run output
**Status:** `FIXED IN REPO / STILL A STALE-SCRIPT SIGNAL (2026-06-12)`

Historical failure: `uptime_seconds` was the only freshness signal and nothing surfaced it automatically.

Current expected behavior: `deploy-staging.sh` prints a final summary containing image tag, `git_sha`, and `uptime_seconds`; `check-staging.sh` also prints `uptime_seconds` and `git_sha`.

**Confirm:** after deploy, the log should end with something like:
```text
Staging deploy complete
image:          ghcr.io/itsborj/bos-api:sha-<sha>
git_sha:        <sha>
uptime_seconds: <low_number>s
```

**Interpretation:** If the deploy log does not print these fields, CI may be running an old deploy script or the script is being launched from the wrong checkout/path (see C19).

---

#### C18 — `STAGING_ENV_FILE` blank/partial; CI rewrites staging into a degraded config every deploy
**Status:** `CONFIRMED — OPEN (2026-06-12)`

**Related context:** commit `8c5e9af` relaxed `deploy-staging.sh` so an explicitly provided container DB URL like `postgresql://bos:bos@db:5432/bos` no longer fails the second validation pass. This removes one false deploy blocker, but it also means env validation must rely on explicit required-key presence checks rather than treating `bos:bos` as automatically invalid.

GitHub Actions writes the `STAGING_ENV_FILE` secret to `.env.staging` on every staging deploy. If that secret is blank or missing required keys, any manual VDS repair is erased on the next push. The stack may still boot because `deploy-staging.sh` enforces ports and auto-fills some `.env.example` defaults, but secret-backed behavior drifts immediately.

**Typical symptoms:**
- staging loads but providers/plugins are degraded or missing
- `API_SECRET_KEY`, `ENCRYPTION_KEY`, `PLATFORM_*`, OAuth, Ads, Analytics, or provider vars disappear after push
- deploy logs show `.env.staging` being rewritten before `deploy-staging.sh`
- localhost works because local `.env` has keys; staging falls back to blanks/defaults

**Confirm without leaking secrets:**
```bash
# CI side: confirm STAGING_ENV_FILE is not blank; do not print secret values
# VDS side: count required keys, not values
grep -E '^(ENV_FILE|API_SECRET_KEY|ENCRYPTION_KEY|DATABASE_URL|DB_PORT|API_PORT|WEB_PORT|NGINX_PORT|PUBLIC_PORT|PLATFORM_GEMINI_KEY|PLATFORM_OPENROUTER_KEY)=' .env.staging | cut -d= -f1

# Runtime side: compare readiness, not secret contents
curl -s -H "X-API-Key: $KEY" "$BASE/providers" | jq
curl -s -H "X-API-Key: $KEY" "$BASE/plugins" | jq
```

**Rule:** The GitHub secret is the source of truth. Manual edits to `.env.staging` on the VDS are temporary and will be overwritten. A deploy must fail closed if `STAGING_ENV_FILE` is empty or missing critical keys; it must not silently bootstrap a degraded staging environment.

**Fix pattern:** update GitHub Actions secret `STAGING_ENV_FILE` with the full known-good staging env; add a CI/deploy guard that checks required key names are present before writing or using the file. Never echo secret values in logs.

---

#### C19 — CI and deploy scripts may operate on different checkouts (`STAGING_PATH` vs hard-coded `~/bos`)
**Status:** `HYPOTHESIS — OPEN (2026-06-12)`

The workflow deploy step uses the `STAGING_PATH` secret, writes `$STAGING_PATH/.env.staging`, `cd`s into `$STAGING_PATH`, and then runs `bash deploy-staging.sh`. But `deploy-staging.sh` currently starts with `cd ~/bos`, and `check-staging.sh` also assumes `~/bos/.env.staging` in places.

If `STAGING_PATH` is anything other than `~/bos` (for example `/root/bos-staging`), CI can reset and write env into one checkout, then the deploy script silently switches to another checkout/env file. That produces classic drift: the GitHub run looks correct, but the container was started from a different repo path or config file.

**Confirm:**
```bash
# In CI logs or on VDS, compare these paths
printf 'STAGING_PATH=%s\n' "$STAGING_PATH"
realpath "$STAGING_PATH"
realpath ~/bos
head -5 "$STAGING_PATH/deploy-staging.sh"

# Runtime proof remains the health fingerprint
curl -s https://staging.klaroha.com/api/ | jq '{git_sha, uptime_seconds}'
```

**Rule:** Deploy scripts must run from the current checkout passed by CI, not a hard-coded home path. If a script needs a path, CI must pass it explicitly and the script must print `pwd` before mutating anything.

**Fix pattern:** remove `cd ~/bos` from deploy/check scripts or replace it with `cd "${BOS_DEPLOY_PATH:-$(pwd)}"`; make CI export `BOS_DEPLOY_PATH="$STAGING_PATH"`; print `pwd`, `git rev-parse HEAD`, and `realpath .env.staging` at deploy start.

---

#### C20 — Staging white screen from frontend asset/runtime failure
**Status:** `CONFIRMED — FIX IN PROGRESS (2026-06-13)`

`staging.klaroha.com` can show a blank/white screen even when API health is green if the browser cannot load or execute the Vite bundle. Prior INC-008 confirmed one version of this class: Cloudflare returned 502 for the JS bundle when nginx served large assets without correct compression/MIME/cache headers. The same user-visible symptom can also come from a JS runtime exception, stale Cloudflare/browser cache serving an old bundle, a web/API contract mismatch, or deploying API and web images from different SHAs.

**Typical symptoms:**
- public page is white/blank but `/api/` returns JSON
- browser console shows a React error, MIME error, `ERR_QUIC_PROTOCOL_ERROR`, or failed `/assets/index-*.js`
- `curl https://staging.klaroha.com/assets/...` differs from origin `curl http://127.0.0.1:8091/assets/...`
- API `git_sha` is current but the web bundle is stale or incompatible

**Offline-first confirm:**
```bash
# Local/offline reproduction before touching staging
cd web && npm ci --silent && npx tsc -b && npm run build

# Read-only staging checks only; no server mutation
curl -s https://staging.klaroha.com/api/ | jq '{git_sha, uptime_seconds}'
curl -I https://staging.klaroha.com/
# Then inspect browser DevTools Console + Network for the first failing JS/CSS/API request.
```

**Findings (2026-06-13):** staging API and deploy fingerprint were healthy at commit `dcd821a`, but browser automation reproduced a blank `#root` when `/assets/index-Qw00dZ5e.js` failed with `net::ERR_HTTP2_PROTOCOL_ERROR` / `net::ERR_QUIC_PROTOCOL_ERROR` through Cloudflare. The Vite entry bundle was 733.84 kB minified (182.25 kB gzip). Route-level lazy loading reduced the entry bundle to 348.27 kB minified (99.54 kB gzip) and split pages into small route chunks.

**Rule:** Do not patch files directly on the VDS and do not bypass CI. If the fix is in `web/`, commit it, push to `staging`, let CI build the web image for that SHA, then verify `GET /api/` `git_sha` and the browser asset load. If the fix is config/CDN, document the exact non-code change and add an automation/backlog item.

---

#### C21 — Auth boundary degraded: staging accepts unintended BOS API keys/login attempts
**Status:** `HYPOTHESIS — OPEN / SECURITY-SENSITIVE (2026-06-12)`

**Related context:** commit `be0d1ba` fixed the frontend manual-key login path so `Auth.tsx` calls `validateKey()` before storing a typed key and navigating to `/cmo`. Before that commit, any non-empty typed key was accepted client-side. This explains the prior "any key logs in" symptom at the UI layer, but it does **not** prove the backend auth boundary is correct; backend protected endpoints still need negative fake-key tests.

A staging deploy with blank/partial env can accidentally weaken the auth boundary. If `API_SECRET_KEY`, DB-backed auth keys, encryption state, or auth configuration is reset/defaulted by `STAGING_ENV_FILE`, staging may appear to allow unintended BOS API login/API-key access. This is related to C18 but tracked separately because it is security-sensitive and must be tested without leaking real keys.

**Typical symptoms:**
- requests with an arbitrary or stale `X-API-Key` succeed on staging
- login/API-key checks behave differently between localhost and staging
- `check-staging.sh` auth boundary check is skipped, points at the wrong `.env.staging`, or validates only unauthenticated rejection while unintended authenticated keys still pass
- staging was recently redeployed after `STAGING_ENV_FILE` was blank/partial

**Offline/read-only confirm:**
```bash
# Negative auth test: arbitrary key must fail
curl -s -o /dev/null -w '%{http_code}\n' \
  -H 'X-API-Key: definitely-not-a-real-key' \
  https://staging.klaroha.com/api/brands
# Expected: 401 or 403. Any 200 is a security incident.

# Positive auth should use only a known staging test key, never printed in logs.
# Do not echo API_SECRET_KEY or real auth keys into CI/GitHub logs.
```

**Rule:** Do not "fix" auth by manually editing `.env.staging` on the VDS as the final answer. The durable fix must be committed/pushed if code-related, or the GitHub secret / deployment-key system must be updated as source of truth. Any confirmed auth bypass must get an incident entry and a backlog automation item before being marked resolved.

---

#### C22 — GHCR image push failure after successful git push (`unknown blob`)
**Status:** `CONFIRMED — OPEN (2026-06-12)`

A local `git push origin staging` can succeed while the staging deploy still fails before reaching the server. In CI run `27393507882` for commit `c94e148`, tests passed and the API Docker image built, but pushing the image to GHCR failed with `ERROR: failed to build: unknown blob`. Because `build-and-push` failed, `deploy-staging-auto` never ran and `staging.klaroha.com` remained on the previous/broken runtime.

**Typical symptoms:**
- local `git push` output says the branch updated successfully
- GitHub run shows failure in `Build & push images`, before SSH deploy
- no new runtime `git_sha` appears on `/api/`
- staging may remain white-screen/502 because the failed run did not change the server

**Confirm:**
```bash
gh run list --branch staging --limit 5
gh run view <run_id> --log-failed
curl -sS -i https://staging.klaroha.com/api/ | head -40
```

**Interpretation:** This is not a git failure and not a VDS deploy failure. It is a registry/image-publish failure. The commit is in GitHub, but the deploy artifact was not published, so the server has nothing new to pull.

**Rule:** Never equate "push succeeded" with "staging deployed". A successful staging deploy requires: GitHub run green, images published, deploy job completed, and `GET /api/` returning the pushed `git_sha`.

**Fix pattern:** first retry the failed GitHub Actions run if the error is a transient GHCR `unknown blob`. If it recurs, investigate buildx/GHCR cache/provenance settings and consider disabling provenance or changing build-push cache behavior. Do not patch the VDS manually to compensate for a missing image artifact.

---

#### C23 — Deploy job reports success even when post-deploy API health is missing
**Status:** `CONFIRMED — OPEN (2026-06-12)`

A staging deploy can be marked green by GitHub Actions even when `deploy-staging.sh` fails to parse a valid API health response. In run `27393813054`, images built and containers started, but the final deploy summary printed `git_sha: missing` and `uptime_seconds: ?s`. The SSH action still reported success, while public `https://staging.klaroha.com/api/` returned Cloudflare 502 immediately after deploy.

**Typical symptoms:**
- GitHub Actions deploy job is green
- deploy log final summary has `git_sha: missing` or `uptime_seconds: ?s`
- public API returns 502 or non-JSON
- staging homepage may return 200 while `/api/` is broken, causing a white screen after React boot/API calls

**Confirm:**
```bash
gh run view <run_id> --log | grep -E 'Staging deploy complete|git_sha:|uptime_seconds:'
curl -sS -i https://staging.klaroha.com/api/ | head -40
```

**Rule:** A deploy must not be considered successful unless post-deploy health returns JSON with `status=ok`, expected `git_sha`, and low `uptime_seconds`. `git_sha: missing` is a failed deploy, not a warning.

**Fix pattern:** make `deploy-staging.sh` fail closed when health JSON is missing/invalid or `git_sha != DEPLOY_SHA`; add a short readiness retry loop before evaluating health so normal API boot time does not produce false failures.

---

#### C24 — Alembic version id exceeds `alembic_version.version_num VARCHAR(32)`
**Status:** `CONFIRMED — OPEN (2026-06-12)`

Staging API can fail to boot during migrations if a migration revision id is longer than Alembic's default `alembic_version.version_num` length. Run `27394391729` exposed this after C23 made deploy health fail closed: migration `039_cleanup_fuzzer_data_stream_dedupe` ran, then Alembic attempted to update `alembic_version.version_num` to that 37-character id and PostgreSQL raised `StringDataRightTruncationError: value too long for type character varying(32)`.

**Typical symptoms:**
- API container starts, then exits/restarts or never becomes reachable
- nginx reports `api could not be resolved`, connection refused, or upstream timeout
- deploy health loops until failure
- API logs show `UPDATE alembic_version SET version_num='039_cleanup_fuzzer_data_stream_dedupe'` followed by `value too long for type character varying(32)`

**Confirm:**
```bash
gh run view <run_id> --log-failed | grep -E 'alembic_version|StringDataRightTruncation|value too long'
```

**Rule:** Keep migration revision identifiers <= 32 characters unless the migration widens `alembic_version.version_num` before Alembic records the new revision. This is independent of plugin/specialist loading and must be fixed before debugging zero specialists.

**Fix pattern:** in the first long-id migration, alter `alembic_version.version_num` to a wider type before any other work. Do not manually update the version table on staging as the durable fix.

---

#### C25 — Staging has zero specialists/plugins loaded
**Status:** `PARTIALLY RULED OUT — PLUGIN DISCOVERY OK; UI/API PERCEPTION STILL TO VERIFY (2026-06-12)`

After API health is restored, staging may still show **0 specialists** if plugin discovery is pointed at the wrong directory, plugin metadata fails validation, internal plugins are intentionally disabled, or the staging env/DB state has no activated plugins. This must be debugged separately from API availability; do not mix it with white-screen/API/migration fixes.

**Findings (2026-06-12):** deploy run `27395023837` added a read-only plugin discovery check inside the running API container. It found `/external_plugins` mounted, 8 `channel.json` packages, 8 loaded plugins, and 0 plugin loader errors: `creative.factory`, `channel.gbp-completeness`, `google.drive`, `channel.hello`, `media.image`, `media.video`, `channel.meta`, `channel.youtube`. Therefore the backend plugin discovery layer is **not zero**. If the UI still shows zero specialists, the next layer is authenticated `/api/plugins` response, brand activation filtering, frontend rendering/state, or stale browser/session state.

**Related context:** `deploy-staging.sh` rewrites `EXTERNAL_PLUGINS_PATH` to `$(pwd)/plugins`, while `docker-compose.yml` mounts `${EXTERNAL_PLUGINS_PATH}` into the API container as `/external_plugins` and plugin loader reads `EXTERNAL_PLUGINS_DIR=/external_plugins`. `.env.example` also has `KLAROHA_LOAD_INTERNAL_PLUGINS=false`, so bundled `api/plugins/` are skipped by default unless explicitly enabled.

**Typical symptoms:**
- Admin/Specialists page shows zero specialists or zero plugins
- `/api/plugins` returns an empty list despite API health being ok
- `/api/agent/capabilities` count is unexpectedly low
- deploy logs show `EXTERNAL_PLUGINS_PATH` pointing at a path with no valid plugin packages
- plugin loader logs show packages skipped due to missing/invalid `plugin.yaml`, no capabilities, or import errors

**Offline/read-only confirm:**
```bash
# First prove API is healthy and deployed; do not debug specialists while /api/ is 502.
curl -s https://staging.klaroha.com/api/ | jq '{git_sha, uptime_seconds}'

# Offline repo checks: confirm plugin package files exist and are tracked.
find plugins -maxdepth 3 -name 'plugin.yaml' -o -name 'plugin.yml'
git ls-files plugins | head

# Authenticated staging checks require a known staging key; never print it in logs.
curl -s -H "X-API-Key: $KEY" https://staging.klaroha.com/api/plugins | jq
curl -s -H "X-API-Key: $KEY" https://staging.klaroha.com/api/agent/capabilities | jq 'length'
```

**Rule:** Fix one layer at a time. Do not enable `KLAROHA_LOAD_INTERNAL_PLUGINS=true` as a blanket staging workaround unless the goal is explicitly to load deprecated bundled examples; that can make Admin show the wrong set of specialists. The durable fix is to make the intended external plugin packages discoverable and valid in the deployed artifact.

**Fix pattern:** verify the mounted `/external_plugins` path contains valid tracked plugin packages, then fix plugin packaging/metadata or deploy path env as code. Add a post-deploy check for plugin/capability count once the intended minimum is defined.

---

#### C26 — No single localhost → GitHub → staging → browser sync ledger
**Status:** `PARTIALLY IMPLEMENTED — LOCAL SCRIPT ADDED (2026-06-13)`

BOS currently has several good individual deploy signals, but no single command that proves all sync layers match. This creates repeated frustration: `git push` may succeed, GitHub Actions may be green, and `/api/` may report the expected `git_sha`, while the frontend bundle, browser/CDN cache, env config, plugin readiness, or DB state is still divergent.

**Typical symptoms:**
- “localhost and staging are never in sync” despite a recent commit/push
- API health is green but the page is white, stale, or behavior differs
- deploy logs show the correct API SHA but the browser is loading an old or failing JS asset
- GitHub Actions is green but no one can answer which local commit, web bundle hash, runtime API SHA, plugin count, and browser-loaded asset are actually active
- agents report “deployed” based on one layer instead of proving all layers

**Required solution: `check-sync.sh`**

Add one operator command that compares all required layers without leaking secrets:

```bash
./check-sync.sh
```

**Local implementation (2026-06-13):** `check-sync.sh` now performs the local build, GitHub Actions run/SHA check, staging API SHA check, web entry asset comparison, JS asset HTTP check, fake-key auth rejection, optional authenticated plugin count (`STAGING_API_KEY=...`), and a Playwright browser load check. GHCR manifest verification warns instead of failing when the local Docker client is not authenticated; use `STRICT_GHCR=1` to make private-manifest auth failures fail closed. Remaining work: wire the same checks into CI post-deploy.

Minimum output:

```text
LOCAL
  branch: staging
  head: <sha>
  dirty: no
  web build: ok
  web entry bundle: /assets/index-<hash>.js

GITHUB
  latest staging run: success
  run sha: <sha>
  images published: api/web/relay

STAGING
  api git_sha: <sha>
  api uptime: <seconds>
  web index asset: /assets/index-<hash>.js
  js asset status: 200
  js asset browser load: ok
  plugins: <count>
  fake API key rejected: yes
```

**Fail conditions:**
- local branch is not `staging` when checking staging
- local tree is dirty unless explicitly allowed
- local `HEAD`, latest successful GitHub staging run SHA, and staging API `git_sha` differ
- local Vite build fails
- staging `index.html` references an asset that does not return HTTP 200
- headless browser cannot load the staging page or `#root` stays empty
- any `/assets/*.js` request fails in browser automation
- fake API key returns anything other than 401/403 on a protected endpoint
- plugin count is below the expected minimum once that minimum is defined

**Rule:** Do not say “staging is synced” or “the deploy worked” unless this sync check passes. API `git_sha` is necessary but not sufficient; it proves only the API image, not the frontend, CDN/browser asset load, config readiness, or state parity.

**Scale alignment:** At 10K org scale, support cannot SSH into individual deployments to infer drift. Each deployment needs a machine-readable sync report that an operator can run and share without exposing secrets.

**Fix pattern:** implement `check-sync.sh` as a local/read-only script first, then wire the same checks into CI post-deploy. Keep secret checks to key-name presence/counts and readiness endpoints; never echo secret values.

---

### Process of Elimination

When a feature breaks after a staging deploy, work through in this order:

1. **C26** — If there is any doubt about localhost → staging sync, run the sync ledger first (`./check-sync.sh` once implemented). Do not rely on a single signal.
2. **C13/C12** — Prove the running code first: `curl -s https://staging.klaroha.com/api/ | jq '{git_sha, uptime_seconds}'`. If `git_sha` is old/missing/`dev`, this is deploy/code drift. Check the deploy job for that SHA.
3. **C22** — If `git push` succeeded but staging did not change, check GitHub Actions for image build/push failures such as GHCR `unknown blob` before investigating the VDS.
4. **C23** — If GitHub deploy is green but `/api/` is 502 or deploy summary says `git_sha: missing`, treat the deploy as failed and inspect post-deploy API/container logs read-only.
5. **C24** — If API logs show Alembic `value too long for type character varying(32)`, fix migration version storage before investigating UI/plugins.
6. **C21** — If auth/login/API-key behavior is permissive, run only negative read-only auth tests with fake keys first. Any fake key returning 200 is a security incident.
7. **C20** — If the symptom is a white screen, inspect browser console/network and asset headers; reproduce the web build locally before touching staging.
8. **C25** — If API is healthy but Specialists/Admin shows zero, debug plugin discovery/activation only; do not mix with provider-key or brand-state drift yet.
9. **C19** — If CI says it deployed the SHA but runtime disagrees, verify CI and scripts are using the same checkout path (`STAGING_PATH` vs `~/bos`) and the same `.env.staging`.
10. **C18** — If `git_sha` is correct but behavior is degraded, check whether `STAGING_ENV_FILE` rewrote `.env.staging` blank/partial and removed provider/plugin/API/encryption keys.
11. **C6** — If deploy jobs run but containers do not restart or ports are stuck, inspect the CI deploy logs and Docker container state.
12. **C1** — `git diff origin/staging -- api/ web/ plugins/` — uncommitted local edits were not deployed.
13. **C15** — Did the change touch `web/`? Rebuild local web manually; on staging, confirm the web image for the same SHA was built before deploy.
14. **C14** — API returning old responses on localhost despite edits? Check `docker compose logs api` for reload failures and restart API.
15. **C3** — Pre-deploy video assets — check Drive connectivity + `drive_file_id` in DB.
16. **C4/C8** — diff local `.env` against `.env.example` and compare `/providers`, `/plugins`, `/social/connections` readiness.
17. **C2/C5** — only if render/import/file errors point there; compare ffmpeg versions and untracked runtime files.
18. **If deploy + smoke are green but behavior still differs, stop treating it as a pure deploy problem and run the Behavior Parity Checklist below.**

### Behavior Parity Checklist — deploy is green, output still differs

Use this when `bash check-staging.sh` passes, containers are healthy, but localhost and staging still produce different CMO/artifact behavior.

1. **Record the repro exactly** — prompt text, environment, clock time, artifact ID, run ID, and brand selected in the UI.
2. **Prove staging is actually the new stack** — `bash check-staging.sh`, `docker compose ... ps`, and API uptime near-zero after deploy.
3. **Clear browser-held state** — hard refresh, private window, clear `bos_active_brand`, re-login, re-select brand.
4. **Inspect the actual chat request** — in DevTools Network, verify `POST /api/chat` or `/api/chat/stream` is sending the expected `brand_id` and not replaying stale history/context.
5. **Compare workspace/brand/objective data** — `/workspace`, `/brands`, `/objectives/active`, `/workspace/documents` on localhost vs staging.
6. **Compare specialist readiness** — `/providers`, `/plugins`, `/social/connections` on localhost vs staging.
7. **Compare the run payload, not just the card text** — `GET /api/runs/{run_id}?include_assets=false` and inspect `brand_id`, `brief`, `result.block`, `self_check`, `error`, `drive_file_id`, and provider/mode fields.
8. **Tail staging API logs during the repro**:
```bash
docker compose -f docker-compose.yml --env-file .env.staging -p staging logs -f api
```
9. **Only after steps 1–8 match should you assume code/image drift.** Most post-recovery differences are state/session/connector drift first.

---

### Incident Log

> One entry per incident. Never delete. Closed entries stay.

#### Pre-history — 2026-05-17 (before this runbook existed)

Three failure modes discovered manually during early staging setup:

- **Wrong stack:** Running `docker compose build web && docker compose up -d web` (no `-p`/`-f` flags) rebuilt the `bos` (production) stack instead of staging. Both stacks live in `~/bos/` so the working directory gives no hint. **Rule:** always use `-p staging --env-file .env.staging` for staging operations.
- **Divergent branches:** Server's local `staging` branch had commits not on the remote (or vice versa). `git pull` refused without a reconciliation strategy, leaving the build running stale code. **Rule:** use `git fetch origin && git reset --hard origin/<branch>` for all server deploys. The server is not a development machine.
- **Fully cached build despite new code:** `git pull` failed silently (divergent branches), but `docker compose build` still ran — on the old code. All layers showed `CACHED`. **Tell:** build context transfer stays tiny (~324kB) and every step is `CACHED`. A real rebuild transfers more context and re-executes `COPY . .` and `RUN npm run build`. **Fix:** always confirm `git reset --hard origin/<branch>` ran successfully before building.

---

#### INC-001 — 2026-05-26 — C1 confirmed: uncommitted local edit not present on staging

- **Cause confirmed:** C1 — Uncommitted local edits not on staging branch
- **Confirmed by:** Controlled experiment. Added `[C1-TEST]` to the `description` field in `api/main.py` without committing. Verified localhost API (`port 8000`) returned the new string. Ran `deploy-staging.sh`. Staging API (`port 8001`) returned the original string with no `[C1-TEST]`. Additionally, `git reset --hard origin/staging` wiped the change from the local filesystem as a side effect — the DEPLOY.md runbook section written earlier in the same session was also lost, a collateral C1 example.
- **Resolved by:** N/A — controlled experiment, no production breakage. Rule established: commit and push before every staging deploy.
- **Notes:** Pydantic Settings env vars override class defaults — `APP_VERSION` in `.env` masked a first attempt using `config.py`. Changed test target to a hardcoded string in `main.py` which has no env override.

---

#### INC-002 — 2026-05-26 — C3 confirmed: /tmp is wiped on every deploy

- **Cause confirmed:** C3 — `/tmp` video files destroyed on every deploy
- **Confirmed by:** Controlled experiment. Created `/tmp/bos_c3_probe.txt` inside the API container. Ran `docker compose restart api` → file survived (same container, filesystem intact). Ran `docker compose up -d --build api` (what `deploy-staging.sh` uses) → file gone on the next exec into the container. The recreate step creates a fresh container from the image; `/tmp` is not a mounted volume, so it starts empty every time.
- **Resolved by:** N/A — controlled experiment. Rule established: `/tmp` is ephemeral across deploys. `drive_file_id` is the only durable video reference.
- **Notes:** `restart` vs `up --build` is the key distinction. Restart keeps the container alive (just stops/starts the process). Build recreates the container from scratch. The deploy script always uses build.

---

#### INC-003 — 2026-05-26 — C6 confirmed: CI silently broken for 14+ hours; VDS running stale code

- **Cause confirmed:** C6 — CI deploy silently succeeds while deploy script fails on VDS
- **Symptom:** VDS `staging.klaroha.com` was running a 14-hour-old build. `creative.shortform.video` module (added in commit `7bb20bc`) was absent from VDS capabilities despite 10+ subsequent CI runs all showing green. User discovered the issue when video dispatch worked in CMO (ISS-009 fixed) but the actual module was not found on VDS.
- **Root cause:** Three compounding bugs — see C6 above.
- **Confirmed by:** VDS API uptime was unchanged (875 min) across multiple CI runs. Direct `GET /agent/capabilities` on VDS showed 29 capabilities without `creative.shortform.video`. Direct execute returned `{"detail":"Module 'creative.shortform.video' not found"}`.
- **Resolved by:**
  1. `ci.yml` — added `git fetch origin && git reset --hard origin/staging` before `bash deploy-staging.sh`; added `script_stop: true`
  2. `deploy-staging.sh` — added `--force-recreate`; removed `docker compose restart nginx`
  3. VDS `.env.staging` — manually updated `NGINX_PORT=8080` → `8091` via SSH (file is gitignored)
  4. VDS — manual `git fetch && git reset --hard origin/staging && bash deploy-staging.sh` to bootstrap out of the loop; followed by `docker compose up -d --force-recreate --remove-orphans` to clear a stale container reference
- **Notes:** The stale container error (`No such container: 0a12b98f…_staging-api-1`) is a Docker Compose artefact from a previous failed/interrupted run. `--remove-orphans` clears it. Future deploys use `--force-recreate` which handles this automatically.

#### INC-004 — 2026-06-01 — STAGING_ENV_FILE missing staging port overrides; stack stuck in `Created`

- **Cause confirmed:** `STAGING_ENV_FILE` / `.env.staging` lost explicit staging host-port overrides, so docker-compose fell back to production defaults.
- **Symptom:** Public `staging.klaroha.com` returned 502 while host nginx itself was healthy. On the VDS, only `staging-redis-1` and `staging-relay-1` were running; `staging-db-1`, `staging-api-1`, `staging-web-1`, `staging-public-1`, and `staging-nginx-1` were stuck in `Created`. `ss -lntp` showed nothing listening on `5433/8001/5174/8091/3001`, and `curl http://127.0.0.1:8091/` failed with connection refused.
- **Confirmed by:** `.env.staging` contained `FRONTEND_URL=https://staging.klaroha.com` but no `DB_PORT`, `API_PORT`, `WEB_PORT`, `NGINX_PORT`, or `PUBLIC_PORT` entries. After restoring `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, and `PUBLIC_PORT=3001`, the staging stack came up immediately and `check-staging.sh` passed 13/13 checks.
- **Resolved by:**
  1. Back up `.env.staging`
  2. Re-add the five staging host-port overrides plus SHA-pinned image tags
  3. `docker compose -p staging -f docker-compose.yml --env-file .env.staging down`
  4. `docker compose -p staging -f docker-compose.yml --env-file .env.staging up -d --no-build --force-recreate`
  5. Run `bash check-staging.sh`
  6. Because the recovered staging DB had no workspace/auth state, bootstrap minimal workspace state with `PUT /api/workspace/brand` using the env `API_SECRET_KEY`, then create a fresh DB-backed login key via `POST /api/auth/keys`
- **Notes:** Manual edits to `.env.staging` on the VDS are temporary. The GitHub Actions secret `STAGING_ENV_FILE` must be updated with the same five port vars before the next push or CI will overwrite the file and re-break staging.

#### INC-005 — 2026-06-01 — Deploy green, but staging media behavior still diverges from localhost

- **Status:** Core parity restored; browser/UI retest still recommended.
- **Symptom:** Manual staging deploy succeeded (`check-staging.sh` 13/13, 36 capabilities loaded, fresh containers), but user-facing behavior still differed from localhost for media prompts. Staging produced generic confirmations such as `The Video Generation Artifact is ready for your review.` / `Image Generation Artifact is ready for review in the Stream.` and exposed `SCOPE brand: My Workspace`, while localhost had real brand-scoped media runs for `Mactan Group`.
- **Cause confirmed:** C7 — staging database/state drift after `INC-004` recovery.
- **Confirmed by:** Direct VDS DB inspection. Staging workspace was `My Workspace` with **0 brands**, **0 objectives**, **0 social_connections**, and **0 provider_keys**. Recent staging media runs were all workspace-scoped (`brand = (workspace)`, `block_brand_name = "My Workspace"`). Localhost, by contrast, had workspace `BOS`, brands `Klaroha` / `Mactan Group` / `MotorMoto`, brand-scoped context rows, and recent media runs under `Mactan Group`.
- **Remediation applied:** preserved the staging `workspaces.id` (so current staging API keys remain valid), replaced the blank staging brand/context tables with local baseline rows (`brands`, `products`, `audiences`, `workspace_documents`, `objectives`), re-encrypted local `provider_keys` and `social_connections` with the staging Fernet key, copied `calendar_pages`, cleared blank-workspace media runs, and renamed staging workspace `My Workspace` → `BOS`.
- **Additional blockers discovered during restore:** C10 — recovered staging had an invalid 64-char hex `ENCRYPTION_KEY`; C11 — staging `api`/`relay` were actually reading `/root/bos/.env` instead of `.env.staging` because `ENV_FILE` was unset.
- **Verification after fixes:** direct staging API retest to `POST /chat` with explicit brand IDs succeeded again. Example: `generate new video for mactangroup. this is a test only` returned a successful `media.video.generate` run with `brand_id = 7a3a3535-9f5b-4035-a5e7-00e2ec8d9b1c`; `new image for motormoto. this is a test only` returned a `media.image.generate` partial run scoped to `brand_id = e44fc8fd-84e6-4cd6-a813-73da5cb63881` rather than `(workspace)`.
- **Current next step:** re-test through the browser/UI. If staging still behaves differently there, investigate only C9 (stale browser-held brand/session state) before assuming new backend drift.
- **Notes:** `INC-004` required manual workspace bootstrap and a fresh login key. That recovery got the stack healthy, but it did not restore behavior parity data.

#### INC-006 — 2026-06-01 — Push-triggered staging deploy rewrote `.env.staging`, dropped port overrides/`ENV_FILE`, and caused 502

- **Cause confirmed:** stale `STAGING_ENV_FILE` secret + active push-triggered `deploy-staging` workflow rewrote `/root/bos/.env.staging` with missing staging-only keys.
- **Symptom:** Minutes after pushing commit `247580d`, `staging.klaroha.com` returned Cloudflare 502 again. Host nginx stayed healthy, but only `staging-redis-1` and `staging-relay-1` were up. `staging-db-1`, `staging-api-1`, `staging-web-1`, `staging-public-1`, and `staging-nginx-1` sat in `Created` because they tried to bind production host ports (`5432/8000/5173/8090/3000`).
- **Confirmed by:** Direct VDS inspection showed current `.env.staging` had lost `DB_PORT`, `API_PORT`, `WEB_PORT`, `NGINX_PORT`, `PUBLIC_PORT`, and `ENV_FILE`. Container state errors included `Bind for 0.0.0.0:5432 failed: port is already allocated` and `Bind for :::8000 failed: port is already allocated`. Backup copies of `.env.staging` from the earlier repair still contained the correct staging values.
- **Resolved by:** restored the missing port overrides + `ENV_FILE=.env.staging` to `/root/bos/.env.staging`, re-ran secret re-encryption against the current staging Fernet key, then ran `bash deploy-staging.sh` manually. `check-staging.sh` returned 13/13 pass and brand-scoped `/chat` worked again.
- **Prevention:** update GitHub secret `STAGING_ENV_FILE` to include `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001`, and `ENV_FILE=.env.staging`. Until the secret is fixed, any push-triggered staging deploy can re-break the stack.
- **Success criteria note:** this incident means the real deploy-parity success criteria is **not yet satisfied**. Manual VDS repair proves the stack can be recovered, but it does **not** prove localhost → commit → push → deploy is reliable. Success is only achieved after `STAGING_ENV_FILE` is corrected in GitHub Secrets and a subsequent small commit/push/deploy reaches `staging.klaroha.com` with **no manual post-deploy intervention**.

#### INC-008 — 2026-06-02 — White screen on staging.klaroha.com; JS bundle returns 502 via Cloudflare

- **Cause confirmed:** bare `web/nginx-spa.conf` — no gzip compression, no MIME types, no cache headers.
- **Symptom:** `staging.klaroha.com` showed a white screen. Browser console showed `ERR_QUIC_PROTOCOL_ERROR`. The JS bundle (`/assets/index-*.js`) returned HTTP 502 when any `Accept-Encoding` header was present. Requests without `Accept-Encoding` returned 200 (served from Cloudflare cache). The origin returned 200 directly (confirmed via `curl http://127.0.0.1:8091/assets/...` on VDS).
- **Root cause:** `nginx-spa.conf` had no gzip, no MIME types, and no cache headers. Nginx served the 613KB JS bundle uncompressed with no `Content-Encoding` header. Cloudflare received the raw uncompressed response and attempted to apply its own JS transformation (Auto Minify). The transformation failed on the large bundle, and Cloudflare returned 502 to the browser. The JS bundle never loaded, React never mounted, white screen.
- **Debug approach:** Replaced the full Vite build with a plain static HTML file (no JS at all). That served 200 through Cloudflare with no issues — confirming the path (nginx → Cloudflare → browser) is clear and the problem was in the JS bundle handling specifically.
- **Fix:** `web/nginx-spa.conf` now includes `gzip on`, `include /etc/nginx/mime.types`, proper `Cache-Control` headers for assets (`immutable`) and `index.html` (`no-cache`). Nginx serves pre-compressed assets directly; Cloudflare receives correctly encoded content and has nothing to transform.
- **Rule:** `nginx-spa.conf` must always include gzip compression, MIME types, and explicit cache headers. A bare config that serves uncompressed static files to a CDN will cause the CDN to attempt its own transformations, which may fail for large files.
- **Resolved (2026-06-02):** Full frontend deployed with corrected `nginx-spa.conf`. White screen gone, `staging.klaroha.com` loads correctly.

---

#### INC-009 — 2026-06-09 — `Cannot read properties of undefined (reading 'find')` on hq.klaroha.com login; works on localhost

- **Status:** Root cause confirmed. Not fixing — logged as a permanent diagnostic record.
- **Symptom:** Logging into `hq.klaroha.com` hits a React render error boundary: `Cannot read properties of undefined (reading 'find')`. Hard refresh does not clear it. localhost (dev machine) has no such error.

**Root cause confirmed:**

Production containers (`bos-web-1`, `bos-api-1`) were rebuilt **locally on the VDS today (03:26 UTC)** while the VDS repo was checked out on the `staging` branch at commit `409e8c3`. This put staging branch code into the production `bos` stack.

Diagnostic trail:
1. `curl https://hq.klaroha.com/api/` → `git_sha: "dev"` — locally built; CI always bakes the real SHA. A local `docker compose build` never passes the `GIT_SHA` build arg.
2. `curl -H "X-API-Key: $KEY" https://hq.klaroha.com/api/plugins` → **plugin count: 0** — no `KLAROHA_LOAD_INTERNAL_PLUGINS`, no `~/bos-plugins/` on production.
3. `docker inspect bos-web-1 --format='{{.Created}}'` → `2026-06-09T03:26:58Z` — built today, not from a CI deploy.
4. `cd ~/bos && git log --oneline -5` → **`HEAD -> staging`** at `409e8c3` — VDS repo was on the staging branch when the build ran.

The `staging` branch at `409e8c3` is missing commits that exist on `main`:
- `b2b2612` — Specialists page redesign; introduced `capability_ids.find()` in AdminModules.tsx
- `8366c68` — thin-core proof complete; full `PluginInfo` `capability_ids` contract
- `a4a5b6a` — TypeScript fix; null guard for `media_provider_options`

Localhost (dev machine) runs `main` branch code via volume mount → all fixes present → no crash. Production ran `staging` branch code missing those fixes → crash at render.

**Why it happened:** Someone ran `docker compose build` (no `-p staging` flag) on the VDS while the repo was on the `staging` branch. The production `bos` stack and the staging stack share the same `docker-compose.yml` and the same working directory. Without `-p staging --env-file .env.staging`, `docker compose` targets the `bos` (production) project. The production stack was silently rebuilt from staging branch code.

**Rule reinforced:** Before any `docker compose` command on the VDS, confirm `git branch` and that the target project flag (`-p`) is correct. The VDS repo branch must match the stack being built: `main` for production (`bos`), `staging` for the staging project. A rebuild on the wrong branch silently corrupts production, and `git_sha: "dev"` in `GET /api/` is the only external signal it happened.

---

#### INC-007 — 2026-06-02 — CI deploy job fails; staging containers stuck in `Created` due to three compounding bugs

- **Cause confirmed:** (a) `script_stop: true` invalid in `appleboy/ssh-action@v1`; (b) `docker compose down` tears down the bridge network, leaving containers with host-port bindings unable to start due to iptables not being ready when `up` immediately recreates the network; (c) staging PORT vars absent from `STAGING_ENV_FILE` secret, so containers are created with production default ports that conflict with the live `bos` stack.
- **Symptom:** CI deploy job emits `Warning: Unexpected input(s) 'script_stop'`. The `up --force-recreate` step starts `staging-redis-1` and `staging-relay-1` (no host port bindings) but leaves `staging-db-1`, `staging-api-1`, `staging-web-1`, `staging-public-1`, and `staging-nginx-1` in `Created` state. Attempting to start them manually fails with `Bind for 0.0.0.0:5432 / 8000 / 5173 failed: port is already allocated` — conflicting with the production `bos` stack running on the same VDS.
- **Root cause detail:**
  - **Bug A:** `script_stop` was removed from `appleboy/ssh-action@v1`'s accepted inputs. The warning is harmless but confirms the CI step is misconfigured.
  - **Bug B:** `deploy-staging.sh` was running `docker compose down --remove-orphans` before `up`. `down` removes the Docker bridge network entirely. When `up` recreates the network immediately after, the kernel's iptables NAT rules are not programmed in time. Containers that bind no host ports (redis, relay) start fine; all containers with `ports:` entries fail and stay in `Created`. The root signal: *every container with a host port binding is in `Created`; every container without one is `Up`.*
  - **Bug C:** `STAGING_ENV_FILE` GitHub secret does not contain `DB_PORT`, `API_PORT`, `WEB_PORT`, `NGINX_PORT`, or `PUBLIC_PORT`. These vars are not in `.env.example` so the auto-fill step skips them. Containers are created with compose defaults (5432, 8000, 5173, 8090, 3000) which directly conflict with the production `bos` stack ports on the same host.
- **Confirmed by:** VDS diagnostic — `docker ps -a --filter name=staging` showed six containers in `Created`, only relay and redis `Up`. `ss -tlnp` showed no staging ports in use. `docker ps` (unfiltered) showed `bos-db-1` on 5432, `bos-api-1` on 8000, `bos-web-1` on 5173 (production). Manual `docker start staging-db-1` succeeded, confirming the iptables race (not a permanent conflict) was the blocker during `up`.
- **Resolved by (manual recovery):**
  1. `docker stop $(docker ps -aq --filter name=staging) && docker rm $(docker ps -aq --filter name=staging)` — remove all stuck containers, preserve `staging_default` network
  2. `export DB_PORT=5433 API_PORT=8001 WEB_PORT=5174 NGINX_PORT=8091 PUBLIC_PORT=3001`
  3. `docker compose -f ~/bos/docker-compose.yml --env-file ~/bos/.env.staging -p staging up -d --no-build` — all 7 containers start cleanly with correct staging ports
  4. `curl -s http://127.0.0.1:8091/api/` returns `{"status":"ok","db":"ok",...}`
- **Fixes committed to repo (2026-06-02, commits 854b808 → 48f9e93):**
  - `ci.yml`: removed `script_stop: true` (not valid in `appleboy/ssh-action@v1`; `set -euo pipefail` in the script already handles abort-on-error)
  - `deploy-staging.sh`: replaced `docker compose down --remove-orphans` with `docker compose stop && docker compose rm -f` — stops and removes containers only, preserving the bridge network so no iptables race on the subsequent `up`
  - `deploy-staging.sh`: added staging port enforcement block — after the env drift check, explicitly writes and exports `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001` to `.env.staging` regardless of what is or is not in `STAGING_ENV_FILE`
  - `deploy-staging.sh`: removed `check-staging.sh` post-deploy call — smoke tests are overhead; verify by hitting the actual endpoint or checking `docker ps`
- **Remaining gap:** `STAGING_ENV_FILE` GitHub secret still does not include the five port vars. The `deploy-staging.sh` enforcement block now closes this gap in-script, but the secret should still be updated so the env file is self-consistent without relying on script-level correction.

#### INC-010 — 2026-06-12 — `STAGING_ENV_FILE` secret is completely blank; every auto-deploy writes empty `.env.staging`

- **Status:** OPEN — root cause confirmed, fix in progress.
- **Symptom:** Staging UI is out of sync with localhost after push. CI run `27390862911` (`feat: token billing...`) shows `STAGING_ENV_FILE: ` (empty) in the deploy job env dump. Every auto-deploy overwrites `/root/bos-staging/.env.staging` with an empty file.
- **Why containers survive:** `deploy-staging.sh` has a port enforcement block (added INC-007 fix) that hard-writes `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001` regardless of secret content. So containers start and bind the right ports. But `ENCRYPTION_KEY`, `API_SECRET_KEY`, `PLATFORM_*` keys, `ENV_FILE=.env.staging`, and all provider/plugin credentials are absent — the stack boots blank/degraded on every deploy.
- **Relation to prior incidents:** INC-006 and INC-007 documented the secret as *missing some keys*. This is worse — the secret is now fully empty, meaning no keys survive a CI deploy at all. Prior manual VDS repairs to `.env.staging` are wiped on every push.
- **Confirmed by:** `gh run view 27390862911 --log-failed` → `STAGING_ENV_FILE: ` (blank value visible in action env dump).
- **Fix:** Go to GitHub → repo Settings → Secrets and variables → Actions → `STAGING_ENV_FILE` → Update. Paste the full contents of the current VDS `.env.staging`. Every future push-triggered deploy will then write a correct env file.
- **To get the current VDS file contents (run once on the VDS):**
  ```bash
  cat ~/bos-staging/.env.staging
  ```
  Paste that output into the GitHub secret. If the file has been wiped by a recent CI deploy, restore from the known-good values (all five port overrides + `ENV_FILE=.env.staging` + `ENCRYPTION_KEY` + `API_SECRET_KEY` + `PLATFORM_*` + provider keys).

#### INC-011 — 2026-06-12 — Staging white screen plus prior permissive API login/key behavior

- **Status:** OPEN — hypotheses created only; no direct staging fix attempted.
- **Symptoms reported:** `staging.klaroha.com` currently renders a white screen. Earlier staging behavior appeared to allow unintended BOS API login/API-key access.
- **Active hypotheses:** C20 (frontend asset/runtime failure) and C21 (auth boundary degraded), with C18 (blank/partial `STAGING_ENV_FILE`) and C19 (deploy path mismatch) as likely contributing causes.
- **Debug rule for this incident:** start offline/local and read-only. Do not mutate VDS files, containers, Cloudflare config, database rows, or secrets as a first response. Any code fix must be committed locally, pushed to `origin/staging`, built by CI, deployed by the staging workflow, and verified by `GET /api/` returning the expected `git_sha` plus a browser retest.
- **Security note:** if a fake/random API key returns HTTP 200 on a protected staging endpoint, treat it as a security incident and document the exact endpoint/status without printing real keys.

#### INC-012 — 2026-06-12 — Push succeeded but CI failed publishing API image to GHCR (`unknown blob`)

- **Status:** OPEN — root cause not yet fixed; initial evidence points to registry/image-publish failure.
- **Symptom:** Commit `c94e148` was pushed to `origin/staging`, but GitHub Actions run `27393507882` failed in `Build & push images` before any staging SSH deploy. `staging.klaroha.com/api/` still returns Cloudflare 502, so the pushed docs commit did not deploy.
- **Confirmed by:** local `git ls-remote origin refs/heads/staging` returns `c94e148803c8d6c665fd75ae3749b4967f0aef71`; `gh run view 27393507882 --log-failed` shows `Build and push API image` ending with `ERROR: failed to build: unknown blob` while pushing `ghcr.io/itsborj/bos-api:sha-c94e148803c8d6c665fd75ae3749b4967f0aef71`.
- **Current interpretation:** GitHub received the commit, but GHCR did not receive a valid API image artifact. Since the deploy job depends on image publication, staging could not update.
- **Debug rule:** debug via GitHub Actions/GHCR first. Do not mutate the VDS to compensate for a missing image artifact.

#### INC-013 — 2026-06-12 — CI deploy green but API health missing and public `/api/` returns 502

- **Status:** OPEN — root cause not yet fixed.
- **Symptom:** Retry commit `fc4c402` produced a green GitHub Actions run `27393813054`; images built and deploy job completed. However the deploy summary printed `git_sha: missing` and `uptime_seconds: ?s`, and public `https://staging.klaroha.com/api/` returned Cloudflare 502 after deploy.
- **Confirmed by:** `gh run view 27393813054 --log` final deploy lines plus external `curl -i https://staging.klaroha.com/api/`.
- **Current interpretation:** C22 was transient or resolved on retry, but C23 is now the active deploy verification failure. The script started containers and exited success without proving API health.
- **Debug rule:** inspect API/container readiness read-only first. Durable fix must make deploy health fail closed; do not manually patch the VDS as the final fix.

#### INC-014 — 2026-06-12 — API down because Alembic cannot store long migration revision id

- **Status:** OPEN — root cause confirmed; code fix required.
- **Symptom:** After commit `ac9a80d`, deploy correctly failed instead of going green. API remains unavailable and nginx returns 502/504 because the API process fails during Alembic upgrade.
- **Confirmed by:** GitHub Actions run `27394391729` failed in deploy health. API logs show `StringDataRightTruncationError: value too long for type character varying(32)` while executing `UPDATE alembic_version SET version_num='039_cleanup_fuzzer_data_stream_dedupe' WHERE alembic_version.version_num = '038_plugin_activations'`.
- **Current interpretation:** this is the current top blocker. It must be fixed before investigating zero specialists, because specialists cannot load while the API is down.
- **Debug rule:** fix one layer at a time: first migration/API health, then auth boundary, then specialist count/provider/plugin readiness.

#### INC-015 — 2026-06-12 — Staging API healthy, but Specialists page reportedly shows zero specialists

- **Status:** OPEN — hypothesis created; debugging starts after API/auth layer verification.
- **Symptom:** User reports staging has zero specialists.
- **Preconditions now satisfied:** API health is restored; fake API key is rejected with 401; homepage and JS assets load. This means specialist debugging can proceed without mixing it with API-down/white-screen causes.
- **Finding:** commit `c560924` added a deploy-time plugin discovery diagnostic. CI run `27395023837` succeeded and reported `plugins: 8`, `channel_json_count: 8`, `error_count: 0` in the running API container.
- **Current interpretation:** backend discovery is healthy. If the Admin UI still shows zero specialists, the issue is one layer higher: authenticated `/api/plugins`, brand activation/filtering, frontend rendering, or stale browser state.
- **Debug rule:** one layer at a time. Do not change provider keys, brand data, or activation state until authenticated plugin API output is checked.

#### INC-016 — 2026-06-13 — Staging white screen from Cloudflare/browser JS bundle load failure

- **Status:** FIX IN PROGRESS — local code fix built; needs commit/push/CI deploy verification.
- **Symptom:** after commit `dcd821a`, `staging.klaroha.com` showed a white screen for the user even though `/api/` returned a healthy runtime fingerprint for the same SHA.
- **Confirmed by:** Playwright reproduced a blank page with empty `#root` when the browser failed to load `/assets/index-Qw00dZ5e.js` via Cloudflare, reporting `net::ERR_HTTP2_PROTOCOL_ERROR` / `net::ERR_QUIC_PROTOCOL_ERROR`. Curl showed API health and asset headers were otherwise 200.
- **Root cause class:** C20 — frontend asset delivery/runtime load failure. The entry Vite bundle had grown to 733.84 kB minified (182.25 kB gzip), making the app brittle to Cloudflare/browser transport failures; if that single entry script fails, React never mounts.
- **Fix in progress:** route-level lazy loading in `web/src/App.tsx` split page/admin bundles and reduced the entry bundle to 348.27 kB minified (99.54 kB gzip). `cd web && npm run build` passes.
- **Success criteria:** commit and push the fix to `origin/staging`; CI deploy must return expected `git_sha`; browser automation must load staging without JS asset errors and non-empty `#root`.

---

## Open Items

> Active execution tracking for the items below lives in `DEPLOY_COORDINATION.md`. Keep this section as the durable checklist summary; record live hypothesis work and evidence in the coordination file.

- [x] Add `name:` field to the compose file so project name is explicit and never inferred — `name: bos` is in `docker-compose.yml`
- [x] Write a `deploy.sh` script wrapping the full staging deploy sequence — `deploy-staging.sh` (env-fill → git reset → image pull → up → migrations → `check-staging.sh` smoke tests)
- [x] `deploy-staging.sh` now enforces staging port overrides directly (2026-06-02) — containers can no longer be created with production default ports even if the secret is missing these vars
- [x] `web/nginx-spa.conf` now has gzip, MIME types, and correct cache headers (2026-06-02) — bare config was causing Cloudflare to 502 on the large JS bundle (INC-008)
- [ ] **C18:** Update GitHub secret `STAGING_ENV_FILE` with the full known-good staging env, not just ports: `ENV_FILE=.env.staging`, `DATABASE_URL`, `API_SECRET_KEY`, `ENCRYPTION_KEY`, all five staging ports, `PLATFORM_*`, OAuth/provider/plugin keys, and any other staging-critical vars. The script enforcement is a safety net, not a replacement for fixing the secret.
- [ ] **C18 guard:** Add a CI/deploy fail-closed check that refuses to write/use an empty `STAGING_ENV_FILE` or one missing critical key names. Print key names/counts only — never values.
- [ ] **C19:** Remove hard-coded `cd ~/bos` / `~/bos/.env.staging` assumptions from `deploy-staging.sh` and `check-staging.sh`; run from `STAGING_PATH`/current checkout and print `pwd`, `git rev-parse HEAD`, and `realpath .env.staging` at start.
- [ ] **C20:** Deploy and verify route-level frontend code splitting fix for the staging white screen. Local build passes and reduces the entry bundle from 733.84 kB to 348.27 kB; remaining success criteria are CI deploy to `origin/staging`, expected `git_sha`, and browser asset-load retest.
- [ ] **C21:** Add/verify a negative auth-boundary test using a fake API key against protected endpoints; any HTTP 200 must fail CI/deploy and be logged as a security incident.
- [ ] **C22:** Investigate GHCR `unknown blob` image-push failure from run `27393507882`; first retry if transient, then inspect buildx/GHCR cache/provenance settings if it recurs. Retry run `27393813054` built/pushed successfully, so treat C22 as transient unless it recurs.
- [x] **C23:** Make `deploy-staging.sh` fail closed when post-deploy health is invalid (`git_sha: missing`, `uptime_seconds: ?s`, non-JSON, wrong SHA) and add a readiness retry loop before failing. Commit `ac9a80d` implemented this and exposed C24.
- [x] **C24:** Widen Alembic `alembic_version.version_num` before recording long revision id `039_cleanup_fuzzer_data_stream_dedupe`; keep this separate from specialist/plugin debugging. Commit `39c9124` restored API health.
- [ ] **C25:** Debug zero specialists one layer at a time: plugin files present ✓, plugin loader discovers packages ✓ (`plugins: 8` in run `27395023837`) → next: authenticated API `/plugins` count → frontend rendering/brand activation → provider readiness.
- [ ] **C26:** Implement `check-sync.sh` as the one-command localhost → GitHub → staging → browser sync ledger. It must verify local branch/HEAD/dirty state, latest GitHub staging run, staging API `git_sha`, web index asset hash, JS asset HTTP 200, headless browser asset load/non-empty `#root`, fake-key rejection, and plugin count without printing secrets.
- [ ] After the secret, path, white-screen, auth-boundary, image-publish, post-deploy-health, migration, specialist-discovery, and sync-ledger fixes, prove the real success criteria with one tiny localhost change → commit → push → CI builds images → auto-deploys → `staging.klaroha.com` returns expected `git_sha` and healthy behavior **without** manual server repair.
- [ ] Set `git config pull.rebase false` (or `--ff-only`) on the server so `git pull` doesn't fail on divergence
- [x] GitHub secrets: `VDS_HOST`, `VDS_USER`, `VDS_DEPLOY_KEY`, `STAGING_PATH`, `PROD_PATH`, `GHCR_TOKEN`, `STAGING_ENV_FILE` — all wired in `ci.yml` (but `STAGING_ENV_FILE` content is currently the C18 risk)
- [x] **C13 fix (scale-required):** API image accepts `ARG GIT_SHA`, CI passes `--build-arg GIT_SHA=${{ github.sha }}`, `GET /api/` exposes `git_sha`, and `check-staging.sh` verifies it when `DEPLOY_SHA` is set.
- [x] **C17 fix:** `deploy-staging.sh` prints final image/`git_sha`/`uptime_seconds`; `check-staging.sh` prints `uptime_seconds` and `git_sha`.
- [ ] **Agent protocol (CLAUDE.md):** Add explicit section documenting that agents must never report staging as reflecting a change without verifying `git_sha` + `uptime_seconds`, and must check C18/C19 when code SHA is correct but behavior still drifts.

---

## Environment Drift — Industry Standards

> The localhost/staging divergence problem is well-understood. Below are the ten industry-standard approaches to eliminating it, in order of highest to lowest leverage. We work through these one at a time.

| # | Standard | Status | Core Idea |
|---|---|---|---|
| 1 | **Build once, deploy the artifact** | `[x]` | CI builds GHCR images tagged `sha-<commit>` and `:staging`. VDS pulls the exact SHA image — no rebuild per environment. `--no-build --force-recreate` on `docker compose up`. Eliminates C1, C3, and C6 at the architectural level. |
| 2 | **Config injection, not per-env config files** | `[x]` | `STAGING_ENV_FILE` GitHub Actions secret is the single source of truth. CI overwrites `.env.staging` on **every** deploy (not just first boot) — manual edits on the VDS are wiped on the next push. `.env.staging` is gitignored and never in source. `deploy-staging.sh` auto-fills any keys missing from the secret using `.env.example` defaults as a safety net. Critical exceptions that are **not** in `.env.example` and therefore must be present in `STAGING_ENV_FILE` explicitly: `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001`, and `ENV_FILE=.env.staging`. |
| 3 | **GitOps — git is the only source of truth** | `[ ]` | What is in the branch is what is running. Tools like ArgoCD or Flux continuously reconcile running state against git. Manual server edits are impossible by design. Drift is detected and corrected automatically. |
| 4 | **Immutable infrastructure** | `[x]` | `.githooks/pre-push` runs `pytest` + `tsc` inside the local running containers before any push to `staging` or `main`. Tests your actual local code — if they fail, the push is blocked. Closes C1 structurally as a pre-push gate. |
| 5 | **Ephemeral preview environments** | `[ ]` | Every PR gets its own isolated environment spun up automatically. Test against the actual deployed artifact before merging. Eliminates localhost-as-staging entirely. |
| 6 | **Infrastructure as Code (IaC)** | `[ ]` | All environment definitions live in code (Terraform, Pulumi, Helm). Staging and production are the same template with different parameter values. Accidental per-env config drift is structurally impossible. |
| 7 | **Secrets management** | `[x]` | All deploy credentials (`VDS_HOST`, `VDS_DEPLOY_KEY`, `GHCR_TOKEN`) and the full staging env (`STAGING_ENV_FILE`) live in GitHub Actions secrets. CI is the only writer of `.env.staging` on the VDS — overwritten on every deploy, never manually editable in a durable way. No Vault/Doppler, but GitHub Secrets is the authoritative store and drift is structurally impossible. |
| 8 | **Automated post-deploy verification** | `[x]` | `check-staging.sh` verifies config, ports, web/public HTTP, API health, `git_sha`/`uptime_seconds`, auth boundary, authenticated DB query, capability manifest count ≥ 20, and migrations at head. Pipeline fails and alerts if any check fails. Remaining gap: make the script path-agnostic (C19). |
| 9 | **Dependency lockfiles pinned and committed** | `[x]` | `requirements.txt` with pinned versions, `package-lock.json` committed. Same dep versions in dev, CI, staging, and production. |
| 10 | **Local dev mirrors production runtime** | `[x]` | devcontainers or Tilt/Skaffold. The developer's local environment IS the production container, not a volume-mounted lookalike. Eliminates the "uncommitted file visible via volume mount" class entirely. |

> #1, #2, #4, #7, #8, #9, #10 done. Remaining: #3 (GitOps), #5 (ephemeral preview envs), #6 (IaC) — lower leverage, defer until distribution scale warrants it.
>
> **Scale directive note:** #3 (GitOps) and #5 (ephemeral previews) become required when daily deployment volume exceeds human-reviewable capacity. At 100+ org deploys/day, manual SSH recovery (as seen in INC-003 through INC-006) is not operationally viable. Target: #3 implemented before reaching 50 active customer orgs. #11 below is newly required at scale.

| 11 | **Deployed version fingerprinting** | `[x]` | API containers expose the exact git commit SHA baked into the image (`GIT_SHA`, surfaced in `GET /api/`). Operators, support, and automated checks can confirm which version is running without SSH access. Remaining work is not fingerprinting itself; it is making every script use the correct checkout/env path (C19). |
| 12 | **End-to-end sync ledger** | `[ ]` | One command (`check-sync.sh`) proves local branch/HEAD, GitHub run, deployed API SHA, web bundle hash, browser JS load, auth boundary, and plugin readiness together. This closes the gap where individual green checks still leave localhost and staging observably divergent (C26). |

---

## Production Model — Click-to-Deploy Software

> **Decision locked 2026-06-01.** Canonical source: `PROJECT_BRIEF.md §10`. This section is a deploy-operations summary — the brief is the authority on model rationale and policy.

BOS is packaged software that organizations deploy on their own cloud infrastructure. It is **not** a multi-tenant SaaS. Klaroha is the software vendor and central services operator; organizations own their data and their cloud environment.

**Scale target:** hundreds of new org deployments per day; 10,000+ concurrent active deployments maintained with no per-org Klaroha intervention.

**Active focus:** one clean end-to-end first-org deploy. Getting that journey right once is the template all future deployments clone. Every manual step eliminated from the first deploy is a step eliminated at 10K-org scale.

---

### What Each Org Gets

- Their own server or cloud environment (DigitalOcean droplet, AWS EC2, VPS)
- Their own isolated PostgreSQL database — no commingling with other orgs
- Their own encryption keys, auto-generated at first boot
- Their own domain or subdomain
- No Klaroha access to their data at rest

### What Klaroha Operates Centrally

| Service | What it does |
|---|---|
| **OAuth relay** (`connect.klaroha.com`) | Holds the one Klaroha-verified Google + Meta + TikTok app. Brokers token exchange for all deployed instances. One stable redirect URI per platform — no per-org app registration ever required. |
| **Platform inference** | Pooled AI provider access for orgs that do not bring their own API keys. Metered against each org's deployment key. |
| **Deployment key issuance** | Each org receives a `KLAROHA_DEPLOYMENT_KEY` at purchase. Gates relay access and usage metering. |
| **Software distribution** | Docker image registry; `stable` and `latest` channels. Klaroha controls what is promoted to `stable`. |
| **Update notifications** | In-app alert when a new version is available. Org controls timing of their own update. |

---

### Target Deploy Experience (Zero-Setup)

Once the relay is built, the full operator experience is:

1. Org purchases license → receives `KLAROHA_DEPLOYMENT_KEY`
2. Clicks "Deploy to DigitalOcean" or runs `curl install.klaroha.com | bash`
3. Sets domain name + deployment key — nothing else
4. Container first boot: auto-generates `API_SECRET_KEY` and `ENCRYPTION_KEY`, runs `alembic upgrade head`, bootstraps admin
5. First login → setup wizard (org name → import brand brief → CMO operational)

No Google Cloud project. No Meta Developer App. No AI API keys required to get started.

### Minimal `.env` at Deploy Time (Target)

```env
KLAROHA_DEPLOYMENT_KEY=dk_live_xxx     # issued at purchase — relay access + metering
KLAROHA_RELAY_URL=https://connect.klaroha.com
FRONTEND_URL=https://theirorg.com      # org's chosen domain
```

All other values (database URL, secret keys, encryption key) are auto-generated at first boot and stored in the container's persisted volume.

> **Local dev note:** Set `FRONTEND_URL=http://localhost:8090` (the Docker nginx HQ port). `http://localhost` (port 80) has no listener — the host nginx config rejects unmatched hosts with 444. Using port 80 locally causes OAuth callbacks and calendar widget links to silently fail.

---

### Current State vs. Target

Today a deployment requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `META_APP_ID`, `META_APP_SECRET`, and all other platform credentials set manually in `.env`. The relay closes this gap entirely. Until the relay is built, new deployments require manual Google Cloud and Meta app setup — this blocks clean customer onboarding.

---

### Distribution Targets

| Platform | Priority | Notes |
|---|---|---|
| DigitalOcean Marketplace | Primary | 1-Click Droplet; right fit for non-technical operator audience |
| Docker Compose + install script | Secondary | `curl install.klaroha.com \| bash`; dev-savvy operators |
| AWS Marketplace | Enterprise | Larger agencies already on AWS infrastructure |

---

### Build Order

| Step | What | Why it unblocks |
|---|---|---|
| 1 | **OAuth relay** (`connect.klaroha.com`) | Zero-setup for all Google + Meta integrations; every deploy currently requires manual cloud project setup without it |
| 2 | **First-boot init script** | Turns `docker compose up` into a real product install; no post-boot shell access required |
| 3 | **Deployment key system** | Gates relay access; enables per-org usage metering and billing |
| 4 | **DigitalOcean Marketplace listing** | Primary distribution channel for the target operator persona |
| 5 | **In-app update notification** | Keeps deployed instances informed without forcing auto-updates |
| 6 | **AWS Marketplace** | Enterprise distribution tier |

---

### Update Strategy

Each deployed instance checks a Klaroha version endpoint periodically. When a new version is available, the admin panel surfaces "Update available — vX.Y.Z" with a changelog. The admin triggers the update manually (pull new Docker image + run migrations). Auto-updates on the `stable` channel are available for orgs that opt in.

**Plugins are baked into the Docker image.** No plugin registry or live delivery mechanism needed. Updating a plugin = build a new image tag.

---

### Google OAuth Setup (per deployment — until relay is built)

| Integration | Redirect URI |
|---|---|
| Gmail | `https://YOUR_DOMAIN/api/social/gmail/callback` |
| Google Calendar | `https://YOUR_DOMAIN/api/social/google-calendar/callback` |

`GOOGLE_CALENDAR_REDIRECT_URI` does not need to be set — it is auto-derived from `GOOGLE_REDIRECT_URI` by replacing the path suffix. Both URIs must be registered in Google Cloud Console under the same OAuth client.

**Required OAuth Scopes:**

| Scope | Used by |
|---|---|
| `https://www.googleapis.com/auth/gmail.send` | Gmail send, Calendar booking confirmations |
| `https://www.googleapis.com/auth/gmail.readonly` | Gmail inbox |
| `https://www.googleapis.com/auth/calendar` | Calendar booking (read/write events + FreeBusy) |
| `openid email` | All Google OAuth flows (user identity) |
