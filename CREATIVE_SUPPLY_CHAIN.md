# Creative Supply Chain — Mini Project Brief

**Status:** Building — Phase A step 1 done (DB migrations live + validated); Google Drive next  
**Phase:** 6 sub-project, runs alongside 6.1 and 6.17  
**Parent brief:** `PROJECT_BRIEF.md` → "Shortform Video Production + Publishing Pipeline" + Key File Ownership table  
**Backlog tracking:** `BACKLOG.md` — add tasks under a new `### 6.18 — Creative Supply Chain` section when build begins

---

## What This Is

A channel-agnostic creative asset factory that produces brand-consistent video, image, and template primitives — then lets channel adapters package them for distribution.

The current BOS model dispatches channel plugins to generate their own creative from scratch. That is wrong at scale. The Meta plugin should not be writing copy and generating images. It should be receiving approved master assets and adapting them to Meta's specs. This mini project builds the manufacturing layer that sits between campaign strategy and channel distribution.

**The mental model:**

```
Raw materials → Manufacturing → Distribution

Raw materials:   Brand assets, AI-generated visuals, existing footage,
                 product images, copy variants, music, templates

Manufacturing:   Assemble → Validate → Stitch → Package

Distribution:    Meta / TikTok / YouTube / Google Ads / Email / Landing Pages
```

Right now BOS does distribution. This project builds manufacturing.

---

## BOS Role in This Pipeline

**BOS is a routing and orchestration system. It does not generate or render anything natively.**

Every piece of creative output — image plates, video, copy, rendered compositions — is produced by a third-party AI or render service. BOS's job is to:

1. Format the right request for the right provider at the right moment
2. Send it, receive the result, store it in Drive, record it in the DB
3. Route the result forward to the next stage
4. Surface approved outputs to the operator for review

The creative factory is, precisely, a **structured prompt pipeline** — it takes campaign intent and brand context and assembles well-formed JSON instructions for external services. Each stage is: build the request → send it → capture the result → move on.

**Who does the actual work:**

| Task | BOS does | Third party does |
|---|---|---|
| Image plate generation | Builds `image_prompt` from brand context + creative brief | OpenAI / Stability / Ideogram generates the image |
| Copy generation | Builds copy prompt from concept + brand voice | Claude / GPT writes the copy |
| Video plate generation | Builds video brief from creative direction | Runway / Kling / other video AI generates footage |
| Composition stitch | Builds CompositionSpec JSON (the layer-by-layer instruction) | Shotstack / Creatomate / FFmpeg composites the layers |
| Concept deck | Activates Huashu SKILL.md, builds design brief | Claude (with Huashu skill active) generates the HTML |
| Storage | Directs upload, writes DB record | Google Drive stores the binary |

**The stitch specifically:** BOS builds a CompositionSpec that says: "background = this AI image plate, layer 2 = this brand logo at safe-zone-bottom-right, layer 3 = this hook text in brand typography, layer 4 = this CTA pill." The render provider (FFmpeg, Shotstack, or Creatomate) receives that instruction and composites the layers into one final file. The AI-generated content and brand assets never merge inside an AI provider — they are separate files that BOS instructs the compositor to assemble.

**Admin implication:** Every provider the creative factory uses must be configured by the operator. See the Admin Provider Configuration section below.

---

## The Agency Model This Replicates

A real digital marketing agency has distinct roles with distinct authority. Klaroha should model them:

| Agency Role | BOS Component | Authority |
|---|---|---|
| Business Leader / CEO | BL — approves in Stream | Strategy gate, creative gate, spend gate |
| CMO / Account Director | CMO agent | Campaign brief, synthesis, delegation |
| Creative Director (concepts) | `creative.concept` capability | Insight mining, big idea, concept scoring |
| Creative Director (production) | Creative Factory orchestrator | Production brief, brand compliance gate |
| Graphic Designer | Image/video AI provider (OpenAI, Runway, etc.) — BOS sends the brief, AI produces the asset | Asset production |
| Motion Designer | Render provider (FFmpeg, Shotstack, Creatomate) — BOS sends the CompositionSpec, provider stitches the layers | Compositing and output |
| Channel Specialist | Channel plugins (Meta, Gmail, Google Ads, etc.) | Platform execution |
| Asset Library / DAM | Google Drive + `creative_assets` DB table | File storage and metadata |

**The key rule the agency operates by that BOS must adopt:**

The BL does not approve individual assets. The BL approves a **Creative Bundle** — a curated package of the best outputs from a production run. The Creative Director (production role) gates what reaches the BL. Individual primitives are internal manufacturing detail.

---

## Three-Layer Architecture

### Layer 1 — Creative Primitives (raw materials)

Reusable blocks that have no platform dependency.

| Primitive | Modality | Purpose |
|---|---|---|
| Video plate | video | Clean background footage — no text, no logos |
| Image plate | image | Still visual scene, lifestyle, product image |
| Product cutout | image | Transparent PNG/WebP product on alpha |
| Brand overlay | image | Logo, frame, gradient, CTA pill, badge |
| Motion card | video | Intro card, CTA card, end card |
| Audio bed | audio | Music, ambience, SFX |
| Voiceover | audio | Narration track |
| Thumbnail frame | image | Still for previews |
| Text block | text | Hook, benefit, CTA, headline, disclaimer |

A TikTok video, Meta ad, YouTube Short, PMax asset, or banner can all be built from the same primitives.

### Layer 2 — Creative Blueprint (channel-agnostic composition)

The master creative unit. Says which template to use, which assets fill which slots, which hook, which CTA, which brand rules apply. Does **not** know whether the final output is TikTok, Meta, YouTube, or display.

