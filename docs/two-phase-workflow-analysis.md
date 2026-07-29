# Two-Phase Workflow Analysis - Copywriting Approval + Image Generation

## Problem Understanding

The workflow involves:
1. **Phase 1**: Copywriting approval/editing with JSON files
2. **Phase 2**: Image generation approval + editing
3. **Backend process**: Logo and templates are part of the pipeline

## Current Architecture Analysis

### Phase 1: Copywriting (creative.post.image)

**Module:** `creative.post.image`
**Location:** `/home/ubu/bos/plugins/creative-factory/capabilities/creative/post/image/`

**Expected Behavior (from SKILL.md):**
- CMO composes brand-aware creative copy from active brand kit
- Presents JSON for operator approval
- Operator reviews and approves copy
- Phase 2 begins - image generation

**What Actually Happens:**
```python
# In module.py:
caption = str(
    brief.get("caption")
    or brief.get("post_text")
    or brief.get("copy")
    or brief.get("message")
    or brief.get("post_copy")
    or ""
).strip()

# The module just grabs caption from brief - NO TWO-PHASE LOGIC
```

**Missing:**
- No `phase` parameter handling
- No `creative_json` structured copy handling
- No separation between copy approval and image generation
- No proper two-phase workflow

### Phase 2: Image Generation

**Expected Behavior:**
- After copy approval, system should generate image using approved copy
- Image should reflect approved copy (headline, subheadline, body, CTA)
- Template-based generation should use approved copy

**What Actually Happens:**
```python
{
  "image_generator_module": "marketing.creative.imprint.generate",  # DOESN'T EXIST
  "requires_generated_image": True
}
```

**The Problem:**
1. `marketing.creative.imprint.generate` plugin doesn't exist
2. System falls back to `media.image.generate` (generic image generator)
3. Generic generator doesn't use approved copy from Phase 1
4. Image generated is generic, not template-based with approved copy

## Logo and Template Handling

### Where Logo Should Come From

**Expected Flow:**
1. Brand uploads logo to Google Drive
2. Brand kit extracts logo URL
3. Logo is injected into brief as `brand_logo_url` or `logo_url`
4. Image generation uses logo in template composition

**Current Reality:**
- Logo handling exists in `brand_json` but not specifically for image generation
- No dedicated logo overlay logic in image generation modules
- Templates are not template-based - they're generic prompts

### Template System Analysis

**Expected Template System:**
- Template library with different layouts (product shot, hero banner, social card)
- Template selection based on creative type
- Template fills slots with approved copy + brand assets
- Template composition happens at generation time

**Current Reality:**
- No template library exists
- No template selection logic
- No slot filling mechanism
- Images are generated from generic prompts only

## The Broken Two-Phase Workflow

### Expected Flow (What Should Happen)

```
User: "Make an image for Facebook post"
    ↓
CMO (Phase 1 - Copywriting):
  - Reads brand kit
  - Composes creative copy (headline, subheadline, body, CTA)
  - Presents JSON for approval
  - creative_json = {
      "headline": "Transform Your Morning",
      "subheadline": "Start with Clarity",
      "body": "Our premium coffee helps you make better decisions.",
      "cta": "Shop Now"
    }
    ↓
Operator: Approves copy
    ↓
System (Phase 2 - Image Generation):
  - Calls marketing.creative.imprint.generate (template-based)
  - Template: "hero_banner_template"
  - Fills template with approved copy
  - Adds brand logo from brand kit
  - Generates image
  - Returns image with copy metadata
    ↓
creative.post.image receives image:
  - Stores image in Drive
  - Creates artifact with copy + image
  - Presents for review and publish
```

### Actual Flow (What's Happening)

```
User: "Make an image for Facebook post"
    ↓
CMO (Phase 1 - Copywriting):
  - DOESN'T EXIST - No two-phase logic
  - Generates generic response
    ↓
Operator: (No copy approval step)
    ↓
System (Phase 2 - Image Generation):
  - Tries to call marketing.creative.imprint.generate
  - PLUGIN NOT FOUND
  - Falls back to media.image.generate (generic)
  - Generic prompt built from brand context
  - NO approved copy used
  - NO template used
  - NO brand logo added
  - Generic image generated
    ↓
creative.post.image receives image:
  - Stores generic image in Drive
  - Creates artifact with generic image
  - DOESN'T REFLECT APPROVED COPY
```

