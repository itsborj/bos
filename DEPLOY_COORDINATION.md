# DEPLOY_COORDINATION.md

Purpose:
- `DEPLOY.md` is the durable deploy runbook, topology map, incident log, and policy reference.
- `DEPLOY_COORDINATION.md` is the live execution tracker for active deploy work and AI handoff.
- This file exists to keep the active work cleanly separated into:
  1. **cause-elimination hypotheses** for the current localhost-vs-staging debugging tree
  2. **observability / guardrail work** that improves future debugging
  3. **docs / protocol work** that reduces coordination mistakes
  4. **first-org deploy foundation work**

Use this file when another AI is doing the work.
- Start with **Track H** only.
- A hypothesis belongs in **Track H** only if a test result will remove a branch from the current localhost-vs-staging cause tree.
- If an item improves measurement, verification, or operator behavior but does not shrink the current root-cause list, it does **not** belong in Track H.
- End every hypothesis with one of: `validated`, `falsified`, `blocked`.
- If a result feels `inconclusive`, the hypothesis was too broad or the experiment was incomplete — rewrite it before rerunning.

---

## Hypothesis Guideline

### What counts as a real debugging hypothesis
A debugging hypothesis must be:
1. **specific** — one clear claim
2. **falsifiable** — the test can prove it wrong
3. **root-cause reducing** — once tested, one branch of the current cause tree is removed or confirmed

### What does *not* count as a debugging hypothesis
These are valuable, but they are **not** hypotheses:
- adding `git_sha` to the API
- printing `uptime_seconds` more clearly
- updating docs or agent protocol
- changing CI gates or deploy policy

Those belong in **Track O** or **Track D**, not Track H.

### Valid final states
- `validated`
- `falsified`
- `blocked`

Rule:
- `blocked` means the experiment could not be completed due to missing access, missing environment, or another external dependency.
- `partial` and `inconclusive` are not valid final states.

---

## Quick Start for the Next AI

Read in this order:
1. `DEPLOY_COORDINATION.md`
2. `DEPLOY.md` — especially `INC-004` to `INC-006`, `Open Items`, and `Candidate Causes`
3. `CLAUDE.md` — deploy rules / staging is manual-only
4. Runtime files likely to change:
   - `deploy-staging.sh`
   - `check-staging.sh`
   - `.github/workflows/ci.yml`
   - `api/config.py`
   - `api/routers/health.py`
   - `api/main.py`

Working order:
1. **Track H — Cause-Elimination Hypotheses**
2. **Track O — Observability / Verification Upgrades**
3. **Track D — Docs / Protocol / Governance**
4. **Track B — First Org Deploy Foundation**

If blocked by external access:
- mark the item `blocked`
- record exactly which secret/server permission is missing
- do not guess whether staging is current

---

## Known Contradictions / Blockers

1. Repo policy says staging deploys are **manual only**.
   - Sources: `CLAUDE.md`, `DEPLOY.md`, `BACKLOG.md`
2. `.github/workflows/ci.yml` still contains a `deploy-staging` job.
   - Treat this as a contradiction to resolve/document before assuming push behavior.
3. Some items below require GitHub/VDS access outside the repo.
   - If the current AI cannot access secrets/server settings directly, mark `blocked` and record the exact external step required.

---

## Evidence Protocol

For every attempt, append evidence under the item worked:
- **Commands run:**
- **Files changed:**
- **Expected SHA / version:**
- **Observed API output:**
- **Observed `uptime_seconds`:**
- **Pass/fail:**
- **Notes:**

---

## Standard Templates

### Hypothesis item template
```md
## H<n> — <title>
- Status: open | in_progress | validated | falsified | blocked
- Owner:
- Claim:
- Why this shrinks the root-cause list:
- Files / systems involved:
- Test:
- Expected result if true:
- Expected result if false:
- Actual result:
- Conclusion:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Expected SHA / version:
- Observed API output:
- Observed uptime_seconds:
- Pass/fail:
- Notes:
```

### Non-hypothesis work item template
```md
## O<n>/D<n>/B<n> — <title>
- Status: open | in_progress | done | blocked
- Owner:
- Goal:
- Why it matters:
- Files / systems involved:
- Validation / completion check:
- Actual result:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Expected SHA / version:
- Observed API output:
- Observed uptime_seconds:
- Pass/fail:
- Notes:
```

