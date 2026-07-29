# Agency-Scale Brand Kit Template Architecture

## Goal

Support 100s of brands and 1000s of simultaneous creative executions without requiring a human to choose a template for every render.

## Core Principle

Templates are **Brand Kit resources classified as approved templates**.

A template is not created by:

- chat wording
- campaign context
- filename alone
- a generated artifact existing in Stream
- a generic base layout family

A template becomes available when a Brand Kit resource is indexed/classified as an approved template in the Brand Kit manifest.

## Hard Requirements

### Surface every failure

No selection/classification/render failure should be hidden, swallowed, logged-only, or silently converted into a fallback render.

Failure must be returned as structured data that can be displayed in the UI and grouped in bulk workflows:

```json
{
  "status": "blocked",
  "reason_code": "no_matching_template | missing_required_assets | low_confidence | manual_review_required | invalid_template_manifest",
  "message": "Human-readable explanation",
  "details": {},
  "suggested_resolution": "..."
}
```

Logging is not failure handling. If a Brand Kit template selector, validator, classifier, hook, or renderer cannot satisfy the approved-template contract, the user-facing run must show the exact blocker.

### No backwards compatibility target

Do not preserve old Postcraft-local template behavior, legacy `CreativeAsset` behavior, `brand.brand_json.postcraft_templates`, `brand_template_id`, `postcraft_template_id`, or Drive filename auto-promotion for compatibility.

Compatibility shims are allowed only as short-lived removal aids inside migrations or tests, not in runtime selection/render logic.

### Consolidate implementation layers

The architecture should avoid bloatware. Similar responsibilities should be collapsed into a small number of clear layers:

```text
Brand Kit Manifest Service
  owns template schema, classification, approval metadata, selection policy

Template Selector
  pure deterministic selector over approved manifest templates + request context

Postcraft Runtime Adapter
  resolves template_id/auto_select_template once, injects selected template into render spec, blocks on failures

Admin Brand Kit UI
  edits resource classification and routing metadata only
```

Do not spread template lifecycle across unrelated hooks, Postcraft-local APIs, Drive validators, chat parsing, Stream artifacts, and brand JSON. If two layers classify, select, validate, or apply templates, consolidate them.

## Ownership Boundary

```text
Brand Kit = canonical brand-specific resource manifest
Postcraft = social creative production capability that consumes Brand Kit templates
Content brief = copy, offer/message, channel/format, custom visual instructions
```

Google Drive, Dropbox, SharePoint, or local uploads may hold the actual files. The app should index/classify them in Brand Kit metadata, not duplicate the agency's whole library and not use the abandoned CreativeAsset path.

## Brand Kit Contents

Each brand context should include:

- logos / marks
- fonts or typography rules
- color palette
- approved visual assets
- approved design templates
- visual references
- brand aesthetic rules
- do/don't constraints

## Brand Kit Template Manifest

The approved template list should live in the approved Brand Kit document metadata, e.g. `WorkspaceDocument(doc_type="campaign_brand_kit").metadata_json.template_manifest`.

Template record shape:

```json
{
  "id": "bk_tpl_123",
  "brand_id": "brand_123",
  "source": {
    "provider": "google_drive",
    "drive_file_id": "...",
    "web_view_link": "..."
  },
  "name": "Product Promo Square v3",
  "status": "approved",
  "renderer": "postcraft",
  "format": "square_feed",
  "content_type": "promo | testimonial | educational | announcement | brand_story | offer",
  "objective_fit": ["awareness", "lead_gen", "conversion", "retention"],
  "tone": ["emotional", "premium", "urgent", "informative"],
  "copy_density": "low | medium | high",
  "required_slots": ["headline", "logo", "hero_image"],
  "optional_slots": ["cta", "supporting_image"],
  "forbidden_slots": ["price"],
  "aesthetic_notes": "...",
  "negative_rules": ["..."],
  "priority": 0,
  "performance_score": null,
  "created_at": "...",
  "updated_at": "..."
}
```

## Template Selection Policy

Humans classify/approve templates once during Brand Kit setup or review auto-classification. Runtime selection should be automatic.

For each creative request, Postcraft receives or derives:

```json
{
  "brand_id": "brand_123",
  "channel": "facebook",
  "format": "square_feed",
  "content_type": "promo",
  "objective": "lead_gen",
  "tone": "urgent",
  "copy_density": "medium",
  "assets_available": ["logo", "hero_image", "product_image"],
  "copy": {
    "headline": "...",
    "body": "...",
    "cta": "..."
  }
}
```

The system scores approved Brand Kit templates:

```text
score =
  format match
+ content type match
+ objective fit
+ tone fit
+ copy density fit
+ required asset availability
+ brand priority
+ historical performance
- missing slot penalties
- forbidden slot conflicts
```

Highest valid template wins.

## Bulk Production Flow

```text
Brand Kit setup:
  connect/import asset folder
  index Brand Kit resources
  classify approved templates in Brand Kit manifest
  validate slot metadata
  approve template policy

Bulk production:
  receive many creative briefs
  auto-select Brand Kit templates
  render drafts
  group exceptions
  human reviews exceptions only
```

Example output:

```text
100 requested creatives
92 auto-routed and rendered
6 blocked by missing required assets
2 blocked by no matching approved Brand Kit template
```

## Human Role

Humans should not select a template for every creative.

Humans should:

- approve/classify templates during Brand Kit setup
- set brand-level template policy
- review low-confidence routing
- resolve missing assets
- approve exceptions

## Runtime Rule

Postcraft should consume one of:

```json
{
  "template_id": "bk_tpl_123"
}
```

or, if no explicit template is passed:

```json
{
  "auto_select_template": true,
  "selection_context": { ... }
}
```

Postcraft should not infer a real template from arbitrary `Template:` text.

## Exception Handling

Stop only when:

- no approved Brand Kit template fits
- required slots/assets are missing
- selection confidence is below threshold
- client/brand requires manual template approval
- brief conflicts with template policy

Otherwise proceed automatically and record:

```json
{
  "selected_template_id": "bk_tpl_123",
  "selection_confidence": 0.92,
  "selection_reason": [
    "format match",
    "promo content type",
    "hero image available",
    "medium copy density fit"
  ]
}
```

## Current-System Direction

The current architecture should be evaluated for removal/refactor around this boundary:

```text
Drive/reference asset != template
Base layout family != template
Prompt label != template
Abandoned CreativeAsset row != template
Brand Kit approved classified resource == template
```

Implementation should gut any logic that:

- auto-promotes Drive files to templates by filename alone
- counts visual references as saved templates
- stores Postcraft templates in `brand.brand_json.postcraft_templates`
- stores templates through the abandoned `CreativeAsset` model/table
- requires per-render human template choice
- treats `template_type` as both base family and user template
- spreads template lifecycle across unrelated surfaces instead of Brand Kit classification
- catches template-selection failures and continues with a fallback render
- preserves legacy runtime template paths for backwards compatibility
- duplicates classification/selection/application logic across hooks, render modules, routers, and UI-specific helpers

## Gut Completed

The old template architecture has been intentionally removed/gutted so the next implementation can start from the Brand Kit manifest boundary.

Removed or disabled:

- `api/models/creative_asset.py` ORM export and model path.
- New migration added to drop abandoned `creative_assets`: `api/migrations/versions/055_drop_creative_assets.py`.
- Postcraft-owned template CRUD routes under `/postcraft/brands/{brand_id}/templates`.
- Frontend Postcraft template API methods and `PostcraftBrandTemplate` type.
- Admin Brand Kit `PostcraftTemplatesManager` manual template CRUD UI.
- Stream `Save as brand template` behavior that wrote Postcraft-local templates.
- Drive validation names that implied templates:
  - `template_files` → `creative_reference_files`
  - `template_count` → `creative_reference_count`
- CMO/Postcraft logic that converted Drive filename matches into approved templates.
- Postcraft hook enrichment that injected `brand_kit.postcraft_templates`.
- Chat `Template:` → `template_type` mapping. `Template:` now maps to `creative_direction`; `template_type` remains a fallback base family.
- Active Postcraft draft/render `brand_template_id` / `postcraft_template_id` handling.