## Root Cause Summary

1. **Missing Imprint Plugin**: `marketing.creative.imprint.generate` doesn't exist
2. **No Two-Phase Logic**: `creative.post.image` doesn't implement phase separation
3. **No Template System**: No template library or slot filling
4. **No Logo Integration**: Brand logo not used in image generation
5. **No Copy Passing**: Approved copy not passed to image generator

## Files That Need Updates

### 1. Create Missing Imprint Plugin

**Create:** `/home/ubu/bos/plugins/marketing/creative/imprint/generate/`

**Structure:**
```
plugins/marketing/creative/imprint/generate/
├── channel.json
├── module.py
└── SKILL.md
```

**Purpose:** Template-based image generation using approved copy

### 2. Update creative.post.image Module

**File:** `/home/ubu/bos/plugins/creative-factory/capabilities/creative/post/image/module.py`

**Changes Needed:**
- Add `phase` parameter handling
- Add `creative_json` structured copy handling
- Implement two-phase workflow logic
- Pass approved copy to imprint module

### 3. Update creative.post.image SKILL.md

**File:** `/home/ubu/bos/plugins/creative-factory/capabilities/creative/post/image/SKILL.md`

**Changes Needed:**
- Document two-phase workflow
- Update triggers and behavior
- Add phase-specific instructions

### 4. Update runs.py Image Generation Logic

**File:** `/home/ubu/bos/api/routers/runs.py`

**Changes Needed:**
- Update `_IMAGE_GEN_MODULE_ID` to use existing module
- Add better error handling for missing modules
- Ensure approved copy is passed to image generator

## Implementation Priority

### High Priority (Fix Broken Workflow)

1. **Update creative.post.image to handle two phases**
   - Add phase detection logic
   - Separate copy approval from image generation
   - Pass approved copy to image generator

2. **Update runs.py fallback logic**
   - Use existing working module
   - Add proper error handling

3. **Add deprecation warnings**
   - Mark missing imprint module as deprecated
   - Document correct workflow

### Medium Priority (Complete Template System)

1. **Create imprint plugin**
   - Implement template-based generation
   - Add logo integration
   - Implement slot filling

2. **Create template library**
   - Define template types
   - Add slot definitions
   - Implement template selection logic

### Low Priority (Enhance Workflow)

1. **Add template management UI**
   - Allow operators to create/edit templates
   - Add template preview functionality

2. **Add logo management**
   - Better logo upload workflow
   - Logo preview and selection

## Verification Steps

1. **Test two-phase workflow:**
   - Create creative.post.image request
   - Verify copy approval step exists
   - Verify image generation uses approved copy

2. **Test template system:**
   - Create image with different template types
   - Verify templates are applied correctly
   - Verify logo is integrated

3. **Test artifact creation:**
   - Verify artifact contains both copy and image
   - Verify artifact reflects approved copy
   - Verify publish action works correctly

## Expected User Experience After Fix

**Phase 1 - Copywriting:**
```
User: "Make an image for Facebook post"

CMO: Here's the creative copy I've composed:

{
  "headline": "Transform Your Morning",
  "subheadline": "Start with Clarity",
  "body": "Our premium coffee helps you make better decisions.",
  "cta": "Shop Now"
}

[Approve Copy] [Edit Copy] [Regenerate Copy]
```

**Phase 2 - Image Generation:**
```
System: Generating image using approved copy and hero_banner_template...
[Adding brand logo...]
[Template filled with approved copy...]
[Image generated successfully!]

Preview: [Image with headline, subheadline, body, CTA]
[Approve & Publish] [Regenerate Image] [Edit Image]
```

**Artifact Created:**
```
Creative Post Artifact
- Copy: Transform Your Morning / Start with Clarity / Our premium coffee helps you make better decisions. / Shop Now
- Image: [Template-based image with approved copy and brand logo]
- Status: Ready for publish
```

## Summary

The workflow is broken because:
1. Two-phase approval system doesn't exist
2. Missing imprint plugin causes fallback to generic generator
3. Approved copy not used in image generation
4. No template system or logo integration

**Fix requires:**
1. Implement two-phase logic in creative.post.image
2. Create missing imprint plugin or update references
3. Add template system with logo integration
4. Ensure approved copy flows through to image generation
