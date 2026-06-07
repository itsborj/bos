# Quickstart Validation Guide: Thin Core + SDK Plugin Architecture

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08

This guide proves the architecture works. Run each validation in sequence.

---

## Prerequisites

- `~/bos/` repo on branch `001-thin-core-proof`
- `~/bos-plugins/` repo initialized (separate git repo)
- Docker and docker-compose available
- `.env` with `DATABASE_URL`, `API_SECRET_KEY`, `ENCRYPTION_KEY`, `PLATFORM_OPENROUTER_KEY`

---

## V1 — SDK Package Installs Clean

```bash
cd ~/bos
pip install -e packages/klaroha_sdk
python -c "from klaroha_sdk import ChannelModule, ArtifactBlock, RunResult, HookPayload; print('SDK OK')"
```

**Expected**: `SDK OK` — no import errors, no BOS internal imports needed.

---

## V2 — Core Starts with Empty Plugin Directory

```bash
mkdir -p ~/bos-plugins   # empty
docker compose up -d
curl -s http://localhost:8090/ | jq .status
```

**Expected**: `"ok"` — BOS starts cleanly with no external plugins loaded.

```bash
curl -s -H "X-API-Key: $KEY" http://localhost:8090/api/plugins/manifest | jq '.capabilities | length'
```

**Expected**: `0` — empty manifest, no error.

---

## V3 — hello Plugin Appears After Adding to bos-plugins

```bash
cp -r ~/bos/api/plugins/hello ~/bos-plugins/hello   # copy + adapt (module.py → sdk-only)
docker compose restart api
curl -s -H "X-API-Key: $KEY" http://localhost:8090/api/plugins/manifest | jq '.capabilities[].module_id'
```

**Expected**: `"marketing.channel.hello.pipeline_test"` in output.

Activate the plugin:
```bash
curl -s -X POST -H "X-API-Key: $KEY" \
  http://localhost:8090/api/plugins/channel.hello/activate | jq .status
```

**Expected**: `"active"`

---

## V4 — hello Dispatches via CMO Chat

```bash
curl -s -X POST -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "run a pipeline test"}' \
  http://localhost:8090/api/chat | jq '{reply: .reply, runs: [.runs[].module_id]}'
```

**Expected**: Reply text + `"marketing.channel.hello.pipeline_test"` in runs.
A `pipeline_test_result` artifact appears in Stream.

**Core check**:
```bash
wc -l ~/bos/api/routers/chat.py
```
**Expected**: Under 200 lines.

```bash
grep -c "hello\|gmail\|google\|meta\|clickup\|tiktok" ~/bos/api/routers/chat.py
```
**Expected**: `0` — no plugin names in chat.py.

---

## V5 — Delete hello, BOS Stays Stable

```bash
rm -rf ~/bos-plugins/hello
docker compose restart api
curl -s http://localhost:8090/ | jq .status
```

**Expected**: `"ok"` — no crash.

```bash
curl -s -H "X-API-Key: $KEY" http://localhost:8090/api/plugins/manifest | jq '.capabilities | length'
```

**Expected**: `0` — empty manifest, no error.

---

## V6 — gbp-completeness Plugin via SDK Only

```bash
# Confirm module.py has only klaroha_sdk imports
grep "^from\|^import" ~/bos-plugins/gbp-completeness/capabilities/marketing/intelligence/gbp/completeness_score/module.py
```

**Expected**: Only `from klaroha_sdk import ...` and `import httpx` — no `api.*`, no `config`, no `db`.

Activate and trigger via CMO:
```bash
curl -s -X POST -H "X-API-Key: $KEY" \
  http://localhost:8090/api/plugins/channel.gbp-completeness/activate | jq .status
```

**Expected**: `"active"`

In CMO chat, send: `"check my google business profile"` or `"gbp audit"`

**Expected outcomes**:
- If Google Business Profile is **not connected** for the active brand:
  `setup_blocker` artifact appears in Stream — not a crash.
- If Google Business Profile **is connected**:
  `gbp_completeness_result` artifact with `approval_bundle` renderer appears in Stream.
  `status: "pending_review"` — operator can Approve or Dismiss.

**SDK boundary check**:
```bash
grep -r "from api\|import api\|from config\|from db" ~/bos-plugins/gbp-completeness/
```
**Expected**: No output — zero BOS internal imports.

---

## V7 — Delete gbp-completeness, BOS + hello Both Stable

```bash
rm -rf ~/bos-plugins/gbp-completeness
docker compose restart api

# hello should still work
curl -s -X POST -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "run a pipeline test"}' \
  http://localhost:8090/api/chat | jq '.runs[0].module_id'
```

**Expected**: `"marketing.channel.hello.pipeline_test"` — unaffected by gbp-completeness removal.

```bash
curl -s http://localhost:8090/ | jq .status
```

**Expected**: `"ok"` — no crash, no errors in logs.

---

## V8 — Live Deploy to hq.klaroha.com

```bash
# On server: ensure ~/bos-plugins is cloned
# git clone <bos-plugins-repo> ~/bos-plugins

# Merge 001-thin-core-proof to main
git checkout main
git merge 001-thin-core-proof

# Deploy via existing runbook (deploy-staging.sh equivalent for prod)
# Verify
curl -s https://hq.klaroha.com/api/ | jq .status
```

**Expected**: `"ok"` — live system running new architecture.

Repeat V4 and V6 against `https://hq.klaroha.com/api/chat`.

---

## What Failure Looks Like

| Symptom | Root cause |
|---|---|
| BOS crashes on startup when a plugin dir is invalid | Scanner not quarantining bad plugins |
| Plugin names appear in `grep` of chat.py | Core not fully extracted |
| `from api.routers import X` succeeds in a plugin | SDK boundary not enforced (check Python path) |
| Removing a plugin dir causes 500 errors | Plugin not properly deregistered from hook registry |
| Manifest shows inactive plugin capabilities | Activation state not checked during manifest build |
