---
id: postcraft.render
name: postcraft-render-branded-social-post-image
module_id: postcraft.render
description: Execute the full high-quality Postcraft image generation pipeline after CMO-level text approval. The CMO writes the social image creative in chat first; only after operator approval should this render directly. Runs 7 isolated steps: brand logo auto-injection from Drive, vision intake, template-spec prompt construction, composite reference sheet, high-quality image generation, Drive upload, and thumbnail.
scope: module
status: active
version: 1.1.0
allowed_from_chat: true
requires_intent:
  - generation
triggers:
  - render the post
  - generate the post image
  - create the image
  - render this
  - approve and render
  - make this post
  - generate post image
  - render approved draft
excluded_triggers:
  - create a video
  - make a video
  - create storyboard
  - publish to instagram
  - schedule post
  - draft a post
output_contract:
  - image_asset
quality_gates:
  - image_generated
  - structured_block_present
metadata:
  version: 1.0.0
  plugin_id: creative.postcraft
  implements: postcraft.render
  artifact_type: image_asset
  platform: openai
  risk_policy: generate_with_gates
---

## What this capability does

Executes the full branded post image pipeline — but only after the operator approves the CMO-written social image creative in chat.

**Gate:** checks brief for `render_approved`, `approved_draft`, `action: render`, `approval_status: approved`, or an approved legacy `postcraft_draft` action. If none is present, render fails without creating a draft artifact. CMO chat approval happens as plain text before this module is called.

**Pipeline (7 steps, each isolated):**
1. **Brand asset resolution** — reads `logo_drive_file_id` from brand spec, fetches logo bytes from Drive, injects as first reference image
2. **Vision intake** — classifies each asset with gpt-4o-mini (type, subject, panel_label, placement_role)
3. **Prompt construction** — loads JSON template spec, resolves `{{placeholders}}` from brand spec + copy fields
4. **Composite reference sheet** — Pillow RGBA PNG for OpenAI path; skipped gracefully if Pillow absent
5. **Image generation** — OpenAI (`images.edit` + composite) · Gemini · ByteDance; one retry on transient error
6. **Drive upload** — hard gate; uploads to Brand Drive `Postcraft/` folder and fails if no durable `drive_file_id` is returned
7. **Thumbnail** — 480px JPEG; sets `asset_omitted: true` if Pillow unavailable

`analyze_output` is written to `/tmp/bos-postcraft-runs/` as an audit file — never blocks the artifact.

## When to invoke

- Operator has approved the CMO-written social image creative in chat
- Brief contains `render_approved: true`, `approved_draft: true`, or `action: render`
- Revision of a prior post image (`edit_instruction` + `original_artifact_block`)

## When NOT to invoke

- No CMO-written social image creative has been approved yet
- Request is for a video or reel
- Request is to publish or schedule an existing post

## CMO may pass as inline params

`render_approved: true`, `approved_draft: true`, `image_quality: high`, `postcraft_text`, `headline`, `subheadline`, `body_copy`, `cta_text`, `template_type`, `post_format`, `location`, `revision_prompt`, `edit_instruction`

`revision_prompt` — CMO-authored authoritative revision instruction written after seeing the current image. Takes priority over `edit_instruction`. Used verbatim in the image generation prompt.

## Template types

- `promo` — high-impact black and gold sales flyer
- `price_card` — formal serif price/offer layout
- `photo_hero` — cinematic full-background photo with text overlay
- `agent_award` — formal recognition post with agent portrait
- `educational` — clean editorial information card

## Output contract

Returns an `image_asset` artifact block:
- `image_data_b64` — 480px JPEG thumbnail (or `asset_omitted: true` if Pillow absent)
- `mime_type` — `image/jpeg`
- `drive_file_id`, `drive_web_view_link` — full-res image in Drive
- `template_type`, `post_format`, `brand_kit`, `brand_spec` — metadata
- `vision_intake` — per-asset classification results
- `pipeline_notes` — degradation notices (composite skip, thumbnail skip, etc.)
- `allowed_actions` — `["approve", "revise", "dismiss"]`
- `action_modules` — `{"revise": "postcraft.render"}`