```
Blueprint 001: coffee plate + "A quiet moment for big decisions" + soft CTA
Blueprint 002: leather chair plate + "Talk it through before you decide" + consultation CTA
Blueprint 003: journal plate + "Clarity starts with one private conversation" + book CTA
```

A blueprint is the source creative. Everything downstream renders from it.

### Layer 3 — Render Target (channel adapter)

Platform-specific output wrapper. Handles: aspect ratio, pixel dimensions, duration limits, safe zones, file format, max file size, caption placement, CTA placement, thumbnail export, naming, metadata.

```
Blueprint 001 → Vertical short (9:16, 1080×1920)
             → Feed square (1:1, 1080×1080)
             → Email header (600px wide)
             → Thumbnail still
```

Adding TikTok later = adding a render adapter. The creative pipeline does not change.

---

## Object Model (8 Core Objects)

### 1. Brand Kit
Source: **generated from existing Campaign Brand Kit** (WorkspaceDocument, doc_type=campaign_brand_kit).  
Not a new database object — structured extraction from the existing prose document.  
Rendered as `BRAND.md` and injected before any creative production capability runs.

Fields extracted:
- `color_primary`, `color_secondary`, `color_accent`
- `typography_heading`, `typography_body`
- `logo_url` (Drive file ID or base64)
- `cta_style` (e.g., "soft", "direct", "urgent")
- `visual_mood` (e.g., "calm and premium", "bold and direct")
- `tone_adjectives` (e.g., "confident, warm, clear")
- `forbidden_elements` (e.g., "no stock-photo-face, no fake text in video")
- `safe_zone_prefs` (per render target: where logo/CTA must not overlap)

### 2. Asset Library
**Two-layer store:**
- DB: `creative_assets` table — metadata, brand/campaign scope, approval status, tags, Drive file ID
- Storage: Google Drive — the actual binary files

```sql
creative_assets
  asset_id          UUID PK
  brand_id          FK → brands
  campaign_id       FK → campaigns (nullable)
  drive_file_id     text        -- Google Drive file ID
  drive_folder_id   text
  asset_type        text        -- image_plate, video_plate, motion_card, brand_asset, template, export
  source            text        -- ai_generated, client_uploaded, stock, existing_footage
  modality          text        -- image, video, audio, template, text
  tags_json         JSONB       -- mood, product, audience, orientation, color_palette
  approval_status   text        -- draft, approved, rejected, archived
  usage_rights      text        -- unrestricted, campaign_only, single_use
  created_at, updated_at
```

### 3. Template Library
Structural rules for a creative type — not generated content, not brand values. A template defines the CompositionSpec skeleton: which layers exist, where they sit, what the safe zones are, what timing and transitions apply. Templates contain no actual assets and no brand-specific values. Those are injected at blueprint assembly time.

A vertical short template says: "background layer fills frame, hook text sits in the top-left safe zone starting at 0.5s, brand overlay sits in the bottom-right safe zone for the full duration." The same template works for every brand because brand assets and colors are slots, not fixed values.

Templates live in the creative-factory plugin. Operators do not edit them — they configure which providers supply the assets that fill them.

### 4. Creative Pack
The strategic production plan. Generated by the `creative.concept` capability from an approved campaign brief.  
Contains: hook bank, CTA bank, visual direction, template recommendations, primitive requirements.  
**Approved by BL before production begins.** The pack is the brief to the creative factory.

### 5. Creative Blueprint
The assembled source creative expressed as a `CompositionSpec` JSON. Not a metadata record with slot mappings — the JSON **is** the edit. It references approved primitives by `asset_id`, defines their positions, timings, transitions, and text values. Channel-agnostic. Render providers consume it directly.  
**Validated by the brand compliance gate before render.**

### 6. Render Target
Channel-specific output specification: aspect ratio, dimensions, duration, safe zones, format.  
Defined by render target capabilities in the creative factory plugin.  
Platform mapping lives here, not in the creative pipeline.

### 7. Export Package
The final distribution-ready bundle. Contains the rendered file (PNG, MP4, HTML), metadata, source blueprint ID, render target ID, and Drive file reference.  
This is what channel plugins receive and distribute.

### 8. CompositionSpec
The JSON document that fully describes a creative edit — tracks, clips, asset references, text values, timings, transitions, dimensions, and render target parameters. The blueprint IS this document. Inspired by Shotstack's track/clip/timeline model for video and Creatomate's modifications/elements model for static image. BOS defines its own schema (`spec_version`) that render provider adapters translate to the target engine's native format. See the JSON Composition Layer section below.

---

## Pipeline Stages

