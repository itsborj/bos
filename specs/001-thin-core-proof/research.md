# Research: Plugin Host MVP — WordPress / VS Code / pi.dev Model

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08

---

## Governing Reference

This research has been narrowed to match:

```text
api/plugins/PLUGIN_ARCHITECTURE_RECOMMENDATION.md
```

The earlier broad thin-core/hook/chat-rewrite research is deferred. This feature implements only the plugin-host MVP primitives.

---

## Decision 1: WordPress / VS Code / pi.dev Architecture Model

**Decision**: BOS combines three architecture references:

```text
WordPress  → install/activate/deactivate lifecycle
VS Code    → extension host + enabled contribution points
pi.dev     → thin core + loaded resources + live manifest
```

BOS follows the lifecycle:

```text
external install root → installed/quarantined → activate per Brand → CMO manifest
```

**Rationale**: WordPress does not expose plugin capabilities until a plugin is installed and activated. VS Code does not expose extension commands until the extension is installed/enabled. pi.dev keeps the core harness thin by loading resources instead of adding permanent branches. BOS should behave the same way.

**Rejected alternative**: Hardcoded platform catalog in core/UI, or a growing CMO/router core that absorbs plugin behavior.

---

## Decision 2: External Root Is Runtime Source

**Decision**: Runtime plugins come from `/external_plugins`, mounted from `~/bos-plugins`.

`api/plugins/` is SDK/example/deprecated source and is not runtime-loaded by default.

**Rationale**: Third-party plugin development must be isolated from the core repo.

**Compatibility**: `KLAROHA_LOAD_INTERNAL_PLUGINS=true` may enable bundled examples for local compatibility only.

---

## Decision 3: MVP Installed State Is Lean

**Decision**: MVP installed state is:

```text
external-root scan
+ manifest validation/quarantine status
+ per-brand activation DB
```

Do not build a full registry/lockfile with hashes in this feature.

**Rationale**: The immediate bug is fake/uninstalled capabilities appearing. Full release integrity is useful later but not required for the MVP.

---

## Decision 4: Activation Is Brand-Scoped

**Decision**: Installed plugins are inactive by default. Activation is explicit and Brand-scoped, with optional org-level default via `brand_id=NULL`.

**Rationale**: A plugin installed for review must not affect production Brands until activated.

---

## Decision 5: CMO Manifest Filters by Activation

**Decision**: The CMO manifest includes plugin capabilities only when the plugin is installed, active for the current Brand, not quarantined, and the SKILL is `allowed_from_chat`.

**Rationale**: The CMO should see active extension contracts, not theoretical platforms.

**Credential note**: Missing credentials are handled by the plugin at execution time via a setup-blocker artifact. Core does not add platform-specific credential gates to chat.

---

## Decision 6: Specialists UI Is Installed-Only

**Decision**: Admin Specialists renders installed plugin cards from `GET /plugins`; it does not hardcode cards for uninstalled platforms.

**Rationale**: A platform card before installation is a fake capability and creates readiness noise.

---

## Decision 7: Generic Credentials and Lean OAuth

**Decision**: Plugins receive credentials through `brief["_channel_credentials"]` only. Core supports lean generic OAuth2 declarations for common providers; unusual providers may use `requires_platform_vars` in MVP.

**Rationale**: Core should be plugin-ready, not platform-ready.

---

## Decision 8: No Module Concept — Everything is a Package

**Decision**: BOS retires the "module" concept. All capabilities are packages. Built-in packages (`api/capabilities/`) and installed packages (`~/bos-plugins/`) follow an identical contract: `SKILL.md` + `module.py` + `channel.json`. No package imports BOS internals. The only distinction between built-in and installed is source location and default activation state.

**Rationale**: WordPress does not have a privileged plugin API for Automattic-authored plugins — Akismet uses the same `add_action`/`add_filter` hook API as any third-party plugin, ships in the install archive, and can be deactivated. VS Code's built-in TypeScript extension lives in `app/extensions/`, uses the same `package.json` + extension API as any third-party extension, and can be disabled. pi.dev keeps the harness thin by treating all capabilities as loaded resources — no hardcoded skill logic in the runner. BOS adopts the same model: the loader discovers packages from `api/capabilities/` (built-in, auto-activated) and `~/bos-plugins/` (installed, activation required); the package contract is uniform.

Retiring "module" eliminates an implicit first-party trust tier that allowed direct DB/model access in capability code. The `resolve` primitive becomes the single context-assembly path; packages become stateless transforms.

**Constitutional reference**: BITE.md § Everything is a Package; PLUGIN_ARCHITECTURE_RECOMMENDATION.md § No Module Concept.

---

## Decision 9: Violations Audit — Active pi.dev Model Violations

**Date**: 2026-06-09
**Status**: All V1–V9 resolved ✓

Code audit against spec.md § Architecture Tests found nine active violations. Resolution status below.

