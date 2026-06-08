# Tasks: Plugin Host MVP — WordPress / VS Code / pi.dev Model

**Branch**: `001-thin-core-proof` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Scope

Implement only the MVP deliverables D1–D8 from:

```text
api/plugins/PLUGIN_ARCHITECTURE_RECOMMENDATION.md
```

Do not implement marketplace, full lockfile, hooks, chat rewrite, SDK adapters, subprocess sandbox, or full plugin migration in this task set.

---

## Phase 0 — Audit Current Partial Work

- [x] T001 Audit `api/plugin_loader.py` against D1/D2/D3. Confirm external root default, internal plugin flag, installed/error state, and per-plugin quarantine behavior.
- [x] T002 Audit `api/routers/plugins.py` against D2/D4. Confirm `GET /plugins` response fields and absence of hardcoded platform catalog behavior.
- [x] T003 Audit `api/capability_manifest.py` and `api/routers/chat.py` against D5. Confirm manifest can be Brand-aware and chat does not add platform gates.
- [x] T004 Audit `web/src/pages/admin/AdminModules.tsx` against D6. Identify hardcoded cards that render when plugin is not installed.
- [x] T005 Audit generic OAuth attempt in `api/provider_auth.py` and `api/routers/social.py` against D8. Record pass/fail before patching.

---

## Phase 1 — D1 External Plugin Root

- [x] T010 Ensure `api/plugin_loader.py` loads `/external_plugins` / `EXTERNAL_PLUGINS_DIR` by default.
- [x] T011 Ensure `api/plugin_loader.py` skips bundled `api/plugins/` unless `KLAROHA_LOAD_INTERNAL_PLUGINS=true`.
- [ ] T012 Add/verify test or manual check: empty external root returns zero plugin capabilities after restart.

Acceptance:

```text
Empty /external_plugins → zero plugin capabilities.
Bundled api/plugins examples absent unless compatibility flag is enabled.
```

---

## Phase 2 — D2/D3 Installed Plugin API + Quarantine

- [x] T020 Update `api/plugin_loader.py` to preserve recoverable invalid plugins as status=`error` with reason when `plugin_id` can be read.
- [x] T021 Update `api/routers/plugins.py` `GET /plugins` response to include: `plugin_id`, `name`, `version`, `source`, `status`, `reason`, `capability_ids`, `requires_platform_vars`, `requires_social_connection`, `connections`, `activation_by_brand`.
- [x] T022 Ensure duplicate `plugin_id` / duplicate `module_id` conflicts quarantine the offending plugin and do not crash BOS.
- [ ] T023 Add/verify test or manual check: one broken plugin does not hide a valid plugin.

Acceptance:

```text
No external LinkedIn plugin → no LinkedIn in GET /plugins.
Broken recoverable plugin → status=error.
Valid plugins still load.
```

---

## Phase 3 — D4 Per-Brand Activation

- [x] T030 Create `api/models/plugin_activation.py` ORM mapping for migration 038.
- [x] T031 Export `PluginActivation` from `api/models/__init__.py` if project convention requires it.
- [x] T032 Add activation read helper in `api/plugin_loader.py` or a small plugin-host helper: `get_active_plugin_ids(db, brand_id)`.
- [x] T033 Implement precedence: Brand-specific activation overrides org-level activation.
- [x] T034 Implement stale rule: activation row + missing directory = stale/uninstalled; never manifest or inject.
- [x] T035 Add `POST /plugins/{plugin_id}/activate` in `api/routers/plugins.py`.
- [x] T036 Add `DELETE /plugins/{plugin_id}/activate` in `api/routers/plugins.py`.
- [x] T037 Ensure installed + no activation row behaves as inactive.

Acceptance:

```text
Installed inactive plugin appears in Admin but not CMO manifest.
POST activate makes it active for selected Brand.
DELETE activate makes it inactive again.
```

---

## Phase 4 — D5 CMO Manifest Activation Filter

- [x] T040 Update `api/capability_manifest.py` to accept Brand/DB context for plugin filtering.
- [x] T041 Filter plugin capabilities by active plugin IDs for the current Brand.
- [x] T042 Keep first-party non-plugin capabilities unaffected.
- [x] T043 Update `api/routers/chat.py` only as needed to pass Brand/DB context into manifest generation. Do not add platform-specific logic.
- [x] T044 Ensure inactive plugin module IDs cannot be RUN from CMO chat.

