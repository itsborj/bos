# BOS — Business Operating System
## Unified Project Brief

**Date:** 2026-06-04
**Status:** Phase 6 in progress — Strategy Workflow fully live; CMO GTM/marketing-plan dispatch fixed; workflow page header contrast fixed; public lead-capture demo direction parked
**Version:** 3.51 (public website-to-plan lead-capture mini brief added; parked until revisited. Critical constraint: the public demo must call/reuse the internal `marketing.planning.strategy_workflow` capability server-side, not recreate a second public planning capability.)

> **MANDATORY READING:** Before any new system update, feature build, or architectural change, read `BITE.md`. It is both the Business Implementation by Example methodology and the BOS architecture constitution for minimal core, plugin/package extensibility, SKILL.md ownership, live manifests, MCP boundaries, lifecycle hooks, and command registration.
---

## ⚑ Current State & Locked Architecture

> **Read this before making any change.** These decisions are final. Reversing any item requires an explicit architectural review and update to this table. The historical changelog now lives in Appendix A; it is a record, not the active architecture source.

### Active Phase (as of 2026-06-04)
- **Phase:** Phase 6 — Full-Stack Marketing Automation
- **Gate 2:** Passed 2026-05-20 (Gmail-only objective loop end-to-end proved via `api/scripts/prove_gate2_gmail_loop.py`)
- **Current UI surface:** Stream (60%) + CMO chat (40%) split-screen. `CmoChat` is mounted at Layout shell level and persists across navigation (hidden via `display:none` when not on /cmo). Mobile = single-panel with `translateX` slide transition. Reference: `wireframes/bos-stream-first.html` (read-only design spec — do not modify).
- **Council:** Fully operational in CMO chat as of 2026-06-02. `@council <question>` → live boardroom in chat with collapsible per-seat round cards, C6 inject/Continue/Finalize, settled brief with settlement + marching orders + expandable transcript. 6-round test verified. See `BACKLOG.md ## Council` for full status and remaining work.
- **Planning:** `marketing.planning.strategy_workflow` is the sole plan module as of 2026-06-04. `marketing.planning.gtm_plan` is **retired** (`status: retired`, `allowed_from_chat: false`) — do not re-enable. `marketing.plan.campaign_strategy` is also retired. All CMO chat GTM/launch/strategy/marketing-plan requests route to `marketing.planning.strategy_workflow`. The Strategy Workflow decomposes the plan into 10 independently revisable components with typed JSON output contracts, archetype weighting (golden_gate / gold_smelting / teko / direct_sales), and a cascade model. Each run persists a `WorkflowRun` record with `WorkflowComponent` rows. `StrategyWorkflowPage` at `/strategy-workflows/:workflowId` fetches live data from `GET /strategy-workflows/:id` (including `brand_name`) and renders the dark header as `{BrandName} Marketing Strategy` with white text. Prototypes at `/prototype/strategy-draft`, `/prototype/golden-gate-plan`, `/prototype/motormoto` remain as static reference builds only. Pre-build contract: `STRATEGY_WORKFLOW.md`. Read before touching any strategy workflow capability or component module.
- **Public lead-capture demo:** Parked mini-project in `PUBLIC_LEAD_CAPTURE_DEMO.md`. Direction: a public website/PDF/text intake can create a provisional Business Profile Draft, allow public correction chat, then call the existing internal Strategy Workflow server-side for a Marketing Plan Preview. It must not duplicate/recreate planning prompts or output logic outside the logged-in BOS capability. The rough HTML at `sample/public_website_to_plan_demo_klaroha.html` is a visual/conversation artifact only, not an approved implementation sample.
- **Next active work:** Council memory integration (approved settlement → MemoryEvent), re-enable C3–C5 seats with diverse models. Then: not-wired strategy workflow components (`market_context`, `framework_lenses`, `channel_content_matrix`, `measurement_model`). Then Phase 6 subsections (creative bundle, shortform video, social publishing).

### Phase 6 Loop Direction — Summary

Klaroha is not becoming a generic chat agent or coding harness. Phase 6 applies pi-style agent loop mechanics inside BOS's business/marketing operating system for an overloaded business leader or marketing operator managing multi-brand, omni-channel work.

Two loops are distinct:
- **CMO execution loop:** fast plan/execute/optimize steering; specialists create Stream artifacts; CMO synthesizes only after specialist results return; operator approves/revises/dismisses; memory closes the optimization loop.
- **Council deliberation loop:** explicit `@council <question>` invocation for high-stakes judgment — GTM strategy, brand redesign, quarterly budget allocation, major positioning shifts, persistent disagreement. Deliberation runs as a live boardroom conversation in CMO chat: round cards per seat (collapsible), C6 (operator) injects or passes between rounds, Finalize extracts settlement + marching orders + parked decisions from transcript. Seats are backed by different LLMs; the divergence is the value. The settled brief is the canonical output. Detail in `sample/bos_council_brief_planning.md`.

Default creative production should run in parallel from a shared campaign brief for speed, with sequential chaining reserved for brand risk, compliance, high-ticket/long-sales-cycle dependency, failed self-checks, or Council recommendation. Details and code-dev marching orders live in `api/routers/chat_notes.md`.

### Locked Rules — Topic by Topic

| # | Topic | ✓ Current (locked) | ✗ Do Not Revert To |
|---|---|---|---|
| 1 | **CMO routing** | LLM reads `capability_manifest.py`; zero routing logic in `chat.py` | `_explicit_platforms()`, `_is_broad_sample_ads_request()`, `_has_generation_intent()`, `_requested_module_ids()`, phrase-matching — all removed 2026-05-12 |
| 2 | **Channel capabilities** | `api/plugins/{channel}/` only | `api/capabilities/marketing/channel/` — deleted; must never be recreated |
| 3 | **CMO artifact output** | Chat returns artifact refs/links only; Workspace + Stream own native preview, approval, revision | Inline Subject/Body, Headline/Description, copy, targeting, budgets, fake proof in CMO chat replies |
| 4 | **Brand dispatch** | `_brand_scoped_brief(db, ws, active_brand, overrides)` when `brand_id` is set | `_resolve_brief(db, ws, overrides)` in an active-brand context (causes cross-brand bleed) |
| 5 | **Brand memory hydration** | `hydrate_memory_slots(brand=active_brand)` — filters products, audiences, docs, run memory by `brand_id` | Workspace-wide memory in active-brand turns |
| 6 | **Brand switching** | Hidden `SCOPE:` directive + `workspace.scope_resolution` SKILL.md | Phrase-matching, hardlock, or brand-name detection in `chat.py` |
| 7 | **Artifact dispatch guard** | Blocks `RUN:` with brand clarification when no Brand can be resolved in multi-brand workspace | `brand_id=NULL` artifact creation in multi-brand workspaces |
| 8 | **CMO product surface** | `marketing.plan`, `marketing.execute`, `marketing.optimize` — collapsed job model | Channel/vendor names (Google Ads, Gmail, Meta, etc.) as primary product nav or capability catalog |
| 9 | **CMO reply style** | Mobile-first: 1–4 short lines, one idea per line, bullets for choices, max one question. Ref: `sample/mobile_cmo_reply_style_v1.md` | Dense paragraphs, pasting full plans or platform content inline |
| 10 | **Capability gate** | `SKILL.md` fields `allowed_from_chat: true`, `triggers`, `excluded_triggers`, `module_id` own activation policy | Hardcoded module ID lists or intent classifiers in `chat.py` / `skills/router.py` |
| 11 | **Plugin credentials** | `inject_channel_credentials()` in `runs.py`; plugins read `brief["_channel_credentials"]` only | Plugins calling `get_settings()` or querying `social_connections` / DB directly |
| 12 | **Capability manifest** | `api/capability_manifest.py` auto-generates from SKILL.md files at runtime | Manual manifest edits; hardcoded module IDs in `_build_system_prompt()` |
| 13 | **`_brand_scoped_brief()` contract** | Builds from overrides + Brand rows only; must not call `_resolve_brief()` first | Calling `_resolve_brief()` as a fallback inside `_brand_scoped_brief()` |
| 14 | **Revise endpoint brand** | Resolves Brand from `original_run.brand_id` before building execution brief | Using workspace context for revision runs |
| 15 | **Plan module** | `marketing.planning.strategy_workflow` is the sole CMO-dispatchable plan module. `marketing.planning.gtm_plan` is retired and must not be re-enabled. | Re-setting `gtm_plan` to `allowed_from_chat: true`; adding any new single-shot GTM plan module that bypasses the WorkflowRun/WorkflowComponent persistence model |

### Key File Ownership
| File | Owns |
|---|---|
| `api/capability_manifest.py` | CMO-dispatchable capability list — generated at runtime from SKILL.md |
| `api/routers/chat.py` | 7-step pipeline only: receive → context → LLM → strip directives → dispatch → persist → return |
| `api/routers/chat_notes.md` | Regression patterns, architecture direction, do-nots for `chat.py` |
| `BITE.md` | Architecture constitution — overrides all conflicting code patterns or stale docs |
| `api/plugins/PLUGIN_SDK.md` | Complete plugin developer contract |
| `api/capabilities/workspace/council/` | CMO Council deliberation layer (post-Gate 2) |
| `CREATIVE_SUPPLY_CHAIN.md` | Creative supply chain mini project brief — concept → primitives → blueprints → render targets → Drive; all detail lives there |
| `sample/creative_factory_ux_v1.md` | Creative Factory user experience documentation — setup, conversation flow, and approval workflow |
| `STRATEGY_WORKFLOW.md` | Strategy Workflow pre-build contract — component DAG, field contracts per component, archetype weight table, cascade rules, workflow record schema, and build prerequisites. Read before touching any strategy workflow capability or component module. |
| `PUBLIC_LEAD_CAPTURE_DEMO.md` | Parked mini project brief for public website/PDF/text → Business Profile Draft → correction chat → Marketing Plan Preview → email/waitlist capture. The public demo must call/reuse `marketing.planning.strategy_workflow` server-side and must not recreate a second marketing-planning capability. |
| `api/models/workflow.py` | `WorkflowRun` + `WorkflowComponent` SQLAlchemy models — one row per strategy run, one component row per component type. |
| `api/routers/strategy_workflows.py` | `GET /strategy-workflows/:id` (full workflow + components + `brand_name`) + `PATCH /strategy-workflows/:id/components/:type` (per-component LLM re-run: routes via `capability_router`, executes live, parses typed component data, cascades stale, bumps version). Not-wired components (`market_context`, `framework_lenses`, `channel_content_matrix`, `measurement_model`) fall back to stale-marking only until their modules are built. |
| `web/src/pages/StrategyWorkflowPage.tsx` | Production strategy workflow page — fetches from `GET /strategy-workflows/:id`, renders all 10 components with live data, locks not-wired components, and shows the header as `{BrandName} Marketing Strategy` in white on the Racing Green header. |

---

---

## 0. Architecture Directive — Strict Plugin Model (Claude Skills + MCP Compatible)

> **This directive supersedes any prior layout described in this brief or in `CLAUDE.md`.** When in doubt, follow this section.

### BOS Core vs. Channel Plugins — Hard Boundary

**BOS core owns the pipeline. Plugins own the channel.**

`api/capabilities/marketing/channel/` **is deleted and must never be recreated.** Every channel Transform node — copy generators, publishers, analytics connectors, comment managers — lives in `api/plugins/{channel}/`. No exceptions.

```
BOS core (api/capabilities/)             Channel plugins (api/plugins/)
─────────────────────────────────────    ──────────────────────────────────
workspace/  ← CMO, plan mode, approval   gmail/           ← outreach draft (BYOK SMTP)
onboarding/ ← brand setup, brand kit     gmail-auth/      ← send + receive (OAuth/brand)
copywriting/← shared copy principles     google-ads/      ← paid search read/draft now; full-control roadmap
workflows/  ← operational checklists     search-console/  ← SEO signals, marketing.optimize
                                         google-calendar/ ← booking pages, availability, iframe widget
                                         test_stub/       ← test harness
```

**Why the boundary matters:**

BOS is the Bridge + Intent + Evaluate layer. Plugins are swappable Transform nodes. If a channel capability lives in `api/capabilities/`, it is coupled to BOS internals and cannot be replaced, versioned, or third-party-owned independently. Once a channel touches `api/providers/`, `api/models/`, or `api/routers/` directly, the boundary is broken.

**Plugin contract (the only things a plugin developer needs to know):**
1. `channel.json` — declares `plugin_id`, `name`, `version`, `requires_social_connection` (list of platforms), `requires_platform_vars`, and `capability_ids`
2. `module.py` — `from klaroha_sdk import ChannelModule` is the ONLY klaroha import allowed
3. `SKILL.md` — same frontmatter contract as first-party skills
4. `template.j2` — Jinja2 template co-located with the capability directory

Credential injection: the host resolves social page tokens and env vars before execution. Plugins read `brief["_channel_credentials"]` — they never call `get_settings()` or query the database.

Developer documentation: `api/plugins/PLUGIN_SDK.md` is the complete guide.

### CMO Capability Registry

`api/capability_manifest.py` is the single source of truth for what the CMO can deploy.

- Generated at runtime from all installed SKILL.md files with `allowed_from_chat: true` and a `module_id`.
- `format_manifest_for_prompt()` produces the deployable capability list injected into the CMO system prompt. Each entry is a `RUN: <module_id>  [Label] — description` line the LLM can copy directly.
- `build_dispatchable_manifest()` returns typed `CapabilityEntry` objects for API use.
- **No hardcoded module IDs, platform names, phrase triggers, or dispatch conditions exist anywhere in `routers/chat.py` or `skills/router.py`.** The LLM reads the manifest and uses its own judgment. Each module's SKILL.md owns its activation policy.
- Adding a new dispatchable capability = add a plugin or capability directory with a valid SKILL.md (`allowed_from_chat: true`, `module_id: <id>`). The manifest and CMO system prompt update automatically on next restart.
- **Target architecture (Phase 4+):** `chat.py` should be a fixed 7-step contract (~100 lines); all cross-cutting concerns (brand-scoping, memory hydration, connector context, `@klar` commands) move into packages subscribing to `bridge.before_transform` and other lifecycle hooks. This eliminates the regression pattern caused by the current monolithic chat endpoint. Full model and BITE mapping: `api/routers/chat_notes.md` § *Architecture Direction — Pi-Pattern Target*.