```
Stage 1 — Campaign Input
  BL gives: product, offer, audience, mood, volume, CTA intent
  CMO produces: approved Campaign Brief (marketing.plan artifact)

Stage 2 — Creative Concept  [creative.concept capability]
  Runs: INTAKE → INSIGHT → IDEATION → EVALUATE (single extended-thinking call)
  Produces: Creative Concept artifact
    - Insight statement
    - 3 scored concepts (originality 25%, strategic fit 20%, emotional 20%,
      feasibility 15%, scalability 10%, simplicity 10%)
    - Discarded directions → written to BOS memory
    - Creative Brief (production spec for the top concept)
  Gate: BL chooses one of 3 concepts before production begins
  BITE sample required: sample/creative_concept_artifact_v1.md

Stage 3 — Primitive Generation  [creative.primitive.generate]
  BOS does: reads primitive requirements from Creative Brief + BRAND.md → builds a
            brand-locked prompt per primitive → sends to configured provider → receives
            result → uploads to Drive
  Provider does: generates the image / video / audio
  Produces: image plates, video plates, motion cards stored in Drive; creative_assets
            rows written with approval_status=draft
  Gate: production Creative Director auto-validates against BRAND.md craft rules;
        passing primitives → approved; failing → retry or rejected (BL never sees this).
        Any primitive with fake text/logo, off-brand tone, unsupported claims, or missing
        required brand slots fails closed.

Stage 4 — Blueprint Assembly  [creative.blueprint.assemble]
  Runs: takes a JSON template skeleton + approved primitives → fills slots → emits a
        complete CompositionSpec JSON per concept variant
  Produces: CompositionSpec JSON stored in DB (creative_blueprints table) + Drive
  Validates: every asset_id resolves to an approved primitive; no slot is empty;
             brand_slots resolve against extracted Brand Kit
  Gate: internal — automated slot validation only; no BL review at this stage

Stage 5 — Brand Validation
  Runs: design discipline checks against BRAND.md
  Checks: contrast ratio, typography compliance, safe zones, no forbidden elements,
          no placeholder text, logo placement, CTA rules, text length limits
  Gate: blocks render if any P0 check fails
  Source: html-anything design constraints adapted as BOS craft rules

Stage 6 — Stitch + Render  [creative.render.*]
  BOS does: resolves asset_ids → Drive URLs; resolves brand_slots → Brand Kit values;
            translates CompositionSpec to provider-native format; POSTs to render engine;
            polls for completion; receives output file; uploads to Drive
  Provider does: composites all layers (AI-generated plates + brand assets + text) into
                 the final MP4 or PNG — this is the stitch
  Render providers (pluggable, set in Admin):
    local_ffmpeg   → BOS builds FFmpeg filter_complex command → FFmpeg stitches → MP4/PNG
    shotstack      → BOS sends Shotstack timeline JSON → Shotstack stitches → MP4/PNG/GIF
    creatomate     → BOS sends template + modifications → Creatomate stitches → MP4/PNG/PDF
    huashu         → BOS activates Huashu SKILL.md, sends design brief → Claude generates
                     HTML → export script converts to PNG/MP4/PPTX
  Render targets:
    poster_vertical   → 1080×1920 MP4 or PNG    (footage-based: local_ffmpeg default)
    carousel_square   → 1080×1080 PNG ×3        (design-forward: huashu default)
    email_html        → 600px CSS-inlined HTML  (HTML-native: huashu default)
    landing_page      → standalone HTML          (HTML-native: huashu default)
    concept_deck      → interactive HTML + PPTX  (always huashu)
  Batch: one CompositionSpec template + N modifications → N stitch calls; job table tracks
  Produces: Export Package per render target → uploaded to Drive
  Gate: Creative Bundle assembled from top outputs → surfaced in Stream for BL approval
```

---

## JSON Composition Layer

Inspired by Shotstack and Creatomate's API-first production model. The core insight: **the Creative Blueprint is not a database record with slot mappings — it is a JSON document that fully describes the edit.** The JSON is the master creative. Render engines consume it. Channel adapters modify it. Batch production loops data through it.

### Why this changes everything

In a traditional production model the master creative is a design file (Figma, After Effects, Premiere). Adapting it for platforms means a human opens the file, adjusts dimensions and safe zones, re-exports. This does not scale.

In the JSON editing model:
- The master creative is a machine-readable JSON document stored in the DB and Drive
- Rendering is an API call — POST the JSON, receive a file URL
- Channel adaptation is a JSON transformation — change dimensions and safe zones, re-render the same blueprint
- Batch production is a data loop — one template JSON + 50 `modifications` arrays = 50 renders, no human in the loop until the Creative Bundle review
- The JSON is diffable, versionable, and auditable — what changed between Blueprint v1 and v2 is a clean diff

### CompositionSpec schema (BOS v1)

BOS defines its own schema rather than locking to any single vendor. Render provider adapters translate it to Shotstack, Creatomate, or FFmpeg's native format.

```json
{
  "spec_version": "1.0",
  "blueprint_id": "bp_...",
  "brand_id": "...",
  "campaign_id": "...",
  "concept_ref": "concept_1",
  "composition": {
    "duration": 15,
    "dimensions": {"width": 1080, "height": 1920},
    "fps": 30,
    "background_color": "#F5F1EC",
    "tracks": [
      {
        "id": "background",
        "clips": [
          {
            "asset_id": "uuid-of-image-plate",
            "asset_type": "image_plate",
            "start": 0,
            "duration": 15,
            "fit": "cover",
            "position": "center",
            "transition_in": "fade",
            "transition_out": null
          }
        ]
      },
      {
        "id": "hook_text",
        "clips": [
          {
            "type": "text",
            "value": "You got the title. Nobody gave you the manual.",
            "brand_slot": "typography_heading",
            "color_slot": "color_primary",
            "start": 0.5,
            "duration": 4.5,
            "position": {"x": "5%", "y": "15%"},
            "max_width": "90%",
            "align": "left",
            "transition_in": "slide-up",
            "transition_out": "fade"
          }
        ]
      },
      {
        "id": "brand_overlay",
        "clips": [
          {
            "asset_id": "uuid-brand-overlay",
            "asset_type": "brand_overlay",
            "start": 0,
            "duration": 15,
            "position": "safe-zone-bottom-right"
          }
        ]
      }
    ]
  },
  "render_targets": [
    {
      "target_id": "poster_vertical",
      "dimensions": {"width": 1080, "height": 1920},
      "format": "mp4",
      "safe_zone": {"top": "10%", "bottom": "20%", "left": "5%", "right": "5%"}
    },
    {
      "target_id": "carousel_square",
      "dimensions": {"width": 1080, "height": 1080},
      "format": "png",
      "duration": null
    }
  ],
  "render_provider": "local_ffmpeg",
  "modifications": {}
}
```

