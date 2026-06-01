# DEPLOY_COORDINATION.md

Purpose:
- `DEPLOY.md` is the durable deploy runbook, topology map, incident log, and policy reference.
- `DEPLOY_COORDINATION.md` is the live execution tracker for active deploy work, hypothesis testing, and AI handoff.
- If these files ever drift, update `DEPLOY.md` for durable truth and use this file to track the work needed to reconcile them.

Use this file when another AI is doing the work.
- Pick the highest-priority open item in **Track A** first, then Track C, then Track B.
- Record evidence after every attempt.
- End every item with one of: `validated`, `falsified`, `blocked`.
- If a result feels `partial` or `inconclusive`, the hypothesis was too broad or the experiment was incomplete — split or rewrite it before re-running.
- Do not treat `git push origin staging` as a deploy. Verify deployed freshness explicitly.

## Scale Directive (read before working any item)

BOS targets **hundreds of new org deployments per day** and **10,000+ concurrent active org deployments**. Every fix and solution must align with this:

| Rule | What it means in practice |
|---|---|
| No per-org SSH | A fix that requires Klaroha to SSH into a customer server is not done — it's a product gap |
| No Klaroha data access | Diagnosis must be possible from admin UI, org-owned logs, or the health endpoint |
| Zero-touch new org deploys | Every manual post-boot step must become automated first-boot behavior |
| Operator-resolvable issues | Org admin resolves via admin panel or one documented command |
| Automated verification | Health, version, migration status — all machine-readable, never human-interpreted only |

Full directive: `DEPLOY.md §Scale Directive`

Any Track A or Track B item resolved by manual SSH is **not closed** — add a BACKLOG item for the automated equivalent.

## Quick Start for the Next AI

Read in this order:
1. `DEPLOY_COORDINATION.md`
2. `DEPLOY.md` — especially Incident Log items `INC-004` to `INC-006` and `Open Items`
3. `CLAUDE.md` — deploy rules / staging is manual-only
4. Runtime files likely to change:
   - `deploy-staging.sh`
   - `check-staging.sh`
   - `.github/workflows/ci.yml`
   - `api/config.py`
   - `api/routers/health.py`
   - `api/main.py`

Default first debugging target:
1. `A1 — STAGING_ENV_FILE` parity
2. `A2 — prove push != deploy and prove the real path`
3. `A4 — uptime visibility`
4. `A3 — git_sha`
5. `A5 — docs/protocol cleanup`

If blocked by external access:
- mark the item `blocked`
- record exactly which secret/server permission is missing
- do not guess whether staging is current

---

## Working Order

1. **Config/secret parity**
2. **Deploy verification signals**
3. **Version visibility (`git_sha`)**
4. **Docs/protocol cleanup**
5. **First-org deploy foundation**

Rule: finish Track A as far as practical before broadening Track B.

---

## Known Contradictions / Blockers

1. Repo policy says staging deploys are **manual only**.
   - Sources: `CLAUDE.md`, `DEPLOY.md`, `BACKLOG.md`
2. `.github/workflows/ci.yml` still contains a `deploy-staging` job.
   - Treat this as a contradiction to resolve/document before assuming push behavior.
3. `DEPLOY.md` documents active staging parity work and first-org deploy work in one place.
   - This file exists to separate active execution tracking from the long-form runbook.
4. Some tasks below require GitHub/VDS access outside the repo.
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

Validation outcomes allowed:
- `validated`
- `falsified`
- `blocked`

Rule:
- `partial` and `inconclusive` are not valid final outcomes.
- If you reach either, rewrite the hypothesis into smaller falsifiable claims or mark the current attempt `blocked` because the experiment could not be completed.

---

## Standard Item Template