### First-party capability shape (non-channel only)

```
api/capabilities/{vertical}/{domain}/{atomic_task}/
  SKILL.md         ← Claude skill (auto-discovered)
  module.py        ← BOS Transform node (auto-discovered)
  template.j2      ← Jinja2 prompt template
  validators.py    ← quality gate (optional)
```

### What stays in `api/capabilities/`

| Path | Why first-party |
|---|---|
| `workspace/` | CMO context, plan mode, approval — BOS pipeline contracts |
| `onboarding/` | Brand setup, brand kit — BOS onboarding flow |
| `copywriting/` | Shared copy principles invoked by the pipeline, not a channel |
| `workflows/` | Operational checklists — no module dispatch |
| `internal/` | Internal service delivery (not a marketing channel) |

### What belongs only in `api/plugins/`

| Belongs in plugins | Why |
|---|---|
| Any social/channel publisher | Write action on external platform — must be third-party owned |
| Any copy generator for a named channel | Platform-specific Transform node |
| Any analytics/read connector for a named channel | Platform data, not BOS core data |
| Any comment/inbox manager for a named channel | Platform action, not BOS pipeline logic |

**Native Marketing Planning Specialist:**
`marketing.planning.gtm_plan` is the sole marketing plan module. `marketing.plan.campaign_strategy` is retired (`status: retired`). All plan requests — whether phrased as "marketing plan", "campaign plan", or any GTM/launch shorthand — route to `marketing.planning.gtm_plan`, which enforces the buyer-map + message-architecture substrate chain. Chat stays a short control surface; the plan itself is a persisted Workspace/Stream `plan_artifact` with structured `gtm_strategy` block data for review, revision, approval, or dismissal. `workspace.plan_mode` skill remains as a planning context/resource contract but does not dispatch modules.

**GTM strategic substrate chain:**
`marketing.planning.gtm_plan` is the go-to-market planning artifact for launch/GTM requests, including shorthand like “need GTM” or “another GTM.” It must consume `buyer_map.v1` and `message_architecture.v1`; these are produced by `reasoning.buyer_intelligence` and `marketing.messaging.architecture` as supporting upstream artifacts when no successful prior artifact exists for the active Brand. The CMO must not ask the user to supply internal substrate such as buyer maps, message architecture, or a primary objective when a Brand Brief exists. Run orchestration enforces `required_upstream` generically from `SKILL.md`: load successful prior contract artifact → generate missing producer output → inject actual output → block only if the contract cannot be produced. GTM artifacts render as `GTM Strategy` in Stream; Google Tag Manager only activates on explicit tag-manager/container language, not bare `GTM`.

**Agency app model for social channels:**
One Meta Developer App at the platform operator level. Brands authorize once via OAuth (`pages_manage_posts,pages_show_list,pages_read_engagement`). The system exchanges for a long-lived user token (~60 days), then stores per-page access tokens encrypted per `(brand_id, platform, page_id)`. Brands never manage their own API credentials.

**Brand_id threading through OAuth without schema change:**
`ProviderLoginSession` has no `brand_id` column. Brand ID is encoded into `verifier_encrypted` using a `verifier|brand_id` separator. The callback handler splits on `|` to recover both values.

**`workflows/` — task-based operational checklists:**
```
api/capabilities/workflows/
  client_onboarding/
    google_business_profile.md   ← checklist template
    meta_business_suite.md
    google_ads_account.md
```
A workflow is NOT a Transform node. It is a stateful task list; no LLM execution per item.

### Specialist Plugin Pipeline — Build Target

**Pipeline-first rule:** Before adding many channel/vendor features to any plugin, prove the core specialist pipeline end-to-end for one CMO-facing job. No plugin should add a catalog of micro-capabilities before the job → specialist → artifact → approval loop works.

**The pipeline:**

```text
[Owner intent] → [CMO job selection] → [Specialist Transform] → [Artifact] → [Owner decision] → [Learning]

Owner intent
  Example: "Find where my ads are wasting money."

CMO job selection
  Job: marketing.optimize
  Intent: testable objective, constraints, success criteria, risk policy

Specialist Transform
  Plugin: selected by job + readiness + specialty metadata
  Input: Bridge envelope + need-to-know memory + connector credentials
  Output: one or more artifacts
  State: pending_review unless read-only informational

Evaluate / owner decision
  Surface: Stream artifact card with native preview when relevant
  pass → approve/apply/save as learning
  fail → revision thread or dismiss

Learning
  Approved findings, rejected ideas, dismissed artifacts, and measured outcomes become future CMO memory.
```

**Pipeline wiring (MVP approach):**
A plugin may initially be read-and-draft only. Approval should save or authorize the next explicit action; dismissal should remove the artifact from the user's attention surface while preserving audit where required. Write/spend/platform mutation actions must be separate approved actions behind clear risk policy.

**What is NOT first-plugin scope:**
- Automatic spend changes
- Automatic publishing
- Broad multi-platform fan-out
- Unreviewed campaign creation
- Exposing connector/API/tool jargon to the owner

All of the above come after the collapsed job model and approval loop are validated.

### Shortform Video Production + Publishing Pipeline

Shortform is a Phase 6 production pipeline, not a CMO chat feature and not a reason to add platform routing logic.

**Fastest path to volume:** BOS should generate **template-rendered vertical video assets**, not rely on cinematic text-to-video models for hundreds/thousands of posts. The scalable path is:

```text
content atom
  → script
  → voiceover
  → branded motion template / captions
  → MP4 asset + metadata
  → shortform_video_asset artifact in Stream
  → human approval
  → export pack / scheduler handoff
  → later: approval-gated native publishing plugin
```

**Generation owner:** a non-channel specialist plugin such as `api/plugins/media-shortform/` should implement `media.shortform.generate` and output a reviewable `shortform_video_asset`. It may use local/free TTS for volume, premium TTS for flagship pieces, Remotion/FFmpeg/HTML template rendering, Cloudflare R2 or equivalent object storage, generated captions from the known script, and brand-compliance checks from Campaign Brand Kit.

**Publishing owners:** platform mutation remains channel-plugin owned. The initial integration order is:

1. **Export/scheduler handoff first** — MP4 + caption + hashtags + title + publish date CSV/ZIP; no platform API dependency.
2. **YouTube Shorts plugin** — likely first native publisher because Google OAuth/API patterns already exist in BOS; quota constraints must be handled.
3. **Meta/Instagram Reels** — use the existing Meta plugin path; requires linked IG Business account, hosted video URL, and relevant Meta permissions/app review for non-admin/client use.
4. **TikTok** — keep manual/scheduler export until Content Posting API access and review are clear.

**Approval boundary:** generating a video asset is safe; publishing to any external platform is an approved external action. Native publish modules must produce `action_result` artifacts with platform IDs/URLs and changed resources. Bulk publishing without approval is forbidden.

**Creative supply chain (manufacturing layer):** The full architecture for the layer between campaign strategy and channel distribution — Creative Director concept capability, primitive generation, blueprint assembly, render targets, BRAND.md injection, Google Drive as the asset library, and agency role mapping — lives in **`CREATIVE_SUPPLY_CHAIN.md`**. Do not duplicate that detail here.

---

## 1. Product Brand: Klaroha

**Klaroha** is the customer-facing product brand. In Cebuano, Klaroha means **"make it clear"** or **"it's very clear."**

Digital marketing creates a massive overlapping signal stream across creative direction, technical implementation, analytics, platform rules, revisions, approvals, and performance reporting. Klaroha consumes that complexity and collapses the traditional multi-human marketing department workflow into a simplified command center.

**Brand promise:** Klaroha increases marketing output by raising confidence, reducing delay, and removing operational drag.

**Primary tagline:** Marketing, Engineered for Clarity.

**Supporting language:** Clarity from every marketing signal. Collapse the noise. Command the signal. All the signal. None of the noise.

See `sample/klaroha_about_us.md` for the current About Us sample copy.

---

## 2. What We're Building

A self-hosted business operating system, internally called BOS, that runs on a per-user VPS. It is designed for a single operator (the CMO) who may manage multiple brands or businesses from a single consolidated interface. The system provides a Klaroha command center to manage AI-driven marketing assets, approvals, and performance signals across these brands.

**Core mental model:** Klaroha is a company communicated through messaging. Not dashboards, not admin panels - organizational reporting upward with clarity.

---

## 3. The Core Thesis

**The BOS knows your business. You don't repeat yourself.**

A traditional API platform is stateless. A business operating system holds your context. By separating the infrastructure (Org) from the identity (Brand), the system allows a single operator to scale across multiple businesses without duplicating technical setup.

**The CMO is the strategic brain; modules are specialist execution arms.**

BOS follows the MOS corporate-structure model. The business owner / CEO provides vision, goals, constraints, risk tolerance, and business priorities. The CMO brain collaborates with that owner to convert vision into a testable strategic intent, then delegates execution to specialist modules. Modules do not own strategy. They are mechanical arms in the execution pipeline: copywriters, analysts, media specialists, creative generators, audio/video/image workers, governance checkers, and other single-responsibility transform nodes.

**The BOS promise:** for a small business owner, BOS should feel like:

```text
I have a CMO in my pocket.
The CMO has specialists.
The specialists use tools.
The tools produce artifacts.
I approve decisions.
BOS remembers what worked.
```

Not:

```text
I have 27 SaaS dashboards and need to learn marketing operations.
```

BOS must therefore compress the enterprise marketing department into an owner-facing operating loop: the owner gives business intent; the CMO translates it into marketing strategy; BOS assembles the right specialists/plugins; specialists produce artifacts; the owner approves, revises, or dismisses decisions; BOS learns from results.

**Modules declare execution. Skills declare operating contracts.**

A specialist module knows how to execute one transform — draft copy, inspect performance data, generate creative guidance, read an inbox, or prepare an approved action. A skill declares when that capability should activate, which workspace memory/resources must be loaded, what workflow to follow, and which evaluation criteria apply. It does not know the broader business strategy, which LLM runs it, or which provider is cheapest today. That is the platform's problem.

**BOS capabilities are organized by business operating function, not artifact format.**

An email can belong to marketing, sales, finance, HR, or internal client operations depending on the business workflow it serves. Example: a Google Business Profile onboarding email is not a marketing email sequence; it is `internal.client_onboarding.google_business_profile` because it governs service delivery after a client is won.

**The BITE framework governs all handoffs.**

BITE is a bridge-first, intent-driven pipeline architecture. It is not merely a final QA step. Every execution handoff starts with a versioned Intent contract, moves through stable Bridge envelopes, is processed by single-responsibility Transform nodes, and is checked by Evaluate gates at significant transitions.

- **Bridge** - The universal, append-only envelope between nodes. It carries `id`, `idempotency_key`, immutable `intent_ref`, `payload`, `payload_type`, lineage, state, attempts, structured feedback, error, and tracing metadata. Domain data never lives at the top level; it lives inside versioned payload schemas. The bridge layer owns state and routing execution.
- **Intent** - A versioned data contract defining what "done and correct" means. Intent comes from CEO/CMO collaboration and must be testable: observable, measurable, bounded, and attributed. It defines criteria, scoring, pass/fail/escalation behavior, retry ceilings, and the responsible evaluator. Strategy lives here and in the CMO brain, not inside transform modules.
- **Transform** - Single-responsibility nodes that accept declared payload types/versions and emit declared payload types. BOS modules are Transform nodes. A Transform node executes one specialized capability, never owns bridge state, never routes, never assumes pipeline context beyond the envelope, and returns structured success/failure rather than throwing unhandled exceptions.
- **Evaluate** - A special node/gate that compares an envelope against its pinned Intent and returns `pass`, `fail`, or `escalate` with score, structured criterion-level feedback, and `route_to`. Evaluate is tiered by cost: inline rules, local model checks, and deep/human/high-authority review. Routing decisions live in Evaluate; the bridge executes them.

Correct BITE build sequence: **Intent → Bridge → Transform nodes → Evaluate gates → implementation**. If BOS cannot define a testable Intent contract for a workflow, that workflow should not be treated as a BITE pipeline yet.

**Omnichannel marketing collapses to three CMO-facing jobs with many need-to-know specialist pipelines.**

BOS must not expose the corporate marketing org chart as product navigation and must not let the capability catalog grow into thousands of channel/task names such as `marketing.channel.google_ads.performance_review`, `marketing.channel.meta.ads.negative_keywords`, or `marketing.channel.email.sequence.week_2_followup`. Those names describe specialist implementation details, not how an owner thinks.

The durable CMO-facing marketing jobs are:

```text
marketing.plan      # decide what to do
marketing.execute   # make or prepare the work
marketing.optimize  # learn what is working and improve it
```

Everything else is metadata, artifact type, connector capability, or internal Transform implementation.

Examples:

| Owner request | CMO-facing job | Specialist/plugin implementation | User-facing artifacts |
|---|---|---|---|
| "Plan a launch for this offer" | `marketing.plan` | strategy/planning package, brand memory, campaign history | campaign plan, channel mix, budget hypothesis, measurement plan |
| "Create the assets" | `marketing.execute` | copywriter, designer, Gmail, Google Ads, landing page, video/image tools | ad drafts, emails, landing copy, creative briefs, launch checklist |
| "Find where my ads waste money" | `marketing.optimize` | Google Ads plugin, GA4/Search Console, CRM/conversion data, analyst evaluators | waste findings, negative keyword suggestions, budget moves, new ad variants |

Plugins declare which jobs they implement and what specialist/tool surface they provide. Example:

```yaml
plugin: google_ads
implements:
  - marketing.optimize
  - marketing.execute
specialty:
  - paid_search
  - search_ads
  - negative_keywords
  - budget_efficiency
platform:
  - google_ads
connector:
  protocol: google_ads_api
risk_policy: read_and_draft_only
```

