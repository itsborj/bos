# Postcraft Operating Contract

## Non-negotiable preflight

Postcraft must never generate, render, or revise a post without all three alignment inputs present:

1. **Brand kit loaded**
   - Brand ID and brand name are present.
   - Brand voice/tone/colors or approved brand visual constraints are present.
   - Generic placeholders such as `brand` or `this brand` are not acceptable.

2. **Google Drive + official logo resolved**
   - Google Drive is connected for the selected Brand.
   - A validated Brand Kit Drive root folder is present.
   - A real logo/wordmark Drive file ID is available from the Postcraft brand spec or the Brand Kit Drive folder validation metadata.
   - Google Drive credentials are available so the logo can be downloaded and included as a visual reference.
   - Postcraft must not rely on prompt text such as “use the logo” unless the actual logo image is sent to the image model.

3. **Optional Brand visual references loaded when present**
   - The validated Brand Kit Drive folder may include mascot, product, people, location, vehicle/property, template/reference masters, or style-reference images.
   - These are injected as additional visual references alongside the logo when relevant.
   - Missing optional references do not block generation; missing Drive root or logo does.

4. **Campaign alignment loaded**
   - The run has a campaign ID and campaign context/alignment data.
   - The brief must carry the campaign name/goal/audience/message angle when available.
   - If no campaign is selected, Postcraft returns a setup blocker instead of spending image-generation credits.

If any required item is missing, Postcraft returns a failed/setup-blocker artifact with a checklist of missing items. It must not call the image provider.

## Revision contract — agency-grade JSON/spec-based image editing

Postcraft revisions must behave like an ad-agency creative revision against an existing approved comp, not like a fresh text-to-image prompt. The operator/client is usually saying “change this part of the current ad” while implicitly expecting the rest of the approved layout, brand identity, and message to remain stable.

The critical lesson from the json-imagen / storyboard image pipeline is that `gpt-image-2` is much more consistent when image editing is driven by a structured JSON spec plus the prior image, rather than by a vague natural-language prompt alone. Postcraft should therefore be **spec-driven editing**, not prompt-driven editing.

### Core revision invariant

For every image revision:

1. The previous approved/generated Postcraft image is the primary source image.
2. The operator's revision note is authoritative.
3. Any newly attached images are revision reference assets, not generic prompt stuffing.
4. The image model receives a structured JSON edit spec that says exactly what changes and what remains locked.
5. Postcraft must preserve the approved comp by default and apply only the requested delta.

An updated prompt/spec without the previous image is not a valid image revision. It is a regeneration and should not be presented as an agency-style revision.

### Canonical artifact render spec

Every successful Postcraft `image_asset` should persist a canonical render spec on the block. Existing fields such as `copy`, `brand_kit`, `brand_spec`, `template_type`, `post_format`, `prompt`, `vision_intake`, and provider metadata are useful, but coding should converge on one explicit JSON object for revision handoff.

Recommended shape:

```json
{
  "schema": "postcraft.render_spec.v1",
  "artifact_kind": "social_post_image",
  "layout": {
    "template_type": "promo",
    "post_format": "square",
    "size": "1024x1024",
    "composition_notes": "large headline, CTA band, hero image panel"
  },
  "brand": {
    "brand_id": "...",
    "name": "Golden Gate Memorial",
    "colors": {
      "primary": "#342f2c",
      "accent": "#c8a84b",
      "background": "#d8d2c8"
    },
    "logo_drive_file_id": "...",
    "visual_constraints": "approved brand visual rules"
  },
  "campaign": {
    "campaign_id": "...",
    "goal": "...",
    "audience": "...",
    "message_angle": "..."
  },
  "copy": {
    "headline": "...",
    "subheadline": "...",
    "body": "...",
    "cta": "...",
    "location": "..."
  },
  "visuals": {
    "logo_position": "top_center",
    "hero_role": "background_or_product",
    "text_safe_area": "preserve current readable text zones",
    "reference_assets_used": []
  },
  "locked_elements": [
    "brand identity",
    "approved copy unless explicitly changed",
    "layout geometry",
    "logo placement unless explicitly changed",
    "campaign tone",
    "readability and platform format"
  ]
}
```

The render spec is not only audit metadata. It is the contract used for later revisions.

### Revision spec / JSON patch first

A revision should first be normalized into a structured revision spec. This can be done deterministically when obvious, or by the CMO/tool layer when the operator feedback is ambiguous. The image provider prompt should include this JSON verbatim or a compact equivalent.

