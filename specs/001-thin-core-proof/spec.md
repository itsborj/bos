# Feature Specification: Thin Core + SDK Plugin Architecture

**Feature Branch**: `001-thin-core-proof`

**Created**: 2026-06-08

**Status**: Draft

---

## Problem Statement

BOS's core routing files (`chat.py`, `runs.py`) have grown to 2,146 and 2,106 lines
respectively against a stated target of a fixed 7-step contract of ~100–200 lines.
Every new plugin currently requires edits to core files — brand scoping, memory
hydration, credential injection, and upstream contract logic all live as branches
inside `chat.py` and `runs.py` instead of in hook subscriptions declared by each
plugin.

The result: adding or removing any plugin risks breaking unrelated plugins. Core is
not stable — it grows with each new plugin.

The fix is a full separation:

- **BOS core** (`~/bos/`) — a fixed 7-step pipeline harness and a public SDK.
  It never changes when plugins are added or removed.
- **Plugin repo** (`~/bos-plugins/`) — a separate git repository. All plugins
  live here. Plugins import only from `klaroha_sdk`. BOS loads them via a
  mounted volume. Deleting a plugin folder from this repo leaves BOS completely
  stable — the capability disappears from the manifest and nothing else changes.

`api/plugins/` inside the main BOS repo is silently deprecated. All current plugins
are copied and adapted to `~/bos-plugins/`. No maintenance happens on the old
internal copies.

---

## User Scenarios & Testing

### User Story 1 — Thin Core (Priority: P1)

An operator uses BOS with only the `hello` smoke-test plugin active. The CMO
dispatches it, an artifact appears in Stream, and the operator approves it.
`chat.py` is under 200 lines and contains zero plugin-specific, channel-specific,
or platform-specific logic.

**Why this priority**: The core is the foundation. Nothing else can be trusted until
the 7-step contract is proven with a trivial plugin.

**Independent Test**: Fresh stack, only `hello` in `~/bos-plugins/`. Send any CMO
message that triggers it. Observe: manifest contains only `hello`, artifact appears,
approval works. Read `chat.py` — no plugin names, no brand-resolution branches, no
credential lists.

**Acceptance Scenarios**:

1. **Given** only `hello` is in `~/bos-plugins/`, **When** the CMO dispatches it,
   **Then** an artifact appears in Stream and `chat.py` contains zero plugin-specific
   code.

2. **Given** the `hello` folder is deleted from `~/bos-plugins/`, **When** BOS
   restarts, **Then** the manifest is empty, no error is raised, and the system
   starts cleanly.

3. **Given** `chat.py` is at its final state, **When** a new plugin is added to
   `~/bos-plugins/`, **Then** `chat.py` requires zero edits — the plugin appears
   automatically via manifest discovery.

---

### User Story 2 — SDK Boundary (Priority: P1)

A plugin developer working only in `~/bos-plugins/` — with no access to BOS
internals — can write a fully functional plugin using only `from klaroha_sdk import
...`. The plugin handles credentials, brand context, and artifact output without
importing anything from the BOS codebase.

**Why this priority**: The SDK boundary must be structural, not conventional.
If a plugin physically cannot import BOS internals (different repo, different Python
path), the boundary is real. If it can but just chooses not to, it is fragile.

**Independent Test**: Write `~/bos-plugins/hello/module.py` with only
`from klaroha_sdk import ChannelModule, ArtifactBlock`. Confirm it dispatches,
produces a valid artifact, and returns it to Stream. Confirm no BOS internal module
is reachable from the plugin's Python environment.

**Acceptance Scenarios**:

1. **Given** a plugin imports only `from klaroha_sdk import ...`, **When** BOS
   dispatches it, **Then** it runs successfully and produces a valid artifact.

2. **Given** a plugin developer attempts `from api.routers import anything`,
   **Then** an `ImportError` is raised — BOS internals are not on the plugin's
   Python path.

3. **Given** a plugin declares credential requirements in `channel.json`,
   **When** the plugin executes, **Then** credentials are injected by the host
   via the declared hook — the plugin never calls a database or reads env vars
   directly.

---

### User Story 3 — Delete Stability (Priority: P1)

Deleting any plugin folder from `~/bos-plugins/` leaves BOS completely stable.
The removed plugin's capabilities disappear from the manifest. No errors. No
crash. All remaining plugins continue working.

**Why this priority**: This is the definitive proof. If the system stays stable
when a plugin is deleted, the boundary is real. If it crashes, the plugin was
coupled to core.