Kept/reframed:

- Google Drive remains the file storage/source.
- Brand Kit remains the brand-specific resource authority.
- Postcraft remains the social creative renderer.
- `plugins/postcraft/templates/*.json` remain temporarily as fallback base families, not brand templates.
- `template_type` remains only as fallback base family until replaced by clearer `base_family` naming.

## Expected Broken State After Gut

The old workflow should fail anywhere it expects Postcraft-local saved templates.

Known failing tests:

```text
api/tests/test_postcraft_brand_templates.py
```

Expected failures:

- `_postcraft_templates_from_validation` no longer exists.
- Drive `template_files` no longer auto-create template candidates.
- `brand.brand_json.postcraft_templates` is no longer merged into runtime context.
- `_postcraft_templates_for_brand` no longer injects template lists.

Passing checks after gut:

```text
PYTHONPYCACHEPREFIX=/tmp/bos-pycache python -m py_compile ...
cd web && npm run build
```

## Next Architecture To Build

### 1. Brand Kit manifest schema

Add a canonical template manifest to the approved Brand Kit document metadata:

```json
{
  "template_manifest": {
    "version": "brand_kit_templates.v1",
    "templates": [],
    "selection_policy": {
      "default_renderer": "postcraft",
      "confidence_threshold": 0.75,
      "manual_review_required": false
    }
  }
}
```

### 2. Brand Kit classification API

Needed endpoints should operate on Brand Kit metadata, not Postcraft-local storage:

```text
GET   /brands/{brand_id}/brand-kit/resources
PATCH /brands/{brand_id}/brand-kit/resources/classify
PATCH /brands/{brand_id}/brand-kit/templates/bulk
PATCH /brands/{brand_id}/brand-kit/templates/{template_id}
```

The API should support bulk operations:

- classify selected Drive files as template/reference/logo/asset
- approve templates
- set routing metadata
- deactivate templates
- bulk edit format/content_type/tone/copy_density/slots

### 3. Template selector

Add deterministic backend selection before Postcraft render. The selector should be pure/business-logic code, not coupled to chat parsing, Drive validation, or rendering internals:

```text
select_brand_kit_template(brand_id, selection_context) -> selected_template | exception
```

Selection context:

```json
{
  "renderer": "postcraft",
  "format": "square_feed",
  "content_type": "promo",
  "objective": "lead_gen",
  "tone": "urgent",
  "copy_density": "medium",
  "assets_available": ["logo", "hero_image"]
}
```

Output:

```json
{
  "template_id": "bk_tpl_123",
  "confidence": 0.92,
  "reason": ["format match", "content type match", "required assets available"]
}
```

### 4. Postcraft runtime contract

Postcraft should accept, resolve, and validate the template contract in one place before provider-costly rendering begins:

```json
{
  "template_id": "bk_tpl_123",
  "auto_select_template": true,
  "selection_context": {},
  "base_family": "promo",
  "creative_direction": "..."
}
```

Rules:

- `template_id` means approved Brand Kit template.
- `auto_select_template=true` invokes Brand Kit selector.
- If template resolution fails, rendering returns a visible structured blocker; it must not silently fall back.
- `base_family` is fallback only.
- `creative_direction` is a prompt/concept label only.
- arbitrary `Template:` text never becomes template identity.

### 5. Frontend rebuild

Replace removed UI with Brand Kit resource classification:

```text
Admin → Brands → Brand Kit
  Resource inventory
  Bulk classify
  Approved templates
  Template routing metadata
  Selection policy
```

No per-render human template picker required. Humans classify and approve templates once; runtime selects automatically.

### 6. Test replacements

Delete/replace old tests in `api/tests/test_postcraft_brand_templates.py`.

New tests should assert:

- Drive filename matches become `creative_reference_files`, not templates.
- Brand Kit metadata `template_manifest.templates[status=approved]` is the only template source.
- Chat `Template:` becomes `creative_direction`, not `template_type` or `template_id`.
- Postcraft blocks render or falls back when no Brand Kit manifest template is available.
- Template selector chooses highest-scoring approved Brand Kit template.
- Low-confidence/no-match cases return grouped exceptions for review.
