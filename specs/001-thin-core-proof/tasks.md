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
- [x] T012 Add/verify test or manual check: empty external root returns zero plugin capabilities after restart. **Done — 3 tests in `api/tests/test_plugin_host_invariants.py` (empty root, no error_states, dirs without channel.json skipped).**

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
- [x] T023 Add/verify test or manual check: one broken plugin does not hide a valid plugin. **Done — 3 tests in `api/tests/test_plugin_host_invariants.py` (invalid JSON, schema failure, duplicate plugin_id).**

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

- [x] T050 Remove hardcoded platform cards from `web/src/pages/admin/AdminModules.tsx` that appear without installed plugin data. **Done — replaced `['media.image','media.video'].includes(plugin.plugin_id)` with manifest-driven `plugin.media_provider_options.length > 0`; replaced hardcoded statuses array with `[...searchParams.entries()]` iteration.**
- [x] T051 Render plugin Specialist cards from `GET /plugins` only.
- [x] T052 Display activation state per Brand for each installed plugin.
- [x] T053 Add Activate/Deactivate controls calling D4 endpoints.
- [x] T054 Show credential/setup/validation status only for installed plugins.
- [x] T055 Ensure uninstalled platforms produce no readiness debt or connector warnings. **Verified — `buildPlatformMeta()` derives from installed plugin manifests; `summarizeInstalledPlugin()` derives connectors from `plugin.connections[]`; no hardcoded platform names outside dynamic param handling.**

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

- [x] T070 Verify plugin-declared `connections` schema is parsed from `channel.json`. **Verified — `ChannelPluginManifest.connections: List[PluginConnectionManifest]` parsed at scan time; `_connection_to_plugin` dict built from `connection.platform`.**
- [x] T071 Verify `/social/connect/start` or equivalent can start OAuth for a plugin-declared platform without a hardcoded handler. **Verified — `_plugin_id_for_platform()` falls back to `get_plugin_id_for_connection()`; `get_oauth_handler()` returns `GenericPluginOAuthHandler` for plugin-declared platforms.**
- [x] T072 Verify generic callback can store `SocialConnection` for plugin-declared platform. **Verified — `GET /{platform}/callback` in `social.py` handles plugin-declared platforms via `GenericPluginOAuthHandler`; stores via `_store_connection()`.**
- [x] T073 Verify `inject_channel_credentials()` can inject the stored token for `requires_social_connection` declared by that plugin. **Verified — `social_token` slot resolver calls `get_page_token(db, brand_id, slot.platform, settings)` and populates `credentials[slot.key]`.**
- [x] T074 If D8 is partial/broken, document the gap and keep `requires_platform_vars` as MVP fallback. Do not build full OAuth edge-case framework. **D8 complete — generic flow is operational. Legacy `requires_platform_vars` converted to `credential_slots` at load time (T063).**

Acceptance:

```text
Standard OAuth2 plugin can connect without platform-specific core handler.
Non-standard OAuth can defer to requires_platform_vars.
```

---

## Phase 9 — Violation Remediation (V2–V8)

> Resolves the remaining violations from research.md Decision 9 that are not covered by Phase 6.
> V1 is covered by T061. V9 is covered by T064.

- [x] T090 (V2) Add `provider_options` array to `channel.json` for `media.image` and `media.video`. Each entry: `{ "provider": "openai", "label": "OpenAI", "models": [...] }`. Remove `_MEDIA_PROVIDER_OPTIONS` dict from `api/routers/plugins.py`. Serve from `PluginInfo.media_provider_options` via the loaded manifest instead. **Done — provider_options in channel.json; plugins.py reads m.provider_options from manifest; no hardcoded dict.**
- [x] T091 (V3) Add `workspace_discovery_url` string field to `ChannelPluginManifest`. Move ClickUp URL into `channel.clickup/channel.json`. Implement generic `/plugins/{plugin_id}/resolve-workspaces` handler that reads the URL from the manifest and makes the request. Remove `_WORKSPACE_RESOLVERS` dict from `api/routers/plugins.py`. **Done — workspace_discovery_url in clickup channel.json; plugins.py reads from manifest; _WORKSPACE_RESOLVERS removed.**
- [x] T092 (V4) Remove `_CHANNEL_DISPLAY` dict from `api/routers/chat.py`. Build display names in `_brand_channel_readiness()` from active plugin connection manifests: read `connections[].platform` from loaded plugin state, use `display_name` from manifest or `titleCase(platform)` as fallback. No hardcoded platform names in core. **Done via T096 — _CHANNEL_DISPLAY removed; _platform_display_name() added.**
- [x] T093 (V5 + V6) Move `workspace/council` logic out of `api/capabilities/` into `api/council.py` as an explicit core service. Update `api/capabilities/workspace/council/module.py` to delegate to `api/council.py` via the brief (not direct import). Remove direct `from capabilities.workspace.council.module import start_session` from `chat.py` — call `api/council.py` directly as a core service call, not a capability dispatch. **Done — `api/council.py` is the core service; `module.py` is a clean execute() stub (no BOS internals); SKILL.md set to `allowed_from_chat: false`; `chat.py` imports from `council` directly.**
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

