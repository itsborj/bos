# creative-factory — Plugin Notes

Regression-prevention notes for the creative supply chain plugin. Architecture: `CREATIVE_SUPPLY_CHAIN.md`.

---

## Invariants

- **Every module MUST declare `platform_hint`.** `registry.list_all()` calls `module_info()` on every registered module at app startup, and `module_base.ModuleBase.module_info()` reads `self.platform_hint` (a `ClassVar[str]` with no default). A module missing it raises `AttributeError` and crashes the entire app on startup — not just the plugin. Same applies to `id`, `vertical`, `capability`. `template` is only read at execution (`build_prompt`), so modules that override `execute_tool_result` and build dicts directly do not strictly need it to boot — but they still need `platform_hint`.

- **BOS generates nothing natively.** Every module here builds a request for a third-party provider (image gen, video gen, render/stitch) and captures the result. No module performs generation or rendering in-process beyond local FFmpeg invocation. See CREATIVE_SUPPLY_CHAIN.md → BOS Role in This Pipeline.

- **AI content and brand assets are separate files.** They are never merged inside an AI provider. The CompositionSpec layers them; the render provider stitches them. Do not build a path that sends a brand logo into an image-generation prompt.

---

## Fixed bugs (pattern → fix)

- **2026-05-23 — App startup crash: `'CreativeBlueprintAssembleModule' object has no attribute 'platform_hint'`.** The three scaffolded modules (`pack/generate`, `primitive/generate`, `blueprint/assemble`) were created without `platform_hint`. Latent because the app only re-scans modules on (re)start/reload; surfaced when an unrelated file edit triggered a watchfiles reload. Fix: added `platform_hint` to all three. Lesson: any new module class needs the full required ClassVar set before the next reload, or the whole app goes down.

---

## creative.post.image (CMO-dispatchable, generate + store)

- **What it does:** CMO chat → generate a Meta post visual creative → store in the brand's Drive under `Creative Assets/Meta Posts/`. Does NOT publish. `allowed_from_chat: true`, in the capability manifest.
- **Image generation is declarative, not hardcoded:** the module sets `requires_generated_image = True` (a `ModuleBase` ClassVar). `runs.py` fires the `media.image.generate` hook for any module with that flag OR an `image_prompt` — so the CMO does NOT have to pass `image_prompt` (media.image builds one from the brand brief as fallback). Generic mechanism; no capability id hardcoded in core.
- **Drive token + root injection:** the plugin declares `requires_social_connection: ["google_drive"]`, so `inject_channel_credentials` injects the google_drive `page_token` AND (new) the `drive_root_folder_id`/`drive_root_name` from the connection's `token_meta_json`. The module loads `drive_client` from `/app/plugins/google-drive/drive_client.py` (absolute path — cross-plugin) and uploads under the picked root.
- **Validated 2026-05-24:** live `/chat` "make an image for a Facebook post…" with brand active → dispatched creative.post.image → image generated from brand brief → stored to Drive (`meta_post_*.png`). Two files confirmed in the operator's real `Creative Assets/Meta Posts/`.
- **Gotcha:** if `image_prompt` absent AND `requires_generated_image` False → no image → fails. The flag is what makes chat-without-explicit-prompt work.

## Local backlog

- The three scaffolded modules (`pack/generate`, `primitive/generate`, `blueprint/assemble`) are stubs from an earlier session. They will be rebuilt in Phase B against the locked architecture: `pack/generate` creates a `creative_job` and returns immediately (async), `primitive/generate` routes to the configured image provider and writes `creative_assets`, `blueprint/assemble` emits a full CompositionSpec JSON (not the current slot-mapping dict).
- `channel.json` `capability_ids` will gain `creative.render.*` capabilities as Phase C lands.
