# Meta Plugin Architecture Changes

## Facebook Draft Capability Routing Fix (2026-05-22)

### Problem
A request for a Facebook post plus matching visual correctly dispatched `marketing.channel.meta.posts.draft` and `media.image.generate`, but the Facebook draft run failed before producing an artifact:

```text
No healthy model options for this capability and policy
```

### Cause
`posts/draft/module.py` pointed at `capability = "marketing.execute"`. In BOS today, `marketing.execute` is a CMO-facing job label / plugin metadata, not a seeded model-routing capability in the `capabilities` table. Channel draft modules must route through the seeded `marketing.channel` capability.

### Fix
Changed:

```python
capability = "marketing.channel"
```

in `api/plugins/meta/capabilities/marketing/channel/meta/posts/draft/module.py`.

### Validation
- The same CMO prompt now should produce Facebook Draft + Image Generation artifacts, not Campaign Plan.
- Relevant tests passed in the API container:

```bash
docker compose exec -T -e PYTHONPATH=/app api pytest -q \
  tests/test_cmo_artifact_boundary_prompt.py \
  tests/test_artifact_refs.py \
  tests/test_google_ads_skill_routing.py \
  tests/test_email_cmo_skill_routing.py
```

### Architecture Note
This is a module routing metadata fix, not CMO chat routing. Do not add phrase matching to `chat.py` for Facebook or image requests.

---

## Meta Publish Wiring (2026-05-22)

### Problem
Meta posts/draft artifacts needed approval-gated publish actions that could execute without:
- CMO chat seeing draft text inline
- Platform-specific routing in chat.py
- Hardcoded exceptions to manifest-driven dispatch

### Solution
Implemented a plugin-declared action handoff system with three core components:

#### 1. Block Metadata Declaration
```json
{
  "allowed_actions": ["revise", "dismiss", "approve", "publish"],
  "action_modules": {
    "publish": "marketing.channel.meta.posts.publish"
  }
}
```

#### 2. Generic Core Endpoint
- `POST /runs/{run_id}/actions/{action}` in `api/routers/runs.py`
- Approves source artifact → builds action brief → executes declared module → stores result
- Works for any plugin-declared action, not just Meta

#### 3. UI-First Execution
- **Approve & Publish** button in Stream/Workspace
- **Approve only** fallback for artifacts without publish actions
- Action-result preview for published artifacts

### Architecture Benefits

#### Before (Problematic)
- CMO chat needed to paste draft text inline for publish
- Hardcoded platform routing in chat.py
- Draft creation and publishing tightly coupled
- No separation of concerns

#### After (Clean Architecture)
- CMO chat stays manifest/SKILL-driven
- UI manages approval + execution workflows
- Draft creation and publishing decoupled
- Generic action system for all channels
- Audit trail through Stream artifacts

### Future Extensibility

This pattern enables approval-gated actions for:
- Email campaigns with send actions
- Google Ads with publish actions  
- Social media with cross-posting actions
- Any plugin that declares action metadata

### Files Modified

**Backend:**
- `api/routers/runs.py` - Action endpoint implementation
- `api/plugins/meta/capabilities/marketing/channel/meta/posts/draft/module.py` - Action metadata
- `api/routers/chat.py` - Removed hardcoded guard

**Frontend:**
- `web/src/pages/Stream.tsx` - Publish controls
- `web/src/components/blocks/ApprovalBundle.tsx` - Publish button
- `web/src/components/Layout.tsx` - Brand selector

**Plugin Documentation:**
- `docs/meta-publish-wiring.md` - Complete implementation guide
- `docs/api-endpoints.md` - Endpoint documentation
- `docs/architecture-changes.md` - This summary

### Validation
- ✅ Python compilation
- ✅ TypeScript compilation  
- ✅ Docker build and deployment
- ✅ ClickUp backlog sync
- ❌ Live publish test (pending user approval for external mutation)

### Plugin-Specific Notes

This documentation is specific to the Meta plugin and its publish integration. Each plugin will have its own documentation directory under `api/plugins/{plugin-name}/docs/` to maintain separation of concerns and avoid documentation sprawl across the entire codebase.