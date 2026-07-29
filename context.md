# Code Context

## Files Retrieved
1. `plugins/plugins.md` (lines 17-52) - locked plugin rules: Drive-first persistence; Drive/root/logo preflight before provider spend; generators do not own publishing.
2. `PROJECT_BRIEF.md` (lines 62-75) - locked brand/plugin/workflow rules, especially one Brand Kit Drive folder and typed module actions.
3. `api/main.py` (lines 45-108) - FastAPI mounts core routers, then dynamically discovered plugin routers.
4. `api/plugin_loader.py` (lines 1-31, 112-163, 212-346, 482-516, 580-782) - runtime plugin root, manifest types, dynamic API mounting, credential-slot resolution, and hook registration.
5. `api/registry.py` (lines 19-51) - recursively imports every plugin `capabilities/**/module.py` and registers IDs, including IDs omitted from `channel.json`.
6. `nginx.conf` (lines 66-96) and `web/src/api/client.ts` (lines 44-46) - browser uses `/api`; nginx strips that prefix before FastAPI. OAuth callbacks are also exposed directly under `/social/`.
7. `plugins/google-drive/api.py` (lines 1-230, 241-320, 361-456, 550-779) - Drive OAuth callback, read/upload routes, root validation, and persisted metadata.
8. `plugins/google-drive/channel.json` (lines 1-48) - Drive credential slots and capability IDs.
9. `plugins/google-drive/drive_client.py` (lines 23-245) - live Drive REST client methods.
10. `plugins/google-drive/capabilities/drive/folder/setup/module.py` (lines 1-76), `drive/asset/list/module.py` (lines 1-67), `drive/asset/get/module.py` (lines 1-72), and `drive/asset/upload/module.py` (lines 1-74) - module-level Drive surfaces and required brief inputs.
11. `api/models/social.py` (lines 1-38), `api/models/workspace.py` (lines 1-43), and `api/models/provider.py` (lines 1-36) - exact DB storage for Brand, Drive connection, and media provider credentials.
12. `api/services/brand_kit.py` (lines 1-132) - maps Drive/onboarding metadata to `brand_spec` and hydrates image/video briefs.
13. `api/routers/cmo_tools.py` (lines 1114-1204) - structured `brand_kit` built from `brands.brand_json`, Drive metadata, and document fallback.
14. `api/routers/onboarding.py` (lines 55-330, 1282-1331) - read-only readiness endpoint, readiness calculation, and Drive/logo metadata projection.
15. `api/routers/documents.py` (lines 67-164, 238-281) - Brand Creative Brief approval requires cached plus live Drive folder/logo validation.
16. `api/routers/brands.py` (lines 1-202, 226-378) and `api/schemas/brands.py` (lines 1-38) - public Brand fields and Brand Kit resource/template routes.
17. `api/routers/social.py` (lines 1-114, 167-259, 1057-1134) - Google Drive OAuth start, connection listing, and disconnect routes.
18. `api/routers/runs.py` (lines 270-378, 699-741, 876-1008) - brand asset/credential/hook hydration order and generic persisted-artifact action execution.
19. `plugins/postcraft/api.py` (lines 1-104) - Postcraft HTTP adapter routes and request shapes.
20. `plugins/postcraft/channel.json` (lines 1-124) and `plugins/postcraft/hooks.py` (lines 1-47, 57-126, 201-312) - declared backend/Drive slots and Campaign V2/template pre-dispatch hook.
21. `plugins/postcraft/capabilities/postcraft/render/module.py` (lines 88-112, 235-263, 267-378, 796-821, 1083-1089, 1221-1432) - actual hard preflight, approval gate, provider key gate, Drive-first upload, actions, and artifact output.
22. `plugins/postcraft/capabilities/postcraft/draft/module.py` (lines 149-217, 291-389) - zero-provider draft module, its readiness gate, and transition metadata.
23. `plugins/postcraft/ARCHITECTURE.md` (lines 17-96) - intended two-stage and brand preflight contract; useful for identifying drift from the live manifest/API.
24. `plugins/storyboard/api.py` (lines 1-59) - Storyboard HTTP adapter routes and request shapes.
25. `plugins/storyboard/channel.json` (lines 1-131) - declared image backend/Drive slots, capability IDs, and storyboard-to-Previs workflow.
26. `plugins/storyboard/capabilities/storyboard/json/render/module.py` (lines 90-286, 289-511) - actual live image module; provider/Drive preflight, non-blocking logo injection, provider call, strict Drive upload.
27. `plugins/storyboard/lib/json_image_storyboard.py` (lines 1681-1758) - older/core helper has the stronger logo and approval preflight that the live render module does not call.
28. `plugins/storyboard/capabilities/storyboard/json/generate/module.py` (lines 1-29) and `plugins/storyboard/storyboard.md` (lines 1-109) - `storyboard.generate` is an image-render alias; docs still describe a missing `storyboard.create` text module.
29. `plugins/previs-motion/api.py` (lines 1-75) - Previs Motion HTTP adapter routes and request shapes.
30. `plugins/previs-motion/channel.json` (lines 1-130) - declared video backend, provider options, Drive slots, capability IDs, and gates.
31. `plugins/previs-motion/capabilities/storyboard/motion/render/module.py` (lines 173-212, 544-689, 692-720, 969-1172, 1175-1234) - actual video preflight, provider execution, Drive-first enforcement, and output actions.
32. `web/src/components/DriveFolderPicker.tsx` (lines 1-127) and `web/src/pages/admin/AdminBrandDetail.tsx` (lines 410-494) - UI folder/logo validation and creative-readiness checklist.
33. `web/src/pages/admin/AdminClientReadiness.tsx` (lines 1-45, 55-101, 160-190) - aggregate UI readiness; notably treats Drive root name as ready without checking `brand_mark_configured`.
34. `web/src/api/client.ts` (lines 475-659) - confirms the browser calls the plugin and Drive routes below.
35. `api/tests/test_google_drive_brand_kit_index.py` (lines 1-116), `api/tests/test_document_brand_kit_approval.py` (lines 1-100), `api/tests/test_storyboard_quality_gate.py` (lines 1-190), `api/tests/test_previs_motion_modelark_payload.py` (lines 1-220), and Postcraft MIME/revision tests - safe unit coverage used during scouting.

