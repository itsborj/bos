---
id: creative.pack.generate
name: creative-pack-generate
module_id: creative.pack.generate
description: >
  Use when the operator wants to plan a creative production run: generating a
  batch of hooks, CTAs, visual directions, and primitive requirements from a
  campaign input. Triggers: "plan creatives", "create a creative pack",
  "generate hooks and visuals for", "build a creative production plan".
  Do not trigger for single asset requests — use creative.primitive.generate for those.
scope: creative
status: active
version: 1.0.0
allowed_from_chat: true
requires_intent:
  - generation
triggers:
  - creative pack
  - plan creatives
  - generate hooks
  - creative production plan
  - batch creative
  - creative strategy
excluded_triggers:
  - single image
  - one video
  - just a thumbnail
memory_slots:
  - brand_profile
  - campaign_brand_kit
---

## Creative Pack Generation

Produce a structured creative production plan from a campaign brief.

### Intake
- Product / service
- Offer and audience
- Visual mood / tone
- Desired volume (number of creatives)
- Any constraints (color, style, forbidden elements)

### Output contract
Returns a `creative_pack` block containing:
- `visual_theme` — the overarching creative direction
- `hooks` — 5–20 short-form hooks ranked by intent strength
- `ctas` — 3–5 CTA variants matched to mood
- `primitive_requirements` — list of raw assets needed (type, count, description)

### Quality gates
- hooks must be distinct — no paraphrases of each other
- CTAs must match brand voice from Campaign Brand Kit if present
- primitive_requirements must cover every slot in the target template
