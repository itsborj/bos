---
id: media.image.generate
module_id: media.image.generate
name: image-generate
description: Generate any image or visual creative from a text prompt — including Google Ads image ads, display ads, social creatives, hero images, product images, and banners. This is the only installed image generation capability. Use it whenever the user asks for an image, ad creative, visual asset, or image ad regardless of the target platform.
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

Activate when the user explicitly asks to generate, create, or produce an image or visual asset from a description or prompt. Also activate when another capability requests an image asset as part of its workflow.

## When NOT to activate

Do not activate for text generation, copywriting, or content requests that do not involve visual media. Do not activate if no prompt or description is provided.

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
