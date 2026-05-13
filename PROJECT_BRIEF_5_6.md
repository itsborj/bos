# BOS — Business Operating System
## Unified Project Brief

**Date:** 2026-05-04
**Status:** Phase 3 in progress — architecture refinement, UI wireframes validated
**Version:** 1.1

---

## 1. What We're Building

A self-hosted business operating system that runs on a per-user VPS. Users interact through a web UI, a chat agent, or a raw API — the system doesn't care which. The marketing vertical ships first. The architecture is designed from day one to support additional verticals without rewrites.

The long-term form is SaaS. The mid-term form is a deployable application — one command, any VPS, owned infrastructure, managed feel. Think Coolify or Twenty CRM, not Salesforce.

**Core mental model:** The BOS is a company communicated through messaging. Not dashboards, not admin panels — organizational reporting upward.

---

## 2. The Core Thesis

**The BOS knows your business. You don't repeat yourself.**

A traditional API platform is stateless — you send context with every call. A business operating system holds your context: your brand, your products, your customers, your campaigns. Every module run draws from that workspace automatically. You specify what changes, not what stays the same.

**Modules declare intent. The platform chooses execution.**

A module for writing a Facebook ad knows it needs copywriting. It does not know which LLM runs it, which provider is cheapest today, or whether the user is on a BYOK plan. That is the platform's problem.

**The BITE framework governs all handoffs.**

Every layer boundary in the system follows the same four-part contract:

- **Bridge** — the contract stays small. Schemas are strict; payloads are minimal. Data must be easy to extend without breaking anything downstream. A bridge that grows business logic has failed its job.
- **Intent** — the BOS decides what runs, against which workspace context, routed to which capability. The BOS thinks; it does not execute. Intent lives in the orchestrator, not in modules or clients.
- **Transform** — each module executes exactly one highly-specialised skill. Copywriting today; text-to-audio, text-to-image, text-to-video, analytics tomorrow. Modules are sealed pipelines: a crash in one cannot propagate to another. The smallest possible surface area is the goal.
- **Evaluate** — the final gate. Output does not leave the system without passing self_check. As the system matures, Evaluate becomes its own dedicated layer with shared validators across all modules — not re-implemented inside each one.

---

## 3. What's Different From the POC

The `~/cl_dm_os/` directory holds two validated POCs (DM-OS and Routing Lab). They are frozen reference material. This project throws away the code and keeps the patterns:

| POC got right | POC got wrong |
|---|---|
| Module independence (file = module) | Two systems built separately, integrated after |
| BITE envelope for handoffs | SQLite — not viable for real deployment |
| Capability-based routing | No persistent business context |
| Billing orthogonal to execution | No real frontend |
| Mock-first validation | No multi-interface design |
| Fault isolation at module boundaries | BYOK not considered |
| | No Intent contract storage |
| | No Stream reporting layer |

---

## 4. The Workspace Layer (What Was Missing)

The POC had no memory of your business. This rebuild centers on a persistent workspace:

```
workspace
  ├── brand
  │     voice, tone, values, visual guidelines
  ├── products
  │     name, tagline, key benefits, positioning per product
  ├── audiences
  │     segments, demographics, pain points
  └── campaigns
        active briefs, module run history, linked outputs, intent contracts
```

Every module run resolves against the active workspace. A user running `marketing.ad_copy.facebook` does not need to pass `product_name` or `tone` if those are already in the workspace. The brief becomes a diff — specify only what changes from the baseline.

**Critical:** Workspace context is not manually configured via forms. The user provides marketing brief documents (text, PDFs, slide decks). CMO AI continuously updates workspace context from these documents. The workspace is CMO's internal representation of the business, not a user-facing CRUD interface.

Workspace data lives in PostgreSQL from day one. It is the source of truth.

---

## 5. Execution Modes — BYOK + Platform

The platform supports two execution modes. A user may use either, or mix by provider.

