# Storyboard Plugin

Artifact-first / JSON-first storyboard planning with image rendering only after approval.

The plugin has two distinct jobs:

1. **Text generation** via `storyboard.create` — produce a reviewable Storyboard Draft / Video Production Blueprint artifact.
2. **Image generation or revision** via `storyboard.render` — render an approved storyboard into a black-and-white prototype storyboard sheet, or revise that sheet using the current image as the visual anchor.

Storyboard rendering is for **prototype/previsualization**, not polished ad art. Brand assets such as logos are used as identity references only where the approved storyboard explicitly asks for branded material.

---

## Pipeline

```text
User asks for storyboard / video / shot list
      ↓
storyboard.create
  → text artifact + structured JSON spec
  → no image model cost
      ↓ operator reviews / revises / approves
storyboard.render
  → black-and-white storyboard image artifact
      ↓ operator reviews / revises / approves
storyboard.render
  → revised storyboard image using source image + revision_prompt
      ↓ picture lock
storyboard.motion.render
  → previs / video handoff
```

`storyboard.create` never renders an image. `storyboard.render` is gated by approval and should not be used for first-pass planning.

---

## Text Generation: `storyboard.create`

### Purpose

Create the first reviewable **Storyboard Draft** or **Video Production Blueprint** artifact. The CMO must not paste the full storyboard into visible chat; it should pass the full markdown body in tool/RUN params, normally as `storyboard_text`.

### Quality contract

The text artifact must be production-ready, not a thin summary.

It must include:

- title / objective / audience / offer or CTA
- ordered shots or panels sized to the requested format, duration, platform, and story complexity
- no fixed panel count; do **not** force six panels or any other default count
- per-shot visual/action
- camera/composition or motion
- script/audio, dialogue, caption, or on-screen text beat where useful
- emotional purpose
- asset / location / prop / constraint notes when relevant
- continuity detail for characters, setting, props, wardrobe, and tone

For video work, the preferred body is a production blueprint with:

- Script section
- Screenplay / Text Storyboard table or ordered shot/panel sections
- Approval checklist
- `## Revised` section

Both markdown tables and ordered panel headings are valid. Examples of valid structures:

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

### Preflight quality gate

Chat v2 preflights storyboard tool calls before a Run is persisted. Invalid first drafts become internal tool feedback, not visible failed artifacts in Stream.

The gate checks for structure/detail, not a hardcoded shot count. It blocks missing essentials such as:

- no ordered shot/panel structure
- no audience/objective/offer context
- no visual/action detail
- no camera/composition/motion detail
- no audio/script/caption/text beat

Missing asset/constraint notes are advisory unless the storyboard depends on them.

---

## Image Generation: `storyboard.render`

### Initial render

Initial image render consumes an approved `storyboard_spec` / `spec_path` and produces one storyboard sheet.

Render style is fixed by the storyboard prototype contract:

- one cohesive storyboard sheet
- ordered connected panels
- rough black-and-white pencil/ink sketch style
- grayscale only
- no polished ads, photorealism, posters, UI mockups, or finished social creative
- avoid readable text/logos unless the storyboard explicitly requests them

### Brand and logo handling

Storyboard render now follows the Postcraft/json-imagen brand-reference pattern.

At execution time BOS hydrates `brand_kit.brand_spec` from the active Brand and Drive connection. When available, `brand_spec.logo_drive_file_id` identifies the official logo. `storyboard.render` will:

1. resolve `brand_spec` from `brand_kit.brand_spec`, `brand_spec`, or `brand_json`
2. fetch the official logo bytes from the brand's Google Drive connection
3. inject the logo as the first `reference_images` item
4. label it as:

```text
OFFICIAL BRAND LOGO — use only where storyboard explicitly requests logo/branded materials; render as rough grayscale storyboard reference
```

The logo is **not** automatically sprayed into every panel. It should only appear when the approved storyboard asks for a logo, branded folder, website, final CTA card, or other branded material.

For storyboard prototype output, logo use means:

- use the official logo as an identity / shape anchor
- render it in rough grayscale storyboard style
- do not create polished final logo lockups unless the downstream final-design step calls for it
- do not invent random logos or substitute lookalike marks

### Brand refs on first render

If `reference_images` exist and there is no source image:

```text
reference_images + approved spec → generate_with_refs
```

For OpenAI, this uses `images.edit` with low input fidelity. The prompt tells the model to use brand references as identity context, not to copy the reference sheet as the output.

---

## Image Revision

### Required inputs

A storyboard image revision must carry:

| Field | Description |
|---|---|
| `source_image_data_b64` / `source_image_path` | Current approved storyboard image; visual continuity anchor |
| `storyboard_spec` / `spec_path` | Approved JSON spec |
| `revision_prompt` | Authoritative instruction for the image model |
| `revision_feedback` | Raw operator note for audit only |
| `reference_images` | Optional character, location, logo, or asset references |

The previous image matters. A revised prompt/spec alone is not enough; the image model must see the current storyboard sheet to preserve composition and unchanged panels.

### CMO-authored `revision_prompt`

CMO should normally inspect the current storyboard image and write a precise, panel-referenced instruction.

Example user note:

```text
#6 outdoor pour scene like panel 1 but outside. #7 tombstone closeup then wide
```

CMO writes:

```text
Panel 6: change to a closeup of two mugs and a hand pouring hot water from a thermos. The table surface is visible but the background shows an open outdoor lawn — same composition as panel 1 but outside. Panel 7 (first sub-panel): closeup of a man's hand carefully placing a mug between flowers and a gravestone. Panel 7 (second sub-panel): wide shot of the man sitting outdoors, drinking from a mug, with the gravestone, flowers, and mug all visible in the frame. Preserve all other panels exactly.
```

### Logo-update revisions

Operators often say short things like:

```text
update logo
replace logo
fix branding
use official logo
```

For storyboard image revisions, the renderer now normalizes those phrases when an official logo reference is available. It expands them into an instruction that tells the model to:

- use the `OFFICIAL BRAND LOGO` reference from the labeled reference sheet
- target panels that contain an existing logo / brand mark / branded material / final CTA card when detectable
- render the logo as rough grayscale storyboard previsualization
- preserve every other panel, character, composition, camera angle, and storyboard style unchanged

This normalization is intentionally narrow. Other visual edits still require a precise CMO-authored `revision_prompt`.

---

## json-imagen / Postcraft Reference Sheet Rule

For OpenAI image edits, the reliable multi-reference path is a **single labeled composite reference sheet**, not loose prompt text.

When revising with both:

- the current storyboard image, and
- a logo / character / location / other reference image

`storyboard.render` builds one composite source image:

```text
PANEL 1: CURRENT APPROVED STORYBOARD — preserve layout and unchanged panels
PANEL 2: OFFICIAL BRAND LOGO — use where requested
PANEL 3: <optional other reference>
```

The prompt says:

- this is one labeled composite reference sheet
- do not copy the reference sheet layout into the output
- use Panel 1 as the continuity anchor
- use other labeled panels only for requested replacements/references
- output one revised storyboard sheet

This mirrors Postcraft/json-imagen lessons:

1. Draw labels into the image itself, not only into the prompt.
2. Give each asset a large enough panel for the model to read.
3. Match prompt labels to labels drawn in the sheet.
4. Preserve current design/storyboard geometry unless explicitly changing it.
5. Avoid using a tiny logo as the sole edit source; it can cause the model to fill the canvas with the logo.

---

## Render Modes

| Mode | Trigger | API behavior |
|---|---|---|
| `generate` | No source image, no refs | Text-to-image from spec |
| `generate_with_refs` | Brand/reference images, no source image | OpenAI edit with refs / provider equivalent |
| `edit` | Source image only | Edit current storyboard image |
| `edit_with_reference_sheet` | Source image + logo/reference images | Edit using labeled composite reference sheet |
| `gemini_generate` | Gemini backend | Prompt + inline image parts |
| `bytedance_generate` | ByteDance backend | Text-to-image only |

---

## Prompt Assembly

`build_prompt()` assembles the image prompt in this order:

1. mode header and image/reference mapping
2. storyboard prototype rendering contract
3. revision instruction block, if present
4. critical storyboard preservation rules
5. source storyboard text
6. JSON spec metadata

When `revision_prompt` exists, the prompt treats it as authoritative. Otherwise, raw `change_request` data is only audit/supporting context.

---

## Spec Shape

```json
{
  "artifact_kind": "video_production_blueprint",
  "source_storyboard_text": "...",
  "production_blueprint": { "source_text": "...", "tables": [] },
  "project": { "title": "...", "aspect_ratio": "9:16" },
  "revision": { "variation_id": "v001", "updated_at": "..." },
  "global_visual_rules": {
    "style": "clean black-and-white hand-drawn storyboard prototype sketch",
    "palette": "black, white, and grayscale only"
  },
  "locked_elements": {
    "must_preserve_across_revisions": [],
    "do_not_add": []
  },
  "acts": [{
    "act_number": 1,
    "shots": [{
      "shot_number": 1,
      "time": "0-5s",
      "script_audio": "...",
      "on_screen_text": "...",
      "action": "...",
      "composition": "...",
      "emotional_intent": "...",
      "must_include": [],
      "must_avoid": []
    }]
  }],
  "brand_assets": {
    "count": 0,
    "reference_images": []
  }
}
```

`brand_assets` stores explicit references supplied during storyboard creation. Official logo injection during render comes from `brand_kit.brand_spec.logo_drive_file_id` and may not appear in the original create spec.

---

## Output Artifacts

### `storyboard.create` block

- `type: storyboard_json`
- `artifact_type: draft_artifact`
- `storyboard_text`
- `storyboard_spec`
- `production_blueprint` when applicable
- `allowed_actions: approve_blueprint/render/revise/dismiss` when valid

### `storyboard.render` block

- `type: image_asset`
- `legacy_type: storyboard_image`
- `storyboard_spec`
- `storyboard_text`
- `brand_kit`
- `brand_spec`
- `brand_reference_count`
- `logo_revision_normalized` when a short logo note was expanded
- `image_data_b64` and thumbnail data for revision continuity
- Drive metadata when upload succeeds
- `allowed_actions: approve/generate_video/revise/dismiss`

Each render writes:

| File | Content |
|---|---|
| `{stem}.png` | Rendered storyboard image |
| `{stem}.spec.json` | Spec used for this render |
| `{stem}.prompt.txt` | Exact provider prompt |
| `{stem}.response.json` | Provider/output metadata |

---

## Google Drive and Brand Kit

Drive is per-brand. BOS injects Drive credentials and root folder data into `_channel_credentials` at execution time.

The canonical brand kit for execution is hydrated by `routers/runs.py` and includes:

- brand id/name/voice/tone/values
- color palette and visual constraints
- `brand_spec`
- `brand_spec.logo_drive_file_id` when the Drive Brand Kit validation found an official logo
- campaign alignment when available

Storyboard render stores outputs in the brand Drive root under:

```text
Brand Kit root/
└── Storyboard/
```

---

## What Not To Do

- Do not dispatch `storyboard.render` for first-pass storyboard planning.
- Do not render a text/image storyboard before the text/JSON artifact is approved.
- Do not hardcode a fixed number of panels.
- Do not ask the image model for polished advertising art, photorealism, or finished social creative.
- Do not rely on text-only “use logo” instructions; pass the official logo as a reference.
- Do not use a tiny logo as the sole OpenAI edit source for revision; use the composite reference sheet with the current storyboard image.
- Do not treat raw `revision_feedback` as sufficient for general image edits; write `revision_prompt` unless the edit is one of the narrow normalized logo-update cases.

---

## Files

```text
storyboard/
├── channel.json
├── SKILL.md
├── README.md
├── STORYBOARD.md
├── storyboard.md
├── lib/json_image_storyboard.py
├── capabilities/storyboard/json/create/
├── capabilities/storyboard/json/render/
├── capabilities/storyboard/json/validate/
├── capabilities/storyboard/json/generate/
└── examples/
```
