# CMO Chat Response Speed Analysis

## Pipeline Overview

`POST /chat/stream` in `api/routers/chat.py` runs through several sequential phases before the first token reaches the user. Each phase involves DB queries, HTTP calls, or both — all blocking the LLM completion.

```
Request → Resolve Brand → Enrich References → Route Skills → Hydrate Memory
→ Build System Prompt → Resolve Providers → LLM Completion → First Token
```

---

## Bottleneck 1: Sequential Provider Resolution

**File:** `api/routers/chat.py` — `_complete_cmo_messages()` (line ~1091)

**Problem:** Every candidate provider is resolved **one at a time**:

```python
# For each provider, sequentially:
# 1. resolve_stored_provider_credential() — DB query
# 2. _live_direct_chat_model() — HTTP call to provider's model catalog API
# 3. Only THEN attempt the actual LLM completion
```

With 3 providers configured (e.g., OpenAI, Anthropic, Gemini), if each live catalog call takes 2s and the first provider fails, you wait 4-6s before the LLM even starts generating.

**Impact:** 2-6s added latency when the first provider is slow or fails.

**Fix:** Parallelize credential resolution + live catalog fetches for all providers, then try them in priority order with the pre-fetched data.

**Risk:** Medium — requires restructuring the provider selection loop to separate resolution from execution.

---

## Bottleneck 2: System Prompt Built Fresh Every Turn

**File:** `api/routers/chat.py` — `_build_system_prompt()` (line 818)

**Problem:** The system prompt is rebuilt from scratch on every chat turn, running **6+ sequential DB queries**:

| Query | Description |
|-------|-------------|
| `_workspace_brands()` | Brand list |
| `select(Product)` | Products (brand-scoped) |
| `select(Audience)` | Audiences (brand-scoped) |
| `select(WorkspaceDocument)` | Brand kit document |
| `select(WorkspaceDocument)` | Brand guideline document |
| `_workflow_state_context()` | Runs + RunTraces join (up to 20 rows) |
| `_actionable_artifacts_context()` | Another Runs + RunTraces join (up to 20 rows) |
| `_brand_channel_readiness()` | Social connections query |
| `format_manifest_for_brand()` | Capability manifest generation |
| `format_connector_status_for_prompt()` | Connector registry status |

The system prompt is mostly static between turns — brand profile, products, audiences, and brand kit change rarely. Only the workflow state and actionable artifacts change per-turn.

**Impact:** 200-500ms per chat turn.

**Fix:** Cache the system prompt per brand with a short TTL (e.g., 30s). Invalidate when brand data changes (brand profile update, product/audience edit, brand kit approval). Only rebuild the dynamic portions (workflow state, actionable artifacts) per-turn.

**Risk:** Low — the cache key is `(brand_id, workspace_id)` and the TTL is short enough that stale data is unlikely.

---

## Bottleneck 3: Reference Enrichment Before LLM Call

**File:** `api/routers/chat.py` — `_generate_chat_stream()` (line ~1575)

**Problem:** Drive references are enriched and **committed to DB** before the LLM call:

```python
await _enrich_drive_references(body.references, ...)  # DB + Drive API calls
await _persist_chat_references(...)                     # DB writes
if body.references:
    await db.commit()                                   # DB commit
```

This happens **twice** in the stream path (once before brand resolution, once after). The enrichment involves Drive API calls to fetch file metadata and content.

**Impact:** 100-500ms when references are attached (varies with Drive API latency).

**Fix:** Fire-and-forget the persistence (defer the `db.commit()` to after the LLM response starts streaming), and only block on enrichment that the LLM actually needs for context injection.

**Risk:** Low — references are already stored client-side; server-side persistence is for audit/retrieval, not for the current turn's LLM context.

---

## Bottleneck 4: Memory Hydration on Every Turn

**File:** `api/routers/chat.py` — `_generate_chat_stream()` (line ~1620)

**Problem:** Memory slots are hydrated from scratch on every turn:

```python
hydrated_memory = await hydrate_memory_slots(db, ws, memory_slots, brand=active_brand)
```

This queries memory events, outcomes, decision briefs, and other historical context — all before the LLM call.

**Impact:** 50-200ms per chat turn.

**Fix:** Cache hydrated memory per brand with a short TTL (e.g., 30s). Invalidate when new memory events or outcomes are written.

**Risk:** Low — memory is append-only and changes infrequently within a conversation.

---

## Bottleneck 5: Skill Routing + Manifest Generation

**File:** `api/routers/chat.py` — `_generate_chat_stream()` (line ~1610)

**Problem:** Skill routing and capability manifest generation run on every turn:

```python
routed = route_chat_skills(body.message)           # NLP routing
modules = await _chat_modules(db, brand_id)         # DB: active plugins + skills
format_manifest_for_brand(db, brand_id)             # Inside _build_system_prompt
```

The capability manifest (`format_manifest_for_brand`) is particularly heavy — it iterates all installed skills, checks plugin activation status, and formats a large text block.

**Impact:** 50-150ms per chat turn.

**Fix:** Cache the capability manifest per brand. It only changes when plugins are activated/deactivated or skills are installed.

**Risk:** Low — plugin/skill changes are rare admin operations.

---

## Summary

| # | Bottleneck | Impact | Fix | Risk |
|---|-----------|--------|-----|------|
| 1 | Sequential provider resolution | 2-6s | Parallelize credential + catalog fetches | Medium |
| 2 | System prompt built fresh every turn | 200-500ms | Cache per brand, 30s TTL | Low |
| 3 | Reference enrichment before LLM call | 100-500ms | Defer persistence, only enrich what LLM needs | Low |
| 4 | Memory hydration on every turn | 50-200ms | Cache per brand, 30s TTL | Low |
| 5 | Skill routing + manifest generation | 50-150ms | Cache manifest per brand | Low |

**Total potential savings:** 2.4-7.4s before first token, depending on provider configuration and reference attachments.

**Highest-impact, lowest-risk fix:** Cache the system prompt (Bottleneck 2). This alone saves 200-500ms per turn with almost no risk of stale data.

**Highest-impact overall:** Parallelize provider resolution (Bottleneck 1). When the first provider is slow or fails, this saves 2-6s — but requires more careful restructuring.