### Platform Mode (default)
- BOS routes through its own pooled provider keys
- Full capability matching, fallback, and billing markup apply
- User pays the platform's sell price
- Recommended for users who don't want to manage API keys

### BYOK Mode (Bring Your Own API Key)
- User registers their own key for one or more providers
- Keys are stored encrypted in their PostgreSQL instance, never logged
- Executor uses the user's key; platform keys are not touched
- Billing: token usage is tracked for the user's awareness; no sell_price markup (user pays provider directly)
- Routing: capability matching still applies, but candidates are limited to providers where the user has a registered key

Both modes use the same module system, the same prompt templates, the same BITE envelope contract. The difference is only at the executor level.

---

## 6. Interface Layer

Three interfaces. One API. No interface owns business logic.

```
Web UI          Chat Bridge        REST API (headless)
   │                │                    │
   └────────────────┼────────────────────┘
                    │
              POST /runs
              GET  /stream
              GET  /workspace
              ...  (same endpoints for all three)
```

All three are bridge clients. They live in `clients/` (or `web/` for the UI), outside BOS core. The BOS API is the only boundary they cross.

### The Three-Tab Experience (Mobile + Web)

**UI Implementation target:** The agreed wireframes in `sample/` are the design source of truth for both the web and mobile experiences. The React app (`web/`) must replicate those wireframes as a single responsive application — the web wireframe (`DONT_USE_ui_wireframe_web.html`) drives the desktop layout, the mobile wireframe (`DON'T_USE_ui_wireframe.html`) drives the mobile layout. Color palettes from the wireframes are stripped; neutral/minimal colors are used instead. Structure, layout, components, and interaction patterns must match.

The same interface structure exists on both mobile and web. Viewport width changes, fundamental interaction model doesn't.

| Tab | Mental Model | What It Shows |
|---|---|---|
| **Stream** | Organization reporting upward | Briefing blocks (typed containers): status updates, performance metrics, alerts, recommendations. Feed terminates when decisions are made. |
| **CMO** | Owner directing organization | Pure conversational interface. User instructs, CMO activates modules, coordinates execution, requests clarification. CMO speaks organizationally — never exposes modules, providers, or pipelines. |
| **Workspace** | Organizational memory | Campaign archive, active campaigns, pinned assets, past campaigns. Asset viewer for drill-down. Read-only browsing; changes requested via CMO. |

**UI Design Principles:**
- **Single focus** — one dominant thing per screen, one action, one insight. No split views, no sidecars.
- **Push intelligence / pull detail** — system reaches out with briefs; full detail is one tap away.
- **No hard buttons in CMO** — all instructions via conversation. Assets surfaced as link previews (`Open in Workspace →`).
- **Feed terminates** — Stream ends when decisions are made. BOS releases attention; it does not compete for it.
- **Organizational voice everywhere** — CMO generates Stream updates that feel authored, not system-generated. "Q2 Launch is performing above projections" not "Module completed successfully."

### Settings Hub (Web Only)

Fourth section accessible via settings button. Contains admin functions:
- **Run History** — filterable table, trace detail, debugging
- **Providers** — BYOK key management, provider health
- **Billing** — cost tracking, budget limits, per-run breakdown
- **Modules** — module health status, success rates, latency

Settings is reporting and system administration. It does not contain workspace configuration forms.

### Chat Bridge

Any process that receives a user message, translates it to a BOS API call, and returns the result. The BOS does not know or care what the caller is. Current candidates:
- `clients/claude/` — Python script; Claude agent calls `POST /runs`, formats result for user
- `clients/whatsapp/` — Node.js process using Baileys (WhatsApp Web WebSocket API); receives WhatsApp message → `POST /runs` → replies. Thin bridge: ~100 lines. No business logic inside.

The bridge stays small. Intent, Transform, and Evaluate all live in BOS, not in the bridge.

### REST API

Headless mode. Any external tool, script, or future workflow engine can call the API directly. Eventually the primary product interface.

---

## 7. System Layers (BITE-annotated)

