#!/usr/bin/env bash
set -uo pipefail

# BOS localhost → GitHub → staging → browser sync ledger.
# Read-only: this script does not mutate staging or print secret values.

STAGING_URL="${STAGING_URL:-https://staging.klaroha.com}"
STAGING_BRANCH="${STAGING_BRANCH:-staging}"
WORKFLOW_FILE="${WORKFLOW_FILE:-ci.yml}"
CURL_TIMEOUT="${CURL_TIMEOUT:-20}"
PLUGIN_MIN="${PLUGIN_MIN:-0}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"
SKIP_WEB_BUILD="${SKIP_WEB_BUILD:-0}"
STRICT_GHCR="${STRICT_GHCR:-0}"

PASS=0
FAIL=0
WARN=0

section() { echo ""; echo "=== $1 ==="; }
ok() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  [WARN] $1"; WARN=$((WARN + 1)); }
info() { echo "  $1"; }

sha_matches() {
  local a="${1:-}" b="${2:-}"
  [[ -n "$a" && -n "$b" && ( "$a" == "$b"* || "$b" == "$a"* ) ]]
}

curl_text() {
  curl -fsSL --max-time "$CURL_TIMEOUT" "$1"
}

curl_code() {
  local url="$1"
  shift || true
  curl -sS -L --max-time "$CURL_TIMEOUT" -o /dev/null -w "%{http_code}" "$@" "$url" 2>/dev/null || printf "000"
}

extract_entry_asset() {
  python3 - "$1" <<'PY'
import re, sys
path = sys.argv[1]
html = open(path, encoding="utf-8", errors="replace").read()
patterns = [
    r'<script[^>]*type=["\']module["\'][^>]*src=["\']([^"\']+\.js)["\']',
    r'<script[^>]*src=["\']([^"\']+\.js)["\'][^>]*type=["\']module["\']',
    r'<script[^>]*src=["\']([^"\']+\.js)["\']',
]
for pattern in patterns:
    match = re.search(pattern, html)
    if match:
        print(match.group(1))
        raise SystemExit(0)
raise SystemExit(1)
PY
}

json_field() {
  local field="$1"
  python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(sys.argv[1], ""))' "$field" 2>/dev/null
}

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR" || exit 1

LOCAL_HEAD=""
LOCAL_ENTRY=""
GITHUB_SHA=""
STAGING_SHA=""
STAGING_ENTRY=""

section "LOCAL"
BRANCH="$(git branch --show-current 2>/dev/null || true)"
LOCAL_HEAD="$(git rev-parse HEAD 2>/dev/null || true)"
SHORT_HEAD="$(git rev-parse --short HEAD 2>/dev/null || true)"
DIRTY="$(git status --porcelain 2>/dev/null || true)"

info "branch: ${BRANCH:-unknown}"
info "head: ${LOCAL_HEAD:-unknown}"
if [[ "$BRANCH" == "$STAGING_BRANCH" ]]; then
  ok "branch is $STAGING_BRANCH"
else
  fail "branch is ${BRANCH:-unknown}; expected $STAGING_BRANCH"
fi

if [[ -z "$LOCAL_HEAD" ]]; then
  fail "could not read local HEAD"
else
  ok "local HEAD detected ($SHORT_HEAD)"
fi

if [[ -z "$DIRTY" ]]; then
  ok "dirty: no"
elif [[ "$ALLOW_DIRTY" == "1" ]]; then
  warn "dirty: yes (allowed by ALLOW_DIRTY=1)"
else
  fail "dirty: yes — commit/stash local changes or set ALLOW_DIRTY=1"
  printf '%s\n' "$DIRTY" | sed 's/^/    /'
fi

if [[ "$SKIP_WEB_BUILD" == "1" ]]; then
  warn "web build skipped by SKIP_WEB_BUILD=1"
else
  if (cd web && npm run build >/tmp/bos-check-sync-web-build.log 2>&1); then
    ok "web build: ok"
  else
    fail "web build failed; see /tmp/bos-check-sync-web-build.log"
  fi
fi