```md
### Item <id> — <title>
- Status: open | in_progress | validated | falsified | blocked
- Owner: <ai / human / unassigned>
- Goal:
- Hypothesis:
- Why it matters:
- Files likely involved:
- Validation steps:
- Expected result:
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

---

# Track A — Staging Deploy Parity

## A1 — `STAGING_ENV_FILE` secret parity `[DEPLOY.md: C11, INC-004, INC-006]`
- Status: blocked
- Owner: ai
- Goal: make the staging secret the true source of staging env values so deploys stop re-breaking `.env.staging`.
- Hypothesis: staging keeps drifting because the GitHub secret `STAGING_ENV_FILE` is missing the required staging-only host-port overrides and `ENV_FILE=.env.staging`.
- Why it matters: until this is corrected, a later deploy can silently reintroduce the 502 / wrong-env failure mode described in `DEPLOY.md` (`INC-004`, `INC-006`).
- Files likely involved:
  - `DEPLOY.md`
  - `.github/workflows/ci.yml`
  - `deploy-staging.sh`
- Validation steps:
  1. Compare the required values in `DEPLOY.md` against the real `STAGING_ENV_FILE` secret.
  2. Confirm the secret includes all of:
     - `DB_PORT=5433`
     - `API_PORT=8001`
     - `WEB_PORT=5174`
     - `NGINX_PORT=8091`
     - `PUBLIC_PORT=3001`
     - `ENV_FILE=.env.staging`
  3. Trigger or perform a staging deploy using the secret-backed env.
  4. Verify staging starts on the staging ports, not production ports.
- Expected result: secret-backed deploy recreates the staging stack cleanly with no manual `.env.staging` surgery.
- Actual result: repo-side inspection confirms the required six staging-only entries are documented in `DEPLOY.md`, and `.github/workflows/ci.yml` writes `STAGING_ENV_FILE` directly to `.env.staging` before deploy. However, the secret value itself is not readable from repo/tooling in this session, so parity cannot be confirmed from source alone.
- Conclusion: blocked pending GitHub Secrets or VDS access. The hypothesis remains plausible and is already supported by `INC-006`, but current-session tooling cannot validate the live secret contents.
- Next action: inspect the actual GitHub Actions secret `STAGING_ENV_FILE` (or the generated `/root/bos/.env.staging` on VDS immediately after a secret-backed deploy) and compare it against the required six values.

Evidence log
- Commands run: `read DEPLOY_COORDINATION.md`; `read .github/workflows/ci.yml`; `read DEPLOY.md`
- Files changed: `DEPLOY_COORDINATION.md`
- Expected SHA / version: n/a for this check
- Observed API output: none — this check is blocked before runtime verification
- Observed uptime_seconds: none
- Pass/fail: blocked
- Notes: `.github/workflows/ci.yml` still contains a `deploy-staging` job that writes `printf '%s' "$STAGING_ENV_FILE" > "$STAGING_PATH/.env.staging"`, which means secret correctness remains a live deploy dependency even though repo policy says staging deploys are manual-only.

## A2 — Prove push != deploy, then prove the real deploy path `[DEPLOY.md: C12]`
- Status: open
- Owner: unassigned
- Goal: prove the actual delivery path from localhost to `staging.klaroha.com` and remove ambiguity for future AI operators.
- Hypothesis: a push alone does not update staging; the successful path is `commit -> push -> CI image build/publish -> manual deploy-staging.sh -> post-deploy verification`.
- Why it matters: this is the primary source of false assumptions about what is running.
- Files likely involved:
  - `DEPLOY.md`
  - `CLAUDE.md`
  - `.github/workflows/ci.yml`
  - `deploy-staging.sh`
  - `check-staging.sh`
- Validation steps:
  1. Make one tiny non-breaking change intended only for version verification.
  2. Commit and push to `staging`.
  3. Confirm whether staging freshness changes before manual deploy.
  4. Run manual staging deploy.
  5. Verify the change appears only after manual deploy.
- Expected result: push alone does not update public staging; manual deploy does.
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

## A2.5 — Design decision: staging gate before re-enabling automated deploy `[DEPLOY.md: C12]`
- Status: open
- Owner: human decision required
- Goal: define the promotion criteria that gates automated staging deploys, so we don't repeat the 2026-06-01 "unfinished features going live" problem.
- Why it matters: C12 (push != deploy) is a structural problem. The fix is automated deploy with a real gate — not permanent manual-only. Without agreeing on the gate first, any CI re-enable risks the same breakage.
- Options to evaluate:
  1. **Protected branch + required PR status checks** — feature branch tests pass → merge to `staging` → deploy fires automatically
  2. **Manual approval step in CI** — `build-and-push` completes → human clicks "Approve Deploy" in GitHub Actions
  3. **Staging-ready label gate** — PRs labeled `staging-ready` trigger deploy on merge
  4. **Time-delayed deploy** — staging deploys automatically 30 min after push, giving author time to cancel
- Decision needed from: human (operator/owner)
- Files likely involved: `.github/workflows/ci.yml`, `DEPLOY.md`, `CLAUDE.md`
- Actual result:
- Conclusion:
- Next action:

Evidence log
- Commands run:
- Files changed:
- Notes:

## A3 — C13 fix: deploy version fingerprint (`git_sha`) `[DEPLOY.md: C13, C16, C17]`
- Status: open
- Owner: unassigned
- Goal: expose the exact deployed git SHA from the running API.
- Hypothesis: adding `GIT_SHA` at image build time and surfacing it in `GET /api/` will close the current verification gap.
- Why it matters: without a version fingerprint, health checks can be green while old code is still running.
- Files likely involved:
  - `api/config.py`
  - `api/routers/health.py`
  - `api/main.py`
  - `api/Dockerfile`
  - `.github/workflows/ci.yml`
  - `check-staging.sh`
  - `DEPLOY.md`
- Validation steps:
  1. Add `ARG GIT_SHA` and bake it into the API image env/config.
  2. Expose `git_sha` in the health response.
  3. Pass `${{ github.sha }}` during CI build.
  4. Update `check-staging.sh` to print and verify it.
  5. Deploy and confirm the reported SHA matches the pushed commit.
- Expected result: `GET /api/` returns a meaningful `git_sha`, and staging verification checks it.
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

## A4 — C17 fix: uptime visibility in deploy tooling `[DEPLOY.md: C17]`
- Status: open
- Owner: unassigned
- Goal: make freshness visible immediately after deploy and during checks.
- Hypothesis: printing `uptime_seconds` in `deploy-staging.sh` and prominently in `check-staging.sh` will reduce false “deploy succeeded” assumptions.
- Why it matters: right now `uptime_seconds` is the only freshness signal, but it is not surfaced clearly enough.
- Files likely involved:
  - `deploy-staging.sh`
  - `check-staging.sh`
  - `DEPLOY.md`
- Validation steps:
  1. Update `check-staging.sh` output formatting to highlight uptime.
  2. Update `deploy-staging.sh` to print post-deploy uptime as a final confirmation line.
  3. Deploy and capture the final output.
- Expected result: both scripts show uptime clearly enough that an operator can verify restart freshness immediately.
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

## A5 — Agent protocol cleanup: push does not equal staging updated
- Status: open
- Owner: unassigned
- Goal: make the AI/operator protocol explicit so future sessions do not misreport staging status.
- Hypothesis: documenting the rule in agent instructions and deploy docs will stop repeat confusion.
- Why it matters: this is a repeated coordination failure, not just a code issue.
- Files likely involved:
  - `CLAUDE.md`
  - `DEPLOY.md`
  - `BACKLOG.md` (if task tracking needs updates)
- Validation steps:
  1. Add explicit protocol language.
  2. Ensure it says staging must be verified with `git_sha` and `uptime_seconds`.
  3. Confirm no remaining nearby text implies push auto-deploys staging.
- Expected result: repo docs consistently state that push alone does not update staging.
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

---

# Track C — Elimination Hypotheses

> A hypothesis belongs here only if: when the implementation is shipped, it **eliminates an entire class of debug problems permanently**.
>
> Format: "If we implement X → problem class Y stops occurring → validate by observing Y stops after X ships."
>
> Confirmation experiments (confirming what we already suspect without eliminating anything) do not belong here. They belong in the Deferred section below or in DEPLOY.md candidate causes.

---

## E1 — `git_sha` in health endpoint eliminates stale-code and false-confidence debug classes
- Status: open
- Owner: `[claude-code]` → implement; `[agent]` → validate post-ship
- Implementation: bake `GIT_SHA` build arg into `api/Dockerfile`; pass `${{ github.sha }}` in CI `build-and-push`; expose `git_sha` in `GET /api/`; add as check in `check-staging.sh`
- Problem classes eliminated:
  - **C13** — no way to verify which commit is running remotely
  - **C16** — `check-staging.sh` confirms availability, not code version
  - **C17** — `uptime_seconds` is the only freshness signal and nothing surfaces it
  - **Agent false-confidence** — agents report staging works without verifying code version
  - **C14 (uvicorn silent reload)** — becomes immediately detectable: `git_sha` mismatch tells you exactly which code is running
- Validation test (post-ship): push a commit → deploy → `curl -s https://staging.klaroha.com/api/ | jq '{git_sha, uptime_seconds}'` returns the pushed SHA with uptime < 120s. An agent can verify without SSH.
- Files: `api/Dockerfile`, `.github/workflows/ci.yml`, `api/config.py`, `api/routers/health.py`, `check-staging.sh`
- Ref: DEPLOY_TODO P1-1, P1-2, P1-3, P1-4 — DEPLOY.md C13, C16, C17

