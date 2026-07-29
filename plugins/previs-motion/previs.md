# Previs Motion Plugin — Consolidated Reference

## Overview

Previs Motion is a BOS plugin that consumes approved Storyboard plugin output and renders motion previs / animatic videos with Seedance 2.0 via BytePlus ModelArk. In the current BOS video-production workflow, this output should be treated as the **final-cut candidate**: the reviewable video the operator can revise, package, and approve as the deliverable unless a separate high-end final-render tier is explicitly requested later.

It does **not** create storyboards. It expects Storyboard JSON plus either:
- `source_image_path` / `source_image_data_b64` for image-to-video, or
- `reference_video_url` / `reference_video_url_path` for JSON-based video edits.

**Plugin ID:** `channel.previs_motion`
**Version:** 0.1.0
**Default backend:** BytePlus ModelArk `dreamina-seedance-2-0-260128`

**Model invariant:** Previs Motion is pinned to Seedance 2.0 video models. It must not inherit storyboard/image-generation model IDs such as `gpt-image-2` from upstream image artifacts.

## Capabilities

| Capability | Module ID | Description |
|---|---|---|
| Render | `storyboard.motion.render` | Image-to-video from an approved Storyboard image/spec via Seedance 2.0 |
| Edit | `storyboard.motion.edit` | Thin alias that forces `mode: video_to_video` — imports and reuses the render module's class directly |

## Pipeline Position

```
storyboard plugin                    previs-motion plugin
─────────────────                    ─────────────────────
storyboard.create  ──(approve)──►  storyboard.render
        │                                  │
   text artifact                     image artifact
   + JSON spec                       (GPT Image 2)
        │                                  │
        │                          ──(approve)──►  storyboard.motion.render
        │                                               │
        │                                          video artifact
        │                                          (Seedance 2.0)
        │                                               │
        └───────────────────────────────────────────────┘
                  JSON spec + image flow through
```

## Inputs

```yaml
RUN: storyboard.motion.render
storyboard_spec: <approved Storyboard JSON object>
spec_path: <optional path to Storyboard JSON>
source_image_path: <optional approved storyboard/keyframe image path for I2V>
source_image_data_b64: <optional image data>
reference_video_url: <optional prior Seedance temporary URL for V2V edit>
reference_video_url_path: <optional file containing prior temporary URL>
task_id: <optional prior Seedance task ID used to refresh an expired reference URL>
edit_instruction: <optional user edit / approval note for the motion prompt>
approval_notes: <optional operator notes captured at storyboard-image approval>
video_generation_notes: <optional alias for approval_notes from the UI>
mode: <optional image_to_video | video_to_video | text_to_video | auto>
seedance_prompt/raw_prompt/direct_prompt/text_to_video_prompt/prompt: <optional exact direct T2V prompt when mode=text_to_video>
duration: <optional seconds, default 15, max 15>
ratio: <optional 16:9 | 9:16 | 1:1 | 4:3 | 3:4 | 21:9>
resolution: <optional 480p | 720p | 1080p>
model: <optional Seedance model id, default dreamina-seedance-2-0-260128>
backend_model_id: <host-stamped video backend; takes precedence over stale artifact model>
_backend_override: <host-stamped backend metadata; model_id used if backend_model_id is absent>
```

## Routing Rules

- If `reference_video_url` or `reference_video_url_path` is present, run JSON-based video-to-video edit.
- Else if `source_image_path` or `source_image_data_b64` is present, run storyboard image-to-video.
- Do not invent a storyboard. If no storyboard spec/image/video reference is available, ask for the Storyboard output first.

## Data Handoff from Storyboard

Previs-motion consumes these fields from the Storyboard plugin's output:

1. **`storyboard_spec`** — the full approved JSON (acts, shots, global visual rules, locked elements, brand assets). Resolved via `_resolve_storyboard_spec()` which looks for keys `storyboard_spec`, `storyboard_json`, `json_spec`, `spec`, or `spec_path`.

