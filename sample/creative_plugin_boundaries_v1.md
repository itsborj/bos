# Creative Plugin Boundaries v1

**Status:** Documented  
**Date:** 2026-05-26  
**Version:** 1.0  

## Overview

This document defines the plugin architecture boundaries for the Creative Factory ecosystem. The architecture separates concerns to enable independent optimization of each plugin type while maintaining a unified creative production workflow.

## Plugin Architecture

### 1. Creative Factory Plugin (Orchestrator)

**Location:** `api/plugins/creative-factory/`

**Role:** Orchestrator only - builds requests and routes to specialists

**Responsibilities:**
- Parse creative intent from user conversation
- Create creative jobs with clear requirements
- Route requests to appropriate specialist plugins
- Coordinate parallel execution of specialists
- Aggregate results into Creative Bundles
- Handle job lifecycle (queued → running → completed/failed)

**Does NOT do:**
- Direct image generation or rendering
- Direct video generation or rendering
- Direct content creation
- Asset storage (delegates to Google Drive plugin)
- Channel publishing (delegates to channel plugins)

**Capabilities:**
- `creative.pack.generate` - Create production job
- `creative.primitive.generate` - Request specialist work
- `creative.blueprint.assemble` - Aggregate assets into composition
- `creative.post.image` - Legacy capability (being refactored)

### 2. Media Image Plugin (Generator)

**Location:** `api/plugins/media-image/`

**Role:** Image generation specialist

**Responsibilities:**
- Generate image assets from creative prompts
- Support multiple image providers (OpenAI, Stability, Ideogram, etc.)
- Upload generated images to Google Drive
- Provide image metadata (dimensions, format, size)
- Apply brand compliance checks
- Optimize image generation performance

**Output Contract:**
```json
{
  "type": "image_asset",
  "status": "succeeded",
  "mime_type": "image/png",
  "width": 1024,
  "height": 1024,
  "prompt": "Brand-safe hero image for Klaroha",
  "byte_size": 981234,
  "asset_omitted": true,
  "allowed_actions": ["use", "regenerate", "dismiss"]
}
```

**Performance Optimizations:**
- Support `include_assets=false` for bulk operations
- Store only metadata in database, not base64 payloads
- Drive-backed asset storage
- Concurrent image generation for multiple variants

### 3. Media Video Plugin (Generator)

**Location:** `api/plugins/media-video/`

**Role:** Video generation specialist

**Responsibilities:**
- Generate video content from creative briefs
- Support multiple video providers (Runway, Kling, etc.)
- Handle aspect ratio and format variations
- Upload generated videos to Google Drive
- Provide video metadata and performance metrics

**Capabilities:**
- `media.video.generate` - Stable video generation capability
- `creative.shortform.video` - Legacy alias for existing CMO dispatches

### 4. Media Render Plugin (Compositor)

**Location:** `api/plugins/media-render/` (to be created)

**Role:** Composition and rendering specialist

**Responsibilities:**
- Execute CompositionSpec JSON instructions
- Apply FFmpeg/Shotstack/Creatomate rendering
- Composite AI content + brand assets + text layers
- Handle different render targets (dimensions, formats)
- Upload final assets to Google Drive

**Input:** CompositionSpec JSON
**Output:** ExportPackage with rendered assets

### 5. Google Drive Plugin (Asset Library)

**Location:** `api/plugins/google-drive/`

**Role:** Asset storage and retrieval

**Responsibilities:**
- OAuth connection per brand
- Folder structure management
- Asset upload/download
- Metadata tracking
- Asset lifecycle management

### 6. Channel Plugins (Distributors)

**Location:** `api/plugins/{channel}/`

**Role:** Platform-specific publishing

**Responsibilities:**
- Receive approved creative assets
- Apply platform-specific formatting
- Handle platform API requirements
- Execute publishing actions
- Return publishing confirmation

## Data Flow

### 1. User Conversation → Job Creation
```
User: "Make a creative bundle"
CMO: Routes to Creative Factory
Creative Factory: Creates creative_job record
Returns: "Creative job started" artifact
```

### 2. Job → Specialist Dispatch
```
Creative Factory: Reads job requirements
Dispatches to media.image.generate
Dispatches to media.video.generate (if needed)
Dispatches to media.render.stitch
```

### 3. Specialists → Asset Generation
```
media.image.generate: Creates image assets in Drive
media.video.generate: Creates video assets in Drive
media.render.stitch: Creates final compositions
All: Update creative_assets with metadata
```