---

## E2 — Agent protocol in CLAUDE.md eliminates recurring false-confidence reports
- Status: open
- Owner: `[claude-code]`
- Implementation: add "Agent Deploy Protocol" section to `CLAUDE.md` — push ≠ staging updated; web/ changes require `docker compose build web`; verification requires `git_sha` + `uptime_seconds`; never report staging as reflecting a change without verifying both
- Problem classes eliminated:
  - **Agent false-confidence** (C12 agent-side) — agents stop claiming staging reflects a push they can't verify
  - **C15** — frontend rebuild gap stops recurring because protocol is explicit
  - All "staging works" false reports that have compounded debugging sessions
- Validation test (post-ship): in the next agent session after CLAUDE.md is updated, agent pushes a change → does NOT claim staging is updated → instructs operator to deploy and verify `git_sha`
- Files: `CLAUDE.md`
- Ref: DEPLOY_TODO P1-5 — DEPLOY.md C12, C15

---

## E3 — Auto-deploy with staging gate eliminates C12 as a structural cause
- Status: blocked on design decision `[A2.5]`
- Owner: `[human]` decision → `[claude-code]` implement → `[agent]` validate
- Implementation: re-enable `deploy-staging` CI job behind the agreed gate (protected branch + PR checks, or manual approval step — see A2.5)
- Problem classes eliminated:
  - **C12** — push no longer fails to reach staging; the structural gap closes
  - **Manual deploy drift** — staging always reflects the latest merged commit without operator SSH
