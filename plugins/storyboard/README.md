# Storyboard BOS Plugin

Official BOS plugin for **artifact-first / JSON-first storyboard planning** with image rendering only after approval.

This plugin packages the successful `openai-json-image-prototype` workflow into BOS capabilities, but broad CMO requests now start by dispatching a text/JSON artifact via hidden `storyboard.create` params instead of drafting inline or generating images directly:

- `storyboard.create` — create or normalize a human-readable storyboard text artifact plus structured JSON source of truth.
- `storyboard.validate` — validate spec shape and missing shot-control fields.
- `storyboard.render` — render or revise approved storyboard images with OpenAI Images, returned as a native BOS `image_asset` review card.
- `storyboard.generate` — compatibility alias for `storyboard.render`; not chat-routable.

Validated through live CMO chat on 2026-06-19: CMO previously dispatched `storyboard.render` directly. Routing is now optimized so broad video/storyboard requests dispatch `storyboard.create` first, producing a reviewable text/JSON artifact with no provider image cost. `storyboard.render` remains available as an approval/action step and returns native `image_asset` with `legacy_type: storyboard_image`.

## Core workflow

1. Create a human-readable storyboard text artifact plus structured JSON source of truth via `storyboard.create` hidden RUN params.
2. Review/revise/approve the artifact text and JSON before any image generation.
3. For a single storyboard/screenplay artifact, keep total planned runtime at 15 seconds or less until multi-shot video stitching is supported.
4. Render v001 from the approved full JSON.
5. For revisions, create v002/v003 JSON with only the requested changes.
6. Pass the previous approved render as `source_image_path` or `source_image_data_b64`.
7. Save audit files for every render:
   - image output
   - `.spec.json`
   - `.prompt.txt`
   - `.response.json`

In BOS containers, external plugins are mounted read-only, so audit files default to `/tmp/bos-storyboard-runs` unless `output_dir` or `out` is provided.

## Why this exists

The prototype proved that storyboard edits are more controllable when the model receives both:

- the revised JSON spec, and
- the previous approved image as the visual continuity anchor.

This enabled edits like:

- make Shot 1 an empty table,
- move the empty mugs to Shot 2,
- show hands placing the mugs,
- remove an extra spoon,
- swap shot order,
- preserve the pencil sketch style and emotional tone.

## Render input examples

Render from a JSON spec path:

```json
{
  "spec_path": "/home/ubu/bos-plugins/storyboard/examples/the_widower_v001.json",
  "out": "/home/ubu/bos-plugins/storyboard/runs/the_widower_v001.png"
}
```

Revise using prior image as source/reference:

```json
{
  "spec_path": "/home/ubu/bos-plugins/storyboard/examples/the_widower_v002.json",
  "source_image_path": "/home/ubu/bos-plugins/storyboard/runs/the_widower_v001.png",
  "out": "/home/ubu/bos-plugins/storyboard/runs/the_widower_v002.png"
}
```

Localized edit with mask:

```json
{
  "spec_path": "specs/v003.json",
  "source_image_path": "runs/v002.png",
  "mask_image_path": "masks/shot_02_area.png",
  "out": "runs/v003.png"
}
```

Mask convention:

- transparent area = editable
- opaque area = preserve

## Spec strategy

Keep these stable between versions unless the edit explicitly changes them:

- `project`
- `global_visual_rules`
- `locked_elements`
- act metadata
- unchanged shot fields
- style / palette / composition rules

Only change the exact shots and fields requested by the revision.

## Shot field pattern

For best compliance, each shot should include:

- `title`
- `image_prompt`
- `composition`
- `action`
- `emotional_intent`
- `must_include`
- `must_avoid`

Repeat critical constraints in both positive and negative fields. Example:

```json
{
  "must_include": ["no other spoon"],
  "must_avoid": ["second spoon", "spare spoon"]
}
```

## OpenAI model gotcha

`gpt-image-2` rejected `input_fidelity` during edit calls in prototype testing. The plugin includes retry logic that removes unsupported parameters when the provider rejects them.

## Credentials

BOS should inject:

- `PLATFORM_OPENAI_KEY`

The module also checks `OPENAI_API_KEY` and `PLATFORM_OPENAI_KEY` environment variables directly as a fallback. The implementation uses stdlib HTTP so the BOS API image does not need the `openai` Python package installed.

## Files

```text
storyboard/
├── channel.json
├── SKILL.md
├── README.md
├── lib/json_image_storyboard.py
├── capabilities/storyboard/json/create/
├── capabilities/storyboard/json/validate/
├── capabilities/storyboard/json/render/
├── capabilities/storyboard/json/generate/
├── examples/the_widower_v001.json
├── examples/the_widower_v002.json
└── runs/
```
