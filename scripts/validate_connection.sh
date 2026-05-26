#!/usr/bin/env bash
# Usage: BOS_KEY=bos_xxx BOS_URL=https://staging.klaroha.com bash validate_connection.sh
set -euo pipefail

BOS_KEY="${BOS_KEY:?BOS_KEY is required}"
BOS_URL="${BOS_URL:-https://staging.klaroha.com}"

pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; exit 1; }

echo "=== BOS Connection Validation ==="
echo "URL: $BOS_URL"
echo ""

# Check 1: API health
echo "1. Health check..."
HEALTH=$(curl -sf "$BOS_URL/" 2>/dev/null) || fail "API unreachable at $BOS_URL"
echo "$HEALTH" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('status') == 'ok', f'Bad status: {d}'
print('   status:', d['status'])
print('   version:', d.get('version', 'n/a'))
" || fail "Health response unexpected: $HEALTH"
pass "API reachable"
echo ""

# Check 2: Auth
echo "2. Auth check..."
STATE=$(curl -sf "$BOS_URL/agent/state" -H "X-API-Key: $BOS_KEY" 2>/dev/null) || fail "Request failed — is the stack up?"
echo "$STATE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if 'detail' in d:
    print('   ERROR:', d['detail'])
    sys.exit(1)
print('   workspace:', d.get('workspace_name', 'n/a'))
print('   brands:', len(d.get('brands', [])))
print('   pending:', d.get('total_pending', 0))
" || fail "Auth failed — check key value"
pass "Key authenticated"
echo ""

# Check 3: Capabilities
echo "3. Capabilities check..."
CAPS=$(curl -sf "$BOS_URL/agent/capabilities" -H "X-API-Key: $BOS_KEY" 2>/dev/null) || fail "Capabilities endpoint failed"
echo "$CAPS" | python3 -c "
import sys, json
caps = json.load(sys.stdin)
if not isinstance(caps, list):
    print('   ERROR: expected list, got', type(caps).__name__)
    sys.exit(1)
print('   modules found:', len(caps))
for c in caps[:3]:
    print('  ', c['module_id'])
if len(caps) > 3:
    print('   ...')
if len(caps) == 0:
    print('   WARNING: no capabilities registered — plugin scanner may have failed')
" || fail "Capabilities response malformed"
pass "Capabilities visible"
echo ""
echo "=== All checks passed. Agent is connected. ==="