2. **`source_image_path` / `source_image_data_b64`** — the rendered storyboard image. Resolved via `_resolve_image_reference()` which also checks nested artifact blocks for `output_path` and `image_data_b64`.

3. **`production_blueprint` / `storyboard_text`** — the original text blueprint from `storyboard.create`. Attached via `_attach_blueprint_context()`.

4. **`reference_video_url`** — for V2V edits on a previously generated previs video.

## Prompt Assembly

`_prompt_from_target()` builds the Seedance prompt from storyboard data:

1. **Header** — varies by mode (image_to_video, video_to_video, text_to_video)
2. **Constraints block** — no panel borders, no captions, cinematic cuts, etc.
3. **Global visual rules** and **locked elements** from the storyboard JSON
4. **Brand assets** — logo must appear in end-card
5. **Approved production blueprint text** — the original narrative

For image-to-video mode, the storyboard image is sent as an `image_url` content item alongside the text prompt. Default role is `reference_image`, which is best for storyboard/contact-sheet guidance. If the operator explicitly needs strict first-frame I2V, pass `image_role: "first_frame"` (or `seedance_image_role`) so the image becomes the starting frame. If the operator enters approval notes while approving the storyboard image (for example “produce a colored version” or “no text overlays”), the UI passes them as `edit_instruction` / `approval_notes`, and `_prompt_from_target()` includes them as operator revision notes in the Seedance prompt.

For explicit text-to-video mode with a direct prompt (`seedance_prompt`, `raw_prompt`, `direct_prompt`, `text_to_video_prompt`, or `prompt`), Previs sends that prompt as the single `content[0].text` item without splitting, sanitizing brand names, dropping music/sound lines, or appending canonical target JSON. This matches the successful direct Seedance 2.0 T2V path for long Markdown story prompts.

## Key Design Decisions

### "Final-cut candidate" philosophy
Previs output should be treated as the deliverable unless a separate high-end render tier is requested later. This is not a throwaway rough cut.

### `generate_audio` defaults to `True`
Previs Motion now asks Seedance to generate audio by default. To disable audio for a render, pass `generate_audio: false` explicitly.

### Direct T2V large-prompt path

