# Plugin Architecture Recommendation — WordPress / VS Code / pi.dev Model

**Date:** 2026-06-08  
**Audience:** BOS core developers, plugin developers, and AI agents collaborating on plugin architecture  
**Status:** Finalized MVP architecture contract / implementation guide

---

## Executive Summary

BOS core should behave like a **thin extension host**, not a hardcoded platform catalog.

This architecture is modeled from three references:

```text
WordPress  → install/activate/deactivate lifecycle; inactive plugins do not affect runtime.
VS Code    → extension host + contribution points; commands appear only when extensions are enabled.
pi.dev     → thin core + large extension surface; capabilities are loaded resources, not core branches.
```

Core should know that plugins exist, can be installed, activated, configured, validated, and quarantined. Core should not know platform-specific products like LinkedIn, TikTok, Meta, Google Ads, or future channels before those plugins are installed.

The WordPress / VS Code / pi.dev rule:

```text
If a plugin is not installed and activated, BOS should act like it does not exist.
```

That means no CMO manifest entry, no Specialist card, no connector warning, no readiness debt, and no RUN-able capability for uninstalled plugins.

---

## Problem

Current architecture has been drifting toward this anti-pattern:

```text
Core knows a platform before the plugin is installed.
Core UI shows possible platforms as if they are available specialists.
Core must be updated before a third-party plugin can become fully operational.
```

Example failure mode:

```text
LinkedIn plugin cannot be fully operational unless core first learns LinkedIn OAuth/setup behavior.
```

That is not a plugin architecture. That is a platform-specific core integration model.

Correct diagnosis:

```text
Core is missing generic extension-host infrastructure.
```

Incorrect diagnosis:

```text
Core needs a LinkedIn integration.
```

---

## Target Mental Model

### WordPress

WordPress core does not show WooCommerce products, settings, or blocks until WooCommerce is installed and activated.

### VS Code

VS Code does not show an extension command until the extension is installed/enabled and its activation conditions are met.

### pi.dev

pi.dev stays thin by treating agent behaviors, prompts, skills, tools, and subagents as loaded resources rather than permanent core branches. The harness stays small; extension packages provide most workflow opinion.

BOS should adopt the same pattern:

```text
Core loop stays thin.
Capabilities are loaded resources.
The live manifest tells the CMO what is actually available.
Adding/removing a plugin changes loaded resources, not core code.
```

### BOS

BOS should not show LinkedIn, TikTok, Meta, Google Ads, or any channel capability unless that plugin is installed and active for the relevant Brand. BOS core should remain a thin host that loads manifests, validates safety, dispatches transforms, persists artifacts, and returns results.

---

## No Module Concept — Everything is a Package

BOS does not distinguish between modules (first-party capabilities) and plugins (external extensions). The concept of "module" is retired.

Everything is a package. The package contract is identical regardless of who wrote it or where it ships from.

```text
Built-in packages    api/capabilities/   ship with BOS; auto-activated org-wide; can be deactivated per brand
Installed packages   ~/bos-plugins/      operator-installed; inactive until explicitly activated per brand
```

**WordPress:** Akismet ships inside the WordPress install archive as a regular plugin — same plugin header comment, same hook API (`add_action`, `add_filter`) as any third-party plugin. WordPress core does not have a separate, more powerful API for Automattic plugins. The loader discovers packages; the package contract is uniform.

**VS Code:** TypeScript language support ships in `app/extensions/` as a standard extension package — same `package.json` with `contributes` and `activationEvents`, same VS Code extension API as any third-party extension. You can disable it from the Extensions panel. The extension host does not treat it differently at runtime.

**pi.dev:** The harness does not hardcode any skill or tool. Everything the agent can do is a loaded resource (SKILL.md, tool config, subagent spec). The harness stays minimal; loaded packages provide all workflow opinion. BOS adopts the same discipline.

BOS applies the same model:

```text
Core (host primitives only)
  load → resolve → inject → dispatch → persist

Built-in packages (api/capabilities/ — ship with BOS)
  System tier:    workspace/*, onboarding/*               auto-activated; BOS operating contract
  Marketing tier: marketing/*, reasoning/*, copywriting/*  auto-activated; workflow capabilities

Installed packages (~/bos-plugins/ — operator-installed)
  Media/Creative: media.image, media.video, creative.factory
  Channels:       gmail, meta, youtube, tiktok, linkedin, google_ads, search_console
  Infrastructure: google.drive, google_calendar, clickup
```

