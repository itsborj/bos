---
id: postcraft.draft
name: postcraft-draft-branded-social-post
module_id: postcraft.draft
description: Retired Postcraft draft artifact path. CMO chat now writes the social image creative as plain text and, after operator approval, calls postcraft.render directly.
scope: module
status: inactive
version: 1.0.0
allowed_from_chat: false
requires_intent:
  - generation
triggers:
  - draft a post
  - preview a post
  - plan a post
  - show me what the post will look like
  - create a post brief
  - draft a social post
  - make a social post
  - create a social media post
  - need social media post
  - generate a post image
  - make a post image
  - what would this post look like
  - plan a promo post
  - draft this post before generating
excluded_triggers:
  - render an approved post
  - render a post that already has an approved draft
  - revise an existing post image
  - create a video
  - publish to instagram
  - schedule post
output_contract:
  - postcraft_draft
quality_gates:
  - draft_text_present
  - structured_block_present
metadata:
  version: 1.0.0
  plugin_id: creative.postcraft
  implements: postcraft.draft
  artifact_type: postcraft_draft
  risk_policy: draft_only
---

## What this capability does

Reads the operator's brief and produces a structured text artifact describing exactly what will be generated — before any provider cost is incurred.

**No provider calls. No Pillow. No composite.** Pure structured text from the brief.

**Output (`postcraft_draft`):**
```
Template:     promo — high-impact sales flyer ...
Format:       square (1024×1024)
Brand:        Golden Gate Memorial Garden
Colors:       primary #C79A42 · background #0A0A09 · text #FFFFFF
Logo:         [Drive file 1abc…] — BRAND LOGO, auto-injected top center
Hero asset:   dakong_cruz.png (operator attached)
Headline:     EXCLUSIVE LAWN LOT PROMO
Subheadline:  Limited Time Offer in Daanbantayan
Body:         Secure your legacy today...
CTA:          RESERVE YOUR LOT TODAY
Negative:     cartoon, neon, cheap flyer, horror cemetery
```

Operator can correct wrong template, wrong assets, wrong copy, or missing logo at zero cost before approving the render.

## When to invoke

- Brand asks to create a social post / social media post and no prior Postcraft draft exists
- Operator asks for a post image but has not explicitly approved rendering yet
- Operator wants to review what will be generated before spending on image generation
- Brief needs to be verified before handing to `postcraft.render`

## When NOT to invoke

- Render has already been approved (use `postcraft.render` directly)
- Operator is revising/editing an existing generated post image (use the existing artifact's revise flow)
- Request is for a video or reel
- Request is to publish or schedule a post that already exists

## CMO may pass as inline params

`headline`, `subheadline`, `body_copy`, `cta_text`, `caption`, `template_type`, `post_format`, `location`

## Output contract

Returns a `postcraft_draft` artifact block:
- `draft_text` — structured text preview of the planned post
- `template_type`, `post_format` — what will be generated
- `brand_kit`, `brand_spec` — brand data resolved at draft time
- `copy` — all copy fields
- `approval_status` — `"pending"`
- `allowed_actions` — `["render", "revise", "dismiss"]`
- `action_modules` — `{"render": "postcraft.render", "revise": "postcraft.draft"}`
