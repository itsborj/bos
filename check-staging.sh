#!/usr/bin/env bash
set -euo pipefail

echo "=== Checking Docker ports ==="
ss -lntp | grep -E ':80|:8080|:5174|:8001' || true

echo "=== Checking Nginx config ==="
nginx -t

echo "=== Verifying staging proxy target is 8080 ==="
nginx -T 2>/dev/null | grep -A20 -B5 "server_name staging.klaroha.com" | grep "127.0.0.1:8080" \
  || { echo "ERROR: staging nginx proxy is not pointing to 127.0.0.1:8080 — check /etc/nginx/nginx.conf"; exit 1; }

echo "=== Checking staging homepage ==="
curl -fsS -H "Host: staging.klaroha.com" http://127.0.0.1/ > /dev/null

echo "=== Checking staging API ==="
curl -fsS -H "Host: staging.klaroha.com" http://127.0.0.1/api/ | grep '"status":"ok"' \
  || { echo "ERROR: staging API health check failed"; exit 1; }

echo ""
echo "Staging is healthy."
