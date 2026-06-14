# Feature Specification: Creative Context Production — Repurposable Reference-to-Image/Video Workflow

**Feature Branch**: `002-creative-context-production`
**Created**: 2026-06-14
**Status**: Draft business specification
**Input**: Planning discussion: users attach images/documents/text to CMO chat; discussion may remain strategic or become image/video generation; references must be reusable, patchable, and addressable across turns.

---

## Business Goal

Enable CMO Chat to become the operator-facing creative production room: users can upload documents, images, storyboard sheets, brand references, and text notes; discuss them with the CMO; refine structured details; then reuse the same context to generate images, videos, revisions, or future campaign assets.

The system must stop treating attachments as temporary prompt stuffing. Every uploaded/reference item becomes a durable, addressable creative reference with extracted structure. The CMO mediates discussion and edits, while specialist generation models consume canonical specs derived from that reusable context.

---

## Core Principle

```text
Upload / Drive reference / inline text
  ↓
Stable ChatReference ID
  ↓
Upload-time extraction and analysis
  ↓
CreativeContext
  ↓
CMO discussion and user decisions
  ↓
ImageSpec / StoryboardSpec / VideoSpec
  ↓
Provider-specific generation
  ↓
Artifact + revision history
  ↓
Patchable next turn
```

The editable source of truth is not chat history, not the returned MP4/image, and not provider-specific JSON. The source of truth is BOS-owned structured context and canonical specs.

---

## Primary Use Case Example

An operator uploads:

1. One document describing a video concept.
2. Four black-and-white images representing 16 storyboard scenes.
3. One colored image representing the final shot.

The system should:

1. Create stable reference IDs for all six uploaded items.
2. Extract the document into structured concept fields.
3. Analyze the four black-and-white images as storyboard/composition references.
4. Detect or allow assignment of 16 scene candidates across the four storyboard images.
5. Analyze the colored image as a final-shot, color, lighting, or mood reference.
6. Let the CMO discuss the material before any generation happens.
7. Build a `StoryboardSpec` for review.
8. Convert the confirmed storyboard into a provider-neutral `VideoSpec` only when the user proceeds.
9. Allow later user edits as patches to references, storyboard scenes, or video spec fields.

This example must be implemented generically so the same system works for:

- single image discussion,
- reference-based image generation,
- text-to-video,
- image-to-video,
- storyboard-to-video,
- JSON/document variable edits,
- later video/image revision.

---

## User Scenarios & Testing

### User Story 1 — Discuss an uploaded image without generating anything (Priority: P1)

A user uploads an image and asks the CMO what it thinks about the direction. The CMO should analyze and discuss the image, identify possible uses, and capture useful creative observations without dispatching image or video generation.

**Why this priority**: This proves references are reusable creative context, not automatic generation triggers.

**Independent Test**: Upload one image and ask for feedback. Verify the system creates a reference ID, extracts/analyzes it, and CMO replies conversationally without creating a generated asset.

**Acceptance Scenarios**:

1. **Given** an uploaded image, **When** the user asks “what do you think of this?”, **Then** the system stores the image as a stable reference and returns CMO analysis without running generation.
2. **Given** the image analysis has possible roles, **When** the CMO replies, **Then** it may suggest next actions such as “use as style reference” or “turn into video” but must not execute them without user intent.

---

### User Story 2 — Discuss references, then generate an image from the same context (Priority: P1)

A user discusses an uploaded image and later says “make a product image like this.” The system should reuse the existing reference, analysis, and user decisions to compose an `ImageSpec` and dispatch image generation.

**Why this priority**: Shows that discussion produces durable production context.

**Independent Test**: Upload image, discuss it, then request a new generated image using the established direction.

**Acceptance Scenarios**:

1. **Given** a previously analyzed image reference, **When** the user requests a new image, **Then** the generated image spec includes the original reference ID and its intended role.
2. **Given** the user clarified “use this as mood, not exact subject,” **When** the image spec is composed, **Then** the reference role is `style_reference` or equivalent, not `character_reference`.