**Independent Test**: With `gmail` and `hello` both active, delete
`~/bos-plugins/gmail/`. Restart BOS. Confirm: only `hello` in manifest, no errors,
`hello` still dispatches correctly.

**Acceptance Scenarios**:

1. **Given** multiple plugins are active, **When** one plugin folder is deleted
   and BOS restarts, **Then** only that plugin's capabilities vanish — all others
   are unaffected.

2. **Given** a plugin folder contains an invalid `SKILL.md` or broken `module.py`,
   **When** BOS starts, **Then** that plugin is skipped with a warning — it does
   not prevent other plugins from loading.

3. **Given** `~/bos-plugins/` is empty, **When** BOS starts, **Then** the manifest
   is empty and CMO chat still responds — it just has no dispatchable capabilities.

---

### User Story 4 — Gmail End-to-End (Priority: P2)

The Gmail plugin is migrated from `api/plugins/gmail/` to `~/bos-plugins/gmail/`,
adapted to use only `klaroha_sdk`, and proven end-to-end: CMO dispatch → draft
artifact → Stream → operator approves.

**Why this priority**: Gmail is the Gate 2 proven path and the most strategically
important specialist. Proving it works through the new architecture validates the
SDK for a real, credential-requiring, brand-aware plugin.

**Independent Test**: Connect Gmail for the active brand. Send "draft an outreach
email." Observe: draft artifact in Stream, editable copy, Approve/Revise/Dismiss
controls present. Approve — run status updates. Inspect `~/bos-plugins/gmail/module.py`
— no BOS internal imports.

**Acceptance Scenarios**:

1. **Given** Gmail is in `~/bos-plugins/` with only `klaroha_sdk` imports,
   **When** the CMO dispatches `gmail.draft`, **Then** a correctly brand-scoped
   draft artifact appears in Stream.

2. **Given** a brand without Gmail connected, **When** the CMO attempts to
   dispatch Gmail, **Then** a setup-blocker artifact appears — not a crash.

3. **Given** Gmail is active and the operator approves a draft, **Then** the
   run status updates to approved and the artifact reflects the decision.

---

### User Story 5 — Live Deploy (Priority: P2)

The thin-core BOS with `klaroha_sdk` and the `~/bos-plugins/` plugin repo is
deployed to hq.klaroha.com. The production system runs the new architecture.

**Why this priority**: The proof only counts on the live system. Staging is not
the goal.

**Independent Test**: Connect to hq.klaroha.com. Confirm Gmail plugin is active
and end-to-end loop works. Confirm manifest only includes capabilities from
`~/bos-plugins/`. Confirm `api/plugins/` internal copies are not loaded.

**Acceptance Scenarios**:

1. **Given** the new architecture is deployed to hq.klaroha.com, **When** the
   operator uses CMO chat with Gmail active, **Then** the full loop works
   identically to local proof.

2. **Given** `api/plugins/` still contains old internal plugin directories,
   **When** BOS starts, **Then** those directories are not loaded — only
   `~/bos-plugins/` (mounted at `/external_plugins/`) is the active plugin source.

3. **Given** the live system is running, **When** a plugin is deleted from the
   server-side `~/bos-plugins/` clone and BOS is restarted, **Then** that
   capability disappears cleanly from the manifest.

---

### Edge Cases

- `~/bos-plugins/` being absent or unmounted must not crash BOS — manifest loads
  with zero external capabilities and a warning is logged.
- A plugin in `~/bos-plugins/` with a duplicate `module_id` matching a built-in
  must be rejected with a clear conflict error, not silently overriding.
- Brand scoping and memory hydration moving to hook subscribers must produce
  identical outputs to the current inline logic — no brand bleed, no missing
  memory slots.
- The @klar command parser and SCOPE directive stripper remain in core as
  deterministic parsing utilities — they are not plugins.

---

## Requirements

### Functional Requirements

- **FR-001**: `chat.py` MUST implement exactly 7 steps and nothing else:
  receive → load manifest → LLM → strip directives → dispatch → persist → return.
- **FR-002**: `chat.py` MUST contain zero plugin-specific, channel-specific, or
  platform-specific logic.
- **FR-003**: Brand scoping MUST execute as a pipeline hook subscriber, not inline
  code in the chat handler.