### 4. Creative Factory → Bundle Assembly
```
Creative Factory: Aggregates approved assets
Creates CompositionSpec
Routes to render plugin
Assembles Creative Bundle artifact
```

### 5. User Review → Publishing
```
User: Approves Creative Bundle
CMO: Dispatches to channel plugin
Channel Plugin: Publishes to platform
Returns: Publishing confirmation
```

## Allowed vs Forbidden Outcomes

### Creative Factory Plugin ✅
- **Allowed:**
  - Build requests from user conversation
  - Route to specialist plugins
  - Coordinate parallel execution
  - Aggregate results into bundles
  - Handle job lifecycle
  - Show progress in Stream
- **Forbidden:**
  - Direct image/video generation
  - Asset storage (delegates to Drive)
  - Channel publishing (delegates to channels)
  - Large base64 payload handling

### Media Plugins ✅
- **Allowed:**
  - Generate images/videos from prompts
  - Upload assets to Drive
  - Provide metadata and performance metrics
  - Support `include_assets=false` for bulk operations
  - Apply brand compliance checks
- **Forbidden:**
  - Orchestrate other plugins
  - Handle channel publishing
  - Store base64 payloads in database
  - Direct composition/rendering

### Channel Plugins ✅
- **Allowed:**
  - Receive approved creative assets
  - Apply platform-specific formatting
  - Execute publishing actions
  - Return platform confirmations
- **Forbidden:**
  - Generate creative content
  - Orchestrate production workflow
  - Access other plugins' internals

### Google Drive Plugin ✅
- **Allowed:**
  - Handle OAuth connections per brand
  - Manage folder structures
  - Upload/download assets
  - Track asset metadata
- **Forbidden:**
  - Generate or modify content
  - Orchestrate creative workflow
  - Access plugin internals

## Performance Optimizations

### Asset Loading Strategy
- **Bulk Operations:** Use `include_assets=false` to omit large payloads
- **Review Items:** Load full assets only when explicitly needed
- **Drive References:** Store assets externally, metadata in database
- **Concurrent Processing:** Specialists run in parallel when possible

### Plugin-Specific Optimizations
- **Image Plugin:** Optimize generation prompts, concurrent requests
- **Video Plugin:** Batch processing, aspect ratio optimization
- **Render Plugin:** Efficient composition execution
- **Drive Plugin:** Minimize upload/download operations

### Database Optimizations
- **Metadata-First:** Stream shows previews, not raw data
- **Asset Omission:** Large fields stripped in bulk operations
- **Indexing:** Optimized queries for asset discovery
- **Pagination:** Efficient listing of large asset libraries

## Error Handling

### Isolation Strategy
- **Plugin Errors:** Single plugin failures don't stop entire job
- **Graceful Degradation:** Continue with available specialists
- **User Communication:** Clear error messages without technical details
- **Retry Logic:** Automatic retry for transient failures

### Error Boundaries
- **Creative Factory:** Job-level error handling and user communication
- **Media Plugins:** Asset generation errors with fallback options
- **Channel Plugins:** Publishing errors with retry mechanisms
- **Drive Plugin:** Storage errors with local caching

## Security Considerations

### Plugin Isolation
- **No Direct Access:** Plugins cannot access other plugins' internals
- **Credential Injection:** Credentials passed via `brief["_channel_credentials"]`
- **Database Access:** Plugins read only from provided context
- **Filesystem Access:** Restricted to temporary directories and Drive

### Data Privacy
- **Asset Storage:** External Drive storage, not database
- **Metadata Only:** Database contains only metadata, not sensitive content
- **Brand Isolation:** Per-brand OAuth and asset storage
- **Audit Trail:** Complete execution history for compliance

## Future Enhancements

### Phase 2 Additions
- **Per-Brand Provider Configuration:** Allow different providers per brand
- **Batch Production:** Multiple variants from single template
- **Advanced Analytics:** Performance metrics across all plugins
- **Creative Asset Search:** Discovery and reuse of existing assets

### Plugin Ecosystem
- **Additional Media Types:** Audio, 3D, AR/VR generation
- **Enhanced Rendering:** Advanced composition and effects
- **Integration Partners:** Third-party creative tools
- **AI Enhancement:** Upscaling, style transfer, enhancement

### User Experience Improvements
- **Rich Previews:** Interactive asset editing and preview
- **Performance Dashboard:** Real-time metrics and optimization
- **Collaboration:** Team workflows and approval processes
- **Learning System:** AI-powered creative optimization

---

This plugin architecture enables independent optimization of each creative production component while maintaining a unified user experience. The separation of concerns allows for scalability, performance improvements, and specialized expertise in each domain.
