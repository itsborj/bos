# Creative Factory Plugin Notes v2

**Status:** Updated with Architecture Documentation & Performance Strategy  
**Date:** 2026-05-26  
**Version:** 2.0  

## Plugin Architecture Overview

The Creative Factory plugin acts as an orchestrator only, coordinating specialist media plugins for image/video generation and rendering. This separation enables independent optimization of each plugin type.

**Plugin Boundaries:**
- **Creative Factory:** Orchestrator - builds requests, routes to specialists
- **Media Image:** Generator - creates image assets
- **Media Video:** Generator - creates video assets (future)
- **Media Render:** Compositor - assembles final outputs
- **Google Drive:** Asset library - stores and retrieves assets
- **Channel Plugins:** Distributors - publish to platforms

## Performance Strategy

### Asset Loading Optimization

**Problem:** Stream slow-load due to large base64 image payloads
**Solution:** Use `include_assets=false` for bulk operations, full assets only for review

**Implementation:**
- `GET /runs?include_preview=true` returns compact preview blocks in one list response
- `GET /runs/{run_id}?include_assets=false` strips large inline payloads when detail hydration is needed
- `asset_omitted: true` marker indicates stripped fields
- Stream fetches full run detail/assets only for pending-review approval surfaces

**Results:**
- 99.7% payload reduction for bulk operations
- 20MB+ base64 bursts eliminated
- Responsive Stream interface maintained

### Plugin-Specific Optimizations

**Media Image Plugin:**
- Concurrent image generation for multiple variants
- Drive-backed storage instead of base64 in database
- Optimized prompts and provider selection
- Support for multiple image providers (OpenAI, Stability, Ideogram)

**Media Video Plugin (Future):**
- Batch processing for multiple video variants
- Aspect ratio optimization
- Provider-specific performance tuning
- Drive storage with metadata tracking

**Media Render Plugin (Future):**
- Efficient composition execution
- FFmpeg/Shotstack/Creatomate optimization
- Render target caching
- Parallel processing for multiple outputs

## User Experience Flow

### Setup Phase
**Admin → Specialists**
- Provider configuration for each plugin type
- Status indicators and performance metrics
- Setup blockers for missing providers
- Brand-specific OAuth connections for Drive

### Conversation Phase
**User → CMO → Creative Factory**
- Natural language commission of creative work
- CMO routes to Creative Factory orchestrator
- Immediate job creation without blocking
- Progress updates in Stream

