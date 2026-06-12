# AI Providers & Fallback Routing

Configuration, routing policy, fallback mechanisms, DB/API contracts, and implementation plan for per-specialist model assignment with automatic failover.

> Decisions are settled. Do not re-add review notes or collaboration logs to this file — those belong in chat, not the spec.

---

## 1. Specialist Model Assignments

**Default strategy: route text and multimodal through OpenRouter.**
OpenRouter is OpenAI-compatible, covers 300+ models through one adapter, and handles transient provider failures internally. BOS-level fallbacks only activate when OpenRouter itself fails or a model is retired.

| Specialist | Provider | Model |
|---|---|---|
| `cmo.main` | `openrouter` | `anthropic/claude-opus-4` |
| `council.seat.c1` | `openrouter` | `anthropic/claude-opus-4` |
| `council.seat.c2` | `openrouter` | `openai/gpt-4o` |
| `council.seat.c3` | `openrouter` | `google/gemini-2.5-pro` |
| `council.seat.c4` | `openrouter` | `meta-llama/llama-3.1-405b-instruct` |
| `council.seat.c5` | `openrouter` | `mistralai/mistral-large` |
| `media.image.generate` | `bytedance` | `seedream-4-5-251128` |
| `media.video.generate` | `bytedance` | `seedance` |
| Task specialists | `openrouter` | `openai/gpt-4o-mini` |

**First production target:** Council seats C1–C5 — diverse models per seat is the deliberation value, and it proves the routing feature end-to-end in a low-risk context.

---

## 2. Architecture & Routing Flow

```
BOS Executor Layer
  resolves: config via precedence chain
  constructs: candidate queue (primary → fallbacks → catalog)
  orchestrates: fallback loop across providers
        ↓
OpenRouter Layer (when provider = "openrouter")
  handles: provider 429/503, latency spikes — transparent to BOS
  optimisation: if all candidates are OR models, single request with models[]
        ↓
Upstream provider
```

### Precedence Chain

1. Admin DB override (`execution_backend_overrides` row for workspace + target)
2. Plugin `default_backend` from `channel.json` (registered at activation)
3. `EXECUTION_BACKEND_OVERRIDES` env var
4. Capability router catalog (`capability_router.py`, based on policy)

---

## 3. API & Data Model

### `PUT /settings/backends/{target:path}`

`:path` converter is required — module IDs contain dots.

```json
{
  "provider": "bytedance",
  "model_id": "seedream-4-5-251128",
  "modality": "image",
  "strict": false,
  "routing_hints": {
    "data_collection": "deny"
  },
  "fallbacks": [
    { "provider": "openai", "model_id": "dall-e-3" },
    { "provider": "openrouter", "model_id": "black-forest-labs/flux-1.1-pro" }
  ]
}
```

### `channel.json` `default_backend`

Plugins declare their preferred backend. Activates on install with no admin config. DB overrides always win.

```json
{
  "plugin_id": "media.image",
  "default_backend": {
    "provider": "openrouter",
    "model_id": "black-forest-labs/flux-1.1-pro",
    "modality": "image",
    "strict": false,
    "routing_hints": { "sort": "price", "allow_fallbacks": true },
    "fallbacks": [
      { "provider": "openai", "model_id": "dall-e-3" }
    ]
  }
}
```

### DB Migration

```python
def upgrade():
    op.add_column("execution_backend_overrides",
        sa.Column("fallbacks_json", postgresql.JSONB, nullable=False, server_default="[]"))
    op.add_column("execution_backend_overrides",
        sa.Column("routing_hints_json", postgresql.JSONB, nullable=False, server_default="{}"))

def downgrade():
    op.drop_column("execution_backend_overrides", "routing_hints_json")
    op.drop_column("execution_backend_overrides", "fallbacks_json")
```

### `BackendRef` (`api/model_overrides.py`)

