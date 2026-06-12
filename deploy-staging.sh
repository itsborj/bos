#!/usr/bin/env bash
set -euo pipefail

cd ~/bos
export ENV_FILE=.env.staging

# ── Env drift check — auto-fill missing keys from .env.example defaults ──────
echo "=== Checking .env.staging for missing keys ==="
CRITICAL_MISSING=()
while IFS= read -r line; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  key="${line%%=*}"
  [[ -z "$key" ]] && continue
  if ! grep -qE "^${key}=" .env.staging 2>/dev/null; then
    default_val="${line#*=}"
    # Never deploy public/example secrets copied from .env.example. Optional
    # third-party API keys may remain blank, but BOS-owned secrets must be
    # generated or explicitly supplied by staging secrets.
    case "$key" in
      ENCRYPTION_KEY)
        generated=$(python3 -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
        echo "ENCRYPTION_KEY=${generated}" >> .env.staging
        echo "  generated Fernet-compatible ENCRYPTION_KEY"
        continue
        ;;
      API_SECRET_KEY|KLAROHA_RELAY_KEY|RELAY_KEY)
        if [[ -z "$default_val" || "$default_val" == *"change-me"* || "$default_val" == *"example"* ]]; then
          CRITICAL_MISSING+=("$key")
          echo "  missing required secret: ${key}"
          continue
        fi
        ;;
      DATABASE_URL)
        if [[ -z "$default_val" || "$default_val" == *"bos:bos"* ]]; then
          CRITICAL_MISSING+=("$key")
          echo "  missing required non-default DATABASE_URL"
          continue
        fi
        ;;
    esac

    echo "${key}=${default_val}" >> .env.staging
    echo "  auto-filled: ${key}"
    case "$key" in
      FRONTEND_URL)
        # Override localhost default with the actual staging domain
        if [[ "$default_val" == *"localhost"* ]]; then
          sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=https://staging.klaroha.com|" .env.staging
          echo "  overrode FRONTEND_URL to https://staging.klaroha.com"
        fi
        ;;
    esac
  fi
done < .env.example

# Fail closed if staging already contains public/default BOS-owned secrets.
_get_env_value() { grep -E "^$1=" .env.staging 2>/dev/null | tail -1 | cut -d= -f2-; }
_api_secret="$(_get_env_value API_SECRET_KEY)"
_relay_secret="$(_get_env_value KLAROHA_RELAY_KEY)"
_legacy_relay_secret="$(_get_env_value RELAY_KEY)"
_db_url="$(_get_env_value DATABASE_URL)"
for pair in \
  "API_SECRET_KEY:${_api_secret}" \
  "KLAROHA_RELAY_KEY:${_relay_secret}" \
  "RELAY_KEY:${_legacy_relay_secret}"; do
  key="${pair%%:*}"
  val="${pair#*:}"
  if [[ -z "$val" || "$val" == *"change-me"* || "$val" == *"example"* ]]; then
    CRITICAL_MISSING+=("$key")
  fi
done
if [[ -z "$_db_url" || "$_db_url" == *"bos:bos"* ]]; then
  CRITICAL_MISSING+=("DATABASE_URL")
fi