### Production Phase
**Creative Factory → Specialist Plugins**
- Parallel execution of media generators
- Asset upload to Google Drive
- Metadata tracking in creative_assets table
- Quality compliance checks
- Error isolation (single failures don't stop entire job)

### Review Phase
**Stream → Creative Bundle**
- Single review surface for complete bundle
- Asset previews with metadata
- Approval/revision/dismiss actions
- Publishing to channel plugins

## Performance Monitoring

### Key Metrics
- **Asset Loading:** Time and size for bulk vs individual operations
- **Plugin Performance:** Generation time, success rate, error rates
- **User Experience:** Decision time in approval workflow
- **System Health:** Memory usage, response times, error rates

### Optimization Targets
- **Bulk Operations:** Sub-second response times for run listings
- **Asset Generation:** Optimize prompts and provider selection
- **Storage Efficiency:** Drive storage with metadata-only database
- **Parallel Processing:** Concurrent execution where possible

## Error Handling Strategy

### Isolation Approach
- **Plugin Errors:** Single plugin failures don't stop entire job
- **Graceful Degradation:** Continue with available specialists
- **User Communication:** Clear error messages without technical details
- **Retry Logic:** Automatic retry for transient failures

### Common Error Patterns
- **Provider Failures:** Fallback to alternative providers
- **Storage Errors:** Local caching with retry mechanisms
- **Network Issues:** Request queuing and retry
- **Validation Errors:** Clear user guidance for fixes

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

## Validation and Testing

### Performance Testing
- **Load Testing:** Simulate high-volume creative production
- **Asset Loading Test:** Verify bulk vs individual performance
- **Plugin Isolation Test:** Confirm error boundaries
- **User Experience Test:** End-to-end workflow validation

### Regression Prevention
- **Automated Monitoring:** Track performance metrics continuously
- **Error Tracking:** Monitor plugin error rates and patterns
- **User Feedback:** Collect and analyze user experience data
- **A/B Testing:** Test optimizations with real user workflows

## Invariants

- **Every module MUST declare `platform_hint`.** `registry.list_all()` calls `module_info()` on every registered module at app startup, and `module_base.ModuleBase.module_info()` reads `self.platform_hint` (a `ClassVar[str]` with no default). A module missing it raises `AttributeError` and crashes the entire app on startup — not just the plugin. Same applies to `id`, `vertical`, `capability`. `template` is only read at execution (`build_prompt`), so modules that override `execute_tool_result` and build dicts directly do not strictly need it to boot — but they still need `platform_hint`.

- **BOS generates nothing natively.** Every module here builds a request for a third-party provider (image gen, video gen, render/stitch) and captures the result. No module performs generation or rendering in-process beyond local FFmpeg invocation. See CREATIVE_SUPPLY_CHAIN.md → BOS Role in This Pipeline.

- **AI content and brand assets are separate files.** They are never merged inside an AI provider. The CompositionSpec layers them; the render provider stitches them. Do not build a path that sends a brand logo into an image-generation prompt.

## Fixed bugs (pattern → fix)

- **2026-05-23 — App startup crash: `'CreativeBlueprintAssembleModule' object has no attribute 'platform_hint'`.** The three scaffolded modules (`pack/generate`, `primitive/generate`, `blueprint/assemble`) were created without `platform_hint`. Latent because the app only re-scans modules on (re)start/reload; surfaced when an unrelated file edit triggered a watchfiles reload. Fix: added `platform_hint` to all three. Lesson: any new module class needs the full required ClassVar set before the next reload, or the whole app goes down.

- **2026-05-26 — Stream performance regression:** Fixed large base64 image payloads by implementing `include_assets=false` parameter and bounded concurrency in Stream.tsx. See performance strategy above for details.
- **2026-05-27 — Stream metadata-first loading:** Added `GET /runs?include_preview=true` and updated Stream to render list preview metadata first. CMO split-screen uses the exact same Stream component as `/stream`; heavy artifact detail/assets hydrate lazily, one card at a time as cards enter the viewport, and additional run pages load on scroll.

## creative.post.image (CMO-dispatchable, generate + store)

- **What it does:** CMO chat → generate a Meta post visual creative → store in the brand's Drive under `Creative Assets/Meta Posts/`. Does NOT publish. `allowed_from_chat: true`, in the capability manifest.
- **Image generation is declarative, not hardcoded:** the module sets `requires_generated_image = True` (a `ModuleBase` ClassVar). `runs.py` fires the `media.image.generate` hook for any module with that flag OR an `image_prompt` — so the CMO does NOT have to pass `image_prompt` (media.image builds one from the brand brief as fallback). Generic mechanism; no capability id hardcoded in core.
- **Drive token + root injection:** the plugin declares `requires_social_connection: ["google_drive"]`, so `inject_channel_credentials` injects the google_drive `page_token` AND (new) the `drive_root_folder_id`/`drive_root_name` from the connection's `token_meta_json`. The module loads `drive_client` from `/app/plugins/google-drive/drive_client.py` (absolute path — cross-plugin) and uploads under the picked root.
- **Validated 2026-05-24:** live `/chat` "make an image for a Facebook post…" with brand active → dispatched creative.post.image → image generated from brand brief → stored to Drive (`meta_post_*.png`). Two files confirmed in the operator's real `Creative Assets/Meta Posts/`.
- **Gotcha:** if `image_prompt` absent AND `requires_generated_image` False → no image → fails. The flag is what makes chat-without-explicit-prompt work.
- **Publish handoff (2026-05-24):** `creative_post_asset` block now declares `action_modules: {"publish": "marketing.channel.meta.posts.publish"}` and includes both `caption` and `message` fields (same value) plus `drive_file_mime`. The Stream "Approve & Publish" button fires `POST /runs/{id}/actions/publish` → action endpoint reads `drive_file_id` + `message` from the block and dispatches the publish module. CMO MUST NOT re-dispatch `posts.publish` from chat for image posts — it doesn't know the drive_file_id. The SKILL.md body instructs the CMO to tell the operator to click the artifact button.

## Local backlog

- The three scaffolded modules (`pack/generate`, `primitive/generate`, `blueprint/assemble`) are stubs from an earlier session. They will be rebuilt in Phase B against the locked architecture: `pack/generate` creates a `creative_job` and returns immediately (async), `primitive/generate` routes to the configured image provider and writes `creative_assets`, `blueprint/assemble` emits a full CompositionSpec JSON (not the current slot-mapping dict).
- `channel.json` `capability_ids` will gain `creative.render.*` capabilities as Phase C lands.
- **New:** Implement media plugin separation - move image generation to media-image plugin, video generation to media-video plugin, rendering to media-render plugin.
- **New:** Implement performance optimizations - asset loading strategy, plugin-specific optimizations, error isolation.
- **New:** Implement user experience flow - setup, conversation, production, review phases.

## If This Regresses

Check these first:

1. **Browser Network Tab:** Stream should call `/api/runs?include_preview=true` for feed load/polling, not detail-hydrate every recent run
2. **Response Bodies:** Preview responses should not contain `image_data_b64`
3. **Asset Markers:** `asset_omitted: true` should appear on stripped blocks
4. **Lazy Hydration:** `/api/runs/<id>?include_assets=true` should happen as cards enter view or are opened, not as a blocking first-load batch
5. **CMO Split Screen:** `/cmo` should render the same Stream component as `/stream`, not a divergent artifact-only feed
6. **Plugin Boundaries:** Creative Factory should not directly generate assets
7. **Performance Metrics:** Monitor asset loading times and plugin performance

## Next Iteration Ideas

- **Dedicated Asset Endpoint:** `GET /runs/{run_id}/asset` with Drive-backed signed URLs
- **Default Drive Storage:** Store generated assets as Drive files with metadata-only database
- **Virtualized Stream:** Cards virtualization for large feed sizes
- **Plugin Hot-swapping:** Runtime plugin updates without system restart
- **Advanced Caching:** Multi-level caching for frequently accessed assets

---

*This documentation is part of the Creative Factory plugin architecture. For complete system architecture, see `CREATIVE_SUPPLY_CHAIN.md`.*