Seedance 2.0 accepts long Markdown/script/storyboard prompts directly in a text-only generation request when the request uses the ModelArk content-generation endpoint and the concrete Seedance 2.0 model ID:

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [{ "type": "text", "text": "# long operator-authored prompt..." }],
  "resolution": "1080p",
  "ratio": "9:16",
  "duration": 15,
  "generate_audio": true,
  "watermark": false
}
```

Operational learnings from direct T2V tests:
- Use `POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks` and poll `GET /contents/generations/tasks/{task_id}`.
- Use the concrete model ID `dreamina-seedance-2-0-260128`; endpoint-style IDs can 403 even when the API key is valid.
- Preserve direct story prompts exactly enough for the model to see timing, audio, visible-text, and negative constraints. Do not run the direct prompt through the normal blueprint splitter because that removes `Sound:`/`Music:` lines and can alter brand text.
- Keep the ModelArk field `generate_audio` in snake_case.
- Text-only T2V is valid, but continuity across revisions/longer pieces should still prefer V2V/I2V references when available.

### Prefer continuity inputs over text-only generation
Auto mode now chooses the strongest available Seedance input in this order:

1. `video_to_video` when a live/refreshed `reference_video_url` is available
2. `image_to_video` when `source_image_path`, `output_path`, `source_image_data_b64`, or `image_data_b64` is available
3. `text_to_video` only when no visual reference is available

This prevents the approved Storyboard image from being silently ignored. If an explicit V2V reference has expired and cannot be refreshed, Previs falls back to I2V only when a storyboard/source image is available; otherwise it fails with `reference_video_expired` rather than doing an unrelated fresh T2V render.

Previs video artifacts now preserve the source storyboard image lineage (`source_image_path`, `source_image_data_b64`, and `source_image_role`) so the revision pipeline can still perform I2V fallback after the prior Seedance video URL/task expires. The path is a local cache; the embedded b64 is the durable fallback copied from the approved Storyboard image artifact when available.

### Backend override beats inherited artifact `model`
Storyboard image artifacts can legitimately contain `model: gpt-image-2` because the image stage used OpenAI/GPT Image. When that artifact is approved and passed to `storyboard.motion.render`, the run host must stamp the active Previs video backend into the brief as `backend_model_id` and `_backend_override`. The Previs module resolves the video model in this order:

1. `backend_model_id`
2. `_backend_override.model_id`
3. `model`
4. default `dreamina-seedance-2-0-260128`

When `backend_model_id` is explicitly set by the admin/host, it bypasses the Seedance 2.0 model-pinning guard — admin-configured overrides are trusted for alternate Seedance 2.0 model variants. This prevents recurring failures like:

```text
Previs Motion is pinned to Seedance 2.0. Refusing non-Seedance-2 model 'gpt-image-2'.
```

If this error reappears, treat it as a host/action-brief routing bug: inspect the action brief and confirm `backend_model_id` is present and one of the allowed Seedance 2.0 IDs. Previs also has a defensive fallback for storyboard-image actions that inherit obvious image model names such as `gpt-image-2`; if that fallback is not happening, inspect `artifact_action`, `source_module_id`, and `approved_artifact_type` in the action brief. Do not fix it by enabling `PREVIS_MOTION_ALLOW_NON_SEEDANCE2` outside explicit provider tests.

### V2V URL refresh before I2V fallback
Seedance output URLs are TOS (BytePlus Object Storage) presigned URLs with `X-Tos-Expires=86400` — they expire **24 hours** after the task completes. The underlying task data persists for **48 hours** (`execution_expires_after=172800`). Re-fetching a completed task within the 48h window via `GET /contents/generations/tasks/{task_id}` returns a freshly-signed URL suitable for V2V reference.

When the stored `reference_video_url` is inaccessible (HTTP 403), the renderer now:
1. Resolves `task_id` from the brief (`brief["task_id"]` or nested artifact blocks — populated automatically since the artifact block always carries `task_id`)
2. Re-fetches the task via ModelArk API for a fresh presigned URL
3. Verifies the new URL is accessible, then proceeds with true V2V editing
4. Only if re-fetch fails or returns no URL (task > 48h) does it fall back to I2V

The **durable copy of the video is the Google Drive file** (`drive_file_id`). Seedance CDN URLs and `/tmp` paths are ephemeral. Drive files cannot be used as V2V reference directly (they require OAuth; Seedance needs a public URL), so the task re-fetch is the only path for V2V after the CDN URL expires.

**V2V editing window summary:**

| Age of prior render | CDN URL status | Task status | V2V possible? |
|---|---|---|---|
| 0–24 h | Live | Active | Yes — use stored CDN URL directly |
| 24–48 h | Expired (403) | Active | Yes — re-fetch task for fresh URL |
| > 48 h | Expired (403) | Expired | No — falls back to I2V from storyboard image |

### The edit module is a pass-through
`storyboard.motion.edit` literally imports `PrevisMotionRenderModule` from the render module and calls `super().execute_tool_result()` with `mode: "video_to_video"` forced. The render module handles V2V logic: URL refresh, sending the prior video as `reference_video` to Seedance, and falling back to I2V when the 48h task window has closed.

## Video Revision Workflow (Seedance 2.0 V2V)

### How Seedance video-to-video editing works

Seedance 2.0 supports true video editing through multimodal reference-based generation. The API accepts a prior video as `reference_video` and applies edit instructions while preserving the original video's continuity, characters, environment, and style.

**API endpoint:** `POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks`

**Payload structure for V2V edit:**

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "Video 1 is the locked reference video. Preserve its storyboard continuity, style, pacing, camera language, characters, props, and final reveal. Perform only the edit requested below. Required edit: <edit_instruction>."
    },
    {
      "type": "video_url",
      "video_url": { "url": "<fresh_presigned_tos_url>" },
      "role": "reference_video"
    }
  ],
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 15,
  "generate_audio": true,
  "watermark": false
}
```