Recommended shape:

```json
{
  "schema": "postcraft.revision_spec.v1",
  "source_artifact_id": "run-id",
  "source_render_spec_schema": "postcraft.render_spec.v1",
  "mode": "localized_image_edit",
  "operator_feedback": "Replace the hero image with the attached product photo, keep everything else the same.",
  "change_request": {
    "summary": "Replace hero visual only",
    "edits": [
      {
        "target": "hero_image",
        "operation": "replace",
        "reference_asset_id": "ref_product_1",
        "instructions": "Use the product photo as the new hero visual while preserving the current layout and copy.",
        "preserve": [
          "overall layout",
          "brand colors",
          "logo",
          "headline",
          "CTA",
          "typography style",
          "campaign tone"
        ]
      }
    ]
  },
  "reference_assets": [
    {
      "id": "ref_product_1",
      "role": "replacement_hero_image",
      "source": "operator_attachment",
      "title": "product-photo.png"
    }
  ],
  "locked_elements": [
    "do not redesign the full ad",
    "do not change copy unless explicitly requested",
    "do not invent a different logo",
    "do not alter the brand palette",
    "do not reinterpret style references as replacement assets"
  ]
}
```

This JSON patch/spec matters because it gives `gpt-image-2` stable targets, operations, and locked elements. Natural-language revision prompts should be treated as input to the revision spec, not as the only provider instruction.

### Agency interpretation of attachments

Multiple image attachments in a revision are normal agency workflow: product packshots, alternate hero photos, client-supplied people/location images, logo updates, competitive/mood references, screenshots with offer details, etc. They must become durable, labeled revision assets.

Each attached image should be enriched into a structured asset record:

```json
{
  "id": "ref_1",
  "title": "family-photo.jpg",
  "mime_type": "image/jpeg",
  "drive_file_id": "...",
  "vision_b64": "...",
  "source": "operator_attachment",
  "revision_reference": true,
  "priority": "operator_revision",
  "role": "replacement_hero_image"
}
```

Allowed roles include:

- `replacement_hero_image` — replace the current hero/background/product visual.
- `product_reference` — include or correct a product/packshot.
- `person_or_portrait_reference` — preserve likeness/pose/identity when relevant.
- `location_reference` — use this venue/property/interior/exterior.
- `logo_update` — replace or correct brand mark only when explicitly requested.
- `style_reference` — borrow mood, lighting, or art direction, not literal content.
- `copy_or_offer_reference` — use for factual offer/context extraction, not as a visual element unless requested.
- `unknown_revision_reference` — role unclear; ask a clarifying question if the requested change cannot be inferred.

Important: attached references should not automatically replace the whole ad. Their role is determined by the operator feedback and/or explicit selection. If the operator says “use these” with several unrelated images and no target, ask which image replaces which part. If the feedback says “replace the background with image 2 and add the product from image 1,” proceed without asking.

### Source/reference image ordering

For revisions, visual priority must be:

1. current generated Postcraft image — the approved comp and continuity anchor,
2. operator-attached revision references — the new client direction,
3. official brand logo — included when needed for brand lockup or because the current comp/logo must be preserved,
4. optional supporting brand visual assets — mascot/product/location/template references from the Brand Kit folder.

For initial renders, visual priority must be:

1. official brand logo,
2. operator-supplied reference images from chat/brief attachments,
3. optional supporting brand visual assets.

Do not let auto-injected brand assets crowd out operator-provided references. The concrete bug was that `_inject_logo()` prepended logo and Brand visual assets before operator references, and later processing used `reference_images[:4]` on initial render. That allowed a valid attached image to survive enrichment in the CMO brief yet still get pushed out before vision intake/composite generation, so the final render ignored the user attachment. Postcraft selection must therefore preserve operator-provided references ahead of optional brand refs on both initial renders and revisions.

### Composite/contact-sheet requirement

When provider constraints or the current client code path allow only one edit source image, Postcraft should build one labeled composite/contact sheet rather than dropping inputs. The composite should contain panels such as:

- `CURRENT APPROVED DESIGN — preserve layout, identity, and unchanged elements`
- `OPERATOR REF 1 — replacement hero image`
- `OPERATOR REF 2 — product reference`
- `OFFICIAL BRAND LOGO — preserve/use according to render spec`

The provider prompt must explicitly map each panel to the JSON revision spec. Never mention a reference sheet unless the image is actually sent to the provider.

