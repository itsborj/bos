#!/usr/bin/env bash
# gitcheck — bounded preflight/postflight system check for git + GitHub.
# Deterministic, finite checks with a clear PASS/WARN/FAIL result and exit
# code. Works in any git repo — not tied to any one project.
#
# Usage:
#   gitcheck preflight  [--allow-wide-diff] [--allow-secrets] [--allow-main]
#                        [--allow-ignored-source]
#                        [--wide-diff-threshold N] [--with-tests] [--no-fetch]
#   gitcheck postflight [--skip-ci] [--allow-ignored-source] [--skip-runtime]
#   gitcheck help

set -uo pipefail

# ---------- output ----------
if [ -t 1 ]; then
  GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else
  GREEN=""; YELLOW=""; RED=""; BOLD=""; RESET=""
fi

PASS=0; WARN=0; FAIL=0

ok()      { echo "${GREEN}✔${RESET} $*"; PASS=$((PASS+1)); }
warn()    { echo "${YELLOW}⚠${RESET} $*"; WARN=$((WARN+1)); }
fail()    { echo "${RED}✘${RESET} $*"; FAIL=$((FAIL+1)); }
info()    { echo "  ${BOLD}·${RESET} $*"; }
section() { echo; echo "${BOLD}$*${RESET}"; }

usage() {
  cat <<EOF
gitcheck — bounded pre/post push system check

Usage:
  gitcheck preflight   [--allow-wide-diff] [--allow-secrets] [--allow-main]
                        [--allow-ignored-source]
                        [--wide-diff-threshold N] [--with-tests] [--no-fetch]
  gitcheck postflight  [--skip-ci] [--allow-ignored-source] [--skip-runtime]
  gitcheck help

preflight  — run before staging/committing.
postflight — run right after a push.

Exits non-zero if any hard-fail check fails. WARN items never block —
they're printed for you to judge.

Optional repo suppressions:
  .gitcheckignore         shell-glob patterns for intentionally ignored source-like files
  .gitcheckignore.local   same, local-only
EOF
}

require_repo() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "${RED}Not inside a git repository.${RESET}" >&2
    exit 2
  }
}

current_branch() { git rev-parse --abbrev-ref HEAD; }

default_branch() {
  local b
  b=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@')
  if [ -z "$b" ]; then
    for cand in main master; do
      if git show-ref --verify --quiet "refs/remotes/origin/$cand"; then b="$cand"; break; fi
    done
  fi
  echo "$b"
}

# path portion of `git status --porcelain=v1`, rename-safe
changed_files() {
  git status --porcelain=v1 | cut -c4- | sed -E 's/.* -> //'
}

status_lines() {
  git status --porcelain=v1
}

count_lines() {
  grep -c . 2>/dev/null || true
}

