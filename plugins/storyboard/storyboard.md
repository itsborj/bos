# Storyboard Plugin Quick Reference

See `STORYBOARD.md` for the full pipeline contract. This file is the short operational reference for CMO/tool behavior.

**Plugin ID:** `channel.storyboard`  
**Default image backend:** OpenAI `gpt-image-2`  
**Primary workflow:** text/JSON approval → storyboard image → picture lock → previs/video

---

## Capabilities

| Module ID | Job | Notes |
|---|---|---|
| `storyboard.create` | Text generation | Creates reviewable Storyboard Draft / Video Production Blueprint. Never renders an image. |
| `storyboard.render` | Image render/revision | Renders approved spec or revises current storyboard image. |
| `storyboard.validate` | Validation | Validates spec shape and shot-control fields. |

---

## Text Generation Contract (`storyboard.create`)

The CMO must create a **production-ready text artifact**, not a thin summary.

Required qualities:

- title / objective / audience / offer or CTA
- ordered shot or panel structure sized to the request
- no hardcoded panel count; do not force six panels
- per-shot visual/action
- camera/composition or motion
- script/audio/caption/on-screen text beat where useful
- emotional purpose
- asset/location/prop/constraint notes when relevant
- continuity detail for characters, settings, props, wardrobe, and tone

Valid text formats include markdown tables or ordered panel headings:

```md
| Shot | Time | Script / audio | On-screen text | Visual / action | Camera / motion | Assets / constraints |
|---|---|---|---|---|---|---|
| 1 | 0-5s | ... | ... | ... | ... | ... |
```

```md
### Panel 1
- Visual/Action: ...
- Camera/Composition: ...
- Caption/Audio: ...
- Emotion: ...
- Assets/Constraints: ...
```

Chat v2 preflights this before creating a Run, so invalid storyboard drafts should not appear as failed Stream artifacts.

### Review-state contract — recurring bug guard

`storyboard.create` produces a text/JSON artifact for operator review. A successful self-check does **not** mean it is approved.

Required defaults:

- `storyboard.create` block must include `approval_status: "pending"` when valid.
- The persisted Run must remain `approval_status = "pending"` unless the block is failed/needs revision.
- Core execution must honor the artifact block's `approval_status`; it must not auto-promote successful text artifacts to `approved` simply because `self_check == pass`.
- Stream should display valid `storyboard_json` / Video Production Blueprint artifacts as **Needs review** by default.

Known recurring failure mode:

- Stream shows `Storyboard Draft` / `Video Production Blueprint` as `Approved` immediately after creation.
- No review decision happened.
- The render/video pipeline appears to skip or dead-end because the text artifact is already marked approved.

Root cause pattern:

- Generic Run persistence auto-approves successful tool artifacts that do not have `publish_*` actions.
- `storyboard.create` has `render`/`revise` actions, not publish actions, so it can be incorrectly auto-approved unless core honors `block.approval_status`.

Required compatibility behavior:

- If `/runs/{id}/approve` is called for a persisted block with `type == "storyboard_json"` and `action_modules.render`, route it to the declared `render` action instead of only flipping `runs.approval_status = approved`.
- Existing stale `storyboard_json` runs already marked `approved` but still carrying `action_modules.render` should be treated as actionable/pending by Stream so the operator can render them after the fix.
- Rendering a text artifact creates a new storyboard image artifact. That image artifact should also keep its own review default (usually `pending`) so video generation only happens after image storyboard approval.

This is the same class of bug as Postcraft draft approval: approval of a staged text artifact is a workflow transition, not a final terminal status.

---

## Image Generation Contract (`storyboard.render`)

Initial render requires approved text/JSON plus validated Brand assets. Before any image provider call, `storyboard.render` must verify Google Drive is connected, a validated Brand Kit Drive root folder exists, and an official logo/wordmark Drive file ID is available. Output is a rough **black-and-white storyboard prototype sheet**, not polished creative.

### Brand asset spec bridge — recurring bug guard

`storyboard.render` requires `brand_spec.logo_drive_file_id`. The approved text artifact created by `storyboard.create` may not contain that spec, because the logo is resolved later from Drive/onboarding metadata.

Required behavior:

- Core execution must inject `brand_spec` for `storyboard.render` from the active Brand before render preflight runs.
- Valid sources include the Brand's connected Google Drive `SocialConnection.token_meta_json` and the latest `campaign_brand_kit.metadata_json`.
- Both metadata shapes must be supported:
  - direct fields: `brand_mark_file_id`, `brand_mark_file_name`, `drive_root_folder_id`, `drive_root_name`
  - onboarding validation fields: `imprint_asset_folder.id/name` and `imprint_asset_validation.logo_files[0].id/name/mimeType`
- The bridge should set both top-level `brief.brand_spec` and `brief.brand_kit.brand_spec` when a brand kit is present.

Known recurring failure mode:

```text
Storyboard render failed — Storyboard blocked before image generation: missing official_logo_drive_file_id
```