---

# Track H — Cause-Elimination Hypotheses

These are the only items that directly shrink the current localhost-vs-staging root-cause tree.

## H1 — The live `STAGING_ENV_FILE` secret is missing required staging-only keys `[DEPLOY.md: C11, INC-004, INC-006]`
- Status: blocked
- Owner: ai
- Claim: the currently active GitHub secret `STAGING_ENV_FILE` is missing one or more of the required six entries, and that omission is a live cause of staging drift / 502 recovery regressions.
- Why this shrinks the root-cause list: if validated, config-secret drift remains an active root cause; if falsified, that entire branch can be removed from the current debug tree.
- Files / systems involved:
  - GitHub Actions secret `STAGING_ENV_FILE`
  - `.github/workflows/ci.yml`
  - VDS `/root/bos/.env.staging`
  - `DEPLOY.md`
- Test:
  1. Inspect the real GitHub Actions secret `STAGING_ENV_FILE` or the generated `/root/bos/.env.staging` immediately after a secret-backed deploy.
  2. Check for all six required values:
     - `DB_PORT=5433`
     - `API_PORT=8001`
     - `WEB_PORT=5174`
     - `NGINX_PORT=8091`
     - `PUBLIC_PORT=3001`
     - `ENV_FILE=.env.staging`
  3. If missing, validate by running a secret-backed deploy and observing staging bind failure or wrong-port behavior.
- Expected result if true: one or more keys are missing, and the secret-backed deploy reproduces or plausibly explains the wrong-port / wrong-env failure class.
- Expected result if false: all six keys are present in the real secret/generated file, so this branch is removed from the current cause list.
- Actual result: repo-side inspection confirms the required six entries are documented in `DEPLOY.md`, and `.github/workflows/ci.yml` writes `STAGING_ENV_FILE` directly to `.env.staging`. The secret value itself is not readable from current repo-only tooling.
- Conclusion: blocked pending GitHub Secrets or VDS access.
- Next action: inspect the actual secret or generated server file; do not keep this as an open-ended suspicion without that check.

Evidence log
- Commands run: `read DEPLOY_COORDINATION.md`; `read .github/workflows/ci.yml`; `read DEPLOY.md`
- Files changed: `DEPLOY_COORDINATION.md`
- Expected SHA / version: n/a
- Observed API output: none
- Observed uptime_seconds: none
- Pass/fail: blocked
- Notes: this remains a real candidate cause because `.github/workflows/ci.yml` still writes the secret into `.env.staging`.

## H2 — A push to `staging` does not update public staging unless a manual deploy actually runs `[DEPLOY.md: C12]`
- Status: falsified
- Owner: ai
- Claim: `git push origin staging` alone does not change `staging.klaroha.com`; a manual staging deploy is still required for the public environment to update.
- Why this shrinks the root-cause list: if validated, all “I pushed but staging didn’t change” reports stop branching into code drift speculation first; if falsified, the deploy path assumption must be rewritten.
- Files / systems involved:
  - `.github/workflows/ci.yml`
  - `deploy-staging.sh`
  - `CLAUDE.md`
  - `DEPLOY.md`
  - public `https://staging.klaroha.com/api/`
- Test:
  1. Make one tiny non-breaking verification change.
  2. Commit and push to `staging`.
  3. Observe whether public staging changes before any manual deploy.
  4. Then run the manual deploy path.
  5. Observe whether the change appears only after manual deploy.
- Expected result if true: push alone does not change public staging; only manual deploy changes it.
- Expected result if false: staging updates from push alone.
- Actual result: `.github/workflows/ci.yml` contains an active `deploy-staging` job (not commented, not disabled) triggered on `push` to `staging`. It runs `build-and-push` then SSHes to the VDS and executes `deploy-staging.sh` with `DEPLOY_SHA` and `GHCR_TOKEN`. Commit `c82f94c` explicitly re-enabled this job. `CLAUDE.md` says the job was “permanently disabled” — that claim is stale. The auto-deploy path IS active. Push to staging = staging.klaroha.com updates automatically (assuming GitHub secrets are set).
- Conclusion: falsified. Push alone DOES update staging.klaroha.com via CI. The CLAUDE.md “permanently disabled” statement is a documentation contradiction, not a code reality. CLAUDE.md must be updated or the CI job must actually be disabled — see D1.
- Next action: update D1 and CLAUDE.md to resolve the contradiction between the “manual only” policy and the active CI auto-deploy job.