Acceptance:

```text
Brand A active plugin appears in Brand A manifest.
Brand B inactive plugin does not appear in Brand B manifest.
No platform-specific checks added to chat.py.
```

---

## Phase 5 — D6 Specialists UI Installed-Only View

- [ ] T050 Remove hardcoded platform cards from `web/src/pages/admin/AdminModules.tsx` that appear without installed plugin data.
- [x] T051 Render plugin Specialist cards from `GET /plugins` only.
- [x] T052 Display activation state per Brand for each installed plugin.
- [x] T053 Add Activate/Deactivate controls calling D4 endpoints.
- [x] T054 Show credential/setup/validation status only for installed plugins.
- [ ] T055 Ensure uninstalled platforms produce no readiness debt or connector warnings.

Acceptance:

```text
No TikTok plugin installed → no TikTok card.
No LinkedIn plugin installed → no LinkedIn card.
Installed plugin shows activation toggle per Brand.
```

---

## Phase 6 — D7 Credential Slot Contract (supersedes requires_social_connection + requires_platform_vars)

> Resolved design in research.md Decision 10. Seven slot types. `credential_slots` supersedes old fields.
> Agreed sample shapes: `google.drive`, `channel.clickup`, `media.image` — implement exactly those.

- [x] T060 Add `CredentialSlot` pydantic model to `api/plugin_loader.py`. Fields: `key`, `type`, `platform`, `field`, `var`, `path`, `module`, `fallback_var`. Remove `requires_social_connection` and `requires_platform_vars` from `ChannelPluginManifest`.
- [x] T061 Implement 7-type slot resolver loop in `inject_channel_credentials`, replacing all platform-specific branches (resolves V1). Resolver types: `social_token`, `social_meta_field`, `platform_var`, `brand_json_path`, `backend_override_provider`, `backend_override_model`, `backend_provider_api_key`. Two-pass: resolve all non-`backend_provider_api_key` slots first, then the dependent key-resolution pass.
- [x] T062 Update all 15 `channel.json` files with `credential_slots` declarations. Remove `requires_social_connection` and `requires_platform_vars` from each. Implement in order: `google.drive`, `channel.clickup`, `media.image`, `media.video`, `creative.factory`, `channel.meta`, `channel.gmail_auth`, `channel.google_calendar`, `channel.youtube`, `channel.tiktok`, `channel.google_ads`, `channel.google_analytics`, `channel.search_console`, `channel.gmail`, `channel.linkedin`.
- [x] T063 Update `required_plugin_vars()` in `plugin_loader.py` to derive required vars from `credential_slots` where `type == platform_var`. Update `GET /plugins` response: `requires_platform_vars` field becomes the derived list; `requires_social_connection` field becomes platforms referenced in `social_token` / `social_meta_field` slots.
- [x] T064 Update `api/plugins/PLUGIN_SDK.md`: document `credential_slots` vocabulary and all seven types. Remove all examples that import from `registry`, `skills.loader`, or any BOS internal. Add "Plugin modules must never import BOS internals" as a hard rule (resolves V9).

Acceptance:

```text
Plugin module.py imports only klaroha_sdk at module level.
Credentials arrive via brief["_channel_credentials"] keyed by declared slot keys.
inject_channel_credentials has zero platform-specific branches.
channel.json has no requires_social_connection or requires_platform_vars fields.
```

---

## Phase 7 — D8 Minimal Generic OAuth Verification

- [ ] T070 Verify plugin-declared `connections` schema is parsed from `channel.json`.
- [ ] T071 Verify `/social/connect/start` or equivalent can start OAuth for a plugin-declared platform without a hardcoded handler.
- [ ] T072 Verify generic callback can store `SocialConnection` for plugin-declared platform.
- [ ] T073 Verify `inject_channel_credentials()` can inject the stored token for `requires_social_connection` declared by that plugin.
- [ ] T074 If D8 is partial/broken, document the gap and keep `requires_platform_vars` as MVP fallback. Do not build full OAuth edge-case framework.

Acceptance:

```text
Standard OAuth2 plugin can connect without platform-specific core handler.
Non-standard OAuth can defer to requires_platform_vars.
```

---

## Phase 9 — Violation Remediation (V2–V8)

> Resolves the remaining violations from research.md Decision 9 that are not covered by Phase 6.
> V1 is covered by T061. V9 is covered by T064.

