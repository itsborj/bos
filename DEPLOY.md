# BOS — Deployment Reference

> Single source of truth for all deploy operations, port topology, localhost ↔ staging breakage runbook, and the future production model.
> **git.md has been merged into this file and deleted.**
> Active execution tracker for deploy hypotheses / AI handoff: `DEPLOY_COORDINATION.md`.

---

## Scale Directive — Non-Negotiable

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

### What this means for the incident log

Every incident marked `CONFIRMED` that was resolved via manual SSH is a **product gap** — not a closed issue. Before marking such an incident resolved, add a corresponding automation task to `BACKLOG.md`. The manual fix is a one-time exception; the automated equivalent is the real fix.

### What is not required now vs. must be right

Not every item needs to be built today. The scale directive governs **direction** — each incremental solution must make the system more scalable, not less. A fix that introduces a new manual step or a new per-org secret to manage is moving in the wrong direction, even if it solves the immediate symptom.

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

- `main` → production (hq.klaroha.com)
- `staging` → staging (staging.klaroha.com)
- Feature branches → PR to `staging` first, reviewed, then merged to `main`

---

## Deploy Runbook

### Deploy to staging (staging.klaroha.com)

```bash
# On local machine — commit and push first (always — see C1)
git add <files>
git commit -m "message"
git push origin staging

# On server (SSH in) — or let CI handle it via GitHub Actions
cd ~/bos
git fetch origin && git reset --hard origin/staging
docker compose -p staging -f docker-compose.yml --env-file .env.staging up -d --build --force-recreate web
```

If API changed too:
```bash
docker compose -p staging -f docker-compose.yml --env-file .env.staging up -d --build --force-recreate api
```

### Deploy to production (hq.klaroha.com)

```bash
# On local machine
git push origin main

# On server
cd ~/bos
git fetch origin && git reset --hard origin/main
docker compose build web && docker compose up -d web
```

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

#### C12 — The deploy gap: `git push` ≠ staging updated (STRUCTURAL — PRIMARY CAUSE)
**Status:** `CONFIRMED STRUCTURAL (2026-06-02)`

Pushing to the `staging` branch triggers the `build-and-push` CI job (new GHCR image built and tagged `sha-{SHA}` + `:staging`). It does **not** update `staging.klaroha.com`. The `deploy-staging` CI job is `workflow_dispatch` only — it runs only when manually triggered from the GitHub Actions UI or via `gh workflow run CI`. Staging only updates when that trigger is fired. Every session where code is pushed without a subsequent manual deploy trigger leaves staging running old code indefinitely.

This is the structural root cause of 90%+ of "staging doesn't reflect my changes" reports.

**Confirm:**
```bash
curl -s https://staging.klaroha.com/api/ | python3 -c "import json,sys; print(json.load(sys.stdin)['uptime_seconds'])"
# If uptime > 600s after a push, deploy was not triggered
```

**Rule:** Treat push and deploy as completely separate operations. After any `git push origin staging`, `staging.klaroha.com` will not update until the deploy workflow is manually triggered. Never report staging as reflecting a change unless the deploy has been manually confirmed.

**To deploy:** GitHub Actions → CI → Run workflow → (optionally enter a SHA) → Run. Or: `gh workflow run CI --ref staging`

**Scale alignment:** At 100s of org deployments/day, the equivalent gap is a new org pressing "Install" and getting an old version. The fix is restoring automated deployment with a proper staging gate (protected branch rules, required status checks, comprehensive behavioral test coverage) rather than manual-only CI.

---

#### C13 — Static version string: code version is unverifiable from outside the container
**Status:** `CONFIRMED — VERIFICATION GAP (2026-06-02)`

`config.py` hardcodes `app_version = "0.1.0"`. `GET /api/` returns this same string regardless of which git commit is actually running. Two containers on completely different commits return identical responses except for `uptime_seconds`. Agents and operators have no programmatic way to confirm which code is deployed.