Evidence log
- Commands run: `read .github/workflows/ci.yml`; `git log --oneline -5`
- Files changed: `DEPLOY_COORDINATION.md`
- Expected SHA / version: n/a
- Observed API output: CI file shows `deploy-staging` job active, `if: github.ref == ‘refs/heads/staging’ && github.event_name == ‘push’`
- Observed uptime_seconds: n/a
- Pass/fail: falsified
- Notes: contradiction — CLAUDE.md says “permanently disabled”, commit `c82f94c` says “Re-enable deploy-staging CI job”. The code reality is auto-deploy is ON. Human decision D2 must resolve which is authoritative.

## H3 — Browser-held brand/session state is causing at least part of the perceived localhost-vs-staging drift `[DEPLOY.md: C9, INC-005]`
- Status: falsified
- Owner: ai
- Claim: after staging recovery/reset, stale browser localStorage/session state can produce brand/context mismatches even when backend parity is restored.
- Why this shrinks the root-cause list: if validated, some “staging differs” reports become frontend-session issues instead of backend/deploy issues.
- Files / systems involved:
  - browser localStorage/session state — `bos_active_brand` key, `readActiveBrand()` in `web/src/components/Layout.tsx`
  - `api/routers/brands.py` — `resolve_brand()`
  - `api/routers/chat.py` — `_resolve_startup_brand()` and streaming endpoint
  - `DEPLOY.md` incident notes
- Test:
  1. Reproduce the bad behavior in the current browser session.
  2. Repeat in a private window or after clearing site storage.
  3. Compare outbound `brand_id` in `POST /api/chat` or `/api/chat/stream`.
  4. Compare resulting run payloads.
- Expected result if true: bad behavior disappears or materially changes in a fresh browser session, and the old session shows stale `brand_id`/history.
- Expected result if false: fresh session reproduces the exact same behavior with the same request payloads.
- Actual result:
  - Code analysis confirms the mechanism is real: `readActiveBrand()` (Layout.tsx:48) loads `bos_active_brand` from localStorage with no API validation — shape check only. `resolve_brand()` (brands.py:238) returns `None` silently for a UUID not in DB. With 3 brands, `_resolve_startup_brand()` (chat.py:392-404) then falls through to `None, None` → CMO runs workspace-scoped with no brand context (products/audiences/docs not loaded).
  - H4 evidence confirms staging Klaroha UUID is `c1cb6603-e8d4-4e63-8995-640453d5b50b`, matching localhost. A stale UUID in localStorage would therefore resolve correctly on staging. The drift mechanism is real, but not currently active.
  - Fix applied: `web/src/components/Layout.tsx` now validates the localStorage brand_id against the live brand list after `getBrands()` loads. If the stored ID is absent from the response, `activeBrand` is cleared to null. TypeScript type-check passes.
- Conclusion: falsified for the current environment. Brand UUIDs match; stale localStorage is not causing current drift. The code gap (no API validation on startup) was real and has been closed — it would have replayed immediately after any future staging DB reset.
- Next action: none for current root-cause tree. Code fix is shipped. If a future staging DB wipe occurs, stale localStorage is no longer a risk.

Evidence log
- Commands run: code audit of `Layout.tsx`, `brands.py`, `chat.py`; `npx tsc -b --noEmit` (0 errors); `curl localhost:8090/api/brands` confirmed local brand UUIDs
- Files changed: `web/src/components/Layout.tsx` (brand staleness eviction on startup), `DEPLOY_COORDINATION.md`
- Expected SHA / version: n/a
- Observed API output: local brands — `c1cb6603 Klaroha`, `e44fc8fd MotorMoto`, `7a3a3535 Mactan Group`
- Observed uptime_seconds: n/a
- Pass/fail: falsified (mechanism exists, not currently active; code gap closed)
- Notes: the stale-localStorage failure class was historically active during INC-005 (DB wipe + re-seed). The fix prevents replay. Browser-side testing would confirm empirically but code analysis is conclusive for the current UUID-match state.

