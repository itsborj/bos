# BOS v2 — Architecture Critique & Migration Roadmap

**Date:** 2026-06-25
**Status:** Architecture assessment — current state vs. stated target
**Source:** Full read of PROJECT_BRIEF.md, BITE.md, BOS_PI_PLAN.md, .arch-rules.yml, STRATEGY_WORKFLOW.md, WORKFLOW_REGISTRY.md, context.md, docs/cmo_chat.md, previs.md, chat_v2.py, chat_v2.md, chat_notes.md, and code structure

---

## What's Good — Genuine Strengths

### 1. The thin-core plugin model is the right bet

The WordPress/VS Code analogy is correct. BOS core owning only load/resolve/inject/dispatch/persist, with everything else as packages, is the architecture that survives 10,000 orgs with different needs. The `.arch-rules.yml` grep rules are a clever enforcement mechanism — they catch regressions at CI time, not code review time.

### 2. BITE methodology is underrated

"Generate a sample output before generating a spec" is a real constraint that prevents architecture astronauts from designing things nobody will use. The sample-first pipeline (Discuss → Sample → Agree → Reverse-spec → Build) is a genuine process innovation.

### 3. The Strategy Workflow component DAG is well-modeled

The cascade rules, archetype weighting, and stale-marking are clean. The typed JSON output contracts per component are the right shape — no markdown-as-source-of-truth. The `status: usable_with_gaps` concept is smart for an AI system where partial results are still valuable.

### 4. The Pi fork plan is realistic

`BOS_PI_PLAN.md` correctly identifies that the only coupling surface is `/chat/stream`, the fork rename is 3 JSON fields, and the provider extension is ~100 lines of TypeScript. The work estimate (~1 week) is honest.

### 5. The `chat_v2` prototype proves the thesis

At 882 lines with native tool calls (Anthropic tool-use, not text regex), it shows what the architecture looks like without the text-protocol parsing layer. The comparison against Smith (`chat_v2.md`) correctly identifies that they're different tools for different jobs, not competitors.

---

## The Critical Gap — Architecture Drift

**The single biggest problem: the implementation has drifted far from the stated architecture.** This isn't a design flaw — it's an execution gap. The architecture documents are internally consistent and well-reasoned. The code is not.

### chat.py: 2,354 lines. Target: ~100.

The `docs/cmo_chat.md` diagnosis is accurate: the chat handler became the domain. Five regexes, three parsers, one orphan-param stripper — 260 lines of text parsing to recover structure the LLM already knows how to emit natively via tool calls. The text protocol (`RUN:`, `SCOPE:`, `ACTION:`, `PATCH_REFERENCE:`) is an accidental complexity layer that `chat_v2.py` proves is unnecessary.

### runs.py: 2,497 lines

`inject_channel_credentials()` is a manually-maintained list that grows with every new plugin. The revision endpoint (`/chat/runs/{run_id}/revise`) is 280 lines of module-specific branching. This is exactly the pattern the hook system in `PROJECT_BRIEF.md` was designed to eliminate.

### social.py: 1,842 lines

