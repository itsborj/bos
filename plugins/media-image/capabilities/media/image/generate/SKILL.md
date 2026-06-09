---
id: media.image.generate
module_id: media.image.generate
name: image-generate
description: Generate any image or visual creative from a text prompt — including sample images, Google Ads image ads, display ads, social creatives, hero images, product images, and banners. This is the only installed image generation capability. Use it whenever the user asks for an image, sample image, ad creative, visual asset, or image ad regardless of the target platform. A bare request like “get me sample image” means dispatch immediately using the active brand brief; do not ask what kind of image.
scope: module
status: active
version: 1.0.0
allowed_from_chat: true
triggers:
  - generate image
  - create image
  - make an image
  - visual asset
  - image for
  - hero image
  - product image
  - banner image
  - ad image
  - social image
  - image ad
  - display ad
  - google ads image
  - image creative
  - ad creative
  - show image
  - sample image
  - image sample
excluded_triggers:
  - generate text
  - generate copy
  - write
  - text ad
  - search ad
related_modules:
  - media.image.generate
quality_gates:
  - image_data_present
  - prompt_present
metadata:
  version: 1.0.0
  author: bos
  plugin_id: media.image
---

## When to activate

Activate when the user asks for any image or visual asset — with or without a specific description. A bare “sample image” / “get me sample image” request is enough. The module auto-generates a prompt from the active brand brief (product, tone, audience) when no explicit prompt is provided. Dispatch immediately; do not ask the user for a prompt or image type before dispatching.

## When NOT to activate

Do not activate for text generation, copywriting, or content requests that do not involve visual media.

## Output contract

Returns an `image_asset` block:

```json
{
  "type": "image_asset",
  "status": "succeeded",
  "image_data_b64": "<base64-encoded PNG>",
  "mime_type": "image/png",
  "width": 1024,
  "height": 1024,
  "prompt": "<the prompt used>",
  "byte_size": 123456,
  "allowed_actions": ["use", "regenerate", "dismiss"]
}
```

The underlying provider is configured via `IMAGE_GEN_WORKER_URL` and `IMAGE_GEN_API_KEY` plugin credentials. Swapping providers requires only updating the stored credentials — this module ID and output contract remain stable.

---

## Stream load performance note

Resolved 2026-05-26. `GET /runs/{run_id}` supports `include_assets=false` so bulk Stream hydration can omit large inline fields such as `image_data_b64` while preserving prompt, dimensions, MIME type, and metadata. `Stream.tsx` uses bounded-concurrency hydration and only requests inline assets for explicit pending-review runs.