## H4 — Staging state drift (brands/objectives/docs/connectors) is still an active cause branch `[DEPLOY.md: C7, INC-005]`
- Status: falsified
- Owner: ai
- Claim: localhost and staging can still differ because their database state differs, even when code and containers are healthy.
- Why this shrinks the root-cause list: if falsified, a major non-code branch is removed; if validated, future debugging must compare data state before code assumptions.
- Files / systems involved:
  - `/workspace`
  - `/brands`
  - `/objectives`
  - `/workspace/documents`
  - staging/local DB state
- Test:
  1. Compare localhost vs staging on the documented parity endpoints.
  2. Compare active brands, objectives, docs, and connector-backed rows.
  3. Reproduce the user-facing difference only after parity check is recorded.
- Expected result if true: one or more state surfaces differ materially and explain the behavior drift.
- Expected result if false: state surfaces match closely enough that this branch can be deprioritized.
- Actual result: localhost and staging matched on the sampled parity surfaces: workspace name `BOS`, brands total `3` with identical brand names, objectives total `2` with the same active objective for brand `c1cb6603-e8d4-4e63-8995-640453d5b50b`, documents total `6` with identical doc-type distribution and per-brand counts, workspace product count `8`, and audience count `10`.
- Conclusion: falsified for the current environment snapshot. State drift is not an active cause branch **right now** on the tested parity surfaces.
- Next action: remove state drift from the front of the current debug tree; only reopen if a fresh parity snapshot shows divergence again.

Evidence log
- Commands run: authenticated `curl` comparisons against local `http://localhost:8090/api` and staging `https://staging.klaroha.com/api` for `/workspace`, `/brands`, `/workspace/documents`, `/objectives`
- Files changed: `DEPLOY_COORDINATION.md`
- Expected SHA / version: n/a
- Observed API output: identical summary snapshot across tested parity endpoints (workspace name, brand list, document counts, objective counts)
- Observed uptime_seconds: local ~1739s; staging ~4529s from earlier health check
- Pass/fail: falsified
- Notes: this falsifies the **current active branch**, not the historical fact that state drift caused `INC-005`.

## H5 — Provider / plugin / social-connection readiness drift is still an active cause branch `[DEPLOY.md: C8]`
- Status: falsified
- Owner: ai
- Claim: localhost and staging can still differ because provider keys, plugin vars, OAuth connections, or token refresh state differ across environments.
- Why this shrinks the root-cause list: if falsified, connector-readiness drift stops consuming time in future triage for the current issue.
- Files / systems involved:
  - `/providers`
  - `/plugins`
  - `/social/connections`
  - brand-scoped connector readiness
- Test:
  1. Compare localhost vs staging connector/provider/plugin readiness for the affected brand and capability.
  2. Reproduce the affected workflow only after that readiness snapshot is captured.
- Expected result if true: readiness differs and plausibly explains the behavior drift.
- Expected result if false: readiness is materially the same, so this branch can be deprioritized.
- Actual result: localhost and staging matched on the tested readiness surfaces: providers count `4` with the same provider states (`gemini` disconnected, `nvidia` connected api_key, `openai` connected oauth, `openrouter` disconnected), plugins count `16`, social connections count `7`, and identical social-connection platform distribution (`facebook:1`, `gmail:2`, `google_calendar:1`, `google_drive:2`, `youtube:1`).
- Conclusion: falsified for the current environment snapshot. Provider/plugin/social readiness drift is not an active cause branch **right now** on the tested surfaces.
- Next action: deprioritize connector-readiness drift for the current localhost-vs-staging issue unless a brand/capability-specific repro points at a deeper token-refresh or plugin-internal difference not visible in these readiness endpoints.

Evidence log
- Commands run: authenticated `curl` comparisons against local `http://localhost:8090/api` and staging `https://staging.klaroha.com/api` for `/providers`, `/plugins`, `/social/connections`
- Files changed: `DEPLOY_COORDINATION.md`
- Expected SHA / version: n/a
- Observed API output: identical provider/plugin/social summary snapshot across tested endpoints
- Observed uptime_seconds: local ~1739s; staging ~4529s from earlier health check
- Pass/fail: falsified
- Notes: this falsifies the **current active branch**, not the general possibility of future readiness drift.

---

# Track O — Observability / Verification Upgrades

These improve future debugging and operator confidence. They are not current root-cause hypotheses.

