# Image Generation Pipeline Analysis - Artifact ID: 7ca86fc4-ba40-4ae1-806f-7868d3bfefa0

## Problem Statement

Image generated after approved copy does not translate into a useful artifact. The purpose of having copy generated and pre-approved template layouts is to reduce the cycle of updates, but this is broken.

## Root Cause Analysis

### 1. Missing Imprint Plugin

**Expected:** `marketing.creative.imprint.generate` (imprint) should be the main image generator

**Actual:** This plugin does not exist in the filesystem

```bash
# Expected to find:
/home/ubu/bos/plugins/marketing/creative/imprint/generate/module.py

# But this directory does not exist:
find /home/ubu/bos/plugins -name "*imprint*"  # Returns nothing
```

### 2. Broken References in creative.post.image

**File:** `/home/ubu/bos/plugins/creative-factory/capabilities/creative/post/image/SKILL.md`

```markdown
image_generator_module: marketing.creative.imprint.generate
```

**File:** `/home/ubu/bos/plugins/creative-factory/capabilities/creative/post/image/module.py`

```python
# References non-existent module
image_generator_module: marketing.creative.imprint.generate
```

### 3. Incorrect Fallback Behavior

**In runs.py line 597-615:**

```python
_IMAGE_GEN_MODULE_ID = "marketing.creative.imprint.generate"

# When this module doesn't exist, the system falls back to media.image.generate
# But this is a generic image generator, not the specialized imprint generator
```

### 4. Wrong Modules Being Used

**Currently active image modules:**

1. **`media.image.generate`** - Generic image generation (OpenAI, Gemini, ByteDance)
   - Path: `/home/ubu/bos/plugins/media-image/capabilities/media/image/generate/module.py`
   - This is being used as fallback but shouldn't be the primary

2. **`creative.post.image`** - Image artifact creator
   - Path: `/home/ubu/bos/plugins/creative-factory/capabilities/creative/post/image/module.py`
   - References non-existent `marketing.creative.imprint.generate`

3. **`creative.primitive.generate`** - Primitive router
   - Path: `/home/ubu/bos/plugins/creative-factory/capabilities/creative/primitive/generate/module.py`
   - Routes to other modules

## The Broken Workflow

### Expected Flow (What Should Happen)

```
1. User approves copy in creative.post.image (Phase 1)
   ↓
2. System calls marketing.creative.imprint.generate (imprint)
   ↓
3. Imprint generates template-based image using approved copy
   ↓
4. creative.post.image receives image and creates artifact
   ↓
5. User reviews and publishes artifact
```

### Actual Flow (What's Happening)

```
1. User approves copy in creative.post.image (Phase 1)
   ↓
2. System tries to call marketing.creative.imprint.generate
   ↓
3. MODULE NOT FOUND - falls back to media.image.generate
   ↓
4. Generic image generator creates image WITHOUT using approved copy
   ↓
5. creative.post.image receives generic image
   ↓
6. User gets useless artifact that doesn't reflect approved copy
```

## Why Approved Copy Is Not Being Used

The `media.image.generate` module does NOT:

1. Read approved copy from `creative_json` in brief
2. Use approved copy in image prompt construction
3. Apply template layouts to approved copy
4. Generate image that reflects approved copy

Instead, it generates generic images based on:
- `image_prompt` from brief (if provided)
- Brand constraints (generic)
- Product/audience context (generic)

## The Missing Imprint Plugin

**What imprint should do:**

1. **Read approved copy** from brief:
   ```python
   creative_json = brief.get("creative_json")
   headline = creative_json.get("headline")
   subheadline = creative_json.get("subheadline")
   body = creative_json.get("body")
   cta = creative_json.get("cta")
   ```

2. **Select template layout** based on creative type:
   - Product shot template
   - Hero banner template
   - Social card template
   - Carousel template

3. **Compose image prompt** using approved copy:
   ```python
   prompt = f"""
   Create a {template_type} image with:
   - Headline: {headline}
   - Subheadline: {subheadline}
   - Body: {body}
   - CTA: {cta}
   - Brand style: {brand_tone}
   """
   ```

4. **Generate image** using provider:
   - Call media.image.generate with composed prompt
   - Or use specialized imprint rendering

