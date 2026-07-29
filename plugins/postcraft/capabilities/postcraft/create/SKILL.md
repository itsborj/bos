---
id: postcraft.create
name: postcraft-create-branded-social-post-image
module_id: postcraft.create
description: Legacy direct Postcraft image path. CMO chat now uses postcraft.render only after CMO-level text approval.
scope: module
status: inactive
version: 1.0.0
allowed_from_chat: false
requires_intent:
  - generation
triggers:
  - make a social post
  - create a post image
  - generate a post
  - make a post for
  - create branded post
  - design a post
  - make an image post
  - generate social media image
  - create a promo post
  - make a promo image
  - design a promotional post
  - make an agent award post
  - create a price card
  - generate a photo hero post
  - create educational post
  - make a post using these images
  - generate post with logo
  - create post from brand assets
  - edit this post
  - revise this post
  - update the post
  - modify the image
  - change the design
  - replace the
  - keep everything else
  - adjust the post
  - redo the post with
  - change the headline
  - update the copy
excluded_triggers:
  - create a video
  - make a video
  - generate a video
  - create storyboard
  - publish to facebook
  - publish to instagram
  - upload post
  - schedule post
output_contract:
  - post_image
quality_gates:
  - image_generated
  - structured_block_present
metadata:
  version: 1.0.0
  plugin_id: creative.postcraft
  implements: postcraft.create
  artifact_type: post_image
  platform: openai
  risk_policy: generate_with_gates
---

## What this capability does

Takes a brand brief and attached image assets, produces a single branded social media post image, and queues it for operator approval before publishing.

**Pipeline:**
1. Vision intake — each attached image is classified (logo / mascot / property photo / portrait / product) and labeled for composite placement
2. Composite reference sheet — all assets composited into one labeled sheet (Pillow)
3. Prompt construction — built from `brand_kit` colors/typography/tone + template type + copy fields + asset labels
4. Image generation — `gpt-image-2` via `images.edit` with the composite sheet as reference
5. Vision breakdown — output is analyzed for quality flags and spec deviations
6. Drive upload — result saved to the brand's Drive root under a `Postcraft/` folder
7. Returns a `post_image` artifact queued for operator review

## When to invoke

- Brand asks to create a social post image from a brief or attached assets
- Operator wants a promo, price card, photo hero, agent award, or educational card for social
- Brief includes headline, copy, CTA, or brand assets to incorporate

## When NOT to invoke

- Request is for a video or reel (use a video generation plugin)
- Request is to publish or schedule a post that already exists
- Request is to create a storyboard or shot list

## CMO may pass as inline params

`headline`, `subheadline`, `body_copy`, `cta_text`, `caption`, `template_type`, `post_format`, `location`, `edit_instruction`

## Revision flow

When the user asks to **edit or modify an existing post image**, pass `edit_instruction` with the specific change requested. Do NOT repeat headline, copy, or template unless the user explicitly changed them — the module restores those from the previous run automatically.

Example: user says "replace the pipes with a vase, keep everything as is" →
```
edit_instruction: "replace the pipes with a vase, keep all other elements unchanged"
```

Do NOT call `postcraft.render` for user-initiated text revisions — that path is for UI action buttons only.

## CMO must NOT pass

`image_prompt`, `background_color`, `aspect_ratio`, visual or scene direction — these are derived internally from the `brand_kit` and vision intake output.

## Template types

- `promo` — high-impact black and gold sales flyer
- `price_card` — cream and gold product/price layout
- `photo_hero` — cinematic brand image with text overlay
- `agent_award` — formal recognition post with portrait
- `educational` — clean cream editorial card

## Post formats

- `square` — 1024×1024
- `portrait_feed` — 1024×1536 (4:5 feed)
- `story_reel` — 1024×1536 (9:16)
- `landscape` — 1536×1024

## Output contract

Returns a `post_image` artifact block with `status="pending_review"`:
- `image_data_b64` — base64 PNG of the generated post
- `mime_type` — `"image/png"`
- `width`, `height` — pixel dimensions
- `template_type`, `post_format` — what was generated
- `vision_intake` — per-asset classification results
- `breakdown` — post-generation vision analysis
- `drive_file_id`, `drive_web_view_link` — Drive upload (if Google Drive connected)
- `allowed_actions` — `["approve", "revise", "dismiss"]`