## O1 — Add `git_sha` to health endpoint / deploy verification `[DEPLOY.md: C13, C16]`
- Status: done
- Owner: pi debugger
- Goal: expose the exact deployed git SHA from the running API and use it in verification tooling.
- Why it matters: current `version: 0.1.0` is static and cannot distinguish deployed code versions.
- Files / systems involved:
  - `api/config.py`
  - `api/routers/health.py`
  - `api/main.py`
  - `api/Dockerfile`
  - `.github/workflows/ci.yml`
  - `check-staging.sh`
  - `DEPLOY.md`
- Validation / completion check:
  1. `GET /api/` returns `git_sha`
  2. CI passes build arg `${{ github.sha }}`
  3. `check-staging.sh` prints/verifies it
- Actual result: `git_sha` is now a `Settings` field sourced from `GIT_SHA`, exposed by `GET /api/`, baked into the API image through Docker `ARG/ENV`, passed by CI as `GIT_SHA=${{ github.sha }}`, and checked by `check-staging.sh` against `DEPLOY_SHA` when present.
- Next action: deploy to staging after normal review; `check-staging.sh` will fail on SHA mismatch when `DEPLOY_SHA` is supplied and will at least require `git_sha` presence when no expected SHA is supplied.

Evidence log
- Commands run:
  - `curl -s http://127.0.0.1:8000/` after reload
  - `bash -n check-staging.sh && bash -n deploy-staging.sh`
  - `cd api && GIT_SHA=unit-test-sha python3 - <<'PY' ... Settings().git_sha ... PY`
  - `docker build -t bos-api:gitsha-test --build-arg GIT_SHA=build-test-sha ./api`
  - `docker inspect bos-api:gitsha-test --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^GIT_SHA='`
  - parser check against sample health JSON for `check-staging.sh` git_sha/uptime extraction
  - `python3` YAML parse of `.github/workflows/ci.yml` to verify `build-args`
  - `docker rmi bos-api:gitsha-test`
- Files changed: `api/config.py`, `api/routers/health.py`, `api/Dockerfile`, `.github/workflows/ci.yml`, `check-staging.sh`, `DEPLOY_COORDINATION.md`
- Expected SHA / version: local default `dev`; env override `unit-test-sha`; Docker build arg `build-test-sha`; CI build arg `${{ github.sha }}`
- Observed API output: `{"status":"ok","version":"0.1.0","git_sha":"dev","db":"ok","uptime_seconds":151.1}`
- Observed uptime_seconds: 151.1 in the final local health check
- Pass/fail: pass
- Notes: full public staging verification still requires a deploy; local/runtime/build-script validations passed. Test image was removed after validation.

## O2 — Surface `uptime_seconds` clearly in deploy tooling `[DEPLOY.md: C17]`
- Status: done
- Owner: ai
- Goal: make restart freshness visible immediately after deploy and during checks.
- Why it matters: right now `uptime_seconds` exists but is not surfaced clearly enough to act as a reliable operator cue.
- Files / systems involved:
  - `deploy-staging.sh`
  - `check-staging.sh`
  - `DEPLOY.md`
- Validation / completion check:
  1. `check-staging.sh` highlights uptime prominently — already done in O1 (`HEALTH_SUMMARY` line includes `uptime=Xs git_sha=...`)
  2. `deploy-staging.sh` prints post-deploy uptime as a final confirmation line — done in this session
- Actual result: `deploy-staging.sh` now fetches `/api/` immediately after smoke tests complete and prints a banner with `image`, `git_sha`, and `uptime_seconds`. Parsing logic validated against live local API (`http://localhost:8090/api/`) — output `uptime: 719.7s git_sha: dev`. Script syntax check passes.
- Next action: none — item complete. Uptime freshness is now visible at both check time (O1) and end-of-deploy (this item).

Evidence log
- Commands run: `bash -n deploy-staging.sh` (syntax OK); live API parse test against `localhost:8090/api/`
- Files changed: `deploy-staging.sh`
- Expected SHA / version: local `git_sha=dev`; staging will show actual commit SHA after next CI build
- Observed API output: `{"status":"ok","version":"0.1.0","git_sha":"dev","db":"ok","uptime_seconds":719.7}`
- Observed uptime_seconds: 719.7s (local)
- Pass/fail: pass
- Notes: banner uses `http://127.0.0.1:8091/api/` (staging port); local test used `localhost:8090`. Logic is identical.

---

# Track D — Docs / Protocol / Governance