The CMO may create a campaign-level Intent and then issue multiple specialist Bridge envelopes. Each Transform node still receives only the payload, memory slots, resources, and evaluation criteria it needs. A Google Ads optimization Transform should not load Gmail drafting rules. A Gmail outreach Transform should not load Google Ads search-term data. Omnichannel coherence comes from the shared Intent and CMO strategic context, not from exposing every specialist action as a separate product capability.

Internal executable IDs may remain specific for auditability and dispatch, but the product language and CMO capability surface must stay collapsed around `marketing.plan`, `marketing.execute`, and `marketing.optimize`.

**Model, tool, and connector routing is infrastructure, not CMO product language.**

The CMO brain has its own configurable strategic LLM for CEO/CMO collaboration, Intent creation, delegation, and synthesis. Transform modules have separately configurable execution backends. A backend may be a text LLM, image generator, audio/TTS provider, video generator, analytics/code runner, search/scraping tool, MCP sidecar, native platform API connector, or other specialized capability. Evaluate gates may also have their own backend tier: deterministic inline checks, local model checks, or deep/human/high-authority review.

MCP connectors are an acceleration layer, not the product architecture. BOS owns the stable capability/module IDs, approval gates, audit trail, credential policy, and CMO workflow. For Meta, read-only analytics/comment monitoring may start through a local MCP-compatible sidecar for speed-to-market; publishing, replies, budget changes, and other write/spend actions should move through explicit approved-action connectors and preferably native Meta API/OAuth once ready.

Routing precedence is:

```text
1. Explicit backend override for the target
2. Module-declared capability and modality
3. Capability default routing policy
4. Available BYOK / OAuth / platform credentials
5. Development mock fallback only where safe
```

Backend configuration should support scopes such as:

```json
{
  "cmo.main": {
    "provider": "openai",
    "model_id": "gpt-5.1",
    "modality": "text",
    "strict": true
  },
  "marketing.plan": {
    "provider": "openrouter",
    "model_id": "anthropic/claude-3.5-sonnet",
    "modality": "text",
    "strict": true
  },
  "marketing.execute.copywriting": {
    "provider": "openrouter",
    "model_id": "anthropic/claude-3.5-sonnet",
    "modality": "text",
    "strict": true
  },
  "marketing.execute.creative.image": {
    "provider": "openai",
    "model_id": "gpt-image-1",
    "modality": "image",
    "strict": true
  },
  "marketing.optimize.analytics": {
    "provider": "python",
    "tool_id": "pandas_profile",
    "modality": "data_analysis",
    "strict": false
  }
}
```

Provider/model/tool IDs are never shown as normal CMO-facing language. The user experiences business jobs and artifacts — planning, execution, optimization, drafts, findings, recommendations, approvals — while backend routing remains operational infrastructure.

---

## 4. System Hierarchy: Org $\to$ Brand $\to$ Market Unit $\to$ Campaign

The system uses a lean hierarchy that scales from one owner/one brand to multi-brand ecommerce, agency client rosters, multi-location service businesses, and broker/agent networks without adding a separate Portfolio layer. The Org itself is the portfolio/control plane.

### Level 1: The Org (Infrastructure Plane)
*Shared across all brands. Managed once, used everywhere.*
- **AI Provider Access:** LLM API keys/OAuth tokens (e.g., OpenAI, Gemini). Provider/model/tool IDs remain system infrastructure and are not CMO-facing product language.
- **Global Billing:** Total token spend and budget caps across the entire deployment.
- **Module Registry:** The library of installed Transform implementations. Internal executable IDs may remain specific for auditability, but the CMO-facing marketing surface collapses to `marketing.plan`, `marketing.execute`, and `marketing.optimize`; channel/vendor names are plugin metadata, not primary product navigation.
- **Org Settings:** Global defaults and system-level configuration.

### Level 2: The Brand / Client (Business Plane)
*The unique identity of a specific business, client, product brand, or managed account.*
- **Brand Profile:** Voice, tone, and core values.
- **Product Catalog:** A list of products, their taglines, and key benefits.
- **Audience Personas:** Defined target segments, demographics, and pain points.
- **Brand Guidelines / Strategic Brief:** Long-form Brand-plane source of truth for positioning, audience strategy, messaging principles, logo concept, visual identity, tone, UI feel, and campaign implications. Stored as a tagged PostgreSQL document with `doc_type=brand_guideline`.
- **Campaign Brand Kit:** Required onboarding document for cohesive multi-platform campaigns. It is the shorter execution summary derived from Brand Guidelines and captures the minimum practical design/voice rules - color palette, tone of voice, typography basics, CTA style, basic campaign components, and platform consistency rules. It is stored as a tagged document in PostgreSQL, not as many hard database columns.
- **CMO Knowledge Context:** The CMO chat must answer brand/project questions from the ingested workspace context - brand profile, products, audiences, Brand Guidelines, and Campaign Brand Kit - instead of acting stateless or asking for already-provided context. When a Brand is active (`brand_id` set in the request), the CMO system prompt and all module execution briefs must be scoped to that Brand's rows — not the workspace-level fallback. `_brand_scoped_brief()` enforces this; `_resolve_brief()` is workspace-only and must not be used for module dispatch when an active Brand is set. When no Brand is active but Brand rows exist, org-level chat may list available Brands, but must not load workspace `brand_json`, products, audiences, or documents as brand facts. Brand switching and artifact ownership are governed by `workspace.scope_resolution` SKILL.md: the CMO emits hidden `SCOPE:` with conversation/execution Brand; code validates and blocks unowned artifact RUNs rather than phrase-routing.
- **Skill-Declared Memory:** Workspace resources are not dumped into every prompt. Activated skills declare memory slots such as `brand_profile`, `product_catalog`, `audience_profiles`, `campaign_brand_kit`, `recent_rejected_runs`, and `approved_claims`; BOS hydrates only the slots relevant to the current turn. With no active Brand, `hydrate_memory_slots()` is workspace/org-scoped. With an active Brand, it must be strictly brand-scoped (`brand_id`) for products, audiences, documents, and run memory; no workspace fallback is allowed inside active-brand chat turns. Module briefs use `_brand_scoped_brief()` in `routers/chat.py`, which must build from overrides + Brand rows only rather than calling workspace `_resolve_brief()` first.
- **Extended Document Types:** The workspace document store supports additional doc types beyond brand guidelines and campaign brand kits: `marketing_report` (performance summaries), `campaign_report` (per-campaign analytics), `competitor_profile` (competitor intelligence, limit 10, 1000 chars each), and `industry_report` (market and sector data). These are consumed as plan memory slots by the `workspace.plan_mode` skill.
- **Social / Plugin Connections:** Each brand can have one or more external OAuth connections stored per platform in the `social_connections` table (`brand_id`, `platform`, `page_id`, `access_token_encrypted`, `token_meta_json`) or through plugin-declared connector requirements. Gmail is an active OAuth channel connection: each brand connects its own Gmail account via PKCE OAuth2; `page_id` is the email address; `token_meta_json` holds `refresh_token_encrypted` + `expires_at` for silent token refresh. `get_page_token()` auto-refreshes OAuth tokens within 5 minutes of expiry before returning them to plugin modules. Plugin API credentials are declared in `channel.json` and configured from the relevant Specialist card's Connectors subsection in Admin, not from a separate connector catalog. Google Ads is an active plugin-owned specialist direction: current capabilities use plugin-declared environment credentials for read/draft work, while full-control brand-scoped account mapping and approval-gated mutations must be implemented through plugin contracts rather than hardcoding platform flows into CMO chat. Search Console is the next plugin-owned specialist target and must begin with an approved BITE sample before any spec/build. Future plugins such as Meta or Amazon PPC must follow the same plugin-contract model.
- **Brand Analytics:** Performance metrics specific to this identity.

### Level 3: The Market Unit (Scope Plane)
*Optional. Used when a brand operates across locations, agents, offices, territories, marketplaces, regions, service lines, SKU groups, or audience segments.*

Market Unit is the lean replacement for many industry-specific hierarchy layers. It can represent:

```text
location | service area | branch | agent | office | territory | marketplace | SKU group | region | service line | audience segment
```

Examples:
- Multi-location services: `Dallas North`, `Austin South`, `Emergency Drain Cleaning`
- Broker/agent networks: `Miami Seller Agents`, `Sarah Nguyen Territory`, `Downtown Office`
- Ecommerce: `Amazon US`, `Shopify DTC`, `Cleanser Bundle`, `Beauty Pros Audience`
- Agency: the agency is the Org; each client is a Brand; that client's locations/markets/agents/products become Market Units when needed.

The user should not have to model this explicitly before using BOS. CMO scope resolution should infer or ask clarifying questions only when the requested work is ambiguous.

### Level 4: The Campaign (Operational Plane)
*The active work and execution scoped to an Org, Brand, optional Market Unit, and objective.*
- **Campaign Intent Contracts:** Versioned, testable definitions of what a campaign execution must satisfy: objective, audience, offer, scope, constraints, success criteria, scoring, and escalation behavior.
- **Bridge Envelopes:** Immutable execution handoffs from the CMO brain into specialist Transform nodes, with pinned `intent_ref`, payload type/version, lineage, attempts, feedback, and routing metadata.
- **Module Runs:** The Transform executions performed by specialist modules against a Bridge envelope.
- **Evaluation Loops:** Evaluate gates compare Transform outputs against the pinned Intent, append structured feedback, and route pass/fail/escalate. Generated module outputs create persistent pending decision tasks until approved or superseded by a revision.

Lean scope contract:

```yaml
job: marketing.optimize
scope:
  org_id: current deployment
  brand_id: optional
  market_unit_id: optional
  campaign_id: optional
  service_line: optional
  product_line: optional
  geography: optional
  audience_segment: optional
  channel_hint: optional
```

The job remains `marketing.plan`, `marketing.execute`, or `marketing.optimize`; only the scope changes.

---

## 5. Interface Layer: The Command Hub

Three interfaces. One API. The **Command Hub** is the primary UX.

### The Command Hub (Web UI)
The interface is designed for a CMO managing one or many brands/clients, with optional market-unit scope for locations, agents, marketplaces, regions, service lines, or SKU groups.

**Core Layout:**
- **Brand Switcher:** A global selector to change the active Brand context.
- **The CMO Center:** A full-width chat interface. The CMO directs the system here.
- **The Aggregated Stream:** A consolidated decision queue. The CMO sees "Pending Decisions" (e.g., Approvals) from *all* brands in one priority list.
- **Workspace Panel:** A sliding right panel (420px) focused on high-frequency CMO work: active campaigns, pinned assets, past campaigns, and pending generated assets. Reference/administrative views do not live here.
- **Workspace Artifacts:** Workspace is the canonical artifact plane. Generated capability/plugin outputs are stored as run-backed artifact records with IDs, status, renderer hints, and approval state. CMO chat only links to these artifact records; it does not render platform-native previews inline.
- **Pending Decisions:** Pending artifact cards in Stream are full inline review surfaces — native platform preview, editable copy textarea, Drive image attachment, and Dismiss/Revise/Approve actions all render directly inside the Stream card (via embedded `ApprovalBundle`). There is no separate side panel for artifact review. The side panel is reserved only for `StreamUpdateOut` cards (decision_brief, outcome, setup_blocker) that need expanded narrative context. Draft Campaign Brand Kit review is linked from onboarding/Admin flows rather than normal CMO chat.
- **Admin:** Setup, memory, specialists/connectors, outcomes, and system/debug. Admin is not the daily marketing dashboard; it configures the company brain and specialist access. Specialists are the primary connector readiness/setup surface.

**Key UX Principles:**
- **Chat-Driven Execution:** No "Run" buttons. The CMO triggers modules via natural language in the chat, but only when an activated skill contract allows it and the user expresses generation/revision/diagnostic/action intent. Capability/context questions may produce capability cards or explanatory artifacts, but they must not mechanically trigger execution modules.
- **Artifact Taxonomy:** Artifacts are not only execution outputs. BOS uses capability cards, plan artifacts, draft artifacts, intelligence artifacts, decision artifacts, and action-result artifacts. The correct fix for unrequested execution is not "no artifacts"; it is the right artifact type with the right action boundary.
- **Capability Outcome Contracts:** The CMO generates intent containers; capabilities/plugins generate native artifacts. The CMO must not freewrite final platform artifacts inline when a capability owns that output. Plugins declare their artifact type, native fields, validation rules, allowed actions, and risk policy, then return structured blocks for Workspace/Stream approval UX.
- **Sample/Example Boundary:** Broad requests like "let me see samples" are treated as artifact-selection prompts, not permission to paste platform-native content into chat. The CMO asks which reviewable Workspace artifact to create, or dispatches a specifically requested installed artifact. It must not invent inline Subject/Body, Headline/Description, product-card copy, targeting, budgets, proof, or action results.
- **Mobile-First CMO Replies:** Most CMO interaction is mobile. Default replies should be short-line, scannable operator messages: 1–4 short lines, one idea per line, bullets for choices, and one question max. Long paragraphs are reserved only for explicit requests for detail, plans, or reports. Approved style sample: `sample/mobile_cmo_reply_style_v1.md`.
- **No Hardwired Chat Copy:** CMO responses should come from the LLM using activated skills and hydrated workspace resources. Deterministic code may route, strip hidden control directives, validate safety, and enforce module permissions; it must not replace normal chat with canned assistant replies except for provider failure/error handling.
- **LLM-Backed Revision Threads:** Generated assets expose Modify/Approve controls. Modify sends the specific run, channel, prior draft, and user feedback back through the CMO LLM before creating a linked revision run.
- **Persistent Decisions:** Pending approval count and pending artifact links survive navigation/reload and point back to the exact approval task.
- **Surface-Agnostic Components:** Content (Reports, Ad Previews) renders as "Blocks" that adapt to their surface (Chat, Panel, or Mobile).
- **Infrastructure Invisibility:** The CMO never sees a model ID or a provider key; they see "Brand Voice" and "Ad Copy".