```
── BRIDGE ──────────────────────────────────────────────────────
  clients/web        Web UI (React + Vite)
  clients/claude/    Claude agent (Python, calls REST API)
  clients/whatsapp/  Baileys bridge (Node.js, optional)
  api/routers/       REST API surface — the only BOS boundary
  api/schemas/       Pydantic contracts — strict, minimal

── INTENT ──────────────────────────────────────────────────────
  api/auth.py              workspace identity
  api/registry.py          module discovery (directory scan)
  api/capability_router.py maps module capability → ranked candidates
  api/executor.py          orchestrates: context → module → provider
                           BOS thinks here. It does not execute.
  api/intent/              Intent contract storage and versioning
    contracts.py           CRUD for intent contracts
    evaluator.py           loads intent, applies criteria

── TRANSFORM ───────────────────────────────────────────────────
  api/modules/{vertical}/{module}.py   sealed pipeline per skill
    marketing.ad_copy.facebook         ┐
    marketing.ad_copy.twitter          │  each fails independently
    marketing.ad_copy.google           │  smallest possible surface
    marketing.email.cold_outreach      │  area; no shared state
    future: text-to-audio              │
    future: text-to-image              │
    future: text-to-video              ┘
  api/templates/{vertical}/*.j2        prompt inputs to Transform
  api/providers/{adapter}.py           execution substrate
    openrouter | gemini | nvidia | ...

── EVALUATE ────────────────────────────────────────────────────
  self_check (currently embedded in each module)
    max_chars, must_mention, banned_phrases
  future: api/evaluate/                shared validators (Phase 4+)
    output does not leave the system without passing this gate

── STREAM GENERATION ───────────────────────────────────────────
  api/stream/              briefing block generation
    generators/            content generators per block type
    types.py               block type registry
    builder.py             assembles daily stream

── DATA ────────────────────────────────────────────────────────
  PostgreSQL
    workspaces | products | audiences | campaigns
    runs | run_attempts | run_results | run_traces
    capabilities | model_options | provider_keys | api_keys
    intent_contracts | campaign_intents | module_criteria
    stream_updates | escalations
```

---

## 8. Stream Architecture

The Stream is not a feed of predefined cards. It is a transport surface for typed organizational messages.

### Briefing Block Primitive

```typescript
interface BriefingBlock {
  id: string;
  timestamp: string;
  
  // Routing/importance
  priority: "urgent" | "high" | "normal" | "low";
  category: "decision_needed" | "performance" | "status" | "recommendation";
  
  // Rendering hints (not rigid schemas)
  layout_hint: "compact" | "media" | "table" | "alert" | "narrative";
  interaction: "passive" | "expandable" | "actionable";
  
  // Opaque payload (Stream doesn't parse this)
  content: any;
  
  // Optional workspace linking
  campaign_id?: string;
  asset_id?: string;
}
```

**Stream rules:**
- Ordered by **importance and urgency**, not chronology
- Blocks are **self-contained** — understandable independently
- Content feels **authored**, not templated
- Feed **terminates** when decisions are made
- Natural **variance** in block height/format

**Block types are extensible.** Adding a new update type = registering a new generator, no Stream code changes.

### Content Generation

Stream updates are generated by LLM with organizational prompting:

```python
def generate_campaign_update(campaign: Campaign) -> str:
    prompt = """
    You are the CMO reporting to the CEO via Slack.
    
    Campaign: {campaign.name}
    Performance: {campaign.metrics}
    Status: {campaign.status}
    
    Write a 2-3 sentence update. Tone: professional but conversational.
    Focus on: decisions needed, anomalies, or strategic observations.
    Never mention: modules, providers, technical infrastructure.
    """
    
    return llm.generate(prompt)
```

---

## 9. Module Contract

A module is a file. Adding a module = creating one file in the correct vertical directory. No other files change.