| # | File | Violation | Rule | Resolution |
|---|------|-----------|------|------------|
| V1 | `plugin_loader.py:503–586` | Three platform-specific branches in `inject_channel_credentials`: `google_drive` root folder extraction, ClickUp `pm_config`/`clickup_team_id` injection, image/video modality string-matching on `module_id` | FR-012, D7 | **✓ T061** — replaced with 7-type `credential_slots` resolver loop; zero platform-specific branches remain |
| V2 | `routers/plugins.py:50–119` | `_MEDIA_PROVIDER_OPTIONS` hardcodes provider catalogs for `media.image` and `media.video` in core router | FR-012, SC-008 | **✓ T090** — `provider_options` array added to channel.json; plugins.py reads from manifest |
| V3 | `routers/plugins.py:295–318` | `_WORKSPACE_RESOLVERS` + `/resolve-workspaces` endpoint makes ClickUp-specific HTTP calls from core | FR-012, SC-008 | **✓ T091** — `workspace_discovery_url` in clickup channel.json; generic handler reads from manifest |
| V4 | `routers/chat.py:555–563` | `_CHANNEL_DISPLAY` hardcodes display names for specific platform keys in core | FR-011, FR-012 | **✓ T096** — `_CHANNEL_DISPLAY` removed; `_platform_display_name()` derives from string transformation |
| V5 | `routers/chat.py:1209` | `@council` dispatches via direct import of capability module, bypassing manifest contract entirely | CMO Rule #1, FR-011 | **✓ T093** — `chat.py` imports from `api/council.py` core service directly; capability SKILL.md set `allowed_from_chat: false` |
| V6 | `capabilities/workspace/council/module.py:27–28,340` | Imports `config`, `executor`, `models.council` — BOS internals from a package file | FR-013, SC-009 | **✓ T093** — `module.py` is a clean execute() stub; all logic in `api/council.py` core service |
| V7 | `AdminModules.tsx:171–197` | `pluginDisplayName`/`pluginDescription` pattern-match on `plugin_id` string instead of reading from manifest | D6, FR-012 | **✓ T094** — functions deleted; call sites use `plugin.name` and `plugin.implements.join(', ')` directly |
| V8 | `AdminModules.tsx:6–13` | `OAUTH_PLATFORMS` hardcodes icons/labels for specific OAuth platforms | FR-012 | **✓ T095** — `OAUTH_PLATFORMS` deleted; replaced by `buildPlatformMeta()` derived from plugin connection manifests |
| V9 | `plugins/PLUGIN_SDK.md:559–585` | SDK docs show `from registry import ...` and `from skills.loader import ...` — teaches BOS internal imports to plugin devs | FR-013 | **✓ T064** — SDK docs updated; "Plugin modules must never import BOS internals" added as hard rule |

**V1 is the most architecturally significant.** `inject_channel_credentials` has grown platform-specific branches for `google_drive`, ClickUp, and image/video modality. This is the exact accumulation pattern the pi.dev model prohibits. The root cause is that the credential injection contract has no way for a plugin to declaratively describe *what* it needs resolved — so core absorbs each new requirement as a branch. Remediation is an open architectural question documented in Decision 10.

**V6 creates a constitutional conflict.** `workspace/council` is classified as a BOS system contract (equivalent to WordPress core infrastructure), but it lives in `api/capabilities/` as a package and imports BOS internals, violating FR-013. Resolution options: (a) move it to `api/council.py` as an explicit core service and call it from `chat.py` directly — system contracts belong in core, not in the package tree; (b) document a privileged system-contract tier with explicit import permissions and hard-fence it from third-party capabilities. Option (a) is preferred — if it needs direct DB/executor access it is core, not a package.

---

## Decision 10: Credential Injection Architecture — Open Question

**Date**: 2026-06-09
**Status**: Under research — see separate discussion

The violations in V1 are symptoms of a deeper architectural mismatch. The WordPress / VS Code analogy was used to model the **plugin lifecycle** (install → activate → manifest), but it is the wrong reference for **credential injection**.

WordPress plugins call `get_option()` themselves. VS Code extensions call `context.secrets.get()` themselves. Neither model has the host injecting platform-specific structured credentials into plugin calls. In both, the plugin owns its credential retrieval.

BOS's current model inverts this: core assembles and injects credentials, which forces core to understand each platform's shape (`drive_root_folder_id`, `clickup_team_id`, `image_gen_provider`). Every new plugin requirement adds a branch.

The two candidate reference models for a correct credential contract are:

```text
MCP         → transport-level auth; server owns its credential retrieval;
              host knows nothing about server-internal credential shapes

SKILL.md    → declarative slot contract; harness resolves each slot by type
  (pi.dev)    generically; no platform names in harness code
```

**Resolved decisions:**

- `credential_slots` **supersedes** `requires_social_connection` and `requires_platform_vars`. Both old fields are removed from `ChannelPluginManifest`. No coexistence, no migration shim.
- Modules receive a **raw dict** — `brief["_channel_credentials"]`. Keys are guaranteed to match what the plugin declared in `credential_slots`. No typed SDK wrapper in MVP.

**Slot vocabulary — seven types, covers all current V1 violations and all known org-channel use cases:**

