# BOS — Deployment Reference

> Single source of truth for all deploy operations, port topology, localhost ↔ staging breakage runbook, and the future production model.
> **git.md has been merged into this file and deleted.**

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

2. **`appleboy/ssh-action` swallows exit codes:** By default, the action reports success even when the remote script exits non-zero. CI showed green for every broken deploy. Added `script_stop: true` to the action so failures are visible.

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

### Process of Elimination

When a feature breaks after a staging deploy, work through in this order:

1. **C6** — check VDS API uptime first. If uptime is hours/days old despite recent CI runs, the CI deploy isn't reaching the containers. `curl https://staging.klaroha.com/api/ | python3 -c "import json,sys; print(json.load(sys.stdin)['uptime_seconds'])"` — anything over 10 minutes after a CI run is suspicious.
2. **C1** — `git diff origin/staging -- api/` — 5 seconds, rules out the most common cause.
3. **C3** — is this a pre-deploy run or a new generation? Pre-deploy video = check Drive connectivity + `drive_file_id` in DB.
4. **C4** — diff local `.env` against `.env.example` for keys the capability uses.
5. **C2** — only if the render itself fails (not just serving). Compare ffmpeg versions between containers.
6. **C5** — only if you see import errors or missing file errors in API logs.

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

---

## Open Items

- [ ] Add `name:` field to the compose file so project name is explicit and never inferred
- [ ] Write a `deploy.sh` script wrapping the full staging deploy sequence (fetch → reset → build → up) for one-command deploys
- [ ] Set `git config pull.rebase false` (or `--ff-only`) on the server so `git pull` doesn't fail on divergence
- [ ] GitHub secrets: add `VDS_HOST`, `VDS_USER`, `VDS_DEPLOY_KEY`, `STAGING_PATH`, `PROD_PATH`, `GHCR_TOKEN` (PAT with `read:packages`) to repo secrets so CI can SSH in and VDS can pull from GHCR without manual setup

---

## Environment Drift — Industry Standards

> The localhost/staging divergence problem is well-understood. Below are the ten industry-standard approaches to eliminating it, in order of highest to lowest leverage. We work through these one at a time.

| # | Standard | Status | Core Idea |
|---|---|---|---|
| 1 | **Build once, deploy the artifact** | `[x]` | CI builds one Docker image tagged with the commit SHA. That exact image is promoted to staging then production. No rebuilding per environment. Eliminates C1, C3, and C6 at the architectural level. |
| 2 | **Config injection, not per-env config files** | `[ ]` | Code is identical across environments. Only env vars differ, injected at runtime. No `.env.staging`, no per-env key sets. One schema (`.env.example`), values from a secrets manager. Eliminates C4. |
| 3 | **GitOps — git is the only source of truth** | `[ ]` | What is in the branch is what is running. Tools like ArgoCD or Flux continuously reconcile running state against git. Manual server edits are impossible by design. Drift is detected and corrected automatically. |
| 4 | **Immutable infrastructure** | `[ ]` | Servers are never modified in place. A deploy replaces containers with new ones built from the latest artifact. No SSH + edit patterns. Solves C1 and C3 architecturally. |
| 5 | **Ephemeral preview environments** | `[ ]` | Every PR gets its own isolated environment spun up automatically. Test against the actual deployed artifact before merging. Eliminates localhost-as-staging entirely. |
| 6 | **Infrastructure as Code (IaC)** | `[ ]` | All environment definitions live in code (Terraform, Pulumi, Helm). Staging and production are the same template with different parameter values. Accidental per-env config drift is structurally impossible. |
| 7 | **Secrets management** | `[ ]` | Vault, AWS Secrets Manager, Doppler, or 1Password Secrets Automation. One source of truth for secrets, versioned, auditable. All environments pull from the same system with different access scopes. Eliminates C4 entirely. |
| 8 | **Automated post-deploy verification** | `[x]` | Every deploy runs a functional test suite against the live environment. Pipeline fails and rolls back if tests fail. No human needed to detect a broken deploy. |
| 9 | **Dependency lockfiles pinned and committed** | `[x]` | `requirements.txt` with pinned versions, `package-lock.json` committed. Same dep versions in dev, CI, staging, and production. |
| 10 | **Local dev mirrors production runtime** | `[ ]` | devcontainers or Tilt/Skaffold. The developer's local environment IS the production container, not a volume-mounted lookalike. Eliminates the "uncommitted file visible via volume mount" class entirely. |