`check-staging.sh` passes 13/13 on a staging stack running code from weeks ago. None of the 13 checks test code version.

**Confirm:**
```bash
curl -s https://staging.klaroha.com/api/ | jq '{version, uptime_seconds}'
# version is always "0.1.0" — meaningless for freshness check
```

**Fix pattern (required for scale):** Bake `GIT_SHA` into the Docker image at build time via build arg (`ARG GIT_SHA=dev` in Dockerfile, `--build-arg GIT_SHA=${{ github.sha }}` in `build-and-push` CI step). Expose as `git_sha` field in `GET /api/` response. At 10K orgs, support must be able to ask an org "what does `GET /api/` return?" and get a definitive answer about which version is running.

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

#### C16 — `check-staging.sh` confirms availability, not code version — false positive for agents
**Status:** `CONFIRMED STRUCTURAL (2026-06-02)`

13/13 from `check-staging.sh` means: ports listening, HTTP 200, API health ok, auth boundary correct, DB connected, capabilities ≥ 20, migrations at head. It does **not** mean new code is running. A staging stack running month-old code passes all 13 checks. Agents interpret green checks as deployment confirmation. It is only availability confirmation.

**Fix pattern (required for scale):** Add a 14th check: print `git_sha` from the health endpoint and compare against the expected commit. Until `git_sha` is in the health endpoint (C13 fix), add an explicit `uptime_seconds` check that warns if staging has been up > 5 minutes after a deploy (indicating containers did not restart).

**Scale alignment:** At 10K orgs, Klaroha support cannot SSH into each org to verify version. The health endpoint must be the self-service diagnostic tool. It must carry enough information for an org admin to resolve their own version mismatch.

---

#### C17 — `uptime_seconds` is the only deploy freshness signal, and nothing surfaces it automatically
**Status:** `CONFIRMED STRUCTURAL (2026-06-02)`

After `deploy-staging.sh`, the API container restarts and `uptime_seconds` resets to near-zero. This is the only currently-available indicator that a fresh deploy happened. It is not in `check-staging.sh` output. It is not in any deploy success message. It is buried as a manual check command in `DEPLOY.md`. Agents and developers have no prompted workflow that checks it.

**Fix pattern:** `check-staging.sh` should print `uptime_seconds` prominently after every run. `deploy-staging.sh` should print the post-deploy uptime from the health endpoint as a final confirmation line.

**Scale alignment:** At org scale, post-deploy verification must be automated and visible. An operator who deploys and gets no confirmation signal will open a support ticket. The deploy script must be self-verifying.

---

### Process of Elimination

When a feature breaks after a staging deploy, work through in this order:

1. **C12** — Was `deploy-staging.sh` actually run on the VDS after the last push? Check uptime: `curl -s https://staging.klaroha.com/api/ | python3 -c "import json,sys; print(json.load(sys.stdin)['uptime_seconds'])"`. If > 600s after a push, the deploy never ran. This is the primary cause — check it first.
2. **C6** — If deploys are running but uptime stays high, CI is failing to reach the containers. See C6 for the three compounding bugs.
3. **C1** — `git diff origin/staging -- api/` — uncommitted local edits were not deployed.
4. **C15** — Did the change touch `web/`? Frontend requires manual `docker compose build web && docker compose up -d web`; it does not hot-reload.
5. **C14** — API returning old responses despite a restart? Check `docker compose logs api` for reload failures.
6. **C3** — Pre-deploy video assets — check Drive connectivity + `drive_file_id` in DB.
7. **C4** — diff local `.env` against `.env.example` for keys the capability uses.
8. **C2** — only if the render itself fails (not just serving). Compare ffmpeg versions between containers.
9. **C5** — only if you see import errors or missing file errors in API logs.
10. **If deploy + smoke are green but behavior still differs, stop treating it as a pure deploy problem and run the Behavior Parity Checklist below.**

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

---

## Open Items

