# Video Production Workflow Analysis - Previs/Storyboard Missing

## Problem Statement

Video production workflow with previs/storyboarding that starts with JSON, then image storyboard before video production is **not implemented**. The imprint workflow works for images but stops at image generation for video production.

## Current Architecture Analysis

### What Exists (Working Components)

**1. Creative Factory Plugin Structure:**
```
plugins/creative-factory/
├── capabilities/creative/
│   ├── concept/generate/        ✅ EXISTS - Strategic concept generation
│   ├── pack/generate/          ✅ EXISTS - Creative pack generation
│   ├── primitive/generate/      ✅ EXISTS - Primitive router (images/videos)
│   ├── blueprint/assemble/      ✅ EXISTS - Blueprint assembly
│   ├── post/image/              ✅ EXISTS - Image artifact creation
│   ├── shortform/video/         ✅ EXISTS (DIR ONLY) - Shortform video production
│   └── primitive/generate/video/ ✅ EXISTS - Video primitive generation
└── CREATIVE_SUPPLY_CHAIN.md     ✅ EXISTS - Architecture documentation
```

**2. Image Workflow (WORKS for Images):**
```
User: "Make an image for Facebook post"
  ↓
CMO (Phase 1 - Copywriting):
  - Reads brand kit
  - Composes creative copy (headline, subheadline, body, CTA)
  - Presents JSON for approval
  - creative-campaigns.json = {
      "headline": "Transform Your Morning",
      "subheadline": "Start with Clarity",
      "body": "Our premium coffee helps you make better decisions.",
      "cta": "Shop Now"
    }
  ↓
Operator: Approves copy
  ↓
System (Phase 2 - Image Generation):
  - creative.post.image receives approved copy
  - Tries to call marketing.creative.imprint.generate (MISSING)
  - Falls back to media.image.generate (generic)
  - Generic image generated WITHOUT using approved copy
  - Image stored in Drive
  - Artifact created but doesn't reflect approved copy
```

**3. Video Workflow (BROKEN - Missing Components):**
```
User: "Create a video for our new product launch"
  ↓
CMO (Phase 1 - JSON Brief):
  - Reads brand kit
  - Composes creative JSON
  - Presents JSON for approval
  - creative-brief.json = {
      "hook": "Transform your morning routine",
      "visual_direction": "calm lifestyle, morning light",
      "product_focus": "new coffee bundle",
      "cta": "Shop Now"
    }
  ↓
Operator: Approves JSON brief
  ↓
System (Phase 2 - Storyboard Generation):
  - MISSING: creative.storyboard.generate capability
  - NO storyboard images generated
  - NO visual narrative created
  ↓
System (Phase 3 - Video Production):
  - MISSING: creative.shortform.video implementation
  - NO video plates generated
  - NO storyboard used
  - NO video created
```

## Missing Components

### 1. Storyboard/Previs Plugin

**Expected Location:**
```
plugins/creative-factory/capabilities/creative/storyboard/generate/
├── channel.json
├── module.py
└── SKILL.md
```

**Status:** DOES NOT EXIST

**What It Should Do:**
- Read approved creative JSON from brief
- Determine number of storyboard frames (typically 6-12)
- Generate sequential storyboard images showing narrative flow
- Each frame shows:
  - Scene composition (product + lifestyle)
  - Text overlay (hook, benefit, CTA)
  - Brand elements (logo, colors, typography)
- Return storyboard artifact for review

### 2. Shortform Video Implementation

**Expected Location:**
```
plugins/creative-factory/capabilities/creative/shortform/video/
├── channel.json
├── module.py
└── SKILL.md
```

**Status:** DIRECTORY EXISTS BUT NO MODULE FILES

**What It Should Do:**
- Accept JSON-based creative brief
- Coordinate storyboard generation
- Coordinate video primitive generation
- Coordinate blueprint assembly
- Coordinate video rendering
- Return video artifact

