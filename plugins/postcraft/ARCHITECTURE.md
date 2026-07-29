# Postcraft — Architecture & System Requirements

> Unified reference. Consolidates learnings from `json-imagen` prototype,
> `storyboard` plugin, and postcraft's own failure history.
> This document supersedes `NOTES.md` for architectural decisions.
> Update here when the design changes — never make a silent architectural assumption.

---

## The One Rule (from Storyboard)

**Split the pipeline. Cheap step first. Expensive step only after approval.**

Storyboard proved this. Postcraft must adopt it.

```
postcraft.draft   →  text artifact   →  $0 cost   →  operator approves
postcraft.render  →  image artifact  →  provider cost  →  only after approval
```

Every failure in the current single-capability design costs a provider image call.
Every wrong result costs a provider image call. The gate eliminates this.

---

## Non-Negotiable Preflight

Postcraft must never generate, render, or revise a post unless all three are present:

1. **Brand kit loaded** — real `brand_id` / `brand_name` plus voice, tone, colors, approved visual constraints, or equivalent brand style data. Placeholder names like `brand` / `this brand` do not pass.
2. **Official logo resolved** — a real logo Drive file ID from the Postcraft brand spec or Brand Kit Drive folder validation metadata, plus Drive credentials so the logo image can be sent to the image model.
3. **Campaign alignment loaded** — a `campaign_id` plus campaign name/goal/audience/message-angle context when available.

If any preflight item is missing, Postcraft returns a setup-blocker artifact with the checklist and must not call the image provider.

For revisions, follow the json-imagen rule: the revised prompt/spec is not enough. Send the previous approved/generated image as the image edit source/reference. If the revision also introduces a new visual reference, compose one source image containing the current design + official logo + new references, with labels drawn into the image and mapped in the prompt. If the CMO model calls `postcraft_render` directly with `source_run_id` + `revision_prompt`, the router must normalize that call through the generic revision path first so the source Run/RunTrace block and previous image are loaded.

---

## Two Capabilities

### `postcraft.draft` (was: `postcraft.create`, draft phase only)

**What it does:** Produces a reviewable text artifact describing exactly what will
be generated — before any provider cost is incurred.

**Output artifact (`postcraft_draft`):**
```
Template:     promo
Format:       square (1024×1024)
Brand:        Golden Gate Memorial Garden
Colors:       primary #C79A42 · background #0A0A09 · text #FFFFFF
Logo:         golden-gate-logo.jpg (from Drive, auto-injected)
Hero asset:   dakong_cruz.png (operator attached) — HERO PROPERTY PHOTO, right panel
Headline:     EXCLUSIVE LAWN LOT PROMO
Subheadline:  Limited Time Offer in Daanbantayan
Body:         Secure your legacy today...
CTA:          RESERVE YOUR LOT TODAY
Negative:     cartoon, neon, cheap flyer, horror cemetery, distorted logo
```

**Operator sees:** which logo is being used, which template, the full copy, which
attached assets go where — before any generation. They can correct wrong assets,
wrong template, or wrong copy at zero cost.

**No provider calls. No Pillow. No composite.** Just structured text from the brief.

**Allowed actions:** `[Render]` · `[Revise]` · `[Dismiss]`

---

### `postcraft.render` (was: `postcraft.create`, generation phase only)

**What it does:** Executes the full pipeline only after draft approval.