## Key Code

### Canonical external paths
FastAPI paths below omit the deployment proxy prefix. Browser/deployed calls use `/api<path>` because `web/src/api/client.ts:44` sets `BASE = '/api'` and `nginx.conf:69-72` strips it. The OAuth callback is additionally routed directly as `/social/...` (`nginx.conf:90-96`). All operational routes except callbacks/thumbnail require `X-API-Key`; thumbnail accepts `api_key` query auth.

#### Brand/readiness and integration
| Method | FastAPI path | Inputs / behavior | Credit-safe? |
|---|---|---|---|
| GET | `/onboarding/status?brand_id={uuid}` | Read-only aggregate: profile, approved kit, live campaign, Drive/brand mark, providers, module readiness (`api/routers/onboarding.py:55-330`). | Yes |
| GET | `/brands/{brand_id}` | Public Brand profile fields (`api/routers/brands.py:134-146`). | Yes |
| GET | `/brands/{brand_id}/brand-kit/resources` | Indexed resources/template manifest (`api/routers/brands.py:295-312`). | Yes |
| PATCH | `/brands/{brand_id}/brand-kit/resources/classify` | Mutates resource classifications (`api/routers/brands.py:314-337`). | No provider credit, but mutates DB |
| PATCH | `/brands/{brand_id}/brand-kit/templates/bulk` | Mutates template manifest (`api/routers/brands.py:339-355`). | No provider credit, but mutates DB |
| PATCH | `/brands/{brand_id}/brand-kit/templates/{template_id}` | Mutates one template (`api/routers/brands.py:357-378`). | No provider credit, but mutates DB |
| POST | `/workspace/documents/{document_id}/approve` | Approves document; a brand-scoped `campaign_brand_kit` triggers live Drive root/logo checks (`api/routers/documents.py:136-164,275-281`). | No AI credit, but mutates DB and calls Drive metadata API |
| POST | `/social/connect/start` | `{brand_id, platform:"google_drive"}`; creates OAuth session/relay URL (`api/routers/social.py:167-259`). | No AI credit, but mutates DB/auth flow |
| GET | `/social/google-drive/callback` | Plugin-owned OAuth/relay callback (`plugins/google-drive/api.py:135-230`). | OAuth only |
| GET | `/social/connections?brand_id={uuid}` | Read-only connection rows/status (`api/routers/social.py:1057-1083`). | Yes |
| DELETE | `/social/connections/{connection_id}` | Disconnects (`api/routers/social.py:1085-1104`). | Mutating |

