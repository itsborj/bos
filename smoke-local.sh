#!/usr/bin/env bash
# Pulls the GHCR :staging image and runs it locally on port 8092 — no volume
# mounts, no override file. Use this before pushing to verify local code that
# was committed and built by CI will actually work on staging.
#
# Usage:
#   bash smoke-local.sh              # use .env.staging
#   bash smoke-local.sh .env.mytest  # use a custom env file
#
# Requirements:
#   - .env.staging present (or pass a custom env file as $1)
#   - GHCR_TOKEN env var set, or already logged in to ghcr.io
#   - Port 8092 free

set -euo pipefail

ENV_FILE="${1:-.env.staging}"
SMOKE_PORT=8092
PROJECT=bos-smoke

# Override all host ports so the smoke stack doesn't clash with the running dev stack
export NGINX_PORT=$SMOKE_PORT
export PUBLIC_PORT=$((SMOKE_PORT + 1))
export DB_PORT=$((SMOKE_PORT + 2))
export API_PORT=$((SMOKE_PORT + 3))
export WEB_PORT=$((SMOKE_PORT + 4))

COMPOSE_CMD="docker compose -f docker-compose.yml --env-file $ENV_FILE -p $PROJECT"

cleanup() {
  echo ""
  echo "=== Tearing down smoke stack ==="
  $COMPOSE_CMD down --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

# ── Auth ──────────────────────────────────────────────────────────────────────
if [[ -n "${GHCR_TOKEN:-}" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u itsborj --password-stdin
fi

# ── Env file check ────────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE"
  echo "       Create it from .env.example or copy from the VDS .env.staging"
  exit 1
fi

FRONTEND_URL=$(grep -E '^FRONTEND_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || true)
if [[ "$FRONTEND_URL" == *"localhost"* ]]; then
  echo "WARN: FRONTEND_URL is set to localhost in $ENV_FILE — OAuth redirects will point at localhost, not staging domain. That's expected for a local smoke run."
fi

# ── Pull images ───────────────────────────────────────────────────────────────
echo "=== Pulling GHCR :staging images ==="
$COMPOSE_CMD pull api web relay

# ── Start stack ───────────────────────────────────────────────────────────────
echo "=== Starting smoke stack on port $SMOKE_PORT ==="
$COMPOSE_CMD up -d --no-build --force-recreate

echo "=== Waiting for API ==="
for i in $(seq 1 20); do
  if curl -sf "http://127.0.0.1:$SMOKE_PORT/api/" | grep -q '"status":"ok"'; then
    break
  fi
  if [[ $i -eq 20 ]]; then
    echo "ERROR: API did not become healthy within 20s"
    $COMPOSE_CMD logs api | tail -30
    exit 1
  fi
  sleep 1
done

# ── Checks ───────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
ok()   { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

API_KEY=$(grep -E '^API_SECRET_KEY=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || true)
BASE="http://127.0.0.1:$SMOKE_PORT"

echo "=== API health ==="
HEALTH=$(curl -s "$BASE/api/")
UPTIME=$(echo "$HEALTH" | python3 -c "import json,sys; print(json.load(sys.stdin).get('uptime_seconds','?'))" 2>/dev/null || echo "?")
if echo "$HEALTH" | grep -q '"status":"ok"'; then
  ok "API status=ok, uptime=${UPTIME}s"
else
  fail "API health check failed: $(echo "$HEALTH" | head -c 120)"
fi

echo "=== Web ==="
WEB_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
if [[ "$WEB_CODE" == "200" ]]; then ok "homepage HTTP $WEB_CODE"; else fail "homepage HTTP $WEB_CODE"; fi

echo "=== Auth boundary ==="
AUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/brands")
if [[ "$AUTH_CODE" == "401" || "$AUTH_CODE" == "403" ]]; then
  ok "unauthenticated blocked (HTTP $AUTH_CODE)"
else
  fail "auth boundary missing — expected 401/403, got $AUTH_CODE"
fi

echo "=== Database + capabilities ==="
if [[ -n "$API_KEY" ]]; then
  DB_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" "$BASE/api/brands")
  if [[ "$DB_CODE" == "200" ]]; then ok "DB query HTTP $DB_CODE"; else fail "DB query HTTP $DB_CODE"; fi

  CAP_COUNT=$(curl -s -H "X-API-Key: $API_KEY" "$BASE/api/agent/capabilities" | \
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  if [[ "$CAP_COUNT" -ge 20 ]]; then
    ok "$CAP_COUNT capabilities loaded"
  else
    fail "only $CAP_COUNT capabilities (expected ≥20)"
  fi
else
  fail "API_SECRET_KEY not in $ENV_FILE — skipping auth checks"
fi

echo "=== Migrations ==="
ALEMBIC_OUT=$($COMPOSE_CMD exec -T api alembic current 2>/dev/null || true)
if echo "$ALEMBIC_OUT" | grep -q "(head)"; then
  ok "migrations at head"
else
  fail "migrations not at head — run: $COMPOSE_CMD exec -T api alembic upgrade head"
fi

# ── Result ────────────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
  echo "Smoke test FAILED — do not push until this is clean."
  exit 1
fi
echo "Smoke test PASSED — image matches staging behavior. Safe to push."