**Key fields:**
- `tracks` — ordered layers, bottom to top. Borrowed from Shotstack's timeline model.
- `asset_id` — references `creative_assets` table. The render adapter resolves to a Drive URL at render time. Asset URLs never hardcoded in the spec.
- `brand_slot` / `color_slot` — instead of hardcoding `font-family: Inter`, the spec declares which brand slot to read. Brand Kit extraction populates the actual values at render time. Keeps the blueprint brand-agnostic until execution.
- `position: "safe-zone-bottom-right"` — named safe zone positions resolved per render target. The same overlay clip renders at the correct position regardless of aspect ratio.
- `modifications` — Creatomate-inspired. For batch production, the template spec has an empty `modifications: {}`. Each batch item provides its own modifications object (different hook text, different product image) and the composition is rendered independently. One spec, N outputs.
- `render_provider` — the adapter to use. Switching from `local_ffmpeg` to `shotstack` or `creatomate` does not change the blueprint. It changes only the translation step.

### The Stitch

The CompositionSpec is the stitch instruction. The render provider executes it.

AI-generated content and brand assets are always **separate files**. The AI image provider never receives the brand logo. The brand logo never passes through the image generation API. They are independent files stored in Drive, referenced separately in the CompositionSpec, and combined by the compositor at render time:

```
Layer 0 — AI-generated image plate       (Drive URL resolved from asset_id)
Layer 1 — AI-generated video plate       (Drive URL resolved from asset_id)
Layer 2 — Hook text block                (value from Creative Brief; font/color from Brand Kit)
Layer 3 — Brand overlay (logo + frame)   (Drive URL — client uploaded to Brand Assets/)
Layer 4 — CTA pill                       (style from Brand Kit cta_style slot)
```

The render provider pulls each file, composites the layers frame by frame, and returns one output file. That output is the branded creative. Nothing upstream of the render provider ever sees a "finished branded asset" — they see separate raw materials. The stitch is what makes it finished.

Templates define **where** the layers go. Brand Kit defines **how** they look (colors, fonts, CTA style). AI providers produce **what** the content layers contain. The compositor assembles all three into the final output. BOS directs all of it.

### Brand-Locked Media Generation Policy

All media production prompts are owned by the CMO brain, but they are **not free-form creative writing prompts**. They are brand-locked production instructions derived from the active Brand's `BRAND.md` / Campaign Brand Kit. Text, images, audio, video, and stitching all inherit the same brand contract before execution.

The approved BITE sample is `sample/brand_locked_media_production_blueprint_v1.json`.

**Hard rule:** brand alignment is a gate, not a style suggestion. No text, image, audio, video, CompositionSpec, render, or Creative Bundle may be generated or surfaced if required brand slots are missing.

Required brand slots for full media production:
- `brand_voice`
- `tone_adjectives`
- `color_primary`, `color_secondary`
- `typography_heading`, `typography_body`
- `logo_asset_id`
- `cta_style`
- `visual_mood`
- `forbidden_elements`
- `safe_zones`

**CMO brain owns the production blueprint:**
- text prompt → script, hook, captions, CTA
- image prompt → clean image plates only; no text/logo baked in
- audio prompt → voiceover/music tone aligned to Brand Kit
- video prompt → clean video plates only; no text/logo/caption baked in
- stitching prompt → CompositionSpec that applies logo, typography, captions, CTA, color treatment, safe zones, and transitions
- validation rules → pre-prompt, post-generation, pre-render, and bundle-review brand gates

**Forbidden:** generic prompts without brand slots; logo baked into AI media; off-brand sound beds; unsupported claims; fake text in generated images/video; final MP4 without editable CompositionSpec JSON; channel-specific publishing inside creative generation.

### Render Provider Abstraction

```
CompositionSpec JSON
        │
        ▼
  render_provider field
        │
   ┌────┴──────────────────┐
   │                       │
local_ffmpeg           cloud_api
   │                       │
FFmpeg filter_complex  ┌───┴───────────────┐
(self-hosted,          │                   │
 no API cost,      Shotstack           Creatomate
 V1 default)       (video-first,       (template/
                    strong for          batch-first,
                    dynamic             strong for
                    timelines)          image + PDF)
```

**V1 default: `local_ffmpeg`** — FFmpeg binaries are already in the repo. No external API cost, no per-render pricing, no vendor dependency for the core pipeline. Suitable for agency volume at moderate scale.

**V2 / scale: Shotstack or Creatomate** — pluggable via `render_provider` field in the CompositionSpec and `render_provider` config in the creative factory plugin's `channel.json`. Add a new provider adapter in `api/plugins/creative-factory/providers/` without touching any other pipeline code.

**When to use each:**

| Provider | Best for | Trade-off |
|---|---|---|
| `local_ffmpeg` | V1, cost control, self-hosted | Complex animations require manual filter_complex wiring |
| `shotstack` | Dynamic video timelines, transitions, multi-track compositing at scale | Per-render pricing; requires internet; 30s–3min render time |
| `creatomate` | Data-driven batch rendering, image + video + PDF from one template | Per-render pricing; template management overhead |

### Batch Rendering Flow

```
creative_job created (status: queued)
  │
  ▼
worker picks up job
  │
  ├─ fetch CompositionSpec template from DB
  ├─ fetch modifications list (one per creative variant)
  │
  ├─ for each modification:
  │     merge modifications into template → resolved CompositionSpec
  │     resolve asset_ids → Drive URLs
  │     resolve brand_slots → Brand Kit values
  │     POST to render provider
  │     store render job ID → poll for completion
  │     on complete: download file → upload to Drive → write Export Package
  │
  └─ when all renders complete:
        Creative Director (production) auto-validates each Export Package
        assemble Creative Bundle from top outputs
        write creative_bundle artifact → surfaces in Stream for BL approval
```

This is what makes 50-creative batch production possible within the async job model. The BL commissions the job from CMO chat, the creative factory runs the loop, the Creative Bundle appears in Stream when ready.