| type | resolves |
|------|----------|
| `social_token` | Full `SocialConnection(brand_id, platform)` — injects `access_token`, `page_token`, `page_id`, `page_name`, `page_handle` as a collapsed set. One slot per OAuth platform. |
| `social_meta_field` | `SocialConnection.token_meta_json[field]` — for platform-specific metadata stored at connect time (e.g. `drive_root_folder_id`) |
| `platform_var` | Env var, then DB-stored plugin var as fallback |
| `brand_json_path` | `brand.brand_json` at a dotted path (e.g. `pm_config.team_id`) |
| `backend_override_provider` | `BackendOverride(module_id).provider`, fallback to `fallback_var` env var |
| `backend_override_model` | `BackendOverride(module_id).model_id` |
| `backend_provider_api_key` | API key from `provider_keys` for the resolved provider — second-pass slot, depends on `backend_override_provider` resolving first |

**Representative samples (agreed shapes — implement exactly these):**

`google.drive/channel.json`:
```json
"credential_slots": [
  { "key": "access_token",         "type": "social_token",            "platform": "google_drive" },
  { "key": "drive_root_folder_id", "type": "social_meta_field",       "platform": "google_drive", "field": "drive_root_folder_id" },
  { "key": "drive_root_name",      "type": "social_meta_field",       "platform": "google_drive", "field": "drive_root_name" }
]
```

`channel.clickup/channel.json`:
```json
"credential_slots": [
  { "key": "clickup_api_token", "type": "platform_var",    "var": "CLICKUP_API_TOKEN" },
  { "key": "clickup_team_id",   "type": "brand_json_path", "path": "pm_config.team_id" },
  { "key": "pm_list_id",        "type": "brand_json_path", "path": "pm_config.list_id" }
]
```

`media.image/channel.json`:
```json
"credential_slots": [
  { "key": "image_gen_provider", "type": "backend_override_provider", "module": "media.image.generate", "fallback_var": "IMAGE_GEN_PROVIDER" },
  { "key": "image_gen_model",    "type": "backend_override_model",    "module": "media.image.generate" },
  { "key": "provider_api_key",   "type": "backend_provider_api_key",  "module": "media.image.generate" }
]
```

Core resolver loop replaces `inject_channel_credentials` entirely. No platform names, no module-id string-matching in core. An org's custom plugin uses `platform_var` and `brand_json_path` with zero Klaroha code change.

---

## Decision 11: Plugin Lifecycle Gap — Agreed Resolution

**Date**: 2026-06-09
**Status**: Resolved — deliverables agreed, parked items documented

Joint analysis between agents after YouTube/Facebook social posting work surfaced activation policy gaps and confusing Admin state. Full analysis: `api/plugins/PLUGIN_LIFECYCLE_GAPS.md`.

**Root causes identified (four lifecycle leaks):**

1. **Visibility leak** — `KLAROHA_LOAD_INTERNAL_PLUGINS=true` makes all 18 bundled `api/plugins/` examples look installed. Should only be used locally. Production plugins must live in `~/bos-plugins/`.
2. **Read-side write leak** — `GET /plugins` auto-creates `plugin_activations` rows with `status=inactive` for every loaded plugin. These rows look operator-managed but were never explicitly created.
3. **Scope leak** — activations sent with `brand_id=null` are org-wide. Any new brand onboarded inherits them automatically.
4. **Dependency expansion leak** — activating a workflow plugin (e.g. YouTube publish) required manually activating 5 dependencies (`media.image`, `media.video`, `creative.factory`, `google.drive`, `channel.youtube`). No chain declared.

**Agreed deliverables (no code):**

| # | Deliverable | Gate |
|---|-------------|------|
| D1 | Copy 6 workflow plugins `api/plugins/` → `~/bos-plugins/` | Now |
| D2 | Remove `KLAROHA_LOAD_INTERNAL_PLUGINS=true` from `.env`, restart API | Now |
| D3 | Clear org-wide `plugin_activations` rows; recreate brand-scoped for Klaroha | Before staging deploy |

**Parked (explicitly deferred until second client brand is onboarded):**

- Stop `GET /plugins` read-side writes (auto-creating inactive rows)
- Block accidental `brand_id=null` activation at API layer
- Admin UI: org-active vs brand-active provenance badge
- Admin UI: plugin source badge (external vs internal compat)
- Dependency activation chain in Admin
- `provider_keys` credential scope (brand vs workspace isolation)

**Non-negotiable rules added to CLAUDE.md** (2026-06-09):
- Do not use `KLAROHA_LOAD_INTERNAL_PLUGINS=true` as a production or staging restore mechanism
- Do not activate with `brand_id: null` as a shortcut when only specific brands need a plugin
- Admin → Specialists must show only externally installed plugins (`~/bos-plugins/`) in normal operation

Tasks: T110–T112 in Phase 11.

---

## Deferred Decisions

The following are explicitly deferred to separate specs:

```text
chat.py 7-step rewrite
hook subscription system
full lockfile/source hash registry
marketplace UI
SDK ABI adapters
plugin-owned migrations
hot reload
subprocess sandbox
full OAuth edge-case framework
migration of Meta/TikTok/LinkedIn/YouTube/etc.
```
