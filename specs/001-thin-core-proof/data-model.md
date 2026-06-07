# Data Model: Thin Core + SDK Plugin Architecture

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08

---

## New Entity: PluginActivation

Tracks whether an installed plugin is active, per plugin per brand (or org-wide).

```
plugin_activations
──────────────────
id              UUID        PK
plugin_id       TEXT        NOT NULL  — matches channel.json plugin_id
brand_id        UUID        FK→brands.id, NULLABLE  — NULL = org-level activation
status          TEXT        NOT NULL  — 'active' | 'inactive' | 'error'
error_reason    TEXT        NULLABLE  — populated when status='error'
activated_at    TIMESTAMP   NOT NULL  DEFAULT now()
updated_at      TIMESTAMP   NOT NULL  DEFAULT now()

UNIQUE (plugin_id, brand_id)  — one record per plugin+brand combination
INDEX  plugin_activations_status_idx ON (status)
INDEX  plugin_activations_brand_idx  ON (brand_id)
```

**State transitions**:
```
discovered (scanner found it)
  → activate() → active
  → invalid manifest → error
active
  → deactivate() → inactive
  → manifest changes break it → error
inactive
  → activate() → active
error
  → fix + re-scan → active | inactive
```

**Rules**:
- A plugin directory present in `/external_plugins/` or `api/plugins/` but with
  no `plugin_activations` row = installed but not active.
- Manifest loads only plugins where `status = 'active'`.
- A plugin with `status = 'error'` appears in Admin as a warning — not in the CMO manifest.
- `brand_id = NULL` means activated for all brands (org-level). A per-brand activation
  row for the same `plugin_id` takes precedence over the org-level row.

---

## In-Memory Entity: HookRegistry

Not persisted to DB. Rebuilt at process startup from activated plugin declarations.

```python
HookRegistry
────────────
_hooks: dict[str, list[Callable]]
  key   = event name ("brief.before_dispatch", "run.after_complete", …)
  value = ordered list of async handler callables

subscribe(event: str, handler: Callable) → None
fire(event: str, payload: HookPayload) → HookPayload
```

**Hook event names (v1)**:
```
brief.before_dispatch   — enrich brief before module execution
run.after_complete      — react after module run completes
manifest.built          — annotate capability entry at scan time
plugin.activated        — plugin sets up resources for a brand
plugin.deactivated      — plugin tears down cleanly
```

---

## In-Memory Entity: PluginState (extended)

Existing `_PluginState` in `plugin_loader.py` extended with new v2 fields.

```
PluginState
───────────
manifest          ChannelPluginManifest  (existing)
root_path         Path                   (existing)
source            Literal["internal", "external"]  NEW
is_active         bool                   NEW — set from DB activation record
hook_subscriptions list[str]             NEW — event names from channel.json v2
credential_injectors list[str]           NEW — credential key names from channel.json v2
sdk_version       str | None             NEW — minimum klaroha_sdk version
```

---

## SDK Package: klaroha_sdk Types

These are the stable public types a plugin author imports. Once published, they
do not change in breaking ways without a major version bump.

```python
# klaroha_sdk/types.py

@dataclass
class BridgeEnvelope:
    run_id: str
    module_id: str
    brand_id: str | None
    workspace_id: str
    payload: dict          # module-specific inputs
    metadata: dict         # lineage, attempt count, intent_ref

@dataclass
class RunResult:
    run_id: str
    status: Literal["success", "failed", "pending_review"]
    artifact_blocks: list[ArtifactBlock]
    self_check: Literal["pass", "fail"] | None
    error: str | None

@dataclass
class ArtifactBlock:
    block_type: str        # "email_draft", "image_asset", "pipeline_test_result", …
    content: dict          # block-type-specific fields
    renderer_hint: str     # "approval_bundle", "stream_card", "narrative"
    allowed_actions: list[str]  # "approve", "revise", "dismiss"

@dataclass
class HookPayload:
    event: str
    brief: dict            # mutable — subscribers enrich this
    context: dict          # read-only turn context (brand, workspace, settings)
    metadata: dict         # hook-specific extras

@dataclass
class CredentialPayload:
    platform: str
    page_token: str | None
    page_id: str | None
    extra: dict            # additional platform-specific fields
```

---

## channel.json v2 Schema (additive)

New optional fields added to the existing manifest schema. All existing v1 plugins
continue loading without changes.

```json
{
  "plugin_id": "channel.gmail",
  "name": "Gmail Channel",
  "version": "0.1.0",
  "sdk_version": "1.0",

  "hook_subscriptions": [
    "brief.before_dispatch"
  ],

  "credential_injectors": [
    "gmail_credentials"
  ],

  "klaroha_min_version": "3.5",
  "capabilities_root": "capabilities/",
  "implements": ["marketing.execute"],
  "specialty": ["outreach", "cold_email", "email_drafting"],
  "platforms": ["gmail"],
  "connector_protocol": "smtp_or_env",
  "risk_policy": "draft_only",
  "output_contracts": ["email_draft"],
  "requires_social_connection": [],
  "requires_platform_vars": ["GMAIL_USER"],
  "capability_ids": ["marketing.channel.gmail.outreach.draft"]
}
```

---

## Relationships

```
Workspace (1) ──────────────── (N) PluginActivation
Brand     (1) ──────────────── (N) PluginActivation  [brand_id FK]
PluginActivation.plugin_id ←→ channel.json.plugin_id  [string key, not FK]
HookRegistry ←── populated from ─── PluginActivation (active rows only)
```
