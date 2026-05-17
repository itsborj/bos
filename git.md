# git.md — Git & Deployment Reference

> Deployment operations, known issues, and deploy runbook for the BOS dev server.
> For the production deployment model (GHCR + Watchtower), see `DEPLOY.md`.

---

## Server Layout

Both stacks run on the same VDS from `~/bos/` using different compose files.

| Stack | Compose file | Branch | Domain | Ports |
|---|---|---|---|---|
| Production | `docker-compose.yml` | `main` | hq.klaroha.com | api:8000, web:5173, nginx:8090 |
| Staging | `docker-compose.staging.yml` | `staging` | staging.klaroha.com | api:8001, web:5174, nginx:8080 |

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
# On local machine — commit and push
git add <files>
git commit -m "message"
git push origin staging

# On server (SSH in)
cd ~/bos
git fetch origin && git reset --hard origin/staging
docker compose -p staging -f docker-compose.staging.yml build web && docker compose -p staging -f docker-compose.staging.yml up -d web
```

If API changed too:
```bash
docker compose -p staging -f docker-compose.staging.yml restart api
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
```

---

## Known Issues & Lessons

### 2026-05-17 — Deploying to wrong stack

**What happened:** `docker compose build web && docker compose up -d web` (no `-p` or `-f` flag) rebuilds the `bos` (production) stack, not staging. Both stacks live in `~/bos/` so the working directory gives no hint which stack you're targeting.

**Fix:** Always use `-p staging -f docker-compose.staging.yml` for staging operations.

### 2026-05-17 — Divergent branches on server

**What happened:** Server's local `staging` branch had commits that weren't on the remote (or vice versa). `git pull` refused to run without a reconciliation strategy.

**Fix:** Use `git fetch origin && git reset --hard origin/<branch>` for server deploys. The server is not a development machine — local commits on the server are never intentional.

### 2026-05-17 — Docker build fully cached despite new code

**What happened:** `git pull` failed silently (divergent branches), but the `docker compose build` still ran after it — using the old code. All layers were `CACHED`. The new container was started but had no changes.

**Tell:** Build context transfer size stays small (e.g. 324kB) and every layer shows `CACHED`. A real rebuild transfers more context and re-executes `COPY . .` and `RUN npm run build`.

**Fix:** Confirm `git reset --hard origin/<branch>` ran successfully before building.

### 2026-05-17 — Server branch state left on `main` after staging deploy

**What happened:** `git reset --hard origin/staging` was run while on the `main` branch, moving `main`'s HEAD to the staging commit. Server ended up on `main` pointing at a staging commit.

**Fix after the fact:**
```bash
git checkout staging 2>/dev/null || git checkout -b staging --track origin/staging
```

**Prevention:** Always verify `git branch` before resetting.

---

## Backlog

- [ ] Add `name:` field to `docker-compose.staging.yml` so project name is explicit and never inferred
- [ ] Write a `deploy.sh` script wrapping the full staging deploy sequence (fetch → reset → build → up)
- [ ] Set `git config pull.rebase false` (or `--ff-only`) on the server so `git pull` doesn't fail on divergence
- [ ] Investigate why the server's `staging` branch and local diverged — may be leftover commits from a past manual edit on the server