> Start with #1. It has the most impact and makes several downstream standards easier to implement.

---

## Production Model (Future — GHCR + Watchtower)

> **Status:** Draft — circle back before implementation. This section describes the target self-hosted customer deployment model, not the current dev/staging setup above.

### Deployment Model

Single-tenant per VPS. Each org gets their own deployment. Code is identical across all instances; only `.env`, domain, and data differ. The product shipped is a Docker image + compose file, not a shared SaaS service.

```
┌─────────────────────────────────────────────────┐
│  GitHub repo                                     │
│  git push → GitHub Actions builds image          │
│           → pushes to GHCR (api:latest or :v1.x) │
└─────────────────────────────────────────────────┘
              ↓ Watchtower polls + pulls
┌─────────────────────────────────────────────────┐
│  Org A VPS (e.g. Hetzner, $6/mo)               │
│  /opt/bos/                                       │
│    docker-compose.prod.yml   ← pulled from git   │
│    .env                      ← unique per org    │
│    Caddyfile                 ← unique domain     │
│    update.sh                 ← manual trigger    │
│                                                  │
│  services: db, api (ghcr image), web (nginx),   │
│            caddy, watchtower                     │
└─────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────┐
│  Org B VPS — same image, different .env          │
└─────────────────────────────────────────────────┘
```

### Key Decisions

**Plugins are baked into the Docker image.** We are the plugin developer. No plugin registry or live delivery mechanism needed. Updating a plugin = build a new image tag = Watchtower picks it up on each VPS automatically.

**Caddy replaces dev nginx.** Auto-provisions Let's Encrypt TLS. No certbot, no manual cert renewal.

**Watchtower solves "dev is offline."** Push a commit from anywhere → GitHub builds + pushes image → Watchtower pulls on each VPS within 5 min. No SSH required for code/plugin updates.

**Config changes (`.env`, domain) always require SSH.** Unavoidable for security.

### Files to Build

| File | Notes |
|---|---|
| `api/Dockerfile.prod` | Remove `--reload`; `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2`; no volume mounts |
| `web/Dockerfile.prod` | Stage 1: `npm ci && npm run build`; Stage 2: nginx serves `/dist` |
| `docker-compose.prod.yml` | No `./api:/app` or `./web:/app` mounts; API uses GHCR image; Caddy + Watchtower |
| `Caddyfile.template` | `yourdomain.com { reverse_proxy /api/* api:8000; reverse_proxy /* web:80 }` |
| `.env.prod.example` | See below |
| `setup.sh` | One-time VPS setup: generate secrets, create `.env` from template, run migrations |
| `update.sh` | `git pull && docker compose pull api && docker compose up -d api && alembic upgrade head` |
| `.github/workflows/release.yml` | Trigger: push to `main` or tag `v*`; build → push to `ghcr.io/you/bos-api` |

```
# .env.prod.example
POSTGRES_PASSWORD=
API_SECRET_KEY=
ENCRYPTION_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://YOUR_DOMAIN/api/social/gmail/callback
FRONTEND_URL=https://YOUR_DOMAIN
PLATFORM_OPENROUTER_KEY=    # optional
```

> **Local dev note:** Set `FRONTEND_URL=http://localhost:8090` (the Docker nginx HQ port).
> `http://localhost` (port 80) has no listener by default — the host nginx config rejects
> unmatched hosts with 444 and has no `localhost` server block. Using port 80 locally
> causes OAuth callbacks and calendar widget links to silently fail.

### Implementation Order

1. `api/Dockerfile.prod` — remove `--reload`, bake code in
2. `web/Dockerfile.prod` — build step + nginx
3. `docker-compose.prod.yml` — Caddy + Watchtower
4. `.env.prod.example` + `setup.sh`
5. Test full stack on one real VPS end-to-end
6. `.github/workflows/release.yml` — image build + push to GHCR
7. Per-org setup README or Notion page

### Google OAuth Setup (per deployment)

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

### Open Questions

- Does the frontend use a hardcoded API key or `VITE_API_KEY` at build time? Needs audit before deploy.
- Watchtower polling interval: 5 min is fine for beta.
- Backup strategy: `pg_dump` cron + local rotation is enough for beta. Add off-site (S3/R2) when data matters.
