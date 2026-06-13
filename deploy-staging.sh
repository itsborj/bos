#!/usr/bin/env bash
set -euo pipefail

cd "${BOS_DEPLOY_PATH:-$(pwd)}"
export ENV_FILE=.env.staging

echo "=== Deploy path ==="
echo "  pwd: $(pwd)"
echo "  head: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "  env:  $(realpath .env.staging 2>/dev/null || echo .env.staging)"

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
_set_env_value() {
  local key="$1" val="$2"
  if grep -qE "^${key}=" .env.staging 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" .env.staging
  else
    echo "${key}=${val}" >> .env.staging
  fi
}
_api_secret="$(_get_env_value API_SECRET_KEY)"
_relay_secret="$(_get_env_value KLAROHA_RELAY_KEY)"
_legacy_relay_secret="$(_get_env_value RELAY_KEY)"
_db_url="$(_get_env_value DATABASE_URL)"
_frontend_url="$(_get_env_value FRONTEND_URL)"
_meta_redirect="$(_get_env_value META_REDIRECT_URI)"
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
if [[ -z "$_db_url" ]]; then
  CRITICAL_MISSING+=("DATABASE_URL")
fi
if [[ -z "$_frontend_url" ]]; then
  CRITICAL_MISSING+=("FRONTEND_URL")
elif [[ "$_frontend_url" == *"localhost"* || "$_frontend_url" == *"127.0.0.1"* ]]; then
  echo "  corrected FRONTEND_URL: local → https://staging.klaroha.com"
  _set_env_value FRONTEND_URL "https://staging.klaroha.com"
  _frontend_url="https://staging.klaroha.com"
fi
if [[ -n "$_meta_redirect" && "$_meta_redirect" != "${_frontend_url%/}/social/facebook/callback" ]]; then
  if [[ "$_meta_redirect" == *"localhost"* || "$_meta_redirect" == *"127.0.0.1"* ]]; then
    echo "  corrected META_REDIRECT_URI: local → ${_frontend_url%/}/social/facebook/callback"
    _set_env_value META_REDIRECT_URI "${_frontend_url%/}/social/facebook/callback"
  else
    echo "  warning: META_REDIRECT_URI host differs from FRONTEND_URL; Facebook OAuth will derive from FRONTEND_URL at runtime"
  fi
fi
_set_env_value ENV_FILE ".env.staging"

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
echo "=== Waiting for API health ==="
_HEALTH=""
_STATUS=""
_GITSHA=""
_UPTIME=""
for i in $(seq 1 30); do
  _HEALTH=$(curl -s http://127.0.0.1:8091/api/ || true)
  parsed=$(printf '%s' "$_HEALTH" | python3 -c 'import json, sys; d=json.load(sys.stdin); print(d.get("status", ""), d.get("git_sha", ""), d.get("uptime_seconds", ""))' 2>/dev/null || true)
  if [[ -n "$parsed" ]]; then
    read -r _STATUS _GITSHA _UPTIME <<< "$parsed"
  else
    _STATUS=""
    _GITSHA=""
    _UPTIME=""
  fi

  if [[ "$_STATUS" == "ok" && "$_GITSHA" == "$SHA" ]]; then
    break
  fi

  echo "  API not ready or wrong version (attempt $i/30): status=${_STATUS:-missing} git_sha=${_GITSHA:-missing} uptime=${_UPTIME:-?}"
  sleep 2
done

_dump_staging_logs() {
  echo ""
  echo "=== docker compose ps ==="
  docker compose -f docker-compose.yml --env-file .env.staging -p staging ps || true
  echo ""
  echo "=== api logs tail ==="
  docker compose -f docker-compose.yml --env-file .env.staging -p staging logs --tail=160 api || true
  echo ""
  echo "=== nginx logs tail ==="
  docker compose -f docker-compose.yml --env-file .env.staging -p staging logs --tail=80 nginx || true
}

if [[ "$_STATUS" != "ok" || "$_GITSHA" != "$SHA" ]]; then
  echo ""
  echo "ERROR: staging API health check failed after deploy"
  echo "  expected git_sha: $SHA"
  echo "  actual status:    ${_STATUS:-missing}"
  echo "  actual git_sha:   ${_GITSHA:-missing}"
  echo "  uptime_seconds:   ${_UPTIME:-?}"
  echo "  raw health head:  $(echo "$_HEALTH" | head -c 200)"
  _dump_staging_logs
  exit 1
fi

# ── Specialist/plugin discovery check ─────────────────────────────────────────
echo "=== Checking specialist/plugin discovery ==="
_PLUGIN_STATUS=0
_PLUGIN_DIAG=$(docker compose -f docker-compose.yml --env-file .env.staging -p staging exec -T api python - <<'PY'
import json
import os
from pathlib import Path
from registry import _ensure
from plugin_loader import get_loaded_plugins, get_error_plugins

root = Path(os.environ.get("EXTERNAL_PLUGINS_DIR", "/external_plugins"))
try:
    _ensure()
    loaded = get_loaded_plugins()
    errors = get_error_plugins()
    payload = {
        "external_root": str(root),
        "external_root_exists": root.exists(),
        "external_children": sorted([p.name for p in root.iterdir() if p.is_dir()]) if root.exists() else [],
        "channel_json_count": len(list(root.glob("*/channel.json"))) if root.exists() else 0,
        "loaded_count": len(loaded),
        "loaded_ids": sorted(loaded.keys()),
        "error_count": len(errors),
        "errors": errors,
    }
    print(json.dumps(payload, sort_keys=True))
    raise SystemExit(0 if loaded else 2)
except SystemExit:
    raise
except Exception as exc:
    print(json.dumps({"error": str(exc), "external_root": str(root)}, sort_keys=True))
    raise SystemExit(2)
PY
) || _PLUGIN_STATUS=$?
_PLUGIN_STATUS=${_PLUGIN_STATUS:-0}
echo "$_PLUGIN_DIAG"
if [[ "$_PLUGIN_STATUS" != "0" ]]; then
  echo ""
  echo "ERROR: no specialists/plugins loaded after deploy"
  _dump_staging_logs
  exit 1
fi

echo ""
echo "================================================"
echo " Staging deploy complete"
echo " image:          ${API_IMAGE}"
echo " git_sha:        ${_GITSHA}"
echo " uptime_seconds: ${_UPTIME}s"
echo " plugins:        $(echo "$_PLUGIN_DIAG" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("loaded_count", "?"))' 2>/dev/null || echo '?')"
echo "================================================"