#### Google Drive plugin HTTP adapter
| Method | Path | Inputs / behavior |
|---|---|---|
| GET | `/social/drive/folders?brand_id={uuid}&parent_id={id?}` | Lists folders; without `parent_id`, returns saved root and its children (`plugins/google-drive/api.py:361-406`). |
| GET | `/social/drive/images?brand_id={uuid}&folder_id={id?}&media_type=image|video|document|all&q={text?}` | Read-only recursive file search (`plugins/google-drive/api.py:409-456`). |
| GET | `/social/drive/thumbnail/{file_id}?brand_id={uuid}&api_key={key}` | Authenticated image-only proxy/cache (`plugins/google-drive/api.py:550-582`). |
| POST | `/social/drive/reference-upload` | JSON `{brand_id,file_name,mime_type,data_b64}`; max 10 MB image; writes `CMO References` and persists reference (`plugins/google-drive/api.py:584-640`). |
| POST | `/social/drive/attachment-upload` | multipart `brand_id`, `file`; max 25 MB; supported images/docs; writes `CMO References` (`plugins/google-drive/api.py:642-706`). |
| POST | `/social/drive/root` | JSON `{brand_id,folder_id,folder_name?,folder_path?}`; validates and stores canonical root (`plugins/google-drive/api.py:709-779`). |

Root validation is meaningful, not just selection: `folder_id="root"` is rejected; the target must be a Drive folder; images are searched recursively; at least one filename matching tokenized `logo|wordmark|brandmark|mark` is required. On success it stores `drive_root_folder_id`, `drive_root_name`, `drive_root_path`, and full `imprint_asset_validation` in `social_connections.token_meta_json` (`plugins/google-drive/api.py:709-769`).

Drive modules registered by capability scan are `drive.folder.setup`, `drive.asset.upload`, `drive.asset.list`, and `drive.asset.get`. Their brief inputs are respectively root/campaign, `parent_folder_id+filename+content_b64`, `parent_folder_id(+mime_type)`, and `file_id(+include_bytes)` (`plugins/google-drive/capabilities/**/module.py`). Setup/upload are mutating; list/get are non-credit reads.

#### Generator plugin adapters
| Plugin | Method/path | Request | Dispatch |
|---|---|---|---|
| Postcraft | POST `/postcraft/runs/{run_id}/render` | `{confirm:true,overrides:{}}`; `confirm:false` returns `CONFIRM_REQUIRED` before action execution | persisted artifact action `render` |
| Postcraft | POST `/postcraft/runs/{run_id}/revise` | `{feedback,references,overrides}` | action `revise`; maps feedback to three revision fields and references to `operator_references` |
| Postcraft | GET `/postcraft/campaign-alignment?brand_id={uuid}&campaign_id={uuid?}` | read-only; explicit campaign or exactly one active campaign; 409 if ambiguous | Campaign V2 rows only |
| Storyboard | POST `/storyboard/runs/{run_id}/render` | `{confirm:true,overrides:{}}`; false safely rejects | persisted action `render` |
| Storyboard | POST `/storyboard/runs/{run_id}/revise` | `{feedback,references,overrides}` | action `revise` |
| Previs Motion | POST `/previs-motion/runs/{run_id}/generate-video` | `{confirm:true,overrides:{}}`; false safely rejects | persisted action `generate_video` |
| Previs Motion | POST `/previs-motion/runs/{run_id}/regenerate` | same; false safely rejects | action `regenerate` |
| Previs Motion | POST `/previs-motion/runs/{run_id}/revise` | `{feedback,references,overrides}` | action `revise` |
| Generic equivalent | POST `/runs/{run_id}/actions/{action}` | `{confirm,overrides}` | same generic action executor (`api/routers/runs.py:876-1008`) |

