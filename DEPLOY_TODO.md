# DEPLOY_TODO.md — Prioritized Task List

> Flat, prioritized task list for deploy reliability and scale work.
> Detailed item specs live in `DEPLOY_COORDINATION.md` (Track A/B/C) and `DEPLOY.md` (candidate causes, incident log).
> Owner tags: `[claude-code]` = code/file changes, `[agent]` = investigation/experiment, `[human]` = operator action required, `[decision]` = needs human decision before work can start.

---

## Priority 0 — Immediate (blocks everything else)

| # | Task | Owner | Ref |
|---|---|---|---|
| P0-1 | Update GitHub Actions secret `STAGING_ENV_FILE` to include `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001`, `ENV_FILE=.env.staging` | `[human]` | DEPLOY.md INC-006, M7 |
| P0-2 | Decide staging gate design before re-enabling CI auto-deploy — pick one: protected branch + PR checks / manual CI approval / staging-ready label / time-delayed deploy | `[decision]` | DEPLOY_COORDINATION A2.5 |

---

## Priority 1 — Deploy Verification (closes the agent false-confidence loop)

| # | Task | Owner | Ref |
|---|---|---|---|
| ~~P1-1~~ | ~~Add `ARG GIT_SHA=dev` to `api/Dockerfile`, pass `--build-arg GIT_SHA=${{ github.sha }}` in CI `build-and-push` job~~ | — | DEPLOY.md C13, A3 — **done 2026-06-02** |
| ~~P1-2~~ | ~~Expose `git_sha` field in `GET /api/` health response (`api/config.py`, `api/routers/health.py`)~~ | — | DEPLOY.md C13, A3 — **done 2026-06-02** |
| ~~P1-3~~ | ~~Update `check-staging.sh` to print `git_sha` and `uptime_seconds` prominently; add `git_sha` as check 14 (non-blocking / informational until A3 is deployed)~~ | — | DEPLOY.md C16, C17, A4 — **done 2026-06-02** |
| ~~P1-4~~ | ~~Update `deploy-staging.sh` to print post-deploy `uptime_seconds` from health endpoint as the final confirmation line~~ | — | DEPLOY.md C17, A4 — **done 2026-06-02** |
| P1-5 | Add "Agent Deploy Protocol" section to `CLAUDE.md` — explicit rule that push ≠ staging updated, and verification requires `git_sha` + `uptime_seconds` check | `[claude-code]` | DEPLOY.md C12, A5 |

---

## Priority 2 — Elimination Hypotheses (Track C)

Each item eliminates a class of debug problems when shipped. Implement → validate by observing that problem class stops recurring.

| # | Task | Owner | Ref | Eliminates |
|---|---|---|---|---|
| ~~P2-1~~ | ~~E1: `git_sha` in health endpoint — bake SHA at CI build, expose in `GET /api/`, add to `check-staging.sh`~~ | — | COORD O1 | **done 2026-06-02** |
| P2-2 | E2: Agent Deploy Protocol in `CLAUDE.md` — push ≠ deploy; web/ rebuild required; verify `git_sha` + uptime | `[claude-code]` | COORD E2 | C12 agent-side, C15, false-confidence class |
| P2-3 | E3: re-enable CI auto-deploy with staging gate (blocked on P0-2 decision) | `[claude-code]` + `[human]` | COORD E3 | C12 structural |
| P2-4 | E4: update `STAGING_ENV_FILE` GitHub secret (blocked on P0-1 human action) | `[human]` | COORD E4 | C11, port-drift, INC-004/006 replay |

---

## Priority 3 — Staging Reliability (after P0-P2 complete)