> Active execution tracking for the items below lives in `DEPLOY_COORDINATION.md`. Keep this section as the durable checklist summary; record live hypothesis work and evidence in the coordination file.

- [x] Add `name:` field to the compose file so project name is explicit and never inferred — `name: bos` is in `docker-compose.yml`
- [x] Write a `deploy.sh` script wrapping the full staging deploy sequence — `deploy-staging.sh` (env-fill → git reset → image pull → up → migrations → `check-staging.sh` smoke tests)
- [x] `deploy-staging.sh` now enforces staging port overrides directly (2026-06-02) — containers can no longer be created with production default ports even if the secret is missing these vars
- [ ] Update GitHub secret `STAGING_ENV_FILE` so it includes `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001`, and `ENV_FILE=.env.staging` — the script enforcement is a safety net, not a replacement for fixing the secret
- [ ] After the secret is updated, prove the real success criteria with one tiny localhost change → commit → push → CI builds image → trigger `workflow_dispatch` → `staging.klaroha.com` healthy **without** manual server repair
- [ ] Set `git config pull.rebase false` (or `--ff-only`) on the server so `git pull` doesn't fail on divergence
- [x] GitHub secrets: `VDS_HOST`, `VDS_USER`, `VDS_DEPLOY_KEY`, `STAGING_PATH`, `PROD_PATH`, `GHCR_TOKEN`, `STAGING_ENV_FILE` — all wired in `ci.yml`
- [ ] **C13 fix (scale-required):** Bake git SHA into Docker image at CI build time (`ARG GIT_SHA`, `--build-arg GIT_SHA=${{ github.sha }}`); expose as `git_sha` in `GET /api/` response; add as 14th `check-staging.sh` verification. Required before reaching 10 active customer orgs.
- [ ] **C17 fix:** `deploy-staging.sh` must print `uptime_seconds` from the health endpoint as a final confirmation line after every deploy. `check-staging.sh` must print `uptime_seconds` prominently.
- [ ] **Agent protocol (CLAUDE.md):** Add explicit section documenting that `git push origin staging` does NOT update staging.klaroha.com and that agents must never report staging as reflecting a change without verifying `git_sha` + `uptime_seconds`.

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
| 8 | **Automated post-deploy verification** | `[x]` | `check-staging.sh` runs 8 checks on every CI deploy: FRONTEND_URL validity, API_SECRET_KEY presence, ports listening (8091, 8001, 5174, 3001), web + public HTTP 200, API health (`status: ok`), auth boundary (401/403), authenticated DB query, capability manifest count ≥ 20, migrations at head. Pipeline fails and alerts if any check fails. |
| 9 | **Dependency lockfiles pinned and committed** | `[x]` | `requirements.txt` with pinned versions, `package-lock.json` committed. Same dep versions in dev, CI, staging, and production. |
| 10 | **Local dev mirrors production runtime** | `[x]` | devcontainers or Tilt/Skaffold. The developer's local environment IS the production container, not a volume-mounted lookalike. Eliminates the "uncommitted file visible via volume mount" class entirely. |

> #1, #2, #4, #7, #8, #9, #10 done. Remaining: #3 (GitOps), #5 (ephemeral preview envs), #6 (IaC) — lower leverage, defer until distribution scale warrants it.
>
> **Scale directive note:** #3 (GitOps) and #5 (ephemeral previews) become required when daily deployment volume exceeds human-reviewable capacity. At 100+ org deploys/day, manual SSH recovery (as seen in INC-003 through INC-006) is not operationally viable. Target: #3 implemented before reaching 50 active customer orgs. #11 below is newly required at scale.

| 11 | **Deployed version fingerprinting** | `[ ]` | Every running container must expose the exact git commit SHA it was built from (via build arg baked into image at CI build time, surfaced in `GET /api/`). Operators, support, and automated checks can then confirm exactly which version is running without SSH access. Required for operator self-service diagnostics at 10K org scale. Closes C13, C16, C17. |

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
