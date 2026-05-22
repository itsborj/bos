#!/usr/bin/env bash
set -euo pipefail

cd ~/bos

echo "=== Pulling staging ==="
git fetch origin
git reset --hard origin/staging

echo "=== Building staging containers ==="
docker compose -f docker-compose.staging.yml -p staging up -d --build

echo "=== Reloading Nginx ==="
nginx -t
systemctl reload nginx

echo "=== Running smoke tests ==="
sleep 5
~/bos/check-staging.sh

echo ""
echo "Staging deploy complete."