- Validation test (post-ship): push a commit → CI completes → `staging.klaroha.com/api/` returns the pushed `git_sha` without any manual server action
- Files: `.github/workflows/ci.yml`, `CLAUDE.md`, `DEPLOY.md`
- Ref: DEPLOY_TODO P3-1 — DEPLOY.md C12, A2.5
- Blocked by: A2.5 staging gate design decision

---

## E4 — `STAGING_ENV_FILE` secret corrected eliminates port-drift and env-mismatch classes
- Status: blocked on operator action `[A1]`
- Owner: `[human]`
- Implementation: update the GitHub Actions secret `STAGING_ENV_FILE` to include all six staging-only values: `DB_PORT=5433`, `API_PORT=8001`, `WEB_PORT=5174`, `NGINX_PORT=8091`, `PUBLIC_PORT=3001`, `ENV_FILE=.env.staging`
- Problem classes eliminated:
  - **INC-004 / INC-006 replay** — next CI deploy will not overwrite `.env.staging` with broken values
  - **C11** — containers will read the correct env file
  - **Port-binding collisions** — staging containers will not attempt to bind production ports
- Validation test (post-ship): trigger a staging deploy → all six staging services start → `ss -lntp | grep -E "8001|8091"` shows ports listening → `check-staging.sh` passes 13/13 with no manual VDS repair
- Files: GitHub Actions secret (outside repo)
- Ref: DEPLOY_TODO P0-1 — DEPLOY.md C11, INC-004, INC-006
- Blocked by: operator must update GitHub Actions secret