if [[ -f web/dist/index.html ]]; then
  if LOCAL_ENTRY="$(extract_entry_asset web/dist/index.html 2>/dev/null)"; then
    ok "web entry bundle: $LOCAL_ENTRY"
  else
    fail "could not find local Vite entry bundle in web/dist/index.html"
  fi
else
  fail "web/dist/index.html missing; local build did not produce dist output"
fi

section "GITHUB"
if ! command -v gh >/dev/null 2>&1; then
  fail "gh CLI not installed; cannot inspect GitHub Actions"
else
  GH_JSON="$(gh run list --branch "$STAGING_BRANCH" --workflow "$WORKFLOW_FILE" --limit 1 --json databaseId,headSha,conclusion,status,event,createdAt,url,displayTitle 2>/tmp/bos-check-sync-gh.log || true)"
  if [[ -z "$GH_JSON" || "$GH_JSON" == "[]" ]]; then
    fail "could not read latest GitHub Actions run (try: gh auth status); see /tmp/bos-check-sync-gh.log"
  else
    GH_PARSED="$(GH_JSON="$GH_JSON" python3 - <<'PY' 2>/dev/null || true
import json, os
runs = json.loads(os.environ.get("GH_JSON", "[]"))
if not runs:
    raise SystemExit(1)
r = runs[0]
fields = [str(r.get(k, "")) for k in ("databaseId", "status", "conclusion", "headSha", "event", "createdAt", "url", "displayTitle")]
print("\t".join(fields))
PY
)"
    if [[ -z "$GH_PARSED" ]]; then
      fail "could not parse GitHub Actions run JSON"
    else
      IFS=$'\t' read -r GH_ID GH_STATUS GH_CONCLUSION GITHUB_SHA GH_EVENT GH_CREATED GH_URL GH_TITLE <<< "$GH_PARSED"
      info "latest staging run: ${GH_CONCLUSION:-unknown} (${GH_STATUS:-unknown})"
      info "run sha: ${GITHUB_SHA:-unknown}"
      info "run: ${GH_URL:-unknown}"
      if [[ "$GH_STATUS" == "completed" && "$GH_CONCLUSION" == "success" ]]; then
        ok "latest staging run succeeded"
      else
        fail "latest staging run is not successful: status=${GH_STATUS:-unknown} conclusion=${GH_CONCLUSION:-unknown}"
      fi
      if sha_matches "$LOCAL_HEAD" "$GITHUB_SHA"; then
        ok "GitHub run SHA matches local HEAD"
      else
        fail "GitHub run SHA does not match local HEAD (${GITHUB_SHA:-missing} vs ${LOCAL_HEAD:-missing})"
      fi
    fi
  fi
fi