The OAuth relay has a known P0 bug (Google Business Profile in `GOOGLE_RELAY_PLATFORMS` but missing from relay's `_PLATFORM_SCOPES`). The Drive Picker depends on local `GOOGLE_CLIENT_ID` even in relay mode. The Facebook multi-page selection has a schema width mismatch (`String(1024)` vs `Text`). These are not architectural problems — they're bugs — but they indicate that the plugin credential system hasn't been fully extracted from core.

### The hook system doesn't exist yet

`PROJECT_BRIEF.md` § Plugin Lifecycle describes `run.before_execute`, `run.after_complete`, `artifact.before_persist`, `brief.before_dispatch` — these are the structural alternative to `chat.py` monolith accumulation. But they're described as "architecture principles. No implementation until a BITE sample is approved." This is the bottleneck. Every new plugin need forces a new branch into core because the hook surface doesn't exist to absorb it.

---

## Structural Risks

### 1. The text protocol is a dead end

`RUN: module.id`, `SCOPE: execution_brand: X`, `ACTION: uuid action`, `PATCH_REFERENCE: {...}` — this is a custom DSL implemented in regex. It has already produced bugs:

- **STRAT-BUG-001 (2026-06-11):** `_ORPHAN_PARAM_BLOCK_RE` used `[^\n]+` (required 1+ chars), silently missing empty-value param lines like `video_prompt:`, leaking them into visible CMO replies.
- **SDK-038 (2026-06-09):** Orphan RUN params leaked into visible reply — required adding `_ORPHAN_PARAM_BLOCK_RE` as a second-pass stripper.

`chat_v2.py` proves native tool calls work. The longer the text protocol stays, the more code accumulates around it, and the harder the migration becomes.

### 2. The Extension Host is vaporware

It's described in detail in `PROJECT_BRIEF.md` — compatibility shims, plugin quarantine, release integrity, contract versioning. But it doesn't exist. Without it, third-party plugins can't be safely installed. The "10,000 orgs with different needs" vision requires it.

### 3. The Generic Workflow Registry is only a proposal

`WORKFLOW_REGISTRY.md` is marked "Proposed architecture direction." Without it, every new multi-step workflow (storyboard → image → video, email sequences, ad creative sets) will add hardcoded branches to `chat.py`. The storyboard pipeline already has module-specific branching in the revision endpoint.

### 4. Previs pipeline has a 7-hour bottleneck

The gap between OpenAI API latency (80–240s) and run elapsed time (up to 25,000s) is a real production problem. The likely cause (SDK blocking on rate limits with no timeout) is a quick fix but indicates the pipeline wasn't built with production timeouts from the start.

### 5. No streaming in chat_v2

The comparison doc correctly notes this is acceptable for image generation (the image dominates latency), but if chat_v2 becomes the main CMO endpoint, the lack of streaming will be a UX regression from the current SSE streaming chat.

---

## What's Missing

| Gap | Impact | Blocked by |
|-----|--------|------------|
| Hook system implementation | Every new plugin forces a core change | No BITE sample approved |
| Extension Host | No safe third-party plugin installation | Depends on hook system |
| Generic Workflow Registry | Multi-step workflows add core branches | Proposal stage only |
| chat.py → chat_v2 migration | 2,354-line monolith persists | chat_v2 is image-only; needs full tool registry |
| Plugin activation per-brand | All bundled plugins auto-activate org-wide | DB model exists, not wired to dispatch |
| Credential slot resolver (generic) | `inject_channel_credentials()` is a manual list | `.arch-rules.yml` rule `no-platform-branches-in-injector` exists but code hasn't been refactored |

---

## Known Bugs (from context.md)

| Priority | Bug | Location |
|----------|-----|----------|
| **P0** | Google Business button broken in relay mode — `google_business` in `GOOGLE_RELAY_PLATFORMS` but missing from relay's `_PLATFORM_SCOPES` | `api/provider_auth.py` + `relay/main.py` |
| **P0** | Drive folder picker fails after relay-based Drive connect — `app_id` derived from local `GOOGLE_CLIENT_ID` which is empty in relay-only installs | `api/routers/social.py:757-772` |
| **P1** | Facebook connect blocked unless Meta plugin credentials saved — no `META_APP_ID`/`META_APP_SECRET` in `.env` | `api/provider_auth.py` + `api/routers/social.py` |
| **P1** | Facebook multi-page selection can break — ORM model `String(1024)` vs migration `Text` width mismatch | `api/models/provider.py` + migration `026_meta_oauth.py` |
| **P1** | GBP local handler fails for valid accounts with multiple accounts/locations — only inspects `accounts[0]` and `locations[0]` | `api/provider_auth.py` |
| **P2** | Brands page Drive status renders `needs_reauth` as connected — shows "Choose folder" button when picker-config returns no token | `web/src/pages/admin/AdminBrands.tsx` |

---

## Recommendations (Ordered by Impact)

### 1. Ship the hook system now

This is the unlock for everything else. Even a minimal implementation with `run.before_execute` and `brief.before_dispatch` would let you extract credential injection, brand scoping, and memory hydration from `chat.py` and `runs.py`. The BITE sample doesn't need to be perfect — it needs to exist so extraction can begin.

**Target files to extract first:**
- `inject_channel_credentials()` from `runs.py` → `brief.before_dispatch` hook
- Brand scoping logic from `chat.py` → `run.before_execute` hook
- Memory hydration from `chat.py` → `run.before_execute` hook

### 2. Migrate CMO chat to native tool calls

`chat_v2.py` proves the pattern works. Expand it from one tool (`json_imagen`) to a dynamic tool registry that reads from `capability_manifest.py`. The text protocol (RUN:/SCOPE:/ACTION:) should be deprecated, not maintained.

**Migration path:**
1. Add tool definitions to `capability_manifest.py` output (one tool per dispatchable capability)
2. Expand `chat_v2.py` to use dynamic tool registry instead of hardcoded `json_imagen`
3. Add streaming to `chat_v2.py`
4. Route CMO chat through `chat_v2.py` once parity is reached
5. Deprecate text protocol parsing in `chat.py`

### 3. Fix the P0 OAuth bugs

Google Business Profile relay routing is broken. Drive Picker fails in relay-only installs. These are user-facing blockers that erode trust in the plugin model.

### 4. Add timeouts to the previs pipeline

A 300s timeout on `_call_openai_edit()` with retry would prevent the 7-hour hangs. This is a one-line fix with outsized impact.

**Additional quick wins from `previs.md`:**
- Skip CMO LLM call for image revisions (use canned reply)
- Reduce Seedance poll interval from 10s to 5s
- Truncate Seedance prompt (68K includes redundant JSON spec)
- Compress source image before OpenAI upload (3MB base64 is oversized)

### 5. Implement the Generic Workflow Registry before adding more multi-step workflows

The storyboard pipeline already has core branches. Each new workflow (email sequences, ad sets, publishing chains) will add more unless the registry exists first.

---

## Architecture Scorecard

| Dimension | Design | Implementation | Gap |
|-----------|--------|----------------|-----|
| Thin core | ★★★★★ | ★★☆☆☆ | chat.py 2,354 lines vs 100 target |
| Plugin model | ★★★★★ | ★★★☆☆ | Hook system missing; Extension Host vaporware |
| Capability manifest | ★★★★★ | ★★★★★ | Auto-generated from SKILL.md — working as designed |
| Brand scoping | ★★★★☆ | ★★★★☆ | `_brand_scoped_brief()` is correct; some edge cases remain |
| Strategy workflow | ★★★★★ | ★★★★☆ | DAG + cascade rules are clean; not-wired components remain |
| Creative supply chain | ★★★★☆ | ★★★☆☆ | Brand-locked contract is correct; previs pipeline has 7h bottleneck |
| OAuth/credentials | ★★★☆☆ | ★★☆☆☆ | P0 bugs in relay routing; manual credential injection list |
| Multi-step workflows | ★★★★☆ | ★★☆☆☆ | Registry proposal is solid; storyboard has core branches |
| Council | ★★★★★ | ★★★★☆ | Clean separation from CMO loop; memory integration pending |
| Pi integration | ★★★★★ | ☆☆☆☆☆ | Plan is realistic; not started |

---

## Bottom Line

The architecture is sound. The vision is coherent. The BITE methodology is genuinely good. But the implementation has accumulated technical debt at the most critical boundary — the chat handler.

The gap between the 100-line target and the 2,354-line reality is not a minor drift; it's the difference between a system that can absorb new capabilities without core changes and one that can't.

The hook system, native tool calls, and the Generic Workflow Registry are the three structural pieces that close this gap. **Ship them in that order.**