---

## Validated — Closed

| Item | Conclusion | Date |
|---|---|---|
| C4 — smoke-local.sh does not see local uncommitted code | **validated** — script inspection + image probe confirm. Correct by design. No fix needed. | 2026-06-02 |
| C5a — manual deploy without `DEPLOY_SHA` uses mutable `:staging` tag | **validated** — script inspection confirms. Manual deploys are tag-race-vulnerable until E3 ships. | 2026-06-02 |

---

## Deferred — Confirmation Only

These were investigation experiments that confirm suspected causes but do not eliminate any class of problem on their own. They are superseded by E1–E4: once those ship, these become detectable or irrelevant.

| Item | Why deferred | Superseded by |
|---|---|---|
| C1 — uvicorn silent reload failure | Confirmed or not, the fix is the same: `git_sha` makes stale code immediately detectable | E1 |
| C2 — frontend rebuild gap | Already known to be true by design (override file + GHCR pull). Fix is documentation, not investigation. | E2 (CLAUDE.md protocol) |
| C5b — live GHCR tag race during CI build window | Moot once E3 ships (auto-deploy uses immutable SHA tags via `DEPLOY_SHA`). Low priority until then. | E3 |

---

# Track B — First Org Deploy Foundation

## B1 — Relay architecture decision
- Status: open
- Owner: unassigned
- Goal: confirm the canonical relay design for zero-setup OAuth.
- Hypothesis: a Klaroha-managed relay with signed one-time token handoff is the correct zero-setup path for Google + Meta integrations.
- Why it matters: first-org deploy cannot be “click to deploy” if each org must create its own cloud OAuth apps first.
- Files likely involved:
  - `PROJECT_BRIEF.md`
  - `BACKLOG.md`
  - `DEPLOY.md`
  - `api/provider_auth.py`
- Validation steps:
  1. Review the existing relay assumptions in docs and code.
  2. Confirm unresolved design choices.
  3. Produce a clear approved decision record before implementation.
- Expected result: one stable relay architecture decision ready for build work.
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

## B2 — First-boot init behavior
- Status: open
- Owner: unassigned
- Goal: turn `docker compose up` into a real first install instead of a manual ops exercise.
- Hypothesis: first-boot secret generation, migration, bootstrap, and onboarding redirect can remove most manual install steps.
- Why it matters: no per-org SSH and zero-touch deploy are explicit scale rules.
- Files likely involved:
  - `docker-compose.yml`
  - API startup / entrypoint files
  - `DEPLOY.md`
  - `.env.example`
- Validation steps:
  1. Confirm current startup behavior.
  2. Identify which init steps already exist and which are missing.
  3. Define the smallest safe automation sequence.
- Expected result: a concrete first-boot automation checklist and implementation order.
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