Root cause pattern:

- `storyboard.create` produces a valid text artifact with `action_modules.render`.
- The action brief copied from that artifact lacks `brand_spec`.
- `storyboard.render` preflight runs before the official logo metadata is bridged into the brief.

Do not fix this by making logo optional. Storyboard render should remain strict; the correct fix is to hydrate the official logo Drive file ID before render preflight.

Rules:

- one cohesive sheet with ordered connected panels
- grayscale pencil/ink storyboard style
- preserve shot order, characters, locations, props, and emotional progression
- no photorealistic renders, finished ads, posters, UI mockups, or social creative
- no readable text/logos unless explicitly requested by the approved storyboard

---

## Proper Logo and Brand Visual Asset Use

Storyboard image generation follows the Postcraft/json-imagen brand-reference pattern.

At execution time BOS hydrates `brand_kit.brand_spec`. `storyboard.render` requires `brand_spec.logo_drive_file_id`, fetches the official logo from the brand's Google Drive connection, and prepends it to `reference_images` as:

```text
OFFICIAL BRAND LOGO — use only where storyboard explicitly requests logo/branded materials; render as rough grayscale storyboard reference
```

The same validated Brand Kit folder may also provide optional visual references: mascot, product, people, location, vehicle/property, template/reference masters, or style images. These are passed as additional image references when present and relevant.

Important:

- Do not rely on text-only instructions like “use logo.” The official logo must be passed as an image reference.
- The logo should appear only where the approved storyboard asks for a logo, branded folder, website, final CTA card, or branded material.
- The logo is an identity/shape anchor for storyboard previsualization; it should be rendered in rough grayscale style, not as polished final branding.
- Do not invent random logos or substitute lookalike marks.

---

## Image Revision Contract

General revisions require:

| Field | Description |
|---|---|
| `source_image_data_b64` / `source_image_path` | Current storyboard image; visual continuity anchor |
| `storyboard_spec` / `spec_path` | Approved spec |
| `revision_prompt` | Precise instruction for the image model |
| `revision_feedback` | Raw operator note for audit |
| `reference_images` | Optional logo / character / location / asset refs |

CMO should inspect the current storyboard image and write a panel-specific `revision_prompt`, e.g.:

```text
Panel 6: replace the invented mark on the CTA card with the official Golden Gate logo reference. Keep the card layout, panel borders, grayscale storyboard style, and all other panels unchanged.
```

### Short logo notes

If the operator says `update logo`, `replace logo`, `fix branding`, or similar, and an official logo reference exists, the renderer normalizes the note into a precise logo instruction:

- target logo / brand mark / branded material / final CTA panels when detectable
- use `OFFICIAL BRAND LOGO` from the reference sheet
- preserve all other panels and composition
- keep rough grayscale storyboard style

This normalization is narrow. Other edits still need a real `revision_prompt`.

---

## json-imagen Reference Sheet Rule

When revising with both the current storyboard image and a logo/reference image, OpenAI uses one labeled composite source image:

```text
PANEL 1: CURRENT APPROVED STORYBOARD — preserve layout and unchanged panels
PANEL 2: OFFICIAL BRAND LOGO — use where requested
PANEL 3: optional extra reference
```

Prompt rules:

- this is a reference sheet, not the output layout
- use Panel 1 as continuity anchor
- use other panels only for requested substitutions/references
- output one revised storyboard sheet

This avoids the known failure mode where a tiny logo used as the sole edit source causes the model to fill the canvas with the logo.

---

## Render Modes

| Mode | Trigger |
|---|---|
| `generate` | Approved spec, no source image, no refs |
| `generate_with_refs` | Approved spec + brand/reference images |
| `edit` | Source storyboard image only |
| `edit_with_reference_sheet` | Source storyboard image + logo/reference images |
| `gemini_generate` | Gemini backend |
| `bytedance_generate` | ByteDance backend |

---

## Output Block Highlights

`storyboard.render` returns an `image_asset` block with:

- `legacy_type: storyboard_image`
- `storyboard_spec`
- `storyboard_text`
- `brand_kit`
- `brand_spec`
- `brand_reference_count`
- `logo_revision_normalized` when applicable
- `image_data_b64` / thumbnail for revision continuity
- Drive metadata when upload succeeds
- actions: `approve`, `generate_video`, `revise`, `dismiss`

---

## Do Not

- Do not dispatch `storyboard.render` for first-pass storyboard planning.
- Render actions must carry the approved `storyboard_spec` from the source `storyboard_json` artifact. If a stale/thin action brief only has approved storyboard markdown, `storyboard.render` defensively reconstructs the spec from that approved text before preflight so approval does not fail with `missing storyboard_spec`.
- Do not hardcode a fixed panel count.
- Do not surface thin storyboard summaries for approval.
- Do not generate polished ad art from storyboard render.
- Do not treat raw feedback as enough for general image edits.
- Do not use text-only logo instructions; pass official logo as a reference.