```
module
  id:               marketing.ad_copy.facebook
  vertical:         marketing
  capability:       marketing.copywriting
  platform_hint:    facebook
  policy_default:   balanced

  input_schema:     BriefPayload   (workspace fields + overrides)
  output_schema:    AdCopyPayload
  prompt_template:  templates/marketing/facebook_ad.j2

  self_check:
    max_chars:      2200
    must_mention:   [product_name]
    banned_phrases: []
  
  health():         returns module health status for routing
```

A module does four things:
1. Resolves brief from workspace + any per-run overrides
2. Calls the executor (platform or BYOK)
3. Wraps result in output envelope, runs self_check
4. Reports health status for capability router

A module does NOT select a provider, manage keys, compute billing, or know about other modules.

### Module Health Checks

```python
def health(self) -> dict:
    return {
        "status": "healthy" | "degraded" | "down",
        "latency_ms": self._avg_latency(),
        "last_success": self._last_success_timestamp(),
        "provider_dependency": "openrouter",
        "fallback_available": True
    }
```

Capability router uses this to route around failures.

---

## 10. Intent Contract Storage

CMO writes Intent contracts when CEO specifies campaign goals. These are versioned, testable acceptance criteria.

### Intent Contract Schema

```json
{
  "id": "seasonal_launch_v1.2",
  "version": "1.2.0",
  "description": "Seasonal product launch campaign",
  "evaluator": "multi_tier_marketing_eval",
  
  "criteria": [
    {
      "id": "brand_voice_compliance",
      "field": "payload.artifacts.copy",
      "rule": "matches_brand_voice_profile",
      "threshold": 0.85,
      "type": "hard",
      "owner": "marketing.ad_copy.*",
      "severity": "blocking"
    },
    {
      "id": "engagement_prediction",
      "field": "payload.artifacts.copy",
      "rule": "predicted_engagement_rate",
      "threshold": 0.6,
      "type": "soft",
      "severity": "warning"
    }
  ],
  
  "scoring": {
    "method": "all_hard_must_pass",
    "soft_pass_cutoff": 0.7
  },
  
  "on_pass": "advance",
  "on_fail": "retry",
  "on_escalate": "cmo_review_queue",
  "max_attempts": 3
}
```

When user says "make it more playful," CMO creates/updates Intent with new thresholds:

```python
# CMO action
intent = get_intent("seasonal_launch_v1.2")
new_version = intent.create_override(
    campaign_id="q2_launch",
    overrides={
        "tone_playfulness": 0.8,  # higher than template default
        "must_mention": ["summer sale"],
    }
)
store_campaign_intent(campaign_id, new_version)
```

---

## 11. API Surface

```
# System
GET  /                              health, version
GET  /verticals                     registered verticals + module counts
GET  /capabilities                  capability profiles

# Stream
GET  /stream                        briefing blocks for workspace
POST /stream/{update_id}/read       mark update as read
DELETE /stream/{update_id}          dismiss update from feed

# Workspace
GET  /workspace                     current workspace state
PUT  /workspace/brand               update brand context (via CMO)
PUT  /workspace/products            update product catalog (via CMO)
PUT  /workspace/audiences           update audience segments (via CMO)

# Campaigns
GET  /campaigns                     active + past campaigns
GET  /campaigns/{campaign_id}       campaign detail + assets
POST /campaigns                     create campaign (via CMO)
PUT  /campaigns/{campaign_id}/intent override Intent criteria

# Modules
GET  /verticals/{vertical}/modules  modules in a vertical
GET  /modules/{module_id}           module detail + schema
GET  /modules/{module_id}/health    module health status

# Runs
POST /runs                          trigger a module run
GET  /runs                          run history (filterable)
GET  /runs/{run_id}                 full trace: routing, attempts, billing

# Providers
GET  /providers                     registered providers + health
POST /providers/keys                register a BYOK key (encrypted at rest)
DELETE /providers/keys/{provider}   remove a BYOK key
POST /providers/check               verify key + connectivity

# Billing
GET  /billing/summary               cost + revenue summary
GET  /billing/runs/{run_id}         per-run billing breakdown

# Intent (Phase 4+)
GET  /intents                       intent contract templates
GET  /intents/{intent_id}           intent contract detail
POST /intents                       create new intent contract
```

