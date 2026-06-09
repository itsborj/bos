#!/usr/bin/env bash
set -euo pipefail

PASS=0
FAIL=0

ok()   { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

# ── Read staging config ───────────────────────────────────────────────────────
ENV_FILE=~/bos/.env.staging
API_KEY=$(grep -E '^API_SECRET_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
FRONTEND_URL=$(grep -E '^FRONTEND_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
BASE=http://127.0.0.1:8091
EXPECTED_GIT_SHA=${DEPLOY_SHA:-}

# ── 1. Config ─────────────────────────────────────────────────────────────────
echo "=== Config ==="
if [[ -z "$FRONTEND_URL" ]]; then
  fail "FRONTEND_URL missing from .env.staging"
elif [[ "$FRONTEND_URL" == *"localhost"* ]]; then
  fail "FRONTEND_URL is localhost ($FRONTEND_URL) — OAuth redirects will break"
else
  ok "FRONTEND_URL=$FRONTEND_URL"
fi

if [[ -z "$API_KEY" ]]; then
  fail "API_SECRET_KEY missing from .env.staging"
elif [[ "$API_KEY" == "change-me-before-deploying" ]]; then
  echo "  [WARN] API_SECRET_KEY is still the default — rotate before production"
  ok "API_SECRET_KEY is set (insecure default)"
else
  ok "API_SECRET_KEY is set"
fi

# ── 2. Ports listening ────────────────────────────────────────────────────────
echo "=== Ports ==="
for port in 8091 8001 5174 3001; do
  if ss -lntp 2>/dev/null | grep -q ":${port}"; then
    ok "port $port is listening"
  else
    fail "port $port is not listening"
  fi
done

# ── 3. Web serving ────────────────────────────────────────────────────────────
echo "=== Web ==="
WEB_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
if [[ "$WEB_CODE" == "200" ]]; then
  ok "homepage HTTP $WEB_CODE"
else
  fail "homepage returned HTTP $WEB_CODE (expected 200)"
fi

PUBLIC_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3001/)
if [[ "$PUBLIC_CODE" == "200" ]]; then
  ok "public service HTTP $PUBLIC_CODE"
else
  fail "public service returned HTTP $PUBLIC_CODE (expected 200)"
fi

# ── 4. API health ─────────────────────────────────────────────────────────────
echo "=== API health ==="
HEALTH=$(curl -s "$BASE/api/")
if echo "$HEALTH" | grep -q '"status":"ok"'; then
  HEALTH_SUMMARY=$(echo "$HEALTH" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("uptime={}s git_sha={}".format(d.get("uptime_seconds", "?"), d.get("git_sha", "missing")))' 2>/dev/null || echo "uptime=?s git_sha=missing")
  UPTIME=$(echo "$HEALTH" | python3 -c "import json,sys; print(json.load(sys.stdin).get('uptime_seconds','?'))" 2>/dev/null || echo "?")
  GIT_SHA=$(echo "$HEALTH" | python3 -c "import json,sys; print(json.load(sys.stdin).get('git_sha',''))" 2>/dev/null || echo "")
  ok "API status=ok (${HEALTH_SUMMARY})"
  if [[ -z "$GIT_SHA" ]]; then
    fail "git_sha missing from API health response"
  elif [[ -n "$EXPECTED_GIT_SHA" && "$GIT_SHA" != "$EXPECTED_GIT_SHA" ]]; then
    fail "git_sha mismatch — expected $EXPECTED_GIT_SHA, got $GIT_SHA"
  elif [[ -n "$EXPECTED_GIT_SHA" ]]; then
    ok "git_sha matches expected deploy SHA ($GIT_SHA)"
  else
    ok "git_sha present ($GIT_SHA)"
  fi
else
  fail "API health check failed — response: $(echo "$HEALTH" | head -c 120)"
fi

# ── 5. Auth layer ─────────────────────────────────────────────────────────────
echo "=== Auth ==="
AUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/brands")
if [[ "$AUTH_CODE" == "401" || "$AUTH_CODE" == "403" ]]; then
  ok "unauthenticated request blocked (HTTP $AUTH_CODE)"
else
  fail "auth layer not working — expected 401/403, got HTTP $AUTH_CODE"
fi

# ── 6. Database (authenticated query) ────────────────────────────────────────
echo "=== Database ==="
if [[ -n "$API_KEY" ]]; then
  DB_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" "$BASE/api/brands")
  if [[ "$DB_CODE" == "200" ]]; then
    ok "authenticated DB query HTTP $DB_CODE"
  else
    fail "authenticated DB query failed — HTTP $DB_CODE"
  fi
else
  fail "skipped — API_SECRET_KEY not available"
fi

# ── 7. Capability manifest ────────────────────────────────────────────────────
echo "=== Capabilities ==="
if [[ -n "$API_KEY" ]]; then
  CAP_RESPONSE=$(curl -s -H "X-API-Key: $API_KEY" "$BASE/api/agent/capabilities")
  CAP_COUNT=$(echo "$CAP_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "0")
  if [[ "$CAP_COUNT" -ge 20 ]]; then
    ok "$CAP_COUNT capabilities loaded"
  elif [[ "$CAP_COUNT" -gt 0 ]]; then
    fail "only $CAP_COUNT capabilities loaded — expected ≥20 (possible scan error)"
  else
    fail "capability manifest empty or failed to parse — response: $(echo "$CAP_RESPONSE" | head -c 120)"
  fi
else
  fail "skipped — API_SECRET_KEY not available"
fi

# ── 8. Migrations current ─────────────────────────────────────────────────────
echo "=== Migrations ==="
ALEMBIC_OUT=$(docker compose -f docker-compose.yml --env-file "$ENV_FILE" -p staging \
  exec -T api alembic current 2>/dev/null || true)
ALEMBIC_REV=$(echo "$ALEMBIC_OUT" | grep -v '^\s*INFO' | grep -v '^\s*$' | head -1 || true)
if echo "$ALEMBIC_OUT" | grep -q "(head)"; then
  ok "migrations at head ($ALEMBIC_REV)"
elif [[ -n "$ALEMBIC_REV" ]]; then
  fail "migrations not at head — current: $ALEMBIC_REV"
else
  fail "alembic reports no current revision — migrations may not have run"
fi

# ── Result ────────────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
  echo "Staging check FAILED."
  exit 1
fi
echo "Staging is healthy."
