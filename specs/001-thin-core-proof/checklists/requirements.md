# Specification Quality Checklist: Plugin Host MVP — WordPress / VS Code Model

**Purpose**: Validate that Spec Kit matches `api/plugins/PLUGIN_ARCHITECTURE_RECOMMENDATION.md`  
**Created**: 2026-06-08  
**Updated**: 2026-06-08  
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Scope is the plugin-host MVP, not the full thin-core rewrite
- [x] WordPress / VS Code model is explicit
- [x] Uninstalled plugins are invisible
- [x] Installed does not mean active
- [x] Admin/Specialists setup is separated from CMO dispatch
- [x] Deferred items are explicitly listed

## Requirement Completeness

- [x] D1 external plugin root acceptance is defined
- [x] D2 installed plugins API acceptance is defined
- [x] D3 quarantine acceptance is defined
- [x] D4 per-brand activation acceptance is defined
- [x] D5 CMO manifest activation filtering acceptance is defined
- [x] D6 installed-only Specialists UI acceptance is defined
- [x] D7 credential injection boundary acceptance is defined
- [x] D8 lean generic OAuth acceptance is defined

## Scope Guardrails

- [x] Marketplace is deferred
- [x] Full lockfile/source hashes are deferred
- [x] Hook system is deferred
- [x] Chat.py 7-step rewrite is deferred
- [x] SDK ABI adapters are deferred
- [x] Plugin migrations/hot reload/subprocess sandbox are deferred
- [x] Full migration of existing plugins is deferred

## Feature Readiness

- [x] Spec is ready for implementation against D1–D8 only
- [x] Plan, data model, tasks, and quickstart should align with the MVP deliverables
- [x] Any current code that conflicts with this checklist is treated as suspect and must be corrected

## Violations Audit (2026-06-09)

Code audit of current implementation against spec.md § Architecture Tests. Items marked `[FAIL]` are active violations that must be resolved before merge.

- [FAIL] `plugin_loader.py:503–586` — `inject_channel_credentials` has `google_drive`, ClickUp, and image/video platform-specific branches (V1)
- [FAIL] `routers/plugins.py:50–119` — `_MEDIA_PROVIDER_OPTIONS` hardcodes plugin provider catalogs in core (V2)
- [FAIL] `routers/plugins.py:295–318` — `/resolve-workspaces` endpoint makes ClickUp-specific HTTP calls from core (V3)
- [FAIL] `routers/chat.py:555–563` — `_CHANNEL_DISPLAY` hardcodes platform display names in core (V4)
- [FAIL] `routers/chat.py:1209` — `@council` dispatches via direct capability import, bypassing manifest (V5)
- [FAIL] `capabilities/workspace/council/module.py:27–28,340` — imports BOS internals from a package file (V6)
- [FAIL] `AdminModules.tsx:171–197` — `pluginDisplayName`/`pluginDescription` pattern-match on `plugin_id` (V7)
- [FAIL] `AdminModules.tsx:6–13` — `OAUTH_PLATFORMS` hardcodes OAuth platform icons/labels (V8)
- [FAIL] `plugins/PLUGIN_SDK.md:559–585` — SDK docs teach plugin devs to import BOS internals (V9)

Root cause of V1–V4 is a missing declarative credential slot contract in `channel.json`. See research.md Decision 10.
Root cause of V5–V6 is `workspace/council` being modeled as a package when it is a core service. Move to `api/council.py`.

## Notes

This feature is ready only for the lean plugin-host MVP. Do not use it to justify broad core rewrites or platform-specific plugin fixes.