---

## 12. Data Layer

PostgreSQL from day one. No SQLite bridge, no migration later.

```sql
-- Core tables
workspaces        id, name, brand_json, created_at
products          id, workspace_id, name, tagline, benefits_json
audiences         id, workspace_id, name, segment_json
campaigns         id, workspace_id, name, status, created_at

-- Intent system (NEW)
intent_contracts  id, contract_type, version, criteria_json, scoring_json, created_at
campaign_intents  id, campaign_id, intent_contract_id, overrides_json, active
module_criteria   id, module_id, criterion_id, field, rule, threshold_json, type

-- Execution
provider_keys     id, workspace_id, provider, key_encrypted, created_at
capabilities      id, key, modality, budget_ceiling, latency_target_ms
model_options     id, capability_id, provider, model_id, cost_per_token, quality_tier

runs              id, workspace_id, module_id, campaign_id, status, created_at
run_attempts      id, run_id, provider, model_id, status, tokens, provider_cost
run_results       id, run_id, content, self_check_verdict, sell_price
run_traces        id, run_id, routing_json, lineage_json, feedback_json

-- Stream system (NEW)
stream_updates    id, workspace_id, campaign_id, type, data_json, priority, created_at, read_at, dismissed_at

-- Escalations (NEW)
escalations       id, run_id, campaign_id, reason, escalated_at, resolved_at, resolution
```

---

## 13. Deployment Shape

```
cl_bos/
├── api/                        BOS core (Python, FastAPI)
│   ├── modules/                [TRANSFORM] one file per module, by vertical
│   │   └── marketing/
│   ├── templates/              prompt inputs (Jinja2), by vertical
│   │   └── marketing/
│   ├── providers/              execution substrate, one file per provider
│   ├── schemas/                [BRIDGE] Pydantic contracts
│   ├── routers/                [BRIDGE] HTTP surface
│   ├── stream/                 [NEW] briefing block generation
│   │   ├── generators/
│   │   ├── types.py
│   │   └── builder.py
│   ├── intent/                 [NEW] Intent contract management
│   │   ├── contracts.py
│   │   └── evaluator.py
│   ├── capability_router.py    [INTENT] routing logic
│   ├── executor.py             [INTENT] orchestrator
│   ├── migrations/             Alembic schema versions
│   └── tests/                  mirrors modules/ structure exactly
│
├── web/                        [BRIDGE] Web UI (React + Vite)
│   └── src/
│       ├── api/                thin REST wrapper
│       ├── pages/              Stream / CMO / Workspace / Settings
│       ├── components/
│       └── tests/
│
├── clients/                    [BRIDGE] thin callers
│   ├── claude/                 Python: Claude agent → POST /runs
│   └── whatsapp/               Node.js (Baileys): WA message → POST /runs
│
├── docker-compose.yml
├── nginx.conf
└── .env.example
```

---

## 14. Phase Map

### Phase 0 — Foundation ✓
- [x] POC learnings extracted
- [x] Unified project brief (this document)
- [x] System shape sample agreed
- [x] Repo initialized, CLAUDE.md written
- [x] docker-compose.yml skeleton
- [x] PostgreSQL schema v1 + migrations
- [x] FastAPI skeleton with health endpoint

### Phase 1 — Core API + Data Layer ✓
- [x] Workspace CRUD (brand, products, audiences)
- [x] Module registry (marketing vertical, 3 modules)
- [x] Capability profiles in PostgreSQL
- [x] `POST /runs` end-to-end in mock mode
- [x] Run history + trace storage
- [x] Basic auth (API key per workspace)

### Phase 2 — Provider Layer + BYOK ✓
- [x] OpenRouter live adapter (platform mode)
- [x] BYOK key registration + encrypted storage
- [x] BYOK execution path
- [x] Billing ledger (provider cost + sell price)
- [x] Provider health checks