All packages — built-in and installed — follow the same contract:

```text
SKILL.md        operating/activation contract
module.py       Transform node (capability code)
channel.json    package identity, capabilities, connections, risk policy
template.j2     prompt/tool template (optional)
```

No package imports BOS internals. The `resolve` primitive assembles everything into the brief before dispatch. Packages are stateless transforms: receive a brief, return a result.

---

## Core Responsibilities

Core owns generic thin-host infrastructure only:

1. External plugin install root
2. Installed plugin state (MVP: external-root scan + quarantine status + activation DB; later: registry / lockfile)
3. Manifest parsing and validation
4. SDK / schema compatibility checks
5. Per-brand activation state
6. Generic credential and connection declarations
7. Generic credential injection into `brief["_channel_credentials"]`
8. Generic validation/readiness status
9. Capability manifest filtering
10. Failure quarantine
11. Admin UI surfaces for installed plugins and optional marketplace discovery

Core must not own:

1. Platform-specific OAuth behavior for every new plugin
2. Channel-specific UI cards before plugin installation
3. Hardcoded connector setup prompts for uninstalled plugins
4. Hardcoded capability IDs for plugin capabilities
5. Platform-specific routing or readiness branches in CMO chat
6. Plugin-specific prompt or artifact behavior
7. Workflow opinion that can live in a plugin/package/resource
8. Permanent chat-router branches for plugin behavior

---

## Plugin Responsibilities

A plugin owns its package and declares its behavior:

```text
channel.json
SKILL.md
module.py
template.j2
connection declarations
validation capability
output contracts
risk policy
```

A plugin may declare:

- capabilities
- CMO-facing jobs implemented
- required platform vars
- OAuth/API connection declarations
- validation capability
- output contracts
- risk and approval policy
- hook subscriptions, once hooks exist

A plugin must not import BOS internals such as:

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

## Plugin Lifecycle State Model

MVP lifecycle — three states:

```text
Installed
  ↓ activate per Brand (explicit, in Admin)
Active
  ↓ included in CMO manifest
Dispatchable
```

Configured and Validated are **Specialists UI status indicators**, not manifest gates. This matches the WordPress/VS Code model: activating a plugin makes it visible and its capabilities registered immediately. The plugin surfaces its own missing-config state — core does not hide it.

WordPress: Activating WooCommerce registers its capabilities immediately. WooCommerce shows its own setup notice. Core does not gate it.

VS Code: Installing an extension makes its commands available in the palette. The extension handles its own missing-config prompt.

BOS: Activating a plugin includes it in the CMO manifest. If credentials are missing, the plugin returns a `setup_blocker` artifact. Core does not hide active plugins.

### 1. Installed

Plugin package exists in the external install root, its manifest validates or quarantines cleanly, and its installed/quarantine status is visible in Admin.

MVP definition: external-root scan + quarantine status. Full registry/lockfile with source hashes is deferred.

Visible in:

```text
Admin → Specialists / Installed
```

Not dispatchable until activated.

### 2. Active

Plugin is active for a specific Brand.

Activation is explicit and per-brand. Installed does not mean active.

Once active: capabilities included in CMO manifest for this Brand.

### 3. Dispatchable

Plugin capabilities appear in the CMO manifest.

Condition:

```text
installed
+ active for brand
+ not quarantined
+ SKILL.md allowed_from_chat=true
```

If credentials are missing at execution time, the plugin returns a `setup_blocker` artifact. Core does not pre-filter on credential state — the plugin owns that.

For external write/publish actions, also require approval policy.

---

### Configured and Validated — Specialists UI status indicators only

These are not manifest gates. They are readiness display states visible in Admin / Specialists:

```text
Active but unconfigured  → Specialist card shows: configure credentials
Configured, not validated → Specialist card shows: run connection check
Validated                → Specialist card shows: ready
```

Configured and Validated inform the operator. They do not block CMO dispatch.

A plugin that needs credentials declares a `validate_capability`. The operator runs it from Admin. The result is stored and displayed in the Specialist card. The plugin blocks its own execution when credentials are absent — via `setup_blocker`, not via manifest exclusion.

---

## Installed Plugin Root

Runtime plugin source should be external to core:

```text
~/bos-plugins/
/external_plugins/
```

Core source examples under:

```text
api/plugins/
```

are not runtime-installed plugins by default.

They are:

- SDK examples
- deprecated bundled packages
- local compatibility fixtures

They should load only with an explicit local/dev flag such as:

