---
id: creative.primitive.generate
name: creative-primitive-generate
module_id: creative.primitive.generate
description: >
  Use when the operator wants to produce a single raw creative asset: an image
  plate, video plate, product cutout, motion card, or brand overlay. This is the
  manufacturing step — it calls the appropriate image/video/audio provider and
  registers the result in the asset library. Triggers: "generate an image plate",
  "produce a video background", "create a product cutout", "make a motion card".
  For batch planning, use creative.pack.generate first.
scope: creative
status: active
version: 1.0.0
allowed_from_chat: true
requires_intent:
  - generation
triggers:
  - generate image plate
  - produce video plate
  - create product cutout
  - make motion card
  - generate background
  - generate primitive
  - produce creative asset
excluded_triggers:
  - creative pack
  - batch of creatives
  - hooks and CTAs
memory_slots:
  - brand_profile
  - campaign_brand_kit
---

## Primitive Generation

Produce a single Layer 1 creative primitive and register it in the asset library.

### Primitive types
| type | modality | description |
|---|---|---|
| `video_plate` | video | Clean background clip, no text/logos |
| `image_plate` | image | Still visual scene or lifestyle image |
| `product_cutout` | image | Transparent PNG/WebP product on alpha |
| `brand_overlay` | image | Logo, frame, gradient, CTA pill, badge |
| `motion_card` | video | Intro card, CTA card, end card |
| `audio_bed` | audio | Music, ambience, SFX |
| `voiceover` | audio | Narration track |
| `thumbnail_frame` | image | Still frame for previews |

### Intake
- `primitive_type` — one of the types above
- `prompt` — visual/audio direction
- `brand_id` — required for asset library registration
- `preferred_provider` — optional; system routes if omitted

### Output contract
Returns a `creative_primitive` block with:
- `primitive_id`
- `type`, `modality`, `source`
- `asset_id` — reference to the stored file/artifact
- `approval_status` — always `draft` until operator approves

### Quality gates
- Prompt must not be empty
- Modality must match type (video_plate → video, image_plate → image)
- asset_id must resolve to a reachable file before block is returned