**Payload structure for I2V render:**

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "Image 1 is the approved storyboard/keyframe reference image. Animate it into one continuous motion previs final-cut candidate..."
    },
    {
      "type": "image_url",
      "image_url": { "url": "data:image/png;base64,<base64_or_accessible_url>" },
      "role": "reference_image"
    }
  ],
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 15,
  "generate_audio": true,
  "watermark": false
}
```

**Task polling:** `GET /api/v3/contents/generations/tasks/{task_id}` — poll every 5 s, up to 15 min. Terminal statuses: `succeeded`, `failed`, `expired`, `cancelled`.

**Task response shape:**

```json
{
  "id": "cgt-<id>",
  "status": "succeeded",
  "content": { "video_url": "https://ark-acg-ap-southeast-1.tos-ap-southeast-1.volces.com/...?X-Tos-Expires=86400&..." },
  "usage": { "completion_tokens": 324900, "total_tokens": 324900 },
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 15,
  "framespersecond": 24,
  "execution_expires_after": 172800,
  "generate_audio": true
}
```

Seedance 2.0 multimodal constraints:
- `content` array: 0–9 reference images, 0–3 reference videos, 0–3 audio references per request
- Reference video must use `"type": "video_url"` with `"role": "reference_video"` — not `"role": "reference"` or other aliases
- Storyboard/reference-image guidance must use `"type": "image_url"` with `"role": "reference_image"`
- Strict first-frame I2V may use `"type": "image_url"` with `"role": "first_frame"` (or blank role per docs, but Previs uses explicit `first_frame` when requested)
- `reference_image`, `first_frame`, and first+last-frame modes are different Seedance scenarios. Do not mix them unless intentionally testing multimodal behavior.
- Both `image_url.url` and `video_url.url` must be a publicly accessible URL or a `data:` URI; OAuth-gated URLs (e.g. Google Drive with permissions) will be rejected
- `generate_audio` must be `true`/`false` (snake_case); `generateAudio` is silently ignored by the endpoint
- Single image input must be under 30 MB and request body under 64 MB; avoid base64 for very large files
- `seed` helps reproducibility within a session but is not deterministic across infrastructure changes
- JSON/XML formatted prompts do NOT guarantee structural consistency — multimodal reference files are the only reliable continuity mechanism

### Live validation: Widower storyboard I2V + V2V (2026-06-30)

A direct Seedance 2.0 API smoke test validated the official multimodal payload shape without changing the Previs piping:

- I2V/reference-image render: exact storyboard JSON text + `/home/ubu/bos/plugins/Widower - 6-30.png` embedded as `data:image/png;base64,...`, role `reference_image`, `generate_audio: true`, `resolution: 480p`, `ratio: 3:4`, `duration: 15`
- Result: succeeded (`cgt-20260630202611-h88jv`), 4.84 MB MP4, ~252 s total, usage ~148K tokens
- Follow-up V2V edit: prior `video_url` sent as `role: reference_video` with edit instruction “make shot 4 consistent with shot 3; update marker text to Beloved Wife”
- Result: succeeded (`cgt-20260630203802-vs2cq`), ~314 s total, usage ~296K tokens

Operational lessons:
- The PNG reference materially anchors panel continuity, character/mug/marker placement, and final Ginto beat better than text-only JSON.
- 480p is a useful profiling/iteration tier before spending on 720p/1080p.
- `generate_audio: true` can succeed on the same grief/memorial concept that previously produced `OutputAudioSensitiveContentDetected`; treat that error as probabilistic output-audio moderation unless silent render also fails.
- Text edits inside generated video remain uncertain. Marker text changes like `Beloved Wife` must be visually reviewed even when the task succeeds.

### Video URL and task lifecycle

Generated Previs videos live in **three places with different lifetimes**:

| Storage | Path / field | Lifetime | Accessible by Seedance V2V? |
|---|---|---|---|
| Seedance TOS CDN | `video_url` in artifact block | **24 h** (`X-Tos-Expires=86400`) | Yes, while live |
| BytePlus ModelArk task | `task_id` → re-fetch via API | **48 h** (`execution_expires_after=172800`) | Yes — re-fetch returns fresh URL |
| Google Drive | `drive_file_id` in artifact block | **Permanent** (brand-owned) | No — requires OAuth; Seedance needs a public URL |

**Implication:** The Drive file is the durable artifact for human use (review, sharing, publishing). It cannot be directly used as a Seedance V2V reference. V2V editing depends on a live CDN URL, obtained either from the stored URL (0–24 h) or by re-fetching the task (24–48 h). After 48 h the task expires and V2V falls back to I2V.

### Revision behavior by age of prior video

| Age | Behavior |
|---|---|
| 0–24 h | `reference_video_url` is live → V2V proceeds directly |
| 24–48 h | CDN URL returns 403 → `_refresh_video_url(task_id, api_key)` fetches a fresh presigned URL → V2V proceeds |
| > 48 h | Task expired → falls back to I2V from storyboard image (or fails with `reference_video_expired` if no image available) |

The `task_id` is always stored in the video artifact block and passed automatically in action briefs. No manual intervention is needed for the 24–48 h window.

### Bug history: V2V never actually fired (fixed 2026-06-28 and 2026-06-29)

**Bug 1 (fixed 2026-06-28):** `storyboard.motion.edit` was forcing `mode: image_to_video` instead of `video_to_video`, and the chat revision bridge was not passing `reference_video_url` in the brief. Every "revise" action was a fresh I2V generation — the prior video was ignored entirely. Fix: edit module now forces `brief["mode"] = "video_to_video"`.

**Bug 2 (fixed 2026-06-29):** All Seedance CDN URLs expire in 24 h. Even after Bug 1 was fixed, revisions the following day would see a 403 on the reference URL and fall back to I2V silently. The fix introduces `_refresh_video_url(task_id, api_key)`: when the stored URL returns 403, the render module re-fetches the completed task from ModelArk to get a fresh presigned URL, verifies it is accessible, and proceeds with V2V. Only if the task itself has expired (> 48 h) does it fall back to I2V.

### V2V cost and performance

Observed from production runs:
- Seedance I2V: 120–400 s, ~140K–325K tokens for a 15 s video
- Seedance V2V: 120–400 s (similar), ~2× tokens of text-only generation
- V2V preserves creator identity, face, location, lighting, and camera movement when the prompt instructs it explicitly
- For exact character/location continuity, V2V over I2V is the only reliable approach

### V2V prompt engineering for Seedance 2.0

Seedance V2V is controllable through prompt structure, not JSON schemas:

- **Anchor the reference video explicitly:** "Video 1 is the locked reference video. Preserve..."
- **State what to change, not what to keep:** "Required edit: [specific change]. Preserve everything else."
- **Avoid over-specifying:** Seedance ignores repeated JSON specs in the prompt for V2V; the reference video carries the visual state
- **For script/voice-over changes:** re-render from updated storyboard spec (V2V cannot reliably replace embedded audio)
- **Audio moderation:** if `OutputAudioSensitiveContentDetected` appears, pass `"generate_audio": false` for a visual-only re-render

### V2V voice-over limitation

V2V edits treat the reference video's audio as locked. Requests like "translate the voice-over to Filipino" rarely replace the existing audio because Seedance treats the reference video's audio track as part of the locked reference. For localization:
1. Update the canonical storyboard/target JSON voice-over/script fields first
2. Send the revised Filipino script prominently near the top of the Seedance prompt
3. For production-grade dubbing, use a separate TTS/dubbing step and mux the audio track onto the video outside Seedance

## Regression Lessons / Wrong Assumptions to Avoid

These assumptions caused repeated same-day regressions and should be checked whenever Storyboard → Previs is touched:

1. **Wrong assumption: fixing Previs video generation fixes the whole video pipeline.**  
   The pipeline has separate transitions: `storyboard.create → storyboard.render` and `storyboard.render → storyboard.motion.render`. A fix in the Previs/video transition does not automatically fix the upstream Storyboard-image render transition.

2. **Wrong assumption: an approved artifact action always carries structured `storyboard_spec`.**  
   Some Stream/chat/action paths can pass a flattened action brief, stale `spec_path`, or approved storyboard markdown without the structured spec. The run host must include `original_artifact_block`, and Storyboard render must hydrate/reconstruct `storyboard_spec` before preflight. Otherwise approval can fail minutes later with `missing storyboard_spec` even though the user approved the artifact.

3. **Wrong assumption: tool connectors always receive backend overrides through normal candidate routing.**  
   Deterministic `execute_tool_result()` modules do not use the normal provider candidate loop. The host must stamp `backend_model_id` / `_backend_override` onto tool briefs, falling back to the plugin `default_backend` when needed. Previs must still defensively ignore inherited image-stage model IDs such as `gpt-image-2` on storyboard-image actions.

4. **Wrong assumption: Storyboard image artifacts expose `source_image_path`.**  
   `storyboard.render` image blocks expose the approved storyboard image as top-level `output_path` and often top-level `image_data_b64`, not `source_image_path`. Action briefs flatten those fields. Previs must read top-level `output_path` / `image_data_b64`; otherwise it silently chooses `text_to_video`, consumes only the script/screenplay text, and ignores the approved storyboard image.

5. **Wrong assumption: the current text-only helper proves I2V is unavailable.**  
   The official Seedance 2 API supports true image input through `content[]` items. A local helper/tool may hide this capability if it exposes only prompt/model/resolution fields. The ModelArk payload must include the PNG as `image_url.url` (public URL or `data:image/png;base64,...`) with role `reference_image` for storyboard guidance or `first_frame` for strict first-frame animation.

6. **Wrong assumption: generated successful videos may default to Approved.**  
   Previs outputs are final-cut candidates, not final approvals. Successful video blocks must set `approval_status: pending` so they appear in Needs review.

7. **Wrong assumption: setup blocker messages can be generic.**  
   Storyboard and Previs blockers must identify the actual plugin/stage. A Storyboard preflight failure must never surface as “Postcraft is blocked.”

8. **Wrong assumption: a patch changes existing cards.**  
   Already-created failed/approved artifacts are stale history. After a fix, restart/redeploy the API/web process and retry the action from the source artifact; existing failed cards will not self-heal.

## Output Contract

Returns a native BOS `video_asset` block plus Previs Motion audit fields. Successful Previs videos are **Needs review by default** (`approval_status: pending`) because they are final-cut candidates that still require operator review before final approval or publishing.

| Field | Description | Durable? |
|---|---|---|
| `drive_file_id` | Google Drive file ID — the permanent artifact identity | Yes |
| `drive_web_view_link` | Drive web view URL for human review/sharing | Yes |
| `video_url` | Seedance TOS CDN presigned URL (expires 24 h after generation) | No — ephemeral |
| `task_id` | ModelArk task ID (task lives 48 h; used to refresh expired CDN URL) | 48 h window |
| `video_path` | Container-local MP4 path for Stream playback cache | No — lost on container restart |
| `target_json_path` | Container-local path to compiled target JSON | No |
| `payload_path` | Container-local path to redacted API payload | No |
| `task_path` | Container-local path to final task JSON response | No |
| `storyboard_spec` | The approved storyboard JSON used for generation | Yes (in block) |
| `mode` | `image_to_video`, `video_to_video`, or `text_to_video` | Yes (in block) |
| `provider` | `byteplus_modelark` | Yes |
| `model` | Seedance model ID used | Yes |

Allowed actions: `approve_final_cut`, `publish_review`, `revise`, `regenerate`, `dismiss`

`drive_file_id` is the only durable video identity. A video artifact without it must not be surfaced as successful in Stream.

## Google Drive Integration

Every Brand in Admin has its own configured Google Drive root directory. Previs Motion must store generated videos there before a video artifact is allowed to appear in Stream.

Drive and Brand asset validation are hard gates, not best-effort enhancements:

- Google Drive must be connected for the selected Brand.
- The Brand must have a validated Drive root folder.
- The Brand must have an official logo/wordmark Drive file ID before video generation starts.
- Optional Brand Kit images such as mascot, product, people, location, vehicle/property, template/reference masters, or style references may be passed through from the Storyboard/Brand spec when relevant.
- `drive_file_id` is the durable video identity.
- `/tmp`, provider CDN URLs, and audit folders are not artifact storage.
- If Google Drive credentials/root/logo/upload are unavailable, Previs Motion must fail and tell the operator what to fix before spending video-generation credits where possible.
- It must not silently return a successful local-only or provider-URL-only video artifact.

### Pattern (matches Postcraft and Storyboard)

```
plugin_loader.inject_channel_credentials()     previs-motion module
──────────────────────────────────────────     ────────────────────
Reads channel.json credential_slots            _load_drive()
  ↓                                              ↓