```python
@dataclass(frozen=True)
class BackendRef:
    provider: str
    model_id: str | None = None
    modality: str = "text"
    tool_id: str | None = None
    strict: bool | None = None
    fallbacks: tuple["BackendRef", ...] = ()
    routing_hints: dict = field(default_factory=dict)
```

`parse_backend_ref` must recursively parse the `fallbacks` array when present.

---

## 4. Execution Runner Algorithm

### Candidate Queue Construction (`runs.py`)

The existing `reorder_candidates_for_model_override` call is replaced by explicit queue construction. Catalog candidates come from the existing `route()` call — their shape is unchanged.

> [!IMPORTANT]
> To ensure type safety, `resolve_backend_override` is updated to always return a `BackendRef` object (or `None`), mapping database ORM rows to `BackendRef` internally. This allows the runner below to treat `override` and its fallbacks as clean `BackendRef` instances.


```python
override = await resolve_backend_override(db, ws.id, module_id)
override_is_strict = effective_strict(settings, override) if override else False

catalog_candidates, routing_meta = await route(db, module.capability, eff_policy)

if override:
    # Primary override
    primary = {"provider": override.provider, "model_id": override.model_id,
               "modality": override.modality, "routing_hints": override.routing_hints,
               "fallback_source": "primary_override"}
    # Explicit fallback chain
    explicit = [
        {"provider": f.provider, "model_id": f.model_id,
         "routing_hints": f.routing_hints, "fallback_source": f"fallbacks_json[{i}]"}
        for i, f in enumerate(override.fallbacks)
    ]
    if override_is_strict:
        candidates = [primary] + explicit
    else:
        seen = {(primary["provider"], primary["model_id"])}
        seen.update((f["provider"], f["model_id"]) for f in explicit)
        tail = [c for c in catalog_candidates if (c["provider"], c["model_id"]) not in seen]
        for c in tail:
            c["fallback_source"] = "catalog"
        candidates = [primary] + explicit + tail
else:
    candidates = catalog_candidates
```

### Credential Pre-flight

Already implemented in `runs.py` lines 1331–1341: candidates without a resolvable API key are skipped before `execute_live` is called. No change needed.

### OR-Native Fallback Optimisation

When the primary **and all explicit fallbacks** are OpenRouter models, pass them as a single `models` array — OR fails over internally instead of BOS making sequential HTTP calls.

```python
# In the OR adapter / execute_live path, before the call:
all_or = (
    override
    and override.provider == "openrouter"
    and all(f.provider == "openrouter" for f in override.fallbacks)
    and override.fallbacks  # only activate if there are fallbacks to pass
)
if all_or:
    payload["models"] = [override.model_id] + [f.model_id for f in override.fallbacks]
    # Single request; OR handles failover. BOS loop runs once.
    # OR validates context windows before routing — models that can't handle the prompt
    # length are skipped automatically. No BOS-side token pre-flight needed.
    # BYOK chains: if primary uses a direct provider key (not openrouter), all_or = False
    # and the BOS sequential loop runs instead. No special handling required.
```

### OpenRouter `routing_hints` Mapping

`routing_hints` maps directly to OR's `provider` body field:

```python
if routing_hints:
    payload["provider"] = {
        k: v for k, v in {
            "sort": routing_hints.get("sort"),
            "order": routing_hints.get("order"),
            "allowFallbacks": routing_hints.get("allow_fallbacks"),
            "dataCollection": routing_hints.get("data_collection"),
        }.items() if v is not None
    }
```

| `routing_hints` key | OR field | Values |
|---|---|---|
| `sort` | `sort` | `"price"` / `"throughput"` / `"latency"` |
| `order` | `order` | `list[str]` of provider names |
| `allow_fallbacks` | `allowFallbacks` | `bool` |
| `data_collection` | `dataCollection` | `"allow"` / `"deny"` |

### Run Trace