**Gate (mirrors storyboard's `_is_render_approved`):**
Check brief for any of:
- `render_approved: true`
- `approved_draft: true`
- `action: render` or `action: render_approved`
- `approval_status: approved`
- `original_artifact_block.type == postcraft_draft` with `approval_status: approved`

If none present → fall back to `postcraft.draft` response (hold render, show draft).
Never error. Never generate without approval.

**Pipeline (7 steps, each isolated):**

```
Step 1  Brand asset resolution
        Read logo_drive_file_id from brand spec → fetch bytes from Drive
        If Drive unavailable: continue without logo, note in artifact
        Merge with operator-attached reference_images (operator images take priority)

Step 2  Vision intake
        Each asset → gpt-4o-mini classify: type / subject / panel_label / placement_role
        On failure: use filename as panel_label, continue — never drop the asset

Step 3  Composite reference sheet (Pillow, OpenAI path only)
        1 asset  → convert to RGBA PNG
        2+ assets → horizontal labeled panels (1024px each, label drawn into image)
        Pillow unavailable: skip composite, fall back to text-only generation, note in artifact
        Clean up temp file in finally block

Step 4  Prompt construction (spec-based, not assembled prose)
        Load template spec for template_type (see Template Specs below)
        Resolve {{placeholders}} from brand spec + copy fields
        Result: structured prompt with layout, negative list, panel instructions

Step 5  Image generation (provider-switchable, one retry on transient)
        OpenAI:    images.edit with composite as source (RGBA PNG required)
                   Fallback to images.generate if no composite available
                   No env-var key fallback — credentials from _channel_credentials only
        Gemini:    generateContent with inline ref parts, no composite needed
        ByteDance: text-to-image only, no reference sheet

Step 6  Drive upload
        Upload to Postcraft/ folder under brand Drive root
        Hard gate: if Drive upload does not return drive_file_id, fail before Stream artifact
        Never surface successful local-only or provider-URL-only image artifacts

Step 7  Thumbnail
        Pillow: 480px JPEG, ~10–20KB
        On Pillow unavailable: set asset_omitted: true, omit image_data_b64
        Never embed full-res bytes in artifact block
```

**No `analyze_output` / vision breakdown in the main pipeline.**
If needed, write `.breakdown.json` to `/tmp/bos-postcraft-runs/` as an audit file.
Never block the artifact on a second LLM call.

**Output artifact (`image_asset`, legacy_type: `post_image`):**
- `image_data_b64`: thumbnail (JPEG, ≤480px, ~10–20KB)
- `mime_type`: `image/jpeg`
- `drive_file_id` + `drive_web_view_link`: full-res in Drive
- `allowed_actions`: `[approve, revise, dismiss]`
- `action_modules`: `{"revise": "postcraft.render"}`

---

## Brand Asset Resolution — How Postcraft Knows Which Logo to Use

**The problem with the current design:** `reference_images` only contains what the
operator manually attached in chat. If they don't attach the logo, postcraft
generates with no logo and no brand colors.

**The fix:** Brand spec stored on `brand.brand_json` (or as a `WorkspaceDocument`
of type `postcraft_brand_spec`). `_brand_scoped_brief` resolves it automatically.

**Brand spec fields (stored per brand):**
```json
{
  "logo_drive_file_id": "1abc...",
  "color_palette": {
    "primary": "#C79A42",
    "background": "#0A0A09",
    "text": "#FFFFFF"
  },
  "typography": "luxury serif, uppercase headlines",
  "visual_tone": ["premium", "formal", "elegant"],
  "negative_prompts": ["cartoon", "neon", "cheap flyer", "horror cemetery"]
}
```

**Resolution order at runtime:**
1. Read `postcraft_brand_spec` from `brand.brand_json` or `WorkspaceDocument`
2. Fetch logo bytes from Drive using `logo_drive_file_id`
3. Inject as first item in `reference_images` (labeled "BRAND LOGO — place at top")
4. Operator-attached images are appended after — operator images take priority for
   hero/mascot slots; brand logo is always first

If no brand spec exists → `postcraft.draft` surfaces a setup instruction:
"Add a logo to this brand's Drive connection to enable auto-injection."

---

## Template Specs (JSON-based, not assembled prose)

Each `template_type` is a stored JSON spec following json-imagen's `spec_v2.json`
structure. The prompt is built by resolving `{{placeholders}}`, not assembled by hand.

**Shared spec structure:**
```json
{
  "template_name": "promo",
  "canvas": { "format": "square", "width": 1024, "height": 1024 },
  "quick_update_inputs": {
    "logo_file_url":    "{{auto_injected_from_brand_spec}}",
    "hero_asset_url":   "{{operator_attached_or_null}}",
    "headline":         "{{headline}}",
    "subheadline":      "{{subheadline}}",
    "body":             "{{body_copy}}",
    "cta":              "{{cta_text}}"
  },
  "brand_style": {
    "color_primary":    "{{color_palette.primary}}",
    "color_background": "{{color_palette.background}}",
    "color_text":       "{{color_palette.text}}",
    "visual_tone":      "{{visual_tone}}"
  },
  "generation_prompt": {
    "prompt":           "...(layout + copy instruction with {{placeholders}})...",
    "important_instruction": "...(composite panel placement rules)...",
    "negative_prompt":  ["{{negative_prompts}}", "cheap flyer", "neon colors", ...]
  }
}
```

**Core templates:** `promo` · `price_card` · `photo_hero` · `agent_award` · `educational`

Brand-specific design masters are optional production aids, not universal prerequisites. Normal Postcraft generation uses the approved Brand Creative Brief, official logo, active campaign truth, and relevant visual references to create an original channel-appropriate composition.

### Optional Brand Kit manifest templates

A brand may still register a locked layout for franchise systems, contractual co-branding, regulatory placement, localization, or intentionally repetitive campaign series. These templates live in `metadata_json.template_manifest.templates`. Postcraft validates and applies one only when the caller explicitly supplies `template_id` or deliberately requests `auto_select_template`; ordinary renders do not auto-select or block on the manifest.

Each template ships with a hand-built `example.html` (required BITE sample before
any template code is written — same gate as storyboard render targets).

---

## Composite Reference Sheet — Proven Rules (from json-imagen)

`gpt-image-2` via `images.edit` accepts exactly ONE source image. Multiple assets
require compositing into a single labeled reference sheet before the API call.

Rules that make it work:
1. Each asset gets its own panel, minimum 1024px wide so detail is legible to the model
2. Labels are drawn into the image itself — not just written in the prompt text
3. Labels name the asset AND its destination: `"BRAND LOGO — place at top center"`
4. Prompt must explicitly map each panel: "LEFT PANEL = logo, RIGHT PANEL = hero photo"
5. Prompt descriptions must match the labels drawn in the image
6. Delete the temp composite file in a `finally` block after the API call

**Asset size matters:** a small logo as the sole source image causes `images.edit`
to fill the canvas with it. Always use the composite sheet when a hero/portrait
is present alongside the logo, even if it means only two panels.

**Proven multi-asset outputs (from json-imagen prototype):**
- `v5.png` — logo top center + Ginto mascot lower right (composite reference sheet)
- `v6.png` — logo top center + Dakong Cruz property photo right panel

---

## What the API Actually Supports (13 attempts, json-imagen)

| Method | Multi-image | Reliable | Notes |
|---|---|---|---|
| `images.generate` | No | Yes | Text-only, no reference images |
| `images.edit` + large source | One image | Yes | Reliable path |
| `images.edit` + small source (logo only) | One image | Fragile | Model fills canvas with logo |
| `images.edit` + composite reference sheet | Effectively multiple | Yes | **The proven workaround** |
| `chat.completions` + gpt-image-2 | Multiple | No | 500 errors, rate limits |
| `responses.create` + gpt-image-2 | N/A | No | Model not found |

---

## Provider Matrix

| Provider | Reference assets | Composite sheet | Vision intake | Notes |
|---|---|---|---|---|
| **OpenAI** (default) | Yes — via `images.edit` | Yes (Pillow, RGBA PNG) | gpt-4o-mini | Scope check; no env-var key fallback |
| **Gemini** | Yes — inline parts | No | gpt-4o-mini | Flash for generation; 4o-mini for intake always |
| **ByteDance** | No | No | gpt-4o-mini | Text-to-image only |

Vision intake always uses OpenAI gpt-4o-mini regardless of image gen provider —
cheap chat call, avoids provider-specific vision branching.

---

## Revision Flow

Revision = `edit_instruction` present in brief + `original_artifact_block` from
prior run.

Module reads from `original_artifact_block` (one canonical key, set by BOS revise
endpoint):
- `brand_kit`: restore if new brief omits it
- `template_type`: restore if new brief omits it
- `post_format`: restore if new brief omits it
- `copy`: restore each field individually if new brief omits it
- `vision_intake`: restore `labeled_assets` if no new reference images attached

`edit_instruction` is prepended to the prompt as:
```
REVISION: {edit_instruction}
Apply this change only. Preserve all other brand elements, layout, colors,
typography, and assets exactly as they appear in the source image.
```

---

## Artifact Type Alignment

**Current (interim):** `type: image_asset`, `legacy_type: post_image`, thumbnail
as `image_data_b64`.

**Target:** `type: image_asset`, `asset_omitted: true`, `drive_file_id` + link.
The BOS `image_asset` renderer handles `asset_omitted` natively with a placeholder
card + Drive link. No thumbnail encoding required. No Pillow dependency on the
output path.

Migrate when the `image_asset` renderer in `ApprovalBundle.tsx` is verified to
render the Drive link card correctly for this artifact.

---

## Stability Rules (from Storyboard and NOTES.md)

1. **Never embed large binary payloads as base64 in artifact blocks.**
   Images → `image_asset` + `asset_omitted: true` + Drive meta.
   Video → `/tmp/bos_video_*.mp4` served via `/api/media/video/{filename}`.

2. **Every step must degrade independently.** Vision intake, composite, generation,
   Drive, thumbnail — each step's failure must produce a clean partial result,
   not crash the run.

3. **Never block the artifact on a second LLM call.** `analyze_output` is an
   audit trail, not a pipeline step. Write it to disk, never to the artifact block.

4. **No env-var API key fallback.** Credentials come from `_channel_credentials`
   only. BYOK model must not be bypassed silently.

5. **Pillow is optional.** All Pillow imports wrapped in `try/except ImportError`.
   Missing Pillow → skip composite → text-only generation. Note the degradation
   in the artifact. Never crash on a missing optional dependency.

6. **The gate protects provider cost.** `postcraft.render` must check
   `_is_render_approved()` before any provider call. If not approved, return a
   `postcraft_draft` artifact. This is the single most important stability rule.

---

## Workflow Stages

```
video_storyboard_pipeline equivalent for postcraft:

Stage 1: postcraft_draft_review  (artifact: postcraft_draft)
  module:  postcraft.draft
  actions:
    render   → postcraft.render  (transition to Stage 2)
    revise   → postcraft.draft   (loop)
    dismiss  → terminal

Stage 2: postcraft_image_review  (artifact: image_asset)
  module:  postcraft.render
  actions:
    approve  → terminal (publish-ready)
    revise   → postcraft.render  (loop with edit_instruction)
    dismiss  → terminal
```

Gates:
- Stage 1 approval: "Does this draft describe the right template, assets, copy, and colors?" — $0 cost
- Stage 2 approval: "Does the image match the approved draft?" — provider image cost

---

## Build Sequence

Order matches json-imagen/storyboard proven approach: sample before code.

**Phase A — Brand spec and logo injection**
1. Add `postcraft_brand_spec` field to `brand.brand_json` (logo_drive_file_id, colors, tone, negative_prompts)
2. Extend `_brand_scoped_brief` to auto-inject logo from Drive into `reference_images`
3. `postcraft.draft` capability: text-only artifact, zero provider cost

**Phase B — Template specs**
4. Core JSON template specs (promo, price_card, photo_hero, agent_award, educational) plus brand-scoped Postcraft template specs managed from the Brand Kit UI
5. Hand-built `example.html` per template (BITE gate — required before code)
6. `{{placeholder}}` resolution from brand spec + brief

**Phase C — Render capability**
7. `postcraft.render` with `_is_render_approved()` gate
8. Step-isolated pipeline (7 steps, each with independent fallback)
9. Pillow guard, composite cleanup, thumbnail as interim delivery

**Phase D — Artifact alignment**
10. Migrate to `image_asset` + `asset_omitted: true` once renderer verified

---

## Open Decisions

| Decision | Status |
|---|---|
| Brand spec stored as `brand.brand_json` field vs separate `WorkspaceDocument` | Open — `brand_json` simpler for V1 |
| `analyze_output` kept as optional audit file vs removed entirely | Open — remove for V1 |
| Per-template JSON specs stored in plugin `templates/` vs DB | Open — plugin files for V1 |
| Thumbnail interim vs `asset_omitted` target | Interim now, migrate after renderer verified |