### Admin Operating Model
Admin owns setup and governance; CMO + Stream own day-to-day marketing operation.

```text
First-time: Teach BOS the business → approve memory → connect specialists → readiness check → go to CMO
Daily: Tell the CMO what to do → review Stream artifacts → approve/revise/dismiss → BOS remembers decisions
Monthly/Quarterly: Review what worked → update strategy/memory → decide what to optimize next
```

Lean Admin IA:

```text
Admin
├── Brands / Clients        # brand memory, products, audiences, guidelines, brand kit, per-brand OAuth accounts
├── Campaign Plans          # marketing.plan intent setup, not channel checkboxes
├── Specialists             # installed plugins/capabilities; implemented jobs/readiness/risk + connector status/setup
├── Outcomes                # monthly reviews, campaign reports, approved learnings
└── System                  # AI providers, billing, run logs/debug
```

Run logs, raw module IDs, provider/model choices, and BITE traces are system/debug information. They must not be the normal owner-facing marketing workflow.

### Chat Bridge & REST API
- **Chat Bridge:** Translates external messages (WhatsApp, etc.) into BOS API calls.
- **REST API:** The headless boundary. All interfaces call the same endpoints.

---

## 6. Skill Contracts (`SKILL.md` Pattern)

BOS uses `SKILL.md` principles as Documentation-as-Code for the CMO. A skill is a named, triggerable operating contract that tells the assistant when to activate, what resources to hydrate, how to perform the work, and how to evaluate output. Skills are not a replacement for modules; they govern modules.

**Progressive disclosure:**
BOS models the Agent Skills three-tier loading strategy, adapted for governed business operations:
1. **Catalog / Discovery:** BOS discovers skill directories by the presence of `SKILL.md` and reads only metadata/frontmatter for cheap routing: `id`, `name`, `description`, `scope`, `status`, `version`, `allowed_from_chat`, `requires_intent`, `triggers`, `memory_slots`, `related_modules`, and `quality_gates`.
2. **Instructions / Activation:** When user intent and BOS policy match, BOS loads the full `SKILL.md` body for the smallest eligible skill node. Parent/shared skills are loaded only through explicit inheritance.
3. **Resources / On-demand support:** BOS lists bundled resources such as examples, references, scripts, validators, and SOP source files, but does not eagerly load them unless the activated skill declares them required or the current task needs them.
4. **Execution:** BOS hydrates declared memory slots, compiles a compact prompt context, optionally dispatches allowed modules, and applies quality gates.

**Initial skill categories:**
- **Workspace CMO Context Skill:** Answers questions like "What is Klaroha?" from brand profile, products, audiences, and Campaign Brand Kit. It never dispatches modules.
- **Marketing Job Skills:** The durable CMO-facing skill surface is `marketing.plan`, `marketing.execute`, and `marketing.optimize`. Channel/vendor skills such as Gmail, Google Ads, Search Console, Meta, GTM, or Amazon PPC are specialist implementations that declare which job(s) they support and can dispatch modules only on explicit generation/revision/optimization intent.
- **Approval/Revision Skill:** Governs Modify/Approve review threads using prior draft, run ID, channel, user feedback, and recent accepted/rejected decisions.
- **Onboarding Skills:** Brand setup and Campaign Brand Kit generation remain explicit onboarding flows, not normal chat-dispatchable skills.

**Skill, memory, resource, upstream split:**
- **Skill:** How to behave for a class of work.
- **Memory:** Atomic facts and learnings BOS knows.
- **Resource:** Source documents and durable artifacts such as briefs, Brand Kits, examples, SOPs, references, scripts, validators, and performance reports.
- **Upstream contract:** A versioned artifact declared in `required_upstream`/`outputs` (for example `buyer_map.v1` or `message_architecture.v1`) that must be loaded or generated before a dependent module runs.
- **Quality Gate:** Deterministic or LLM-assisted check before output is shown or a run is accepted.

**Agent Skills principles BOS adopts:**
- Discover skills by scanning for directories containing a file named exactly `SKILL.md`.
- Build a compact skill catalog from metadata; do not load every skill body into the base CMO context.
- Expose only eligible skills to the model after BOS filters by status, trust, permissions, scope, and chat/module policy.
- Prefer harness-controlled activation over raw model file reads. BOS owns activation, memory hydration, module permission checks, source tracing, and approval gates.
- Activate the smallest relevant skill node; broader parent skills require explicit inheritance.
- Treat `SKILL.md` as the guardrail between explanation and execution: capability questions may activate informational skills that produce capability cards, while execution skills require matching intent, trigger, inputs, connector readiness, and risk policy.

**CMO behavior sample matrix:**

| User intent | Correct artifact | Tool action |
|---|---|---|
| "What can you do with email?" | Email Specialist capability card | None |
| "Plan an email campaign" | Email Campaign Plan | None beyond generation |
| "Draft email 1" | Email Draft | None beyond generation |
| "Check replies" | Inbox Intelligence | Read-only connector action if explicitly requested |
| "Send this approved email" | Send confirmation/result | Approval-gated send only after approved draft and required fields |

The agreed email sample lives at `sample/email_cmo_chat_behavior.md` and is the regression reference for future CMO/email changes.
- Return activated skill content in structured wrappers that include skill id, version, source path/version, and available resources.
- List bundled resources without eagerly reading them; resolve resource references relative to the skill directory.
- Deduplicate activations within a turn/session so the same skill is not repeatedly injected.
- Preserve activated skill instructions during context compaction; normal chat history may be summarized, but active operating contracts must remain exact.
- Parse skill metadata leniently where safe, but default to safe behavior: missing required metadata skips activation, invalid module links disable dispatch, and invalid approval policy requires approval.

**Where BOS intentionally differs from generic Agent Skills:**
- BOS does not rely on model judgment alone. Routing combines deterministic policy, metadata, intent classification, and LLM assistance.
- BOS skills are operating contracts, not just helper prompts: they can declare intent, memory, workflow, quality gates, resources, related modules, and approval policy.
- BOS resources are governed business artifacts with source references, approval state, scope, sensitivity, and version history.
- SOP ingestion never installs or overwrites skills directly; it produces a governed change proposal first.

**Need-to-know skill structure:**
The CMO-facing marketing skill surface should stay small and job-oriented, while specialist skills/packages remain need-to-know underneath. BOS should not load a broad channel/vendor skill when a job-level contract plus a selected specialist contract is enough.

Current target skill structure:
```text
api/capabilities/
  workspace/cmo_context/SKILL.md
  workspace/approval_review/SKILL.md
  workspace/plan_mode/SKILL.md              # strategic planning mode; never dispatches modules

  reasoning/buyer_intelligence/SKILL.md     # supporting substrate; outputs buyer_map.v1
  marketing/messaging/architecture/SKILL.md # supporting substrate; outputs message_architecture.v1
  marketing/planning/gtm_plan/SKILL.md      # GTM Strategy artifact; consumes buyer_map + message architecture
  # marketing/plan/campaign_strategy/ — RETIRED (status: retired; use marketing.planning.gtm_plan)
  marketing/execute/SKILL.md                # make or prepare the work
  marketing/optimize/SKILL.md               # learn what works and improve it

  onboarding/brand_setup/SKILL.md
  onboarding/campaign_brand_kit/SKILL.md

api/plugins/
  gmail/.../SKILL.md                        # specialist implementation of marketing.execute
  google-ads/.../SKILL.md                   # specialist implementation of marketing.optimize/execute
  search-console/.../SKILL.md               # next specialist implementation of marketing.optimize
```

Parent or shared skills may exist only for explicit inheritance, for example `marketing.brand.voice`, `marketing.compliance.claims`, or `marketing.shared.offer_strategy`. They must not be loaded automatically just because a child/specialist skill activates. Specialist skills declare inheritance explicitly.

**Skill resources:**
A skill directory may bundle optional resources on a need-to-know basis:
- `SKILL.md` - human-readable operating contract.
- `skill.yaml` - optional machine-readable manifest for routing, status, version, triggers, inheritance, resources, related modules, approval policy, trust/source metadata, and context-preservation behavior.
- `examples.md` - approved examples for this exact task.
- `channel_rules.md`, `format_rules.md`, `checklist.md`, or `references.md` - task-specific source resources.
- `validators.py` - optional task-level validators for output quality gates.

**Canonical BOS skill shape from Agent Skills samples:**
- **Frontmatter description is an activation contract, not a short summary.** It should include direct task names, vague user phrases, synonyms, exclusions, and handoffs to related skills.
- **Related-skill routing is explicit.** Use `related_skills` to say when another skill is a better fit, e.g. `schema-markup` for structured data implementation instead of a broad SEO audit.
- **Task-specific intake is part of the operating contract.** The skill should inspect BOS memory first, then ask only for missing context.
- **Tool limitations and caveats belong inside the skill.** Example: an SEO audit must not claim schema is missing based only on static fetch/curl because JS-injected JSON-LD may be invisible.
- **Output format is an evaluation contract.** The skill declares the expected sections so BOS can later validate structure and quality.
- **References/resources are first-class but lazy.** The activated skill lists resources such as `references/international-seo.md`; BOS does not read them unless needed.

Example frontmatter pattern:
```yaml
---
id: marketing.seo.audit
name: seo-audit
description: Use when the user wants to audit, review, or diagnose SEO issues... For structured data implementation, see schema-markup.
scope: diagnostic
status: active
allowed_from_chat: true
requires_intent:
  - diagnostic
triggers:
  - seo audit
  - technical seo
excluded_triggers:
  - structured data implementation
memory_slots:
  - brand_profile
  - analytics_summary
resources:
  - references/international-seo.md
related_skills:
  schema-markup: Use for implementing structured data after audit findings identify schema needs.
required_context:
  - site_url
output_contract:
  - Executive Summary
  - Prioritized Action Plan
quality_gates:
  - do_not_report_missing_schema_from_static_fetch_only
metadata:
  version: 1.2.0
---
```

**Skill vs module boundary:**
- A skill changes when instructions, workflow steps, quality gates, examples, memory slots, or context-loading behavior changes.
- A module changes when executable API behavior changes: schemas, persistence, provider calls, orchestration, programmatic validation, or exposed capabilities.
- A resource changes when an authoritative source document should be attached without changing behavior.
- Memory changes when the SOP contains durable facts, preferences, decisions, or learnings rather than procedure.
- Config/data changes when the SOP defines structured operational settings such as reviewer assignments, approval matrices, or claims libraries.

**SOP ingestion governance:**
SOP ingestion is a governed diff process, not a summarize-and-overwrite process:
```text
SOP → extraction → skill/module matching → diff → recommendation → approval → versioned update
```

For any uploaded SOP, BOS should extract title, type, scope width, entities, triggers, rules, workflow steps, quality gates, resources, approval requirements, definitions, and memory candidates. It then compares those components against the existing skill registry, module registry, resources, memory, and config.

The ingestion output is a change proposal across operational truth surfaces:
```json
{
  "sop": {
    "title": "Twitter Paid Social Copy SOP",
    "type": "channel_workflow",
    "scope_width": "atomic_task"
  },
  "recommended_plan": [
    {
      "surface": "skill",
      "action": "update",
      "target": "marketing.twitter.ad_copy",
      "reason": "Adds copy rules and quality gates."
    },
    {
      "surface": "resource",
      "action": "attach",
      "target": "marketing.twitter.ad_copy",
      "resource_type": "source_sop"
    },
    {
      "surface": "module",
      "action": "no_change",
      "target": "marketing.twitter_ad_copy",
      "reason": "No API/schema/persistence behavior changed."
    },
    {
      "surface": "memory",
      "action": "candidate",
      "fact": "Marketing prefers five Twitter ad variants by default."
    }
  ],
  "conflicts": [],
  "approval_required": true
}
```

Allowed proposal actions include `create`, `update`, `replace`, `archive`, `attach_resource`, `memory_candidate`, `config_change`, and `no_change`. Sensitive changes - brand voice, legal/compliance, product positioning, approved claims, pricing, targeting strategy, approval workflows, or any replacement/supersession - require human approval before activation.

**Skill context management:**
Activated skill content is treated as protected context for the active task. BOS should deduplicate repeated activations, preserve exact skill instructions during context compaction, and keep normal conversation summarization separate from active operating contracts.

**Skill versioning:**
Skill updates create new versions rather than overwriting active behavior. The previous version remains available for rollback, with source references back to the SOP and a change summary.

---

## 7. Execution Modes - BYOK + Platform

The platform supports two execution modes. A user may use either, or mix by provider.

### Platform Mode (default)
- BOS routes through its own pooled provider keys. User pays the platform's sell price.

### BYOK Mode (Bring Your Own API Key)
- User registers their own keys. Keys are encrypted at rest.
- Executor uses the user's key; no markup is applied.

### Login/OAuth Mode (provider auth)
- Interactive browser login (e.g., OpenAI Chat). BOS manages encrypted refresh tokens.

### Platform OAuth Broker — customer self-host model (decided 2026-05-24)

**Deployment model:** BOS is a product Klaroha makes; customers **self-host** it in their own cloud on their own domains. But the *system* — its identity and third-party integrations — is **Klaroha's**. The analogy: a company installs Windows on its own machines, but when a user signs into their Microsoft account / OneDrive, they authenticate against Microsoft's identity service — they never register their own Azure app. Microsoft runs the central auth; the install just talks to it.

**Therefore: third-party OAuth (Google Drive/Gmail/Calendar/YouTube, Meta, etc.) must NOT require any per-customer or per-deployment provider setup.** A customer must never create a Google Cloud project, OAuth client, consent screen, or API key. Requiring that is wrong and is explicitly rejected.