```bash
KLAROHA_LOAD_INTERNAL_PLUGINS=true
```

If no external plugins are installed, a restart should produce:

```text
0 plugin capabilities
```

---

## Admin UX Recommendation

Split plugin UX into two surfaces.

### Specialists / Installed

Shows installed plugins only.

For each plugin:

```text
Name
Version
Source
Installed status
Activation status per Brand
Credential status
Connection status
Validation status
Capabilities contributed
Risk policy
Configure
Validate
Activate / Deactivate
Uninstall
```

If LinkedIn is not installed, there is no LinkedIn Specialist card.

### Marketplace / Available

Optional catalog of installable packages.

Shows:

```text
Plugin name
Description
Publisher
Version
Permissions
Risk policy
Install button
Docs
```

Marketplace packages are not capabilities.

They must not appear in:

- CMO manifest
- Specialist readiness debt
- connector warnings
- RUN suggestions
- approval actions

---

## CMO Manifest Rule

The CMO manifest must be generated from runtime-active capabilities only.

Do not include:

- available marketplace packages
- bundled SDK examples
- uninstalled plugins
- installed but inactive plugins
- quarantined plugins
- incompatible plugins
- retired capabilities

The CMO should only see what can actually be used for the active Brand.

---

## Readiness Rule

Readiness is a property of installed/active plugins, not theoretical integrations.

Bad UX:

```text
TikTok needs setup
LinkedIn needs setup
Meta needs setup
```

when those plugins are not installed.

Correct UX:

```text
No TikTok card unless TikTok plugin is installed.
No LinkedIn card unless LinkedIn plugin is installed.
No Meta card unless Meta plugin is installed.
```

If installed but inactive:

```text
LinkedIn Specialist installed — activate for this Brand
```

If active but unconfigured:

```text
LinkedIn Specialist active — configure OAuth credentials
```

If configured but not validated:

```text
LinkedIn Specialist configured — run connection check
```

If validated:

```text
LinkedIn Specialist ready
```

---

## Generic Connection Model

Core should support plugin-declared connections generically.

Core does not need to know LinkedIn, TikTok, or future platforms.

A plugin declares:

```json
{
  "connections": [
    {
      "platform": "example_platform",
      "type": "oauth2",
      "auth_url": "https://example.com/oauth/authorize",
      "token_url": "https://example.com/oauth/token",
      "scopes": ["profile", "content.write"],
      "client_id_var": "EXAMPLE_CLIENT_ID",
      "client_secret_var": "EXAMPLE_CLIENT_SECRET",
      "redirect_uri_var": "EXAMPLE_REDIRECT_URI",
      "userinfo_url": "https://example.com/me",
      "id_path": "id",
      "name_path": "name",
      "validate_capability": "marketing.channel.example.connection.validate"
    }
  ],
  "requires_social_connection": ["example_platform"]
}
```

Core performs protocol mechanics:

1. start OAuth
2. handle callback
3. store encrypted token
4. inject credentials into brief

Plugin performs platform semantics:

1. validate token
2. call platform API
3. return connection status
4. block downstream actions when missing/invalid

---

## Failure Quarantine

One bad plugin must not crash BOS or hide unrelated capabilities.

Invalid plugins should appear as structured system/admin status:

```json
{
  "plugin_id": "channel.example",
  "installed": true,
  "active": false,
  "status": "error",
  "reason": "invalid channel.json / incompatible sdk_range / duplicate module_id / import failed"
}
```

The CMO manifest should continue serving valid active capabilities.

---

## Thin-Core Principle from pi.dev

WordPress and VS Code define the install/activation lifecycle. pi.dev defines the core-size discipline.

The pi.dev lesson for BOS:

```text
Do not let the host become the product catalog.
Do not let one more plugin become one more branch in core.
Do not let the CMO prompt become stale hand-written capability documentation.
Load resources; generate the live manifest; dispatch through stable contracts.
```

For this MVP, that means:

```text
plugin_loader.py discovers installed packages
capability_manifest.py reflects active resources
chat.py reads the manifest but does not know platform names
runs.py executes by stable module contract
plugins own platform semantics
```

This MVP does not require the full pi-style hook system yet. The immediate thin-core primitive is lifecycle + manifest correctness: uninstalled/inactive plugins must not be visible, and installed/active plugins must not require core branches.

---

## Alignment and Pushbacks

### Alignment

We align on these decisions:

