#!/usr/bin/env bash
set -euo pipefail

cd ~/bos

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
          # Generate a random 32-byte hex key for fresh deploys
          generated=$(python3 -c "import secrets; print(secrets.token_hex(32))")
          sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${generated}|" .env.staging
          echo "  generated random ENCRYPTION_KEY"
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
