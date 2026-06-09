# Feature Specification: Plugin Host MVP — WordPress / VS Code / pi.dev Model

**Feature Branch**: `001-thin-core-proof`  
**Created**: 2026-06-08  
**Updated**: 2026-06-08  
**Status**: MVP contract agreed — implementation must follow `api/plugins/PLUGIN_ARCHITECTURE_RECOMMENDATION.md`

---

## Scope Correction

This spec supersedes the earlier broad thin-core rewrite scope for this feature.

Do **not** use this feature to rewrite `chat.py`, build hooks, migrate all plugins, build a marketplace, create a full lockfile, add SDK compatibility adapters, add plugin migrations, implement hot reload, or create a subprocess sandbox.

The MVP goal is narrower:

```text
Make BOS core behave like a WordPress / VS Code / pi.dev style plugin host.
```

Reference models:

```text
WordPress  → install/activate/deactivate lifecycle
VS Code    → extension host + enabled extension contribution points
pi.dev     → thin core + loaded resources + live manifest instead of core branches
```

If a plugin is not installed and activated, BOS must act like it does not exist.

---

## Problem Statement

BOS has been drifting toward a hardcoded platform catalog:

```text
Core knows a platform before its plugin is installed.
Admin UI shows possible platforms as if they are installed specialists.
CMO manifest can expose capabilities that are not truly installed/active.
New third-party plugins can require core updates before becoming operational.
```

This violates the plugin model.

Correct model:

```text
Core is plugin-ready, not platform-ready.
Plugins declare themselves.
Installed/active plugins appear.
Uninstalled plugins are invisible.
```

WordPress does not show WooCommerce products until WooCommerce is installed and activated. VS Code does not show extension commands until the extension is installed/enabled. pi.dev keeps the agent harness thin by loading skills/tools/subagents/resources instead of growing core branches. BOS must combine these lessons.

---

## Non-Negotiable MVP Deliverables

### D1 — External plugin root is runtime source

Runtime plugin discovery MUST read external installed plugins from:

```text
EXTERNAL_PLUGINS_DIR=/external_plugins
```

The external root is normally mounted from:

```text
~/bos-plugins
```

Bundled examples under `api/plugins/` MUST NOT load by default. They may load only with explicit local compatibility:

```text
KLAROHA_LOAD_INTERNAL_PLUGINS=true
```

**Acceptance**:

```text
Empty /external_plugins → zero plugin capabilities after restart.
Bundled api/plugins examples do not appear unless compatibility flag is set.
```

---

### D2 — Installed plugins API shows installed packages only

Admin/Core MUST expose a plugin list derived from the external install root and manifest validation.

MVP installed state is intentionally lean:

```text
external-root scan
+ manifest validation/quarantine status
+ per-brand activation DB
```

Do not build a full source-hash lockfile in MVP.

Minimum fields:

```text
plugin_id
name
version
source
status: installed | error
reason
capability_ids
requires_platform_vars
requires_social_connection
connections
activation_by_brand
```

**Acceptance**:

```text
No external LinkedIn plugin → no LinkedIn entry in GET /plugins response.
One invalid plugin does not prevent valid plugins from appearing.
```

---

### D3 — Basic quarantine

A broken plugin MUST NOT crash BOS startup or hide unrelated plugins.

Minimum quarantine reasons:

```text
invalid_channel_json
incompatible_klaroha_version
duplicate_plugin_id
duplicate_module_id
module_import_failed
skill_parse_failed
```

Lean MVP behavior:

```text
If plugin_id can be read → return plugin with status=error and reason.
If plugin_id cannot be read → report path-level error in diagnostics/logs; do not crash.
```

**Acceptance**:

```text
One broken plugin appears as status=error when recoverable.
Valid plugins still load.
BOS startup does not fail.
```

---

### D4 — Minimal per-brand activation

Add minimal plugin activation state.

Minimum shape:

```text
plugin_id
brand_id
status: active | inactive | error
reason
created_at
updated_at
```

Default behavior:

```text
Directory present + no activation row → installed, inactive.
Activation row + no directory → stale/uninstalled; never inject or manifest.
```

Activation is explicit and Brand-scoped.

**Acceptance**:

```text
Installed but inactive plugin appears in Admin / Installed.
Installed but inactive plugin does not appear in CMO manifest.
```

---

### D5 — CMO manifest filters by activation

The CMO manifest MUST include plugin capabilities only when the plugin is:

```text
installed
active for the current Brand
not quarantined
SKILL.md allowed_from_chat=true
```

Credential state is not a core manifest gate once the plugin is active. If credentials are missing, the active plugin returns a `setup_blocker` artifact at execution time. This matches WordPress/VS Code setup-notice behavior.

The filter point must be generic. Do not add platform-specific checks to `chat.py`.

**Acceptance**:

```text
Inactive plugin module_id cannot be RUN from CMO chat.
Active plugin with missing credentials returns setup_blocker artifact, not a core crash.
No platform-specific CMO routing logic is added.
```

---

### D6 — Specialists / Installed UI is manifest-driven

Admin Specialists UI MUST show installed plugins only.

It MUST NOT show hardcoded platform cards for uninstalled platforms.

Build/patch:

```text
Render installed plugin cards from GET /plugins.
Show activation state per Brand.
Add Activate/Deactivate per Brand.
Show setup/validation status only for installed plugins.
```

**Acceptance**:

```text
No TikTok plugin installed → no TikTok Specialist card.
No LinkedIn plugin installed → no LinkedIn Specialist card.
Uninstalled platforms create no connector warnings or readiness debt.
```

---

### D7 — Generic credential injection is the only plugin credential path

Core MUST inject declared credentials into:

```python
brief["_channel_credentials"]
```

Plugins MUST NOT read settings, DB, routers, provider tables, or BOS internals.

**Acceptance**:

```text
Plugin module.py imports only from klaroha_sdk at module level.
Credential-requiring plugin receives credentials only through brief["_channel_credentials"].
```

---

### D8 — Minimal generic plugin-declared OAuth

Core SHOULD support lean plugin-declared OAuth2 so a third-party platform does not require platform-specific core code.

MVP fields:

```text
platform
type=oauth2
auth_url
token_url
scopes
client_id_var
client_secret_var
redirect_uri_var
userinfo_url
id_path
name_path
validate_capability
```

Do not implement every OAuth edge case. If a platform has an unusual OAuth flow, the plugin can use `requires_platform_vars` for MVP.

**Acceptance**:

```text
A plugin-declared OAuth platform can start auth, complete callback, store token, and receive injected credentials without adding a platform-specific core handler.
```

---

## Explicitly Deferred