1. **Core must be plugin-ready, not platform-ready.** Core should not need a LinkedIn/TikTok/etc. update before a third-party plugin can install and declare itself.
2. **Uninstalled means invisible.** No Specialist card, CMO manifest entry, connector prompt, or readiness warning exists for a plugin that is not installed.
3. **Installed does not mean active.** Installation is package presence and validation; activation is explicit and Brand-scoped.
4. **Admin owns setup.** Configuration, connection, and validation status belong in Admin / Specialists, not normal CMO dispatch.
5. **CMO sees active extension contracts, not theoretical platforms.** The CMO manifest should reflect active, non-quarantined plugin capabilities for the current Brand. Missing credentials are handled by the plugin with a `setup_blocker` artifact, matching WordPress/VS Code setup-notice behavior.
6. **Plugin authors own platform semantics.** Core handles generic protocol mechanics and credential injection; plugins validate and use their platform.
7. **Core stays thin like pi.dev.** If behavior can be a loaded package/resource, it should not become a permanent core branch.

### Pushbacks / guardrails

These are intentional constraints to keep the work lean:

1. **Do not build a marketplace now.** The optional Marketplace / Available surface is a later discovery layer. MVP only needs Installed Plugins.
2. **Do not build a full lockfile now.** MVP installed state is external-root scan + quarantine status + activation DB. Source hashes, manifest hashes, and release-integrity ledgers are deferred.
3. **Do not hide active plugins from the CMO manifest because credentials are missing.** Active = in manifest. The plugin returns a `setup_blocker` artifact when credentials are absent. Core does not pre-filter on credential state — that is the WordPress/VS Code model.
4. **Do not implement every OAuth edge case.** MVP generic OAuth supports common OAuth2. Odd providers can start with `requires_platform_vars` until a real need proves a generic extension is necessary.
5. **Do not build hooks, SDK adapters, migrations, hot reload, or subprocess sandbox in this pass.** They are valid architecture later, but they are not required to stop fake capabilities and platform-specific core preparation. Defer hooks without rejecting the pi.dev model: this MVP builds the lifecycle/manifest foundation that hooks will later attach to.
6. **Do not migrate/fix Meta, TikTok, LinkedIn, or other plugins before the primitives are in place.** Otherwise every plugin fix risks becoming another core-specific workaround.

---

## Lean Deliverables

Do not start by fixing individual platform plugins. First fix the core/plugin host boundary with the smallest set of primitives that prevents fake capabilities and platform-specific core preparation.

### Previously attempted — must verify before relying on it

Some of these primitives may already have partial code changes. Treat current code as suspect until each acceptance check passes. Do not infer architecture from the current implementation if it conflicts with this document.

#### D1 — External plugin root is runtime source

`EXTERNAL_PLUGINS_DIR` + `KLAROHA_LOAD_INTERNAL_PLUGINS` flag live in `plugin_loader.py`.

Acceptance:

```text
Empty /external_plugins → zero plugin capabilities after restart.
```

#### D2 — Installed plugins API returns installed packages only

`GET /plugins` should return installed packages from the external-root scan only.

Minimum acceptance fields:

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

Acceptance:

```text
No external LinkedIn plugin → no LinkedIn entry in GET /plugins response.
Bundled api/plugins examples do not appear unless KLAROHA_LOAD_INTERNAL_PLUGINS=true.
```

#### D3 — Basic quarantine

Scanner/import failures are isolated per plugin. BOS continues.

Lean MVP quarantine rule:

```text
If plugin_id can be read → return plugin with status=error and reason.
If plugin_id cannot be read → report path-level error in diagnostics/logs; do not crash.
```

Acceptance:

```text
One broken plugin does not crash startup.
Valid plugins still load.
Broken plugin is visible as status=error when plugin_id is recoverable.
```

#### D7 — Generic credential injection is the only plugin credential path

`inject_channel_credentials()` is the single injection path. Plugins read only from `brief["_channel_credentials"]`.

Acceptance:

```text
Plugin module.py imports only from klaroha_sdk at module level.
```

#### D8 — Generic plugin-declared OAuth

Generic OAuth2 support should handle start, callback, token storage, and credential injection for any plugin-declared OAuth2 connection without platform-specific core code.

Acceptance:

```text
A plugin-declared OAuth platform can start auth, complete callback, store token, and receive injected credentials without adding a platform-specific core handler.
If the provider needs non-standard OAuth, plugin can use requires_platform_vars for MVP.
```

---

### Remaining build — D4, D5, and D6

#### D4 — Per-brand activation (build)