If the image provider/API supports multiple input images, the adapter may send separate images instead of a contact sheet, but the same labeling and JSON spec rules still apply. The model must be told which image is the source comp and what each reference asset is for.

### Provider prompt pattern

The image-edit prompt should follow this pattern:

```text
You are editing an existing approved social ad.

IMAGE 1 / PANEL 1 is the CURRENT APPROVED DESIGN. Preserve it except where the JSON revision spec explicitly requests a change.

Other images/panels are labeled reference assets. Use each only for the role stated in the JSON revision spec.

Apply the JSON revision spec exactly.
Do not redesign the ad.
Do not change copy unless the JSON says to.
Do not invent new brand elements.
Do not treat style references as replacement assets.

JSON_REVISION_SPEC:
{...}

SOURCE_RENDER_SPEC:
{... compact prior render spec ...}
```

The older freeform `revision_prompt` should still be stored for audit, but the provider-facing instruction should be generated from the structured revision spec.

### No silent truncation

Postcraft must never silently discard operator-provided revision attachments. If there are too many references for the provider path:

- Prefer building a larger labeled contact sheet.
- If visual detail would become too small, ask the operator which references matter most.
- If a hard limit remains, return a clear setup/revision blocker explaining which assets need prioritization.

Silent `reference_images[:4]` truncation is acceptable only for optional background Brand Kit refs, not for operator revision refs.

### ApprovalBundle routing, revision references, and template intent split

Postcraft is plugin-owned. The runtime source of truth is `plugins/postcraft/`, and inline review cards must use the plugin-owned endpoints:

- draft approval → `POST /postcraft/runs/{run_id}/render`
- revision → `POST /postcraft/runs/{run_id}/revise`

Do not route Postcraft approval/revision through legacy `chat.py` paths or plugin-specific branches in the generic CMO loop.

The ApprovalBundle may send multiple revision attachments. The contract is:

1. The plugin endpoint accepts raw `references` from the UI.
2. It passes them through the generic action brief contract as `operator_references`.
3. Generic action execution resolves those references through the shared attachment pipeline:
   - ensure reference identity,
   - enrich Drive references,
   - persist the references,
   - convert enriched image inputs into `reference_images` via `attachment_context.brief_fields(...)`,
   - tag them as `revision_reference=true`, `priority=operator_revision`, `source=operator_attachment`.
4. The action brief passed to `postcraft.render` must preserve `source_image_data_b64` from the original artifact as the continuity anchor.
5. Postcraft render owns ordering, role inference, contact-sheet/composite construction, revision-spec generation, and lineage persistence.

This keeps the fix generic: the core understands typed `operator_references`, not Postcraft-specific attachment semantics, while Postcraft still owns how those references influence the edit.

#### Frontend intent split — revision reference vs template

Inside `ApprovalBundle`, the operator must be able to do three different things without ambiguity:

1. **Use image as revision reference** — temporary, local to the current revision flow.
2. **Save uploaded image as template** — durable Brand Kit template candidate for future Postcraft work.
3. **Save generated artifact as template** — promote the current generated Postcraft image into a reusable template candidate.

These are not the same action and must not auto-convert into one another.

UI rule:
- uploaded/attached images shown under `Revision references` may expose `Save as template`
- the current generated Postcraft image may expose `Save as template`
- all new template saves default to `status = draft`
- revision references remain revision-only unless the operator explicitly saves them as a template

Frontend-only implementation rule:
- do not add a Postcraft-specific backend endpoint for template save
- reuse the existing Brand Kit template APIs and keep template saves inside the ApprovalBundle UX
- a template save should create/update `metadata_json.template_manifest.templates` for the active brand

Required Postcraft render behavior:

1. Detect `is_revision`.
2. Separate references into operator revision refs vs auto-injected logo/brand refs.
3. Build the edit source/contact sheet in revision priority order.
4. Generate and store `postcraft.revision_spec.v1` on the new artifact block.
5. Store `source_run_id`, `parent_run_id`, `source_render_spec`, `revision_feedback`, and `reference_assets` for lineage.

### Expected agency behavior

- “Make the CTA stronger” → update copy/layout emphasis only; keep image and brand stable.
- “Use this product photo” + one attached image → replace/insert product reference, preserve rest.
- “Use these three images” with no target → ask a clarifying question unless their roles can be inferred from filenames/context.
- “New direction / start over” → this is not a revision; create a fresh Postcraft render using the current brand/campaign context.
- “Try warmer, more premium” → style/tone adjustment while preserving copy, logo, and main layout unless requested otherwise.

