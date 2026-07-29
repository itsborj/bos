# Imprint Pipeline Audit — Recurring Image Generation Failure

**Date:** 2026-06-22
**Artifact ID:** 7ca86fc4-ba40-4ae1-806f-7868d3bfefa0
**Status:** Root cause identified, fix pending

---

## Problem Statement

After the CMO composes approved copy via `imprint.draft` and the operator clicks "Approve", the generated image does not translate into a useful artifact. Instead of an AI-generated image matching the CMO's `image_prompt`, the output is a plain brand-colored rectangle with copy composited on top. The purpose of having copy generated and pre-approved templated layouts is to reduce the cycle of updates — this pipeline fails to deliver that.

---

## Intended Pipeline

```
Operator: "Create an image with headline 'Summer Sale', use this photo as inspiration" + [image.jpg]
  │
  ▼
attachment_context.brief_fields()
  → operator_reference_context, reference_images, image_spec, creative_context
  │
  ▼
CMO chat → RUN: imprint.draft
  creative_json: {"headline":"Summer Sale","subheadline":"Limited time offer","body":"","cta":"Shop Now"}
  image_prompt: "bright summer scene with beach vibes, warm golden light..."
  │
  ▼
imprint.draft module → copy-only artifact (imprint_draft block)
  → Operator reviews copy, clicks "Approve"
  │
  ▼
execute_declared_run_action("approve")
  → _brief_from_action_artifact() builds brief from block
  → _execute_module("marketing.creative.imprint.generate", brief)
  │
  ▼
ImprintGenerateModule.execute_tool_result()
  → Should: generate AI image from image_prompt, composite approved copy + logo
  → Actual: produces plain colored rectangle
```

---

## Root Causes

### 1. PRIMARY: `image_prompt` is discarded — AI image generation never fires

**File:** `api/capabilities/creative/imprint/generate/module.py`
**Lines:** ~632-650

The `_generate_image()` function (which calls `media.image.generate` to produce an actual AI image) is gated behind `prompt_integrated_ai`, which requires `integrate_copy_in_prompt=true`. This flag defaults to `false` and **no code path sets it to `true`** during normal approval flow.

```python
# Line ~632
integrate_copy_in_prompt = str(brief.get("integrate_copy_in_prompt", "false")).lower() in {"1", "true", "yes"}

# Line ~650
prompt_integrated_ai = (
    integrate_copy_in_prompt          # ← defaults to False
    and bool(headline or subheadline or body or cta_text)
    and str(brief.get("disable_prompt_integrated_generation") or "").lower() not in {"1", "true", "yes"}
    and (not has_operator_visual_source or str(brief.get("force_prompt_integrated_generation") or "").lower() in {"1", "true", "yes"})
)
```

The CMO's carefully composed `image_prompt` (e.g., "bright summer scene with beach vibes...") is stored in the block but **never sent to any AI image model**.

### 2. Reference images lack role classification

**File:** `api/attachment_context.py` — `brief_fields()`
**Lines:** ~495-510

`brief_fields()` produces `reference_images` entries with `{id, title, vision_b64, mime_type, drive_file_id}` but **no `role` field**.

```python
reference_images.append({
    "id": _get(ref, "id"),
    "title": _get(ref, "title") or _get(ref, "drive_file_name"),
    "drive_file_id": _get(ref, "drive_file_id"),
    "mime_type": mime,
    "vision_b64": vision_b64,
    # ❌ No "role" field
})
```

**File:** `api/capabilities/creative/imprint/generate/module.py` — `_find_reference_by_role()`
**Lines:** ~200-210

The module looks for references with role `"insert"` or `"inspiration"`:

```python
def _reference_role(ref: dict | None) -> str:
    text = " ".join(str(ref.get(k) or "") for k in ("role", "image_role", "attachment_role", "usage", "notes", "title")).lower()
    if any(t in text for t in ("inspiration", "inspire", "mood", "style")):
        return "inspiration"
    if any(t in text for t in ("logo", "wordmark", "brandmark")):
        return "logo"
    return "insert"
```

Since `role` is never set, `_reference_role()` falls back to checking the title for keywords. If the title doesn't contain "inspiration" or "logo", it returns `"insert"` — but this is unreliable and depends on the operator's file naming. More importantly, the resolution chain calls `_find_reference_by_role(refs, "insert")` and `_find_reference_by_role(refs, "inspiration")` — both return `None` when roles aren't explicitly set, because the fallback `"insert"` only works if the caller asks for `"insert"`.

**Result:** The operator's attached image is invisible to the visual source resolution chain. Steps 4 and 6 in the chain both skip.

### 3. Template resources are a hard gate, not optional enhancement

**File:** `api/capabilities/creative/imprint/generate/module.py`
**Lines:** ~670-675

```python
if not selected_template_meta:
    return self._fail(
        start,
        "missing_template_resource",
        "Imprint checked Drive but could not select an approved Brand Template resource. "
        "Configure a template image in the brand template/resources folder before rendering the final PNG.",
    )
```

Even when the CMO provides a perfect `image_prompt` and the operator attaches reference images, if no Drive template folder is configured with approved Brand Template resources, the **entire pipeline fails**. Template resources should be optional inspiration/enhancement, not a blocker.

