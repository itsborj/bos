# Data Model: Plugin Host MVP — WordPress / VS Code / pi.dev Model

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08

---

## Scope

This data model supports the MVP plugin host lifecycle:

```text
external-root scan → installed/quarantined → activate per Brand → CMO manifest
```

It intentionally does **not** implement a full lockfile, marketplace catalog, SDK adapter registry, hook registry, plugin migration ledger, or sandbox process model.

---

## Entity: PluginActivation

Tracks whether an installed plugin is active for a Brand or org-wide.

```text
plugin_activations
──────────────────
id              UUID        PK
plugin_id       TEXT        NOT NULL  — matches channel.json plugin_id
brand_id        UUID        NULLABLE  — NULL = org-level activation
status          TEXT        NOT NULL  — active | inactive | error
reason          TEXT        NULLABLE  — error or operator-visible note
created_at      TIMESTAMP   NOT NULL  DEFAULT now()
updated_at      TIMESTAMP   NOT NULL  DEFAULT now()

UNIQUE (plugin_id, brand_id)
INDEX  status
INDEX  brand_id
```

If the existing migration uses `error_reason` / `activated_at`, the ORM may map to those exact column names while exposing the conceptual fields above.

### Rules

```text
Plugin package present + no activation row → installed, inactive.
Activation row + package missing → stale/uninstalled; never manifest or inject.
status=active → plugin capabilities may enter CMO manifest for matching Brand.
status=inactive → Admin-visible only; not in CMO manifest.
status=error → Admin-visible warning; not in CMO manifest.
brand_id=NULL → org-level default.
brand-specific row overrides org-level row.
```

---

## In-Memory Entity: PluginState

Represents one scanned plugin package.

```text
PluginState
───────────
manifest          ChannelPluginManifest
root_path         Path
source            external | internal
status            installed | error
reason            string | null
capabilities_path Path
```

MVP source rules:

```text
source=external → normal runtime plugin from /external_plugins
source=internal → only when KLAROHA_LOAD_INTERNAL_PLUGINS=true
```

Quarantine behavior:

```text
If plugin_id can be read → PluginState(status=error, reason=...)
If plugin_id cannot be read → path-level diagnostic/log; no PluginState required
```

---

## Manifest Schema Additions

`channel.json` remains the plugin package contract.

MVP fields relevant to plugin host lifecycle:

```json
{
  "plugin_id": "channel.example",
  "name": "Example Channel",
  "version": "0.1.0",
  "klaroha_min_version": "3.5",
  "capabilities_root": "capabilities/",
  "implements": ["marketing.execute"],
  "specialty": ["example"],
  "platforms": ["example_platform"],
  "connector_protocol": "oauth2",
  "risk_policy": "draft_only",
  "output_contracts": ["example_draft"],
  "requires_platform_vars": [],
  "requires_social_connection": ["example_platform"],
  "connections": [
    {
      "platform": "example_platform",
      "type": "oauth2",
      "auth_url": "https://example.com/oauth/authorize",
      "token_url": "https://example.com/oauth/token",
      "scopes": ["profile"],
      "client_id_var": "EXAMPLE_CLIENT_ID",
      "client_secret_var": "EXAMPLE_CLIENT_SECRET",
      "redirect_uri_var": "EXAMPLE_REDIRECT_URI",
      "userinfo_url": "https://example.com/me",
      "id_path": "id",
      "name_path": "name",
      "validate_capability": "marketing.channel.example.connection.validate"
    }
  ],
  "capability_ids": ["marketing.channel.example.draft"]
}
```

---

## API Shapes

### GET /plugins

Minimum response shape:

```json
{
  "plugins": [
    {
      "plugin_id": "channel.example",
      "name": "Example Channel",
      "version": "0.1.0",
      "source": "external",
      "status": "installed",
      "reason": null,
      "capability_ids": ["marketing.channel.example.draft"],
      "requires_platform_vars": [],
      "requires_social_connection": ["example_platform"],
      "connections": [],
      "activation_by_brand": {
        "brand_uuid": "active"
      }
    }
  ]
}
```

### POST /plugins/{plugin_id}/activate

Request:

```json
{
  "brand_id": "uuid-or-null"
}
```

Response:

```json
{
  "plugin_id": "channel.example",
  "brand_id": "uuid-or-null",
  "status": "active"
}
```

### DELETE /plugins/{plugin_id}/activate

Request:

```json
{
  "brand_id": "uuid-or-null"
}
```

Response:

```json
{
  "plugin_id": "channel.example",
  "brand_id": "uuid-or-null",
  "status": "inactive"
}
```

---

## Capability Manifest Filtering

Manifest generation receives Brand context:

```python
build_dispatchable_manifest(brand_id=None, db=None)
format_manifest_for_prompt(brand_id=None, db=None)
```

Rules:

```text
First-party non-plugin capabilities → unaffected.
Plugin capabilities → included only if plugin_id is active for Brand and not quarantined.
Inactive plugin module IDs → excluded.
Uninstalled plugin module IDs → excluded.
Quarantined plugin module IDs → excluded.
```

Credential state is not the manifest gate for active plugins. Missing credentials should produce plugin-owned `setup_blocker` artifacts at execution time.

---

## Deferred Data Models

Do not build these in MVP:

```text
Plugin marketplace catalog
Installed-state lockfile with source hashes
Capability release-integrity ledger
SDK compatibility adapter registry
Plugin migration/resource ledger
Hook subscription persistence
Sandbox process/session registry
```
