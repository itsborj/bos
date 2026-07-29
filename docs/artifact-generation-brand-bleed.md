# Artifact Generation Recurring Issue: Brand Bleed and Guideline Text Leakage

Date investigated: 2026-06-22

## Incident investigated

Artifact/run ID: `4009af25-50aa-4d3d-bec1-28c0a8706e89`

This was not a standalone uploaded artifact row. It is a `runs.id` row:

- Module: `marketing.creative.imprint.generate`
- Brand: `Golden Gate Memorial` (`10967e2e-bfd2-4687-a150-d01a9f0d6617`)
- Workspace: `Üñ³`
- Parent run: `3e8f997a-227c-464c-bf06-df83e9337fe0`
- Parent module: `imprint.draft`
- Trigger: operator approved the text-only imprint draft; backend auto-dispatched the image-generation action.
- Result file: `imprint_1782111712.png`, uploaded to Google Drive as `1zHYCOgqmkvER96NFk5PJO8Acmnz5jqti`
- Selected Drive template: `22-template-columbarium-light.png`
- Copy approved in Gate 1:
  - Headline: `Plan today`
  - Supporting line: `For your family's peace`
  - CTA: `Learn More`

Backend path:

1. `PATCH /runs/{parent_run_id}/approve` marks the `imprint.draft` run approved.
2. `api/routers/runs.py::approve_run` detects block type `imprint_draft` and calls `execute_declared_run_action(..., action="approve")`.
3. `execute_declared_run_action` resolves `action_modules.approve` to `marketing.creative.imprint.generate`.
4. `_execute_module` injects brand scope, image provider credentials, Drive credentials, and campaign brand-kit style constraints.
5. `api/capabilities/creative/imprint/generate/module.py` uses the `prompt_integrated_ai` path and calls `media.image.generate` with approved copy plus raw style constraints.
6. The generated PNG is then logo-overlaid and uploaded to Drive.

## Observed failure

The final image contained visible non-client/system artifacts, including:

- A large `BOS` logo/wordmark generated into the image.
- Faint repeated watermark-like `BOS ...` text.
- Visible guideline/design-token remnants such as hex/color-token-looking text (`#111827`, `#3422...`, `ffffff`) and similar metadata-like strings.
- Provider/watermark-like text (`AI generated`) despite instructions not to add watermarks.

This means the failure is not just a metadata issue; parts of the internal prompt and brand-guideline vocabulary became pixels in the client-facing artifact.

## Why it happened

The artifact was brand-scoped correctly in the database. The bleed came from prompt construction and artifact rendering boundaries.

### 1. The media model was given internal system vocabulary

The image-generation prompt included phrases such as:

- `... the real brand logo may still be stitched by BOS.`
- `BOS will composite the approved copy and real logo after base-image generation.`
- `Leave safe space for BOS-applied captions, CTA, typography, and logo overlays.`

Even though these were intended as instructions, the image model treated `BOS` as visual brand text and rendered it.

### 2. Brand guidelines were passed as prompt text, not structured non-renderable constraints

`_inject_campaign_brand_kit_style()` extracts campaign brand-kit markdown into `brand_visual_constraints`. That string still contains human-readable token names and values, e.g. color token names, hex values, usage labels, and voice summaries.

`imprint.generate::_build_imprint_prompt()` appends this directly as:

```text
Brand constraints: <constraints>
```

`media.image.generate` may append it again as:

```text
Use the following as non-visible brand style constraints only; do not render ...: <constraints>
```

For image models, negative text instructions are unreliable. Supplying exact token names and hex values makes them candidates for visible typography.

### 3. Prompt-integrated copy path asks the image model to typeset the final ad

For this run:

- `image_source = ai_prompt_integrated`
- `copy_integration_mode = prompt_integrated_ai`
- `copy_sent_to_image_model = true`
- `copy_composited = false`

Because the model was responsible for both artwork and typography, it also hallucinated extra readable text. The deterministic compositor did not get a chance to enforce an allow-list of approved visible copy.

### 4. Raw prompts are stored and surfaced as artifact content/metadata

`media.image.generate` returns content in the form:

```text
Image generated successfully (... bytes). Prompt: <full prompt>
```

and stores the prompt in the block. Imprint stores `image_generation_prompt` in the final block. This is useful for audit, but it means raw brand guidelines can appear in artifact details or fallback previews unless renderers explicitly hide internal prompt fields.

## Recurring pattern

This issue has appeared in multiple imprint runs using the same prompt-integrated AI path, for example:

- `4009af25-50aa-4d3d-bec1-28c0a8706e89` — visible `BOS` logo/text and hex-token-looking strings.
- `2ca2312e-3212-4338-a1e6-03e3dd834c5f` — visible guideline token `neutral-700`, truncated CTA/copy, and provider watermark.
- `e1ebceeb-7b8d-41bb-b35e-8c792dce62e4` — visible `BOS`, truncated body/CTA, and provider watermark.

## Impact

- Client trust risk: internal BOS/system brand appears inside client creative.
- Brand compliance risk: guideline names and implementation tokens become user-visible copy.
- Review risk: self-check currently passes because it validates text metadata, not visual OCR/pixel content.
- Approval-loop risk: artifacts can look successful in run state while being unusable as client-facing assets.

## Recommended fixes

1. **Remove BOS/internal product names from provider prompts.** Use neutral wording like `post-processing will add approved logo and typography`.
2. **Do not send raw brand guideline text or token names to image models.** Compile guidelines into visual attributes only: palette swatches, mood, contrast, composition, font style — not labels such as `color-neutral-700` or `#111827` unless the provider supports non-renderable structured controls.
3. **Prefer deterministic copy/logo composition for final ads.** Let AI generate background/imagery only; render approved headline, supporting copy, CTA, and logo in a controlled compositor with an allow-list.
4. **Add OCR/vision self-check before marking image artifacts pass.** Fail if visible text contains anything outside the approved copy allow-list plus allowed brand logo text.
5. **Keep raw prompts out of reviewable artifact surfaces.** Store prompts in audit/system details only, not in `content` or default preview fields.
6. **Add regression fixtures for generated artifacts.** Include checks for forbidden visible strings: `BOS`, `color-`, `neutral-`, `Hex`, `Usage`, `AI generated`, and unapproved `#` color codes.

## Mitigation implemented

The first code mitigation now removes internal BOS wording from media prompts, sanitizes brand-kit constraints before they reach image/video providers, defaults Imprint to deterministic copy/logo post-composition instead of model-rendered typography, and stops raw provider prompts from appearing in default image artifact content/previews. OCR/vision self-check remains a recommended follow-up.