if [[ ${#CRITICAL_MISSING[@]} -gt 0 ]]; then
  echo ""
  echo "ERROR: critical keys missing with no default — set these in .env.staging:"
  for k in "${CRITICAL_MISSING[@]}"; do echo "  $k"; done
  exit 1
else
  echo "OK — .env.staging is complete."
fi

# ── Staging port overrides — must never match production defaults ─────────────
# These vars are not in .env.example (no auto-fill) and may be absent from the
# STAGING_ENV_FILE secret. Enforce them here so staging never conflicts with the
# production bos stack running on the same host.
declare -A STAGING_PORTS=(
  [DB_PORT]=5433
  [API_PORT]=8001
  [WEB_PORT]=5174
  [NGINX_PORT]=8091
  [PUBLIC_PORT]=3001
)
for key in "${!STAGING_PORTS[@]}"; do
  val="${STAGING_PORTS[$key]}"
  if grep -qE "^${key}=" .env.staging 2>/dev/null; then
    current=$(grep -E "^${key}=" .env.staging | cut -d= -f2)
    if [[ "$current" != "$val" ]]; then
      echo "  corrected ${key}: ${current} → ${val}"
      sed -i "s|^${key}=.*|${key}=${val}|" .env.staging
    fi
  else
    echo "  added ${key}=${val}"
    echo "${key}=${val}" >> .env.staging
  fi
  # Also export so docker compose picks them up even before file is re-read
  export "${key}=${val}"
done

echo "=== Pulling staging ==="
git fetch origin
git reset --hard origin/staging

# ── Point plugin loader at the repo-tracked plugins/ directory ────────────────
# ~/bos-plugins is a local-only directory on dev machines.
# On the staging/production server, plugins live in the repo at ./plugins/.
REPO_PLUGINS_PATH="$(pwd)/plugins"
if grep -qE "^EXTERNAL_PLUGINS_PATH=" .env.staging 2>/dev/null; then
  sed -i "s|^EXTERNAL_PLUGINS_PATH=.*|EXTERNAL_PLUGINS_PATH=${REPO_PLUGINS_PATH}|" .env.staging
else
  echo "EXTERNAL_PLUGINS_PATH=${REPO_PLUGINS_PATH}" >> .env.staging
fi
export EXTERNAL_PLUGINS_PATH="${REPO_PLUGINS_PATH}"
echo "  EXTERNAL_PLUGINS_PATH=${REPO_PLUGINS_PATH}"

# ── Resolve image tags ────────────────────────────────────────────────────────
# Always deploy an immutable SHA-tagged image, never the mutable :staging tag.
# CI sets DEPLOY_SHA to the tested commit SHA. Manual runs derive it from git HEAD
# (safe because git reset --hard origin/staging ran above).
SHA="${DEPLOY_SHA:-$(git rev-parse HEAD)}"
export API_IMAGE="ghcr.io/itsborj/bos-api:sha-${SHA}"
export WEB_IMAGE="ghcr.io/itsborj/bos-web:sha-${SHA}"
export RELAY_IMAGE="ghcr.io/itsborj/bos-relay:sha-${SHA}"

echo "=== Pulling images ==="
echo "  API:   $API_IMAGE"
echo "  Web:   $WEB_IMAGE"
echo "  Relay: $RELAY_IMAGE"

# Authenticate to GHCR if token provided (required for private packages).
if [[ -n "${GHCR_TOKEN:-}" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u itsborj --password-stdin
fi

# Wait for all 3 images to be present in GHCR before pulling.
# CI builds api → web → relay sequentially; checking only api causes a race.
echo "=== Waiting for all images to be available in GHCR ==="
for i in $(seq 1 30); do
  API_OK=$(docker manifest inspect "$API_IMAGE" 2>&1 | head -1)
  WEB_OK=$(docker manifest inspect "$WEB_IMAGE" 2>&1 | head -1)
  RELAY_OK=$(docker manifest inspect "$RELAY_IMAGE" 2>&1 | head -1)
  if [[ "$API_OK" == "{" && "$WEB_OK" == "{" && "$RELAY_OK" == "{" ]]; then
    echo "All images ready."
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "ERROR: images not available after 10 minutes. CI may have failed."
    echo "  api:   $([[ $API_OK == '{' ]] && echo ok || echo missing)"
    echo "  web:   $([[ $WEB_OK == '{' ]] && echo ok || echo missing)"
    echo "  relay: $([[ $RELAY_OK == '{' ]] && echo ok || echo missing)"
    exit 1
  fi
  echo "  not ready yet (attempt $i/30) — waiting 20s..."
  sleep 20
done

# Use -f explicitly so docker-compose.override.yml (local dev) is never loaded.
docker compose -f docker-compose.yml --env-file .env.staging -p staging pull api web relay

echo "=== Stopping any previously stuck containers ==="
# Stop+remove containers only — do NOT remove the network.
# Removing the network tears down the Docker bridge and the kernel's iptables
# rules aren't ready in time when up recreates it, causing host-port-binding
# containers (db, api, web, nginx) to fail while port-less ones (redis, relay)
# start fine.
docker compose -f docker-compose.yml -p staging stop 2>/dev/null || true
docker compose -f docker-compose.yml -p staging rm -f 2>/dev/null || true

echo "=== Starting staging containers ==="
docker compose -f docker-compose.yml --env-file .env.staging -p staging \
  up -d --no-build --force-recreate

# ── Post-deploy health summary ────────────────────────────────────────────────
_HEALTH=$(curl -s http://127.0.0.1:8091/api/ || true)
_UPTIME=$(echo "$_HEALTH" | python3 -c "import json,sys; print(json.load(sys.stdin).get('uptime_seconds','?'))" 2>/dev/null || echo "?")
_GITSHA=$(echo "$_HEALTH" | python3 -c "import json,sys; print(json.load(sys.stdin).get('git_sha','missing'))" 2>/dev/null || echo "missing")

echo ""
echo "================================================"
echo " Staging deploy complete"
echo " image:          ${API_IMAGE}"
echo " git_sha:        ${_GITSHA}"
echo " uptime_seconds: ${_UPTIME}s"
echo "================================================"