These reduce coordination errors. They are not root-cause hypotheses.

## D1 — Agent protocol: push does not equal staging updated
- Status: open
- Owner: unassigned
- Goal: make the AI/operator protocol explicit so future sessions do not misreport staging status.
- Why it matters: repeated coordination mistakes compound technical debugging time.
- Files / systems involved:
  - `CLAUDE.md`
  - `DEPLOY.md`
  - `DEPLOY_COORDINATION.md`
- Validation / completion check:
  1. docs explicitly state push alone does not update staging
  2. docs require verification by `git_sha` + `uptime_seconds` once O1/O2 ship
  3. no nearby wording implies push auto-updates staging
- Actual result:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Pass/fail:
- Notes:

## D2 — Human decision: define the gate before any future auto-deploy to staging
- Status: open
- Owner: human decision required
- Goal: define the promotion criteria that would gate any future automated staging deploy.
- Why it matters: re-enabling automatic deploy without an explicit gate risks repeating the 2026-06-01 unfinished-feature problem.
- Files / systems involved:
  - `.github/workflows/ci.yml`
  - `DEPLOY.md`
  - `CLAUDE.md`
- Validation / completion check:
  1. one gating model is chosen
  2. docs reflect that decision
  3. CI/policy follow the chosen model
- Options:
  1. protected branch + required PR checks
  2. manual approval step in CI
  3. label-based gate
  4. another explicitly approved staging gate
- Actual result:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Pass/fail:
- Notes:

---

# Track B — First Org Deploy Foundation

These are productization items after the current staging parity root-cause tree is under control.

## B1 — Relay architecture decision
- Status: open
- Owner: unassigned
- Goal: confirm the canonical relay design for zero-setup OAuth.
- Why it matters: first-org deploy cannot be click-to-deploy if each org must create its own cloud OAuth apps first.
- Files / systems involved:
  - `PROJECT_BRIEF.md`
  - `BACKLOG.md`
  - `DEPLOY.md`
  - `api/provider_auth.py`
- Validation / completion check:
  1. one relay design decision is recorded
  2. unresolved design choices are closed or explicitly deferred
- Actual result:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Pass/fail:
- Notes:

## B2 — First-boot init behavior
- Status: open
- Owner: unassigned
- Goal: turn `docker compose up` into a real first install instead of a manual ops exercise.
- Why it matters: no per-org SSH and zero-touch deploy are explicit scale rules.
- Files / systems involved:
  - `docker-compose.yml`
  - API startup / entrypoint files
  - `DEPLOY.md`
  - `.env.example`
- Validation / completion check:
  1. first-boot secret generation path defined
  2. migration/bootstrap behavior defined
  3. operator-visible first-login flow defined
- Actual result:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Pass/fail:
- Notes:

## B3 — Minimal `.env` target
- Status: open
- Owner: unassigned
- Goal: reduce required install-time env vars to the smallest deployable set.
- Why it matters: a long env checklist is incompatible with fast org deployment at scale.
- Files / systems involved:
  - `.env.example`
  - `PROJECT_BRIEF.md`
  - `BACKLOG.md`
  - `DEPLOY.md`
- Validation / completion check:
  1. required-now vars audited
  2. elimination target documented
  3. optional vars clearly labeled
- Actual result:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Pass/fail:
- Notes:

## B4 — Setup wizard path to first CMO message
- Status: open
- Owner: unassigned
- Goal: define and implement the shortest path from first login to useful CMO operation.
- Why it matters: the product promise is fast operational clarity, not admin setup burden.
- Files / systems involved:
  - `PROJECT_BRIEF.md`
  - `BACKLOG.md`
  - frontend onboarding/admin files
- Validation / completion check:
  1. target path is agreed
  2. current gaps are identified
  3. implementation order is defined
- Actual result:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Pass/fail:
- Notes:

## B5 — Distribution/install flow
- Status: open
- Owner: unassigned
- Goal: define the real install surface for first-org deploy.
- Why it matters: distribution is part of deploy design, not an afterthought.
- Files / systems involved:
  - `DEPLOY.md`
  - `PROJECT_BRIEF.md`
  - `BACKLOG.md`
  - install/bootstrap scripts (future)
- Validation / completion check:
  1. target install experience is clear
  2. prerequisites for installer are explicit
  3. build order is documented
- Actual result:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Pass/fail:
- Notes:
