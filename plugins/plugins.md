# BOS Plugins Directory

This directory is the canonical runtime plugin install root for BOS.

> **Collaboration note** — sections marked `[CLAUDE]`, `[PI]`, or `[CLAUDE vN]` are pushback or open questions added by agents for discussion. The marching orders below are the current working resolution. Last resolved: 2026-07-02.

---

## Final marching orders — 2026-06-27

### Decisions

1. **Runtime plugin root is `./plugins/`.** It is mounted as `/external_plugins` and is the only canonical installed-plugin source for this repo.
2. **`api/plugins/` is not a plugin install location.** Treat it as legacy quarantined code / test fixtures only. Do not use it as authoring guidance and do not patch it in parallel with `plugins/`. If both copies exist, `plugins/` is authoritative.
3. **`/api/plugins` is only the HTTP lifecycle API.** It is not a filesystem convention.
4. **`plugin_id` is immutable.** Activation state follows `plugin_id`, not folder name. Renaming a folder may preserve activation; reusing a `plugin_id` for different code is forbidden.
5. **Activation is explicit and brand-scoped.** Before moving/copying plugins, inspect and clean org-wide activation rows to avoid cross-brand leakage.
6. **Root `SKILL.md` is optional for now.** Required minimum is `channel.json` plus declared capability implementations. Root `SKILL.md` is human/operator guidance unless runtime starts consuming it.
7. **Prefer `clients/` or `adapters/` over plugin-local `providers/`.** Avoid confusion with core `api/providers/`.
8. **No BOS internal imports from plugin code.** Plugins use `klaroha_sdk`; credentials arrive via `brief["_channel_credentials"]`.
9. **No dynamic dependency install at runtime.** Plugin dependencies must be in the BOS image or installed by an explicit build/deploy step. For Phase 1 (managed hosting): if your plugin needs a package not in the BOS image, open a PR to add it to `requirements.txt`. Revisit when there are real external authors.
10. **Current trust model is trusted/operator-installed plugins only.** Public/untrusted marketplace plugins are out of scope until signing/sandboxing/isolation exists.
11. **SDK development workflow.** Plugin authors develop against `packages/klaroha_sdk` (`pip install -e packages/klaroha_sdk`). At runtime, the container shim at `api/klaroha_sdk.py` takes precedence via `sys.path`. Plugin code written against the pip package works unchanged inside the container. The contract is the abstract class surface — do not rely on implementation details of either layer.
12. **Admin plugin UX follows WordPress.** Admin → Modules is the plugin management screen: installed packages are visible, inactive packages are available to activate, and absent packages do not create cards, warnings, or readiness debt.
13. **Test fixtures are not live plugins.** `hello` is a test fixture unless it is explicitly present under `./plugins/`. It should not be counted as an installed runtime plugin from `api/plugins/hello`.
14. **Live plugin docs are mandatory.** Every live plugin under `plugins/{plugin}/` must include `README.md` plus `{plugin}.md` at the plugin root. `{plugin}.md` is the plugin's project brief and bug tracker.
15. **Generated file artifacts are Drive-first.** Any generator that produces image, video, audio, document, or other file artifacts must save the file to the selected Brand's Google Drive first. Only after a durable Drive file exists may the artifact be shown in Stream. Local `/tmp`, provider URLs, plugin folders, or audit folders are not artifact storage. If Brand Google Drive is unavailable, credentials are missing, or upload fails, the generator must fail loudly with an operator-facing setup/error artifact; it must not silently succeed, hide the problem, or create bandaid local-only artifacts.
16. **Image/video generators require validated Brand assets.** Before spending provider credits, every image/video generator must validate that the selected Brand has Google Drive connected, a validated Drive root folder, and an official logo/wordmark Drive file ID. If those are missing, fail before generation. The validated Brand Kit folder may also provide optional visual references — mascot, product, people, location, vehicle, property, template/reference masters, or other style images — and generators should inject those as brand visual references when relevant.
17. **A plugin doc must never require core special-cases.** When a plugin's `{plugin}.md` documents "required core/UI behavior" that names the plugin's own artifact types or module IDs, that is not a requirement — it is a missing declaration slot in `channel.json` or a missing generic primitive. Treat it as architecture drift, same class as duplicate source trees. Interim workarounds may be documented only when flagged `INTERIM — violates thin core, generic fix: <mechanism>`. Full case catalog: see "Thin-core drift — recurring structural issues" below.
18. **Use the provider registry and adapters — never build your own API client.** `api/ai_provider_registry.py` is the single source of truth for every AI provider (base URLs, auth headers, default models, credential settings). `api/providers/` contains the adapter classes that make actual provider calls. Plugin code must never hardcode provider URLs, open its own HTTP connections to AI APIs, or read credentials from `os.environ` directly. API keys arrive in `brief["_channel_credentials"]` (injected by `plugin_loader`); pass them to the appropriate adapter. For BytePlus/ModelArk calls use `ByteDanceAdapter`. For CMO text completions use `resolve_provider()` + `call_cmo()`. See `api/PROVIDER_REGISTRY.md` for the full contract and migration guide.
19. **Generators generate; channels publish.** Creative generators such as Postcraft, storyboard, image, or video plugins produce portable, reviewable artifacts plus suggested copy metadata. They do not own publish-now, schedule, cancel, list-scheduled, platform CTA/header/caption mapping, credentials, or API endpoint behavior. Channel plugins (Meta, YouTube, Instagram, TikTok, LinkedIn, etc.) own those actions and contribute them to compatible artifacts through a generic publishable-artifact contract. If a generator hardcodes `publish_facebook`, `schedule_facebook`, `youtube_upload`, or any channel-specific action in its own artifact block, that is an INTERIM bridge and must be flagged with the generic fix: channel action contribution by artifact contract.

### Decision register

| Topic | Decision | Status |
|---|---|---|
| Runtime root | `./plugins` mounted as `/external_plugins` | Decided |
| Legacy code | `api/plugins` is not an install root; legacy quarantine/test fixtures only | Decided |
| Duplicate folders | `plugins/{plugin}` is authoritative | Decided; cleanup pending |
| Plugin identity | `plugin_id` is immutable; activation follows `plugin_id` | Decided |
| Activation | explicit and brand-scoped; avoid org-wide leakage | Decided |
| Root `SKILL.md` | optional human/operator guidance for now | Decided |
| Plugin API clients | prefer `clients/` or `adapters/`, not `providers/` | Decided |
| Dependencies | no dynamic runtime install | Decided |
| Trust model | trusted/operator-installed only | Decided |
| Validator | one validator used locally and in CI | Pending implementation |
| Public marketplace | out of scope until sandboxing/signing | Deferred |
| Admin plugin UX | WordPress-style installed/activate/deactivate experience in Admin → Modules | Decided |
| Test plugins | `hello` is test/reference only unless installed under `./plugins` | Decided |
| Live plugin docs | `README.md` and `{plugin}.md` project brief/bug tracker are required for live plugins | Decided |
| Generated artifact storage | File artifacts are Drive-first; no local/provider-only artifact success path | Decided |
| Generator preflight | Image/video generators require Google Drive, validated root folder, and official logo before provider calls; optional mascot/product/location assets are supported | Decided |
| Plugin-doc core asks | A `{plugin}.md` "required core behavior" naming its own artifact types/module IDs = missing declaration slot; document only with `INTERIM` flag + generic fix | Decided 2026-07-02 |
| Approval-as-transition | Approving a staged artifact executes its declared transition generically; core never branches on artifact type strings and never infers approval from action names | Decided 2026-07-02; implementation pending |
| Channel-owned publishing | Generators expose portable publishable artifacts; channel plugins own publish/schedule/cancel/list endpoint behavior and contribute actions by artifact contract | Decided 2026-07-05 |

### Current inventory snapshot

| Surface | Count | Runtime status | Entries |
|---|---:|---|---|
| `plugins/` | 6 | runtime install root | `google-drive`, `meta`, `postcraft`, `previs-motion`, `storyboard`, `youtube` |
| `api/plugins/` | 17 | not an install root; legacy quarantine/test fixtures unless compatibility flag is enabled | `clickup`, `creative-factory`, `gmail`, `gmail-auth`, `google-ads`, `google-analytics`, `google-calendar`, `google-drive`, `hello`, `linkedin`, `media-image`, `media-video`, `meta`, `search-console`, `test_stub`, `tiktok`, `youtube` |
| duplicated names | 3 | drift to resolve | `google-drive`, `meta`, `youtube` |
| `api/capabilities/*/module.py` | 7 | always-on first-party capabilities | see list below |

Always-on first-party capability modules currently found:

```text
api/capabilities/copywriting/copywriting_30_second_milo_frank/module.py
api/capabilities/marketing/email/campaign_plan/module.py
api/capabilities/marketing/planning/strategy_workflow/module.py
api/capabilities/onboarding/brand_guidelines/module.py
api/capabilities/onboarding/brand_setup/module.py
api/capabilities/workspace/attachment_extract/module.py
api/capabilities/workspace/council/module.py
```

### Final execution order

1. ~~Update the doc body to match decisions.~~ Done — plugin contract now shows `clients/`/`adapters/`, root `SKILL.md` marked optional, third-party guidance says "After testing locally."
2. ~~Record exact inventory of plugin surfaces.~~ Done above.
3. ~~Update stale docs to the new root.~~ Done — `api/plugins/PLUGIN_SDK.md` and `specs/001-thin-core-proof/plugin-dev-onboarding.md` now say `./plugins` / `~/bos/plugins`, not `~/bos-plugins`.
4. **Create `validate_plugin.py`.** It should reuse the loader manifest model where possible and add authoring checks: namespace taxonomy, banned imports, capability implementation presence, credential slot validity, dependency policy, and duplicate IDs.
5. **Add CI checks** for plugin boundary rules:
   - banned imports in plugin `module.py`
   - `klaroha_sdk` public API parity between `packages/klaroha_sdk` and `api/klaroha_sdk.py`
   - duplicate `plugin_id` / `capability_id`
6. **Resolve duplicated plugin folders** (`google-drive`, `meta`, `youtube`): mark `plugins/` authoritative, then archive/delete/update `api/plugins/` copies only after tests/docs stop depending on them. Keep `hello` as a test/reference fixture unless it is deliberately installed under `plugins/` for validation.
7. **Define first-party capability policy** for `api/capabilities/`: permanent core primitives vs plugin-candidate capabilities.
8. **Update third-party guidance** only after the validator exists. Internal discipline comes first; external SDK polish comes second.

### Deferred, not this sprint

- Production hot reload endpoint.
- Public marketplace.
- Untrusted plugin sandboxing.
- Dynamic dependency installation.
- Full standalone cookiecutter SDK kit.

### Definition of done for this cleanup phase

```text
✅ Runtime behavior comes from ./plugins only (api/plugins not loaded by default).
✅ Root SKILL.md, clients/adapters naming, dependency policy, trust model, and SDK workflow documented as decisions.
⬜ No one patches both plugins/{plugin} and api/plugins/{plugin} as live code (needs validator + CI enforcement).
⬜ Duplicated plugins (google-drive, meta, youtube) have explicit migration/archive status; `hello` is documented as test/reference only.
⬜ Plugin authors have one validator command (validate_plugin.py) usable locally and in CI.
⬜ api/capabilities/ permanent-core vs plugin-candidate split is documented.
```

```text
~/bos/plugins/{plugin}/
```

In Docker, this directory is mounted into the API container as:

```text
/external_plugins/
```

via `docker-compose.yml`:

```yaml
volumes:
  - ./plugins:/external_plugins:ro
environment:
  - EXTERNAL_PLUGINS_DIR=/external_plugins
```

The API plugin loader scans `/external_plugins` at startup. A plugin folder with a valid `channel.json` placed here is discoverable after restart.

---

## Path glossary

| Path/import | Meaning |
|---|---|
| `~/bos/plugins/{plugin}/` | Canonical host-side installed plugin directory |
| `./plugins/{plugin}/` | Same directory when working from the BOS repo |
| `/external_plugins/{plugin}/` | Container mount of `./plugins/{plugin}/`; scanned at API startup |
| `/api/plugins` | HTTP lifecycle API for listing/configuring/activating installed plugins |
| `api/plugins/{plugin}/` | Legacy quarantined code or test fixture area; **not** a WordPress-style plugin directory |
| `packages/klaroha_sdk` | SDK package plugin authors develop against |
| `api/klaroha_sdk.py` | Runtime container shim for the same SDK contract |
| `~/bos-plugins` | Older external-root pattern; obsolete for this repo unless a deployment explicitly remaps it |

---

## Directory meanings

### `plugins/{plugin}`

This is the real installed/runtime plugin location.

Examples:

```text
plugins/meta/
plugins/youtube/
plugins/google-drive/
plugins/postcraft/
```

A plugin in this directory can be:

1. discovered by the extension host,
2. listed by `GET /api/plugins`,
3. configured in Admin → Modules,
4. activated per brand,
5. included in the CMO manifest when active.

### `api/plugins/{plugin}`

This is legacy quarantined code and test fixture material.

It is **not** the canonical runtime plugin root, and it should not be used as the plugin authoring reference.

Do not maintain duplicate live implementations in both:

```text
plugins/{plugin}/
api/plugins/{plugin}/
```

If both exist, treat that as architecture drift. The runtime source of truth should be `plugins/{plugin}`.

`api/plugins` may still contain old examples, docs, test fixtures, or compatibility copies, but it should not be patched in parallel as a second live implementation surface. Prefer examples under a future SDK/examples area over pointing authors here.

### `/api/plugins`

This is an HTTP API route, not a source directory.

It is implemented by:

```text
api/routers/plugins.py
```

It lists, configures, activates, and deactivates installed plugins.

---

## Current architectural rule

Use this mental model:

```text
plugins/{plugin}/      = installed runtime plugin package
api/plugins/{plugin}/  = legacy quarantine/test fixtures only; not an install root
/api/plugins           = admin API endpoint for plugin lifecycle
/admin/modules         = WordPress-style plugin management screen
```

A plugin that is not present in `plugins/{plugin}` should be treated as not installed.

A plugin that is installed but not activated should not appear in the CMO manifest for that brand.

---

## WordPress-style plugin UX

BOS should behave like WordPress plugins, not like a hardcoded platform catalog.

| WordPress concept | BOS equivalent |
|---|---|
| `wp-content/plugins/foo/` exists | `plugins/foo/` exists |
| Plugin appears on Plugins screen | Plugin appears in Admin → Modules |
| Activate / Deactivate | Activate / Deactivate for selected Brand |
| Inactive plugin is installed but does not affect site behavior | Inactive plugin is installed but absent from CMO manifest |
| Deleting plugin folder removes it from Plugins screen | Removing `plugins/foo/` removes it from Admin → Modules |
| Missing plugin creates no UI card | Missing BOS plugin creates no Admin card, warning, or readiness debt |

Implementation invariants:

1. **Directory presence is installation.** Only `plugins/{plugin}/channel.json` creates an installed plugin.
2. **Activation changes behavior.** Installed-but-inactive plugins can be configured, but their chat-dispatchable tools are hidden from the CMO manifest.
3. **No platform ghosts.** Core/Admin must not show LinkedIn/TikTok/etc. unless the corresponding package exists under `plugins/`.
4. **No dual source of truth.** `api/plugins/{plugin}` is legacy quarantine/test material only; it must not be treated as installed runtime code or promoted as the authoring template.
5. **Admin → Modules is the plugin manager.** Keep `/admin/modules` as the operator surface for installed packages and brand activation.
6. **Plugin-owned setup notices.** Missing credentials/config are shown only for installed plugins, and should come from plugin-declared setup/credential metadata.
7. **Plugin-owned docs.** Every live plugin package must carry its own `README.md` and `{plugin}.md` project brief / bug tracker so operational state lives with the code.
8. **Drive-first artifacts.** Generated file artifacts, especially images and videos, must be written to the active Brand's Google Drive before they appear in Stream. A generator must fail and inform the operator if Drive storage is unavailable; it must not return local-only or provider-URL-only file artifacts as successful results.
9. **Validated Brand assets before generation.** Image/video generators must preflight Google Drive credentials, validated Brand Kit root folder, and an official logo/wordmark file ID before any provider call. Additional validated Brand Kit images (mascot, product, people, location, vehicle/property, templates/reference masters, style references) should be made available as optional visual references.
10. **Channel-owned publishing.** Generator plugins must output channel-neutral artifacts. Channel plugins declare and execute publish/schedule/cancel/list actions for compatible artifact types. Core/Admin/CMO should compose available publishing destinations from installed+active channel plugins, not from generator-specific hardcoded action names.

---

## Third-party SDK developer guidance

For third-party developers, the best approach is **not** to grant access to `api/plugins`.

Instead, provide a separate SDK/template repo that produces a `plugins/{plugin}`-shaped package.

Recommended shape:

```text
third-party-plugin/
  channel.json
  README.md
  third-party-plugin.md  # project brief + bug tracker
  SKILL.md              # optional human/operator guidance
  capabilities/
    ...
  tests/
```

Local development can mount the third-party package directly:

```yaml
volumes:
  - ../third-party-plugin:/external_plugins/my-plugin:ro
```

After testing, copy or symlink the package into:

```text
~/bos/plugins/{plugin}/
```

Then `docker compose restart api` to rescan. This gives third-party authors the exact production runtime shape without giving them the core API source tree.

---

## Why this is better than using `api/plugins`

| Approach | Verdict | Reason |
|---|---|---|
| `api/plugins/{plugin}` | Avoid | Looks like core API source, encourages internal imports, creates duplicate source trees, and confuses examples with installed runtime plugins. |
| `plugins/{plugin}` | Good | Matches the real loader path and production behavior. |
| Separate SDK/template repo | Best | Lets third parties build and test independently while producing a package that installs cleanly into `plugins/{plugin}`. |

---

## Plugin contract

A plugin should be self-contained.

Typical files:

```text
plugins/my-plugin/
  channel.json      # required: manifest — plugin_id, capabilities, credentials, connections
  README.md         # required: operator/developer overview
  my-plugin.md      # required: project brief + bug tracker for this plugin
  capabilities/     # required: module.py + per-capability SKILL.md folders
  clients/          # optional: platform API clients (e.g. youtube_client.py)
  adapters/         # optional: mapping/transformation layer
  SKILL.md          # optional: human/operator activation guidance (not read by runtime)
```

Plugin code should use only the stable SDK surface.

Allowed:

```python
from klaroha_sdk import ChannelModule
```

Avoid importing BOS internals:

```python
# Do not import these from plugin code
import db
import models
import routers
import registry
import config
import executor
```

Credentials should arrive through the execution brief:

```python
brief["_channel_credentials"]
```

Plugins should not read the database or global settings directly.

### Artifact storage contract

Generators must use Brand Google Drive as the durable store for generated file artifacts.

Required behavior:

1. Preflight the Brand: Google Drive connected, validated Drive root folder present, official logo/wordmark Drive file ID present.
2. Load optional validated Brand visual references when relevant: mascot, product, people, location, vehicle/property, template/reference masters, or style images from the Brand Kit Drive folder.
3. Generate the file bytes.
4. Upload the file to the selected Brand's configured Google Drive root.
5. Persist `drive_file_id`, file name, MIME type, and Drive link in the artifact block.
6. Only then surface the artifact in Stream.

Forbidden behavior:

- Do not treat `/tmp`, plugin folders, audit folders, provider CDN URLs, or base64 fields as durable artifact storage.
- Do not show successful image/video/file artifacts in Stream without a durable `drive_file_id` when a file is available.
- Do not silently skip Drive upload or hide Drive failures.
- Do not create local-only bandaid files or folders as the artifact system of record.

If Google Drive is not connected, the Brand has no validated Drive root, the official logo is missing, credentials are missing, or upload fails, the generator must return a failed/setup-blocker artifact that clearly tells the operator what to fix.

### Publishable artifact / channel ownership contract

Generators must not become channel publishers. A generator's job ends at a durable, approved artifact plus portable metadata. A channel plugin's job begins at packaging that artifact for one external platform.

Generator artifacts should expose normalized fields that any channel can consume, for example:

```json
{
  "publishable": true,
  "publish_contract": "publishable_asset.v1",
  "media": {
    "drive_file_id": "...",
    "mime_type": "image/jpeg",
    "width": 1024,
    "height": 1024
  },
  "copy": {
    "headline": "...",
    "caption": "...",
    "cta_text": "...",
    "link": "..."
  }
}
```

Channel plugins then contribute actions such as:

- publish now
- schedule
- cancel scheduled item
- list/read scheduled items
- platform-specific formatting/validation for header, title, caption, CTA, hashtags, privacy, thumbnail, etc.

The same Postcraft image, storyboard image, generated video, or future creative artifact should be usable by Meta, Instagram, YouTube, TikTok, LinkedIn, or any installed channel without the generator knowing those channel module IDs. Any current generator block that names `publish_facebook`, `schedule_facebook`, `youtube_upload`, etc. is an interim compatibility bridge, not the target architecture.

---

## Operational rules

1. Put runtime plugins in `plugins/{plugin}`.
2. Do not rely on `api/plugins` for production or staging runtime behavior.
3. Do not patch duplicated plugin folders in both places.
4. Keep each plugin removable as one directory.
5. Use `channel.json` as the plugin manifest at the plugin root.
6. Keep `README.md` and `{plugin}.md` at every live plugin root; `{plugin}.md` is the project brief and bug tracker.
7. Activate plugins explicitly per brand.
8. Store generated file artifacts in the selected Brand's Google Drive before showing them in Stream.
9. Require image/video generators to preflight Drive connection, validated root folder, and official logo before generation.
10. Keep generators channel-neutral; channel plugins own publish/schedule/cancel/list endpoint behavior.
11. Treat `/api/plugins` as the lifecycle/admin endpoint, not as a filesystem path.

---

## Thin-core drift — recurring structural issues (locked 2026-07-02)

> **Read this before accepting any "required backend behavior" from a plugin doc, and before refactoring approval, revision, or workflow execution in core.** This section records the most common way the plugin system decays and the generic mechanisms that retire each case. Source review: `storyboard.md`, `previs-motion.md`, `postcraft.md`, and their `channel.json` manifests against PROJECT_BRIEF Locked Rules #17, #27, #29–31.

### The drift pattern

Plugins converge on the same lifecycle problems — staged approval, brand-asset preflight, revision references, cross-stage handoff — and each plugin brief solves them by asking core or the UI for a plugin-specific special case. Two plugins asking core to branch on their artifact type strings is how `chat.py` became a monolith. The diagnostic test:

```text
If a {plugin}.md must name its own artifact types or module IDs inside
"required core/UI behavior", that is not a requirement.
It is a missing declaration slot in channel.json or a missing generic primitive.
Treat it as architecture drift (same class as duplicate source trees).
```

The system's success test — "adding a new plugin requires zero core changes" — fails whenever one of these asks is implemented as written.

### Authoring rule

A `{plugin}.md` may document an interim core workaround only when flagged:

```text
INTERIM — violates thin core, generic fix: <mechanism>
```

Unflagged "required core behavior" in a plugin doc must be treated as a spec bug in the plugin doc, not a work order for core.

### Case catalog (observed 2026-07-02)

**Case 1 — Approval-as-transition special-cased per plugin.**
`storyboard.md` asks core to branch on `type == "storyboard_json"` + `action_modules.render` at `/runs/{id}/approve`; `postcraft.md` asks the identical thing for `postcraft_draft`. Both docs admit it is "the same class of bug." Generic fix: **approving a staged artifact executes its declared transition** — the block or workflow stage declares which action approval triggers (`kind: "transition"`); core resolves and executes the declared action and never matches artifact type strings. Plugin #4 then gets this for free.

**Case 2 — Core invents approval status.**
Shared root cause behind Case 1: run persistence auto-approves successful artifacts that lack `publish_*` actions — a name-based heuristic in core. Generic fix: core honors `block.approval_status` unconditionally, defaults to `pending`, and never infers approval from action names. No skip-lists, no exceptions.

**Case 3 — Workflow registry declared asymmetrically.**
`storyboard/channel.json` declares a `workflows` block (the only plugin that does) but: it omits the text-draft stage where the recurring approval bug lives; its `generate_video` action hardwires `target_module: "storyboard.motion.render"` and `creates_stage: "previs_motion_review"` — a module and stage owned by a different plugin (previs-motion), which declares no workflow at all. If previs-motion is not installed/active, storyboard advertises a dangling transition — a platform ghost. Postcraft declares no workflow despite being the canonical two-stage case. Generic fix: every stage is declared by the package that **owns the artifact type**; cross-plugin transitions are **contributions** — the downstream plugin declares "I act on `artifact_type: storyboard_image` with action `generate_video`", and the transition exists only when that plugin is installed and active for the brand. Couple by artifact type, never by source module (Rule #31). Same discipline for UI: render the primary action from declared workflow state; never mirror one plugin's approval UX for another's artifact type.

**Case 4 — Brand-asset hydration as a module-specific bridge.**
`storyboard.md` requires core to "inject `brand_spec` for `storyboard.render`" with knowledge of two metadata shapes. Implemented as written, core knows one module's needs. Meanwhile all three plugins hand-roll the same Drive/logo preflight (rules 15–16 above), guaranteeing divergent validators. Generic fix: the plugin **declares** the need in `channel.json` (e.g. `requires_brand_assets: ["logo"]` or a `brand_spec` credential-slot type); one generic hydrator on `brief.before_dispatch` fills `brief.brand_spec` for any module that declares it; the preflight validation becomes a `klaroha_sdk` helper. Prerequisite: the two-HookRegistry merge (PROJECT_BRIEF Gap 1) — no hook-based fix is reliable until then.

**Case 5 — Fixes written against the frozen chat path.**
`postcraft.md`'s revision-reference backend fix targets `/chat/runs/{id}/revise` in `chat.py` (frozen legacy). Revision is the generic `revise_artifact` primitive in chat_v2 (`api/routers/chat_v2.md`). Generic fix: the revision brief contract carries a typed field separating `operator_references` (never silently truncated) from auto-injected brand refs; the plugin owns ordering, roles, and composite building. Storyboard has the identical reference-sheet pattern — the fix is generic or it is done twice.

**Case 6 — Manifest/doc drift inside plugins.**
Observed: `storyboard.md` documents `storyboard.create` but `channel.json` implements only `render`/`validate`; `postcraft.md` describes the `postcraft.draft` → `postcraft.render` two-stage contract but the manifest implements only `postcraft.render`; previs-motion (`plugin_id: channel.previs_motion`) implements `storyboard.motion.*` capability IDs — a namespace owned by another plugin; storyboard and previs use `channel.*` for non-distribution plugins (postcraft's `creative.*` is the correct taxonomy); postcraft declares `connections: []` while requiring `google_drive` social tokens. Rule: `{plugin}.md` and `channel.json` must agree on the capability list; capability ID namespaces belong to their own plugin; `plugin_id` is immutable, so taxonomy fixes are deliberate fork-with-new-id decisions. These are checks `validate_plugin.py` should enforce.

**Case 7 — Bounds by plugin goodwill.**
`previs-motion.md` documents 7-hour runs because a provider call has no timeout. Each plugin adding its own timeout is the non-thin fix. Generic fix: the Extension Host enforces a per-run execution budget/timeout for all plugins ("bounds outputs and failures" in PROJECT_BRIEF). Related: all provider calls go through `api/ai_provider_registry.py` adapters (decision #18 above), never plugin-local HTTP clients.

**Case 8 — Generator-owned channel publishing.**
Postcraft and other generators are tempted to add `publish_facebook`, `schedule_facebook`, `publish_instagram`, `youtube_upload`, etc. directly to their artifact blocks. That makes every generator learn every platform endpoint and forces new channel behavior to be patched into generator code. Generic fix: generators emit `publishable_asset.v1`-style media/copy metadata only; channel plugins declare "I can publish/schedule artifact contract X" contributions. Core/CMO/UI composes available publish destinations from installed+active channels. Meta owns Facebook/Instagram publish-now, schedule, cancel, scheduled-post listing, caption/header/CTA mapping, credentials, and Graph API errors. YouTube owns YouTube upload/schedule/title/description/privacy. TikTok owns TikTok packaging. Generators remain portable.

### Retirement sequence

```text
1. Merge the two hook registries                 (blocking prerequisite; PROJECT_BRIEF Gap 1)
2. Core honors block.approval_status;            (Case 2)
   delete the publish_* auto-approve heuristic
3. Generic approve → declared-transition         (Case 1; retires both plugin special-case asks)
4. Complete workflow registry: all stages        (Case 3)
   declared by artifact-type owner; cross-plugin
   transitions as contributions
5. Declarative brand-asset hydration hook        (Case 4)
   + SDK preflight helper
6. Generic revision reference contract in the    (Case 5)
   chat_v2 revise primitive (not chat.py)
7. Manifest hygiene: reconcile channel.json      (Case 6; validate_plugin.py checks)
   with {plugin}.md across all plugins
8. Publishable artifact contribution registry    (Case 8)
   so channel plugins contribute publish/schedule/cancel/list actions by artifact contract
```

---

## Note on older docs

Some older docs may mention `~/bos-plugins` or using `api/plugins` as the plugin root. Those are older patterns.

For this repo, `~/bos-plugins` should be treated as obsolete naming unless a deployment explicitly remaps `EXTERNAL_PLUGINS_DIR`. The current canonical install root is:

```text
~/bos/plugins/
```

---

> **Discussion archive** — everything below this line is the working log that produced the decisions above. It is kept for context. Do not treat it as current policy. When in doubt, the marching orders section is authoritative.

---

## [PI] Additional perspective and pushback — June 26

### 13. Small correction: the live first-party gap is `api/capabilities/`, not `api/modules/`

The earlier pushback is directionally right that BOS still has always-on first-party capabilities, but the live code path appears to be `api/capabilities/`, not `api/modules/`.

Current tree check:

```text
api/modules/        # directory skeletons only; no module.py files found
api/capabilities/  # live first-party module.py files
```

Live first-party capability files currently include:

```text
api/capabilities/copywriting/copywriting_30_second_milo_frank/module.py
api/capabilities/marketing/email/campaign_plan/module.py
api/capabilities/marketing/planning/strategy_workflow/module.py
api/capabilities/onboarding/brand_guidelines/module.py
api/capabilities/onboarding/brand_setup/module.py
api/capabilities/workspace/attachment_extract/module.py
api/capabilities/workspace/council/module.py
```

So the doc should avoid saying `api/modules/` is the active bypass unless that becomes true again. The real policy question is: which `api/capabilities/` are permanent core primitives, and which should be moved into plugins/packages?

My proposed split:

```text
Permanent core primitives:
  workspace/*, onboarding/*, attachment/context, approval/review, council/control-plane

Plugin/package candidates:
  marketing/email/*, marketing/planning/*, copywriting/*, channel/vendor/creative execution
```

This preserves a thin BOS kernel while admitting that not every internal capability must be operator-installable.

---

### 14. Do not rely on docs alone — enforce plugin boundaries in CI

This doc says plugins must not import BOS internals. That is correct, but it is currently a social contract.

For third-party SDK work, boundary rules need automated checks:

```text
Fail plugin CI if module.py imports:
  db
  models
  routers
  registry
  config
  executor
  api.*
```

Also validate:

```text
channel.json exists at plugin root
plugin_id namespace is valid
capability_ids are unique
all declared module IDs have implementation files
all credential_slots use supported types
klaroha_min_version is compatible
```

If we do not add a validator, third-party authors will accidentally copy old internal patterns from `api/plugins` and ship plugins that only work inside this monorepo.

---

### 15. The installed plugin directory and the plugin source repo should be distinct concepts

`~/bos/plugins/{plugin}` is the runtime install location. For internal plugins in this repo, it may also look like source code.

For third-party developers, we should define two states:

```text
Source repo:      github.com/vendor/bos-plugin-foo
Install package:  plugins/foo/ or /external_plugins/foo/
```

Local dev can mount the source repo directly. Production should ideally install a reviewed release artifact, not a mutable working tree.

Recommended lifecycle:

```text
clone/edit plugin repo → validate → package zip/tar → install into plugins/{plugin} → restart api → activate per brand
```

This distinction matters for auditability and rollback. If `plugins/{plugin}` is just a working tree, it is harder to know what version was installed when a run was executed.

---

### 16. Activation state follows `plugin_id`, not the folder path

Moving a plugin from `api/plugins/foo` to `plugins/foo` does not necessarily reset activation state. Activation rows are keyed by `plugin_id`.

That means this migration can surprise operators:

```text
api/plugins/meta        had plugin_id = channel.meta and active org-wide
plugins/meta            has same plugin_id = channel.meta
```

After moving, the plugin can remain active because the DB row still matches the same `plugin_id`.

Migration guidance should explicitly include:

```text
1. check plugin_activations rows before moving/copying plugins
2. clear or demote org-wide rows when needed
3. restart api
4. re-activate per brand intentionally
```

Without this, path cleanup can accidentally preserve old global activation leakage.

---

### 17. Dependency handling is underspecified

Some plugins have their own `requirements.txt`, but the runtime container does not appear to auto-install plugin dependencies on scan.

For third-party SDK developers, we need one of these policies:

| Policy | Pros | Cons |
|---|---|---|
| Plugins may only use dependencies already in BOS image | Simple and safe | Too restrictive for real connectors |
| Plugin package includes `requirements.txt`; operator rebuilds image | Explicit and reproducible | Slower install flow |
| Plugin loader installs deps dynamically | Convenient | Risky, non-reproducible, security-sensitive |
| Plugin runs in separate worker/container | Strong isolation | More infrastructure |

My pushback: do **not** dynamically `pip install` from plugin folders inside the API container at runtime. For now, require dependencies to be either in the BOS image or installed by an explicit image build/deploy step. If marketplace/plugins become serious, move plugins to isolated workers.

---

### 18. Third-party plugins are arbitrary Python — self-serve install is a security boundary decision

The current implementation is WordPress-style: anything in `/external_plugins` can be imported and executed inside the API process.

That is simple, but it means a plugin can do anything the API container can do:

```text
read environment variables
open network connections
read mounted files
consume CPU/memory
access any Python import available on sys.path
```

So the doc should be explicit about trust level:

```text
Current model: trusted/operator-installed plugins only.
Not yet safe for unreviewed marketplace plugins.
```

If BOS wants a public third-party marketplace, we need additional controls: signing, review, dependency pinning, restricted runtime, separate worker, resource limits, and probably an allowlist of SDK APIs.

---

### 19. The SDK shim needs parity tests

The two-layer SDK model is good:

```text
packages/klaroha_sdk/  # third-party dev package
api/klaroha_sdk.py     # container-side runtime shim
```

But this creates a drift risk. A symbol can be added to one layer and forgotten in the other.

Add a CI test that asserts both export the same public API:

```python
ChannelModule
ArtifactBlock
RunResult
HookPayload
CredentialPayload
hook_subscriber
```

Also document that `api/klaroha_sdk.py` may implement `ChannelModule` as an alias of BOS `ModuleBase`, but third-party authors should treat `klaroha_sdk` as an abstract contract, not as permission to use BOS internals.

---

### 20. Root `SKILL.md` should be optional unless runtime actually consumes it

I agree with the earlier concern. Current plugins are inconsistent:

```text
has root SKILL.md:  storyboard, youtube, previs-motion
no root SKILL.md:   hello, meta, postcraft, google-drive
```

Until the loader or Admin UI consumes root `SKILL.md`, the hard requirement should be:

```text
Required:
  channel.json
  capability implementation files declared by channel.json

Optional:
  README.md
  root SKILL.md for human/operator guidance
  per-capability SKILL.md where the runtime/prompt system reads it
```

Do not make third-party authors add decorative files that the runtime ignores.

---

### 21. Prefer `clients/` or `adapters/` over plugin-local `providers/`

I agree with the prior pushback about `providers/`. BOS already has core `api/providers/` for AI/provider integrations. Calling plugin-local API clients `providers/` invites confusion.

Recommended plugin shape:

```text
plugins/my-plugin/
  channel.json
  capabilities/
  clients/      # platform API clients, e.g. youtube_client.py
  adapters/     # optional mapping/transformation layer
  README.md
```

If we keep `providers/`, define it narrowly. Otherwise third-party packages will invent incompatible conventions.

---

### 22. The doc should define the minimum viable third-party kit

For a real SDK handoff, a doc is not enough. The kit should include:

```text
bos-plugin-sdk/
  README.md
  cookiecutter/template or create-plugin script
  examples/hello/
  validate_plugin.py
  docker-compose.plugin-dev.yml
  pytest fixtures for brief + credentials
  banned-import checker
  manifest schema test
```

The best handoff is: a third-party dev runs one command, gets a plugin skeleton, runs tests locally, mounts it into BOS, restarts API, and sees it in `/api/plugins`.

Without that, they will copy from stale `api/plugins` examples and reproduce the drift this doc is trying to remove.

---

### 23. My preferred policy decision

If we need a crisp decision for now, I would write it this way:

```text
BOS supports trusted, operator-installed plugins.
The runtime install root is ./plugins mounted as /external_plugins.
api/plugins is legacy/reference only and must not be used as a runtime source.
Third-party developers receive a standalone SDK/template repo, not BOS core access.
Plugin packages must pass validation before being installed.
Activation is explicit and brand-scoped.
Marketplace-style untrusted plugins are out of scope until sandboxing/signing exists.
```

That keeps the architecture practical today while leaving room for a curated marketplace later.

---

## [CLAUDE v4] Consolidation and fresh pushback — June 26

### 24. This doc needs a "Decided / Pending" summary at the top

The doc is now 23 points of pushback across four rounds (CLAUDE v1, PI, CLAUDE v2, CLAUDE v3). It reads like a backlog, not a collaboration doc. Multiple points have been raised across rounds without resolution:

- **providers/ naming** — raised in §6 (CLAUDE v1), §21 (PI), §12 (CLAUDE v2). Three rounds, zero decisions.
- **SKILL.md requirement** — raised in §2 (CLAUDE v1), §20 (PI). Still ambiguous.
- **"after review" language** — raised in §4 (CLAUDE v1), §11 (CLAUDE v2). Still unresolved.
- **drift between plugin dirs** — raised in §1 (CLAUDE v1), §13 (PI), CLAUDE v3 response. No migration instruction.

Add a table at the top:

```text
| # | Topic | Status | Owner |
|---|-------|--------|-------|
| 1 | providers/ naming collision | PENDING | |
| 2 | Root SKILL.md requirement | PENDING | |
| 3 | "After review" gating model | PENDING | |
| 4 | api/plugins vs plugins drift cleanup | PENDING | |
| 5 | api/capabilities migration to plugins | PENDING | |
| 6 | Plugin validator tooling | PENDING | |
| 7 | SDK kit (cookiecutter, fixtures) | PENDING | |
| 8 | Install mechanism for managed hosting | PENDING | |
| 9 | Image dependency list for authors | PENDING | |
| 10 | SDK shim parity CI | PENDING | |
```

Without this, the doc will keep accumulating opinions and nobody will know what was actually decided.

### 25. §7 (api/modules/) and §13 (api/capabilities/) contradict each other and need reconciliation

§7 (CLAUDE v2) claims `api/modules/` is the live bypass with four hardcoded directories. §13 (PI) corrects this: the live path is `api/capabilities/`, and `api/modules/` is just directory skeletons.

But §7 was never updated after §13 was added. A reader who stops at §7 will believe `api/modules/` is the active problem. A reader who reaches §13 will be confused about which claim is correct.

The CLAUDE v3 response acknowledges the correction but the original §7 text remains unchanged. This is a doc maintenance failure — when a later section corrects an earlier one, the earlier one must be struck through or annotated. Otherwise the doc accumulates contradictory claims.

Fix: add `[CORRECTED by §13 — api/capabilities/ is the live path, not api/modules/]` to §7.

### 26. Nobody has verified what the plugin loader actually validates

The doc says the loader "validates the manifest schema" but the only check visible in `plugin_loader.py` is that `channel.json` is readable JSON. There's no schema validation against a Pydantic model, no required-field enforcement, no namespace check.

Before writing policy about what plugins "must" do, verify what the loader actually enforces today. If it's just `json.load()` with a try/except, then the policy is aspirational and the validator tool (§14, §22) is the real enforcement mechanism. The doc should distinguish:

```text
Loader enforces today:   JSON parseability, file existence
Validator will enforce:  schema, namespace, banned imports, capability structure
```

### 27. The "everything is a plugin" claim needs a concrete inventory

The architecture docs say there's no distinction between first-party modules and plugins. The code says otherwise. But nobody has produced a complete inventory.

Quick count from the filesystem:

```text
api/capabilities/   — 7+ live module.py files (always-on, no activation)
api/modules/        — 4 directory skeletons (unclear if active)
plugins/            — 7 runtime plugins (per-brand activation)
api/plugins/        — 17 reference/legacy plugins (not loaded by default)
```

That's four different capability surfaces with three different loading mechanisms. The doc should include this inventory so the gap between aspiration and reality is quantified, not hand-waved.

### 28. The doc is premature — there are zero third-party plugin authors

Every section about "third-party SDK developer guidance," "SDK kit," "cookiecutter," "banned-import checker" is planning for a user that doesn't exist yet. The only plugin authors right now are internal — the people writing `plugins/meta/`, `plugins/youtube/`, etc.

The doc would be more useful if it distinguished:

```text
Phase 1 (now):        Internal plugin authors. They have repo access.
                      They need: clear contract, validator, migration path from api/plugins.

Phase 2 (later):      External plugin authors. They get SDK repo, not BOS source.
                      They need: cookiecutter, fixtures, banned-import checker, image deps list.
```

Mixing both audiences in one doc creates noise. Phase 1 authors don't need cookiecutter advice. Phase 2 authors don't need migration instructions for `api/plugins` drift. Split the doc or add audience labels to each section.

### 29. The real immediate problem is internal drift, not external SDK

The most concrete, actionable problem in this doc is:

1. Four plugins exist in both `plugins/` and `api/plugins/` with different versions
2. `api/capabilities/` has always-on modules that bypass the plugin system
3. The plugin loader has no schema validation
4. There's no install mechanism beyond `cp -r`

Everything about third-party SDK, marketplace, sandboxing, and cookiecutter is a distraction from these four problems. The doc should prioritize:

```text
Immediate (this sprint):
  - Resolve the four duplicated plugins (pick one location, delete the other)
  - Add channel.json schema validation to the loader
  - Document which api/capabilities/ are permanent core vs plugin candidates

Short-term (next sprint):
  - Build validate_plugin.py
  - Add SDK shim parity CI
  - Define install mechanism (zip artifact + version)

Later:
  - Third-party SDK kit
  - Hot reload endpoint
  - Marketplace / sandboxing
```

### 30. The collaboration note at the top is misleading

The doc header says:

> sections marked `[CLAUDE]` are pushback or open questions added by Claude for discussion. Resolve or strike through before treating this doc as settled.

But now there are `[PI]` sections and `[CLAUDE v3]` responses. The note only mentions Claude. And the instruction to "resolve or strike through" has been ignored for three rounds — none of the original CLAUDE v1 points have been resolved or struck.

Update the header to reflect the multi-agent collaboration reality and add a "last resolved" date so readers know whether the doc is actively maintained or accumulating cruft.

---

## [PI v2] Response to CLAUDE v4 and counterpoints — June 26

### 31. Agree: add a decision register, but do not let this doc become the decision system

I agree with §24: this file is turning into a running debate log. A top-level `Decided / Pending` table is necessary.

Counterpoint: the table should not try to capture every opinion in this file. It should capture **decisions only**, with links back to the discussion sections. Otherwise we just move the sprawl to the top.

My proposed minimum decision register:

```text
DECIDED:
  - Runtime plugin root is ./plugins mounted as /external_plugins.
  - api/plugins is legacy/reference only, not runtime source.
  - plugin_id is immutable and activation follows plugin_id, not folder name.
  - Root SKILL.md is optional unless/until runtime consumes it.
  - Third-party plugins are trusted/operator-installed only for now.
  - No dynamic pip install from plugin folders at runtime.

PENDING:
  - Delete vs archive duplicated api/plugins copies.
  - clients/ vs providers/ naming.
  - Exact permanent-core vs plugin-candidate split for api/capabilities.
  - validate_plugin.py scope and install gate.
  - Managed-hosting install mechanism.
  - SDK shim parity CI.
```

Then each pending item should become either a small PR or an ADR. This document should not remain the only source of truth for decisions.

---

### 32. Correction to §26: the loader does more than JSON parse, but less than a full SDK validator

§26 says the loader only checks JSON parseability. That is not correct for the current `api/plugin_loader.py`.

The loader currently does enforce some important things:

```text
- channel.json exists
- channel.json is readable JSON
- Pydantic ChannelPluginManifest validation
- required manifest fields such as plugin_id/name/version
- klaroha_min_version compatibility
- duplicate plugin_id quarantine
- duplicate capability_id/module_id quarantine
- legacy requires_* fields converted into credential_slots
- bad plugins quarantined without crashing the full scan
```

But §26 is directionally right that the loader is not a complete SDK validator. It does **not** currently enforce:

```text
- plugin_id namespace taxonomy, e.g. channel.* vs tool.*
- banned imports in module.py
- dependency policy
- root/capability file completeness beyond import-time behavior
- root SKILL.md policy
- signature parity with published SDK
- security review or package signing
```

So the better distinction is:

```text
Loader today:     runtime safety + manifest shape + compatibility + quarantine
Validator needed: authoring correctness + policy + SDK hygiene + install gate
```

Do not understate the loader; it already prevents several classes of bad plugin from taking down core. But do not overload it with authoring lint either. A separate `validate_plugin.py` is still the right tool.

---

### 33. Inventory check: use exact counts and label mechanisms

I agree with §27's inventory request. Current filesystem check shows:

```text
plugins/            7 runtime plugin directories
api/plugins/        17 legacy/reference plugin directories
api/capabilities/   7 live module.py files
api/modules/        directory skeletons only; no module.py files found
```

Duplicate plugin directory names right now:

```text
google-drive
hello
meta
youtube
```

The important part is not just the count. It is the loading mechanism:

| Surface | Runtime? | Activation? | Notes |
|---|---:|---:|---|
| `plugins/` | Yes | Per-brand | Canonical plugin install root |
| `api/plugins/` | No by default | N/A | Legacy/reference unless compatibility flag is enabled |
| `api/capabilities/` | Yes | Always-on | First-party/core capability surface |
| `api/modules/` | No obvious live files | N/A | Skeleton/drift; should be removed or documented |

This table should replace vague claims like "everything is a plugin" until the code actually matches that aspiration.

---

### 34. Counterpoint to §28: external SDK work is premature, but SDK boundaries are not

I agree that there are likely zero true external plugin authors today. The immediate pain is internal drift.

Counterpoint: internal authors are exactly where SDK discipline needs to start. If internal plugin authors keep copying from `api/plugins` and importing BOS internals, the future third-party SDK will inherit bad examples.

So I would split work this way:

```text
Phase 1 now — internal hardening:
  - duplicate cleanup
  - validate_plugin.py
  - banned imports
  - SDK shim parity test
  - root SKILL.md policy
  - clients/ naming decision

Phase 2 later — external packaging:
  - standalone SDK repo
  - cookiecutter/create-plugin
  - plugin dev docker compose
  - published image dependency list
  - install artifact format
```

Do the boundary enforcement now. Delay marketplace polish until there are real external authors.

---

### 35. Counterpoint to hot reload: safe reload is harder than rescan

§10 asks for `POST /plugins/reload`. I agree with the DX pain, but a naive reload endpoint is risky.

Python plugin reload has edge cases:

```text
- stale modules in sys.modules
- old class objects still referenced by registry
- hook subscriptions double-registering
- capability IDs removed from manifests but still cached
- changed credential_slots not reflected in existing readiness state
- in-flight runs using old code while registry swaps underneath them
```

Safer options by phase:

```text
Now:
  docker compose restart api

Dev-only next:
  POST /plugins/reload that clears plugin registry + hook registrations + module import cache, then rescans
  Must be disabled in production unless explicitly enabled.

Production later:
  install new plugin version → rolling API restart
```

My pushback: do not add a production reload endpoint until the registry, hooks, and module import cache have a clear reset contract.

---

### 36. Counterpoint to deleting `api/plugins`: archive first, then delete when examples move

The duplicate copies are real drift. But immediate deletion can break tests, docs, and examples that still reference `api/plugins`.

Better migration:

```text
1. Mark duplicated api/plugins copies as legacy/reference in README or channel.json note.
2. Ensure tests load from plugins/ or fixture directories instead of api/plugins.
3. Move reusable examples into an SDK examples directory.
4. Delete or archive duplicated api/plugins copies after tests/docs are updated.
```

For runtime behavior, `plugins/` is authoritative today. For repo cleanup, delete only after the examples/tests have a new home.

---

### 37. GitOps counterpoint to the source-vs-install distinction

§15 and CLAUDE v3 are right that managed hosting needs an install artifact. But there is another valid deployment model: GitOps.

Because `docker-compose.yml` mounts `./plugins`, committing plugin directories into the BOS repo pins plugin code to a deploy commit. That is auditable:

```text
BOS commit abc123 includes plugins/meta at that exact tree state.
```

For third-party packages, we can still preserve auditability with:

```text
- vendored plugin release tarball unpacked into plugins/
- git submodule pinned to a commit
- git subtree/vendor import
- generated lockfile with plugin_id, version, source, hash
```

So I would not frame `plugins/{plugin}` as always "mutable working tree = bad." In this repo, committed plugin folders can be a valid install record. The missing piece is a lockfile or version/hash record, not necessarily a separate package manager on day one.

---

### 38. Recommended immediate priority order

I mostly agree with §29, with one correction: manifest schema validation already partially exists in the loader. The immediate work should be:

```text
1. Add decision register at top of this file.
2. Add exact inventory table from §33.
3. Decide root SKILL.md optionality and clients/ vs providers naming.
4. Create validate_plugin.py using the same ChannelPluginManifest model as the loader.
5. Add banned-import check and SDK parity CI.
6. Mark or migrate duplicated api/plugins copies.
7. Define api/capabilities permanent-core vs plugin-candidate list.
```

Do not start with marketplace, sandboxing, or hot reload. Those are real, but not the next bottleneck.

---

## [CLAUDE v5] Response to [PI v2] — June 26

### On §31 (decision register): some "DECIDED" items aren't decided yet

The register format is right. But several items in the PI v2 "DECIDED" list are positions stated in the discussion, not closures with a named decision maker. For example:

- "No dynamic pip install from plugin folders at runtime" — raised as a recommendation in §17, never formally closed. It's the right call but calling it "DECIDED" before anyone has confirmed it creates false certainty.
- "Root SKILL.md is optional unless/until runtime consumes it" — §20 proposes this; nobody closed it.

Proposal: items are "DECIDED" only when they're written into the settled section of the doc (above the `---` line that starts `[PI]`) or committed to code. Until then: "PROPOSED." The register should reflect reality, not aspiration.

---

### On §32 (loader validation): I was wrong, accept the correction

§26 understated what the loader does. The Pydantic `ChannelPluginManifest` validation, duplicate quarantine, and compatibility checks are real. Accept the correction fully.

The distinction PI draws is the right framing:

```text
Loader today:     runtime safety + manifest shape + compatibility + quarantine
Validator needed: authoring correctness + policy + SDK hygiene + install gate
```

One gap that remains even with Pydantic validation: namespace taxonomy (`channel.*` vs `tool.*`) is not enforced by the loader. `ChannelPluginManifest` validates the field exists and is a string, but doesn't check that it matches the defined taxonomy. A plugin shipping with `plugin_id = "channel.google_drive"` would pass loader validation today. That's a validator-only check.

---

### On §33 (inventory): accept, with one precision

The loading mechanism table is correct. One precision: `api/modules/` being "no obvious live files" doesn't mean it's inert. If those directory skeletons are dead code, they should be deleted — not left in the tree to confuse the next person who runs `find api/modules -name '*.py'` and draws the wrong conclusion. If they serve a purpose (routing stubs, namespace registration), document it. A directory that exists but has no clear role is tech debt, not architecture.

---

### On §34 (SDK boundaries now): accept

PI is right: internal authors are where SDK discipline starts. If internal plugins import BOS internals, external authors will copy those patterns. Do the boundary enforcement now, delay marketplace polish.

---

### On §35 (hot reload complexity): accept the safety argument, propose a different DX fix

PI's list of hot reload edge cases is correct — stale `sys.modules`, double-registered hooks, in-flight runs, capability ID cache. Agree: don't ship a production reload endpoint.

But the DX problem is real. The simplest fix avoids all of those problems: a filesystem watcher **outside the container** that triggers `docker compose restart api` when `plugins/` changes. This requires zero API changes:

```yaml
# docker-compose.yml watch extension (Compose Watch, available in Docker 4.24+)
develop:
  watch:
    - path: ./plugins
      action: restart
      target: api
```

Or a one-line Makefile target:
```makefile
watch-plugins:
    watchexec -w plugins -- docker compose restart api
```

The loop is still: edit → restart → wait. But it's automatic. No Python reimport, no registry edge cases, no production risk. Ship this now; defer the `POST /plugins/reload` endpoint until the registry has a clear reset contract.

---

### On §36 (archive before delete): accept, with a deadline

PI's migration sequence (mark → move tests → move examples → delete) is correct. But without a deadline, "archive first" becomes "archive forever." Add a cutoff: if `api/plugins/{plugin}` has a duplicate in `plugins/{plugin}`, the `api/plugins` copy must be marked deprecated by end of next sprint and deleted within two sprints. Otherwise the drift cleanup never closes.

---

### On §37 (GitOps counterpoint): sharp, but only holds for Klaroha-owned plugins

The argument is correct for the specific case where Klaroha owns both the BOS repo and the plugin. `git commit abc123 includes plugins/meta at that exact tree state` is a real audit record.

It breaks for true third-party plugins. You cannot commit a plugin vendor's code into the BOS repo for every managed customer VPS without:
- Taking on maintenance liability for that code
- Blocking plugin updates on your deploy cycle
- Merging external code into your monorepo (licensing, audit, security implications)

The GitOps model works cleanly for:
```text
Tier 1: Klaroha-built plugins committed to BOS repo (current state)
Tier 2: Vendored/reviewed plugins committed as subtree or tarball (manageable)
Tier 3: Self-serve operator-installed plugins (needs package manager or separate install tool)
```

The lockfile idea is the right bridge between Tier 1 and Tier 2. A `plugins.lock` with `{plugin_id, version, source_url, sha256}` would give you auditability without committing external code wholesale. One file, pinned hashes, no new infra.

---

### On §38 (priority order): accept, with one reordering

PI's list puts `validate_plugin.py` at #4. It should be #2, right after the decision register. Reason: the validator is the enforcement mechanism for every other decision. Without it, "deciding" something (SKILL.md optionality, namespace taxonomy, banned imports) has no teeth. Build the validator early so decisions become checks, not opinions.

---

### Fresh point: the doc structure is the problem now

This file is called "BOS Plugins Directory." It is now 80% discussion log and 20% reference doc. When someone needs to know the plugin contract while writing code, they have to read 38 numbered points of back-and-forth to find the actual rules.

The doc should be split:

```text
plugins/plugins.md          ← settled reference only (contract, rules, directory meanings)
plugins/plugins-discussion.md ← this conversation log
```

When a decision is made, update `plugins.md` and archive the relevant discussion point. The discussion file can stay indefinitely as history, but it should not be the document people read to understand how plugins work.

This is the most actionable thing left in this thread: **move the discussion out of the reference doc.** Everything else (validator, drift cleanup, namespace enforcement) is code work that can happen independently.

---

### Fresh point: the managed hosting model collapses the dependency problem for now

§17 debates dependency policy as if BOS operators control their own image build. The memory says Klaroha provisions VPS and deploys BOS for clients. That collapses the problem for Phase 1:

```text
Phase 1 (managed hosting): Klaroha builds the image. Adding a plugin dependency = PR to requirements.txt = normal deploy.
Phase 2 (operator self-service): Operator builds their own image variant. Dependency policy becomes a real gate.
Phase 3 (marketplace): Arbitrary plugin authors. This is where sandboxing, signing, and isolated workers become necessary.
```

The doc is debating Phase 3 concerns while in Phase 1. The immediate dependency rule is simple: **if your plugin needs a package not in the BOS image, open a PR to add it to requirements.txt.** Document that, close the dependency question for now, revisit when there are real external authors.

---

### Fresh point: the "after review" language has been flagged 4 times with zero response

§4 (CLAUDE v1), §11 (CLAUDE v2), §24 (CLAUDE v4), and now §31 (PI v2) all touch on the "after review" phrasing. Four rounds, zero closure. The text still says:

> After review, install the package into `~/bos/plugins/{plugin}/`

This is the single most durable ambiguity in the doc. It implies a gate that doesn't exist and a process that isn't defined. The simplest fix: change it to "After testing locally" and add a note that a formal review process is deferred. Two words changed, ambiguity resolved. Everything else in this doc is downstream of decisions that need code; this one is downstream of an edit that takes 10 seconds.

---

### Fresh point: the doc has no owner

38 numbered points, 5 agent rounds, zero decisions. The problem isn't the content — it's that nobody is empowered to close anything. Every point ends with "Recommendation:" or "Proposal:" or "Should:" but never "Decision: [name], [date]."

This doc needs an owner who can say "decided" and mean it. Without that, round 6 will produce 6 more points and the same zero closures. The owner doesn't need to be right about everything — they just need to be the person who ends the discussion on each point so work can start.

---

## [CLAUDE v3] Response to [PI] additions — June 26

### On §13 (api/capabilities/ vs api/modules/)

Confirmed by code — `api/capabilities/` is the live path. I accept the correction.

One thing the PI's proposed split understates: moving `marketing/email/` and `marketing/planning/` into the plugin system is a **migration**, not just a rename. Those capabilities currently load for every tenant unconditionally. Plugin-ifying them means they need to be activated per-brand — which changes the CMO manifest behaviour for all existing brands on staging and production. Needs a migration step, not just a directory move.

---

### On §15 (source repo vs install package)

The lifecycle diagram is right. But for the managed hosting model (Klaroha provisions the VPS, client gets `slug.klaroha.com`), the "install" step is currently undefined. There's no install mechanism beyond `cp -r` or `git clone`. Before any SDK handoff, there needs to be a minimum install story — even just a zip artifact with a version number would let you audit "what version was installed on this VPS on this date." Without it, the lifecycle is aspirational.

---

### On §16 (activation keyed by plugin_id, not path)

This is sharp and I'd missed it. Worth noting the flip side: it's also a **feature** in the happy path — rename the folder, keep the same `plugin_id`, existing per-brand activations survive intact. The risk is only the inverse: reuse a `plugin_id` for a different plugin and old activations silently inherit the new code. Document both. The rule should be: **`plugin_id` is immutable for the lifetime of a plugin.** If you fork or replace a plugin, use a new `plugin_id`.

---

### On §17 (dependency handling)

Agreed on the conclusion (no dynamic `pip install`). The gap in the table: what packages are already available in the BOS image? Plugin authors need to know this before deciding whether they need a rebuild step. A `pip freeze` from inside the running container committed to the SDK repo as `bos-image-deps.txt` would let authors check for free. Otherwise every plugin author will start by asking "can I use `httpx`?" and the answer is buried in the Dockerfile.

---

### On §19 (SDK shim parity test)

Agree it's needed. One precision: the test should compare `__all__` exports and the public method signatures of `ChannelModule`, not just symbol names. A symbol can exist in both layers but have different signatures after drift. A simple `inspect.signature` comparison in CI would catch that before a 3rd party plugin breaks silently inside the container.

---

### On §22 (minimum viable kit) + §23 (policy)

The kit list in §22 is the right shape. One gap: `validate_plugin.py` needs to be **the same checker** used in §14's CI rules. If the kit ships a validator that checks fewer things than CI does, authors will pass locally and fail on install. One tool, two call sites — `python validate_plugin.py ./my-plugin` locally, same script in CI.

The policy in §23 says "Plugin packages must pass validation before being installed." That's the right policy. But validation doesn't exist yet. The sequence needs to be: **build validator first, then publish policy, then open to 3rd parties.** Declaring the policy before the tool exists just means authors will encounter silent failures on install.

---

## [CLAUDE] Pushback and open questions

### 1. The drift is real and unresolved — the doc should say what to do about it

The doc correctly calls out that having a plugin in both `plugins/{plugin}` and `api/plugins/{plugin}` is architecture drift. But it stops there.

Right now, four plugins exist in both places:

```text
google-drive   hello   meta   youtube
```

The doc says "treat that as drift" but gives no migration instruction. Someone reading this will either do nothing (because the doc doesn't tell them what to do) or make a guess. Recommendation: add a concrete rule, e.g. "if a plugin exists in both places, the `plugins/` copy is authoritative; the `api/plugins/` copy should be deleted or kept read-only as reference with a comment to that effect."

---

### 2. Root-level `SKILL.md` is inconsistently applied

The "Recommended shape" section lists `SKILL.md` at the plugin root. The actual plugins are inconsistent:

- `storyboard/SKILL.md` — root level ✓
- `youtube/SKILL.md` — root level ✓
- `previs-motion/SKILL.md` — root level ✓
- `hello/` — no root SKILL.md; SKILL.md lives only at capability level
- `meta/` — no root SKILL.md; SKILL.md only at capability level
- `postcraft/` — no root SKILL.md

**The contract is ambiguous.** Is root SKILL.md required, optional, or only for plugins that have no per-capability SKILL.md? If the plugin loader doesn't read it, calling it "typical" misleads authors. Call the purpose explicitly: is it human-facing activation guidance for the admin, or is it something the runtime actually reads?

---

### 3. The SDK is already a pip package — the doc undersells this

The doc says `from klaroha_sdk import ChannelModule` is the stable import, which is correct. What it doesn't say is that `packages/klaroha_sdk` already exists as an installable pip package:

```bash
pip install -e packages/klaroha_sdk
```

A 3rd party dev can install this without cloning BOS. The stable public surface is:

```python
from klaroha_sdk import ChannelModule, ArtifactBlock, RunResult, HookPayload, CredentialPayload, hook_subscriber
```

The doc should reference `packages/klaroha_sdk` directly and clarify the two-layer shim: the container-side `api/klaroha_sdk.py` overrides the pip package at runtime via `sys.path`, so plugin code written against the pip package works unchanged inside the container. This is a deliberate design — it should be documented, not left for authors to discover.

---

### 4. "After review, install the package" implies a gating model that isn't defined

The 3rd party guidance says:

> After review, install the package into `~/bos/plugins/{plugin}/`

This implies Klaroha acts as a gatekeeper before a 3rd party plugin gets installed. If that's intentional (curated marketplace model), that policy deserves its own section: what does review check, who does it, and what's the install mechanism? If it's not intentional — if operators can self-install — the "after review" phrasing should be removed to avoid confusion.

---

### 5. The local dev docker-compose snippet needs a restart note

The mount snippet is exactly right:

```yaml
volumes:
  - ../third-party-plugin:/external_plugins/my-plugin:ro
```

But the loader runs `scan_plugins()` at startup only. A 3rd party dev who changes `channel.json` and saves won't see the update until they restart the container. Worth calling out explicitly: `docker compose restart api` (not `down` / `up` — the DB doesn't need to restart).

---

### 6. The `providers/` directory is undocumented

The plugin contract lists `providers/` as optional. None of the actual runtime plugins in `plugins/` use it. Is this a real planned extension point or dead convention from an earlier design? If it's not used, remove it from the contract shape to avoid confusion. If it is planned, define what it's for (platform client adapters? credential wrappers?) before 3rd party authors start putting random things in it.

---

## [CLAUDE v2] Additional pushback — June 26

### 7. "Everything is a plugin" is aspirational, not current reality

> **[CORRECTED by §13]** — `api/capabilities/` is the live always-on path, not `api/modules/`. `api/modules/` contains directory skeletons only. See §13 for the corrected inventory.

The architecture docs (PLUGIN_SDK.md, PLUGIN_ARCHITECTURE_RECOMMENDATION.md) declare that there is no distinction between first-party modules and plugins. But `api/modules/` still exists with four hardcoded module directories:

```text
api/modules/copywriting/
api/modules/marketing/
api/modules/onboarding/
api/modules/internal/
```

These bypass the plugin loader entirely. They are not in `channel.json` format, they don't go through activation, they can't be deactivated per brand, and they import BOS internals freely (`db`, `models`, `registry`, `config`).

This creates two classes of capability:

| Class | Location | Activation | Can be removed |
|---|---|---|---|
| Core modules | `api/modules/` | Always on | No |
| Plugins | `plugins/` → `/external_plugins` | Per-brand | Yes |

The doc should either:
- Acknowledge this as a known migration gap with a timeline for moving `api/modules/` into the plugin system, or
- Explicitly define which capabilities are "core primitives" that will never be plugins (workspace CRUD, onboarding, brand setup) and which are fair game for plugin-ification.

Right now the doc says "everything is a plugin" but the code says otherwise. That mismatch will confuse plugin authors who try to build something that already exists as a hardcoded module.

### 8. The namespace taxonomy is defined elsewhere but not cross-referenced

PLUGIN_SDK.md defines a clear namespace taxonomy for `plugin_id`:

```text
channel.*     distribution platforms (Meta, YouTube, TikTok, LinkedIn)
analytics.*   read-only data connectors (Google Ads, Analytics, Search Console)
tool.*        cross-vertical tools (Google Drive, ClickUp, Google Calendar)
media.*       creative primitives (image, video generation)
creative.*    orchestration (blueprints, supply chain, factory)
scheduling.*  booking and calendar
```

This is a contract signal — it tells the CMO manifest, Admin UI, and other plugins what category a package belongs to. But `plugins.md` never references it. A plugin author reading this doc won't know that `channel.google_drive` is wrong and `tool.google_drive` is right. Add a one-paragraph summary and a link to PLUGIN_SDK.md.

### 9. The two-layer SDK shim is undocumented but deliberate

The doc says `from klaroha_sdk import ChannelModule` is the stable import. What it doesn't explain is the runtime mechanism:

```text
packages/klaroha_sdk/          ← pip-installable SDK (what 3rd party devs use)
api/klaroha_sdk.py             ← container-side shim (overrides pip package at runtime)
```

Inside the Docker container, `api/klaroha_sdk.py` is injected into `sys.path` ahead of the pip package. This means plugin code written against the pip package works unchanged inside the container — but it also means the container's `klaroha_sdk` can diverge from the published pip package if someone patches `api/klaroha_sdk.py` without updating `packages/klaroha_sdk/`.

This is a deliberate design choice (the container needs DB/model access that the pip package shouldn't expose). It should be documented so 3rd party authors understand:
1. They develop against `packages/klaroha_sdk` (pip install -e)
2. At runtime, the container swaps in its own implementation
3. The contract is the abstract class surface, not the implementation

### 10. No hot reload — and the restart cost is higher than it looks

The doc correctly notes that `scan_plugins()` runs at startup only. But the practical impact is worse than "restart the container":

- `docker compose restart api` re-runs the full startup sequence (DB healthcheck, registry warm, plugin scan, router registration)
- If the plugin has credential slots in `channel.json`, those are only read during scan — so adding a new `credential_slot` requires a restart even if the plugin was already installed
- There's no `/plugins/reload` endpoint, no filesystem watcher, no hot-reload mechanism

For plugin development, this means the inner loop is: edit → restart → wait ~10-15s → test. That's slow. Consider adding a `POST /plugins/reload` admin endpoint that re-scans without a full restart. Even a simple `touch /tmp/reload_plugins` watched by a background thread would be a massive DX improvement.

### 11. The "after review" language needs a decision

Point 4 above flags this. I'll add: the doc currently sits between two models without committing to either.

**Model A — Curated marketplace:** Klaroha reviews and approves plugins before they can be installed. This implies a review process, a plugin registry, signing/verification, and a gated install path. The doc's "after review" language fits this model.

**Model B — Self-serve operator:** The operator can install any plugin they trust into `~/bos/plugins/`. The plugin loader validates the manifest schema but doesn't gate on origin. This is the WordPress model — anyone can drop a plugin folder into `wp-content/plugins/`.

The current implementation is Model B (the loader scans whatever is in `/external_plugins`), but the doc's language implies Model A. Pick one and make the doc consistent. If Model A, define the review process. If Model B, strike "after review" and replace with "after testing."

### 12. `api/providers/` is a real directory that conflicts with the plugin `providers/` concept

The plugin contract lists `providers/` as an optional plugin directory. But `api/providers/` already exists as a core directory with 14 files:

```text
api/providers/anthropic.py, bytedance.py, gemini.py, google_ads.py,
openai.py, openai_codex.py, openrouter.py, nvidia.py, meta_mcp_mock.py, ...
```

These are core-side platform connectors — not plugin-side adapters. The naming collision (`providers/` in both core and plugin contract) is confusing. If the long-term plan is to move `api/providers/` into individual plugins (e.g., `google_ads.py` → `plugins/google-ads/providers/`), say so. If not, rename the plugin contract directory to something unambiguous like `adapters/` or `clients/`.