---

### User Story 3 — Convert a creative discussion into a video plan (Priority: P1)

A user discusses images/documents with the CMO and later says “turn this into a 15-second reel.” The system should compose a provider-neutral `VideoSpec` from the existing context instead of relying on chat memory.

**Why this priority**: This is the central path for CMO-mediated video production.

**Independent Test**: Upload one document and one image, discuss them, then request video. Verify the video spec references the same IDs and uses structured extracted context.

**Acceptance Scenarios**:

1. **Given** a concept document and reference image, **When** the user asks to proceed to video, **Then** the system creates a `VideoSpec` with scenes, duration, aspect ratio, reference roles, and constraints.
2. **Given** the user has not specified duration/aspect ratio, **When** the video spec is drafted, **Then** the system uses reasonable defaults and exposes assumptions for confirmation.

---

### User Story 4 — Storyboard-to-video from document + 4 B&W images + final color image (Priority: P1)

A user uploads a concept doc, four black-and-white storyboard sheets covering 16 scenes, and one colored final-shot image. The system should produce a reviewable scene map before generation.

**Why this priority**: This captures the flagship business use case for high-value video production.

**Independent Test**: Provide the six references and ask CMO to prepare the video. Verify a 16-scene `StoryboardSpec` is created before any provider call.

**Acceptance Scenarios**:

1. **Given** four black-and-white storyboard images, **When** the system analyzes them, **Then** it treats them as storyboard/composition references by default, not final color/style references.
2. **Given** one colored final image, **When** the storyboard is composed, **Then** it is assigned as final-shot/color/lighting reference unless the user chooses otherwise.
3. **Given** the system detects 16 scene candidates, **When** CMO presents the plan, **Then** the user can confirm, reorder, rename, or revise scenes before generation.
4. **Given** user confirms the storyboard, **When** the user says “proceed,” **Then** the system composes a `VideoSpec` and dispatches the video specialist.

---

### User Story 5 — CMO-mediated in-turn JSON patching (Priority: P1)

A user asks the CMO to change an extracted document variable, such as “change body_gold hex to #D4A800.” The CMO should emit a structured patch referencing the stored `ChatReference` ID and JSON path.

**Why this priority**: Enables editable creative context without needing immediate server-side persistence for every in-chat change.

**Independent Test**: Upload a JSON/doc reference with extracted variables, ask for a scalar change, and verify the frontend receives a structured patch event.

**Acceptance Scenarios**:

1. **Given** a document reference with extracted variables, **When** the user asks to change a specific variable, **Then** CMO emits a `PATCH_REFERENCE` directive containing `reference_id`, path, operation, and new value.
2. **Given** a valid patch directive, **When** the backend streams the response, **Then** the visible CMO text excludes the directive and a structured patch event is sent to the frontend.
3. **Given** the frontend receives the patch, **When** it applies it locally, **Then** the next chat turn sends the patched working copy of the reference.

---

### User Story 6 — Revise generated video by patching the canonical spec (Priority: P2)

After a generated video returns, the user asks for an edit such as “make scene 7 darker” or “use the colored look across all scenes.” The system should patch the canonical spec and create a new version.

**Why this priority**: Prevents fragile “revise the last video” prompt-only workflows.

**Independent Test**: Generate a video spec, simulate an edit request, and verify a patch targets stable scene IDs rather than array indexes or raw provider JSON.

**Acceptance Scenarios**:

1. **Given** a `VideoSpec` with stable scene IDs, **When** the user requests a scene edit, **Then** the patch references `scene_id` and a field path.
2. **Given** the provider does not support partial video editing, **When** an edit is requested, **Then** the system falls back to full regeneration from the patched spec.

---

## Functional Requirements

### Reference Ingestion and Identity