### 3. Video Primitive Generation

**Expected Location:**
```
plugins/creative-factory/capabilities/creative/primitive/generate/video/
├── channel.json
├── module.py
└── SKILL.md
```

**Status:** EXISTS BUT INCOMPLETE

**Current Implementation:**
```python
# From module.py:
modality = _MODALITY_MAP.get(primitive_type, "image")

# This treats ALL primitives as images!
# Video primitives would need different routing
```

**What It Should Do:**
- Detect video primitive type
- Route to video generation provider
- Generate video plates (background footage)
- Return video primitive asset

### 4. Template System

**Expected Location:**
```
plugins/creative-factory/capabilities/creative/templates/ (MISSING)
```

**Status:** DOES NOT EXIST

**What It Should Provide:**
- Template library with different layouts
- Product shot templates
- Hero banner templates
- Social card templates
- Carousel templates
- Template selection based on creative type

## Why Imprint Works for Images But Not Video

### Image Workflow (WORKS):

1. **Two-Phase Structure:**
   - Phase 1: Copywriting approval
   - Phase 2: Image generation
   - Both phases use same creative.post.image module

2. **Missing Imprint Plugin:**
   - Falls back to media.image.generate (generic)
   - Generic generator ignores approved copy
   - But still produces SOME image (just not template-based)

3. **Fallback Behavior:**
   - System tries to call marketing.creative.imprint.generate
   - Plugin doesn't exist
   - Falls back to media.image.generate
   - Generic image generated
   - creative.post.image receives and stores it

### Video Workflow (BROKEN):

1. **No Storyboard Generation:**
   - Phase 2 (storyboard) doesn't exist
   - No visual narrative created
   - No storyboard images for review

2. **No Shortform Implementation:**
   - Phase 3 (video production) doesn't exist
   - No video plates generated
   - No video composition

3. **No Template System:**
   - No template library to use
   - No blueprint assembly for video

4. **Broken Chain:**
   - JSON brief approval (Phase 1) - WORKS
   - Storyboard generation (Phase 2) - MISSING
   - Video production (Phase 3) - MISSING

## The Complete Video Production Workflow (What Should Exist)

### Expected Flow:

```
User: "Create a video for our new product launch"
  ↓
CMO (Phase 1 - JSON Brief):
  - Reads brand kit
  - Composes creative JSON:
    {
      "hook": "Transform your morning routine",
      "visual_direction": "calm lifestyle, morning light",
      "product_focus": "new coffee bundle",
      "cta": "Shop Now",
      "scenes": [
        {
          "duration": 3,
          "description": "Person waking up, making coffee",
          "visual_elements": ["coffee_machine", "morning_light"]
        },
        {
          "duration": 4,
          "description": "Person enjoying coffee, feeling clarity",
          "visual_elements": ["coffee_cup", "product_shot"]
        },
        {
          "duration": 3,
          "description": "Person working with renewed focus",
          "visual_elements": ["laptop", "product_bundle"]
        }
      ]
    }
  - Presents JSON for approval
  ↓
Operator: Approves JSON brief
  ↓
System (Phase 2 - Storyboard Generation):
  - creative.storyboard.generate receives approved JSON
  - Determines scene count from creative_json.scenes
  - Generates storyboard images:
    - Frame 1: Morning routine scene
    - Frame 2: Coffee enjoyment scene
    - Frame 3: Clarity at work scene
  - Each frame includes:
      - Product shot
      - Lifestyle footage
      - Brand elements
      - Text overlays
  - Returns storyboard artifact with all frames
  ↓
Operator: Reviews storyboard
  - Approves or requests edits
  ↓
System (Phase 3 - Video Production):
  - creative.shortform.video receives:
    - Approved JSON brief
    - Storyboard artifact
  - Template selection
  - Generates video plates:
    - Background plates (AI-generated or stock)
    - Product cutouts (transparent PNGs)
    - Brand overlays (logo, frames)
  - Calls video generation provider (Runway/Kling)
  - Returns video primitive asset
  ↓
System (Phase 4 - Blueprint Assembly):
  - creative.blueprint.assemble receives:
    - Video primitive assets
    - Template selection
    - Fills template slots with assets
    - Creates CompositionSpec JSON
  - Validates all slots filled
  - Stores blueprint in DB
  ↓
System (Phase 5 - Render):
  - creative.render.video receives:
    - CompositionSpec
    - Resolves asset IDs to Drive URLs
    - Resolves brand slots to Brand Kit values
    - Translates to FFmpeg/Shotstack format
    - Executes render
    - Uploads video to Drive
  - Returns export package
  ↓
System (Phase 6 - Bundle Assembly):
  - Creative Director assembles:
    - Top export packages
    - Creates creative_bundle artifact
  - Surfaces in Stream for review
  ↓
Operator: Reviews video
- Approves for distribution
```

