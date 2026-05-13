# BOS v1 — System Shape Sample

**Tier:** T2 — Mock (real shape, no code)
**Date:** 2026-05-01
**Purpose:** agree on system boundaries before any spec is written

---

## The System in One Diagram

```
╔══════════════════════════════════════════════════════════════════╗
║  INTERFACE LAYER  (all call the same API — none own logic)      ║
║                                                                  ║
║  ┌─────────────┐   ┌─────────────────────┐   ┌───────────────┐  ║
║  │   Web UI    │   │   Chat Agent        │   │  REST API     │  ║
║  │  (browser)  │   │  (Claude / agent)   │   │  (headless)   │  ║
║  └──────┬──────┘   └──────────┬──────────┘   └───────┬───────┘  ║
╚═════════╪════════════════════╪═══════════════════════╪══════════╝
          │                    │                       │
          └────────────────────┼───────────────────────┘
                               │  HTTP  (same API for all three)
╔══════════════════════════════╪═══════════════════════════════════╗
║  BOS CORE                   ▼                                   ║
║                                                                  ║
║  ┌───────────────────────────────────────────────────────────┐   ║
║  │  Module Registry                                         │   ║
║  │                                                          │   ║
║  │  vertical: marketing                                     │   ║
║  │    marketing.ad_copy.facebook                            │   ║
║  │    marketing.ad_copy.twitter                             │   ║
║  │    marketing.ad_copy.google                              │   ║
║  │    marketing.email.cold_outreach                         │   ║
║  │    ...                                                   │   ║
║  │                                                          │   ║
║  │  vertical: finance          ← not built yet, slot exists │   ║
║  │  vertical: hr               ← same                       │   ║
║  └───────────────────────────────┬───────────────────────────┘   ║
║                                  │ BriefEnvelope                  ║
║  ┌───────────────────────────────▼───────────────────────────┐   ║
║  │  Capability Router                                       │   ║
║  │                                                          │   ║
║  │  module declares:  capability = "marketing.copywriting"  │   ║
║  │                    policy     = "balanced"               │   ║
║  │                                                          │   ║
║  │  router resolves:  eligible providers → ranked list      │   ║
║  │                    winner:  openrouter / claude-haiku    │   ║
║  └───────────────────────────────┬───────────────────────────┘   ║
║                                  │ RouteEnvelope                  ║
║  ┌───────────────────────────────▼───────────────────────────┐   ║
║  │  Executor                                                │   ║
║  │                                                          │   ║
║  │  attempt 1 → winner provider  ──→ success                │   ║
║  │  attempt 2 → fallback          (only if attempt 1 fails) │   ║
║  │                                                          │   ║
║  │  on success: writes ResultEnvelope                       │   ║
║  │  on total failure: writes FailedEnvelope (structured)    │   ║
║  └───────────────────────────────┬───────────────────────────┘   ║
║                                  │                                ║
║  ┌───────────────────────────────▼───────────────────────────┐   ║
║  │  Billing Ledger  (orthogonal to execution)               │   ║
║  │                                                          │   ║
║  │  provider_cost  = raw API cost per attempt               │   ║
║  │  sell_price     = provider_cost × markup                 │   ║
║  │  failed runs    = no sell_price charged                  │   ║
║  └───────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════╝
                               │
╔══════════════════════════════╪═══════════════════════════════════╗
║  PROVIDER ADAPTERS          ▼                                   ║
║                                                                  ║
║   OpenRouter    Anthropic    OpenAI    Gemini    NVIDIA    ...   ║
║   (text)        (text)       (text)    (text)    (text)          ║
║                                                                  ║
║   StabilityAI   Replicate    Fal.ai                             ║
║   (image)       (image)      (image)                            ║
║                                                                  ║
║   ElevenLabs    Deepgram                                        ║
║   (audio/tts)   (transcription)                                 ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Module Contract

A module is a file. Adding a module = creating one file. Nothing else changes.

```yaml
# modules/marketing/ad_copy_facebook.py  ← file IS the module

id:               marketing.ad_copy.facebook
vertical:         marketing
capability:       marketing.copywriting
platform_hint:    facebook
policy_default:   balanced

input:            BriefPayload
output:           AdCopyPayload
prompt_template:  templates/marketing/facebook_ad.j2

constraints:
  max_chars:      2200
  must_mention:   [product_name]
  banned_phrases: []