- **FR-001**: The system MUST create a stable `ChatReference.id` for every uploaded, Drive-selected, or inline creative reference.
- **FR-002**: The system MUST persist `ChatReference` metadata in a database table so references can be addressed across chat turns.
- **FR-003**: The system MUST support reference kinds: `image`, `document`, and `text` at minimum.
- **FR-004**: The system MUST support reference sources: `upload`, `inline`, and `google_drive` at minimum.
- **FR-005**: The system MUST keep extraction state per reference: `pending`, `read`, `vision_ready`, `failed`, `empty`, or `skipped`.
- **FR-006**: The system MUST preserve file/source metadata such as title, MIME type, Drive ID/link, thumbnail link, storage URL, hash, dimensions, and file size when available.

### Upload-Time Extraction

- **FR-007**: Extraction MUST happen on upload or reference ingest, not only during `/chat` request handling.
- **FR-008**: Document references MUST produce text excerpts and, when possible, parsed `extraction_json`.
- **FR-009**: JSON documents MUST preserve their parsed JSON structure exactly as editable source context.
- **FR-010**: Text documents that are not JSON MUST be wrapped into a JSON document envelope so downstream skills receive structured context.
- **FR-011**: Image references MUST be marked `vision_ready` and/or analyzed into reusable observations.
- **FR-012**: Extraction failures MUST be visible in the reference state and MUST NOT be silently treated as readable context.

### Variables and Patching

- **FR-013**: The system MUST expose editable scalar variables from `extraction_json` using stable JSONPath-like paths.
- **FR-014**: Variable paths SHOULD be relative to the reference `extraction_json`, not to a transient chat packet index.
- **FR-015**: CMO MUST be able to emit a hidden `PATCH_REFERENCE` directive for reference edits.
- **FR-016**: `PATCH_REFERENCE` MUST include at minimum: `reference_id`, `op`, `path`, `value`, and optional `reason`.
- **FR-017**: Backend MUST strip patch directives from visible CMO text.
- **FR-018**: Backend MUST emit patch directives as structured frontend events.
- **FR-019**: For MVP, the frontend MAY apply patches to its local working copy without immediately persisting the patched version server-side.
- **FR-020**: The next `/chat` request MUST be able to send the patched reference working copy back to the server.

### Creative Context

- **FR-021**: The system MUST assemble selected references into a reusable `CreativeContext` packet for CMO and specialist skills.
- **FR-022**: `CreativeContext` MUST include references, extraction summaries, image analyses, user decisions, constraints, and candidate next actions when available.
- **FR-023**: CMO discussion MUST be able to add creative decisions without triggering generation.
- **FR-024**: Creative decisions MUST be reusable by image and video spec composers.
- **FR-025**: The system MUST distinguish discussion mode from production mode.

### Image and Video Specs

- **FR-026**: The system MUST compose provider-neutral `ImageSpec` objects from creative context for image generation.
- **FR-027**: The system MUST compose provider-neutral `VideoSpec` objects from creative context for video generation.
- **FR-028**: The system MUST compose a `StoryboardSpec` when the input material represents a multi-scene storyboard.
- **FR-029**: Specs MUST use stable IDs for scenes, references, panels, and versions.
- **FR-030**: Specs MUST NOT depend on provider-specific request schemas as their source of truth.
- **FR-031**: Provider adapters MUST compile canonical specs into provider-specific requests.
- **FR-032**: Provider request and response JSON MUST be stored for audit but MUST NOT replace canonical specs.

### Storyboard-to-Video

- **FR-033**: The system MUST support mapping multiple images into scene candidates.
- **FR-034**: The system MUST support treating black-and-white images as storyboard/composition references by default.
- **FR-035**: The system MUST support treating a colored image as final-shot, color, lighting, or mood reference.
- **FR-036**: The system MUST present a reviewable scene map before generating video when a storyboard is detected.
- **FR-037**: Users MUST be able to confirm or revise scene order, descriptions, roles, and assumptions before generation.

### Revisions

- **FR-038**: Revisions to generated creative outputs MUST be represented as patches to canonical specs or references.
- **FR-039**: Video scene revisions MUST target stable `scene_id` values, not array positions.
- **FR-040**: The system MUST create new spec versions for material revisions.
- **FR-041**: If partial regeneration is unavailable, the system MUST safely fall back to full regeneration from the patched spec.