## B3 — Minimal `.env` target
- Status: open
- Owner: unassigned
- Goal: reduce required install-time env vars to the smallest deployable set.
- Hypothesis: `KLAROHA_DEPLOYMENT_KEY`, `KLAROHA_RELAY_URL`, and `FRONTEND_URL` should be enough for first deploy once relay + first-boot init are in place.
- Why it matters: a long env checklist is incompatible with fast org deployment at scale.
- Files likely involved:
  - `.env.example`
  - `PROJECT_BRIEF.md`
  - `BACKLOG.md`
  - `DEPLOY.md`
- Validation steps:
  1. Audit current `.env.example`.
  2. Separate required-now vars from vars that should be eliminated.
  3. Identify which optional vars remain truly optional.
- Expected result: a documented minimal-env target and reduction plan.
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

## B4 — Setup wizard path to first CMO message
- Status: open
- Owner: unassigned
- Goal: define and then implement the shortest path from first login to useful CMO operation.
- Hypothesis: the setup flow should be `org name -> brand brief import -> CMO open with brand context`, with BYOK as optional.
- Why it matters: the product promise is fast operational clarity, not admin setup burden.
- Files likely involved:
  - `PROJECT_BRIEF.md`
  - `BACKLOG.md`
  - frontend onboarding/admin files
- Validation steps:
  1. Confirm the target user path.
  2. Compare against current onboarding behavior.
  3. Identify missing steps and blockers.
- Expected result: one agreed setup path ready for implementation/testing.
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

## B5 — Distribution/install flow
- Status: open
- Owner: unassigned
- Goal: define the real install surface for first-org deploy.
- Hypothesis: a one-command installer plus later marketplace packaging is the right sequence.
- Why it matters: distribution is part of deploy design, not an afterthought.
- Files likely involved:
  - `DEPLOY.md`
  - `PROJECT_BRIEF.md`
  - `BACKLOG.md`
  - install/bootstrap scripts (future)
- Validation steps:
  1. Confirm the target install experience.
  2. Identify prerequisites for `curl install... | bash`.
  3. Sequence the install script work after relay + first-boot init.
- Expected result: a clear build order for install/distribution work.
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

---

# Missing Pieces — Not Yet in Any Track

These gaps are confirmed but have no owner and no track item yet. Add to DEPLOY_TODO.md and promote to a track when prioritized.

| # | Gap | Why it matters at scale | Scale severity |
|---|---|---|---|
| M1 | **No rollback procedure** | If a staging or prod deploy corrupts state, the runbook covers recovery only. Fast rollback to the previous image tag is not documented. At 10K orgs, a bad release needs an instant rollback path, not a multi-hour recovery. | Critical |
| M2 | **`check-staging.sh` capability count threshold hardcoded (≥ 20)** | As capabilities grow, this floor silently becomes a false minimum. A deploy that drops to 21 passes; 19 fails for the wrong reason. Needs a dynamic floor or a documented update process. | Medium |
| M3 | **No in-app admin diagnostic panel** | All current diagnosis requires CLI or curl. Non-technical org admins cannot self-diagnose. At 10K orgs, Klaroha cannot field support tickets for every version mismatch or config issue. Required before hitting 50 active customer orgs. | High |
| M4 | **OAuth relay (`connect.klaroha.com`) not built** | Every current org deploy requires manual Google Cloud and Meta app setup. Absolute blocker for 100/day deploy velocity. DEPLOY.md Build Order step 1. | Critical |
| M5 | **First-boot init script not built** | Every current deploy requires post-boot shell access for workspace bootstrap. Directly violates zero-touch new org deploys. DEPLOY.md Build Order step 2. | Critical |
| M6 | **Deployment key system not built** | Relay access gating and per-org usage metering don't exist. DEPLOY.md Build Order step 3. | High |
| M7 | **`STAGING_ENV_FILE` GitHub secret known stale** | Missing 5 port overrides + `ENV_FILE=.env.staging`. Next push-triggered deploy (if CI re-enabled) overwrites `.env.staging` and re-breaks staging (INC-006 replay). Operator action required before any CI change. | Immediate |
