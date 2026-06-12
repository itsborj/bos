# Backend Debug Task List — CMO Brain, Brand Onboarding, Drive, ByteDance Media, FB/YT Publishing

Date: 2026-06-11
Status: task list only — no fixes applied
Owner/lock: RESERVED FOR FUTURE MULTI-AGENT DEBUGGING WORK. Do not edit, implement, or remove items from this task list unless the user explicitly reopens this exact workstream.
Coordination note: Other agents may read this file for context, but should not touch the listed tasks or related fixes without explicit user approval.

## Goal

Make the operator workflow reliable end-to-end:

1. Brand onboarding creates correct brand-scoped context.
2. CMO chat uses OpenAI premier/released models, not stale hard-coded defaults.
3. CMO can generate image/video artifacts with ByteDance/BytePlus.
4. Artifacts store/reload through the brand's Google Drive folder.
5. Approved artifacts can publish to Facebook and YouTube.

---

## P0 — Must unblock first

### 1. Fix active-plugin CMO chat crash
- Evidence: `api/routers/chat.py` references `plugin.manifest.requires_social_connection`, but manifests use `credential_slots`.
- Verify with active plugins: Google Drive, Meta, YouTube, Creative Factory, media image/video.
- Expected: CMO prompt builds without AttributeError and includes only brand-active capabilities.

### 2. Verify runtime plugin installation/activation shape
- Confirm required plugins are installed in `/external_plugins`, not only bundled under `api/plugins/`.
- Required plugin IDs:
  - `google.drive`
  - `channel.meta`
  - `channel.youtube`
  - `creative.factory`
  - `media.image`
  - `media.video`
- Confirm each is active for the target Brand.

### 3. Fix OpenAI live adapter mismatch
- Evidence: `api/executor.py` passes `extra_body`; `OpenAIAdapter` and `OpenAICodexAdapter` do not accept it.
- Expected: direct OpenAI, BYOK OpenAI, and OAuth OpenAI runs do not fail with `unexpected keyword argument 'extra_body'`.

### 4. Replace/override hard-coded CMO brain model list
- Evidence: `api/routers/chat.py` has `_CHAT_MODELS` with fixed model IDs.
- Desired: CMO brain uses configured OpenAI premier/released model from Admin/backend override or live catalog.
- Verify `cmo.main` backend override works before fallback list.

### 5. Fix brand-scoped AI BYOK credential resolution
- Evidence: workspace-level AI API keys can be ignored for brand-scoped runs.
- Expected: OpenAI key saved in Admin works for brand-scoped CMO chat/runs.

---

## P1 — ByteDance image/video generation

### 6. Verify ByteDance API key injection for image generation
- `media.image.generate` defaults to `bytedance`.
- Ensure `provider_api_key` is injected through backend override/env/provider key path.
- Expected: ByteDance image generation succeeds without needing OpenAI/Gemini.

### 7. Add/verify ByteDance provider options for video generation
- Code supports provider `bytedance`.
- `media-video/channel.json` provider options currently emphasize `gemini`, `seedance`, `custom`.
- Expected: Admin UI can select ByteDance/ModelArk video provider and model.

### 8. Validate ByteDance model IDs
- Image defaults/options need confirmation against actual BytePlus ModelArk model IDs.
- Video requires explicit `video_gen_model`; missing model currently fails.
- Expected: chosen Seedream/Seedance IDs match live BytePlus API.

### 9. Confirm generated video storage path
- `media.video.generate` should upload to Google Drive when Drive token/root are present.
- Expected block fields: `drive_file_id`, `drive_web_view_link`, `drive_folder`, reusable asset state.

### 10. Decide image storage route
- `media.image.generate` returns bytes but does not store to Drive.
- `creative.post.image` generates/stores Meta-ready images.
- Expected CMO behavior: for Facebook image posts, dispatch `creative.post.image`, not raw `media.image.generate` unless user asks for an image asset only.

---

## P2 — Google Drive folder connection and artifact plane

### 11. Fix Drive folder setup root mismatch
- `drive.folder.setup` expects `brief["root_folder_id"]`.
- Credential injection puts root at `_channel_credentials.drive_root_folder_id`.
- Expected: setup works after operator picks Drive root.

### 12. Remove hard-coded `/app/plugins/google-drive/drive_client.py` dependency
- External plugin mode may place Drive plugin under `/external_plugins`.
- Affected modules include:
  - `creative.post.image`
  - `media.video.generate`
- Expected: modules locate Drive client in external/internal plugin mode reliably.

### 13. Verify Drive picker prerequisites
- `/social/drive/picker-config` needs:
  - Google Drive connected for brand
  - `GOOGLE_PICKER_API_KEY`
  - valid `GOOGLE_CLIENT_ID` app id
- Expected: operator can pick brand root folder from Admin UI.

### 14. Verify generated assets are discoverable in Drive browser
- Generated paths:
  - `Creative Assets/Meta Posts`
  - `Creative Assets/Video`
- Check whether UI searches nested folders or only direct children.
- Expected: generated assets are visible/selectable for publish actions.

### 15. Verify Drive reload for publish actions
- Image path: `drive_file_id` → `_image_data_b64` before Meta publish.
- Video path: `drive_file_id` → temporary `video_path` before Meta/YouTube publish.
- Expected: publish still works after local `/tmp` files are gone.