has_push_workflows() {
  [ -d .github/workflows ] || return 1
  grep -lE '^[[:space:]]*push:' .github/workflows/*.y*ml >/dev/null 2>&1
}

list_push_workflows() {
  [ -d .github/workflows ] || return 0
  grep -lE '^[[:space:]]*push:' .github/workflows/*.y*ml 2>/dev/null || true
}

# Runtime parity: for each compose service backed by a local Dockerfile
# (i.e. one of ours, not a third-party base image like postgres/redis/nginx),
# compare the running container's image `git_sha` LABEL against HEAD.
# - bind-mounted service: image staleness doesn't matter, source is live — info only
# - unstamped image: can't verify — warn, tell the user how to enable it
# - label unknown to this repo: probably built from a different checkout — warn
# - label == HEAD: exact match — ok
# - label != HEAD but no path changes since: still correct — ok
# - label != HEAD and path changed since: genuinely stale — fail
runtime_parity_report() {
  local head_sha="$1"
  if ! command -v docker >/dev/null 2>&1; then
    info "docker not found — skipping runtime parity check."
    return
  fi
  if ! docker compose version >/dev/null 2>&1; then
    info "docker compose not found — skipping runtime parity check."
    return
  fi
  local services svc
  services=$(docker compose config --services 2>/dev/null || true)
  if [ -z "$services" ]; then
    info "No docker-compose services detected — skipping runtime parity check."
    return
  fi
  local any_checked=0
  for svc in $services; do
    [ -f "$svc/Dockerfile" ] || continue
    local cid image label_sha bind_mounted
    cid=$(docker compose ps -q "$svc" 2>/dev/null || true)
    if [ -z "$cid" ]; then
      warn "$svc: has a Dockerfile but no running container — cannot verify runtime parity."
      any_checked=1
      continue
    fi
    any_checked=1
    image=$(docker inspect --format '{{.Image}}' "$cid" 2>/dev/null || true)
    label_sha=$(docker image inspect --format '{{ index .Config.Labels "git_sha" }}' "$image" 2>/dev/null || true)
    bind_mounted=0
    if docker inspect --format '{{range .Mounts}}{{.Type}}{{"\n"}}{{end}}' "$cid" 2>/dev/null | grep -q '^bind$'; then
      bind_mounted=1
    fi
    if [ -z "$label_sha" ] || [ "$label_sha" = "dev" ] || [ "$label_sha" = "<no value>" ]; then
      if [ "$bind_mounted" -eq 1 ]; then
        info "$svc: image not stamped with GIT_SHA, but source is bind-mounted (live) — served code reflects the working tree, not the image."
      else
        warn "$svc: image not stamped with GIT_SHA — rebuild with GIT_SHA=\$(git rev-parse HEAD) docker compose build $svc to enable this check."
      fi
    elif [ "$bind_mounted" -eq 1 ]; then
      info "$svc: bind-mounted source (live) — image git_sha (${label_sha:0:12}) isn't authoritative, the working tree is."
    elif ! git cat-file -e "${label_sha}^{commit}" 2>/dev/null; then
      warn "$svc: image git_sha ($label_sha) is not a commit known to this repo — built from a different checkout or fork?"
    elif [ "$label_sha" = "$head_sha" ]; then
      ok "$svc: running image matches HEAD exactly (${label_sha:0:12})."
    elif git diff --quiet "$label_sha" "$head_sha" -- "$svc" 2>/dev/null; then
      ok "$svc: running image predates HEAD but no relevant changes in $svc/ since (${label_sha:0:12} -> ${head_sha:0:12})."
    else
      fail "$svc: running image (${label_sha:0:12}) is stale relative to $svc/ changes in HEAD (${head_sha:0:12}) — rebuild and restart."
    fi
  done
  [ "$any_checked" -eq 0 ] && info "No services with a local Dockerfile detected — skipping runtime parity check."
}

is_suppressed_path() {
  local path="$1" file pat
  for file in .gitcheckignore .gitcheckignore.local; do
    [ -f "$file" ] || continue
    while IFS= read -r pat || [ -n "$pat" ]; do
      case "$pat" in
        ''|'#'*) continue ;;
      esac
      case "$path" in
        $pat) return 0 ;;
      esac
    done < "$file"
  done
  return 1
}

is_junk_like_path() {
  local path="$1" base="${1##*/}"
  case "$path" in
    .env|.env.*|*.log|*.tmp|*.pyc|*.pyo|*.sqlite|*.sqlite3|*.db|*.swp|*.swo|*.tsbuildinfo) return 0 ;;
    node_modules/*|*/node_modules/*|node_modules.bak/*|*/node_modules.bak/*) return 0 ;;
    __pycache__/*|*/__pycache__/*|.pytest_cache/*|*/.pytest_cache/*|.mypy_cache/*|*/.mypy_cache/*|.ruff_cache/*|*/.ruff_cache/*|.hypothesis/*|*/.hypothesis/*|.cache/*|*/.cache/*) return 0 ;;
    .venv/*|*/.venv/*|venv/*|*/venv/*|env/*|*/env/*|dist/*|*/dist/*|build/*|*/build/*|coverage/*|*/coverage/*|htmlcov/*|*/htmlcov/*) return 0 ;;
    graphify-out/*|*/graphify-out/*|experiment_results/*|*/experiment_results/*) return 0 ;;
    *.egg-info/*|*/.git/*|.claude/worktrees/*|*/.claude/worktrees/*) return 0 ;;
    .claude/settings.local.json) return 0 ;;
  esac
  case "$base" in
    .DS_Store|Thumbs.db|CACHEDIR.TAG) return 0 ;;
  esac
  return 1
}

is_source_like_path() {
  local path="$1" base="${1##*/}"
  case "$base" in
    package.json|package-lock.json|pyproject.toml|requirements.txt|Pipfile|Pipfile.lock|poetry.lock|Dockerfile|Makefile|docker-compose.yml|docker-compose.override.yml|docker-compose.*.yml|.env.example)
      return 0 ;;
  esac
  case "$path" in
    *.py|*.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.json|*.yml|*.yaml|*.toml|*.ini|*.cfg|*.conf|*.sh|*.bash|*.zsh|*.ps1|*.md|*.txt|*.sql|*.html|*.css|*.scss|*.svg|*.j2)
      return 0 ;;
  esac
  return 1
}

