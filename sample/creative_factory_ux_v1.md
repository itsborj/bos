# Creative Factory User Experience v1

**Status:** Documented  
**Date:** 2026-05-26  
**Version:** 1.0  

## Overview

The Creative Factory transforms complex creative production into a streamlined, conversation-driven experience. Business leaders commission work through natural language, while specialists execute behind the scenes. Final outputs are reviewed as curated Creative Bundles, separating creative production from channel distribution.

## User Experience Flow

### 1. Setup Phase (Admin Interface)

**Location:** Admin → Specialists

**What the user sees:**
- Separate cards for each specialist capability:
  - Creative Factory (orchestrator)
  - Image Generation (media.image)
  - Video Generation (media.video)
  - Render / Stitch (composition)
  - Google Drive (asset library)

**Each card displays:**
- Status (connected/disconnected/needs setup)
- Provider name and version
- Credential configuration status
- Performance metrics (latency, last run)
- Error logs if any
- Setup/Connect buttons where needed

**Provider configuration:**
- **Image Generation:** Choose from OpenAI gpt-image-1, Stability AI, Ideogram, Flux (OpenRouter)
- **Video Generation:** Choose from Runway Gen-4, Kling, Hailuo, or skip (image-only campaigns)
- **Render/Stitch:** Choose from local FFmpeg (default), Shotstack API, or Creatomate API
- **Google Drive:** OAuth connection with folder selection

**Setup blockers:**
- If any required provider is missing, Stream shows a clear setup blocker before job creation
- Error messages guide users to complete configuration first

### 2. Natural Conversation (CMO Interface)

**User input:** "Make a creative bundle for Klaroha's launch"

**CMO response:** 
"I'll produce a reviewable creative bundle. Image, video, and render work will run as separate specialist steps."

**Key UX principles:**
- No technical jargon in conversation
- No "Run" buttons or UI controls
- Chat feels like directing a creative director
- Brief confirmation of commission sets expectations
- No final assets pasted into chat

### 3. Job Creation (Stream Interface)

**Stream card appears:** "Creative job started"

**Card contents:**
- Brand context (Klaroha)
- Objective (Product launch creative bundle)
- Planned outputs: 
  - Hero image plates
  - Shortform video (15-30s)
  - Social post creative variants
  - Email banner assets
  - Brand compliance status
- Job ID for tracking
- Quick status overview (queued/running/completed)

**User experience:**
- No spinner-lock in chat
- Immediate return to conversation
- Job runs asynchronously in background
- Progress updates appear in Stream

### 4. Specialist Execution (Behind the Scenes)

**Creative Factory orchestrates specialist plugins:**

**Image Generation (media.image.generate):**
- Generates image plates from creative brief
- Uploads results to Google Drive
- Records metadata in creative_assets table
- Auto-validates against brand compliance rules
- Outputs: image_asset with metadata, no base64 payloads

**Video Generation (media.video.generate):**
- Generates video content from creative direction
- Supports multiple aspect ratios (9:16, 16:9, 1:1, 4:5)
- Uploads results to Google Drive
- Records performance metrics (latency, cost)
- Outputs: video_asset with metadata

**Render/Stitch (media.render.stitch):**
- Assembles CompositionSpec from approved primitives
- Applies brand styling and safe zones
- Executes FFmpeg/Shotstack/Creatomate rendering
- Uploads final assets to Drive
- Outputs: export_package per render target