---

## Key Entities

### ChatReference

A durable reference item attached by the user or selected from storage. Represents image, document, or text context used for discussion and production.

Key attributes:

- `id`
- `workspace_id`
- `brand_id`
- `conversation_id`
- `campaign_id`
- `kind`
- `source`
- `title`
- `notes`
- `mime_type`
- `storage_url`
- `drive_file_id`
- `drive_web_view_link`
- `thumbnail_link`
- `sha256`
- `metadata_json`
- `text_excerpt`
- `extraction_status`
- `extraction_error`
- `extracted_chars`
- `extraction_json`
- `variables_json`

### ReferenceAnalysis

Structured interpretation of a reference, especially image/storyboard analysis. May be stored inline on `ChatReference` initially or split later.

Key attributes:

- `reference_id`
- `facts`
- `style`
- `composition`
- `possible_roles`
- `risks`
- `detected_panels`

### CreativeContext

A reusable packet assembled from references, analyses, user decisions, and constraints. It supports discussion, image generation, video generation, and revisions.

Key attributes:

- `context_id`
- `brand_id`
- `conversation_id`
- `reference_ids`
- `source_summary`
- `creative_decisions`
- `constraints`
- `production_candidates`

### CreativeDecision

A user-confirmed or CMO-proposed decision captured during discussion.

Examples:

- “Use this image as mood only, not exact character.”
- “The colored image should define the final scene only.”
- “Apply the gold color #D4A800.”

### StoryboardSpec

A provider-neutral scene map created before video generation.

Key attributes:

- `storyboard_id`
- `source_reference_ids`
- `scene_count`
- `scenes`
- `assumptions`
- `status`

### VideoSpec

Canonical BOS-owned video production recipe.

Key attributes:

- `spec_id`
- `version`
- `format`
- `creative_direction`
- `source_references`
- `scenes`
- `audio`
- `cta`
- `constraints`

### ImageSpec

Canonical BOS-owned image generation recipe.

Key attributes:

- `spec_id`
- `version`
- `objective`
- `references`
- `prompt_components`
- `constraints`

### SpecPatch / ReferencePatch

A structured change requested through CMO discussion.

Key attributes:

- `patch_id`
- `target_type`
- `target_id`
- `from_version`
- `op`
- `path`
- `value`
- `reason`

---

## Proposed `chat_references` Table

```text
chat_references
- id uuid primary key
- workspace_id uuid not null
- brand_id uuid null
- conversation_id text null
- campaign_id uuid null

- kind text not null
- source text not null
- title text null
- notes text null
- mime_type text null

- drive_file_id text null
- drive_file_name text null
- drive_web_view_link text null
- thumbnail_link text null

- storage_url text null
- sha256 text null
- metadata_json jsonb null

- text_excerpt text null
- extraction_status text not null
- extraction_error text null
- extracted_chars int null
- extraction_json jsonb null
- variables_json jsonb null

- created_at timestamptz not null
- updated_at timestamptz not null
```

This table stores the original extracted reference. The in-conversation patched working copy may initially live client-side and be resent with each chat turn.

---

## Proposed Patch Directive

CMO hidden directive:

```text
PATCH_REFERENCE: {
  "reference_id": "ref_123",
  "op": "replace",
  "path": "$.brand_brief.visual_design.primary_colors.body_gold.hex",
  "value": "#D4A800",
  "reason": "User requested body_gold color update"
}
```

Backend behavior:

1. Parse directive.
2. Validate shape.
3. Strip from visible text.
4. Emit structured frontend event:

```json
{
  "type": "reference_patch",
  "patch": {
    "reference_id": "ref_123",
    "op": "replace",
    "path": "$.brand_brief.visual_design.primary_colors.body_gold.hex",
    "value": "#D4A800",
    "reason": "User requested body_gold color update"
  }
}
```

Frontend behavior:

1. Apply patch to local `ChatReference.extraction_json`.
2. Recompute variables.
3. Keep patched working copy in conversation state.
4. Include patched reference in the next `/chat` call.