if [[ -n "$GITHUB_SHA" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    warn "docker not installed; cannot inspect GHCR image manifests"
  else
    IMAGE_FAIL=0
    IMAGE_WARN=0
    for svc in api web relay; do
      image="ghcr.io/itsborj/bos-${svc}:sha-${GITHUB_SHA}"
      log="/tmp/bos-check-sync-${svc}-manifest.log"
      if docker manifest inspect "$image" >"$log" 2>&1; then
        ok "image published: $image"
      elif grep -qiE 'denied|unauthorized|authentication required' "$log" && [[ "$STRICT_GHCR" != "1" ]]; then
        warn "image manifest auth required: $image (set STRICT_GHCR=1 to fail closed)"
        IMAGE_WARN=1
      else
        fail "image missing or inaccessible: $image (docker login to GHCR may be required)"
        IMAGE_FAIL=1
      fi
    done
    [[ "$IMAGE_FAIL" == "0" && "$IMAGE_WARN" == "0" ]] && info "images published: api/web/relay"
    [[ "$IMAGE_FAIL" == "0" && "$IMAGE_WARN" != "0" ]] && info "images published: not verified locally due GHCR auth"
  fi
else
  fail "skipped image manifest checks because GitHub run SHA is missing"
fi

section "STAGING"
info "url: $STAGING_URL"
HEALTH="$(curl_text "$STAGING_URL/api/" 2>/tmp/bos-check-sync-health.log || true)"
if [[ -z "$HEALTH" ]]; then
  fail "staging API health request failed; see /tmp/bos-check-sync-health.log"
else
  STATUS="$(printf '%s' "$HEALTH" | json_field status || true)"
  STAGING_SHA="$(printf '%s' "$HEALTH" | json_field git_sha || true)"
  UPTIME="$(printf '%s' "$HEALTH" | json_field uptime_seconds || true)"
  if [[ "$STATUS" == "ok" ]]; then
    ok "api status: ok"
  else
    fail "api status is ${STATUS:-missing}; raw head: $(printf '%s' "$HEALTH" | head -c 120)"
  fi
  info "api git_sha: ${STAGING_SHA:-missing}"
  info "api uptime: ${UPTIME:-?}s"
  if sha_matches "$LOCAL_HEAD" "$STAGING_SHA"; then
    ok "staging API git_sha matches local HEAD"
  else
    fail "staging API git_sha does not match local HEAD (${STAGING_SHA:-missing} vs ${LOCAL_HEAD:-missing})"
  fi
  if [[ -n "$GITHUB_SHA" ]]; then
    if sha_matches "$GITHUB_SHA" "$STAGING_SHA"; then
      ok "staging API git_sha matches GitHub run SHA"
    else
      fail "staging API git_sha does not match GitHub run SHA (${STAGING_SHA:-missing} vs ${GITHUB_SHA:-missing})"
    fi
  fi
fi

INDEX_FILE="/tmp/bos-check-sync-staging-index.html"
if curl_text "$STAGING_URL/" > "$INDEX_FILE" 2>/tmp/bos-check-sync-index.log; then
  ok "staging index.html fetched"
  if STAGING_ENTRY="$(extract_entry_asset "$INDEX_FILE" 2>/dev/null)"; then
    ok "web index asset: $STAGING_ENTRY"
    if [[ -n "$LOCAL_ENTRY" ]]; then
      if [[ "$STAGING_ENTRY" == "$LOCAL_ENTRY" ]]; then
        ok "staging web entry matches local build"
      else
        fail "staging web entry differs from local build (${STAGING_ENTRY} vs ${LOCAL_ENTRY})"
      fi
    fi
    JS_CODE="$(curl_code "$STAGING_URL$STAGING_ENTRY")"
    if [[ "$JS_CODE" == "200" ]]; then
      ok "js asset status: 200"
    else
      fail "js asset status: HTTP $JS_CODE for $STAGING_ENTRY"
    fi
  else
    fail "could not find JS entry asset in staging index.html"
  fi
else
  fail "could not fetch staging index.html; see /tmp/bos-check-sync-index.log"
fi

AUTH_CODE="$(curl_code "$STAGING_URL/api/brands" -H "X-API-Key: bos-check-sync-fake-key")"
if [[ "$AUTH_CODE" == "401" || "$AUTH_CODE" == "403" ]]; then
  ok "fake API key rejected: yes (HTTP $AUTH_CODE)"
else
  fail "fake API key rejected: no — expected 401/403, got HTTP $AUTH_CODE"
fi

PLUGIN_KEY="${STAGING_API_KEY:-${API_SECRET_KEY:-}}"
PLUGIN_BODY="/tmp/bos-check-sync-plugins.json"
if [[ -n "$PLUGIN_KEY" ]]; then
  PLUGIN_CODE="$(curl -sS -L --max-time "$CURL_TIMEOUT" -o "$PLUGIN_BODY" -w "%{http_code}" -H "X-API-Key: $PLUGIN_KEY" "$STAGING_URL/api/plugins" 2>/dev/null || printf "000")"
else
  PLUGIN_CODE="$(curl -sS -L --max-time "$CURL_TIMEOUT" -o "$PLUGIN_BODY" -w "%{http_code}" "$STAGING_URL/api/plugins" 2>/dev/null || printf "000")"
fi

if [[ "$PLUGIN_CODE" == "200" ]]; then
  PLUGIN_COUNT="$(python3 - "$PLUGIN_BODY" <<'PY' 2>/dev/null || echo "parse_error"
import json, sys
with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
    data = json.load(f)
if isinstance(data, list):
    print(len(data))
elif isinstance(data, dict):
    for key in ("plugins", "items", "results", "data"):
        if isinstance(data.get(key), list):
            print(len(data[key]))
            break
    else:
        print(1 if data else 0)
else:
    print(0)
PY
)"
  info "plugins: $PLUGIN_COUNT"
  if [[ "$PLUGIN_COUNT" =~ ^[0-9]+$ ]]; then
    if (( PLUGIN_COUNT >= PLUGIN_MIN )); then
      ok "plugin count >= expected minimum ($PLUGIN_MIN)"
    else
      fail "plugin count $PLUGIN_COUNT is below expected minimum $PLUGIN_MIN"
    fi
  else
    fail "could not parse plugin count"
  fi
elif [[ -z "$PLUGIN_KEY" && ( "$PLUGIN_CODE" == "401" || "$PLUGIN_CODE" == "403" ) ]]; then
  warn "plugins: protected endpoint (set STAGING_API_KEY to include plugin count without printing the key)"
else
  fail "plugin check failed: HTTP $PLUGIN_CODE"
fi

section "BROWSER"
if [[ ! -d node_modules/playwright && ! -d web/node_modules/playwright ]]; then
  warn "Playwright package not installed; run npm install or set up browser check dependencies"
else
  BROWSER_OUT="$(node - "$STAGING_URL" <<'NODE' 2>&1
const url = process.argv[2];
let chromium;
try {
  chromium = require('playwright').chromium;
} catch (err) {
  try { chromium = require('./web/node_modules/playwright').chromium; }
  catch (inner) { console.error(`cannot load playwright: ${inner.message}`); process.exit(2); }
}
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const failures = [];
  const pageErrors = [];
  page.on('requestfailed', request => {
    const type = request.resourceType();
    const failedUrl = request.url();
    if (['document', 'script', 'stylesheet', 'xhr', 'fetch'].includes(type) || failedUrl.includes('/assets/')) {
      failures.push(`${type} ${failedUrl} ${request.failure()?.errorText || ''}`.trim());
    }
  });
  page.on('response', response => {
    const responseUrl = response.url();
    if (responseUrl.includes('/assets/') && response.status() >= 400) {
      failures.push(`HTTP ${response.status()} ${responseUrl}`);
    }
  });
  page.on('pageerror', error => pageErrors.push(error.message));
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1000);
    const rootChars = await page.locator('#root').evaluate(el => (el.textContent || el.innerHTML || '').trim().length).catch(() => 0);
    const title = await page.title().catch(() => '');
    await browser.close();
    if (failures.length || pageErrors.length || rootChars === 0) {
      console.log(JSON.stringify({ ok: false, title, rootChars, failures, pageErrors }, null, 2));
      process.exit(1);
    }
    console.log(JSON.stringify({ ok: true, title, rootChars, failures: 0, pageErrors: 0 }));
  } catch (err) {
    await browser.close().catch(() => {});
    console.log(JSON.stringify({ ok: false, error: err.message, failures, pageErrors }, null, 2));
    process.exit(1);
  }
})();
NODE
)"
  BROWSER_STATUS=$?
  if [[ "$BROWSER_STATUS" == "0" ]]; then
    ok "js asset browser load: ok"
    info "$BROWSER_OUT"
  else
    fail "js asset browser load failed"
    printf '%s\n' "$BROWSER_OUT" | sed 's/^/    /'
  fi
fi

echo ""
echo "Results: $PASS passed, $FAIL failed, $WARN warnings"
if [[ "$FAIL" -gt 0 ]]; then
  echo "Sync check FAILED. Do not call staging synced until failures are resolved."
  exit 1
fi

echo "Sync check PASSED. Local, GitHub, staging API, web asset, and browser checks are aligned."
if [[ "$WARN" -gt 0 ]]; then
  echo "Warnings remain; see above."
fi
