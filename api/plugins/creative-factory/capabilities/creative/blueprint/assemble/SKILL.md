---
id: creative.blueprint.assemble
name: creative-blueprint-assemble
module_id: creative.blueprint.assemble
description: >
  Use when approved primitives and a creative pack exist and the operator wants
  to assemble them into a channel-agnostic Creative Blueprint — the master
  composition that maps primitives into template slots before any render target
  is applied. Triggers: "assemble blueprint", "compose the creatives", "build
  the master creative", "put the primitives together".
  Do not trigger until primitives are approved — blueprint assembly requires
  approved primitive_ids in the brief.
scope: creative
status: active
version: 1.0.0
allowed_from_chat: true
requires_intent:
  - generation
triggers:
  - assemble blueprint
  - compose creatives
  - build master creative
  - put primitives together
  - create blueprint
  - assemble the creative
excluded_triggers:
  - generate image
  - generate video
  - creative pack
  - render
  - export
memory_slots:
  - brand_profile
  - campaign_brand_kit
---

## Blueprint Assembly

Combine approved Layer 1 primitives into a Layer 2 Creative Blueprint using a
slot-based template. The blueprint is channel-agnostic — it does not know
whether the final output is TikTok, Meta, YouTube, or a banner.

### Intake
- `creative_pack` — the parent pack (for hooks, CTAs, visual theme)
- `primitive_ids` — list of approved primitive IDs to fill slots
- `template_id` — which template shell to use (default: `short_form_v1`)

### Templates
| template_id | slots | default aspect |
|---|---|---|
| `short_form_v1` | hero_visual, hook_text, cta_button, branding_overlay | 9:16 |
| `static_square_v1` | background_image, headline, logo | 1:1 |

### Output contract
Returns a `creative_blueprint` block with:
- `blueprint_id`
- `template_id`
- `slot_mappings` — which primitive fills which slot
- `status` — always `draft` until validated

### Quality gates
- All required template slots must be filled
- hook_text must be under 120 characters
- No slot may reference a primitive with `approval_status != approved`
- Blueprint must be validated before render targets are requested