## Root Cause Summary

1. **Missing Storyboard Plugin**: No creative.storyboard.generate capability
2. **Incomplete Shortform Video**: Directory exists but no implementation
3. **No Template System**: No template library for video production
4. **Broken Video Chain**: Phase 2 and 3 completely missing

## Implementation Priority

### High Priority (Fix Broken Video Workflow):

1. **Create Storyboard Plugin**
   - Location: `plugins/creative-factory/capabilities/creative/storyboard/generate/`
   - Generate sequential storyboard images from approved JSON
   - Each frame shows narrative progression

2. **Implement Shortform Video**
   - Complete module.py implementation
   - Add SKILL.md documentation
   - Implement video production coordination

3. **Create Template System**
   - Location: `plugins/creative-factory/capabilities/creative/templates/`
   - Define video templates
   - Implement template selection logic

### Medium Priority (Complete Template System):

1. **Template Library**
   - Product shot templates
   - Hero banner templates
   - Social card templates
   - Carousel templates

2. **Template Management UI**
   - Template editor
   - Template preview
   - Template library browser

3. **Logo Integration**
   - Better logo upload workflow
   - Logo preview and selection

### Low Priority (Enhancement):

1. **Video Preview System**
   - Interactive storyboard preview
   - Real-time video rendering preview

2. **Batch Production**
   - Multiple variants from one template
   - Automated variant testing

## Files That Need Updates

### High Priority:

1. **Create:** `plugins/creative-factory/capabilities/creative/storyboard/generate/module.py`
2. **Create:** `plugins/creative-factory/capabilities/creative/storyboard/generate/SKILL.md`
3. **Complete:** `plugins/creative-factory/capabilities/creative/shortform/video/module.py`
4. **Create:** `plugins/creative-factory/capabilities/creative/shortform/video/SKILL.md`

### Medium Priority:

1. **Create:** Template library structure
2. **Update:** CREATIVE_SUPPLY_CHAIN.md with template system docs

### Low Priority:

1. **Update:** creative-factory plugin_notes_v2.md
2. **Add:** Template management UI components

## Related Documentation

- **CREATIVE_SUPPLY_CHAIN.md** - Full creative supply chain architecture
- **plugin_notes_v2.md** - Creative factory development notes
- **creative-factory-architecture-note.md** - Architecture status note

## Summary

**Root Cause:** Video production workflow with previs/storyboarding is completely missing. Only Phase 1 (JSON brief approval) works. Phases 2-3 (storyboard + video production) don't exist.

**Impact:** 
- No video production capability
- No storyboard generation
- No template-based video creation
- Approved JSON briefs can't be used for video

**Fix Required:** 
1. Create storyboard generation plugin
2. Implement shortform video module
3. Create template system
4. Connect phases into complete video production workflow

The creative factory plugin is actively developing this architecture, but video production is completely missing while image workflow works (with broken imprint fallback).