### Tests future coding should cover

- Revision with no attachments uses prior image as source and preserves layout.
- Initial render with one attached image passes that image through vision intake and composite/reference assembly instead of letting optional Brand Kit refs displace it.
- Revision with one attached image passes that image as an operator revision reference.
- Revision with multiple attached images passes all of them or returns a clear prioritization blocker; none are silently ignored.
- Operator-provided refs are prioritized before optional Brand Kit visual refs on both initial render and revision flows.
- The generated provider prompt includes both JSON revision spec and source render spec.
- The new artifact block contains the revision spec and lineage back to the source artifact.
- ApprovalBundle `references` are honored by `POST /postcraft/runs/{run_id}/revise` through the generic `operator_references` action-brief contract.
- Prompt text never claims a reference sheet exists unless a composite/reference image is actually sent.

## Draft approval must render, not only approve

Postcraft is a two-stage workflow:

1. `postcraft.draft` creates a zero-cost `postcraft_draft` review artifact.
2. `postcraft.render` turns the approved draft into the generated image artifact.

A Postcraft draft is not complete when its `approval_status` becomes `approved`. Approval of a draft is a process trigger: it must execute the declared artifact action `render` from the draft block:

```json
{
  "allowed_actions": ["render", "revise", "dismiss"],
  "action_modules": {"render": "postcraft.render", "revise": "postcraft.draft"}
}
```

### Known failure mode

Bad behavior:

- Stream shows `Postcraft Draft` as `Approved`.
- No sticky generation notification appears.
- No new `postcraft.render` / image artifact is created.
- The operator sees the text draft only, even after clicking Approve.

Root cause:

- The UI or a stale client can call the generic `PATCH /runs/{id}/approve` path.
- Generic approve only flips `runs.approval_status = approved`.
- That bypasses the `POST /runs/{id}/actions/render` path and never runs `postcraft.render`.

### Required backend behavior

The backend must guard against stale clients:

- If `/runs/{id}/approve` is called for a persisted block with `type == "postcraft_draft"` and `action_modules.render`, route it to `execute_declared_run_action(..., action="render")` instead of only setting approval status.
- `_brief_from_action_artifact(..., action="render")` must include explicit render gate fields:

```json
{
  "action": "render",
  "artifact_action": "render",
  "render_approved": true
}
```

`postcraft.render` uses these fields to pass its approval gate. Without them, render may fall back to another draft instead of generating the image.

### Required UI behavior

The frontend must mirror the Storyboard approval UX:

- Clicking the primary button on a `postcraft_draft` should execute the declared `render` action when present.
- While render is running, keep the source draft visible as `Needs review` / pending.
- Show a sticky pipeline notification such as `Postcraft image generation in progress`.
- When render finishes, add/focus the new Postcraft image artifact as a separate Needs review item.
- Do not remove the source draft or show a final dead `Approved` state before a render artifact exists.

### Existing stale drafts

Older drafts may already be persisted as `approval_status = approved` without a rendered image. If the block is still a `postcraft_draft` with `action_modules.render`, Stream should treat it as actionable/pending so the operator can trigger render after the fix.

## Channel publishing handoff

Postcraft owns generating a reviewable post image artifact. It does **not** own channel posting.

After `postcraft.render` succeeds, the resulting `image_asset` may expose publish actions, but those actions must point to installed channel-owned publish modules. For Facebook, the canonical action module is Meta's approval-gated publish capability:

```json
{
  "allowed_actions": ["approve", "revise", "dismiss", "publish_facebook"],
  "action_modules": {
    "revise": "postcraft.render",
    "publish_facebook": "marketing.channel.meta.posts.publish"
  }
}
```

Do not use pseudo-module IDs such as `meta.pages.post`; the generic action executor resolves only installed capability IDs. Postcraft should hand off generic artifact fields only:

- image bytes or Drive image reference (`image_data_b64`, `_image_data_b64`, `drive_file_id`, `drive_file_mime`)
- human-facing copy (`headline`, `subheadline`, `body_copy`, `cta_text`, or `message`)
- artifact metadata needed for audit (`source_run_id`, `brand_name`, dimensions, provider/model)

Meta, LinkedIn, Twitter/X, Instagram, and future channel plugins own credentials, API endpoints, platform-specific validation, live mutations, and result artifacts.