- [ ] T090 (V2) Add `provider_options` array to `channel.json` for `media.image` and `media.video`. Each entry: `{ "provider": "openai", "label": "OpenAI", "models": [...] }`. Remove `_MEDIA_PROVIDER_OPTIONS` dict from `api/routers/plugins.py`. Serve from `PluginInfo.media_provider_options` via the loaded manifest instead.
- [ ] T091 (V3) Add `workspace_discovery_url` string field to `ChannelPluginManifest`. Move ClickUp URL into `channel.clickup/channel.json`. Implement generic `/plugins/{plugin_id}/resolve-workspaces` handler that reads the URL from the manifest and makes the request. Remove `_WORKSPACE_RESOLVERS` dict from `api/routers/plugins.py`.
- [ ] T092 (V4) Remove `_CHANNEL_DISPLAY` dict from `api/routers/chat.py`. Build display names in `_brand_channel_readiness()` from active plugin connection manifests: read `connections[].platform` from loaded plugin state, use `display_name` from manifest or `titleCase(platform)` as fallback. No hardcoded platform names in core.
- [ ] T093 (V5 + V6) Move `workspace/council` logic out of `api/capabilities/` into `api/council.py` as an explicit core service. Update `api/capabilities/workspace/council/module.py` to delegate to `api/council.py` via the brief (not direct import). Remove direct `from capabilities.workspace.council.module import start_session` from `chat.py` — call `api/council.py` directly as a core service call, not a capability dispatch.
- [x] T094 (V7) `pluginDisplayName()` and `pluginDescription()` deleted from `AdminModules.tsx`. Call sites use `plugin.name` and `plugin.implements.join(', ')` directly.
- [x] T095 (V8) `display_name` and `icon` added to `PluginConnectionManifest` and `PluginConnectionInfo`. Added to 6 channel.json connection entries. `OAUTH_PLATFORMS` deleted from `AdminModules.tsx`; replaced by `buildPlatformMeta()` derived from plugin connection manifests.

Acceptance:

```text
_MEDIA_PROVIDER_OPTIONS and _WORKSPACE_RESOLVERS removed from core router.
_CHANNEL_DISPLAY removed from chat.py.
@council routes via council.py core service — no direct capability import in chat.py.
workspace/council module.py has no BOS internal imports.
AdminModules.tsx has no pluginDisplayName(), pluginDescription(), or OAUTH_PLATFORMS.
All display data comes from plugin manifests.
```

---

## Phase 9b — Arch Cop: Agent Work Review (2026-06-09)

> Violations found during arch-cop review of changes made by external agent (YouTube/Facebook work).
> Context: another agent made changes to activate social posting. YouTube posted successfully.
> Facebook on hold (localhost domain not registered in Meta app — not a code issue).
> These violations must be fixed before Phase 8 final validation.

### What the agent did correctly
- YouTube publish module (`video/publish/module.py`): only `klaroha_sdk` + stdlib, no BOS internals ✅
- `_chat_modules()` now async, filters by `get_active_plugin_ids(db, brand_id)` ✅
- `format_manifest_for_brand()` added to `capability_manifest.py` — brand-filtered manifest, clean ✅
- `_brand_channel_readiness()` now derives allowed platforms from active plugin manifests (no hardcoded list) ✅
- YouTube `channel.json` migrated to `credential_slots` (removed old `requires_social_connection`) ✅
- `GoogleBusinessOAuthHandler` added to `provider_auth.py` — follows existing handler pattern, not a violation ✅

### Violations to fix

- [x] T096 · VIOLATION (pre-existing T092) — `_CHANNEL_DISPLAY` removed from `chat.py`. `_platform_display_name()` added. All platform name lookups now derive from string transformation.
- [x] T097 · VIOLATION (Rule 1) — `_CONTROL_PARAM_LINE_RE` removed from `chat.py`. `_RUN_PARAMS_RE` handles indented params under RUN blocks structurally.
- [x] T098 · REGRESSION — Retired capabilities: test cleanup applied. `test_strategic_substrate_skills.py` deleted; `test_gtm_strategy_planner.py` reduced to retirement check only; `test_marketing_planning_specialist.py` module import removed; `test_cmo_action_directives.py` updated; `test_youtube_plugin_smoke.py` cleaned of `YouTubeModule` references.
- [x] T099 · CLEANUP — `api/plugins/youtube/module.py` deleted. No import references found (smoke test updated).

Acceptance:
```text
_CHANNEL_DISPLAY removed from chat.py; display names derived from plugin manifests or titleCase(platform).
_CONTROL_PARAM_LINE_RE removed from chat.py; no plugin param names hardcoded in core.
Deleted capabilities either migrated to plugins or test references cleaned up — no broken test imports.
api/plugins/youtube/module.py deleted; no remaining import references.
```

---

## Phase 10 — Plugin Credential Display Bugs (found 2026-06-09 ping test)

> Found during live ping test of Klaroha social publishing pipeline.
> All three bugs are in `api/routers/plugins.py` — the plugin status API response.
> These are display-only bugs; runtime credential resolution is unaffected.
> Fix before Phase 8 final validation so the acceptance criteria are legible.

- [x] T100 · FIX `credentials_configured` false-negative for `backend_override_*` slots. Fixed in `plugins.py`: formula now `not missing and social_configured`. Plugins with no `platform_var` slots return `True` when nothing is missing.
- [x] T101 · FIX `credentials_configured` false-negative for `social_token` slots. Fixed: preload connected social platforms at request time; `social_token_platforms & connected_social_platforms` check added.
- [x] T102 · ADD `GET /api/capability-manifest` endpoint. Added to `api/routers/plugins.py` as `capability_manifest_router`; registered in `main.py`. Returns brand-filtered capability list.

Acceptance:
```text
media.image and media.video show credentials_configured=true when execution_backend_overrides rows exist.
google.drive shows credentials_configured=true when social connection status=connected.
GET /api/capability-manifest?brand_id=<id> returns capability list for that brand.
Inactive plugin capabilities do not appear in the manifest response.
```

---

## Phase 11 — Plugin Lifecycle Fix (D1–D3, 2026-06-09)

> Agreed deliverables from `api/plugins/PLUGIN_LIFECYCLE_GAPS.md`. No code changes required.
> D1 and D2 fix Admin noise immediately. D3 is the staging gate — must complete before any staging deploy.
> Full analysis: `api/plugins/PLUGIN_LIFECYCLE_GAPS.md § Agreed deliverables`.

- [ ] T110 · D1 (operator): Copy 6 workflow plugins from `api/plugins/` → `~/bos-plugins/`: `youtube`, `meta`, `media-image`, `media-video`, `creative-factory`, `google-drive`. Commands in `PLUGIN_LIFECYCLE_GAPS.md § Phase 0 — Containment`. After copy, Admin should show only externally installed plugins.
- [ ] T111 · D2 (operator): Remove `KLAROHA_LOAD_INTERNAL_PLUGINS=true` from `.env`. Run `docker compose up -d api`. Confirm Admin → Specialists shows ≤8 plugin cards (external installs only).
- [ ] T112 · D3 (staging gate): Clear 6 org-wide `plugin_activations` rows (`brand_id=null`, `status=active`). Recreate brand-scoped for Klaroha brand `c1cb6603-e8d4-4e63-8995-640453d5b50b` via `POST /api/plugins/{id}/activate`. Affected plugin IDs: `media.image`, `media.video`, `creative.factory`, `channel.meta`, `google.drive`, `channel.youtube`. SQL to verify: `SELECT plugin_id, brand_id, status FROM plugin_activations WHERE status = 'active' AND brand_id IS NULL`.

Acceptance:
```text
Admin shows only plugins from ~/bos-plugins/ (no bundled api/plugins/ examples).
No org-wide active rows (brand_id=null) remain in plugin_activations.
All 6 social workflow plugins are active for Klaroha brand specifically.
A second Brand created on staging sees no plugins active unless explicitly activated for it.
```

---

## Phase 8 — Final Validation

- [ ] T080 Run `specs/001-thin-core-proof/quickstart.md` V1–V7.
- [ ] T081 Record pass/fail notes in the implementation PR or task log.
- [ ] T082 Confirm architecture tests all answer `no`:

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
```

Source of truth: BITE.md → Architecture Violation Test. These ten questions must stay verbatim-matched with spec.md → Architecture Tests.

---

## Deferred Tasks

Create separate specs before doing any of these:

```text
Marketplace / Available UI
full lockfile/source hash registry
capability release-integrity diff
SDK compatibility adapters
hook subscription system
plugin-owned migrations
hot reload
subprocess sandbox
chat.py 7-step rewrite
full migration of Meta/TikTok/LinkedIn/YouTube/etc.
```