- [x] T110 · D1 (operator): Copy 6 workflow plugins from `api/plugins/` → `~/bos-plugins/`. Done — 8 external plugins load (6 + hello + gbp-completeness). All `source: external`, bundled api/plugins/ no longer appear.
- [x] T111 · D2 (operator): Remove `KLAROHA_LOAD_INTERNAL_PLUGINS=true` from `.env`. Done — set to `false`; API restarted; 8 external-only plugins confirmed. Fixed `gbp-completeness/channel.json` missing `key` field in credential_slot.
- [x] T112 · D3 (staging gate): Clear org-wide rows + recreate brand-scoped. Done — 0 org-wide active rows; 6 brand-scoped active rows for Klaroha brand `c1cb6603-e8d4-4e63-8995-640453d5b50b`.

Acceptance:
```text
Admin shows only plugins from ~/bos-plugins/ (no bundled api/plugins/ examples).
No org-wide active rows (brand_id=null) remain in plugin_activations.
All 6 social workflow plugins are active for Klaroha brand specifically.
A second Brand created on staging sees no plugins active unless explicitly activated for it.
```

---

## Phase 8 — Final Validation

- [x] T080 Run `specs/001-thin-core-proof/quickstart.md` V1–V7. **Done — all 7 checks pass (see T081).**
- [x] T081 Record pass/fail notes in the implementation PR or task log. **Done — V1: 3 tests (empty root, no error_states, dirs without channel.json), PASS. V2: channel.hello shows installed+inactive, PASS. V3: 6 brand-scoped active plugins for Klaroha, PASS. V4: deactivate with query param works (brand-scoped inactive row confirmed), PASS. V5: 0 quarantined plugins, 8 installed, covered by T023 quarantine tests, PASS. V6: AdminModules.tsx derives entirely from plugin manifests, no hardcoded platform names, PASS. V7: no forbidden BOS internal imports in ~/bos-plugins/ (only klaroha_sdk which is allowed), PASS.**
- [x] T082 Confirm architecture tests all answer `no`. **Done — all 13 answer no: no platform-before-install, no platform-specific core, no core edit required, no uninstalled-plugin warnings, no inactive capabilities in manifest, KLAROHA_LOAD_INTERNAL_PLUGINS=false, no workflow opinion in core, no chat-router platform branches, no new primitives, council/capabilities have no BOS internal imports, sample-first followed, artifact types not confused, no artifact banning.**

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

Source of truth: BITE.md → Architecture Violation Test. These thirteen questions must stay verbatim-matched with spec.md → Architecture Tests.

---

---

## Phase 12 — Spec Completeness (from 2026-06-09 architecture review)

- [x] T113 · Update `specs/001-thin-core-proof/spec.md`: add FR-014–FR-019, SC-010–SC-011. Done — org-wide activation guard, deactivation demotion, read-side no-write, brand-scoped credential filtering, council/core boundary, capability-manifest endpoint, source field, scope badge.
- [x] T114 · Update `specs/001-thin-core-proof/spec.md`: add 3 missing BITE.md Architecture Violation Test questions (sample-first, artifact confusion, ban-artifacts anti-pattern). Update T082 checklist verbatim-match. Done.
- [x] T115 · Mark violations V1–V9 as resolved in `specs/001-thin-core-proof/research.md` Decision 9 table. V1→T061✓, V2→T090✓, V3→T091✓, V4→T096✓, V5+V6→T093✓, V7→T094✓, V8→T095✓, V9→T064✓. Done.
- [x] T116 · Admin Specialists sort: active/ready plugins first, inactive/needs-setup after. Sort by readiness tier (ready → installed → needs_setup) then alphabetical within tier. Done in `AdminModules.tsx`.
- [x] T117 · Verify `specs/001-thin-core-proof/plugin-dev-onboarding.md` covers: absolute path requirement for `EXTERNAL_PLUGINS_PATH`, `excluded_triggers` guidance, `credential_slots` vocab replacing old fields, `requires_intent` canonical values list. Update any outdated sections. **Done — added absolute path Docker warning, requires_intent canonical values block.**
- [x] T118 · Add prominent note to `api/plugins/PLUGIN_SDK.md`: `api/plugins/` is SDK examples only; direct plugin authors to `~/bos-plugins/` as canonical install location. **Done — note block added at top of PLUGIN_SDK.md.**
- [ ] T119 · Post-merge live verification at hq.klaroha.com (after T110–T112 complete + branch merged to main + deployed): confirm server logs show external plugins as `[external]`; hello dispatches via CMO chat producing `pipeline_test_result`; GBP audit produces `setup_blocker` or `gbp_completeness_result`. This is V8 of the quickstart sequence.

Acceptance for Phase 12:
```text
spec.md FR count = 19, SC count = 11, Architecture Tests = 13 questions.
tasks.md T082 checklist matches spec.md Architecture Tests verbatim.
research.md Decision 9 violation table has resolution notes for V1–V9.
```

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