**Warning:** none of the three `/revise` plugin routes has a `confirm` guard. Do not use revisions for a readiness probe; a valid run can spend image/video credits. All action routes require the persisted artifact block to include the requested action in `allowed_actions` and map it in `action_modules`; an arbitrary run ID will not dispatch (`api/routers/runs.py:707-721,876-914`).

### Required DB and hydrated fields

#### Shared Brand/Drive readiness
1. `brands`: valid `id`, `workspace_id`, non-placeholder `name`, and `brand_json` (`api/models/workspace.py:21-32`). Public create/update only exposes `voice`, `tone`, `values`, `domain`, `website_url`, `social_handles`, and `pm_config` (`api/schemas/brands.py:4-38`), while creative hydration also reads optional `brand_json.color_palette|colors`, `visual_language|visual_tone`, `typography`, `mandatory_treatments`, and `negative_prompts` (`api/routers/cmo_tools.py:1188-1204`).
2. A brand-scoped `social_connections` row with `platform='google_drive'`, `status='connected'`, nonempty encrypted token, and that Brand's `brand_id` (`api/models/social.py:12-35`).
3. `social_connections.token_meta_json.drive_root_folder_id`, normally `drive_root_name`/`drive_root_path`, and `imprint_asset_validation.logo_files[0].id`. The latter is transformed to `brand_spec.logo_drive_file_id`; root becomes `brand_spec.drive_root_folder_id` (`api/services/brand_kit.py:20-48`). Optional reference groups become up to five `brand_visual_assets` (`api/services/brand_kit.py:50-85`).
4. Latest brand-scoped `workspace_documents` row with `doc_type='campaign_brand_kit'` is a fallback source for the same root/logo metadata. Product/UI readiness expects it approved; approval is blocked unless the root and indexed logo both still exist live (`api/services/brand_kit.py:103-128`; `api/routers/documents.py:67-164`).
5. Provider credentials live in `provider_keys` (`workspace_id`, optional `brand_id`, `provider`, `auth_mode`, `key_encrypted`, optional refresh/expiry metadata) (`api/models/provider.py:9-31`). Backend provider/model is resolved through per-module backend override or manifest default, then provider credential injection (`api/plugin_loader.py:653-779`).
6. The plugin must be installed and explicitly active for the Brand. Directory presence only means installed (`plugins/plugins.md:17-24`; `api/routers/onboarding.py:228-307`).

#### Postcraft live hard gate
`_postcraft_preflight` requires all of the following before `_run_pipeline`:
- structured `brand_kit.brand_id`;
- real `brand_kit.brand_name|name` (not empty/`brand`/`this brand`/`this business`);
- at least one style signal: colors, visual tone, tone, voice, or visual constraints;
- Drive token in `_channel_credentials.google_drive_page_token|page_token|access_token`;
- Drive root in credentials or `brand_spec.drive_root_folder_id`;
- `brand_spec.logo_drive_file_id`;
- `campaign_alignment` plus a nonempty campaign ID (`plugins/postcraft/capabilities/postcraft/render/module.py:301-327`).

Then render additionally requires explicit approval (`render_approved`, `approved_draft`, render/revise action, approved status, or approved prior draft) and an image provider key (`plugins/postcraft/capabilities/postcraft/render/module.py:88-112,1282-1334`). Campaign truth is rebuilt in the `brief.before_dispatch` hook from an explicit campaign or exactly one active campaign; copied caller alignment is removed first (`plugins/postcraft/hooks.py:283-312`). A generated image is not successful unless Drive upload returns `drive_file_id` (`plugins/postcraft/capabilities/postcraft/render/module.py:1083-1089`).

The zero-provider `postcraft.draft` module reports `provider='none'`, `provider_cost=0`, but currently applies the same full Drive/logo/campaign gate before producing text (`plugins/postcraft/capabilities/postcraft/draft/module.py:291-338`). Templates are optional unless the caller explicitly supplies `template_id` or `auto_select_template`; the hook does not auto-select on ordinary renders (`plugins/postcraft/hooks.py:246-283`).

#### Storyboard live hard gate (important gap)
The active `storyboard.render` module requires only:
- `storyboard_text`;
- an image provider key;
- Google Drive token;
- credential `drive_root_folder_id` (`plugins/storyboard/capabilities/storyboard/json/render/module.py:237-252,346-371`).

