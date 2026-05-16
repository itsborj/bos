# BOS — Business Operating System
## Unified Project Brief

**Date:** 2026-05-15  
**Status:** Phase 3 in progress — Workspace artifact plane hardening, CMO-in-pocket operating model, plugin-owned channel specialists, LLM-driven capability dispatch; multi-dev workflow infrastructure established; domain structure live (hq.klaroha.com = Command Hub, staging.klaroha.com = staging, klaroha.com = public marketing/investor pages)  
**Version:** 3.22 (Public site live on klaroha.com)  

> **MANDATORY READING:** Before any new system update, feature build, or architectural change, read `BITE.md`. It is both the Business Implementation by Example methodology and the BOS architecture constitution for minimal core, plugin/package extensibility, SKILL.md ownership, live manifests, MCP boundaries, lifecycle hooks, and command registration.
---

## Changelog

| Version | Date | Changes |
|---|---|---|
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

---

## 0. Architecture Directive — Strict Plugin Model (Claude Skills + MCP Compatible)

> **This directive supersedes any prior layout described in this brief or in `CLAUDE.md`.** When in doubt, follow this section.

### BOS Core vs. Channel Plugins — Hard Boundary

**BOS core owns the pipeline. Plugins own the channel.**

`api/capabilities/marketing/channel/` **is deleted and must never be recreated.** Every channel Transform node — copy generators, publishers, analytics connectors, comment managers — lives in `api/plugins/{channel}/`. No exceptions.

```
BOS core (api/capabilities/)             Channel plugins (api/plugins/)
─────────────────────────────────────    ──────────────────────────────────
workspace/  ← CMO, plan mode, approval   gmail/      ← outreach draft (BYOK SMTP)
onboarding/ ← brand setup, brand kit     gmail-auth/ ← send + receive (OAuth/brand)
copywriting/← shared copy principles     google-ads/ ← paid search read/draft now; full-control roadmap
workflows/  ← operational checklists     search-console/ ← next marketing.optimize plugin target
                                         test_stub/  ← test harness
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
`@klar plan` resolves the active/requested brand, builds a brand-scoped planning brief, and calls the first-party `marketing.plan.campaign_strategy` Transform. Chat stays a short control surface; the plan itself is a persisted Workspace `plan_artifact` with structured `marketing_plan` block data for review, revision, approval, or dismissal. The older `workspace.plan_mode` skill remains as a planning context/resource contract, but mobile CMO output must not paste full plans inline.

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
- **Provider Access:** API keys and OAuth tokens (e.g., OpenAI, Gemini).
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
- **Social / Provider Connections:** Each brand can have one or more external connections stored per platform in the `social_connections` table (`brand_id`, `platform`, `page_id`, `access_token_encrypted`, `token_meta_json`) or through plugin-declared connector requirements. Gmail is an active OAuth channel connection: each brand connects its own Gmail account via PKCE OAuth2; `page_id` is the email address; `token_meta_json` holds `refresh_token_encrypted` + `expires_at` for silent token refresh. `get_page_token()` auto-refreshes OAuth tokens within 5 minutes of expiry before returning them to plugin modules. Google Ads is an active plugin-owned specialist direction: current capabilities use plugin-declared environment credentials for read/draft work, while full-control brand-scoped account mapping and approval-gated mutations must be implemented through plugin contracts rather than hardcoding platform flows into CMO chat. Search Console is the next plugin-owned specialist target and must begin with an approved BITE sample before any spec/build. Future plugins such as Meta or Amazon PPC must follow the same plugin-contract model.
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
- **Pending Decisions:** Generated artifacts surface in Stream as timestamped native previews until approved, revised, or dismissed. Draft Campaign Brand Kit review is linked from onboarding/Admin flows rather than normal CMO chat.
- **Admin:** Setup, memory, connectors, specialists, outcomes, and system/debug. Admin is not the daily marketing dashboard; it configures the company brain and specialist access.

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
├── Brands / Clients        # brand memory, products, audiences, guidelines, brand kit
├── Campaign Plans          # marketing.plan intent setup, not channel checkboxes
├── Specialists             # installed plugins/capabilities; implemented jobs/readiness/risk
├── Connectors              # brand/platform connections exposed from installed plugins
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

**Skill, memory, resource split:**
- **Skill:** How to behave for a class of work.
- **Memory:** Atomic facts and learnings BOS knows.
- **Resource:** Source documents and durable artifacts such as briefs, Brand Kits, examples, SOPs, references, scripts, validators, and performance reports.
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

  marketing/plan/campaign_strategy/SKILL.md # native campaign plan artifact; decide what to do
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