---

## Business Rules

- **BR-001**: Uploading a reference does not imply generation intent.
- **BR-002**: CMO discussion can produce reusable creative decisions without dispatching a specialist.
- **BR-003**: Specialist generation must consume structured context/specs, not only chat transcripts.
- **BR-004**: Provider-specific JSON is an execution artifact, not the editable business source of truth.
- **BR-005**: Black-and-white storyboard images default to composition/storyboard role, not final style role.
- **BR-006**: Colored final-shot references default to final-shot/color/lighting role, not global style role, unless user confirms otherwise.
- **BR-007**: The system must ask for clarification when a requested patch cannot be mapped to a unique variable, reference, or scene.
- **BR-008**: The system must not claim to have read or understood a failed extraction.
- **BR-009**: Human approval is required before generation when the system has inferred scene order or roles from ambiguous storyboard references.

---

## Edge Cases

- A document fails extraction: CMO must say the file could not be read and cannot rely on its content.
- An image contains multiple panels but panel detection is uncertain: CMO should present assumptions and ask the user to confirm.
- The user says “change the gold” but multiple gold variables exist: CMO must ask which one or present candidates.
- The user wants video generation immediately from ambiguous references: system may draft assumptions but should request confirmation before costly generation.
- A reference was patched locally but the server still has the original DB row: the current chat turn must prefer the client-sent working copy for that conversation.
- A user edits scene 7 after scenes were reordered: patch must target stable `scene_id`, not visible order alone.
- The provider cannot accept image references directly: adapter must convert references to supported prompt/context form while preserving audit trail.
- The user wants the colored final image applied globally: system should patch creative direction explicitly rather than silently changing all scenes.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of uploaded/selected references used in CMO chat have stable IDs before the next user turn.
- **SC-002**: 95%+ of valid JSON document references expose editable scalar variables after upload-time extraction.
- **SC-003**: A user can upload a concept doc, 4 storyboard images, and 1 final-shot image and receive a reviewable 16-scene storyboard plan without triggering video generation.
- **SC-004**: A user can request a variable edit such as “change body_gold hex to #D4A800” and receive a structured patch event without the directive leaking into visible chat.
- **SC-005**: Image generation and video generation can both consume the same uploaded reference IDs and creative decisions.
- **SC-006**: Video revisions target canonical spec fields or stable scene IDs in 100% of patchable revision cases.
- **SC-007**: No generation provider request is made until user intent clearly indicates production, not discussion.

---

## Non-Goals for MVP

- Persisting every in-chat patch back to the server immediately.
- Advanced mask-based video editing.
- Guaranteed automatic panel detection for every storyboard layout.
- Full scene-level video regeneration and stitching.
- Provider-specific optimization for every video model.
- Public asset library UX beyond chat references.
- Automatic publishing to YouTube/Facebook.

---

## Assumptions

- Existing CMO Chat remains the operator-facing surface.
- PostgreSQL, SQLAlchemy, and Alembic are required for schema changes.
- Existing `attachment_context.py` behavior can be evolved into upload-time extraction.
- Existing `ChatReference` DTO can be extended with `id` and `variables`.
- Existing media generation modules will eventually be adapted to consume canonical specs.
- For MVP, frontend-local patched references are acceptable as the conversation working copy.
- Server persistence stores original extraction unless/until an explicit save/apply endpoint is added.

---

## Open Questions

1. Should `conversation_id` become a first-class table/entity, or should MVP use the existing chat session/local frontend identifier?
2. Should image analysis be stored directly on `chat_references.metadata_json` for MVP, or split into a `reference_analyses` table immediately?
3. Should `CreativeContext` be persisted as its own table in MVP, or assembled per turn from selected references and client-sent working copies?
4. Which provider should be the first canonical `VideoSpec` adapter target: BytePlus Seedance, Gemini Veo, or generic HTTP?
5. What UI should review the `StoryboardSpec`: chat card, artifact detail page, or a dedicated storyboard editor?