These are intentionally out of MVP scope:

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
chat.py 7-step rewrite as part of this feature
full migration of all existing plugins
```

---

## User Stories

### User Story 1 — Empty plugin root is clean

As an operator, I can start BOS with no external plugins installed and the app still runs normally.

**Acceptance**:

```text
Given /external_plugins is empty
When BOS restarts
Then GET /plugins returns no installed plugins
And the CMO manifest contains no plugin capabilities
And CMO chat still responds without crashing
```

---

### User Story 2 — Installed but inactive plugin is visible only in Admin

As an operator, I can install a plugin package and review it before activating it for a Brand.

**Acceptance**:

```text
Given hello plugin exists in /external_plugins
And no activation row exists for the active Brand
When BOS restarts
Then Admin / Specialists shows hello as installed/inactive
And CMO manifest does not include hello
```

---

### User Story 3 — Activation makes capabilities available

As an operator, I can activate an installed plugin for a Brand and then use its CMO-dispatchable capabilities.

**Acceptance**:

```text
Given hello plugin is installed
When I activate hello for Brand A
Then Brand A CMO manifest includes hello allowed_from_chat capabilities
And Brand B does not see hello unless separately activated
```

---

### User Story 4 — Broken plugin is quarantined

As an operator, one bad plugin should not break BOS or hide valid plugins.

**Acceptance**:

```text
Given hello is valid
And broken-plugin has invalid channel.json or broken module.py
When BOS starts
Then hello still loads
And broken-plugin is reported as error when recoverable
And BOS does not crash
```

---

### User Story 5 — Third-party OAuth does not require platform-specific core code

As a plugin developer, I can declare a standard OAuth2 platform in `channel.json` and let core perform generic OAuth mechanics.

**Acceptance**:

```text
Given plugin channel.json declares connections[0].platform = example_platform
When operator starts social connect for example_platform
Then core starts OAuth using the manifest declaration
And callback stores a SocialConnection
And plugin receives credentials through brief["_channel_credentials"]
Without adding a platform-specific OAuth handler to core
```

---

## Functional Requirements

- **FR-001**: BOS MUST use external plugin root as runtime plugin source by default.
- **FR-002**: BOS MUST NOT load bundled `api/plugins/` by default.
- **FR-003**: BOS MUST expose installed plugin metadata from external root only, unless local compatibility is explicitly enabled.
- **FR-004**: BOS MUST isolate plugin load failures per plugin.
- **FR-005**: BOS MUST support inactive-by-default plugin installation.
- **FR-006**: BOS MUST support per-brand plugin activation.
- **FR-007**: CMO manifest MUST include active plugin capabilities only.
- **FR-008**: Specialists UI MUST be generated from installed plugin manifests, not hardcoded platform cards.
- **FR-009**: Plugins MUST receive credentials only through `brief["_channel_credentials"]`.
- **FR-010**: Core SHOULD support lean generic OAuth2 declarations in `channel.json`.
- **FR-011**: Core MUST NOT add platform-specific routing or readiness branches to CMO chat for this work.
- **FR-012**: Core MUST preserve the pi.dev-style thin-host invariant: plugin behavior appears through installed resources/manifests, not permanent core branches.
- **FR-013**: BOS MUST treat all capabilities as packages with an identical contract regardless of source location. Built-in packages (`api/capabilities/`) and installed packages (`~/bos-plugins/`) share the same contract: `SKILL.md` + `module.py` + `channel.json`. No package — including built-in packages — may import BOS internals (`db`, `models`, `routers`, `settings`, `executor`). There is no module concept.
- **FR-014**: `POST /plugins/{id}/activate` MUST block org-wide activation (`brand_id=null`) unless both `scope="org"` and `confirm_org_wide=true` are present in the request. Standard activation requires an explicit `brand_id`.
- **FR-015**: `DELETE /plugins/{id}/activate?brand_id=X` MUST also demote any org-wide (`brand_id=null`) active rows for that plugin to inactive, preventing org-wide rows from bleeding across brands after brand-scoped deactivation.
- **FR-016**: `GET /plugins` MUST NOT create `plugin_activations` rows as a side effect. Missing activation rows MUST be synthesized as `installed/inactive` in the response only — never written to the DB.
- **FR-017**: `GET /plugins?brand_id=X` MUST filter `connected_social_platforms` and `credentials_configured` to the specified brand's social connections. Workspace-wide credential checks are not acceptable when a brand scope is provided.
- **FR-018**: Any capability in `api/capabilities/` that requires direct imports of BOS internals (`db`, `models`, `executor`, `config`, `routers`) is a core service, not a package. It MUST live in a dedicated core module (e.g. `api/council.py`). The capability module in `api/capabilities/` MUST delegate via the execute interface — not via direct internal import.
- **FR-019**: `GET /api/capability-manifest?brand_id=` endpoint MUST exist and return the brand-filtered capability list so operators and agents can inspect what the CMO can dispatch for a given brand without triggering a chat turn.

---

## Success Criteria

- **SC-001**: Empty external plugin root produces zero plugin capabilities and no startup crash.
- **SC-002**: Uninstalled platforms do not appear in Specialists UI, CMO manifest, connector warnings, or readiness debt.
- **SC-003**: Installed but inactive plugins appear in Admin only and are not RUN-able.
- **SC-004**: Active Brand-scoped plugins appear in the CMO manifest for that Brand only.
- **SC-005**: One broken plugin does not prevent valid plugins from loading.
- **SC-006**: A standard plugin-declared OAuth2 connection works without adding a platform-specific core handler.
- **SC-007**: Existing core/platform-specific behavior is not expanded while implementing this MVP.
- **SC-008**: Adding a new plugin changes external plugin resources and activation state only; it does not require a new platform branch in core.
- **SC-009**: Built-in packages (`api/capabilities/`) and installed packages (`~/bos-plugins/`) are indistinguishable at dispatch time — same contract, same brief assembly path, no BOS internal imports in either.
- **SC-010**: `GET /plugins` returns the same response shape for bundled (compat flag) and external plugins, with a `source` field distinguishing `external` vs `internal_compat`. Operators can identify which plugins come from `~/bos-plugins/` vs the compat flag.
- **SC-011**: Org-wide activation rows (`brand_id=null`) are visible in the API response with a `scope` field distinguishing `org_wide` vs `brand_scoped`, enabling operators to audit and correct scope leaks.

---

## Deployment Assumptions

- Local BOS core remains in `~/bos`.
- Third-party/plugin work happens in `~/bos-plugins`.
- Docker mounts `~/bos-plugins` into the API container as `/external_plugins`.
- Production uses the same model: a separately managed plugin root mounted into BOS.
- `api/plugins/` remains in the repo as SDK examples / deprecated bundled source, not runtime source.
- Existing code may already contain partial or buggy attempts. This spec is the correction source of truth.

---

## Architecture Tests

Before merge, answer yes/no:

```text
Does this make a platform visible before its plugin is installed?
Does this add platform-specific behavior to core?
Does this require a core edit to install/remove a plugin?
Does this show connector setup warnings for uninstalled plugins?
Does this put inactive plugin capabilities in the CMO manifest?
Does this treat api/plugins/ source folders as runtime-installed plugins?
Does this add workflow opinion to core that could instead live in a plugin or loaded resource?
Does this add a permanent chat-router branch for plugin-specific behavior?
Does this add a new primitive beyond load / resolve / inject / dispatch / persist without a constitutional decision?
Does this treat api/capabilities/ entries as core code with special privileges, or allow them to import BOS internals?
Did this build before producing and agreeing on a sample output?
Did this confuse capability artifacts with tool execution artifacts?
Did this ban artifacts when the actual problem was unrequested execution?
```

Any `yes` means the implementation violates this spec. Source of truth for these questions: BITE.md → Architecture Violation Test.
