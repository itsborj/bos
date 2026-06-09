# Meta Publish Wiring Implementation

**Date:** 2026-05-22  
**Status:** ✅ Completed  
**Version:** 3.38 (Meta publish wiring)

## Overview

Completed the Meta publish integration by implementing a plugin-declared action handoff system that separates draft creation from approval-gated publishing through a generic core endpoint.

## Problem Statement

Meta posts/draft artifacts needed approval-gated publish actions that could execute without CMO chat seeing draft text inline or requiring platform-specific routing in the chat router.

## Solution Architecture

### 1. Plugin-Declared Action Metadata

Draft artifacts now declare their publish action capability in the block metadata:

```json
{
  "allowed_actions": ["revise", "dismiss", "approve", "publish"],
  "action_modules": {
    "publish": "marketing.channel.meta.posts.publish"
  }
}
```

### 2. Generic Action Endpoint

Added `POST /runs/{run_id}/actions/{action}` in `api/routers/runs.py` that:
- Approves the source artifact
- Builds an action brief from the persisted block metadata
- Executes the declared module
- Stores the resulting action artifact
- Returns the action run for UI updates

### 3. UI Integration

Updated Stream and Workspace components with:
- **Approve & Publish** button for artifacts with publish actions
- **Approve only** option for artifacts without publish actions
- Action-result preview for `fb_page_post_result` artifacts
- Loading states and error handling

### 4. Architecture Cleanup

Removed the hardcoded Meta publish guard from `api/routers/chat.py`, keeping CMO chat manifest/SKILL-driven without platform-specific routing exceptions.

## Implementation Details

### Backend Changes

- **`api/plugins/meta/capabilities/marketing/channel/meta/posts/draft/module.py`**
  - Added `action_modules.publish` to block metadata
  
- **`api/routers/runs.py`**
  - Added `execute_run_action()` endpoint
  - Added action module resolution helpers
  - Added action brief builders
  - Added action result approval logic

- **`api/plugins/meta/capabilities/marketing/channel/meta/posts/publish/SKILL.md`**
  - Updated guidance about using artifact UI for publish actions

### Frontend Changes

- **`web/src/pages/Stream.tsx`**
  - Added `hasArtifactAction()` helper
  - Added `onActionRun` prop to `StreamArtifactCard`
  - Added publish action controls
  - Added `fb_page_post_result` preview

- **`web/src/components/blocks/ApprovalBundle.tsx`**
  - Added `Approve & Publish` button
  - Added publish loading states
  - Added `fb_page_post_result` renderer

### Documentation Updates

- **`api/plugins/meta/README.md`**
  - Added approved action handoff section
  - Updated routing contract with action_modules example
  - Updated publish SKILL guidance

- **`api/plugins/meta/capabilities/marketing/channel/meta/posts/draft/SKILL.md`**
  - Added action_modules declaration

## Validation

### 2026-06-09 Localhost Retest Note

- Image generation + Drive storage passed locally for Klaroha: `creative.post.image` run `7c9dbea8-27e6-4997-b3b4-7c40156f538d`, Drive file `1up6n28CWzOHuJsvhyxHafUDlJMRqedcS`.
- Localhost Facebook publish failed at Graph API with OAuth code `190`: page token lacked required page impersonation permissions.
- Operator context: previous Facebook auth was validated on `staging.klaroha.com`; the Meta app/domain validation is staging-based. Do not use localhost as the final live Facebook proof surface unless the Meta app explicitly allows the exact localhost callback and scopes.
- Next validation should run on `staging.klaroha.com` with fresh Facebook auth for `pages_show_list,pages_read_engagement,pages_manage_posts`, then retry publish from the existing source artifact if available.

### Code Quality
- ✅ Python compilation: `docker compose exec -T api python -m py_compile ...`
- ✅ TypeScript compilation: `cd web && npx tsc -b`
- ✅ Docker build and deployment: `docker compose build web && docker compose up -d web`
- ✅ HTTP endpoint validation: `curl http://localhost:8090/stream` → `200`

### Testing
- ✅ Unit tests for action module resolution
- ✅ Unit tests for action brief building
- ✅ ClickUp backlog sync: updated 1 task, created 1 task

## Next Steps

### Pending
- [!] **Live publish test deferred to staging**: Approve a Meta draft/creative in Stream with **Approve & Publish** and confirm live page result from `staging.klaroha.com`, not localhost.
- [ ] End-to-end test: draft/creative → approve → publish → result → Stream display

### Future Implications

This pattern enables approval-gated actions for other channel plugins:
- Email campaigns with send actions
- Google Ads with publish actions
- Social media with cross-posting actions

## Architecture Benefits

1. **Separation of Concerns**: Draft creation and publishing are separate capabilities
2. **UI-First Execution**: Approval and execution happen through the UI, not chat routing
3. **Generic Core**: Action endpoint works for any plugin-declared action
4. **Manifest-Driven**: No hardcoded platform routing in chat.py
5. **Audit Trail**: All publish actions create result artifacts in Stream

## Files Modified

### Backend
- `api/routers/runs.py` - Action endpoint implementation
- `api/plugins/meta/capabilities/marketing/channel/meta/posts/draft/module.py` - Action metadata
- `api/plugins/meta/capabilities/marketing/channel/meta/posts/publish/SKILL.md` - Updated guidance
- `api/routers/chat.py` - Removed hardcoded Meta guard
- `api/plugins/meta/README.md` - Documentation updates

### Frontend
- `web/src/pages/Stream.tsx` - Publish controls and previews
- `web/src/components/blocks/ApprovalBundle.tsx` - Publish button and states
- `web/src/components/Layout.tsx` - Brand selector (bonus)

### Documentation
- `PROJECT_BRIEF.md` - Version update
- `BACKLOG.md` - Task updates
- `api/plugins/meta/docs/meta-publish-wiring.md` - This document

## Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-22 | Use plugin-declared action_modules instead of hardcoded chat routing | Keeps CMO chat manifest-driven and prevents platform-specific routing violations. Enables generic action execution through UI-approved workflows. |

## Plugin-Specific Notes

This documentation is specific to the Meta plugin and its publish integration. Each plugin will have its own documentation directory under `api/plugins/{plugin-name}/docs/` to maintain separation of concerns and avoid documentation sprawl across the entire codebase.