interesting_ignored_paths() {
  git ls-files --others --ignored --exclude-standard 2>/dev/null | while IFS= read -r path; do
    [ -n "$path" ] || continue
    is_junk_like_path "$path" && continue
    is_source_like_path "$path" || continue
    is_suppressed_path "$path" && continue
    printf '%s\n' "$path"
  done | sort -u
}

human_bytes() {
  python3 - "$1" <<'PY'
import sys
n = int(sys.argv[1])
units = ['B', 'KB', 'MB', 'GB', 'TB']
i = 0
v = float(n)
while v >= 1024 and i < len(units) - 1:
    v /= 1024.0
    i += 1
print(f"{v:.1f}{units[i]}" if i else f"{int(v)}{units[i]}")
PY
}

ignored_suspects_report() {
  interesting_ignored_paths | while IFS= read -r path; do
    [ -f "$path" ] || continue
    size=$(wc -c < "$path" 2>/dev/null | tr -d ' ')
    printf '%s\t%s\n' "${size:-0}" "$path"
  done | sort -rn -k1,1
}

SECRET_PATTERNS=(
  'AKIA[0-9A-Z]{16}'
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  'xox[baprs]-[0-9A-Za-z-]{10,}'
  '(api[_-]?key|secret|token|password|passwd|pwd)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9/+_=-]{16,}'
)

GENERIC_COMMIT_RE='^(snapshot|wip|updates?|changes?|misc|temp|checkpoint)([[:space:][:punct:]]|$)'

# ---------- preflight ----------
usage_preflight() { usage; }

