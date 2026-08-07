# GitHub Flight Check

Purpose: make GitHub a trustworthy, human-auditable snapshot of what actually exists locally.

## Success criteria

A pass means all of these are true:

- the intended work is on the intended branch
- local is not behind the tracked remote
- the change scope is understandable, not a random wide snapshot
- no junk files are about to leak into history
- no meaningful source/config/doc files are hiding in ignored paths
- no obvious secrets are being added
- after push, local HEAD, upstream, and remote branch agree
- GitHub Actions visibility is checked for the exact pushed SHA when `gh` access exists
- commit history is understandable to another human, not just `snapshot current working version`

## Why this exists

`git status` and `HEAD == origin/branch` are necessary but too weak.
They miss the class of failures where:

- important local files are ignored by Git
- push succeeds but GitHub visibility is unclear
- commit messages are too generic to serve as an audit trail
- GitHub is only a partial shadow of the real working version

## Usage

From repo root:

```bash
scripts/gitcheck.sh preflight
scripts/gitcheck.sh postflight
```

Useful options:

```bash
scripts/gitcheck.sh preflight --with-tests
scripts/gitcheck.sh preflight --allow-wide-diff
scripts/gitcheck.sh preflight --allow-main
scripts/gitcheck.sh preflight --allow-ignored-source
scripts/gitcheck.sh postflight --skip-ci
scripts/gitcheck.sh postflight --allow-ignored-source
scripts/gitcheck.sh postflight --skip-runtime
```

## What it checks beyond basic HEAD matching

### Preflight

- branch safety
- remote freshness
- diff breadth across top-level paths
- junk/untracked artifact detection
- ignored source drift detection
- secret-pattern scan
- optional local check script execution

### Postflight

- local HEAD vs upstream ref vs `git ls-remote`
- exact GitHub Actions run visibility for the pushed SHA when `gh` works
- leftover dirty working tree after push
- ignored source drift still present after push
- runtime parity: running docker-compose containers vs HEAD (see below)
- generic commit subject warning

## Ignored source drift

This is the key guardrail.

The checker fails if files that look like real source/config/docs exist only in ignored paths, for example:

- `package.json`
- `package-lock.json`
- `*.py`
- `*.md`
- `*.sh`
- config files like `.env.example`, `Dockerfile`, `*.yml`

That closes the false-positive gap where Git says everything is fine while meaningful local work is still outside version control.

## Runtime parity

VCS checks prove GitHub matches your git tree. They don't prove the thing
actually running on `localhost` was built from that tree — an image can sit
stale for days while `git status` stays clean.

Postflight closes part of that gap for docker-compose setups. For every
compose service backed by a local `<service>/Dockerfile`, it bakes a
`git_sha` image `LABEL` at build time (via a `GIT_SHA` build arg) and, at
postflight time, compares that label against `HEAD`:

- **bind-mounted service** (e.g. `api` in local dev, via `docker-compose.override.yml`) —
  the image label isn't authoritative since the container serves the live
  working tree; reported as info only, not scored.
- **unstamped image** — can't verify; rebuild with
  `GIT_SHA=$(git rev-parse HEAD) docker compose build <service>` to enable
  the check.
- **label == HEAD** — exact match, pass.
- **label != HEAD but the service's directory hasn't changed since** — still
  correct, pass.
- **label != HEAD and the service's directory did change** — genuinely
  stale, fail: rebuild and restart.

This only covers docker-compose-based runtime parity, and only for images
built from a `Dockerfile` in this repo. It says nothing about feature
behavior — see the operator rule below.

## Local suppressions

If a repo intentionally keeps certain ignored source-like files local-only, add patterns to:

- `.gitcheckignore`
- `.gitcheckignore.local`

Use this sparingly. Suppression means: “this hidden local file is intentional and should not block trust in GitHub.”

## Operator rule

Do not say “all good” unless the flight check passes.

And even when it passes:

- this proves **version-control integrity**
- for docker-compose services with a local Dockerfile, it also checks
  **image/runtime parity** against HEAD (see "Runtime parity" above) — but
  only for what's running locally under compose, not staging/production
- it does **not** prove feature behavior