```

The module does three things and nothing else:
1. Assembles prompt from `BriefPayload` using its template
2. Calls the router (`POST /runs` internally)
3. Wraps the result in `AdCopyPayload` and runs `self_check`

The module does NOT know which provider ran. It does NOT know which model was selected. It does NOT touch billing.

---

## API Surface

One API. All three interfaces (web, chat, headless) call this.

```
# Discovery
GET  /                              → version, health, uptime
GET  /verticals                     → list of registered verticals
GET  /verticals/{vertical}/modules  → modules in a vertical
GET  /capabilities                  → capability profiles
GET  /providers                     → registered providers + health

# Execution
POST /runs                          → trigger a module run (main operation)
GET  /runs                          → run history (filterable by vertical, module, status)
GET  /runs/{run_id}                 → full run trace: routing decisions, attempts, billing

# Provider management
POST /providers/check               → verify API key + connectivity
GET  /providers/catalog             → cached model metadata per provider

# Billing
GET  /billing/summary               → cost + revenue summary (filterable by date, vertical)
GET  /billing/runs/{run_id}         → per-run billing breakdown
```

---

## The Two Key Envelopes

### What a caller sends to `POST /runs`

```json
{
  "module_id": "marketing.ad_copy.facebook",
  "policy": "balanced",
  "payload": {
    "brief": {
      "product_name": "Notion",
      "tagline": "Your connected workspace",
      "audience": "remote teams",
      "tone": "conversational",
      "key_benefit": "everything in one place"
    },
    "constraints": {
      "max_chars": 2200,
      "must_mention": ["Notion"],
      "banned_phrases": []
    }
  }
}
```

### What `POST /runs` returns on success

```json
{
  "run_id": "run_20260501T142300_a3f9b1",
  "module_id": "marketing.ad_copy.facebook",
  "vertical": "marketing",
  "status": "success",
  "result": {
    "content": "Your team's second brain just got smarter...",
    "self_check": "pass",
    "platform": "facebook"
  },
  "execution": {
    "provider": "openrouter",
    "model": "anthropic/claude-3-haiku",
    "attempts": 1,
    "latency_ms": 1840,
    "tokens_used": 312,
    "provider_cost": 0.000187,
    "sell_price": 0.000253
  },
  "trace": {
    "capability": "marketing.copywriting",
    "policy": "balanced",
    "candidates_considered": 4,
    "candidates_filtered": 1,
    "winner": "openrouter/anthropic/claude-3-haiku",
    "routing_reason": "balanced score: cost 0.4 + quality 0.35 + latency 0.25"
  }
}
```

---

## Deployment Shape

One command on any VPS. No cloud dependency.

```
bos/
├── api/              ← BOS core (Python, FastAPI)
├── web/              ← dashboard UI (optional, can be omitted for headless)
├── modules/          ← one file per module, organized by vertical
│   └── marketing/
│       ├── ad_copy_facebook.py
│       ├── ad_copy_twitter.py
│       └── ad_copy_google.py
├── templates/        ← prompt templates, one per module
│   └── marketing/
├── providers/        ← one adapter file per provider
│   ├── openrouter.py
│   ├── anthropic.py
│   └── gemini.py
├── docker-compose.yml
├── .env.example
└── nginx.conf

# docker-compose.yml services:
#   api      → BOS core on :8000
#   db       → PostgreSQL 16
#   web      → dashboard UI on :3000 (optional)
#   nginx    → reverse proxy on :80 / :443
```

The chat agent (Claude, GPT, any agent) is NOT a service in the compose stack. It is a client. It calls `POST /runs` the same way the web UI does. The BOS is agnostic to who calls it.

---

## What This Is Not

- Not a SaaS yet. No multi-tenancy. One instance per VPS per user/org.
- Not a workflow engine. Modules are single-step. Chaining is deferred.
- Not an agent framework. The BOS executes modules; it does not orchestrate agents.
- Not a publishing platform. Outputs are API responses and stored run records.
- The chat interface is a thin caller. It does not live inside the BOS.

---

## The One Test This Sample Must Pass

Run one module end-to-end via all three interfaces:

```
# Same operation, three callers:

curl -X POST /runs -d '{"module_id": "marketing.ad_copy.facebook", ...}'
→ returns AdCopyPayload

web UI "Run module" button
→ shows same result in dashboard

chat agent: "write a facebook ad for Notion"
→ agent calls POST /runs, returns same content to user
```

Same result. Same run record. Same billing entry. Different interface.

If this passes, the interface-agnostic principle is proven and the system shape is correct.
