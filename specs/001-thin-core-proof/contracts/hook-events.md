# Contract: Hook Event Payloads (v1)

**Stability**: v1 — breaking changes require a new major version and a deprecation path.

---

## Event: `brief.before_dispatch`

Fired by `runs.py` immediately before `module.build_prompt(brief)` is called.
Subscribers receive and return a `HookPayload`. Mutations to `payload.brief` are
passed to the next subscriber and ultimately to the module.

**Payload**:
```json
{
  "event": "brief.before_dispatch",
  "brief": {
    "workspace_name": "...",
    "module_id": "marketing.channel.gmail.outreach.draft",
    "brand_id": "uuid-or-null",
    "_channel_credentials": {}
  },
  "context": {
    "brand": { "id": "...", "name": "...", "brand_json": {} },
    "workspace": { "id": "...", "name": "..." },
    "turn_id": "uuid"
  },
  "metadata": {
    "plugin_id": "channel.gmail",
    "attempt": 1
  }
}
```

**What subscribers may do**:
- Enrich `payload.brief` with brand context, memory slots, credentials
- Set `payload.brief["_channel_credentials"]` with resolved credential dict
- Read `payload.context` (read-only)
- Return the modified payload

**What subscribers must not do**:
- Raise exceptions (wrap errors, log, return payload unchanged)
- Make mutations to `payload.context`
- Call other hook events (no recursive firing)

---

## Event: `run.after_complete`

Fired by `runs.py` after a module run is persisted to the DB.
Action hook — subscribers react; they do not modify the run.

**Payload**:
```json
{
  "event": "run.after_complete",
  "brief": {},
  "context": {
    "run_id": "uuid",
    "module_id": "...",
    "status": "success | failed | pending_review",
    "brand_id": "uuid-or-null"
  },
  "metadata": {}
}
```

---

## Event: `manifest.built`

Fired when the capability manifest is being assembled for a plugin's capabilities.
Subscribers may annotate individual capability entries (e.g., add readiness warnings).

**Payload**:
```json
{
  "event": "manifest.built",
  "brief": {
    "module_id": "...",
    "entry": {}
  },
  "context": {
    "plugin_id": "...",
    "brand_id": "uuid-or-null"
  },
  "metadata": {}
}
```

---

## Event: `plugin.activated`

Fired when a plugin is activated for a brand or org-wide.
One-time setup: validate credentials, create plugin-owned tables, seed defaults.

**Payload**:
```json
{
  "event": "plugin.activated",
  "brief": {},
  "context": {
    "plugin_id": "...",
    "brand_id": "uuid-or-null",
    "manifest": {}
  },
  "metadata": {}
}
```

---

## Event: `plugin.deactivated`

Fired when a plugin is deactivated. Teardown: cancel scheduled work, release connections.

**Payload**:
```json
{
  "event": "plugin.deactivated",
  "brief": {},
  "context": {
    "plugin_id": "...",
    "brand_id": "uuid-or-null"
  },
  "metadata": {}
}
```
