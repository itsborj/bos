# Quickstart Validation Guide: Plugin Host MVP — WordPress / VS Code Model

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08

This guide validates the MVP plugin-host lifecycle from `api/plugins/PLUGIN_ARCHITECTURE_RECOMMENDATION.md`.

---

## Prerequisites

- BOS core repo at `~/bos`
- External plugin root at `~/bos-plugins`
- Docker Compose running BOS
- API key available as `$KEY`
- `EXTERNAL_PLUGINS_PATH=/home/ubu/bos-plugins` or equivalent absolute path
- `KLAROHA_LOAD_INTERNAL_PLUGINS` unset or false for normal validation

---

## V1 — Empty External Root Produces No Plugin Capabilities

```bash
mkdir -p /tmp/empty-plugins
cd ~/bos
EXTERNAL_PLUGINS_PATH=/tmp/empty-plugins docker compose up -d --force-recreate api
curl -s http://localhost:8090/api/ | jq .status
```

Expected:

```text
"ok"
```

Check plugins:

```bash
curl -s -H "X-API-Key: $KEY" http://localhost:8090/api/plugins | jq '.plugins | length'
```

Expected:

```text
0
```

Check CMO manifest by sending a chat turn or using an available manifest/debug endpoint. Expected: no plugin capabilities.

---

## V2 — D2/D4 Install Plugin, Default Inactive

Place a valid plugin in external root:

```bash
mkdir -p ~/bos-plugins
# example: copy or checkout hello into ~/bos-plugins/hello
# do not use api/plugins as runtime source
cd ~/bos
docker compose restart api
```

Check installed list:

```bash
curl -s -H "X-API-Key: $KEY" http://localhost:8090/api/plugins | jq '.plugins[] | {plugin_id, status, activation_by_brand}'
```

Expected:

```text
plugin appears as installed
activation is inactive or absent for current Brand
```

Expected CMO behavior:

```text
Plugin capability is not in CMO manifest while inactive.
```

---

## V3 — Activate Plugin for Brand

Activate installed plugin:

```bash
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"brand_id":"<BRAND_ID>"}' \
  http://localhost:8090/api/plugins/<PLUGIN_ID>/activate | jq .
```

Expected:

```text
status = active
```

Expected CMO behavior:

```text
Plugin allowed_from_chat capabilities appear in CMO manifest for that Brand.
Other Brands do not see the plugin unless activated separately or org-wide.
```

---

## V4 — D4 Deactivate Plugin

```bash
curl -s -X DELETE \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"brand_id":"<BRAND_ID>"}' \
  http://localhost:8090/api/plugins/<PLUGIN_ID>/activate | jq .
```

Expected:

```text
status = inactive
```

Expected CMO behavior:

```text
Plugin capability disappears from CMO manifest for that Brand.
RUN for inactive module_id is rejected/not available.
```

---

## V5 — D3 Broken Plugin Quarantine

Create a broken plugin in external root:

```bash
mkdir -p ~/bos-plugins/bad-plugin
printf '{ bad json' > ~/bos-plugins/bad-plugin/channel.json
cd ~/bos
docker compose restart api
```

Expected:

```text
BOS starts normally.
Valid plugins still load.
Bad plugin is reported as status=error if plugin_id is recoverable, otherwise path-level warning appears in logs.
```

Cleanup:

```bash
rm -rf ~/bos-plugins/bad-plugin
docker compose restart api
```

---

## V6 — D6 Specialists UI Shows Installed Plugins Only

Open:

```text
http://localhost:8090/admin/modules
```

Expected:

```text
Only plugins returned by GET /plugins have Specialist cards.
No TikTok card if TikTok plugin is not installed.
No LinkedIn card if LinkedIn plugin is not installed.
Uninstalled platforms create no connector warnings or readiness debt.
Installed plugins show activation controls per Brand.
```

---

## V7 — D7 Generic Credential Injection Boundary

For each external plugin:

```bash
grep -R "from config\|from db\|from models\|from routers\|from registry\|import config\|import db\|import models\|import routers\|import registry" ~/bos-plugins || true
```

Expected:

```text
No output from plugin module code.
```

At runtime, credential-requiring plugins read only:

```python
brief["_channel_credentials"]
```

---

## V8 — D8 Generic Plugin-Declared OAuth Verification

Use a test plugin or real simple OAuth2 plugin with `connections` in `channel.json`.

Expected flow:

```text
1. Plugin declares standard OAuth2 connection.
2. Operator starts /social/connect/start for the declared platform.
3. Core uses manifest-declared auth_url/token_url/scopes/client vars.
4. Callback stores SocialConnection.
5. inject_channel_credentials injects token into brief["_channel_credentials"].
6. No platform-specific core OAuth handler is added.
```

If this fails, record the gap. Do not implement full OAuth edge-case framework in this MVP.

---

## Failure Table

| Symptom | Likely violation |
|---|---|
| Plugin from `api/plugins/` appears with compatibility flag off | D1 violation |
| LinkedIn/TikTok card appears when plugin not installed | D6 violation |
| Installed inactive plugin appears in CMO manifest | D5 violation |
| Bad plugin crashes startup | D3 violation |
| New OAuth platform requires hardcoded core handler | D8 violation |
| Plugin imports `db`, `models`, `routers`, or `config` | D7 violation |