---

## P3 — Facebook publishing

### 16. Verify Facebook connection and credential injection
- Meta publish needs `facebook_page_token`/`page_token` and `facebook_page_id`/`page_id`.
- Expected: brand-scoped Facebook page connection injects both token and page ID.

### 17. Verify Facebook image publish path
- Intended flow:
  1. CMO dispatches `creative.post.image`.
  2. Artifact stores image in Drive.
  3. User approves/publishes.
  4. Action runs `marketing.channel.meta.posts.publish`.
- Expected: caption/message is preserved and image is uploaded to Facebook Photos API.

### 18. Verify Facebook video publish path
- Intended flow:
  1. CMO dispatches `media.video.generate`.
  2. ByteDance creates video.
  3. Video stores in Drive.
  4. User approves/publishes to Facebook.
  5. Action runs `marketing.channel.meta.video.publish`.
- Expected: generated/reloaded MP4 is uploaded to Facebook Videos API.

### 19. Prevent bad direct-publish from raw image artifact
- Raw `media.image.generate` has `publish_facebook` action, but may not include good caption/message.
- Expected: either remove/adjust that action or ensure a valid message is required before publishing.

---

## P4 — YouTube publishing

### 20. Verify YouTube OAuth connection and credential injection
- YouTube video publish needs `youtube_page_token`/`page_token`/`access_token`.
- Expected: brand-scoped YouTube connection injects a valid upload token.

### 21. Verify YouTube video publish path
- Intended flow:
  1. CMO dispatches `media.video.generate`.
  2. ByteDance creates video.
  3. Video stores in Drive.
  4. User approves/publishes to YouTube.
  5. Action runs `marketing.channel.youtube.video.publish`.
- Expected: video uploads with title, description, privacy, tags.

### 22. Decide YouTube image requirement
- Current YouTube plugin has video publish only.
- No YouTube community/image post module exists.
- Expected decision: either add YouTube image/community post support or mark it out of scope.

---

## P5 — Brand onboarding and CMO context

### 23. Make onboarding status brand-scoped
- Current status can mark ready using workspace-wide/any-brand context.
- Expected: selected Brand must have brand profile, product, audience, and approved kit.

### 24. Fix onboarding module readiness false negatives
- Current onboarding status routes every module through LLM capability router.
- Tool/plugin modules may appear not ready even when credentials are correct.
- Expected: readiness checks plugin activation + credential slots + provider overrides appropriately.

### 25. Verify Campaign Brand Kit per-brand lookup
- `/onboarding/brand-kit/latest` defaults to `brand_id IS NULL` when no brand_id passed.
- Expected: selected brand UI always passes brand_id, and CMO context loads the correct kit.

### 26. Avoid legacy workspace-only onboarding for multi-brand workflows
- Ingest without `brand_id` writes `Workspace.brand_json` and brandless product/audience rows.
- Expected: multi-brand onboarding creates/updates Brand rows and brand-scoped product/audience rows.

### 27. Verify CMO active brand context after onboarding
- CMO should use selected Brand profile/products/audiences/docs only.
- Expected: no cross-brand bleed from workspace fallback or chat history.

---

## P6 — Existing backend safety bugs to keep in scope

### 28. Public/default secrets can deploy
- `deploy-staging.sh` can copy default secrets from `.env.example`.

### 29. ClickUp webhook accepts unauthenticated mutation if secret missing
- Should fail closed unless a webhook secret is configured.

### 30. Migration 039 can delete valid multiline user data
- Regex treats normal control characters like newlines as fuzzer garbage.

### 31. Per-brand plugin deactivate demotes org-wide activation
- Deactivating one brand should not disable all other brands.

### 32. Plugin connection metadata creates fake `CLIENT_ID` / `CLIENT_SECRET` requirements
- Lightweight built-in connection declarations should not require generic OAuth vars.

### 33. Legacy plugin credential conversion can quarantine old plugins
- Converted slots need valid `key` values.

### 34. Plugin version comparison is lexicographic
- Use semantic version comparison.

### 35. Activation endpoints should verify brand existence before DB commit
- Return clean 404/422 instead of FK commit failure.

### 36. Invalid `GET /plugins?brand_id=` should not fall back to global readiness
- Return 422 for invalid brand_id.

### 37. Multi-social-token readiness should require all required tokens
- Example: Meta + Google Drive should not show ready when only one is connected.

---

## Suggested multi-agent work split

### Agent A — CMO brain + OpenAI routing
- Tasks: 1, 3, 4, 5.
- Validate CMO chat with OpenAI configured as `cmo.main`.

### Agent B — Plugin activation + credential readiness
- Tasks: 2, 16, 20, 31, 32, 35, 36, 37.
- Validate installed/active plugins and per-brand credential state.

### Agent C — Google Drive artifact plane
- Tasks: 11, 12, 13, 14, 15.
- Validate Drive root selection, upload, browse, reload.

### Agent D — ByteDance media generation
- Tasks: 6, 7, 8, 9, 10.
- Validate ByteDance image/video end-to-end.

### Agent E — Facebook/YouTube publish flows
- Tasks: 17, 18, 19, 21, 22.
- Validate approved artifact actions.

### Agent F — Brand onboarding + CMO context isolation
- Tasks: 23, 24, 25, 26, 27.
- Validate onboarding through CMO context hydration.