---

## BRAND.md Injection Architecture

Before any creative production capability runs, the executor generates `BRAND.md` from the active brand's Campaign Brand Kit and injects it. For full media production, this injection is mandatory and blocks execution when required slots are missing.

Skills declare what they need:

```yaml
bos.brand_slots:
  - color_primary
  - color_secondary
  - typography_heading
  - logo_url
  - cta_style
  - visual_mood
  - forbidden_elements
bos.craft.requires:
  - typography
  - color
  - anti-ai-slop
  - safe-zones
```

Full text/image/audio/video/stitch jobs additionally require the brand-locked production blueprint contract in `sample/brand_locked_media_production_blueprint_v1.json`. The CMO brain must generate every downstream provider prompt from `BRAND.md`; providers do not improvise brand identity.

Shared craft rules live at:

```
api/capabilities/marketing/creative/craft/
  typography.md       ← heading scale, body size, line height rules
  color.md            ← contrast minimums (4.5:1), palette application
  anti-ai-slop.md     ← no fake text in visuals, no lorem ipsum, no placeholder faces
  safe-zones.md       ← per render target: CTA/logo exclusion zones
  motion.md           ← frame duration, easing, transition rules
```

Brand tokens override craft rules on conflict. The `bos:` namespace is used for capability extensions — backward-compatible with Claude Code's base SKILL.md format.

---

## Selected External Integrations

### From smixs/creative-director-skill

**Take:**
- 5-phase methodology: INTAKE → INSIGHT → IDEATION → EVALUATE → ARTICULATE
- Creative Constitution (Layer 1: 8 brief compliance checks, Layer 2: 7 quality principles)
- 6 weighted scoring criteria
- 18 campaign patterns (P01–P18) as SKILL.md reference tags
- "Discarded directions" output → BOS memory
- Feedback template structure as BL review contract

**Leave:**
- 571 campaign cards — reference the 18 pattern tags only
- 4 output presentation templates — BOS renders in Stream
- Python maintenance scripts
- Recursive refinement loop complexity — single extended-thinking call for V1

**Implementation:** `api/capabilities/marketing/creative/concept/`  
Single extended-thinking LLM call, not sequential turns.

### From nexu-io/html-anything

**Take (6 template shells only):**

| Template | BOS Render Target | Output |
|---|---|---|
| `poster-hero` | `creative.render.poster_vertical` | 1080×1920 PNG |
| `social-carousel` | `creative.render.carousel_square` | 1080×1080 PNG ×3 |
| `email-marketing` | `creative.render.email_html` | CSS-inlined HTML 600px |
| `video-hyperframes` | `creative.render.video_frames` | HTML → FFmpeg → MP4 |
| `saas-landing` | `creative.render.landing_page` | Standalone HTML |
| `deck-product-launch` | `creative.render.concept_deck` | BL concept presentation |

**Design discipline as craft rules** — 8px grid, 4.5:1 contrast, no placeholder text, inline styles for email.

**Leave:**
- The html-anything application (Next.js, agent detection, WeChat export, Zhihu)
- CJK-specific templates (XHS, Xiaohongshu)
- Business ops templates (runbooks, OKRs, invoices)
- All remaining deck variants

### From nexu-io/open-design protocol

**Take:**
- DESIGN.md injection pattern → renamed BRAND.md in BOS
- craft/ directory pattern for shared design discipline
- `bos:` extension namespace for SKILL.md (Claude Code compatible)
- Hand-built example.html requirement as BITE sample gate
- Scan precedence concept (brand-specific skill overrides shadow defaults)