### Phase 3 — Frontend + Stream (active)
- [x] UI wireframes validated — Stream/CMO/Workspace + Settings
- [x] Stream architecture defined — briefing block system
- [x] CMO organizational voice guidelines
- [ ] Intent contract storage (tables + API)
- [ ] Stream generation (block generators)
- [ ] Web UI implementation (React + Vite)
- [ ] Chat agent integration (thin caller using the API)

### Phase 4 — Marketing Vertical Complete
- All planned marketing modules
- Campaign management with Intent contracts
- Brief templates drawing from workspace context
- Module health checks and routing
- Evaluate layer extraction (shared validators)
- Output export (copy-paste ready per platform)
- Frontend + API testing (component tests, integration, contract)

### Phase 5 — Hardening + Second Vertical
- Retry with structured feedback
- Escalation queue and resolution
- Rate limiting, quotas
- Second vertical (finance or HR)
- Deployment packaging (one-command VPS setup docs)

---

## 15. Non-Goals (This Version)

- No multi-tenancy. One workspace per deployment. SaaS tenancy is a later architectural addition.
- No workflow chaining between modules. Modules are single-step.
- No agentic orchestration inside the BOS. Agents are clients, not services.
- No mobile app (native). Web UI is mobile-first responsive.
- No fine-tuning infrastructure.
- No A/B testing or variant generation per module.
- No manual workspace configuration forms. Workspace updated via CMO conversation and document uploads.

---

## 16. What Success Looks Like at Each Phase Gate

**Phase 1 gate:** A module run triggered via `curl`, stored in PostgreSQL, retrievable with full trace. No provider call yet (mock). Workspace context flows into the run.

**Phase 2 gate:** A real Facebook ad written by OpenRouter via a real brief, using either platform keys or the user's own key. Both paths produce the same output shape.

**Phase 3 gate:** User opens the interface (mobile or web), reads Stream briefing blocks, tells CMO "launch Q2 campaign focused on operational simplicity," CMO writes Intent contract and activates modules, user reviews assets in Workspace. All via the 3-tab UI.

**Phase 4 gate:** Full marketing workflow — CMO receives campaign brief document → updates workspace → writes Intent contract → activates all platform modules → outputs ready for publishing. Module failures route around gracefully (sick employee pattern).

---

## 17. Key Architectural Decisions

### Why Stream is Organizational Communication
Traditional dashboards are pull-based: user must know what to look for. Stream is push-based: the system tells you what needs attention. The BOS appears as a functioning organization, not software.

### Why CMO Never Exposes Infrastructure
When CMO says "calling marketing.ad_copy.twitter," it breaks the organizational illusion. The user should experience the BOS as a marketing department, not as a technical system. Infrastructure invisibility is a design principle, not an implementation detail.

### Why Workspace is Document-Based
Manual form-filling scales poorly for multi-product businesses. A solo founder might manage 3 products via forms. A 50-person company has 20+ products. Document-based context lets CMO extract structure from existing marketing materials (pitch decks, brand guides, positioning docs).

### Why Intent Contracts are Versioned Data
If Intent is code, changing acceptance criteria requires deployments. If Intent is versioned data, CEO can say "make ads more playful" and CMO updates the contract without touching the pipeline. This enables non-technical strategic control.

### Why Modules Report Health
The router needs to know which modules are available before dispatching. Health checks enable "sick employee" resilience — the system continues with reduced capability rather than failing entirely.

---

## 18. Reference

- POC (frozen): `~/cl_dm_os/` — DM-OS pipeline + Routing Lab
- Mobile wireframe: `sample/DON'T_USE_ui_wireframe.html` — source of truth for mobile (Stream/CMO/Workspace tabs, bottom nav)
- Web wireframe: `sample/DONT_USE_ui_wireframe_web.html` — source of truth for desktop (sidebar + main + CMO rail, 5 screens)
- BITE framework: `BITE_framework.md`
- Patterns carried forward: module independence, BITE envelope, capability routing, billing separation, mock-first validation