It resolves `brand_spec.logo_drive_file_id` and attempts to download it, but `_inject_logo_reference` catches every failure and returns existing references; the call site explicitly says logo injection is non-blocking, then calls the image provider (`plugins/storyboard/capabilities/storyboard/json/render/module.py:137-169,385-473`). Therefore **live Storyboard is not compliant with locked rule 16**: a missing/stale logo does not stop credit spend. It also has no internal approval boolean gate; safety depends on the persisted artifact transition or CMO behavior. Drive-first after generation is enforced: missing uploaded `drive_file_id` returns `drive_storage_unavailable` (`module.py:481-486`).

There is a stronger `_storyboard_preflight` in `plugins/storyboard/lib/json_image_storyboard.py:1681-1714` that requires spec, Drive token/root, official logo, and render approval, but the live `StoryboardRenderModule.execute_tool_result` above does not invoke it.

#### Previs Motion live hard gate
Before any video provider call, `storyboard.motion.render` requires:
- provider credential (`provider_api_key`/Gemini key or `ark_api_key|byteplus_api_key`);
- Google Drive token;
- credential `drive_root_folder_id`;
- `brand_spec.logo_drive_file_id` (`plugins/previs-motion/capabilities/storyboard/motion/render/module.py:590-611,989-1005`).

It then resolves mode/input: V2V needs a reference video, I2V needs source image/path/base64, while T2V can run from text/spec. The HTTP `generate-video` path is safer because generic action dispatch requires a declared action from an approved/persisted storyboard artifact. Successful provider output is still failed and local cache removed if Drive upload does not return `drive_file_id` (`module.py:1159-1170`). The output exposes `revise -> storyboard.motion.edit` and `regenerate -> storyboard.motion.render` (`module.py:1175-1234`).

### Manifest/module/hook drift that affects readiness
- Runtime discovery recursively imports every capability module and appends actual IDs (`api/registry.py:28-45`; `api/plugin_loader.py:394-402`). Consequently Postcraft's live tree includes `postcraft.draft`, `postcraft.create`, and `postcraft.render`, although `channel.json` declares only `postcraft.render` (`plugins/postcraft/channel.json:20-27`). Readiness/manifests can under-report the extra modules.
- Storyboard docs describe `storyboard.create`, but no such module exists in the live tree or API. `storyboard.generate` is merely an image-render alias (`plugins/storyboard/capabilities/storyboard/json/generate/module.py:1-29`); manifest declares only `storyboard.render` and `storyboard.validate` (`plugins/storyboard/channel.json:62-66`).
- Storyboard's workflow points `generate_video` at another plugin's `storyboard.motion.render` and stage `previs_motion_review` (`plugins/storyboard/channel.json:95-111`). If Previs is inactive/missing, the action is advertised but generic execution returns `ACTION_MODULE_NOT_FOUND` (`api/routers/runs.py:900-914`).
- Postcraft alone subscribes to `brief.before_dispatch`; Storyboard and Previs rely on generic core brand-asset hydration plus credential slots (`api/routers/runs.py:293-355`).
- Aggregate `/onboarding/status` is stricter/different from execution: it requires every registered module ready, an approved kit, live campaign, brand mark, and some provider (`api/routers/onboarding.py:309-324`). Its plugin check also evaluates required `platform_var`s and explicit backend override/provider connectivity (`lines 228-288`), which can disagree with manifest defaults/fallback credential behavior.
- Admin Client Readiness is weaker than both the API and generator gate: it considers Drive ready from connected status + root name and ignores `status.brand_mark_configured` (`web/src/pages/admin/AdminClientReadiness.tsx:25-45,171-186`). Brand Detail's creative-readiness checklist does check an official logo (`web/src/pages/admin/AdminBrandDetail.tsx:469-480`).

### Safe non-credit tests

Verified in this checkout (all provider/Drive calls mocked or absent):
```bash
cd /home/ubu/bos
pytest -q api/tests/test_previs_motion_modelark_payload.py \
  api/tests/test_storyboard_quality_gate.py \
  api/tests/test_google_drive_pagination.py
# 45 passed

pytest -q api/tests/test_google_drive_brand_kit_index.py \
  api/tests/test_document_brand_kit_approval.py
# 14 passed (one Pydantic deprecation warning)

pytest -q api/tests/test_postcraft_artifact_mime.py \
  api/tests/test_postcraft_codex_image_parser.py \
  api/tests/test_postcraft_render_mime.py \
  api/tests/test_postcraft_revision_routing.py
# 8 passed
```