**Leave:**
- `od:` frontmatter fields (not BOS's namespace)
- Daemon CLI (`od skill add/remove`)
- `od.parameters` slider UI
- pptx/jsx preview modes
- Localization infrastructure

---

## Google Drive Integration

**Why Drive:** Google OAuth already exists in BOS (Gmail, Calendar use the same Google app). Drive is an additive scope — no new vendor, no new OAuth app.

**OAuth scopes:**
- `https://www.googleapis.com/auth/drive.file` — read/write files BOS creates
- `https://www.googleapis.com/auth/drive.readonly` — read brand assets client uploads manually

**Folder structure (created at OAuth connection time per brand):**

```
Klaroha BOS/
└── {Brand Name}/
    ├── Brand Assets/          ← client uploads logos, product images, existing footage
    │   ├── Logos/
    │   ├── Products/
    │   └── Footage/
    ├── Templates/             ← HTML template shells
    ├── Campaigns/
    │   └── {Campaign Name}/
    │       ├── Creative Concepts/   ← Creative Director output
    │       ├── Primitives/
    │       │   ├── Image Plates/
    │       │   ├── Video Plates/
    │       │   └── Motion Cards/
    │       ├── Blueprints/
    │       └── Export Packages/     ← render targets, ready for channels
    └── Archive/
```

**Plugin location:** `api/plugins/google-drive/`  
**Capabilities:** `drive.folder.setup`, `drive.asset.upload`, `drive.asset.list`, `drive.asset.get`  
**Asset ID:** Drive file ID used as `asset_id` in `creative_assets` table

---

## Components and Their Locations

```
api/capabilities/marketing/creative/
  concept/              ← Creative Director (strategic) — new first-party capability
    SKILL.md
    module.py
    template.j2
    references/
      creative-constitution.md
      scoring-criteria.md
      pattern-map.md          ← P01–P18 pattern tags (not 571 cards)
  craft/                ← shared design discipline files
    typography.md
    color.md
    anti-ai-slop.md
    safe-zones.md
    motion.md

api/plugins/creative-factory/
  channel.json          ← already exists
  capabilities/
    creative/
      pack/generate/    ← already scaffolded
      primitive/generate/  ← already scaffolded
      blueprint/assemble/  ← already scaffolded
      render/           ← NEW — render target capabilities
        poster_vertical/
          SKILL.md
          module.py
          assets/template.html
          assets/example.html   ← hand-built, required before build
          references/checklist.md
        carousel_square/
        video_frames/
        email_html/
        landing_page/
        concept_deck/

api/plugins/google-drive/
  channel.json          ← new plugin
  capabilities/
    drive/
      folder/setup/
      asset/upload/
      asset/list/
      asset/get/
```

---

## Admin Provider Configuration

The creative factory cannot run until the operator configures its providers in Admin → Specialists. This follows the existing BYOK model — same pattern as configuring an OpenAI key for the CMO LLM, applied per modality.

**Readiness check:** if any required provider for the requested creative type is not configured, the creative factory surfaces a setup blocker in Stream before the job is queued. Same pattern as the existing `onboarding/status` readiness check.

```
Admin → Specialists → Creative Factory

Image generation
  Provider:  [ OpenAI gpt-image-1 ▾ ]    API key: [••••••••]
  Options:   OpenAI gpt-image-1 | Stability AI | Ideogram | Flux (OpenRouter)

Video generation  (required for video plates — optional for image-only campaigns)
  Provider:  [ Runway Gen-4 ▾ ]           API key: [••••••••]
  Options:   Runway | Kling | Hailuo | skip (image-only campaigns)

Stitch / render
  Provider:  [ local FFmpeg ▾ ]           (no key — binary already in repo)
  Options:   local FFmpeg (default) | Shotstack (API key) | Creatomate (API key)

Design / HTML render
  Provider:  [ Claude + Huashu skill ▾ ]  (uses configured CMO LLM — no separate key)

Copy generation
  Inherits CMO LLM configuration — no separate setting needed
```

**How credentials reach the plugin:** same as all other plugins — `inject_channel_credentials()` in `runs.py` resolves configured provider keys and passes them in `brief["_channel_credentials"]`. The creative factory plugin reads from there. It never calls `get_settings()` or queries the DB directly.

**Per-brand provider override (future):** V1 uses workspace-level provider configuration. A future iteration could allow per-brand provider overrides (e.g., Motormoto uses Stability, Klaroha uses OpenAI). Not in scope now.

---

## Build Sequence

Order matters. Each phase gates the next.

### Phase A — Foundation (build first, nothing else runs without these)

1. **DB migrations** — three new tables:
   - `creative_assets` (asset library metadata)
   - `creative_blueprints` (CompositionSpec JSON storage)
   - `creative_jobs` (async job lifecycle: queued → running → completed / failed)

2. **google-drive plugin** — folder setup per brand at OAuth time; `drive.asset.upload`, `drive.asset.list`, `drive.asset.get` capabilities; reuses existing Google OAuth app with `drive.file` + `drive.readonly` scopes added

3. **Admin provider configuration UI** — Specialists panel additions for image gen, video gen, stitch provider, design provider; `inject_channel_credentials()` extended to resolve creative factory provider keys; readiness check for missing providers

### Phase B — Core pipeline (the request-build-and-route chain)

4. **`creative.concept`** — first-party capability at `api/capabilities/marketing/creative/concept/`; single extended-thinking LLM call; outputs `creative_concept` artifact to Stream; BITE sample: `sample/creative_concept_artifact_v1.md` (produced)

5. **`creative.pack.generate`** — creates `creative_job` row, returns `creative_job` artifact immediately; starts the async job; CMO chat is freed

6. **`creative.primitive.generate`** — reads primitive requirements from Creative Brief + `BRAND.md`; builds a brand-locked prompt per primitive type; calls configured image/audio/video provider; receives result; uploads to Drive; writes `creative_assets` row; production CD auto-validates against BRAND.md

7. **`creative.blueprint.assemble`** — loads template CompositionSpec skeleton; fills slots with approved primitive `asset_id`s and brand slot references; validates all slots filled; writes completed CompositionSpec to `creative_blueprints` + Drive

### Phase C — Stitch and surface

8. **`creative.render` / FFmpeg adapter** — translates CompositionSpec to FFmpeg `filter_complex` command; resolves `asset_id`s to Drive URLs; resolves `brand_slot`s to Brand Kit values; applies typography/logo/CTA/caption/safe-zone rules; executes FFmpeg; uploads output to Drive; writes Export Package record. Render is blocked if brand validation fails.

9. **Creative Bundle assembly** — curates top Export Packages from a completed job; writes `creative_bundle` artifact; surfaces in Stream for BL approval

10. **Stream card for `creative_bundle`** — render target previews, concept reference, brand compliance status, `[Approve Bundle]` / `[Request revision]` actions

### Phase D — Design outputs

11. **Huashu concept deck** — activates Huashu SKILL.md for concept presentation HTML; produces interactive device-mockup deck; exports PPTX for client sharing; gates on Phase B creative.concept being proven

### Phase E — Scale (V2, not in this build)

- Shotstack / Creatomate render provider adapters
- Per-brand provider overrides in Admin
- Batch modifications loop (N renders from one template)

---

## Next Iteration — Two Acceptance Scenarios

These are the concrete proofs the next iteration must demonstrate. They define what "the Google Drive + stitch layer works" actually means in practice. Both start from a real brand asset in Drive.

### Scenario A — Brand asset → stitched channel-specific creatives (the manufacturing path)

Prove that one brand asset (a logo, a product image) plus a background plate can be stitched into multiple channel-specific outputs from a single source:

```
Brand asset in Drive (logo.png, product.png)
  + background plate (AI-generated or client footage)
  + brand slots (color, font, CTA from Brand Kit)
        │
        ▼  one CompositionSpec, three render targets
        │
  ├── Banner ad        → 300×250 + 728×90 PNG   (Google Display)
  ├── IG carousel      → 1080×1080 PNG ×3
  └── Shortform video  → 1080×1920 MP4
```

Pass condition: the same logo and product asset appear, correctly placed and brand-styled, across all three formats — produced by changing render target parameters on one CompositionSpec, not by three separate creative jobs.

### Scenario B — Attach existing creative → single social post (the fast path)

Prove the simplest, highest-frequency operator action: the client already has a finished creative; the operator just wants to push it.

```
Existing creative in Drive (or a past Export Package)
        │
        ▼
  operator: "post this to Instagram"
        │
  drive.asset.get → attach to channel plugin's post → publish (approval-gated)
```

Pass condition: no generation, no stitching — an existing asset is selected from the library and handed to a channel plugin for a single approved post. This is the "I already made this, just post it" case and must be as frictionless as the manufacturing path is powerful.

**Why both matter:** Scenario A proves the factory. Scenario B proves the library is useful even when nothing is manufactured. Most real operator days are Scenario B with occasional Scenario A. The Drive plugin and asset library must serve both from day one.

---

## What Is Not Being Built

Explicitly out of scope for this mini project:

- Ad platform publishing (Meta, TikTok, YouTube publish actions) — those are channel plugins
- Performance optimization or attribution — Phase 2
- Budget or audience logic — belongs in marketing.plan
- Shotstack / Creatomate render adapters — V2 (Phase E); FFmpeg covers V1
- Batch modifications loop (N renders from one template) — V2 (Phase E)
- Per-brand provider overrides in Admin — V2
- TikTok Content Posting API — waiting on API access approval
- The html-anything application or any part of its UI
- The 571-campaign library as embedded data
- BOS generating or rendering anything natively — all generation and rendering is third-party

---

## Open Decisions

All resolved. See Decisions table below.

---

## User Experience Flow

### Overview
The Creative Factory provides a streamlined user experience where business leaders commission creative work through natural conversation, specialists produce assets behind the scenes, and final outputs are reviewed as curated Creative Bundles. The system separates creative production from channel distribution, ensuring each plugin can be optimized independently.

### Setup Once in Admin
**Admin → Specialists**
- User sees separate cards for each specialist:
  - Creative Factory (orchestrator)
  - Image Generation (media.image)
  - Video Generation (media.video)
  - Render / Stitch (composition)
  - Google Drive (asset library)
- Each card shows status, provider, credentials, latency, last run, and errors
- User connects/configures providers as needed

### Provider Configuration
**Image Generation:** OpenAI / Stability / Ideogram / etc.
**Video Generation:** Runway / Kling / local FFmpeg / etc.
**Render/Stitch:** FFmpeg / Shotstack / Creatomate
**Drive:** Brand asset folder structure
- If any required provider is missing, Stream shows a setup blocker
- Provider credentials are stored per workspace, not per brand

### Natural CMO Conversation
**User:** "Make a creative bundle for Klaroha's launch."
**CMO Reply:** "I'll produce a reviewable creative bundle. Image, video, and render work will run as separate specialist steps."
- Chat does not paste final copy/assets inline
- User experience feels like commissioning a print job to production

### Creative Job Creation
**Stream Card:** "Creative job started"
- Brand context
- Objective
- Planned outputs: image plates, short video, social post creative, banner, etc.
- No spinner-lock in chat
- Job ID and quick status overview

### Specialist Execution (Behind the Scenes)
Creative Factory orchestrates:
- `media.image.generate` for image plates
- `media.video.generate` for video content
- `media.render.stitch` for composition
- Drive upload for asset durability
- Quality compliance checks
Each plugin runs independently with optimized performance profiles

### User Progress Visibility
**Stream Shows:**
- "Generating image plates"
- "Rendering shortform video"
- "Uploading assets to Drive"
- "Curating bundle"
**User Does NOT See:**
- Raw primitive outputs
- Individual provider failures
- System implementation details
- Large base64 image payloads

### Creative Bundle Output
**Stream Card:** One primary review surface
- Hero image preview
- Shortform video preview
- Caption/copy variants
- Banner/social variants
- Drive links for assets
- Self-check notes
**Actions:**
- Approve Bundle
- Request Revision
- Dismiss
- Export / Send to Channel

### Revision Workflow
**User:** "Make the video more direct and less polished."
**CMO Routes:**
- Visual issues → image/video plugin
- Assembly issues → render plugin
- Concept issues → Creative Factory / Creative Director
- User doesn't need to know which plugin is called

### Approval and Learning
**Approved Assets:** Become reusable Drive assets
**BOS Records:**
- Approved concepts
- Rejected variants
- Provider latency/cost
- Quality notes
**Future Improvement:** Creative jobs learn from approved/rejected decisions

### Publishing Separation
**User:** "Post this to Facebook"
**Channel Plugin Receives:** Approved Drive asset reference
**CMO Dispatches:** Appropriate channel capability
**Distribution:** Platform-specific execution

### Allowed vs Forbidden Outcomes
**Allowed:**
- User commissions work through natural conversation
- Creative Factory orchestrates specialist plugins
- Stream shows curated Creative Bundle for approval
- Assets stored in Drive with metadata
- Publishing is approval-gated and channel-owned
- Performance optimizations per plugin type

**Forbidden:**
- Giant base64 image payloads slowing Stream
- Hidden video rendering inside Creative Factory
- Channel-specific publish buttons hardwired into creative generation
- CMO pasting final assets as chat text
- Failed providers buried inside generic creative errors
- Creative Factory directly generating or rendering content

### Intended User Feeling
- **User says what they want**
- **BOS commissions the right specialists**
- **Stream shows one clean decision surface**
- **Assets are stored in Drive**
- **Publishing is approval-gated and channel-owned**
- **System learns from decisions**

## Build Gate — BITE Compliance

**No capability is built until its sample is produced and agreed.**

Required samples before any code:

| Capability | Sample file | Status |
|---|---|---|
| `creative.concept` | `sample/creative_concept_artifact_v1.md` | **Produced — pending BL approval** |
| `CompositionSpec` schema | `sample/creative_composition_spec_v1.json` | **Produced — valid JSON** |
| Primitive image-gen request | `sample/creative_primitive_request_v1.json` | **Produced — valid JSON; live gen proven (981KB PNG via media.image.generate)** |
| `creative.render.poster_vertical` | `api/plugins/creative-factory/capabilities/creative/render/poster_vertical/assets/example.html` | Not started |
| `creative.render.video_frames` | `api/plugins/creative-factory/capabilities/creative/render/video_frames/assets/example.html` | Not started |
| `creative.render.email_html` | `api/plugins/creative-factory/capabilities/creative/render/email_html/assets/example.html` | Not started |
| `google-drive` folder setup | `sample/google_drive_setup_v1.md` | **Produced — pending approval** |
| Creative Bundle artifact (BL review surface) | `sample/creative_bundle_v2.md` | `creative_bundle_artifact_v1.md` exists — needs revision |

Samples are hand-built. No AI-generated placeholder content.

---

## Decisions

| Decision | Rationale |
|---|---|
| Creative Director runs as single extended-thinking call | Avoids sequential LLM turn complexity for V1; good enough for concept quality |
| BL approves Creative Bundle, not individual primitives | Matches agency model; Creative Director gates what the BL sees |
| Google Drive as asset library storage backend | OAuth already in BOS; no new vendor; clients already use Drive |
| BOS DB tracks asset metadata; Drive stores binaries | Mirrors professional DAM pattern; enables intelligent asset selection |
| BRAND.md injected before any creative production capability | Keeps brand rules out of templates; templates stay channel-agnostic |
| html-anything templates taken as shells only, not the application | BOS has its own execution model; only the HTML layouts are needed |
| `bos:` extension namespace for SKILL.md | Backward-compatible with Claude Code base format; avoids `od:` namespace collision |
| channel.json used for production plugins (creative factory) | Pragmatic; will revisit manifest type if production/channel boundary needs enforcement |
| Creative Blueprint is a CompositionSpec JSON, not a slot-mapping record | JSON is the edit — machine-readable, diffable, render-engine agnostic. Inspired by Shotstack (track/clip/timeline) and Creatomate (modifications/batch). BOS owns the schema; adapters translate to each engine. |
| V1 render provider is local FFmpeg | FFmpeg binaries already in repo, no per-render cost, no vendor dependency. Shotstack and Creatomate are V2 pluggable options via `render_provider` field — no pipeline changes needed to switch. |
| `brand_slot` / `color_slot` references in CompositionSpec, not hardcoded values | Blueprint stays brand-agnostic until render time. Brand Kit extraction populates actual values. Same blueprint spec can be re-rendered for a different brand by changing the Brand Kit injection. |
| Drive connection is per brand, not per workspace | Agency and multi-brand org both require isolation — Client A's assets must never mix with Client B's. Errors and Drive permissions are brand-scoped. |
| Drive root folder is operator-picked via Google Picker, not a hardcoded `Klaroha BOS/{Brand}` path | Hierarchy is Org → agency/project → brand; an agency already has a Drive layout (e.g. `Clients/{Brand}/`). Operator picks the existing root via the Google Picker (which grants `drive.file` write access to it); BOS creates its working subfolders underneath. Root folder ID stored on the connection; creative factory, channels, and CMO all resolve from it. Requires `GOOGLE_PICKER_API_KEY` + Picker API enabled. |
| Primitive generation is async — plugin-local job lifecycle | Both core use cases (agency managing multiple clients, multi-brand org) require commission-and-return, not waiting on a spinner. Creative production is a print job, not a chat response. `creative_job` table + lightweight worker lives inside the creative-factory plugin only — no BOS-core queue. |
| Creative Director (production) auto-approves individual primitives | BL does not see raw primitives. The production CD gates quality internally; BL reviews the curated Creative Bundle only. Keeps approval cadence human-scale. |
| BRAND.md injection via existing `_inject_campaign_brand_kit_style()` hook in `runs.py` | Hook is already brand-scoped, already fires pre-execution, isolation guarantee proven. Extending it reuses a trusted boundary. New lifecycle hook deferred to pi-pattern refactor. |
| BOS is a routing and orchestration system — it generates nothing natively | Every image, video, copy block, and rendered composition is produced by a configured third-party AI or render service. BOS builds the request, sends it, captures the result, and routes it forward. |
| Templates define structural rules only — no brand values, no generated content | A template says where layers go and what the safe zones are. Brand assets and AI-generated content are separate files that fill the template slots at stitch time. Same template works for every brand. |
| AI-generated content and brand assets are stitched by the render provider, not by BOS | BOS writes the CompositionSpec (the layer-by-layer instruction). The render provider (FFmpeg/Shotstack/Creatomate) composites AI content + brand assets + text into the final file. BOS directs the stitch; the compositor performs it. |
| Huashu is Claude + SKILL.md, not a separate API or render service | When BOS needs a design output (concept deck, HTML-native render targets), it activates the Huashu SKILL.md and the configured LLM generates the HTML. No separate API key, no separate vendor. Uses the same LLM already configured for the CMO. |
| Admin must configure a provider per modality before the creative factory can run | Image gen, video gen, stitch/render, and design/HTML providers are all set in Admin → Specialists. Missing provider = readiness blocker surfaced in Stream. Follows existing BYOK pattern. |