| # | Task | Owner | Ref |
|---|---|---|---|
| P3-1 | Re-enable CI staging auto-deploy with agreed gate from P0-2 | `[claude-code]` + `[human]` | DEPLOY.md C12, A2.5 |
| P3-2 | Prove end-to-end deploy path: commit → push → CI image build → auto-deploy → `staging.klaroha.com` healthy with correct `git_sha` — no manual intervention | `[agent]` validation | DEPLOY_COORDINATION A2 |
| P3-3 | Document rollback procedure: how to revert to previous `sha-{SHA}` image tag on staging and production without data loss | `[claude-code]` | DEPLOY.md M1 |
| P3-4 | Update `check-staging.sh` capability count threshold from hardcoded `≥ 20` to a dynamic value or documented update process | `[claude-code]` | DEPLOY.md M2 |

---

## Priority 4 — First Org Deploy Foundation (longer horizon)

Sequence is fixed — each item depends on the previous. Do not start B2 before B1 is decided.

| # | Task | Owner | Ref |
|---|---|---|---|
| P4-1 | Design and approve OAuth relay architecture (`connect.klaroha.com`) | `[decision]` → `[claude-code]` | DEPLOY.md Build Order #1, COORD B1 |
| P4-2 | Implement first-boot init script: auto-generate `API_SECRET_KEY` + `ENCRYPTION_KEY`, run `alembic upgrade head`, bootstrap admin | `[claude-code]` | DEPLOY.md Build Order #2, COORD B2 |
| P4-3 | Reduce required install-time env to `KLAROHA_DEPLOYMENT_KEY` + `KLAROHA_RELAY_URL` + `FRONTEND_URL` | `[claude-code]` | DEPLOY.md Build Order target, COORD B3 |
| P4-4 | Define and test setup wizard path: first login → org name → brand brief import → CMO operational | `[claude-code]` | COORD B4 |
| P4-5 | Build deployment key issuance and relay access gating | `[claude-code]` | DEPLOY.md Build Order #3, COORD B6 |
| P4-6 | Build `curl install.klaroha.com | bash` installer wrapping docker compose + first-boot init | `[claude-code]` | COORD B5 |

---

## Priority 5 — Scale Ops Infrastructure (50+ active orgs trigger)

These are not needed now but must be designed before reaching 50 active customer orgs.

| # | Task | Owner | Ref |
|---|---|---|---|
| P5-1 | In-app admin diagnostic panel: version info, migration status, provider health, env completeness — no CLI required | `[claude-code]` | DEPLOY.md M3 |
| P5-2 | GitOps reconciliation (ArgoCD or Flux equivalent) — continuous reconciliation of running state against git | `[decision]` | DEPLOY.md Industry Standard #3 |
| P5-3 | Ephemeral preview environments per PR | `[decision]` | DEPLOY.md Industry Standard #5 |
| P5-4 | Infrastructure as Code for org environments (Terraform/Pulumi/Helm) | `[decision]` | DEPLOY.md Industry Standard #6 |

---

## Completed

_(move items here when done, with date and one-line resolution)_

| Date | Task | Resolution |
|---|---|---|
| 2026-06-02 | Add scale directive to DEPLOY.md | Added §Scale Directive + C12-C17 hypotheses |
| 2026-06-02 | Document C12-C17 in DEPLOY.md | Done — see candidate causes section |
| 2026-06-02 | C4: smoke-local.sh scope hypothesis | **validated** — script inspection + image probe confirm GHCR image used, not local source |
| 2026-06-02 | C5a: manual deploy tag-resolution subclaim | **validated** — unset `DEPLOY_SHA` falls back to mutable `:staging`; live race claim split to C5b and remains blocked pending CI/GHCR/deploy evidence |
| 2026-06-02 | O1/E1: git_sha deploy verification | Added `GIT_SHA` Docker build arg/env, health `git_sha`, CI build arg, and `check-staging.sh` presence/match verification |
| 2026-06-02 | P1-4: uptime_seconds in deploy-staging.sh final banner | Added post-smoke-test health fetch; banner prints `image`, `git_sha`, `uptime_seconds` |
| 2026-06-02 | H2: push-does-not-deploy hypothesis | **falsified** — `deploy-staging` CI job is active (re-enabled by c82f94c); push to staging auto-deploys via CI |