Do not bundle `api/tests/test_postcraft_brand_templates.py` into the above command in this Pi environment: collection currently resolves the repo-local `sqlalchemy` shim and fails importing `or_`; this is an environment/path issue, not a provider call.

Safe live probes (no generation credits):
```bash
# Confirm actually mounted plugin paths from the running deployment.
curl -sS "$BASE/openapi.json" | jq -r '.paths|keys[]' \
  | grep -E '^/(social/drive|postcraft|storyboard|previs-motion|onboarding/status)'

curl -sS -H "X-API-Key: $KEY" \
  "$BASE/api/onboarding/status?brand_id=$BRAND_ID"
curl -sS -H "X-API-Key: $KEY" \
  "$BASE/api/social/connections?brand_id=$BRAND_ID"
curl -sS -H "X-API-Key: $KEY" \
  "$BASE/api/brands/$BRAND_ID/brand-kit/resources"
curl -sS -H "X-API-Key: $KEY" \
  "$BASE/api/postcraft/campaign-alignment?brand_id=$BRAND_ID&campaign_id=$CAMPAIGN_ID"

# Read-only Drive API calls; they consume Google API quota but no AI/media credits.
curl -sS -H "X-API-Key: $KEY" \
  "$BASE/api/social/drive/folders?brand_id=$BRAND_ID"
curl -sS -H "X-API-Key: $KEY" \
  "$BASE/api/social/drive/images?brand_id=$BRAND_ID&media_type=image"

# Guard-only adapter checks: confirm=false rejects before DB action/provider dispatch.
curl -sS -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
  -d '{"confirm":false}' "$BASE/api/postcraft/runs/$RUN_ID/render"
curl -sS -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
  -d '{"confirm":false}' "$BASE/api/storyboard/runs/$RUN_ID/render"
curl -sS -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
  -d '{"confirm":false}' "$BASE/api/previs-motion/runs/$RUN_ID/generate-video"
```
Expected guard response is HTTP 400 `CONFIRM_REQUIRED`. Do **not** probe `/revise` with a real run, do not use `confirm:true`, and do not call `/onboarding/brand-kit` (LLM generation) as a readiness test. `POST /social/drive/root` has no AI cost but mutates selected-root metadata and performs a recursive Drive scan, so reserve it for intentional setup.

## Architecture
1. The external plugin loader scans `./plugins` locally (mounted as `/external_plugins` in production), validates each `channel.json`, registers manifest capabilities/connections/hooks, and the registry recursively imports capability modules.
2. `api/main.py` mounts each plugin's `api.py` router. These HTTP adapters do not call providers directly; generator routes call `execute_declared_run_action` against an existing Run artifact.
3. Generic Run execution scopes the brief to Brand, hydrates `brand_spec` from Drive or campaign-brand-kit document metadata, injects declarative credentials, hydrates upstream context, then fires `brief.before_dispatch`. Postcraft's hook replaces campaign alignment from Campaign V2 and optionally resolves an explicitly requested Brand Kit template.
4. The module performs its own preflight and provider call. Postcraft and Previs enforce Drive/token/root/logo before spend; current Storyboard omits the logo hard gate. All three enforce Drive-first success after provider output.
5. Root/logo truth is canonical in the brand-scoped Google Drive `SocialConnection.token_meta_json`. The Brand Creative Brief document provides fallback metadata and approval state, while `brands.brand_json` supplies voice/style profile. UI combines these inconsistently across Brand Detail and Client Readiness.

## Start Here
Open `plugins/storyboard/capabilities/storyboard/json/render/module.py` at lines 237-486 first. It is the clearest readiness defect: the live preflight omits `official_logo_drive_file_id`, logo injection is explicitly non-blocking, and the provider call follows. Compare it with the locked requirement in `plugins/plugins.md:27-28` and the unused stronger gate in `plugins/storyboard/lib/json_image_storyboard.py:1681-1714`.
