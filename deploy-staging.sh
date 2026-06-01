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
    echo "${key}=${default_val}" >> .env.staging
    echo "  auto-filled: ${key}"
    # Only block deploy for keys that have no usable default and no generator
    case "$key" in
      DATABASE_URL|API_SECRET_KEY)
        if [[ -z "$default_val" ]]; then
          CRITICAL_MISSING+=("$key")
        fi
        ;;
      ENCRYPTION_KEY)
        if [[ -z "$default_val" ]]; then
          generated=$(python3 -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
          sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${generated}|" .env.staging
          echo "  generated Fernet-compatible ENCRYPTION_KEY"
        fi
        ;;
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

if [[ ${#CRITICAL_MISSING[@]} -gt 0 ]]; then
  echo ""
  echo "ERROR: critical keys missing with no default — set these in .env.staging:"
  for k in "${CRITICAL_MISSING[@]}"; do echo "  $k"; done
  exit 1
else
  echo "OK — .env.staging is complete."
fi

echo "=== Pulling staging ==="
git fetch origin
git reset --hard origin/staging

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
docker compose -f docker-compose.yml -p staging down --remove-orphans || true

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