```json
{
  "winner": "openai/dall-e-3",
  "routing_reason": "Primary bytedance/seedream failed HTTP 429; fell back to fallbacks_json[0]",
  "attempts_log": [
    { "provider": "bytedance", "model_id": "seedream-4-5-251128",
      "status": "failed", "error": "HTTP 429", "fallback_source": "primary_override" },
    { "provider": "openai", "model_id": "dall-e-3",
      "status": "succeeded", "fallback_source": "fallbacks_json[0]" }
  ]
}
```

`fallback_source` values: `primary_override` / `fallbacks_json[n]` / `catalog`.
Cost and latency on the run record always reflect the winning attempt — `execute_live` already returns these from the successful call.

---

## 5. UI Wireframe

```
+-------------------------------------------------------------------------+
| Configure Specialist AI: media.image.generate                           |
+-------------------------------------------------------------------------+
|  PRIMARY BACKEND                                                        |
|  Provider: [ ByteDance v ]  Model: [ seedream-4-5... v ]                |
|  OR sort:  [ none v ]  (price / throughput / latency — OR only)        |
|                                                                         |
|  FALLBACK CHAIN  (tried in order if primary fails)                     |
|  1. [ OpenAI v ]  [ dall-e-3 v ]  [ Remove ]                           |
|  2. [ OpenRouter v ]  [ flux-1.1-pro v ]  [ Remove ]                   |
|  [ + Add Fallback ]                                                     |
|                                                                         |
|  ( ) Strict — fail if all explicit options fail                        |
|  (x) Balanced — try catalog models if all explicit options fail        |
|                                                                         |
|  Source: admin override  (plugin default: openrouter/flux-1.1-pro)     |
|  [ Cancel ]                              [ Save Changes ]              |
+-------------------------------------------------------------------------+
```

---

## 6. Implementation Plan

1. **`BackendRef` + `parse_backend_ref`** (`api/model_overrides.py`) — add `fallbacks` and `routing_hints`; parse recursively.
2. **DB model** (`api/models/backend.py`) — add `fallbacks_json`, `routing_hints_json` columns.
3. **Alembic migration** — `add_fallbacks_routing_hints_to_backend_overrides`.
4. **Pydantic schemas** (`api/schemas/backend_settings.py`) — add `FallbackModel`; update `BackendOverrideIn` / `BackendOverrideOut`.
5. **Settings router** (`api/routers/backend_settings.py`) — update `resolve_backend_override` to always return a unified `BackendRef` (converting DB ORM rows if found); update `_row_to_out` and `put_backend_override` to persist/return new columns.
6. **Plugin loader** (`api/plugin_loader.py`) — read `channel.json` `default_backend` at activation; register as lower-priority override.
7. **Execution runner** (`api/routers/runs.py`) — replace `reorder_candidates_for_model_override` call with explicit queue construction; pass `routing_hints` to `execute_live`.
8. **OR adapter** (`api/providers/openrouter.py` or executor) — add OR-native fallback optimisation and `routing_hints` mapping.
9. **Frontend** (`AdminModules.tsx`) — fallback chain UI, source indicator, OR sort selector.

---

## 7. Test Checklist

- [ ] `PUT /settings/backends/media.image.generate` saves `fallbacks_json` and `routing_hints_json` correctly
- [ ] `GET /settings/backends` returns the configured fallback array
- [ ] Plugin `channel.json` `default_backend` is used when no DB override exists
- [ ] DB override takes precedence over `channel.json` default
- [ ] Primary failure → runner proceeds to `fallbacks_json[0]`; trace shows correct `fallback_source`
- [ ] All-OR fallback chain → single request with `models[]` array; BOS loop runs once
- [ ] Mixed-provider chain → BOS retry loop; OR-native optimisation does not activate
- [ ] `strict: true` — run fails if all explicit options fail; catalog not touched
- [ ] `strict: false` — catalog candidates used after all explicit options fail
- [ ] Winning attempt's cost and model ID are what get persisted on the run