- **FR-004**: Memory hydration MUST execute as a pipeline hook subscriber.
- **FR-005**: Credential injection MUST be declared in `channel.json` and executed
  by the host — not by a manually-maintained list in `runs.py`.
- **FR-006**: `klaroha_sdk` MUST be a pip-installable Python package containing
  all types and base classes a plugin author needs: `ChannelModule`, `ArtifactBlock`,
  `BridgeEnvelope`, `RunResult`, `HookPayload`.
- **FR-007**: BOS MUST scan an external plugin directory (`/external_plugins/`,
  mounted from `~/bos-plugins/`) in addition to, and eventually instead of,
  `api/plugins/`.
- **FR-008**: `api/plugins/` MUST be deprecated — no new plugin work happens there.
  Existing internal plugins are not deleted but receive no maintenance.
- **FR-009**: A plugin with an invalid manifest or broken module MUST be skipped
  with a warning — it MUST NOT prevent other plugins from loading.
- **FR-010**: Deleting a plugin folder from `~/bos-plugins/` and restarting BOS
  MUST leave all other plugins and core fully functional.
- **FR-011**: The Gmail plugin MUST be migrated to `~/bos-plugins/gmail/` with
  only `klaroha_sdk` imports and proven end-to-end.
- **FR-012**: The system MUST deploy to hq.klaroha.com and run stably with plugins
  loaded exclusively from `~/bos-plugins/`.

### Key Entities

- **Pipeline Hook**: A named event (`brief.before_dispatch`, `run.after_complete`,
  etc.) that core fires at lifecycle boundaries. Subscribers are registered by
  plugins via `channel.json`. Core fires; it never imports plugins directly.
- **klaroha_sdk**: The public Python package defining the stable plugin contract.
  Everything a plugin author needs. Nothing from BOS internals.
- **External Plugin Directory**: `/external_plugins/` inside the BOS container,
  volume-mounted from `~/bos-plugins/` on the host. The scanner reads both this
  and `api/plugins/` (deprecated) during the transition.
- **Activation State**: Installed (directory present) vs Active (DB record). Only
  active plugins contribute to the manifest. A missing directory = uninstalled,
  not an error.

---

## Success Criteria

- **SC-001**: `chat.py` is under 200 lines.
- **SC-002**: Zero plugin, channel, or platform names appear in `chat.py` or in
  the core dispatch path.
- **SC-003**: Adding a new plugin to `~/bos-plugins/` requires zero edits to any
  file in `~/bos/api/`.
- **SC-004**: Deleting any plugin from `~/bos-plugins/` and restarting BOS
  produces zero errors and leaves all other plugins functional.
- **SC-005**: A plugin written with only `from klaroha_sdk import ...` dispatches,
  produces an artifact, and completes the approval loop.
- **SC-006**: The Gmail end-to-end loop (CMO → draft artifact → Stream → approve)
  works through `~/bos-plugins/gmail/` with zero BOS internal imports in the plugin.
- **SC-007**: hq.klaroha.com runs the new architecture with plugins from
  `~/bos-plugins/` — stable, no regressions on the Gmail loop.

---

## Assumptions

- `~/bos-plugins/` is initialized as a separate git repository on the same host.
- During local development, `~/bos-plugins/` is volume-mounted into the BOS
  container at `/external_plugins/`.
- On the server (hq.klaroha.com), `~/bos-plugins/` is cloned separately and
  mounted the same way via `docker-compose.yml`.
- `api/plugins/` deprecation is silent — no announcement, no deletion rush.
  Old plugin directories stay in the repo but receive no further changes.
- The first-party hook subscribers (brand scoping, memory hydration) are system
  packages inside `~/bos/api/` — they use the same hook API third-party plugins
  use, which proves the hook API works from day one.
- @klar command parsing and SCOPE directive stripping stay in core — they are
  deterministic step-1 and step-4 utilities, not plugins.
- Council (@council routing) stays in core as a deterministic command parser
  that routes to a capability — it is not a plugin.
- `gbp-completeness` is the chosen second proof plugin (replaces gmail for initial
  proof — already written in `~/bos-plugins/`, exercises OAuth credential injection,
  `approval_bundle` renderer, and `pending_review` status without SMTP complexity).
  Gmail migration proceeds as a follow-on step after GBP proof passes.
- All other current plugins are migrated to `~/bos-plugins/` in a follow-on
  pass — the initial deploy proves the architecture with `hello` + `gbp-completeness` only.
- The deploy target is `main` → hq.klaroha.com via the existing deploy runbook.