Resolves SocialConnection                       Searches for google-drive/
for platform="google_drive"                     drive_client.py in 3 paths
  ↓                                              ↓
Injects into brief:                             _store_in_drive(brief, video_bytes, filename)
_channel_credentials = {                          ↓
  access_token,                                   Reads token + brand Drive root from
  drive_root_folder_id,                           _channel_credentials
  drive_root_name                                 ↓
}                                                client.ensure_path(["Previs Motion"], root)
                                                 client.upload_file(name, bytes, mime, folder_id)
                                                   ↓
                                                 Returns {drive_file_id, drive_web_view_link, ...}
```

### Credential slots
- `byteplus_api_key` (type=platform_var) — BytePlus ModelArk API key for Seedance
- `access_token` (type=social_token, platform=google_drive) — Brand's Google Drive OAuth token
- `drive_root_folder_id` (type=social_meta_field, platform=google_drive) — Brand's Drive root folder
- `drive_root_name` (type=social_meta_field, platform=google_drive) — Human-readable Drive root name

### Drive folder structure
```
Brand Kit root/
├── Storyboard/         ← storyboard images (from storyboard plugin)
├── Postcraft/          ← postcraft images (from postcraft plugin)
├── Previs Motion/      ← previs videos (ensure_folder)
├── Brand Assets/
│   ├── Logos/
│   └── Products/
├── Templates/
└── Archive/
```

## Gates

| Gate | Phase | Question |
|---|---|---|
| `storyboard_picture_lock` | 1 | Is the storyboard image/spec approved for motion testing? |
| `previs_video_review` | 2 | Does the motion preserve the approved storyboard, timing, and continuity? |

## chat_v2 Integration

### Current state
- **No `actions` dict declared** — LLM gets opaque `brief: string` parameter
- Module receives brief as dict via `execute_tool_result(brief)`
- `plugin_loader.inject_channel_credentials()` injects Drive tokens/root metadata declared in `channel.json`
- The storyboard image artifact's `action_modules.generate_video` routes to `storyboard.motion.render`

### Planned: `actions` dict for typed parameters
```python
actions = {
    "render": {
        "description": "Render a motion previs/animatic final-cut candidate from an approved storyboard image and JSON spec via Seedance 2.0",
        "parameters": {
            "source_run_id": {"type": "string", "description": "Run ID of the approved storyboard image artifact"},
            "storyboard_spec": {"type": "string", "description": "The approved storyboard JSON (as JSON string)"},
            "spec_path": {"type": "string", "description": "Path to the approved storyboard JSON spec file"},
            "duration": {"type": "integer", "description": "Video duration in seconds (default 10)"},
            "ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]},
            "resolution": {"type": "string", "enum": ["480p", "720p", "1080p"]},
            "generate_audio": {"type": "boolean", "description": "Generate audio/voice-over (default true; pass false to disable)"},
        },
        "required": ["source_run_id"],
        "produces": "previs_motion_video",
        "consumes": "storyboard_image",
    },
    "revise": {
        "description": "Revise a previs motion video using JSON edit instruction",
        "parameters": {
            "source_run_id": {"type": "string", "description": "Run ID of the previs video to revise"},
            "edit_instruction": {"type": "string", "description": "What to change in the video"},
        },
        "required": ["source_run_id", "edit_instruction"],
        "produces": "previs_motion_video",
        "consumes": "previs_motion_video",
    },
}
```

## Known Issues

### Container-local playback cache can disappear from Stream

Previs Motion writes a playable MP4 to the API container's writable storage and audit files to a run directory. These paths live **inside the `bos-api-1` container** and are not durable across container restart. The configurable root is set via `PREVIS_MOTION_RUNS_DIR` (defaults to a container-local path). A Previs artifact that carries only a `video_path` but no `drive_file_id` is invalid and must not be surfaced as successful in Stream.

Past incident:
- The container-local MP4 was lost after container restart; recovery required a still-valid Seedance `video_url` to re-download and re-upload to Drive
- Once the Seedance CDN URL also expires (> 24 h), recovery requires a durable Drive copy or a full re-render

Required invariant for Previs artifacts:

- `drive_file_id` is required before a successful video artifact may appear in Stream.
- `video_path` is a playback cache only, not durable storage.
- `video_url` is temporary provider storage only (expires 24 h).
- Drive upload failure is a failed/setup-blocker artifact, not a warning on an otherwise successful result.
- The artifact block must preserve lineage:
  - `source_run_id` — direct storyboard image or prior video run used as input
  - `source_module_id`
  - `source_artifact_type`
  - `approved_blueprint_source_run_id` — original/approved Storyboard blueprint run, when known

### OutputAudioSensitiveContentDetected (Fixed)
Seedance's audio generation can trigger content safety errors when the storyboard prompt contains sensitive themes. Audio is enabled by default; pass `generate_audio: false` for visual-only renders or sensitive prompts.

Session learning, 2026-06-30:
- `OutputAudioSensitiveContentDetected` is an **output audio moderation** failure, not proof that the storyboard/visual prompt is blocked. A grief/memorial prompt can fail after Seedance generates or attempts audio even when the same visual content is acceptable.
- The failure can be **non-deterministic**. In one run, the exact widower/memorial JSON prompt failed with `OutputAudioSensitiveContentDetected`; a later resend of the exact JSON prompt with only audio enabled (`generateAudio: true`) succeeded.
- Triage order for this error:
  1. Re-render the same prompt with `generate_audio: false` to confirm whether visuals process.
  2. If the silent render succeeds, treat the incident as audio moderation/probabilistic audio output, not a visual prompt issue.
  3. If the silent render also fails, investigate a separate issue: visual safety, prompt/schema incompatibility, model access, provider outage, or asset/reference input.
  4. If audio is required, one retry with the exact prompt and `generate_audio: true` may succeed; otherwise render visuals silent and attach approved music/VO in a separate mux/dubbing step.
- When testing through direct ModelArk/Seedance tooling, specify the pinned Seedance 2.0 model (`dreamina-seedance-2-0-260128`) if the default endpoint returns `AccessDenied`; that is a model/endpoint access issue distinct from content moderation.

### Drive folder organization
Previs videos are uploaded under the selected Brand's configured Google Drive root in a `Previs Motion/` subfolder. The local `/tmp` MP4 remains only a playback cache after Drive persistence succeeds; `drive_file_id` is the durable artifact identity.

## Files

```text
previs-motion/
├── channel.json
├── SKILL.md
├── previs.md             ← consolidated plugin reference (canonical)
├── previs-motion.md      ← project brief, bug tracker, bottleneck assessment
├── capabilities/storyboard/motion/render/
│   ├── SKILL.md
│   └── module.py
└── capabilities/storyboard/motion/edit/
    ├── SKILL.md
    └── module.py
```