### 4. `_select_drive_template_resource` returns `template_bytes=None` by default

**File:** `api/capabilities/creative/imprint/generate/module.py`
**Lines:** ~175-180

```python
# Default: validate/select the approved template but do not download
if str(brief.get("use_drive_template_as_base") or "").lower() in {"1", "true", "yes"}:
    data = dc.download_file(selected["id"])
    return data, mime, selected, details
return None, mime, selected, details  # ← bytes=None
```

Template metadata is found and validated, but the actual image bytes are **never downloaded** unless `use_drive_template_as_base=true` is explicitly set. This means `template_bytes` is always `None` on first approval, causing steps 5 and 8 in the resolution chain to skip.

---

## Visual Source Resolution Chain (annotated trace)

This is the exact decision tree in `ImprintGenerateModule.execute_tool_result()` for a normal first approval with `image_prompt` present and reference images attached:

| Step | Check | Value on first approval | Outcome |
|------|-------|------------------------|---------|
| 1 | `prompt_integrated_ai` | `integrate_copy_in_prompt=false` → **False** | **SKIP** — `_generate_image()` never called |
| 2 | Operator-attached Drive image | `drive_file_id` not in brief | **SKIP** |
| 3 | `source_image_b64` | only set on revision with inline image | **SKIP** |
| 4 | `insertion_ref` | `_find_reference_by_role(..., "insert")` → **None** (no role set) | **SKIP** |
| 5 | `template_bytes` + `use_drive_template_as_base` | `template_bytes=None`, flag=false | **SKIP** |
| 6 | `inspiration_ref` | `_find_reference_by_role(..., "inspiration")` → **None** (no role set) | **SKIP** |
| 7 | `allow_ai_base` | default `false` | **SKIP** |
| 8 | `template_bytes` → `_make_inspiration_background()` | `template_bytes=None` | **SKIP** |
| 9 | `selected_template_meta` exists | template metadata found in Drive | **HIT** → `_make_brand_background()` — plain colored rectangle |

---

## Contributing Issues

### A. `_brief_from_action_artifact` strips underscore-prefixed keys

**File:** `api/routers/runs.py`
**Lines:** ~2011-2016

```python
brief = {
    k: v for k, v in (block or {}).items()
    if k not in {"allowed_actions", "action_modules"} and not k.startswith("_")
}
```

This removes `_channel_credentials` — which `ImprintGenerateModule` needs for:
- Drive access (to download templates, upload results)
- Image provider API keys (to call `_generate_image()`)

The module then can't call `_generate_image()` even if the gate were opened.

### B. No campaign linkage

**File:** `api/routers/runs.py` — `_brief_from_action_artifact()`

`campaign_id` lives on the Run row, not the artifact block. `_brief_from_action_artifact` doesn't include it. The generated image artifact has no campaign scope, breaking campaign-level tracking and brand kit context.

### C. `image_prompt` survives but is unused

The `image_prompt` field is correctly stored in the `imprint_draft` block and correctly copied through `_brief_from_action_artifact`. It reaches `ImprintGenerateModule.execute_tool_result()` intact. The problem is that the module's resolution chain **never reads it** as a visual source — it's only used if `prompt_integrated_ai` is true, which it never is.

---

## Plan of Execution

### Fix 1: Make `image_prompt` the primary visual source
**File:** `api/capabilities/creative/imprint/generate/module.py`

When `image_prompt` is present and no operator visual source (attached image, insertion ref) exists, call `_generate_image()` as the **primary** path — not a gated opt-in behind `integrate_copy_in_prompt`. The `integrate_copy_in_prompt` flag should only control whether copy text is embedded in the AI prompt vs composited post-generation.

### Fix 2: Add role classification to reference images
**File:** `api/attachment_context.py` — `brief_fields()`

Add a `role` field to `reference_images` entries. Default to `"inspiration"` when the operator's message indicates reference/inspiration intent, `"insert"` when they indicate replacement/use intent. Alternatively, make `ImprintGenerateModule` treat all `reference_images` as usable for both insertion and inspiration without requiring explicit role matching.

### Fix 3: Make template resources optional
**File:** `api/capabilities/creative/imprint/generate/module.py`

Remove the hard `missing_template_resource` gate. Template resources should be used when available (for layout/palette inspiration), but `image_prompt` + reference images should be sufficient to produce a useful artifact.

### Fix 4: Fix `_brief_from_action_artifact`
**File:** `api/routers/runs.py`

Preserve `_channel_credentials` and other pipeline keys that downstream modules need. The underscore-prefix filter is too aggressive.

### Fix 5: Add campaign linkage
**File:** `api/routers/runs.py` — `_brief_from_action_artifact()`

Pass `campaign_id` through so the generated image artifact is scoped to the campaign.

### Fix 6: Deprecate non-Imprint creative plugins
**Files:** `api/capabilities/creative/post/image/module.py`, `api/plugins/creative-factory/capabilities/creative/*/module.py`

Mark `creative.post.image`, `creative-factory/capabilities/creative/post/image`, `creative-factory/capabilities/creative/primitive/generate`, and `creative-factory/capabilities/creative/blueprint/assemble` as deprecated. Imprint is the canonical image pipeline.
