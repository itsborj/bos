# Implementation Plan: Plugin Host MVP — WordPress / VS Code / pi.dev Model

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08 | **Spec**: [spec.md](spec.md)

---

## Summary

Implement the MVP plugin-host primitives agreed in:

```text
api/plugins/PLUGIN_ARCHITECTURE_RECOMMENDATION.md
```

The one rule:

```text
If a plugin is not installed and activated, BOS should act like it does not exist.
```

This feature is **not** the full thin-core rewrite. It is the lean WordPress / VS Code / pi.dev plugin-host layer:

```text
WordPress  → install/activate/deactivate lifecycle
VS Code    → enabled extension contribution points
pi.dev     → thin host, loaded resources, live manifest, no platform branches
```

```text
external install root → installed/quarantined → activate per Brand → CMO manifest
```

---

## MVP Deliverables

This plan implements D1–D8 from the recommendation.

| ID | Deliverable | Status Target |
|---|---|---|
| D1 | External plugin root is runtime source | Verify / patch |
| D2 | Installed plugins API shows installed packages only | Build / patch |
| D3 | Basic quarantine | Build / patch |
| D4 | Minimal per-brand activation | Build |
| D5 | CMO manifest filters by activation | Build |
| D6 | Specialists UI is manifest-driven | Build / patch |
| D7 | Generic credential injection is the only plugin credential path | Verify / patch |
| D8 | Minimal generic plugin-declared OAuth | Verify / patch only if missing |

---

## Explicitly Out of Scope

Do not implement these in this feature:

```text
Marketplace / Available UI
full installed-state lockfile with source hashes
capability release-integrity diff
SDK ABI compatibility adapters
hook subscription system
plugin-owned migrations
hot reload
separate sandbox/subprocess extension host
full OAuth provider edge-case framework
chat.py 7-step rewrite
full migration of existing plugins
```

If current code contains partial attempts at these, do not expand them as part of this MVP.

---

## Technical Context

**Language/Version**: Python 3.11 target, TypeScript/React for Admin UI  
**Backend**: FastAPI, SQLAlchemy async, Pydantic  
**Storage**: PostgreSQL; `plugin_activations` table via migration 038  
**Plugin source**: external volume mounted at `/external_plugins` from `~/bos-plugins`  
**Bundled examples**: `api/plugins/` is SDK/example/deprecated source, not runtime source by default

---

## Architecture Rules

1. Core must be plugin-ready, not platform-ready.
2. Uninstalled plugins are invisible.
3. Installed does not mean active.
4. Activation is explicit and Brand-scoped.
5. Active plugin capabilities appear in the CMO manifest.
6. Missing credentials are handled by plugin-owned `setup_blocker` artifacts, not by hardcoded core platform branches.
7. Specialists UI is a view over installed plugins, not a hardcoded platform catalog.
8. `api/plugins/` must not create runtime capabilities unless `KLAROHA_LOAD_INTERNAL_PLUGINS=true`.
9. Core must preserve the pi.dev thin-host invariant: loaded plugin resources change behavior; core code does not grow a branch per plugin.
10. There is no module concept. Everything is a package. Built-in packages (`api/capabilities/`) and installed packages (`~/bos-plugins/`) share an identical contract and identical trust level. No package imports BOS internals. This follows the WordPress/VS Code model: the loader discovers packages from one or more source roots; the contract is uniform regardless of who wrote the package or where it ships from.

---

## Constitution Check

| Principle | Check | Status |
|---|---|---|
| Minimal Core | Adds generic plugin-host primitives only; no platform-specific routing; follows pi.dev thin-host discipline. | Pass |
| Capability-as-Package | Runtime plugin packages come from external install root. | Pass |
| SKILL.md Contract | Manifest remains generated from plugin/skill declarations. | Pass |
| CMO Integrity | CMO manifest filters by active plugin state; no hardcoded platform cards. | Pass |
| Brand Isolation | Activation is Brand-scoped. | Pass |
| Persistence | Uses `plugin_activations` table; no inline ad-hoc state. | Pass |
| Lean Scope | Marketplace, hooks, lockfile, sandbox, and chat rewrite deferred. | Pass |

---

## Project Structure Changes

Expected core files touched for MVP:

```text
api/plugin_loader.py                 # external root, installed/quarantine state, plugin mapping
api/models/plugin_activation.py       # ORM model for migration 038
api/routers/plugins.py                # installed plugin API + activate/deactivate endpoints
api/capability_manifest.py            # brand-aware active plugin filtering
api/routers/chat.py                   # only call manifest with brand context if needed; no platform logic
api/routers/runs.py                   # verify credential injection remains generic
web/src/pages/admin/AdminModules.tsx  # installed-only Specialists UI + activation toggle
web/src/api/types.ts                  # plugin activation/status types
web/src/api/client.ts                 # activate/deactivate API calls
```

Files explicitly **not** targeted:

```text
api/routers/chat.py full rewrite
api/pipeline/hooks.py expansion
marketplace UI
all plugin migrations
```

---

## Implementation Sequence

### Phase 1 — Verify/Patch D1, D2, D3

1. Confirm `EXTERNAL_PLUGINS_DIR` is the runtime plugin root.
2. Confirm `api/plugins/` is skipped unless `KLAROHA_LOAD_INTERNAL_PLUGINS=true`.
3. Ensure `GET /plugins` returns installed external packages only.
4. Ensure invalid plugins are quarantined per plugin and do not crash startup.

Acceptance:

```text
Empty /external_plugins → zero plugin capabilities.
No external LinkedIn plugin → no LinkedIn plugin in GET /plugins.
Broken plugin does not hide valid plugin.
```

---

### Phase 2 — Build D4 Activation

1. Add `PluginActivation` ORM model for existing migration 038.
2. Add activation read helper:

```text
get_active_plugin_ids(db, brand_id)
```

3. Add endpoints:

```text
POST   /plugins/{plugin_id}/activate
DELETE /plugins/{plugin_id}/activate
```

4. Default: installed + no activation row = inactive.

Acceptance:

```text
Installed but inactive plugin appears in Admin / Installed but not in CMO manifest.
```

---

### Phase 3 — Build D5 Manifest Filtering

1. Make capability manifest generation brand-aware.
2. Filter plugin capabilities by active plugin IDs.
3. Do not add a second platform-specific gate in `chat.py`.
4. First-party non-plugin capabilities remain unaffected.

Acceptance:

```text
Brand A activates hello → Brand A manifest includes hello.
Brand B does not activate hello → Brand B manifest excludes hello.
Inactive module_id cannot be RUN from CMO chat.
```

---

### Phase 4 — Build/Patch D6 Specialists UI

1. Remove hardcoded cards for uninstalled platforms.
2. Render Specialists from `GET /plugins` data.
3. Show activation state per Brand.
4. Add activate/deactivate controls.
5. Show setup/validation status only for installed plugins.

Acceptance:

```text
No TikTok plugin installed → no TikTok Specialist card.
No LinkedIn plugin installed → no LinkedIn Specialist card.
Uninstalled platforms create no warnings/readiness debt.
```

---

### Phase 5 — Verify/Patch D7 and D8

D7:

```text
Plugins receive credentials only via brief["_channel_credentials"].
```

D8:

```text
A standard plugin-declared OAuth2 connection can start auth, complete callback, store token, and inject credentials without a platform-specific core handler.
```

If D8 is partial, document the gap and keep `requires_platform_vars` as the MVP escape hatch for unusual providers.

---

## Testing Strategy

Run the quickstart validations in [quickstart.md](quickstart.md):

```text
V1 empty root
V2 install/inactive
V3 activate/manifest
V4 quarantine
V5 installed-only UI
V6 generic credential path
V7 generic OAuth verification
```

Also run targeted tests for:

```text
plugin_loader external/internal flag behavior
plugins API installed/error output
PluginActivation precedence
capability_manifest brand filtering
AdminModules installed-only rendering
```

---

## Deployment Plan

Local:

```text
~/bos              # core
~/bos-plugins      # external plugins
/external_plugins  # container mount
```

Production uses the same shape.

Before deploy:

```text
1. Verify /external_plugins empty → no plugin capabilities.
2. Verify installed inactive plugin → Admin only.
3. Verify activation → manifest entry.
4. Verify uninstalled platforms absent from UI.
```

---

## Rollback

If activation filtering breaks dispatch:

```text
Disable external plugins by emptying /external_plugins or deactivating plugin rows.
Core should continue running with first-party capabilities only.
```

Do not re-enable `api/plugins/` runtime loading in production as rollback unless explicitly approved.