cmd_preflight() {
  local allow_wide=0 allow_secrets=0 allow_main=0 allow_ignored_source=0 wide_threshold=3 with_tests=0 no_fetch=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --allow-wide-diff) allow_wide=1 ;;
      --allow-secrets) allow_secrets=1 ;;
      --allow-main) allow_main=1 ;;
      --allow-ignored-source) allow_ignored_source=1 ;;
      --wide-diff-threshold) wide_threshold="${2:-3}"; shift ;;
      --with-tests) with_tests=1 ;;
      --no-fetch) no_fetch=1 ;;
      -h|--help) usage_preflight; exit 0 ;;
      *) echo "Unknown option: $1" >&2; usage_preflight; exit 2 ;;
    esac
    shift
  done

  require_repo
  local repo branch def_branch
  repo=$(basename "$(git rev-parse --show-toplevel)")
  branch=$(current_branch)
  def_branch=$(default_branch)

  echo "${BOLD}gitcheck preflight — ${repo} @ ${branch}${RESET}"

  section "Repo state"
  local status raw_status_count
  status=$(status_lines)
  raw_status_count=$(printf '%s\n' "$status" | count_lines)
  if [ -z "$status" ]; then
    ok "Working tree clean (tracked + untracked). Still checking ignored/source drift."
  else
    ok "Changes detected — running checks."
    info "$raw_status_count tracked/untracked status line(s) present."
  fi

  section "Branch"
  if [ -n "$def_branch" ] && [ "$branch" = "$def_branch" ] && [ "$allow_main" -eq 0 ]; then
    fail "On protected/default branch '$branch'. Commit on a feature/working branch instead, or pass --allow-main."
  else
    ok "On branch '$branch' (default: ${def_branch:-unknown})."
  fi

  section "Remote freshness"
  local upstream ahead behind
  upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
  if [ -z "$upstream" ]; then
    warn "No upstream tracking branch set — skipping freshness check."
  else
    if [ "$no_fetch" -eq 0 ]; then
      git fetch --quiet 2>/dev/null || warn "git fetch failed — freshness check may be stale."
    fi
    behind=$(git rev-list --count "HEAD..$upstream" 2>/dev/null || echo 0)
    ahead=$(git rev-list --count "$upstream..HEAD" 2>/dev/null || echo 0)
    info "ahead=$ahead behind=$behind relative to $upstream"
    if [ "$behind" -gt 0 ]; then
      fail "Local branch is $behind commit(s) behind $upstream. Pull/rebase before committing."
    else
      ok "Not behind $upstream."
    fi
  fi

  section "Diff scope"
  local files n_files top_dirs n_top
  files=$(changed_files)
  n_files=$(printf '%s\n' "$files" | count_lines)
  top_dirs=$(printf '%s\n' "$files" | awk -F/ '{ if (NF==1) print "."; else print $1 }' | grep -v '^$' | sort -u)
  n_top=$(printf '%s\n' "$top_dirs" | count_lines)
  if [ "$n_files" -eq 0 ]; then
    info "No tracked/untracked path changes in git status."
    ok "Diff scope check skipped cleanly."
  else
    info "$n_files file(s) changed across $n_top top-level path(s):"
    printf '%s\n' "$top_dirs" | sed 's/^/      - /'
    if [ "$n_top" -gt "$wide_threshold" ] && [ "$allow_wide" -eq 0 ]; then
      fail "Diff spans $n_top unrelated top-level paths (threshold: $wide_threshold). Split into separate commits, or pass --allow-wide-diff."
    elif [ "$n_top" -gt "$wide_threshold" ]; then
      warn "Diff spans $n_top top-level paths (threshold: $wide_threshold) — allowed via --allow-wide-diff."
    else
      ok "Diff scope within threshold ($n_top <= $wide_threshold)."
    fi
  fi

  section "Untracked junk"
  local junk
  junk=$(status_lines | awk '$1=="??"{print $2}' | grep -iE '\.(bak|log|tmp|swp)$|(^|/)(\.DS_Store|Thumbs\.db|__pycache__|node_modules\.bak)(/|$)' || true)
  if [ -n "$junk" ]; then
    fail "Untracked junk-looking files present — clean up or .gitignore before committing:"
    printf '%s\n' "$junk" | sed 's/^/      - /'
  else
    ok "No obvious junk files in untracked list."
  fi

  section "Ignored source drift"
  local ignored_report ignored_count ignored_bytes ignored_human
  ignored_report=$(ignored_suspects_report)
  ignored_count=$(printf '%s\n' "$ignored_report" | count_lines)
  ignored_bytes=$(printf '%s\n' "$ignored_report" | awk -F'\t' '{s+=$1} END {print s+0}')
  ignored_human=$(human_bytes "$ignored_bytes")
  if [ "$ignored_count" -gt 0 ] && [ "$allow_ignored_source" -eq 0 ]; then
    fail "Ignored source/config/doc files present — git can say 'clean' while real work exists outside version control ($ignored_count file(s), $ignored_human):"
    printf '%s\n' "$ignored_report" | head -20 | awk -F'\t' '{printf "      - %s (%s bytes)\n", $2, $1}'
    info "Commit them, delete them, or intentionally suppress them via .gitcheckignore / .gitcheckignore.local."
  elif [ "$ignored_count" -gt 0 ]; then
    warn "Ignored source/config/doc files present ($ignored_count file(s), $ignored_human) — allowed via --allow-ignored-source."
    printf '%s\n' "$ignored_report" | head -20 | awk -F'\t' '{printf "      - %s (%s bytes)\n", $2, $1}'
  else
    ok "No suspicious ignored source/config/doc files detected."
  fi

  section "Secret scan"
  local hits="" m diff_added
  diff_added=$(git diff HEAD -- . 2>/dev/null | grep -E '^\+[^+]' || true)
  for pat in "${SECRET_PATTERNS[@]}"; do
    m=$(printf '%s\n' "$diff_added" | grep -iE -- "$pat" || true)
    [ -n "$m" ] && hits="${hits}${m}"$'\n'
  done
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    [ -f "$f" ] || continue
    git check-ignore -q "$f" 2>/dev/null && continue
    if command -v file >/dev/null 2>&1 && ! file "$f" | grep -qi text; then continue; fi
    for pat in "${SECRET_PATTERNS[@]}"; do
      m=$(grep -iE -- "$pat" "$f" 2>/dev/null || true)
      [ -n "$m" ] && hits="${hits}${f}: ${m}"$'\n'
    done
  done < <(status_lines | awk '$1=="??"{print $2}')
  if [ -n "$(printf '%s' "$hits" | tr -d '[:space:]')" ] && [ "$allow_secrets" -eq 0 ]; then
    fail "Possible secret/credential pattern(s) found — review before committing (or pass --allow-secrets if false positive):"
    printf '%s\n' "$hits" | sed 's/^/      - /' | head -20
  else
    ok "No obvious secret patterns detected."
  fi

  section "Local check gate"
  local check_script=""
  for c in scripts/check.sh scripts/ci.sh Makefile; do
    [ -f "$c" ] && check_script="$c" && break
  done
  if [ -n "$check_script" ]; then
    if [ "$with_tests" -eq 1 ]; then
      if [ "$check_script" = "Makefile" ]; then
        info "Running make check ..."
        if make check; then
          ok "make check passed."
        else
          fail "make check failed — fix before committing."
        fi
      else
        info "Running $check_script ..."
        if bash "$check_script"; then
          ok "$check_script passed."
        else
          fail "$check_script failed — fix before committing."
        fi
      fi
    else
      warn "Found $check_script — not run (pass --with-tests to run it automatically)."
    fi
  else
    warn "No local check script found (scripts/check.sh, scripts/ci.sh, Makefile) — verify tests/lint manually."
  fi

  section "Judgment calls (not enforced — confirm yourself)"
  cat <<'EOF'
    [ ] Every hunk in the diff traces to something you can name
    [ ] Commit message will answer "why", not just "what" (no "snapshot"/"wip"/"updates")
    [ ] There are no meaningful ignored source/config/doc files hiding outside Git
    [ ] If this touches a locked architecture rule or plugin contract, the doc update lands in this same commit/session