**Quality Assurance:**
- Automated brand compliance checks
- Performance optimization per plugin type
- Error isolation (single plugin failures don't stop entire job)

### 5. Progress Visibility (Stream Updates)

**Stream shows progress cards:**
- "Generating image plates" (with progress indicator)
- "Rendering shortform video" (with estimated time)
- "Uploading assets to Drive" (with file count)
- "Curating creative bundle" (with selection criteria)

**What users DON'T see:**
- Raw primitive outputs
- Individual provider error details
- System implementation details
- Large base64 payloads
- Technical execution logs

### 6. Creative Bundle Output (Final Review)

**Stream card:** Single review surface for the complete bundle

**Card contents:**
- Hero image preview (with metadata)
- Shortform video preview (playable inline)
- Caption/copy variants (expandable sections)
- Banner/social variants (grid preview)
- Drive links for all assets
- Brand compliance status
- Performance metrics (generation time, file sizes)
- Self-check notes and quality indicators

**Available actions:**
- [Approve Bundle] → Saves assets, enables publishing
- [Request Revision] → Opens revision thread
- [Dismiss] → Archives the bundle
- [Export] → Downloads all assets
- [Send to Channel] → Opens channel selection

### 7. Revision Workflow

**User:** "Make the video more direct and less polished"

**CMO intelligence:**
- Routes to appropriate specialist based on issue type
- Visual issues → image/video plugin
- Assembly issues → render plugin  
- Concept issues → Creative Factory/Concept Director
- User doesn't need to know which plugin is called

**Revision process:**
- Creates linked revision job
- Preserves original bundle reference
- Shows revision progress in Stream
- Presents revised bundle for approval

### 8. Approval and Learning

**Asset management:**
- Approved assets become reusable Drive assets
- Metadata includes creation context, performance, usage rights
- Asset library organized by campaign and type

**Learning system:**
- Records approved concepts
- Tracks rejected variants with reasons
- Monitors provider performance (latency, cost, quality)
- Captures quality notes and compliance issues
- Future creative jobs improve from this memory

### 9. Publishing Separation

**User:** "Post this to Facebook"

**CMO dispatches:**
- Channel plugin with approved Drive asset reference
- Platform-specific execution (Meta API integration)
- Approval-gated publishing workflow

**Distribution process:**
- Channel plugin receives asset metadata
- Applies platform-specific formatting
- Handles platform API requirements
- Returns publishing confirmation with post ID/URL

## Performance Optimizations

### Asset Loading Strategy
- **Bulk loads:** Use `include_assets=false` to omit large base64 payloads
- **Review items:** Load full assets only when explicitly needed for approval
- **Metadata-first:** Stream shows asset previews, not raw data
- **Drive references:** Assets stored externally, metadata in database

### Plugin Performance
- **Independent optimization:** Each plugin can be optimized separately
- **Parallel execution:** Specialists run concurrently when possible
- **Error isolation:** Single plugin failures don't stop entire job
- **Metrics tracking:** Performance data helps identify bottlenecks

### User Experience Performance
- **Immediate feedback:** Job creation returns immediately
- **Progress updates:** Stream shows progress without blocking
- **Lightweight interfaces:** No large payloads in initial load
- **Efficient asset handling:** Drive references instead of inline data

## Allowed vs Forbidden Outcomes

### Allowed ✅
- User commissions work through natural conversation
- Creative Factory orchestrates specialist plugins
- Stream shows curated Creative Bundle for approval
- Assets stored in Drive with metadata
- Publishing is approval-gated and channel-owned
- Performance optimizations per plugin type
- Error isolation and graceful degradation
- Revision workflows for iterative improvement

### Forbidden ❌
- Giant base64 image payloads slowing Stream
- Hidden video rendering inside Creative Factory
- Channel-specific publish buttons hardwired into creative generation
- CMO pasting final assets as chat text
- Failed providers buried inside generic creative errors
- Creative Factory directly generating or rendering content
- Raw primitive outputs shown to users
- System implementation details in user interface
- Blocking UI waits for long-running processes

## Intended User Feeling

### Core Experience
- **"I say what I want, and it happens"**
- **"BOS commissions the right specialists automatically"**
- **"One clean decision surface for the final bundle"**
- **"Assets are safely stored and reusable"**
- **"Publishing is controlled and channel-appropriate"**

### Emotional Journey
1. **Simplicity:** No technical knowledge required
2. **Confidence:** Clear progress indicators and expectations
3. **Control:** Final approval on curated outputs
4. **Efficiency:** No waiting or manual coordination
5. **Scale:** Handles complex production without complexity
6. **Learning:** System improves from user decisions

### Pain Points Addressed
- **No more creative bottlenecks** - specialists handle the work
- **No more technical overwhelm** - conversation drives everything
- **No more version confusion** - single source of truth
- **No more publishing friction** - channel plugins handle distribution
- **No more performance issues** - optimized plugin execution

## Technical Implementation Notes

### Plugin Boundaries
- **Creative Factory:** Orchestrator only - builds requests, routes to specialists
- **Media Plugins:** Generators only - image/video production
- **Render Plugins:** Compositors only - assembly and final output
- **Channel Plugins:** Distributors only - platform-specific publishing

### Data Flow
1. User intent → CMO conversation
2. CMO → Creative Factory job creation
3. Creative Factory → Specialist plugin dispatch
4. Specialists → Asset generation + Drive upload
5. Creative Factory → Bundle assembly
6. Stream → User review and approval
7. Channel plugins → Publishing (if approved)

### Performance Monitoring
- Track each plugin's performance independently
- Monitor asset loading times and sizes
- Measure user decision time in approval workflow
- Track revision rates and success rates
- Monitor Drive storage efficiency

## Future Enhancements

### Phase 2 Additions
- Per-brand provider overrides in Admin
- Batch production (multiple variants from one template)
- Advanced analytics and performance insights
- Creative asset search and discovery
- Integration with third-party creative tools

### User Experience Improvements
- Richer previews and interactive editing
- Performance metrics dashboard
- Creative asset library browser
- Publishing analytics and optimization
- Collaboration features for team workflows

---

This UX documentation provides the foundation for the Creative Factory user experience, ensuring a seamless workflow from conversation to approval to publishing.