5. **Return image** with copy metadata:
   ```python
   return {
       "image_data_b64": generated_image,
       "creative_json": creative_json,
       "template_used": template_type
   }
   ```

## Deprecation Warnings Needed

The following modules should be marked as deprecated if they're doing image generation:

1. **`media.image.generate`** - Should be marked as:
   - "Use `marketing.creative.imprint.generate` for template-based image generation"
   - "This module is for raw image generation only"

2. **`creative.primitive.generate`** - Should be marked as:
   - "Use `marketing.creative.imprint.generate` for image primitives"
   - "This module is for routing only"

## Immediate Fix Required

### Option 1: Create the Missing Imprint Plugin

Create `/home/ubu/bos/plugins/marketing/creative/imprint/generate/` with:

```
plugins/marketing/creative/imprint/generate/
├── channel.json
├── module.py
└── SKILL.md
```

**channel.json:**
```json
{
  "plugin_id": "marketing.creative",
  "name": "Creative Marketing",
  "capabilities_root": "capabilities/",
  "implements": ["marketing.creative.imprint.generate"],
  "output_contracts": ["image_asset"],
  "default_backend": {
    "provider": "bytedance",
    "model_id": "seedream-4-5-251128"
  }
}
```

**module.py:** Should implement the imprint logic described above

### Option 2: Update creative.post.image to Use Existing Generator

**File:** `/home/ubu/bos/plugins/creative-factory/capabilities/creative/post/image/module.py`

Change:
```python
# OLD (broken):
image_generator_module: marketing.creative.imprint.generate

# NEW (working):
image_generator_module: media.image.generate
```

And update the module to properly pass approved copy to the generator.

### Option 3: Fix runs.py Fallback Logic

**File:** `/home/ubu/bos/api/routers/runs.py`

Lines 597-615 should be updated to be more explicit:

```python
# OLD:
_IMAGE_GEN_MODULE_ID = "marketing.creative.imprint.generate"

# NEW:
_IMAGE_GEN_MODULE_ID = "media.image.generate"  # Use existing working module
_IMPRINT_MODULE_ID = "marketing.creative.imprint.generate"  # Mark as deprecated/missing
```

## Recommended Action Plan

1. **Immediate (Day 1):**
   - Update `creative.post.image/module.py` to use `media.image.generate`
   - Add deprecation warning about missing imprint plugin
   - Update documentation to reflect current state

2. **Short-term (Week 1):**
   - Create the missing `marketing.creative.imprint.generate` plugin
   - Implement proper template-based image generation
   - Test approved copy → image generation flow

3. **Long-term (Month 1):**
   - Add comprehensive imprint template library
   - Implement A/B testing for templates
   - Add template performance tracking

## Verification Steps

1. Check if imprint plugin exists:
   ```bash
   ls -la /home/ubu/bos/plugins/marketing/creative/imprint/
   ```

2. Check current image generation references:
   ```bash
   grep -r "marketing.creative.imprint.generate" /home/ubu/bos/plugins/
   ```

3. Test artifact creation with approved copy:
   - Create creative.post.image with approved copy
   - Verify image reflects approved copy
   - Check if template layout was applied

## Files Requiring Updates

1. `/home/ubu/bos/plugins/creative-factory/capabilities/creative/post/image/SKILL.md`
   - Update to use `media.image.generate`
   - Add deprecation notice

2. `/home/ubu/bos/plugins/creative-factory/capabilities/creative/post/image/module.py`
   - Update `image_generator_module` reference
   - Add proper copy passing logic

3. `/home/ubu/bos/api/routers/runs.py`
   - Update `_IMAGE_GEN_MODULE_ID` to use working module
   - Add better error handling for missing modules

4. `/home/ubu/bos/plugins/marketing/creative/imprint/generate/` (CREATE)
   - Create missing imprint plugin
   - Implement template-based generation

## Summary

**Root Cause:** The `marketing.creative.imprint.generate` plugin is referenced but doesn't exist, causing the system to fall back to generic `media.image.generate` which doesn't use approved copy.

**Impact:** Approved copy is not being used in image generation, breaking the template-based workflow and creating useless artifacts.

**Fix:** Either create the missing imprint plugin or update references to use the existing working generator with proper copy passing.