EOF

  echo
  echo "${BOLD}Result: PASS=$PASS WARN=$WARN FAIL=$FAIL${RESET}"
  [ "$FAIL" -gt 0 ] && exit 1
  exit 0
}

# ---------- postflight ----------
usage_postflight() { usage; }

cmd_postflight() {
  local skip_ci=0 allow_ignored_source=0 skip_runtime=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --skip-ci) skip_ci=1 ;;
      --allow-ignored-source) allow_ignored_source=1 ;;
      --skip-runtime) skip_runtime=1 ;;
      -h|--help) usage_postflight; exit 0 ;;
      *) echo "Unknown option: $1" >&2; usage_postflight; exit 2 ;;
    esac
    shift
  done

  require_repo
  local repo branch
  repo=$(basename "$(git rev-parse --show-toplevel)")
  branch=$(current_branch)

  echo "${BOLD}gitcheck postflight — ${repo} @ ${branch}${RESET}"

  section "Push landed"
  local upstream local_sha remote_sha local_upstream_sha
  upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
  local_sha=$(git rev-parse HEAD)
  info "local HEAD: $local_sha"
  if [ -z "$upstream" ]; then
    fail "No upstream tracking branch — cannot verify push landed."
  else
    git fetch --quiet 2>/dev/null || warn "git fetch failed — using last known upstream ref."
    local_upstream_sha=$(git rev-parse "$upstream" 2>/dev/null || echo "")
    remote_sha=$(git ls-remote origin "refs/heads/$branch" 2>/dev/null | awk 'NR==1{print $1}')
    [ -n "$local_upstream_sha" ] && info "$upstream: $local_upstream_sha"
    [ -n "$remote_sha" ] && info "origin/$branch (ls-remote): $remote_sha"
    if [ -z "$local_upstream_sha" ]; then
      fail "Could not resolve upstream ref $upstream."
    elif [ "$local_sha" != "$local_upstream_sha" ]; then
      fail "Local HEAD (${local_sha:0:12}) does not match $upstream (${local_upstream_sha:0:12}). Push may not have landed, or remote moved."
    elif [ -n "$remote_sha" ] && [ "$local_sha" != "$remote_sha" ]; then
      fail "Local HEAD matches cached upstream but not origin/$branch on the server (${remote_sha:0:12}). Re-fetch / inspect remote."
    else
      ok "Local HEAD matches upstream remote state (${local_sha:0:12})."
    fi
  fi

  section "Working tree"
  if [ -z "$(status_lines)" ]; then
    ok "Working tree clean — no leftover tracked/untracked changes."
  else
    fail "Working tree not clean after push — uncommitted changes remain:"
    status_lines | sed 's/^/      /'
  fi

  section "Ignored source drift"
  local ignored_report ignored_count ignored_bytes ignored_human
  ignored_report=$(ignored_suspects_report)
  ignored_count=$(printf '%s\n' "$ignored_report" | count_lines)
  ignored_bytes=$(printf '%s\n' "$ignored_report" | awk -F'\t' '{s+=$1} END {print s+0}')
  ignored_human=$(human_bytes "$ignored_bytes")
  if [ "$ignored_count" -gt 0 ] && [ "$allow_ignored_source" -eq 0 ]; then
    fail "Push landed, but ignored source/config/doc files still exist locally — GitHub is not a full snapshot of your working state ($ignored_count file(s), $ignored_human):"
    printf '%s\n' "$ignored_report" | head -20 | awk -F'\t' '{printf "      - %s (%s bytes)\n", $2, $1}'
    info "Commit them, delete them, or intentionally suppress them via .gitcheckignore / .gitcheckignore.local."
  elif [ "$ignored_count" -gt 0 ]; then
    warn "Ignored source/config/doc files present ($ignored_count file(s), $ignored_human) — allowed via --allow-ignored-source."
    printf '%s\n' "$ignored_report" | head -20 | awk -F'\t' '{printf "      - %s (%s bytes)\n", $2, $1}'
  else
    ok "No suspicious ignored source/config/doc files detected."
  fi

  section "GitHub visibility"
  if [ "$skip_ci" -eq 1 ]; then
    warn "CI/GitHub visibility check skipped (--skip-ci)."
  elif ! command -v gh >/dev/null 2>&1; then
    warn "gh CLI not found — check GitHub Actions manually."
  elif ! gh auth status >/dev/null 2>&1; then
    warn "gh CLI not authenticated (gh auth login) — check GitHub Actions manually."
  else
    local run_json picked parsed rc exact_marker run_id status conclusion head_sha url title workflow created
    run_json=$(gh run list --branch "$branch" --limit 20 --json databaseId,status,conclusion,headSha,displayTitle,url,workflowName,createdAt 2>&1)
    rc=$?
    if [ "$rc" -ne 0 ]; then
      warn "gh run list failed (exit $rc) — auth may be stale or no Actions access. Check manually: $(printf '%s' "$run_json" | head -1)"
    elif [ -z "$run_json" ] || [ "$run_json" = "[]" ]; then
      if has_push_workflows; then
        fail "No GitHub Actions runs found for branch '$branch' even though push-trigger workflows exist."
      else
        warn "No CI runs found for branch '$branch'."
      fi
    else
      parsed=$(GH_JSON="$run_json" LOCAL_SHA="$local_sha" python3 - <<'PY' 2>/dev/null || true
import json, os
runs = json.loads(os.environ.get('GH_JSON', '[]'))
local_sha = os.environ.get('LOCAL_SHA', '')
if not runs:
    raise SystemExit(1)
exact = [r for r in runs if str(r.get('headSha', '')) == local_sha]
chosen = sorted(exact or runs, key=lambda r: r.get('createdAt', ''), reverse=True)[0]
marker = 'exact' if exact else 'latest'
fields = [marker, str(chosen.get('databaseId', '')), str(chosen.get('status', '')), str(chosen.get('conclusion', '')), str(chosen.get('headSha', '')), str(chosen.get('url', '')), str(chosen.get('displayTitle', '')), str(chosen.get('workflowName', '')), str(chosen.get('createdAt', ''))]
print('\t'.join(fields))
PY
)
      if [ -z "$parsed" ]; then
        warn "Could not parse GitHub Actions response."
      else
        IFS=$'\t' read -r exact_marker run_id status conclusion head_sha url title workflow created <<< "$parsed"
        info "run id: ${run_id:-unknown}"
        info "workflow: ${workflow:-unknown}"
        info "run commit: ${head_sha:-unknown}"
        info "status=${status:-unknown} conclusion=${conclusion:-unknown}"
        info "${url:-unknown}"
        if [ "$exact_marker" != "exact" ]; then
          if has_push_workflows; then
            fail "No GitHub Actions run found yet for exact HEAD SHA ${local_sha:0:12}. Latest visible run is for ${head_sha:0:12}."
          else
            warn "No GitHub Actions run found for exact HEAD SHA ${local_sha:0:12}."
          fi
        elif [ "$status" = "completed" ] && [ "$conclusion" = "success" ]; then
          ok "GitHub Actions green for exact HEAD SHA."
        elif [ "$status" != "completed" ]; then
          warn "GitHub Actions run exists for exact HEAD SHA but is still running. Re-run 'gitcheck postflight' shortly."
        else
          fail "GitHub Actions run for exact HEAD SHA is not successful (conclusion=$conclusion)."
        fi
      fi
    fi
  fi

  section "Runtime parity"
  if [ "$skip_runtime" -eq 1 ]; then
    warn "Runtime parity check skipped (--skip-runtime)."
  else
    runtime_parity_report "$local_sha"
  fi

  section "Commit message quality"
  local subject
  subject=$(git log -1 --pretty=%s 2>/dev/null || echo "")
  info "HEAD subject: ${subject:-missing}"
  if [ -z "$subject" ]; then
    warn "Could not read HEAD subject."
  elif printf '%s' "$subject" | grep -Eiq "$GENERIC_COMMIT_RE"; then
    warn "Generic commit subject detected — this makes GitHub history a weak source of truth. Prefer a specific why/what message over '${subject}'."
  else
    ok "HEAD subject is specific enough for a human audit trail."
  fi

  section "Deploy-trigger awareness (informational only)"
  if [ -d .github/workflows ]; then
    local hits
    hits=$(list_push_workflows)
    if [ -n "$hits" ]; then
      info "Workflow file(s) that appear to trigger on push:"
      printf '%s\n' "$hits" | sed 's/^/      - /'
      info "Confirm this push didn't fire anything beyond what you intended (e.g. a deploy)."
    fi
  fi

  section "Judgment calls (not enforced — confirm yourself)"
  cat <<'EOF'
    [ ] Tracking docs (backlog / decision records / locked-rules) updated in this same session, not deferred
    [ ] GitHub history alone is enough for another human to understand what shipped
    [ ] If this was a meaningful milestone, it's described specifically — not another generic "snapshot"
EOF

  echo
  echo "${BOLD}Result: PASS=$PASS WARN=$WARN FAIL=$FAIL${RESET}"
  [ "$FAIL" -gt 0 ] && exit 1
  exit 0
}

# ---------- main ----------
main() {
  local cmd="${1:-}"
  [ $# -gt 0 ] && shift
  case "$cmd" in
    preflight) cmd_preflight "$@" ;;
    postflight) cmd_postflight "$@" ;;
    help|-h|--help|"") usage ;;
    *) echo "Unknown command: $cmd" >&2; usage; exit 2 ;;
  esac
}

main "$@"
