# Plugin Developer Onboarding — MVP Boundary

You are building a third-party plugin for Klaroha BOS.

Start from the public SDK guide:

```text
api/plugins/PLUGIN_SDK.md
```

This onboarding document summarizes the isolation model agreed for the plugin-host MVP.

---

## Mental Model

Two concepts: **Core** and **Plugin**.

Core (`workspace.*`, `onboarding.*`) is the CMO harness — context loading, brand scoping, approval gating. It cannot be deactivated and it does not know your platform.

Your plugin is an installed package. The plugin directory is the skill bundle — install it, remove it, upgrade it as one unit. Everything your capability needs lives inside that directory.

```text
Not installed → invisible
Installed → visible in Admin only
Activated for Brand → CMO can see allowed capabilities
Missing credentials → plugin returns setup_blocker artifact
```

Core must not know your platform before your plugin is installed.

---

## Where Plugin Work Happens

Do not work inside the BOS core repo.

```text
~/bos          # core repo, owned by BOS core developers
~/bos-plugins  # third-party plugin workspace / install root
```

At runtime, Docker mounts:

```text
~/bos-plugins → /external_plugins
```

**Important — use an absolute path.** Docker does not expand `~`. In `docker-compose.yml`, `EXTERNAL_PLUGINS_PATH` must be an absolute path (e.g. `/home/user/bos-plugins`), not `~/bos-plugins`. The default in the container is `/external_plugins`.

A plugin package lives at:

```text
~/bos-plugins/your-plugin/
├── channel.json
└── capabilities/
    └── ...
```

Bundled examples under `~/bos/api/plugins/` are not runtime-installed plugins by default.

---

## Minimum Plugin Files

```text
your-plugin/
├── channel.json
└── capabilities/{domain}/{action}/
    ├── SKILL.md
    ├── module.py
    └── template.j2        # optional for direct tool execution
```

The capability path does not repeat the platform name — the plugin directory already establishes context. Keep paths short: `capabilities/post/publish/`, `capabilities/analytics/performance/`, `capabilities/connection/validate/`.

---

## Import Rule

At module level, plugin code imports only:

```python
from klaroha_sdk import ChannelModule
```

Do not import:

```text
config
db
models
auth
executor
registry
routers
settings
```

Credentials arrive only through:

```python
brief["_channel_credentials"]
```

---

## Credential Rules

Declare what your plugin needs in `channel.json` as `credential_slots`. Core resolves each slot by type — no platform names in core.

**API key credential:**

```json
"credential_slots": [
  { "key": "EXAMPLE_API_KEY", "type": "platform_var", "var": "EXAMPLE_API_KEY" }
]
```

**OAuth2 social connection:**

```json
"connections": [
  {
    "platform": "example_platform",
    "type": "oauth2",
    "scopes": ["profile"],
    "client_id_var": "EXAMPLE_CLIENT_ID",
    "client_secret_var": "EXAMPLE_CLIENT_SECRET",
    "validate_capability": "example.connection.validate"
  }
],
"credential_slots": [
  { "key": "access_token", "type": "social_token", "platform": "example_platform" }
]
```

**AI provider override (e.g. media plugins):**

```json
"credential_slots": [
  { "key": "IMAGE_PROVIDER", "type": "backend_override_provider" },
  { "key": "IMAGE_MODEL",    "type": "backend_override_model" },
  { "key": "IMAGE_API_KEY",  "type": "backend_provider_api_key", "module": "IMAGE_PROVIDER" }
]
```

See `PLUGIN_SDK.md § 7` for all seven slot types. Do not use `requires_platform_vars` or `requires_social_connection` — those fields are retired.

---

## Missing Credentials

A plugin must fail gracefully with a setup-blocker style artifact/block.

Example direct-tool result shape:

```python
return attempt_data, {
    "content": "Connect Example Platform before running this specialist.",
    "sell_price": None,
    "block": {
        "type": "example_connection_check",
        "platform": "example_platform",
        "status": "failed",
        "reason_code": "missing_credentials",
        "message": "Example Platform is not connected for this Brand.",
        "read_only": True,
        "changed_resources": [],
        "allowed_actions": ["connect", "dismiss"],
        "risk_policy": "connection_validate_is_read_only",
    },
}
```

Do not raise for missing credentials.

---

## Activation

Installation is not activation.

After your plugin is installed in `~/bos-plugins`, the operator must activate it for a Brand in Admin / Specialists.

Only active plugin capabilities can enter the CMO manifest.

---

## SKILL.md Guidance

`SKILL.md` controls when the CMO may dispatch your capability.

Use specific triggers and exclusions.

Avoid broad triggers like:

```text
write
create
post
analyze
```

Prefer platform/task-specific triggers:

```text
linkedin post
check linkedin connection
google business profile audit
```

For overlapping ecosystems, use `excluded_triggers` aggressively.

**`requires_intent` — use canonical values only.** The field must be one or more of the following exact strings. Non-canonical values cause the SKILL.md to be silently skipped by the parser:

```text
discussion
generation
revision
approval
onboarding
diagnostic
action
publish
```

Leave `requires_intent: []` (empty) if your capability responds to any intent class.

---

## Local Validation

```bash
# verify source isolation
grep -R "from config\|from db\|from models\|from routers\|from registry" ~/bos-plugins/your-plugin || true

# restart host after install
cd ~/bos
docker compose restart api

# verify plugin appears installed but inactive
curl -s -H "X-API-Key: $KEY" http://localhost:8090/api/plugins | jq .
```

Expected before activation:

```text
plugin appears in Admin/plugin API
plugin does not appear in CMO manifest
```

Expected after activation:

```text
plugin allowed_from_chat capabilities appear for the activated Brand
```
