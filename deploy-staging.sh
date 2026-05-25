#!/usr/bin/env bash
set -euo pipefail

cd ~/bos

# ── Env drift check ──────────────────────────────────────────────────────────
echo "=== Checking .env.staging for missing keys ==="
MISSING=()
while IFS= read -r line; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  key="${line%%=*}"
  [[ -z "$key" ]] && continue
  if ! grep -qE "^${key}=" .env.staging 2>/dev/null; then
    MISSING+=("$key")
  fi
done < .env.example

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo ""
  echo "ERROR: the following keys are in .env.example but missing from .env.staging:"
  for k in "${MISSING[@]}"; do echo "  $k"; done
  exit 1
else
  echo "OK — .env.staging has all keys from .env.example."
fi

echo "=== Pulling staging ==="
git fetch origin
git reset --hard origin/staging

echo "=== Building staging containers ==="
docker compose --env-file .env.staging -p staging up -d --build

echo "=== Running migrations ==="
docker compose --env-file .env.staging -p staging exec -T api alembic upgrade head

echo "=== Restarting staging nginx (re-resolves container IPs) ==="
docker compose --env-file .env.staging -p staging restart nginx

echo "=== Running smoke tests ==="
sleep 5
~/bos/check-staging.sh

echo ""
echo "Staging deploy complete."