**The mechanism — a central Klaroha-run OAuth broker:**
- Klaroha runs one always-on auth service (e.g. `connect.klaroha.com`) holding **one verified** Google app (all Google scopes) + the Picker API key, and the platform Meta app. Verified once, by Klaroha.
- A self-hosted BOS instance never holds `GOOGLE_CLIENT_SECRET` (or any platform client secret). It holds only a **broker URL + a deployment identity credential**.
- Connect flow: BOS instance → redirect to broker → broker runs consent on Klaroha's verified app → provider calls back to **one stable redirect URI** at the broker → broker hands the token back to the originating instance via a signed one-time exchange → instance stores it locally in its own `social_connections`. One verified app covers every install; no per-domain redirect registration.

**Critical scoping note — this only changes token *acquisition*.** Everything downstream — `get_page_token()` and its auto-refresh, the per-brand `social_connections` model, all channel plugins, the creative factory — reads tokens from the connection row and is unaffected by whether they arrived via env-var app (today's single dev box) or the broker (productization). So feature work that consumes connections does **not** block on the broker, and the broker slots in behind the existing connection model with no downstream rework.

**Status:** Decision locked; broker is its own platform-level mini-project (spans all integrations, needs Google app verification + CASA assessment for restricted scopes, secure signed token handoff, and a Klaroha-hosted Picker page for cross-domain referrer constraints). The current single Klaroha deployment continues on env-var platform credentials (`GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI/PICKER_API_KEY`) until the broker is built. Per-deployment BYO-Google-app setup is **not** the model and must not be documented as a customer step.

---

## 8. UI Component Architecture

**Principle: Surface-Agnostic Components**
Every renderable unit (e.g., `PerformanceReport`) is a self-contained component: data in, render out. It does not know if it is in a chat bubble or a full-screen report. The `SurfaceContext` provides the layout constraints.

| Component | Renders | Driven by |
|---|---|---|
| `PerformanceReport` | Stats grid + chart + campaign table | `layout_hint: "table"` |
| `ApprovalBundle` | Platform preview + copy panel + approval actions in Workspace/Stream artifact surfaces, not inline CMO chat | `layout_hint: "media"` |
| `ModuleCard` | Health badge + channels + run stats | `layout_hint: "compact"` |
| `AlertBlock` | Priority alert with action link | `layout_hint: "alert"` |
| `NarrativeBlock` | CMO-authored text update | `layout_hint: "narrative"` |

---

## 9. Technical Reference

### Deployment Operations

Both stacks run on one VDS from `~/bos/` using one compose file with different env vars. Production (`hq.klaroha.com`) uses project name `bos`; staging (`staging.klaroha.com`) uses project name `staging` with `--env-file .env.staging`. See **`DEPLOY.md`** for the full deploy runbook, correct commands, port topology, and the localhost ↔ staging breakage runbook (C1–C6 candidate causes, incident log).

**Do not run smoke tests.** The pre-push smoke test (`smoke-local.sh`) and the post-deploy smoke check (`check-staging.sh`) are overhead — they do not replace observing the actual running app. Never invoke them, never treat a passing smoke test as a sign a deploy succeeded, and never report a task complete based on smoke test output alone. Verify by hitting the real endpoint or observing containers directly.

### Backlog → ClickUp Sync

`BACKLOG.md` is the source of truth for BOS development tasks. ClickUp (`Klaroha BOS` list) mirrors it for team visibility. These are two separate concerns:

- **BOS build tracking** — `BACKLOG.md` → ClickUp (`Klaroha BOS` list). Internal dev workflow only. App users never see or interact with this.
- **Client/org marketing ops** — CMO artifact plane → brand's ClickUp via the ClickUp plugin (`tasks.create`, `tasks.read`). Product-level workflow; no BACKLOG.md involved.

**Running the sync** (run from `~/bos/` on the host):

```bash
export CLICKUP_API_TOKEN=pk_...
export CLICKUP_TEAM_ID=90161582949

# Dry run — see what would change without applying
python3 api/plugins/clickup/scripts/sync_backlog.py --dry-run --list "Klaroha BOS"

# Apply
python3 api/plugins/clickup/scripts/sync_backlog.py --list "Klaroha BOS"
```

Credentials are stored encrypted in the BOS database (`provider_keys` table, `provider = 'plugin.channel.clickup'`). Decrypt with `ENCRYPTION_KEY` from `.env` using `cryptography.fernet.Fernet` if you need to retrieve them outside the app.

**Status mapping** (matches ClickUp custom statuses in the `Klaroha BOS` list):

| `BACKLOG.md` | ClickUp status |
|---|---|
| `[x]` | `shipped` |
| `[~]` | `in development` |
| `[!]` | `blocked` → falls back to `backlog` if list has no blocked status |
| `[-]` | `cancelled` |
| `[ ]` | `backlog` |

Run this sync whenever a significant batch of tasks is completed or added. The script is idempotent — tasks already in sync are skipped.

### Directory Layout
- `api/capabilities/{vertical}/{domain}/{task}/`: First-party, non-channel capability packages. Each executable package contains `SKILL.md`, `module.py`, `template.j2`, and optional resources/validators. Marketing job-level packages should align to `marketing.plan`, `marketing.execute`, and `marketing.optimize` where possible.
- `api/plugins/{plugin}/`: Third-party/channel/vendor specialist packages. A plugin declares which CMO-facing jobs it implements (`marketing.plan`, `marketing.execute`, `marketing.optimize`) plus its specialty, platform, connector, risk policy, and output contracts. Plugin internals may have specific executable IDs for audit, but those IDs are not the product navigation model.
- `api/providers/`: Adapter files for LLM providers and shared infrastructure providers only. Channel/vendor API behavior belongs in plugins or connector adapters behind plugin contracts.
- `web/`: React + Vite frontend.

### Critical Endpoints
- `POST /chat`: The primary entry point for the CMO. It handles discussion and intent-gated module dispatch, then returns artifact references for generated outputs.
- `POST /chat/runs/{run_id}/revise`: LLM-backed approval-thread revision for a specific generated module result.
- `POST /runs`: Trigger a specific module run.
- `GET /onboarding/status`: Deployment readiness check (Org + Brand + Campaign Brand Kit + installed specialists).
- `POST /onboarding/brand-kit`: Generate the required Campaign Brand Kit document from the current workspace context.
- `GET /onboarding/brand-kit/latest`: Return the newest Campaign Brand Kit document by update time, including full `content_markdown`; use `?status=approved` to fetch only an approved kit.
- `GET /workspace/documents`: List tagged workspace documents, including `campaign_brand_kit`. Supports `?doc_type=` filter for `brand_guideline`, `marketing_report`, `campaign_report`, `competitor_profile`, `industry_report`.
- `POST /providers/login`: Start interactive OAuth flow.
- `GET /social/gmail/callback`: Server-side Gmail OAuth callback. Stores `SocialConnection(platform="gmail", page_id=email)` with refresh_token in `token_meta_json`, redirects to frontend.
- `GET /social/connections?brand_id=X`: List all external/social connections for a brand or workspace.
- `DELETE /social/connections/{id}`: Disconnect an external/social connection.
- Future plugin OAuth/connect endpoints must be registered through generic connector/plugin contracts where possible; CMO chat must not gain platform-specific routing or publish branches.

---

## 10. Deployment Model — Click-to-Deploy Software

**Decision locked (2026-06-01).** BOS is packaged software that organizations deploy on their own cloud infrastructure. It is **not** a multi-tenant SaaS. Klaroha is the software vendor and central services operator; organizations own their data and their cloud environment.

**The analogy:** An organization installs the software on their own server, but authenticates against Klaroha's central identity and integration services — they never register their own Google Cloud project or Meta Developer App. Klaroha runs the central auth relay and AI services; organizations run the application on their own infrastructure.

**Active focus:** Before distribution to many orgs, the immediate goal is one clean end-to-end first org deploy. Getting that journey right once is the template that all future deployments clone.

### What Each Org Gets
- Their own server or cloud environment (DigitalOcean droplet, AWS EC2, VPS)
- Their own isolated PostgreSQL database — no commingling with other orgs
- Their own encryption keys, auto-generated at first boot
- Their own domain or subdomain, their choice
- No Klaroha access to their data at rest

### What Klaroha Operates Centrally
- **OAuth relay** (`connect.klaroha.com`) — holds the one Klaroha-verified Google app (all Google scopes) + Meta app + TikTok app; brokers token exchange for all deployed instances; one stable redirect URI per platform; no per-customer app registration ever required
- **Platform inference** — pooled AI provider access for orgs that do not bring their own API keys; metered against each org's deployment key
- **Deployment key issuance** — each org receives a `KLAROHA_DEPLOYMENT_KEY` at purchase; gates relay access and usage metering
- **Software distribution** — Docker Hub image registry; `stable` and `latest` channels; Klaroha controls what is promoted to `stable`
- **Update notifications** — in-app alert when a new version is available; org controls timing of their own update

### Why Multi-Tenant SaaS Is Rejected
- The target operator (agency owner, overloaded business leader) cannot accept their clients' marketing data on shared infrastructure alongside competitors
- The product promise "your CMO, your server" requires the data layer to remain on the org's own infrastructure
- The relay centralizes auth and inference — data isolation is maintained by keeping the data layer org-local

### Target Deploy Experience (Zero-Setup)
The full operator experience once the relay is built:

1. Org purchases license → receives `KLAROHA_DEPLOYMENT_KEY`
2. Clicks "Deploy to DigitalOcean" or runs `curl install.klaroha.com | bash`
3. Sets domain name + deployment key — nothing else
4. Container first boot: auto-generates `API_SECRET_KEY` and `ENCRYPTION_KEY`, runs `alembic upgrade head`, bootstraps admin
5. First login → setup wizard (org name → import brand brief → CMO operational)

No Google Cloud project. No Meta Developer App. No AI API keys required to get started.

### Minimal `.env` at Deploy Time (Target)
```env
KLAROHA_DEPLOYMENT_KEY=dk_live_xxx     # issued at purchase — relay access + metering
KLAROHA_RELAY_URL=https://connect.klaroha.com
FRONTEND_URL=https://theirorg.com      # org's chosen domain
```
All other values (database URL, secret keys, encryption key) are auto-generated at first boot and stored in the container's persisted volume.

### Current State vs. Target
Today a deployment requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `META_APP_ID`, `META_APP_SECRET`, and all other platform credentials set manually in `.env`. The relay closes this gap entirely. Until the relay is built, new deployments require manual Google Cloud and Meta app setup, which blocks clean customer onboarding for any org that wants Gmail, Calendar, Drive, YouTube, or Facebook connected.

### Distribution Targets
| Platform | Priority | Notes |
|---|---|---|
| DigitalOcean Marketplace | Primary | 1-Click Droplet; right fit for non-technical operator audience |
| Docker Compose + install script | Secondary | `curl install.klaroha.com \| bash`; dev-savvy operators |
| AWS Marketplace | Enterprise | Larger agencies already on AWS infrastructure |

### Build Order
| Step | What | Why it unblocks |
|---|---|---|
| 1 | **OAuth relay** (`connect.klaroha.com`) | Zero-setup for all Google + Meta integrations; every deploy currently requires manual cloud project setup without it |
| 2 | **First-boot init script** | Turns `docker compose up` into a real product install; no post-boot shell access required |
| 3 | **Deployment key system** | Gates relay access; enables per-org usage metering and billing |
| 4 | **DigitalOcean Marketplace listing** | Primary distribution channel for the target operator persona |
| 5 | **In-app update notification** | Keeps deployed instances informed without forcing auto-updates |
| 6 | **AWS Marketplace** | Enterprise distribution tier |

### Update Strategy
Each deployed instance checks a Klaroha version endpoint periodically. When a new version is available, the admin panel surfaces "Update available — vX.Y.Z" with a changelog. The admin triggers the update manually (pull new Docker image + run migrations). This gives Klaroha control over what is available on each channel while giving each org control over when they update. Auto-updates on the `stable` channel are available for orgs that opt in.

---

## Appendix A — Historical Changelog

> Historical record only. The **Current State & Locked Architecture** section at the top of this brief is the active source of truth. If an older changelog row conflicts with a locked rule, the locked rule wins.

| Version | Date | Changes |
|---|---|---|
| 3.51 | 2026-06-04 | **Public lead-capture demo direction parked:** Added `PUBLIC_LEAD_CAPTURE_DEMO.md` for the public website/PDF/text → Business Profile Draft → correction chat → Marketing Plan Preview → email/waitlist flow. Critical constraint recorded: the public wrapper must call/reuse the internal `marketing.planning.strategy_workflow` capability server-side; it must not duplicate planning prompts, output structure, or maintain a second public planning capability. The rough HTML sample at `sample/public_website_to_plan_demo_klaroha.html` is visual/conversation exploration only, not an approved implementation sample. |
| 3.49 | 2026-06-04 | **Strategy Workflow: per-component re-run + parser fixes + web rebuild.** `PATCH /strategy-workflows/:id/components/:type` now executes real LLM calls: routes via `capability_router.route()` + `execute_live()`, builds a per-component prompt injecting brand context + upstream component data from DB, parses typed field dicts per component type (buyer_map, strategic_thesis, offer_architecture, channel_stack, tactical_funnel, work_orders), cascades stale to dependents per the DAG in `STRATEGY_WORKFLOW.md`, and bumps `version`. Not-wired components fall back to stale-marking only. **Bug fix — channel_stack.do_now always empty:** `_do_now_channels()` in `StrategyWorkflowModule` only handled the template-spec format (`Do now:\n**Channel**`). LLMs generate two additional formats: `Do now: **Channel**` (label + channel inline) and `### Do now: **Channel**` (heading merged with channel name). Fixed by checking the inline pattern first (horizontal-whitespace-only between label and `**`) before falling back to the template-spec parser. Same fix applied to the per-component PATCH parser. Channel_stack summaries now populate correctly for new runs. Existing DB records retain `do_now: []` — the `raw` field is correct and can be re-parsed if needed. **Bug fix — Stream showed "Campaign Plan" + ApprovalBundle for strategy_workflow artifacts:** Web container was built on 2026-06-03, before `StrategyWorkflowStreamCard` and the `artifactTitle` strategy_workflow check were committed. The old build fell through to `includes('plan') → "Campaign Plan"` and rendered standard ApprovalBundle (Dismiss/Revise/Approve). Fixed by rebuilding web container. Stream now correctly renders `StrategyWorkflowStreamCard` (archetype chip, motion, wedge, component count, "Open Strategy Workflow →" nav button). Known open data issue: `WorkflowRun.request` is always `""` — the CMO chat message is not captured in the brief when the module is dispatched. |
| 3.47 | 2026-06-03 | **Bug fixes + planning module cleanup:** `marketing.plan.campaign_strategy` retired (`status: retired`, `allowed_from_chat: false`) — `marketing.planning.gtm_plan` is now the sole planning module; all plan triggers route there. `CmoChat` moved to Layout shell level (`display:none` when not on /cmo) so in-flight streams and React state survive navigation. Upstream contract failures in `_execute_module` now persist a failed Run before re-raising so chat surfaces an error artifact reference instead of silently yielding nothing. Backend override for `image_gen_provider`/`image_gen_model` in `plugin_loader.py` uses assignment (not `setdefault`) so operator config is never silently ignored. |
| 3.46 | 2026-06-01 | **Click-to-deploy deployment model locked:** BOS is packaged software orgs deploy on their own cloud — not multi-tenant SaaS. Klaroha operates the OAuth relay (`connect.klaroha.com`) and platform inference centrally; org data stays on org infrastructure. Multi-tenancy explicitly rejected and moved to Parking Lot. Build order: relay → first-boot init → deployment key system → DigitalOcean Marketplace → in-app update notification → AWS Marketplace. Active focus is one clean first-org deploy before distribution. Full model in Section 10. |
| 3.45 | 2026-05-27 | **GTM upstream-contract workflow:** Added executable strategic substrate capabilities `reasoning.buyer_intelligence` (`buyer_map.v1`) and `marketing.messaging.architecture` (`message_architecture.v1`). `marketing.planning.gtm_plan` now enforces `required_upstream` generically through run orchestration: load successful prior contract artifact, generate missing producer output, inject actual upstream content, and block only when a required contract cannot be produced. Shorthand “GTM” now means go-to-market unless the user explicitly says Google Tag Manager/container/tags. GTM artifacts title as `GTM Strategy`, render through Stream, and chat Review focuses the inline Stream card rather than navigating to Workspace. Strict backend override credential/execution failures fall back to normal model routing so Brand Brief-driven substrate generation can complete. |
| 3.44 | 2026-05-27 | **Specialists + connectors unified:** Admin Specialists (`/admin/modules`) is now the single readiness/setup surface for installed specialists and their connector rows. Connector rows show status, description, Implements, Missing vars, and Configure/Update/Remove actions. Brand-scoped OAuth connect/disconnect stays on Brands/Clients. `/admin/connectors` is only a compatibility alias and OAuth callback results now route to `/admin/modules`. The standalone `AdminConnectors` component was removed. |
| 3.41 | 2026-05-24 | **CMO chat → creative → Drive (live):** `google-drive` plugin built (`drive_client.py` Drive REST v3 + `drive.folder.setup`/`asset.upload`/`asset.list`/`asset.get`); Google Drive OAuth connection (per-brand) + Google Picker root-folder selection. New `creative.post.image` capability (creative-factory, `allowed_from_chat`) generates a Meta-post visual via the image hook and stores it in the brand's Drive under `Creative Assets/Meta Posts/` — does NOT publish. Declarative `requires_generated_image` ClassVar on `ModuleBase` + generic `runs.py` hook (no capability hardcoded in core); `inject_channel_credentials` now surfaces `drive_root_folder_id` for google_drive. Validated live via `/chat` on the Klaroha brand. Per-brand isolation confirmed: a brand without a Drive connection correctly fails closed (no fallback to another brand's Drive). Detail: `CREATIVE_SUPPLY_CHAIN.md`. |
| 3.40 | 2026-05-24 | **Platform OAuth Broker — customer self-host model:** Locked the deployment model — BOS is self-hosted by customers in their own cloud, but the system/integrations are Klaroha's (Windows-install analogy: customers run the OS, auth against Microsoft's identity, never register their own app). Third-party OAuth (Google Drive/Gmail/Calendar/YouTube, Meta) must require ZERO per-customer provider setup; BYO-Google-app per deployment is explicitly rejected. Mechanism: one Klaroha-run central OAuth broker holding one verified app + Picker key, one stable redirect URI, signed one-time token handoff back to each self-hosted instance. Critical scope: broker only changes token *acquisition* — `get_page_token()`, `social_connections`, channel plugins, and the creative factory are unaffected, so feature work does not block on it. Broker is its own platform mini-project (needs Google verification + CASA, Klaroha-hosted Picker page). Current single Klaroha dev box continues on env-var platform credentials until the broker is built. See Section 7 → Platform OAuth Broker. |
| 3.39 | 2026-05-24 | **Creative Supply Chain mini-project:** Channel-agnostic creative manufacturing layer (concept → primitives → blueprint CompositionSpec → stitch/render → export) between campaign strategy and channel distribution. BOS is routing/orchestration only — all generation/rendering is third-party (image/video AI, Shotstack/Creatomate/FFmpeg, Huashu); BOS builds the JSON request and captures the result. Per-brand Google Drive as asset library (operator picks existing root folder via Google Picker). Full detail in `CREATIVE_SUPPLY_CHAIN.md`. Phase A foundation built: `creative_jobs`/`creative_assets`/`creative_blueprints` tables, Google Drive OAuth connection layer + Picker folder selection. |
| 3.37 | 2026-05-22 | **CMO/Council Loop Marching Orders:** Distilled Phase 6 agentic direction after pi.dev comparison and agency-process discussion. Klaroha applies pi-style loop mechanics inside a business/marketing operating system for overloaded multi-brand operators. Two loops are distinct: the CMO execution loop shortens idea → artifact → approval → memory, while the Council deliberation loop is explicit `@council` escalation for high-stakes GTM, brand, budget, resource, and positioning judgment. Council's final product is a `council_brief` artifact; transcript may be supporting detail. Creative production defaults to parallel specialists from a shared brief, with sequential chaining reserved for risk/dependency. Full details live in `api/routers/chat_notes.md`. |
| 3.36 | 2026-05-21 | **Shortform Video Production + Publishing Pipeline Direction:** Added Phase 6 build direction for high-volume shortform content. The fastest path is not cinematic text-to-video generation; it is template-rendered vertical assets: content atom → script → voiceover → motion text/branded template → captions/metadata → `shortform_video_asset` artifact → Stream approval → export/manual scheduler handoff first, then approval-gated native publishing plugins. A new non-channel `media-shortform` specialist should own generation/rendering/storage/QA. Platform publishing remains plugin-owned: YouTube Shorts first (Google OAuth/API pattern already familiar), Meta/Instagram Reels second (existing Meta plugin/OAuth path), TikTok later/manual export until Content Posting API approval is clear. No shortform platform behavior belongs in CMO chat routing or BOS core. |
| 1.0-1.7 | 2026-05-01..06 | Foundation, Core API, Provider Layer (BYOK), Frontend Shell, and CMO Chat. |
| 1.8-1.9 | 2026-05-06 | Admin UX refresh to setup-first flow; OpenAI login auth enabled. |
| 1.10 | 2026-05-06 | Fixed OpenAI runtime routing and token storage limits. |
| 2.0 | 2026-05-06 | **Architectural Pivot:** Transitioned from single-workspace to Org $\to$ Brand $\to$ Campaign hierarchy to support multi-business management by a single CMO. |
| 2.1 | 2026-05-07 | Required onboarding now includes an approved Campaign Brand Kit, stored as a tagged PostgreSQL document rather than hard-coded brand/design columns. |
| 2.2 | 2026-05-08 | CMO chat refined into a context-aware executive interface: no scripted new-chat greetings, discussion questions do not trigger modules, brand brief/product/audience/Brand Kit context is loaded into CMO responses, generated module results become persistent pending approval decisions, and modification flows use LLM-backed revision threads. |
| 2.3 | 2026-05-08 | Adopted `SKILL.md` principles for BOS: expertise is modular, explicit, triggerable, source-linked, and workflow-bound. Skills become the CMO's intent/memory/workflow contracts around modules and workspace resources. |
| 2.4 | 2026-05-08 | Added atomic need-to-know skill resource model and SOP ingestion governance: SOPs produce versioned change proposals across skills, resources, modules, memory, and config rather than blindly overwriting operational contracts. |
| 2.5 | 2026-05-08 | Modeled BOS skill support principles from Agent Skills client implementation: discover by `SKILL.md`, catalog metadata first, activate full instructions only when needed, list resources without eager loading, preserve/deduplicate activated skills, and enforce BOS governance before model exposure. |
| 2.6 | 2026-05-08 | Reverse-engineered canonical BOS skill shape from SEO, email-sequence, and analytics-tracking samples: descriptions act as activation policy, related skills define routing boundaries, required context drives intake, resources remain lazy, caveats become quality gates, and output format becomes evaluation contract. |
| 2.7 | 2026-05-08 | Added executable `marketing.email.sequence` module linked to the atomic email sequence skill; SEO audit and analytics tracking remain skill-only until their data/tool requirements are defined. |
| 2.8 | 2026-05-08 | Expanded BOS beyond marketing by adding nested internal service-delivery modules. Module discovery now recurses under verticals, enabling structures like `api/modules/internal/client_onboarding/google_business_profile.py` for provider-specific operating capabilities. |
| 2.9 | 2026-05-08 | Added Google Business Profile post ideas as a marketing skill/module using the 50-tactic checklist resource; distinguished organic GBP posts from internal GBP client onboarding and paid Google ads. |
| 3.0 | 2026-05-08 | Reframed the external product brand as Klaroha: marketing, engineered for clarity. BOS remains the internal architecture; Klaroha is the customer-facing promise of collapsing marketing signal complexity into a transparent command center. |
| 3.1 | 2026-05-08 | Added long-form Brand Guidelines as the Brand-plane source of truth. Campaign Brand Kit is now the shorter campaign execution summary derived from Brand Guidelines. Admin Workspace exposes both documents. |
| 3.2 | 2026-05-09 | Added Meta MCP sidecar direction: read-only Meta paid ads performance and Page/comment monitoring can use a local MCP-compatible connector first, while BOS keeps stable capability contracts so native Meta API write/spend actions can replace or extend it later. |
| 3.3 | 2026-05-10 | Adopted capability-centric directory layout (`api/capabilities/`) compatible with Claude Code skills discovery and MCP tool/resource/prompt registration. Each capability is a self-contained directory: `SKILL.md` + `module.py` + `template.j2` + resources. Internal client onboarding becomes a `workflows/` checklist system, not a capability module. GBP is a marketing channel only. |
| 3.4 | 2026-05-10 | Added @klar Plan Mode strategic planning capability (`workspace.plan_mode`): skill-activated, extended thinking, mobile-first card-stack output format. Added Facebook Page Management social layer: agency app model (one platform Meta Developer App, brands authorize via OAuth, system holds long-lived page tokens per brand). New: `social_connections` table, `SocialConnection` model, `/social` router, `providers/facebook.py`, `FacebookPageOAuthHandler`. New document types for plan memory slots: `marketing_report`, `campaign_report`, `competitor_profile`, `industry_report`. |
| 3.5 | 2026-05-10 | **Channel Plugin Architecture:** Third-party channels install into `api/plugins/` and integrate via `klaroha_sdk` — one stable import, no internal access. Plugin contract: `channel.json` manifest + `ChannelModule` subclass + SKILL.md. Host scans plugins at startup identically to first-party capabilities. Credentials injected at execution time via `inject_channel_credentials()` in runs.py. Facebook page management is the first validation plugin built externally. |
| 3.6 | 2026-05-11 | **Gmail Channel Integration:** Gmail OAuth added as a first-class social connection (`GmailOAuthHandler`, PKCE OAuth2, Google token endpoint). Gmail accounts connect per-brand identically to Facebook. Token auto-refresh implemented in `get_page_token()` — expired access tokens are refreshed transparently using stored `refresh_token_encrypted` from `token_meta_json`. Plugin skill discovery gap fixed: `register_skill_root()` in `skills/loader.py` now called by `registry._scan()` so plugin SKILL.md files are fully discoverable from CMO chat routing. Bug fixed: `inject_channel_credentials()` was only in the LLM execution path — moved before `execute_tool_result` so plugin tool modules receive credentials. Gmail send and receive now dispatchable from CMO chat with distinct platform hints (`gmail send` / `gmail inbox`). |
| 3.7 | 2026-05-12 | **Strict Plugin Model + Facebook Page Management Pipeline:** All channel Transform nodes removed from `api/capabilities/marketing/channel/` — this directory is deleted. All channel capabilities are now third-party plugins in `api/plugins/`. Legacy `api/skills/marketing/` channel skill files removed. System prompt module ID examples replaced with dynamic registry-driven references. Broad sample ads fallback made registry-driven — no hardcoded module IDs anywhere. `api/plugins/facebook/` built as the first production plugin: organic page post (copy gen), organic page publish (execute_tool_result → Graph API), paid ads copy. Build direction: pipeline first — the draft → approve → publish sequence is the primary target before adding more channel capabilities. |
| 3.8 | 2026-05-12 | **Gmail-Only + LLM-Driven CMO Capability Registry:** At this checkpoint, Facebook, Twitter, Meta, and Google Ads channel capabilities/plugins were removed to reset around Gmail-only focus and eliminate hardcoded routing. Created `api/capability_manifest.py` as the single source of truth for CMO-dispatchable capabilities — generated at runtime from installed SKILL.md files, injected into CMO system prompt. CMO LLM reads the manifest and uses its own judgment to invoke capabilities; no platform-specific routing, phrase-matching, or module dispatch rules exist in `routers/chat.py` or `skills/router.py`. `_build_system_prompt()` no longer accepts a `modules` list parameter — capability list is fully self-contained via `format_manifest_for_prompt()`. Superseded for Google Ads scope by v3.11, which reintroduces Google Ads as a plugin-owned specialist only. |
| 3.9 | 2026-05-12 | **CMO-in-Pocket Marketing Operating Model:** BOS product architecture is now anchored on the promise that a small business owner gets the leverage of an enterprise marketing department without managing 27 SaaS dashboards. CMO-facing marketing work collapses to three durable jobs — `marketing.plan`, `marketing.execute`, and `marketing.optimize`. Channel/vendor/plugin specifics such as Google Ads, Gmail, Meta, Search Console, or GTM are specialist/tool implementations behind those jobs, not the primary product language or a thousand-entry capability catalog. |
| 3.10 | 2026-05-13 | **Workspace Artifacts Canonical Plane:** CMO chat no longer renders platform-native artifacts inline. Chat returns concise narrative plus artifact references; Workspace owns artifact review/native previews; Stream surfaces the same persisted artifact records for mobile. Plugins/capabilities continue to return typed artifact blocks, but chat stores/links references rather than duplicating native content in conversation history. |
| 3.11 | 2026-05-13 | **Google Ads Full-Control Direction:** Google Ads is back in scope as a plugin-owned specialist, not BOS core behavior. Approved sample `sample/google_ads_full_control_v1.md` and reverse-spec `api/plugins/google-ads/FULL_CONTROL_SPEC.md` define the control ladder: read diagnostics, draft recommendations, approved selected mutations, destructive second-confirmation actions, and mandatory audit/rollback metadata. Current installed Google Ads capabilities remain read/draft only until approval-gated action capabilities are added. |
| 3.12 | 2026-05-13 | **Mobile-First CMO Replies:** Approved `sample/mobile_cmo_reply_style_v1.md` as the CMO chat style contract. Normal CMO replies should read like short mobile operator messages: 1–4 short lines, one idea per line, bullets for choices, one question max, no dense paragraphs, while preserving Workspace artifact boundaries. |
| 3.13 | 2026-05-13 | **Native Marketing Planning Specialist:** Approved `sample/marketing_planning_specialist_v1.md` and added `marketing.plan.campaign_strategy` as a first-party planning Transform. `@klar plan` now resolves brand context and creates a reviewable Workspace plan artifact instead of pasting long markdown plans into mobile chat. |
| 3.14 | 2026-05-13 | **Search Console Plugin Next:** Google Search Console is the next plugin target after Google Ads read expansion. It must follow the same plugin-only/BITE sequence: produce and approve a sample first, reverse-spec from that sample, then build read-only `marketing.optimize` artifacts for properties, queries, pages, CTR, impressions, clicks, position, indexing/coverage signals, and SEO opportunity recommendations. The Search Console plugin must be custom-built for BOS against native Google Search Console APIs only — no Membrane, Rube, Composio, or arbitrary MCP sidecar. No Search Console behavior belongs in CMO chat routing or BOS core. |
| 3.15 | 2026-05-13 | **Search Console Plugin v1:** Added custom native Google Search Console plugin under `api/plugins/search-console/` with five read-only `marketing.optimize` capabilities: properties list, performance query, URL inspection, sitemaps read, and SEO opportunity plan. Added plugin manifest, contracts, spec, docs, tests, and `.env.example` variables. V1 remains read-only: no sitemap submit/delete, add/delete site, indexing request, website edit, Membrane, Rube, Composio, MCP sidecar, or BOS core/chat-router logic. |
| 3.16 | 2026-05-13 | **Brand isolation fix:** CMO module dispatch and revise endpoint were using `_resolve_brief(db, ws)` — always workspace-scoped — even when an active Brand was set. Fixed: `chat.py` module dispatch now calls `_brand_scoped_brief(db, ws, active_brand, overrides)`; revise endpoint resolves brand from `original_run.brand_id` and uses the same path for both system prompt and execution brief. `_resolve_brief` is workspace-only and must not be used for module dispatch when an active brand is set. |
| 3.17 | 2026-05-15 | **Active-brand CMO context isolation:** Found remaining bleed paths after v3.16: `hydrate_memory_slots()` still loaded workspace-wide memory into active-brand chat prompts, and `_brand_scoped_brief()` called workspace fallback before overlaying Brand rows. Fixed: active-brand memory now filters products, audiences, docs, and run memory by `brand_id`; `_brand_scoped_brief()` builds from overrides + Brand rows only; CMO prompt now includes an active-brand isolation rule and trace logs expose scoped counts without content. |
| 3.18 | 2026-05-15 | **Unscoped artifact dispatch guard:** Found remaining path where frontend activeBrand state was lost after reload, causing normal chat artifact runs to execute with `brand_id=NULL` and legacy workspace context (MotorMoto) even when the operator expected Klaroha. Fixed: frontend persists activeBrand; backend recovers Brand scope when the user names a Brand; org-level prompts with Brand rows list available Brands but do not load workspace brand/products/docs; artifact dispatch is blocked with a one-question brand clarification when no Brand can be resolved. |
| 3.19 | 2026-05-15 | **SKILL-owned Brand scope resolution:** Replaced mechanical brand hardlock/phrase switching with `workspace.scope_resolution` SKILL.md. The CMO now emits a hidden `SCOPE:` directive separating `conversation_brand`, `execution_brand`, and comparison mode. Chat code only validates the directive, resolves Brand names to IDs, blocks RUNs without an execution Brand in multi-brand workspaces, and passes the resolved `brand_id` into module execution. |
| 3.20 | 2026-05-15 | **Per-capability dev notes + bug sweep:** Introduced co-located `*_notes.md` files as the regression prevention system for each capability/plugin. Each notes file captures invariants, fixed bugs with the pattern that caused them, do-nots, and a short local backlog. Master `BACKLOG.md` remains core BOS only; plugin regressions stay in their plugin's notes file. Bug fixes this session: (1) named-brand mention in chat no longer overrides a persisted brand_id without explicit switch intent (`_BRAND_SWITCH_INTENT_RE`); (2) revision runs now carry `brand_id` into `_execute_module()` (were getting `brand_id=NULL`); (3) Google Ads RSA headlines no longer cut mid-word — `_clip()` now truncates at word boundary. `api/routers/chat_notes.md` and `api/plugins/google-ads/plugin_notes.md` are the first two notes files. |
| 3.21 | 2026-05-15 | **Multi-dev workflow + domain structure:** Established full multi-dev engineering workflow. Domain structure: `hq.klaroha.com` = BOS Command Hub (internal); `staging.klaroha.com` = staging stack; `klaroha.com` = reserved for public Astro marketing site (Parking Lot). Infrastructure created: `.github/workflows/ci.yml` (pytest + banned-pattern guardrails on PR, SSH auto-deploy to staging on staging branch push, production on main push); `CODEOWNERS` (api/plugins/ scoped to Dev 2 + main dev, core paths main dev only); `docker-compose.staging.yml` (ports 8080/8001/5174, isolated bos_staging DB). CMS platforms (WordPress, Webflow, Shopify) parked as plugin publish targets following same model as Gmail/Google Ads. Pending server-side: Cloudflare DNS records, SSH deploy key setup, GitHub secrets, branch protection rules, non-root SSH lockdown. |
| 3.23 | 2026-05-16 | **Multi-dev pipeline operational:** All server-side infrastructure live. Host nginx deployed as edge router — `hq.klaroha.com` → prod stack (port 8090), `staging.klaroha.com` → staging stack (port 8080), unknown hosts rejected. CI/CD fully verified end-to-end: 33/33 tests pass, push to `staging` branch auto-deploys to staging.klaroha.com. Dev 2 (@kibanu) onboarded as plugin specialist with Write access scoped to `api/plugins/` via CODEOWNERS. GitHub secrets and branch protection pending GitHub Team upgrade for enforcement. Plugin architecture documented as WordPress/VS Code model — separate `bos-plugins` repo pattern identified for contractor access without core exposure. |
| 3.24 | 2026-05-16 | **Google Calendar Booking plugin:** First scheduling plugin added (`api/plugins/google-calendar/`). OAuth uses same Google app as Gmail — no new env vars for deploying orgs; calendar redirect URI auto-derives from `GOOGLE_REDIRECT_URI`. New models: `CalendarPage` (booking page settings per brand) + `CalendarBooking` (appointments). New router `/calendar/`: 5 authenticated endpoints (page CRUD, bookings list/cancel) + 3 public endpoints (availability, booking form, embeddable HTML widget). Availability engine checks existing bookings + Google Calendar FreeBusy API; creates Google Calendar events and sends Gmail confirmation on booking. Widget served at `/api/calendar/book/{slug}` — clients embed as an iframe. `FRONTEND_URL` local dev bug fixed: was `http://localhost` (port 80, nothing listening); corrected to `http://localhost:8090`. |
| 3.27 | 2026-05-19 | **Pi-pattern architecture insight documented:** Studied pi.dev (minimal terminal coding harness) to diagnose why `chat.py` regressions keep recurring. Root cause: the current chat endpoint is a 1,144-line monolith that owns routing, brand-scoping, prompt-building, directive parsing, dispatch, and command logic in one place — every bug fix can break the previous one. Pi avoids this with three mechanisms: (1) a fixed ~50-line core loop that never changes; (2) capabilities as filesystem objects (SKILL.md), not code branches; (3) extensions that subscribe to lifecycle hooks rather than modifying the pipeline. The target for BOS is a fixed 7-step chat contract (receive → context → LLM → strip directives → dispatch → persist → return) with all cross-cutting concerns (brand-scoping, memory hydration, connector context, `@klar` commands) moved into packages that subscribe to `bridge.before_transform` and other hooks. BITE mapping and full hook model documented in `api/routers/chat_notes.md`. |
| 3.28 | 2026-05-19 | **Streaming agentic loop:** CMO pipeline now streams via SSE (`POST /chat/stream`). Steps appear live as modules run; artifact refs land one at a time before the reply; step log persists as greyed ✓ so the operator sees the full execution trace. Backend: `StreamingResponse` endpoint + `_generate_chat_stream()` async generator + `_run_modules_streaming()` as single dispatch source of truth for both `/chat` and `/chat/stream`. Frontend: `api.chatStream()` async generator consumes SSE; `CmoChat.tsx` renders step labels with pulse animation during execution and ✓ on completion; step log is never removed if it accumulated steps. Nginx: dedicated `/api/chat/stream` location block with `proxy_buffering off` + `X-Accel-Buffering: no` response header (belt + suspenders — both required). |
| 3.29 | 2026-05-19 | **Campaign execution cascade architecture:** Defined the channel-sovereign execution model. Strategy layer (`marketing.plan`) produces positioning, message framing, and market segment — fully channel-agnostic. On plan approval, all enabled channel plugins receive the campaign brief simultaneously via parallel `RUN:` dispatch. Each channel plugin is self-sovereign: it knows its own enabled sub-capabilities (Google Ads: search ads, display banners, video; Meta: square post, carousel) and calls image gen (`media.image.generate`, already installed) with its own format specs. No sequential agentic loop is needed for V1 — copy and image both derive from the shared campaign brief in parallel dispatch. Two documented arch gaps define the build path: (A) image→publish handoff: `posts/draft` block carries `image_prompt`; `posts/publish` calls image gen + photo upload inline; (B) credential pre-check: surface connected channels in CMO system prompt so LLM self-selects before dispatching modules that will fail at execution. Phase 6 section 6.11 tracks the build. |
| 3.35 | 2026-05-21 | **Stream + CMO Unified Surface:** Stream page redesigned as a split-screen — CMO chat occupies the left column (40%) and the decision feed occupies the right (60%). Artifact links in CMO chat dispatch a `bos:focus-artifact` event that opens the run in Stream's side panel instead of the workspace slide-over; no navigation required. Mobile screens (≤900px) switch to full-screen single-panel mode: CMO chat is the default view; Stream slides in from the right when an artifact is focused; a `← Chat` button returns to CMO. The old Stream/Workspace mobile nav was removed; the prototype Stream/Admin tab bar is now the single bottom navigation on all screen sizes. Stream data bug fixed: `pendingRunItems` in localStorage accumulated stale rejected/failed runs, causing artifact count to jump between sessions (e.g. 41 vs 27) and stale localStorage data to overwrite live API `approval_status` (causing styling inconsistencies). Fix: API data is authoritative; localStorage items are only included if absent from the API response and created within the last hour. |
| 3.36 | 2026-05-22 | **Plugin Documentation Strategy:** Established plugin-specific documentation structure where each plugin maintains its own documentation directory under `api/plugins/{plugin-name}/docs/` to maintain separation of concerns and avoid documentation sprawl across the entire codebase. Each plugin maintains its own documentation structure with implementation guides, API endpoints, architecture changes, and a README hub. This approach ensures plugin-specific issues are documented in isolation, documentation doesn't need to be pulled up across all code changes, and each plugin maintains its own project brief and implementation logs. |
| 3.34 | 2026-05-21 | **Implementation note — prototype-to-localhost task failure:** Claude Code misunderstood the task for implementing `wireframes/bos-stream-first.html` into the local React app. The prototype is a UX/UI redesign spec — implementing it means translating its design patterns, component structure, layout, and interactions into working React components while preserving all existing functional capabilities (CMO chat, artifact pipeline, brand management, connectors, admin sections, etc.). What Claude Code actually did was copy-paste the HTML prototype into the working app at a route (`/cmo/prototype`) and mark the 13-item implementation queue complete. The existing React app capabilities were not visually updated to match the prototype. Any future implementation pass must treat `bos-stream-first.html` as a design reference only (do not modify it), identify the delta between prototype visual design and the current React component output, and implement those deltas per-component in `web/src/` without breaking existing API integrations. |
| 3.33 | 2026-05-20 | **Gate 2 Gmail-only objective loop proof passed:** Ran `api/scripts/prove_gate2_gmail_loop.py` successfully through the full primitive loop: Objective → Gmail draft artifact → approval → manual OutcomeRecord → MemoryEvent → DecisionBrief → Stream cards. Proof IDs: objective `0feb55a6-e430-420f-baa6-4d8bde820015`, Gmail draft run `5508783c-5835-49e3-bb08-a370562554ca`, OutcomeRecord `b0f17311-2309-4dba-a84b-47ae76a4b124`, MemoryEvent `415caee9-46b3-4955-be3a-3054045e5881`, DecisionBrief `b6f78179-cf24-457f-936f-683281e2e28c`. Verified Stream returns both `outcome` and `decision_brief` cards scoped to the proof objective, and the DecisionBrief uses recorded outcome memory to recommend the next Gmail artifact with approval boundary intact. Also added Admin → Agent Activity panel over `/agent/state` and pending run review queue, Campaign Brand Kit style injection for image generation prompts, and image-generation brand-compliance gate metadata/self-check. Started BITE sample for `creative_bundle` paired copy+image artifact at `sample/creative_bundle_artifact_v1.md`; no build until approved. |
| 3.32 | 2026-05-20 | **Gate 2 Handoff Brief + PendingDecision implementation:** Added `PendingDecision` object and API (`GET/POST /pending-decisions`, `POST /pending-decisions/{id}/resolve`) plus on-demand Handoff Brief endpoint (`GET /handoff/brief`). Pending decisions write structured `MemoryEvent` entries (`decision_not_to_act` when opened, `decision_made` when resolved). Handoff brief returns active objectives, performance narrative, pending decisions, committed actions, known risks, what is working/not, decided-against items, and recommended first action. Started Gate 2.6 proof harness at `api/scripts/prove_gate2_gmail_loop.py` to verify Objective → Gmail artifact → approval → outcome → memory → DecisionBrief → Stream cards. Gate 2.6 Gmail-only loop proof is now the active target. |
| 3.31 | 2026-05-20 | **Gate 2 primitives implementation:** Added live backend primitives for the Gmail-only objective loop: `Objective` anchor (`/objectives`), append-only `MemoryEvent` ledger (`/memory/events`) with passive run/artifact lifecycle writes, manual `evaluate_outcome` v0 (`/outcomes/evaluate`) creating `OutcomeRecord + MemoryEvent(type=outcome_recorded)`, and `DecisionBrief` v0 (`/decision-briefs/generate`). Stream builder now emits `outcome` and `decision_brief` StreamUpdate cards, and the web Stream renders backend StreamUpdate cards alongside persisted artifact cards. Next active target is Gate 2.5 Handoff Brief + PendingDecision. |
| 3.30 | 2026-05-20 | **Architecture alignment — judgment system, Gate 2 marching order:** BOS repositioned as a judgment system — competitive advantage is judgment quality, not production speed. Three layers formalized: Attention (eyes), Memory (intelligence), Execution (hands). Three surfaces: Stream (attention queue), CMO (steering), Admin (configuration). Six primitives mapped to layers: `read_signal`, `write_memory`, `create_artifact`, `request_approval`, `execute_approved_action`, `evaluate_outcome`. Six Stream card families frozen: `pending_artifact`, `decision_brief`, `setup_blocker`, `signal_update`, `outcome`, `council_brief`. Stream card contract defined: `objective_ref`, `card_type`, `why_now`, `confidence`, `primary_evidence`, `recommended_next`, `approval_boundary`, `allowed_actions`, `source_state`. CMO Council specified: 5 members (Strategist, Analyst, Creative, Channel Specialist, Devil's Advocate), two triggers (`strategic_complexity`, `persistent_dismissal`). Key data objects defined: `MemoryEvent` (append-only ledger, two write paths — passive lifecycle + active CMO rationale), `Objective`, `DecisionBrief`, `OutcomeRecord`, `PendingDecision` (deferred decision first-class object with `waiting_for`/`action_blocked` fields). Confidence model: `staleness_score + corroboration + instrumentation state`. Surfacing rule: signal surfaces only when it changes the recommended action for an active objective. Gate 1 sample complete: `sample/bos_stream_sample.md`. Gate 2 (active): six sequential steps proving one Gmail-only objective through the full primitive loop. Gate 3 (seven dependency-ordered items) and Parked list defined. Architecture doc at `sample/bos_systems_architecture.md`. |
| 3.26 | 2026-05-18 | **Backlog → ClickUp sync as build process:** `BACKLOG.md` is the source of truth; `Klaroha BOS` ClickUp list mirrors it for team visibility. Sync script at `api/plugins/clickup/scripts/sync_backlog.py` — idempotent, creates missing tasks, updates changed statuses, rate-limited to stay under ClickUp's 100 req/min cap. Documented in Section 9 (Technical Reference). Distinct from the product-level ClickUp plugin (`tasks.create`/`tasks.read` for client org workflows — app users never touch the backlog sync). |
| 3.25 | 2026-05-17 | **Import Brief scope gate + Getting Started banner:** AdminOnboarding now requires a scope selection step before the form — first-time users choose org vs brand; returning users pick from existing brands or create new. New brand imports create the Brand row first, then pass `brand_id` to ingest — workspace-level slot (`brand_id=NULL`) is never touched. Scope lock badge shown in update mode. Getting Started banner added to all admin pages; uses `workspace_configured && campaign_brand_kit_approved` instead of `all_ready` (which also checks module routing). `brand_profile_configured` in onboarding status now accepts `brand_json` on any Brand row, not only `ws.brand_json`. Deployment ops documented: two stacks (`bos` + `staging`) run from `~/bos/` using `docker-compose.yml` and `docker-compose.staging.yml`; correct deploy commands and known pitfalls captured in `DEPLOY.md` (git.md merged in). |

---

## Appendix B — Pi.dev Capability Development Standards

> Extracted 2026-05-25 from pi.dev documentation. Pi is the minimal agent harness BOS takes direct architectural inspiration from. These standards translate pi's patterns into BOS-specific rules. Where BOS already complies, the rule is a confirmation. Where BOS does not yet comply, the rule is a build target.

### B.1 SKILL.md is an activation contract, not a config file

Pi's progressive disclosure model: descriptions always in context; full instructions load on demand only. The description alone determines when the LLM activates a skill.

**BOS rules:**
- `description` must name direct task phrases, synonyms, exclusions, and handoffs — not a one-liner summary. Bad: "Facebook post helper." Good: "Drafts, formats, and publishes Facebook posts with image attachments. Use when the user wants to create or schedule a Facebook post."
- `description` ≤ 1024 chars. `name` ≤ 64 chars, lowercase-with-hyphens only.
- Full instructions (triggers, memory slots, template hints, quality gates) stay in the SKILL.md body — never bloat frontmatter.
- `allowed-tools` restricts what tools a skill can invoke. `disable-model-invocation: true` marks purely deterministic capabilities.
- BOS extends pi's base fields with: `allowed_from_chat`, `requires_intent`, `triggers`, `excluded_triggers`, `module_id`, `memory_slots`, `related_skills`, `output_contract`, `quality_gates`.

### B.2 Single-entrypoint plugin factory — one public surface

Pi extensions export one default factory function. All registration happens inside it. No side effects at import time.

**BOS rules:**
- Every plugin's `module.py` exposes one function: `execute(brief, context)`. Nothing else is public.
- Async startup work (token validation, credential check) belongs inside `execute()`, not at module import.
- Plugins register their own capabilities via `channel.json` and `SKILL.md`. The core router never inspects plugin internals.

### B.3 State in run records, never in process memory

Pi's explicit rule: store extension state in tool result `details` for session branching support. State is rebuilt from stored records on restart — never held in memory.

**BOS rules:**
- `Run` records are the canonical state. Never rely on in-process cache across API requests.
- The `execution_brief` passed to a module must be fully self-contained — the module never reaches out to reconstruct context not passed to it.
- Approval/revision state persists in the `Run` record (`approval_status`, `revision_of`). Never infer it from chat history.

### B.4 Typed JSONL event stream — deterministic lifecycle order

Pi streams `AgentSessionEvent` objects as newline-delimited JSON (LF-only). Event sequence is fixed and deterministic.

**BOS target stream event order:**
```
run_start → step_start → [delta...] → step_end → [approval_required] → run_end
```

**BOS rules:**
- Every stream event object carries: `type`, `run_id`, `timestamp`. No bare string messages.
- Retry and compaction events are explicit typed objects — never inlined into delta text.
- Module output passed back to the orchestrator must be bounded. Truncate and annotate; never silently drop content.
- `terminate: true` equivalent: modules may return `skip_followup: true` to prevent an automatic follow-up LLM call.

### B.5 RPC pattern — enqueue + stream, never block

Pi RPC: commands in via stdin (with optional `id` for correlation), events out via stdout. HTTP response never blocks waiting for LLM completion.

**BOS rules:**
- `POST /chat` and `POST /runs` return immediately with `run_id` (accepted response). Completion events come over the SSE stream.
- Webhook/callback payloads to external callers include the originating `request_id`.
- Mid-stream messages (steer vs follow-up) require explicit behavior declaration — not implicit ordering assumptions.

### B.6 Package manifest — explicit, glob-aware, auto-discovered

Pi packages declare resources under a `pi` key in `package.json`. Auto-discovery falls back to convention directories (`skills/`, `extensions/`, `prompts/`) when no manifest exists.

**BOS → pi mapping:**

| Pi concept | BOS equivalent | Location |
|---|---|---|
| `pi.skills` (package manifest) | plugin SKILL.md auto-scan | `api/plugins/{channel}/` |
| `pi.extensions` | plugin `module.py` (discovered by scanner) | same |
| `pi.prompts` | `template.j2` co-located in capability dir | same |
| glob exclusions `!pattern` | scanner ignore list | `capability_manifest.py` |
| peerDependencies `"*"` | BOS SDK import only (`from klaroha_sdk import ChannelModule`) | `module.py` |
| bundledDependencies | plugin-owned third-party libs declared in `channel.json` | `api/plugins/{channel}/channel.json` |

### B.7 Tool registration — schema-first, cancellable, output-bounded

Pi tools require typed `parameters` schema (TypeBox), an `AbortSignal` for cancellation, and output truncation above ~50 KB.

**BOS rules:**
- Every capability's `module.py` `execute()` must be cancellable — check a stop signal at each I/O boundary.
- Module output schemas are defined in Pydantic — not inferred from LLM output shape.
- Use `StringEnum`-style enumerations (not raw string unions) in schemas for cross-provider compatibility.
- If output exceeds safe context bounds, the module truncates and appends a truncation notice to the payload. Never silently drop content.

### B.8 Auth resolution — priority chain, never logged

Pi resolves credentials in strict priority: **runtime overrides → stored credentials → environment variables**. Keys are never logged or returned in responses.

**BOS auth resolution order (confirmed):**
```
SocialConnection row (per-brand, auto-refreshed) → BYOK encrypted key → platform env var
```

**BOS rules:**
- Never short-circuit this chain. If a `SocialConnection` row exists for the brand and platform, it is always the first source.
- Any code path that handles a raw token must not write it to logs, run output, or API responses.
- `get_page_token()` in `api/routers/social.py` is the only place token refresh logic lives. Callers never handle expired tokens themselves.

### B.9 Three run modes — interactive, single-shot, headless

Pi exports three modes: full TUI (interactive), single execution (print), JSON-RPC subprocess (headless).

**BOS rules:**
- Every capability must be invokable in at least two modes: **interactive** (CMO chat → Stream UX) and **headless** (direct `POST /runs`, no UX dependency).
- Approval gates must be bypassable via API flag (`auto_approve: true`) for programmatic/scheduled runs.
- `module.py` `execute()` must never import or reference UI components. Output is data; rendering belongs to the frontend.

### B.10 Security boundary — one gate, never re-checked downstream

Pi: extensions run with full system permissions; the only gate is at install time (trust the source). Pi does not re-verify intent inside execution.

**BOS rules (confirmed, from Locked Rule #4 and CLAUDE.md):**
- Security is enforced at one point: is this `module_id` in `allowed_module_ids`? If yes, dispatch. If no, log and skip.
- No intent re-checking, phrase re-matching, or platform re-filtering inside execution. The LLM decided; the manifest allowed it; the module runs.
- Channel credential scope is enforced at `inject_channel_credentials()` in `runs.py` — modules receive a scoped token, never full OAuth credentials.

### B.11 Concept → sample → build sequence (pi + BITE alignment)

Pi's async factory pattern allows one-time startup work before the pipeline runs. BOS uses BITE's Discuss → Sample → Agree → Reverse-spec → Build sequence for the same reason: validate shape before committing to implementation.

**BOS rules:**
- No new capability, plugin, or stream event type enters build without an approved sample in `sample/`.
- The sample must include both allowed and forbidden outcomes (per CLAUDE.md CMO rules).
- Progressive disclosure applies to samples too: produce the minimal sample that proves the shape, not a full production artifact.

### B.12 Pi → BOS full concept map

| Pi concept | BOS equivalent | File/location |
|---|---|---|
| Extension factory | Plugin `module.py` `execute()` | `api/plugins/{channel}/` |
| SKILL.md | SKILL.md | Co-located with module |
| `pi` manifest key | Plugin auto-scan config | `capability_manifest.py` |
| `registerTool()` | Executor interface | `api/providers/` |
| RPC JSON event stream | Run SSE stream | `api/routers/runs.py` + `Stream.tsx` |
| `AgentSession.prompt()` | CMO chat POST | `api/routers/chat.py` |
| `ctx.signal` (AbortSignal) | Run cancellation flag | orchestrator |
| `AuthStorage` priority chain | `get_page_token()` | `api/routers/social.py` |
| Session state rebuild on start | Run history replay | `api/routers/runs.py` |
| `extension_ui_request` | Approval gate event | Stream approval widget |
| `terminate: true` | `skip_followup: true` in module return | `module.py` |
| `renderCall` / `renderResult` | Artifact renderer hints (`layout_hint`) | Plugin output schema |

**Current BOS gaps vs pi.dev (build targets):**
1. Typed JSONL event lifecycle (run_start → step_start → delta → step_end → run_end) is not yet consistently enforced across all run types.
2. Explicit `AbortSignal` / cancellation propagation into `module.py` `execute()` is not implemented.
3. Output truncation with annotation is ad hoc — no standard utility function shared across modules.