The `plugin_activations` table exists (migration 038). The ORM model, read path, and API endpoint do not.

Build:

```text
api/models/plugin_activation.py   — PluginActivation ORM model
plugin_loader.py                  — read activation state on scan; directory present + no row → auto-insert inactive
POST /plugins/{id}/activate        — brand_id optional (null = org-wide)
DELETE /plugins/{id}/activate      — deactivate
```

Precedence rule:

```text
Directory present + no activation row → installed, inactive (auto-create row)
Activation row + no directory        → stale; treat as uninstalled; log warning; never inject
```

Acceptance:

```text
Installed but inactive plugin appears in GET /plugins but not in CMO manifest.
```

#### D5 — CMO manifest filtered by brand activation (build)

`capability_manifest.py` currently generates a global manifest. Add `brand_id` parameter and filter by activation state.

```text
capability_manifest.generate(brand_id)
  → LEFT JOIN plugin_activations on (plugin_id, brand_id COALESCE org-row)
  → filter status='active'
  → filter not quarantined
  → filter allowed_from_chat=true
```

This is the single filter point. No second gate in `chat.py`.

Active plugin with missing credentials returns a `setup_blocker` artifact at execution time. Core does not pre-filter on credential state.

Acceptance:

```text
Inactive plugin module_id cannot be RUN from CMO chat.
Active plugin with missing credentials returns setup_blocker artifact, not a manifest exclusion.
```

---

#### D6 — Specialists UI activation (build/patch)

Specialists UI must be a view over installed plugin manifests, not a hardcoded platform catalog.

Build/patch:

```text
Remove hardcoded uninstalled platform cards.
Render installed plugin cards from GET /plugins.
Show activation state per Brand.
Add Activate/Deactivate toggle per Brand per installed plugin, calling D4 endpoints.
Show setup/validation status only for installed plugins.
```

Acceptance:

```text
No TikTok plugin installed → no TikTok Specialist card.
No LinkedIn plugin installed → no LinkedIn Specialist card.
Active/inactive toggle visible per Brand per installed plugin.
Uninstalled platforms create no connector warnings or readiness debt.
```

### Explicitly deferred

These are valid later, but should not block the MVP.

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
```

### Plugin migration order after MVP primitives

After D1–D8, fix existing plugins one at a time:

1. Meta
2. TikTok
3. LinkedIn
4. YouTube
5. Google Drive-dependent creative/media plugins
6. Remaining env-var plugins

---

## Implementation Guardrails Added in MVP Patch

The current MVP patch enforces the architecture contract with these concrete guardrails:

1. **Installed defaults to inactive.** A present plugin directory with no activation row is persisted as `inactive`; deactivation writes `inactive` instead of deleting the row, so Brand-specific inactive can override org-level active.
2. **Runtime ownership is registered from imported modules.** Plugin module ownership is recorded for every imported plugin `ModuleBase`, even when a plugin forgot to list a module in `channel.json.capability_ids`. This prevents undeclared plugin modules from bypassing activation filtering.
3. **Inactive plugin modules are not RUN-able.** Direct `/runs`, CMO dispatch, vertical module listing, generated-image helpers, Drive helpers, and PM sync helpers all check plugin activation before executing plugin-owned modules or plugin-declared platforms.
4. **Quarantine covers import and skill failures.** Duplicate plugin IDs, duplicate module IDs, module import failures, and SKILL.md parse/validation failures quarantine the plugin and keep unrelated plugins available.
5. **Specialists is installed-plugin-only.** `Admin → Specialists` renders cards from `GET /plugins`; first-party/core modules such as Marketing, Reasoning, Onboarding, or Email must not appear there unless they are installed plugins. Platform connector rows are shown only from installed plugin declarations.

If a future change reintroduces module-derived Specialist cards, unmapped plugin modules, or row-deletion deactivation semantics, it violates this contract.

---

## Architecture Tests

Before merging any plugin/core change, ask:

```text
Does this make a platform visible before its plugin is installed?
Does this add platform-specific behavior to core?
Does this require a core edit to install/remove a plugin?
Does this show connector setup warnings for uninstalled plugins?
Does this put inactive plugin capabilities in the CMO manifest?
Does this treat api/plugins/ source folders as runtime-installed plugins?
```

A yes means stop and redesign around:

```text
plugin manifest
external install root
installed registry
activation state
generic connection declaration
extension host
```

---

## One-Line Rule

```text
If a plugin is not installed and activated, BOS should act like it does not exist.
```
