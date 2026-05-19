# BOS — Backlog

**Last updated:** 2026-05-13
**Active phase:** Phase 3 — Frontend / CMO Command Hub refinement / Skill Contract preparation
---
## How to Use This
- Pick the topmost `[ ]` item in the current phase and work it.
- Mark `[~]` when started, `[x]` when done.
- Move to the next phase only when all items in the current phase are `[x]`.
- Add new items at the bottom of the relevant phase. Never reorder done items.
- `[!]` = blocked — note the blocker inline.
## Legend
```
[ ]  Todo
[~]  In Progress
[x]  Done
[!]  Blocked (note reason)
[-]  Deferred (moved out of scope for this phase)
## Phase 0 — Foundation ✓
### Reference & Planning
- [x] POC learnings extracted from cl_dm_os
- [x] Unified project brief written (PROJECT_BRIEF.md)
- [x] System shape sample agreed (sample/bos_v1.md)
- [x] BACKLOG.md initialized
- [x] CLAUDE.md written
### Repo Structure
- [x] Create folder skeleton (api/, web/, migrations/, templates/, providers/)
- [x] .env.example with all required vars documented
- [x] .gitignore
### Docker + Infrastructure
- [x] docker-compose.yml — services: api, db (postgres:16), web, nginx
- [x] nginx.conf — proxy api:8000, web:3000
- [x] Verify `docker compose up` starts all services
### Database
- [x] PostgreSQL connection confirmed from api container
- [x] Migration tooling chosen (Alembic)
- [x] Migration 0001: workspaces table
- [x] Migration 0002: core tables (products, audiences, campaigns)
- [x] Migration 0003: provider_keys table
- [x] Migration 0004: capabilities + model_options tables
- [x] Migration 0005: runs, run_attempts, run_results, run_traces tables
### API Skeleton
- [x] FastAPI project initialized
- [x] GET / returns version + health + db status
- [x] Basic API key auth middleware (header: X-API-Key)
- [x] Error response shape standardized (code, message, details)
- [x] Request/response logging middleware
## Phase 1 — Core API + Data Layer ✓
### Workspace
- [x] GET /workspace
- [x] PUT /workspace/brand
- [x] PUT /workspace/products (create + update)
- [x] PUT /workspace/audiences (create + update)
- [x] Workspace context auto-resolves on run (brief inherits from workspace)
### Module Registry
- [x] Module discovery via directory scan (modules/marketing/)
- [x] GET /verticals
- [x] GET /verticals/marketing/modules
- [x] GET /modules/{module_id}
- [x] First module file: marketing.ad_copy.facebook (mock)
- [x] Second module file: marketing.ad_copy.twitter (mock)
- [x] Third module file: marketing.ad_copy.google (mock)
### Capabilities
- [x] Capability profiles loaded from DB (seeded via migration)
- [x] GET /capabilities
- [x] Router: filter eligible candidates, rank by policy weights
### Runs — Mock Mode
- [x] POST /runs — triggers module, runs mock executor, stores result
- [x] Run stored in PostgreSQL with full BITE envelope
- [x] GET /runs — list with filters (module_id, status, date range)
- [x] GET /runs/{run_id} — full trace
- [x] run_summary equivalent in run trace
### Auth
- [x] API key generation endpoint (POST /auth/keys)
- [x] API key validated on all protected endpoints
- [x] Keys stored hashed in PostgreSQL
## Phase 2 — Provider Layer + BYOK ✓
### Platform Mode — OpenRouter Adapter
- [x] Provider adapter interface defined
- [x] OpenRouter adapter implemented
- [x] Live execution wired into executor
- [x] Response normalized to same shape as mock
- [ ] Real run: brief → OpenRouter → ad copy stored (needs PLATFORM_OPENROUTER_KEY in .env)
### BYOK
- [x] POST /providers/keys — register key (AES-256 encrypted)
- [x] DELETE /providers/keys/{provider}
- [x] GET /providers/keys — list registered providers (key value never returned)
- [x] BYOK execution path in executor
- [x] POST /providers/check — verify key + connectivity
- [ ] Real BYOK run: user's own OpenRouter key → ad copy stored (needs real key)
### Billing
- [x] Billing ledger tables confirmed
- [x] sell_price computed (provider_cost × MARKUP) for platform mode
- [x] BYOK runs: provider_cost tracked, sell_price = null
- [x] GET /billing/summary
- [x] GET /billing/runs/{run_id}
### Additional Adapters
- [x] Gemini adapter (gemini-2.0-flash, gemini-1.5-pro)
- [x] NVIDIA adapter (llama-3.1-8b, llama-3.3-70b)
- [-] Anthropic adapter — deferred; routed via OpenRouter
### Bug Fixes
- [x] BUG: Google Ads text module missing headline/description preview and block in API response
- [x] BUG: failed run mode always stored as "mock"
- [x] BUG: POST /providers/check false positive on OpenRouter
- [x] BUG: GET /runs date-range filter not implemented
- [x] BUG: POST /providers/check returns "unknown" for gemini/nvidia
- [x] BUG: twitter template doesn't enforce product_name
- [x] QUALITY: gemini-2.0-flash quality_tier upgraded to "high" (migration 008)
- [x] BUG: no fallback to next candidate on provider error
- [x] MISSING: GET /providers endpoint
## Phase 3 — Frontend (active)
**Goal:** Non-technical user directs CMO, reviews collateral bundles, approves or requests changes, reads performance reports — all from the web interface. Same runs triggerable via API.
### Pre-work (API gaps)
- [x] Workspace name: PUT /workspace endpoint
- [x] Auth bootstrap: POST /auth/bootstrap
- [x] Pagination metadata: GET /runs returns total count
- [x] Provider auth (pi-style): OAuth/login credential storage + /providers/login start/complete + executor credential resolution
- [x] OpenAI Chat provider login: browser auth flow + callback completion + executor/chat routing support
### Stack
- [x] React + Vite chosen
- [x] Decision documented in CLAUDE.md
- [x] Frontend project initialized in web/
- [x] Dev server wired into docker-compose
### CMO Chat — API
- [x] BUG: /chat sample-ad requests crashed on invalid generation-intent regex
- [x] BUG: Google sample-ad chat run returned partial because exact product self-check rejected punctuation/spacing variations
- [x] BUG: /chat "all modules ad coppy" returns prose instead of dispatching all ad-copy modules
- [x] BUG: Google ad-copy preview does not look like native Google Search result
- [x] BUG: Modify action does not send draft content/context with revision request
- [x] BUG: broad "sample ads from each module" returns prose instead of platform-native module cards
- [x] Workspace brand profile needs domain and social handle fields for native ad previews/context
- [x] POST /chat — conversational endpoint with real LLM routing
- [x] complete_messages() on OpenAICompatAdapter — multi-turn message history support (all adapters inherit)
- [x] BYOK-first provider selection for chat (gemini → nvidia → platform openrouter → mock)
- [x] _RUN_RE regex parses all RUN: triggers in LLM reply (not just last one)
- [x] Multi-module dispatch — runs[] in ChatResponse; brief resolved once, all triggered modules executed
- [x] System prompt scopes RUN: to current message only — prevents re-triggering from conversation history
- [x] Infrastructure invisibility enforced — CMO never exposes module IDs, providers, or API terms in reply
- [x] Mock fallback with warning log when all providers fail
### CMO Chat — Frontend
- [x] CmoChat.tsx send() wired to POST /chat (api.chat())
- [x] buildHistory() snapshots conversation before each send (excludes typing indicator and run cards)
- [x] Typing indicator while awaiting response
- [x] Reply text rendered as CMO message; run cards rendered per result in runs[]
- [x] Run card: platform label, content preview, self-check status, execution mode, link to full result
- [x] BUG FIX: isMounted guard removed — was silently discarding responses in React Strict Mode
- [x] BUG: frontend shell renders blank / nothing loads after OpenAI provider auth changes
- [x] Fix OpenAI auth execution routing: use the actual ChatGPT-account-supported endpoint/model path after successful provider login
### Onboarding
- [x] GET /onboarding/status — workspace configured, per-provider connection status (byok/platform/none), per-module readiness via capability router, all_ready boolean, issues[]
- [x] Migration 011: onboarding.brand_profiling capability + gemini/nvidia/openrouter model options
- [x] onboarding.brand_setup module — transforms brand inputs into structured JSON profile (brand_name, voice, tone, values[], products[], audiences[]); called during initial project/client setup only
- [x] onboarding/brand_setup.j2 template — synthesizes raw brand inputs with slot-by-slot guidance; outputs valid JSON only
- [x] BrandSetupModule.self_check — validates JSON parseable, required top-level fields present, products[] non-empty with name/tagline/benefits, audiences[] non-empty with name/demographics/pain_points
- [x] onboarding.brand_guidelines module — generates required Campaign Brand Kit for cohesive multi-platform marketing campaigns
- [x] Required Campaign Brand Kit onboarding artifact — store as tagged PostgreSQL document, not hard-coded design columns
### Surface-Agnostic Component System
**Must be built before collateral bundle work. All block rendering goes through this system.**
- [x] `SurfaceContext.ts` — define surface types: panel / full-screen / chat-inline / mobile-card
- [x] `SurfaceContext` provider component — wraps any rendering surface, exposes layout constraints
- [x] `BlockRenderer.tsx` — reads `BriefingBlock.layout_hint` → selects and renders correct component
- [x] `PanelSurface.tsx` — 420px right drawer constraints
- [x] `FullScreenSurface.tsx` — full viewport constraints
- [x] `ChatInlineSurface.tsx` — max 640px, inline in conversation
- [x] `MobileCardSurface.tsx` — full-width swipeable card
### Block Components
**Surface-agnostic. Data in, render out. No container knowledge.**
- [x] `NarrativeBlock.tsx` — CMO-authored text, organizational voice
- [x] `AlertBlock.tsx` — priority alert with action link
- [x] `ModuleCard.tsx` — health badge, channels, run count, latency, last run
- [x] `PerformanceReport.tsx` — stats grid + placeholder chart + campaign table; adapts layout via SurfaceContext
  - panel: 2-col stats + compact table
  - full-screen: 4-col stats + chart + detailed table with channel tabs (Google Ads / Social / Consolidated)
  - mobile-card: single stat per swipe or summary card
- [x] `ApprovalBundle.tsx` — platform-accurate preview + copy panel + approve/request changes
  - Variants: Google Search (SERP render), Google Display (banner dimensions), Facebook Feed, Instagram Feed, Instagram Story, Email (inbox + body), Pinterest
### Platform-Accurate Preview Components
**Sub-components of ApprovalBundle. Each renders the channel exactly as the end user sees it.**
- [x] `GoogleSearchPreview.tsx` — SERP format: Ad label, green URL, blue headline, description
- [x] `GoogleDisplayPreview.tsx` — banner at stated dimensions with creative placeholder
- [x] `FacebookFeedPreview.tsx` — page avatar, sponsored, copy, creative, CTA, reactions
- [x] `InstagramFeedPreview.tsx` — username, square creative, actions, caption
- [x] `InstagramStoryPreview.tsx` — vertical full-bleed, swipe-up zone
- [x] `EmailPreview.tsx` — inbox row (subject + preheader) then full body
- [x] `PinterestPreview.tsx` — vertical pin, title, description
### Web UI — Shell
- [x] Sidebar: conversation history list, pending decisions pill, Settings link, Workspace link
- [x] CMO center: full-width chat shell (conversation history + input)
- [x] CMO messages render NarrativeBlock, AlertBlock, PerformanceReport (chat-inline surface), ApprovalBundle (chat-inline surface)
- [x] Pending decisions pill: live count from decision_needed blocks; click opens Workspace panel
- [x] Workspace sliding panel: opens from right (420px), Campaigns only; Brand Kit, Modules, and Reports moved to Admin Workspace
- [x] Settings modal overlay: tabs = Providers & BYOK / API Usage / Run History
### Web UI — Workspace Panel Tabs
- [!] Campaigns tab: active campaigns list → past campaigns list; click to expand detail (BLOCKED: awaits Phase 4 campaigns API)
- [x] Modules tab moved to Admin Workspace; data from GET /verticals/marketing/modules
- [!] Reports tab moved to Admin Workspace with channel sub-tabs (BLOCKED: Phase 4 dependency)
### Web UI — Settings Modal Tabs
- [x] Providers & BYOK tab: per-provider rows — BYOK/Platform badge, Add/Remove key action (live API data)
- [x] API Usage tab: token consumption, cost per run (live from GET /billing/summary)
- [x] Run History tab: every module run — module ID, status, timestamp (live from GET /runs)
### Mobile UI
- [x] Stream tab: MobileCardSurface wrapping BriefingBlocks ordered by priority; swipeable
- [x] CMO tab: full-screen conversation interface (bos-cmo responsive layout)
- [!] Workspace tab: campaigns drill-down (BLOCKED: carries over to Phase 4)
### Existing Pages (carry-forward, update to new component system)
- [x] Dashboard / home
- [x] Workspace setup
- [x] Provider status
- [x] Module browser
- [x] Run a module
- [x] Run result
- [x] Run history
- [x] Ops screen: add Provider·Model and Latency columns to module health table
- [!] Intelligence screen: channel performance and product comparison tables (BLOCKED: Phase 4 dependency)
- [x] History screen: add Provider, Tokens, Cost columns; add Campaign column (Phase 4 dependency)
- [x] Settings screen: provider latency display (requires backend latency_ms in GET /providers)
### Stream + Intent
- [x] Intent contract storage (migration 009, models, CRUD, /intents router)
- [x] Stream generation (block generators, types, builder)
- [x] Chat agent integration — `clients/claude/` scaffold
### Bug Fixes (Phase 3)
- [x] FEATURE: Replace mechanical brand hardlock with SKILL.md-owned scope resolution for CMO chat; parse/validate LLM SCOPE directives and require execution_brand for artifacts.
- [x] BUG: Natural-language brand switching is broken when activeBrand is already set; messages like "how about for Motormoto" or "shift to Motormoto" stay scoped to Klaroha instead of resolving the named Brand.
- [x] TEST: Re-verify brand switching after chat.py changes — explicit follow-up switch dispatches MotorMoto artifact with MotorMoto `brand_id`, while incidental Brand mention remains in the persisted active Brand scope.
- [x] BUG: Gmail/Google artifacts in Klaroha context still contain MotorMoto copy; traced runs had `brand_id=NULL` because activeBrand was not persisted and org-level prompt fell back to MotorMoto workspace context. Fixed backend brand-name inference, no-brand org prompt isolation, unscoped artifact dispatch block, frontend activeBrand persistence, and dismissed the two wrong pending artifacts.
- [x] BUG: Localhost returns nginx 502 Bad Gateway after live server upload/deploy changes; traced nginx upstream to web:80 while stale web container was still Vite on :5173; rebuilt/recreated web/api and localhost now returns 200.
- [x] BUG: CMO chat leaks/cross-pulls context from another brand during active-brand turns. Bad sample: active Brand B asks "what do you know about us?" and answer mentions Brand A products/docs. Fixed sample: active Brand B answer only uses Brand B name/profile/products/audiences/docs, with no Brand A references; test via brand-scoped trace.
- [x] BUG: CMO answers capability questions like customer support/VA and generic sample ads bypass native channel output
- [x] BUG: Facebook plan/post chat requests produce generic CMO prose instead of dispatching platform-native module output
- [x] Update Klaroha brand docs to retain primary tagline Marketing, Engineered for Clarity
- [x] Add long Klaroha brand guideline/brief document to platform context
- [x] Update Klaroha workspace positioning from stale generic marketing context to approved demand-capture strategy
- [x] BUG: CMO recommends existing stored audience as a new market segment during positioning discussion
- [x] BUG: CMO chat strict backend override fails all chat instead of falling back to another live provider
- [x] BUG: Provider Access shows contradictory state like OpenAI Error while last check is connected
- [x] UX: Admin Provider Access information is scattered and hard to scan
- [x] BUG: Provider settings do not expose live/check/last-used status or model options, making broken CMO routing hard to diagnose
- [x] BUG: Google Ads performance run renders as approval/copy bundle with raw JSON instead of platform-style performance report
- [x] BUG: MCP connector context is hardcoded in CMO prompt instead of registry-driven for omnichannel scale
- [x] BUG: CMO LLM lacks operational connector context for MCP/system questions and asks user what MCP means
- [x] BUG: Google Ads MCP/performance requests like "check mcp for google ads" do not trigger the analytics module and CMO hallucinates MCP meaning
- [x] BUG: Campaign Brand Kit approval is not surfaced in the primary Workspace/pending-decision UX
- [x] BUG: Admin onboarding Step 3 shows Campaign Brand Kit title/status but not contents after approval
- [x] BUG: Admin module browser Run button points to non-routed /settings/run instead of manually triggering POST /runs
- [x] BUG: Admin/CMO UX has slow-loading pages; profile route/API timings and remove avoidable slow fetch/render paths
- [x] BUG: API reload crashes on campaigns router because CampaignSummaryResponse uses BaseModel without import
- [x] BUG: CMO/Layout frontend build fails because Layout.tsx references missing setPendingCount
- [x] BUG: GET /onboarding/status returns 500 when module platform_hint is None
- [x] BUG: admin provider UX only supports raw API keys; OAuth/login providers show wrong connected state and no connect flow
- [x] BUG: admin pages have weak / inconsistent whitespace and missing dedicated layout styling after setup-first refresh
- [x] BUG: latest admin styling/update leaves pages rendering as nothing
- [x] BUG: OpenAI provider login completion fails because encrypted OAuth tokens exceed current provider_keys column length
- [x] BUG: OpenAI OAuth connection stores successfully but provider check rejects the credential because BOS is using an unsupported Codex model/path for ChatGPT-account auth
- [x] BUG: CmoChat.tsx imports unused navigate, causing frontend production build failure
- [x] BUG: CmoChat.tsx link preview wrong route
- [x] BUG: provider login flow implemented for unused gitlab-duo instead of requested OpenAI auth provider
- [x] CLEANUP: remove gitlab-duo provider from provider auth flow, admin UI, and project docs
- [x] BUG: Auth connect button double-mount issue
- [x] BUG: Error messages showed generic fallback
- [x] BUG: Chat used hardcoded mock instead of real LLM (provider waterfall had wrong key lookup path)
- [x] BUG: isMounted.current guard blocked state updates — typing indicator stuck indefinitely in React Strict Mode
- [x] BUG: Regex _RUN_RE only captured last RUN: trigger — first modules silently dropped on multi-module response
- [x] BUG: System prompt re-triggered channels from conversation history — user saying "twitter" after earlier facebook/google messages ran all three
- [x] BUG: No desktop navigation link to return to chat after clicking away or following links
- [x] BUG: Non-functional "Request Changes" button and "CHANGES REQUESTED" status removed from ApprovalBundle — CMO chat handles feedback
- [x] BUG: Chat module dispatch ignored user's explicit channel names — triggered all modules instead of only named ones (fixed: strengthened system prompt with examples, strict regex, validation against user's current message, partial match for misspellings like "twit"→"twitter")
- [x] BUG: Chat module dispatch failed for misspelled/abbreviated channel names (twet, fb) — added channel mapping with abbreviations/misspellings and fallback intent parsing
- [x] BUG: Chat history lost when navigating away — added localStorage persistence to CmoChat, updated sidebar to show current chat preview, "New" button clears history
- [x] BUG: Brand Kit generated empty content — regenerated with proper content from brand guidelines (voice, tone, values, products, audiences)
- [x] BUG: CMO chat couldn't hold proper conversation — removed hardcoded intro/mock replies, made LLM handle everything naturally, system prompt rewritten for conversational CMO persona
- [x] BUG: CMO chat too verbose — tightened system prompt to 1-2 sentences max, never reveal RUN: syntax, lean executive style
- [x] BUG: CMO chat broke after lean refactor — LLM stopped outputting RUN: lines, validation logic filtered out follow-ups like "redo both" (fixed: only validate when user EXPLICITLY names channels, trust LLM for context follow-ups)
- [x] BUG: CMO chat does not call modules when users ask for channel collateral
- [x] BUG: New CMO chat auto-starts with duplicate scripted greetings
- [x] BUG: Generated module results need modify/revision thread UX
- [x] BUG: Revision thread CMO response is scripted instead of LLM-generated
- [x] BUG: Pending decisions count/list does not link to generated module approvals
- [x] BUG: New chat clears old discussion from left conversation list
- [x] BUG: Pending module decisions are lost when navigating away from chat
- [x] BUG: Workspace approval panel gets crowded by threaded modifications
- [x] BUG: Workspace Modify action feels generic instead of tied to its module/thread
- [x] BUG: White page after ApprovalBundle HMR served empty module
- [x] BUG: CMO chat mechanically triggers modules during discussion questions
- [x] BUG: CMO chat does not use ingested brand brief/workspace context in discussion — system prompt now includes workspace brand profile, products, audiences, and Campaign Brand Kit excerpt; verified `what is klaroha about?` returns contextual answer with no module runs
- [x] BUG: CMO chat can leak inline RUN directives and expose non-chat modules — inline RUN directives are stripped from visible replies, chat-dispatchable modules are limited to marketing modules, and `run> explain what klaroha is` no longer triggers runs
- [x] FEATURE: Add operator-configured model routing for the main CMO chat and per-module action runs via environment variables
- [x] DOC: Update project brief with corrected MOS/BITE omnichannel directive before code changes
- [x] FEATURE: Add modality-aware execution backend routing for CMO, modules, and specialized tools
- [x] FEATURE: Add Admin Module Browser controls for CMO brain and per-module backend overrides
- [x] UX: Refresh Stream and legacy/settings pages with executive hero cards, stats, and cleaner module/run layouts
- [x] UX: Rework Stream into TikTok-inspired daily marketing signal feed
### Skill Contract Preparation
- [x] Add file-backed skill directory scaffold under `api/skills/` for workspace context, approval review, marketing modules, and onboarding skills
- [x] Define initial `SKILL.md` frontmatter contract: `id`, `name`, `description`, `scope`, `allowed_from_chat`, `module_id`, `requires_intent`, `triggers`, `memory_slots`, and `quality_gates`
- [x] Implement skill loader that reads frontmatter for discovery and full Markdown body only after activation
- [x] Implement deterministic skill router for CMO chat: discussion/context skills vs generation/revision module skills
- [x] Implement memory slot hydrator for `brand_profile`, `product_catalog`, `audience_profiles`, `campaign_brand_kit`, and recent approved/rejected runs
- [x] Refactor `/chat` prompt assembly to compile activated skills + hydrated memory instead of one monolithic system prompt
- [x] Move chat-dispatch permissions out of hardcoded module filtering into skill frontmatter (`allowed_from_chat` + `requires_intent`)
- [x] Add quality gate to ensure hidden control directives like `RUN:` never appear in user-visible CMO replies
- [x] Add tests for skill discovery, activation, memory hydration, and chat dispatch non-regression examples — added `api/tests/test_skills.py`; smoke-tested manually because container image lacks pytest despite requirements entry
- [x] Update Admin/Workspace documentation to explain Skills as BOS operating contracts, not user-facing prompt hacks — documented in `PROJECT_BRIEF.md` and `api/skills/README.md`
- [x] Update project brief with atomic need-to-know skill resources and SOP ingestion governance model
- [x] Prepare sample SOP ingestion change proposal before implementation spec — `sample/sop_ingestion_change_proposal.md`
- [x] Update project brief with Agent Skills client-implementation principles adapted for BOS governance
- [x] Reverse-engineer canonical BOS skill shape from SEO/email/analytics samples and implement support for metadata routing, resource listing, related skills, and atomic sample skills
- [x] Create executable `marketing.email.sequence` module linked to the email sequence skill
- [x] Add nested internal client-onboarding capability for Google Business Profile and update module discovery to recurse
- [x] Add Google Business Profile client onboarding questionnaire as skill resource
- [x] Add Google Business Profile post ideas marketing skill/module from checklist SOP
- [x] DOC BUG: CLAUDE.md still described modules as flat-only after nested module architecture; updated agent-facing docs to prevent path hallucination
- [x] Add Klaroha About Us sample and update project brief with external brand reframe
- [x] BUG: Workspace Active Modules still surfaces legacy flat marketing module IDs instead of nested need-to-know operating paths
- [x] UX: Remove Modules/Reports from CMO Workspace panel and move those reference tabs into Admin Workspace
- [x] UX: Match desktop CMO Workspace Campaigns empty state to mobile Workspace sections
- [x] UX: Remove Brand Kit from CMO Workspace panel; keep Brand Kit review in Admin Workspace
- [x] UX: Make CMO chat artifact-first by hiding run logs/trace by default, compacting capability answers, improving approval middle states, and making Workspace act as attention/folder surface
- [x] UX: Move pending decisions out of left sidebar into Stream, remove chat artifact workspace link, and simplify approval actions with Dismiss + Revise
- [x] UX: Stream individual persisted chat artifacts with timestamped native platform previews, independent of deletable chat history, without changing Workspace
- [x] BUG: Stream page is not responsive and cannot scroll inside BOS shell
- [x] BUG: Stream Dismiss should remove artifact from feed; simplify CMO left/chat actions to New Chat, What can you do, and Plan a campaign
- [x] ARCH: Set CMO-in-pocket promise and collapsed marketing jobs (`marketing.plan`, `marketing.execute`, `marketing.optimize`) into PROJECT_BRIEF.md
- [!] ARCH VIOLATION: Remove leftover `api/capabilities/marketing/channel/` directory stubs/pycache and enforce channel capabilities as plugins only — BLOCKED: permission-owned `.pyc` files cannot be deleted from host user
- [ ] ARCH: Capability manifest v2 should expose CMO-facing jobs (`marketing.plan`, `marketing.execute`, `marketing.optimize`) with plugin implementation metadata instead of only raw module IDs
- [x] ARCH AUDIT: Re-check Admin/code/UX alignment after CMO-in-pocket and collapsed marketing jobs architecture update
- [x] ADMIN ALIGNMENT: Remove stale Facebook connect/page picker UI from Admin Brands; only installed/registered connectors should render
- [x] ADMIN ALIGNMENT: Replace channel-checkbox campaign builder with `marketing.plan` intent/job setup; remove hardcoded Facebook/Instagram/Twitter/Google Ads/LinkedIn list
- [x] ADMIN ALIGNMENT: Reframe Admin Modules as Specialists/Extensions inventory; hide manual Run actions from primary admin UX and show implemented jobs/readiness/risk instead
- [x] ADMIN ALIGNMENT: Reframe Admin Reports as future Marketing Intelligence/Outcomes; remove fake channel report tabs and "run modules" copy
- [x] BACKEND ALIGNMENT: Extend plugin manifest/SKILL metadata with `implements`, `specialty`, `platform`, `connector`, `risk_policy`, and output contracts for capability manifest v2
- [ ] BACKEND ALIGNMENT: Add generic installed connector registry endpoint for Admin instead of hardcoded provider/social UI assumptions
- [x] ARCH: Formalize Workspace Artifacts as canonical artifact plane; CMO chat returns artifact links only, while Workspace/Stream render native previews
- [x] BUG: CMO answers broad sample follow-up with inline email/Google Ads/Product examples instead of asking for a reviewable artifact or dispatching installed capabilities
- [x] DOCS: Document no-inline sample/artifact boundary across BITE, project brief, agent instructions, skills, and plugin SDK
- [x] GOOGLE ADS PLUGIN: Review cohenen/mcp-google-ads for plugin-only hardening inspiration; do not add MCP or skill changes
- [x] IMPLEMENT: Lean Admin structure — Brands/Clients, Campaign Plans, Specialists, Outcomes, System; remove stale channel-first admin UX
- [x] BUG: Admin Specialists still exposes raw module-level implementation details, backend controls, system IDs, and test stub
- [x] EMAIL MVP: Optimize Email Specialist around setup/readiness, campaign planning, draft artifacts, approved send/test flow, inbox reply intelligence, and optimization learnings
- [x] BUG: "let me see a plan for X" routes to no skill — marketing.plan.campaign_strategy and marketing.email.campaign_plan had requires_intent:[discussion] only; "let me see" classifies as generation intent so skill gate filtered both out; added generation to requires_intent on both
- [x] BUG: Email capability questions trigger execution/timeout instead of wrong execution artifacts; capability questions now route to Email Specialist overview card only
- [x] DOCS: Tighten BITE/brief/agent instructions around artifact taxonomy, sample gates, and capability-vs-execution boundaries
- [x] GOOGLE ADS PLUGIN MVP: Build a third-party, read-only Google Ads data-pull plugin without touching BOS core code
- [x] ARCH: Add Capability Outcome Contract v1 so CMO sends intent containers and capabilities/plugins return native artifacts
- [x] BUG: CMO left chat history panel is cramped and missing conversation delete controls
- [x] BUG: Web white screen after WorkspacePanel HMR served an empty transformed module
- [x] BUG: Broad skill triggers like post/ad/copy route unrelated channels when the user explicitly names X, Facebook, Google, or GBP
- [x] FEATURE: Update google-ads skill with comprehensive campaign management content (RSA ads, ad strength, GAQL, workflows)
- [x] FEATURE: Create launch-sequencing skill (PLF-style launch orchestration, v1.0.0)
- [x] FEATURE: Create launch-execution skill (launch checklists and coordination, v1.0.0)
- [x] FEATURE: Create launch-strategy skill (launch strategy and channel planning, v1.0.0)
- [x] FEATURE: Create google-ads-analysis skill (GAQL performance analysis, v1.0.0)

- [x] FEATURE: Create google-tag-manager skill (GTM workflows, tags/triggers/variables, v1.0.0)
- [x] FEATURE: Create metaads-automation skill (Meta Ads performance, page comments, v1.0.0)
- [x] FEATURE: Create campaign-structure skill (ABO vs CBO, targeting, budget rules, v1.0.0)
- [x] FEATURE: Create meta-social-comments skill (Facebook Page comment monitor, v1.0.0)
- [x] FEATURE: Update twitter-x-posts skill to v1.1.1 (X/Twitter post/thread guidance)
- [x] FEATURE: Update google-ads skill to v1.2.0 (BOS-aligned: RSA copy, campaign drafts, performance)
- [x] BUG FIX: Skills loader parser — empty `module_id:` set to `[]` instead of `None`, causing Pydantic validation failure
- [x] BUG FIX: Skills router — `_skill_platform()` not detecting `meta_ads` skill, fixed platform detection
- [x] BUG FIX: Chat router — added "design" to `_has_generation_intent()` patterns for campaign structure requests
- [x] BUG: Brand brief import updates content artifacts but does not rename/update the selected brand, causing imports like MotorMoto to leave the brand as Klaroha
- [x] UX: Reorder onboarding/import workflow to Brand Brief → Campaign Brand Kit → optional BYOK Provider Access
- [x] BUG: Gmail auth/connect flow is broken in Admin Provider/brand setup
- [x] SECURITY/UX: BYOK provider keys must be brand-scoped, not workspace/org-level, for brand runs and setup UI
- [x] GOOGLE ADS FULL CONTROL: Reverse-spec approved sample `sample/google_ads_full_control_v1.md` into plugin-only control ladder, approval tiers, mutation audit, and safety contracts — wrote `api/plugins/google-ads/FULL_CONTROL_SPEC.md`
- [x] GOOGLE ADS FULL CONTROL: Align docs/manifest with approved direction; resolve Gmail-only/project-brief conflict and plugin `GOOGLE_ADS_LOGIN_CUSTOMER_ID` optional-vs-required mismatch — updated PROJECT_BRIEF.md, cmo_context prompt, skill README, plugin README/contracts/changelog/spec, and channel.json v0.3.0
- [x] GOOGLE ADS FULL CONTROL: Inventory existing core Google Ads provider mutation methods and plan migration behind approval-gated plugin capabilities — wrote `api/plugins/google-ads/MUTATION_INVENTORY.md`
- [x] GOOGLE ADS FULL CONTROL: Add plugin-local read/write/edit/delete/optimization capability samples before implementation — wrote `api/plugins/google-ads/sample/full_control_capability_outputs_v1.md`
- [x] GOOGLE ADS FULL CONTROL: Implement first read expansion capabilities inside plugin only: account discovery and campaign report artifacts — added `account.discover` and `campaigns.read` plugin capabilities, updated channel.json v0.4.0/docs/tests
- [x] UX: Optimize CMO replies for mobile-first short-line style — implemented from approved sample: `sample/mobile_cmo_reply_style_v1.md`
- [x] FEATURE: Native Marketing Planning Specialist should create Workspace plan artifacts instead of long inline @klar plan replies — implemented from approved sample: `sample/marketing_planning_specialist_v1.md`
- [x] BUG: Native Marketing Planning Specialist artifact is too generic and UI is copy-oriented — removed hallucinated targets/channels, exposed focus/not-recommended/next-artifacts, and improved plan review labels
- [x] BUG: Native Marketing Planning Specialist fails for follow-up requests like “build another one for Klaroha” — tightened generic artifact-promise RUN rule and follow-up planning triggers
- [x] DOCS: Mark Search Console as the next plugin-owned `marketing.optimize` specialist after Google Ads read expansion; update PROJECT_BRIEF.md to v3.14 and preserve BITE sample-first gate
- [x] SEARCH CONSOLE PLUGIN: Produce Stage 2 sample output for Search Console property inventory, query/page performance, indexing signals, and SEO opportunity artifacts before spec/build — approved by user; custom BOS/native API only
- [x] SEARCH CONSOLE PLUGIN: Reverse-spec approved sample and build custom native Google Search Console plugin v1 read-only capabilities — added `api/plugins/search-console/` native API plugin with properties, performance, URL inspection, sitemaps, and opportunity plan capabilities
- [x] CLICKUP PLUGIN: BITE sample approved 2026-05-15 (tasks.read intelligence artifact + tasks.create approval-gated write). Reverse-spec and built native ClickUp plugin v0.1.0 — `api/plugins/clickup/` with `tasks.read` (marketing.optimize, read-only) and `tasks.create` (marketing.execute, approval-gated). Personal API token auth via `CLICKUP_API_TOKEN` + `CLICKUP_DEFAULT_LIST_ID`. Reference: ClickUp REST API v2 + Composio skill doc for pitfall inventory (no MCP, no CLI).
- [x] CLICKUP PLUGIN: In-BOS credential setup — `GET/POST/DELETE /plugins/{id}/credentials` stores encrypted plugin vars in `provider_keys` table (no migration needed); `inject_channel_credentials` checks DB before env vars so users configure connectors via Admin UI; Admin Specialists page shows ClickUp card with Configure modal.
- [x] CLICKUP PLUGIN: Full workspace coverage — removed `CLICKUP_DEFAULT_LIST_ID` from required credentials; `tasks.read` traverses all spaces/folders/lists and returns workspace-wide status grouped by space; `tasks.create` resolves target list from `brief["list_id"]` or `brief["list_name"]`, returns available lists if neither provided. v0.1.1.
- [x] CLICKUP PLUGIN: Exported full BOS backlog (642 tasks) to ClickUp Development list with phase/section context and status mapping ([x]→shipped, [ ]→backlog, [~]→in development, [!]→blocked, [-]→cancelled).

### Multi-Dev Pipeline (2026-05-16)
- [x] INFRA: Host nginx deployed as edge router — routes hq.klaroha.com → prod Docker nginx (8090), staging.klaroha.com → staging Docker nginx (8080), unknown hosts rejected (444)
- [x] INFRA: Production Docker nginx moved from port 80 to 8090; both domains live and isolated with separate DBs
- [x] INFRA: `docker-compose.staging.yml` deployed to server; staging stack live at staging.klaroha.com with isolated `bos_staging` DB
- [x] INFRA: GitHub Actions CI end-to-end verified — `Test & lint` (33/33) passes, `Deploy → staging` auto-deploys on push to staging branch
- [x] BUG: 8 stale test files importing from deleted `capabilities.marketing.channel` path removed from `api/tests/`
- [x] BUG: `test_brand_guidelines.py` had stale template path assertion (`brand_guidelines.j2` → `brand_guidelines/template.j2`) and section name mismatch (`Platform Rules` → `Multi-Platform Rules`)
- [x] INFRA: Dev 2 (@kibanu) added as plugin specialist — GitHub collaborator with Write access, CODEOWNERS scoped to `api/plugins/`
- [x] BUG: Production Docker nginx cached stale API container IP after rebuild; fixed by `docker compose restart nginx`
- [x] BUG: Production and staging API keys lost after stack restarts; bootstrapped fresh keys for both environments

### Testing
- [x] BUG: `api/tests/test_google_ads_skill_routing.py` imports removed chat intent helper `_has_diagnostic_intent`; updated stale test to SKILL.md/manifest-driven routing contract
- [x] FEATURE: Create launch-sequencing skill (PLF-style launch orchestration, v1.0.0)
- [x] BUG: Google Ads RSA headlines truncated/repetitive (e.g., "turn search demand into qualified leads with clearer Googl"); added template constraints + module self_check for truncation, trailing spaces, repetitive patterns, and boring "Brand | X" structures
Deferred to Phase 4.
- [x] BUG: Import Brand Brief overlapped org/brand data — importing via Getting Started with no brand_id in nav state silently wrote to workspace-level (`brand_id=NULL`), overwriting existing workspace profile and polluting org context in multi-brand workspaces
- [x] FEATURE: Import Brief scope gate — on first import (no brands): "Is this your Organization or a Brand?" step; when brands exist: brand selector listing existing brands + "New Brand" option; update mode (brand_id in nav state) is locked to that brand with a scope badge and cannot write to any other scope
- [x] FEATURE: New brand imports always create a Brand row first (via `POST /brands`) then pass the new `brand_id` to ingest — workspace-level slot (`brand_id=NULL`) is never touched in new-brand or update-brand flows
- [x] FEATURE: Getting Started checklist banner on all admin pages — fetches onboarding status on mount; shows dismissible amber strip until `workspace_configured && campaign_brand_kit_approved`; dismissal persisted in localStorage (`bos_gs_dismissed`)
- [x] FEATURE: Getting Started quick actions reordered — Import Brief (primary), Review Brand Memory, Manage AI Providers, Go to CMO (last); setup checklist labels updated to reflect multi-brand flow
- [x] BUG: Getting Started banner showed "Setup incomplete" when all 5 checklist steps were done — `all_ready` from onboarding status includes module routing checks that fail even with a complete setup; banner now uses `workspace_configured && campaign_brand_kit_approved` instead
- [x] BUG: `brand_profile_configured` in `GET /onboarding/status` only checked `ws.brand_json` — false in multi-brand workspaces where brand data lives in Brand rows; now also checks if any Brand row has `brand_json` set
## Admin Web Dashboard ✓
- [x] Route `/admin` — standalone dashboard shell
- [x] Overview: workspace name, billing summary, provider health
- [x] Run table: full filterable run history with pagination
- [x] Workspace editor: brand, products, audiences
- [x] Provider management: list, register/remove BYOK, connectivity checks
- [x] Module browser: list all modules by vertical
- [x] Admin UX refresh: replace generic dashboard-first flow with setup-first Getting Started flow
- [x] Admin nav refresh: prioritize Getting Started / Provider Access / Workspace above ops pages
- [x] Provider Access redesign: feature OpenAI Chat login as primary action; move generic provider matrix to secondary/advanced section
- [x] Onboarding redesign: convert current page into guided setup flow (provider access → brand brief import → review extracted profile → first test run)
- [x] Dashboard repositioning: move billing/ops metrics behind setup completion instead of using them as first admin landing state
## Phase 4 — Marketing Vertical Complete
### Modules
- [x] Add Meta MCP sidecar path for read-only paid ads performance and Page/comment monitoring
- [x] Add generic Google Ads campaign draft skill/module from user-provided Google Ads source without brand/entity hardcoding
- [x] Add mock Google Ads MCP connector and weekly performance summary skill/module
- [x] Google Ads MCP integration — 7 new capabilities (search_terms, keyword_performance, optimization_suggestions, budget_health, campaigns/list, campaigns/update_status, campaigns/update_budget)
  - [x] Extend providers/google_ads.py with GAQL methods (search_terms, keyword_performance, optimization_suggestions, budget_health, list_campaigns, update_campaign_status, update_campaign_budget)
  - [x] Extend providers/google_ads_mock.py with matching mock methods + module-level convenience functions
  - [x] Extend fixtures/google_ads_demo.json with keywords, device splits, recommendations, budget health data
  - [x] Tier 2 confirmation gate implemented in update_status and update_budget modules
- [x] All planned marketing modules with real prompt templates
- [x] Prompt templates draw from workspace (brand voice, product, audience)
- [x] Per-platform self_check (char limits, must-mention, banned phrases)
- [x] Module fan-out: run all marketing modules from one brief
- [x] marketing.email.cold_outreach module created
- [x] Add reusable copywriting skill module: copywriting_30_second_milo_frank
### Campaigns
- [x] Campaign model
- [x] POST /campaigns
- [x] POST /campaigns/{id}/run (placeholder - needs module dispatch logic)
- [x] GET /campaigns/{id}
### Approval Flow (full round-trip)
- [x] Approved bundle → status update in DB (backend complete)
- [ ] CMO acknowledges in conversation (frontend)
- [x] Feedback submitted → triggers module revision run (backend complete)
- [ ] Feedback submitted via chat → resubmits bundle (frontend)
- [x] Approval history stored per campaign (backend - parent_run_id)
- [ ] Approval history displayed in frontend
- [x] Migration 015: approval tracking fields (approval_status, feedback, parent_run_id)
- [x] Run model updated with approval fields
- [x] Migration 016: workspace_documents tagged document storage for Campaign Brand Kit and future workspace docs
- [x] Surface Campaign Brand Kit contents through a latest-kit endpoint and Admin Workspace tab
- [x] `api/tests/modules/marketing/test_ad_copy_facebook.py`
- [x] `api/tests/modules/marketing/test_ad_copy_twitter.py`
- [x] `api/tests/modules/marketing/test_ad_copy_google.py`
- [x] `api/tests/modules/marketing/test_email_cold_outreach.py`
- [x] `api/tests/modules/copywriting/test_copywriting_30_second_milo_frank.py`
- [ ] `web/src/tests/BlockRenderer.test.tsx` — layout_hint → correct component
- [ ] `web/src/tests/SurfaceContext.test.tsx` — same component, different layout per surface
- [ ] `web/src/tests/ApprovalBundle.test.tsx`
- [ ] `web/src/tests/PerformanceReport.test.tsx`
- [x] Frontend production build verification blocked locally: `web/node_modules` is root-owned and missing `react-router-dom`; `npm install` cannot write dependencies as current user
- [ ] Integration: submit run from browser, verify record in GET /runs
- [ ] Contract: same run via curl and UI produces identical DB record
### Output
- [x] Copy-paste ready export per platform (GET /runs/{id}/export)
- [x] Campaign summary: which modules passed, costs (GET /campaigns/{id}/summary)
## Phase 4 — Brand Architecture + @klar Command System

### Data Model
- [x] Migration 018: brands table (workspace_id FK, name, brand_json)
- [x] Migration 018: brand_id (nullable FK) added to products, audiences, workspace_documents, campaigns, runs
- [x] Migration 018: intent_ref (nullable FK → intent_contracts.id) added to runs — BITE plan hook
- [x] Brand SQLAlchemy model added to models/workspace.py
- [x] Run model updated with brand_id + intent_ref columns
- [x] WorkspaceDocument model updated with brand_id column

### Brand API
- [x] POST /brands — create brand
- [x] GET /brands — list brands with total
- [x] GET /brands/{id} — get brand detail
- [x] PUT /brands/{id} — update brand profile
- [x] DELETE /brands/{id} — delete brand
- [x] resolve_brand() helper — load Brand by ID (used by chat router)
- [x] find_brand_by_name() helper — case-insensitive name lookup with partial match fallback

### @klar Command System
- [x] _is_klar_command() — detects @klar prefix
- [x] _parse_klar_command() — routes to: brand_switch, plan, evaluate, pending, list_brands, directive
- [x] @klar check brand X / switch to X — loads brand by name, returns KlarAction{brand_switch}
- [x] @klar list brands — returns brand list with KlarAction{brand_list}
- [x] @klar what's pending — cross-brand pending decisions summary
- [x] @klar plan [description] — injects PLAN MODE instruction into LLM turn; no DB write until confirmation
- [x] @klar evaluate [campaign] — stub response with Phase 5 hook note; intent_ref FK is live
- [x] @klar [directive] with no active brand — returns "Which brand are we working on?"
- [x] KlarAction Pydantic model on ChatResponse (backend)
- [x] KlarAction type on ChatResponse (frontend types.ts)
- [x] brand_id field on ChatRequest — sent per chat turn by frontend

### Brand Context in Chat
- [x] active_brand resolved from body.brand_id at start of /chat endpoint
- [x] _build_system_prompt accepts brand param — loads brand-scoped products/audiences/docs when brand active
- [x] Falls back to workspace-level rows when no brand is active (backwards compatible)
- [x] System prompt labels context as "brand: X" vs "workspace" depending on active brand

### Frontend
- [x] BrandResponse, BrandListResponse, KlarAction types added to types.ts
- [x] api.getBrands(), createBrand(), getBrand(), updateBrand(), deleteBrand() added to client.ts
- [x] api.chat() accepts optional brandId param — included in POST /chat body
- [x] ActiveBrand type + activeBrand/setActiveBrand added to UIContext
- [x] Layout.tsx: activeBrand state wired into UIContext provider
- [x] Layout.tsx: active brand indicator shown in sidebar (green dot + name + clear button)
- [x] Sidebar logo renamed from BOS → Klar
- [x] CmoChat.tsx: reads activeBrand from UIContext, passes brand_id to api.chat()
- [x] CmoChat.tsx: handles klar_action brand_switch — calls setActiveBrand()

### Decisions Log additions
- [x] Org → Brand → Campaign hierarchy confirmed; Org = single company/agency, Brand = distinct client or business unit
- [x] @klar is the explicit CMO command prefix; without it, all messages are discussion-only
- [x] "Which brand are we working on?" is the no-context @klar response — one question, no list
- [x] hello klar / hey klar triggers org-level entry via existing LLM routing (no special handler needed)
- [x] tell me about klaroha → system identity answer from cmo_context skill, not brand data
- [x] @klar plan is a LLM-turn injection pattern; DB writes happen after user confirms the plan
- [x] @klar evaluate is a Phase 5 stub; intent_ref FK is live now so evaluate has data to compare against
- [x] Brand-scoped products/audiences/docs query when brand active; workspace-level fallback when no brand

### @klar Command — Additions (2026-05-10)
- [x] @klar org — clears active brand, returns to org-level context; KlarAction{brand_clear} clears activeBrand in frontend
- [x] @klar brief — stub response redirecting to Stream tab (Stream is the brief; @klar brief dropped as active command)
- [-] hello klar org-level briefing format — dropped; Stream tab handles cross-brand morning brief
- [x] CmoRail.tsx identified as dead code (built but never mounted); retained for potential future use

### Stream Redesign (2026-05-10)
- [x] Migration 019: campaign_id (nullable FK → campaigns.id) added to runs
- [x] Run model updated with campaign_id column
- [x] RunListItem schema (backend) updated: campaign_id, campaign_name, brand_id, approval_status
- [x] Runs list query joins Campaign table to populate campaign_name in one query
- [x] RunListItem type (frontend) updated: campaign_id, campaign_name, brand_id, approval_status
- [x] buildCampaignStream() — groups runs by campaign_id, infers channel from module path, approval-first sort
- [x] Stream.tsx redesigned — lean campaign-grouped cards, inline approve/revise, no cognitive load
- [x] buildBriefingStream() + countPendingDecisions() retained as legacy exports (used by ReportsView, AdminReports)

### UX Architecture Decisions (2026-05-10)
- [x] Campaign = organizing unit for Stream (not employee/module, not signal type)
- [x] Modules are invisible execution; output is organized by campaign + channel
- [x] Capability transparency surfaces at @klar plan time (before execution), not on output cards
- [x] Stream = campaign progress feed (TikTok-scroll, mobile-first)
- [x] Technical/Analytics runs = informational status line, no approval action
- [x] @klar org = explicit command to clear brand context (mirrors sidebar ✕ button)

### Pending (carry forward)
- [x] Run migrations: docker compose exec api alembic upgrade head
- [x] Admin brand management UI — brand list, add brand, brand detail (products/audiences/docs per brand)
- [x] Onboarding flow: import brand brief into a named brand (brand_id on products/audiences/docs)
- [x] @klar plan confirmation flow — save IntentContract + Campaign to DB after user approves plan draft; tags runs with campaign_id
  - [x] @klar confirm handler: creates Campaign + IntentContract + CampaignIntent in DB
  - [x] @klar run handler: resolves campaign by ID or name, falls through to LLM module dispatch
  - [x] campaign_id + brand_id threaded into _execute_module and Run creation
  - [x] Frontend: plan_draft klar_action → "Confirm Plan" button above input
  - [x] Frontend: plan_confirmed klar_action → activeCampaign set in UIContext + sidebar indicator
  - [x] Frontend: activeCampaign passed as campaign_id in every chat request
- [ ] Brand switcher dropdown in admin header (alongside @klar chat switching)
- [ ] Frontend tests: KlarAction handling, brand context state

### @klar Plan Mode (2026-05-10)
- [x] FEATURE: workspace.plan_mode skill v1.0.0 — full CMO strategic planner; 9 memory slots; omnichannel card-stack output; extended thinking; expandable resource drop-in
- [x] FEATURE: memory.py — 5 new slots: brand_guidelines, marketing_reports, campaign_reports, competitor_profiles, industry_data (all from workspace_documents by doc_type)
- [x] FEATURE: plan mode skill auto-activated in chat router when @klar plan fires; front-loaded before normal skill routing
- [x] BUG: @klar plan dispatched ad modules — dispatch decision tree re-added modules from conversation history execution intent; gated entire tree on `not pending_plan_action`
- [x] BUG: @klar plan LLM ignored skill contract — injected message referenced old section headers; rewrote to card-stack format with explicit NO TABLES / NO section headers directive
- [x] FEATURE: workspace.plan_mode v1.1.0 — mobile-first card-stack output contract; emoji channel anchors; confidence signals (⚠️ TBD); Hold rows; gaps list maps each resource to specific unlock
- [x] FEATURE: workspace.plan_mode v1.2.0 — concrete few-shot example added to skill body; quality gates updated to card-stack contract
- [-] Plan mode output format — LLM still falling back to document-style on some providers; deferred to v1.3.0 with further prompt reinforcement

### Facebook Page Management — Phase 1: Connect (2026-05-10)
**Architecture:** Platform-level Meta Developer App (agency model) — one app, all brands authorize once. No per-brand API keys.
- [x] Migration 020: social_connections table — brand_id FK, platform, page_id, page_name, page_handle, access_token_encrypted, status
- [x] models/social.py: SocialConnection SQLAlchemy model
- [x] providers/facebook.py: Graph API adapter — publish_post(), get_page_info(), get_pages_for_user(), exchange_for_long_lived_token()
- [x] provider_auth.py: FacebookPageOAuthHandler — browser OAuth, long-lived token exchange, multi-page support
- [x] routers/social.py: POST /social/connect/start, GET /social/facebook/callback (auto-completes flow), GET /social/connect/pages/{session_id}, POST /social/connect/select-page, GET /social/connections, DELETE /social/connections/{id}
- [x] routers/social.py: get_page_token() helper for publish modules to resolve brand page credentials
- [x] main.py: social router registered
- [x] config.py: FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, FACEBOOK_REDIRECT_URI, FRONTEND_URL
- [x] .env.example: Facebook vars documented with setup instructions
- [x] web: AdminBrands — Connect/Disconnect Facebook row per brand card; toast notifications; multi-page picker modal; OAuth callback param handling
- [x] web: api/client.ts — startSocialConnect, listSocialConnections, getPendingPages, selectSocialPage, disconnectSocial
- [x] BUG: Facebook OAuth opens in a popup, so callback params land in the popup instead of refreshing the Admin Brands connection row; fixed sample: same-window redirect returns to `/admin/brands?facebook=connected` and reloads the row. Sample: `sample/facebook_auth_page_management.md`.
- [x] BUG: Facebook OAuth defaults still point `FRONTEND_URL` at Vite `:3000` in config/.env.example; fixed sample: local nginx redirect defaults to `http://localhost`.
- [x] BUG: `/social/connect/start` surfaces missing Facebook/Gmail OAuth config as a 500 instead of a clear provider configuration error.
- [x] BUG: Frontend production build fails on stale KlarAction union and AdminBrands social/create-brand types while validating Facebook auth management.
- [x] Facebook Login for Business auth: support Meta Login Configuration ID (`config_id`) in OAuth start URL while keeping classic scope-based login as dev fallback.
- [ ] SETUP REQUIRED: Create Meta Developer App at developers.facebook.com; add FACEBOOK_APP_ID + FACEBOOK_APP_SECRET to .env; register callback URI; go through App Review for production use
- [-] Facebook Page publish module (capability + skill + CMO dispatch) — deferred; connect flow must be tested first
- [-] Facebook Page insights in Stream — deferred to Phase 5
- [-] Facebook comment management — deferred, user engagement scoped out for now

### Channel Plugin Infrastructure (2026-05-10)
**Architecture:** External channel plugins install into `api/plugins/`. Each declares a `channel.json` manifest. Klaroha scans plugins at startup alongside first-party capabilities — no core changes needed per channel. Plugin developers only import from `klaroha_sdk`.
- [x] `api/klaroha_sdk.py` — stable plugin developer import surface (`ChannelModule` only)
- [x] `api/plugin_loader.py` — `ChannelPluginManifest` schema, `scan_plugins()`, `get_plugin_for_module()`, `inject_channel_credentials()`
- [x] `api/module_base.py` — `register_template_root()` + multi-root Jinja2 env (plugins register their own template roots)
- [x] `api/registry.py` — extended `_scan()` to scan `api/plugins/` after capabilities; `_load_file()` accepts `root_dir` + `prefix` args; plugin modules load under `bos_ext_` namespace
- [x] `api/routers/runs.py` — `inject_channel_credentials()` called before `module.build_prompt(brief)` in the LLM execution path
- [x] `api/plugins/` — third-party plugin root created
- [x] `api/plugins/PLUGIN_SDK.md` — complete developer guide (channel.json schema, module.py pattern, credential injection, SKILL.md frontmatter, install steps)
- [x] TEST: Drop a minimal stub plugin into `api/plugins/test_stub/` and verify it loads in `GET /verticals`
- [x] ARCH: Strict 3rd-party plugin enforcement — all channel Transform nodes move to `api/plugins/`; `api/capabilities/marketing/channel/` deleted; legacy `api/skills/marketing/` channel files removed; chat.py system prompt examples made dynamic; broad sample ads fallback made registry-driven (no hardcoded module IDs)
- [x] Facebook channel plugin: `api/plugins/facebook/` — organic page post (copy gen), organic page publish (execute_tool_result → Graph API), paid ads copy; all via klaroha_sdk only; all 3 modules verified live in GET /verticals/marketing/modules; CMO chat routes to plugin correctly
- [-] Facebook channel plugin (external): `klaroha-channel-facebook` developed outside klaroha — superseded by strict plugin enforcement; build directly in `api/plugins/facebook/`
- [-] BITE sample: third-party Google Ads channel plugin output — `sample/google_ads_plugin_output.md` (awaiting human approval before spec/build)
- [x] SETUP: Facebook plugin live — all 3 modules verified in GET /verticals/marketing/modules; CMO chat routes correctly

### Facebook Page Management Pipeline — Wiring (2026-05-12)
**Rule:** Pipeline first. No new capabilities until draft → approve → publish is validated end-to-end.
- [x] `POST /social/facebook/publish/{run_id}` — approve run + fire publish module atomically; reads run content, resolves brand page credentials, returns `facebook_publish_result` block
- [ ] Frontend ApprovalBundle: "Approve & Publish" button for `platform_hint: facebook post` runs calls the new endpoint
- [ ] CMO chat confirmation: `facebook_publish_result` block rendered inline after publish
- [ ] TEST: end-to-end — brand with connected page → CMO drafts post → approves → post appears live on Facebook Page
- [ ] SETUP REQUIRED: Create Meta Developer App at developers.facebook.com; add FACEBOOK_APP_ID + FACEBOOK_APP_SECRET to .env; register callback URI

### Gmail OAuth Support (2026-05-11)
**Architecture:** Brand-scoped Gmail OAuth using existing SocialConnection table. Each brand connects its own Gmail account via PKCE OAuth2. Tokens stored encrypted; refresh_token persisted for long-lived access.
- [x] BUG FIX: `_store_connection()` in routers/social.py hardcoded platform="facebook" — generalized to accept `platform: str` parameter; all call sites updated
- [x] `provider_auth.py`: GmailOAuthHandler — PKCE OAuth2, Google authorize URL, token exchange, userinfo fetch, refresh_auth
- [x] config.py: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI settings
- [x] routers/social.py: GET /social/gmail/callback — validates session, completes login, stores SocialConnection(platform="gmail", page_id=email) with refresh_token in token_meta_json
- [x] .env.example: Google OAuth vars documented
- [x] plugins/gmail-auth SKILL.md files: fixed scope: execution → scope: module, requires_intent: execution → requires_intent: generation
- [x] TOKEN REFRESH: get_page_token() in social.py returns raw stored access_token without checking expiry or refreshing — Gmail tokens expire in 1 hour; wire refresh via GmailOAuthHandler.refresh_auth() using refresh_token from token_meta_json
- [ ] SETUP REQUIRED: Create Google OAuth 2.0 app in Google Cloud Console; enable Gmail API; add http://localhost:8000/social/gmail/callback as redirect URI; copy GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET to .env

### Plugin Skill Discovery Fix (2026-05-11)
**Root cause:** skills/loader.py only scanned api/capabilities/ — plugin SKILL.md files were invisible to CMO skill routing.
- [x] BUG FIX: `skills/loader.py` — added `_extra_skill_roots`, `_skill_file_map`, `register_skill_root()`, multi-root scan in `list_skill_manifests()`
- [x] BUG FIX: `registry.py` — calls `register_skill_root(str(cap_root))` alongside `register_template_root()` in `_scan()` so plugin skills are discovered at startup
- [x] BUG FIX: `PLUGIN_SDK.md` — corrected `scope: execution` → `scope: module` in SKILL.md template (was SDK documentation bug propagated to all 3rd party plugins)
- [x] BUG FIX: `plugins/gmail/capabilities/.../SKILL.md` — fixed scope: execution → scope: module (3rd party file broken by SDK docs)
- [x] TEST: Drop a minimal stub plugin into `api/plugins/test_stub/` and verify it loads in `GET /verticals` (validates the skill discovery fix end-to-end)
- [x] BUG FIX: SKILL.md frontmatter parser does not handle inline `[]` — passes literal string to Pydantic, silently drops skill; documented in PLUGIN_SDK.md; test_stub SKILL.md updated to omit empty list fields
- [x] BUG FIX: `inject_channel_credentials()` was only called in LLM execution path — moved before `execute_tool_result` check so plugin tool modules receive brand credentials
- [x] BUG FIX: `FRONTEND_URL` not set in .env — defaulted to http://localhost:3000 causing OAuth callbacks to redirect to wrong port; added `FRONTEND_URL=http://localhost` to .env
- [x] Google Cloud Console OAuth app created; GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET added to .env (angle brackets removed); Gmail API enabled
- [x] Gmail connect flow tested end-to-end: brand connected to jvcatingub@gmail.com via OAuth
- [x] Frontend AdminBrands.tsx: Gmail callback param handling (gmail=connected/denied/error) + Connect/Disconnect Gmail row per brand card
- [x] gmail-auth SKILL.md files: added `module_id:` field — was missing, causing skills to be excluded from CMO chat dispatch
- [x] gmail-auth module.py files: distinct platform hints (send → "gmail send", receive → "gmail inbox") — shared "gmail" hint caused both to fire on any gmail mention
- [x] chat.py `_requested_module_ids`: added "gmail send" and "gmail inbox" candidate expansion
- [x] BUG: `RunRequest` schema had no `brand_id`/`campaign_id` fields — silently dropped from POST /runs body; `_execute_module` always received `brand_id=None`; plugin credential injection never fired for direct runs
- [x] TEST: Send a real email via POST /runs — delivered to borj.villazorda@gmail.com, message_id 19e17eea95a3b69e, status success
- [x] TEST: Receive emails via POST /runs — 10 emails returned from jvcatingub@gmail.com inbox, status success
- [x] BUG: `_RUN_RE` stopped at `-` — LLM used skill name `gmail-auth-email-send` as RUN tag; regex left `-auth-email-send` visible in reply; fixed by adding `-` to character class
- [x] BUG: gmail send SKILL.md triggers too specific ("gmail send email") — "send an email to borj" and "send it" never activated the skill; added "send an email", "send email", "email to", "send it", "send the draft" as triggers
- [x] BUG: CMO claimed "I can't send emails" — LLM ignored module list; added explicit instruction #10 to system prompt stating BOS CAN send through connected Gmail and to never deny this capability
- [x] BUG: gmail send dispatched from chat with empty brief (no to/subject/body) — module would fail; added `_extract_email_fields()` to parse recipient from USER messages and email body from most recent AI message in conversation context before dispatching
- [x] BUG: `inject_channel_credentials` skipped credential lookup when brand_id=None (no @klar brand active in chat) — plugin modules always failed with "missing OAuth access token"; fixed by auto-resolving: query social_connections for the first connected brand for the required platform; also added `access_token` as an explicit credential alias alongside `page_token`

### Google Calendar OAuth + Admin Scheduling UI (2026-05-16)
**Architecture:** Brand-scoped Google Calendar OAuth. Each brand connects its own Google account via PKCE OAuth2. Tokens stored encrypted with refresh in token_meta_json. Booking pages and bookings managed via `/calendar/` router.
- [x] `provider_auth.py`: GoogleCalendarOAuthHandler — PKCE OAuth2, calendar-only scopes (`calendar openid email`), token exchange, userinfo fetch, refresh_auth
- [x] `provider_auth.py`: GOOGLE_CALENDAR_REDIRECT_URI auto-derived from GOOGLE_REDIRECT_URI when not set
- [x] `routers/social.py`: GET /social/google-calendar/callback — validates session, completes login, stores SocialConnection(platform="google_calendar")
- [x] `routers/social.py`: renamed `_admin_brands_redirect` → `_admin_connectors_redirect` — all OAuth callbacks now land at `/admin/connectors`
- [x] `nginx.conf`: added `/social/` and `/calendar/` proxy blocks — OAuth callbacks must hit nginx, not direct API port
- [x] `.env.example`: added GOOGLE_CALENDAR_REDIRECT_URI
- [x] `web/src/api/types.ts`: CalendarPageResponse, BookingResponse interfaces
- [x] `web/src/api/client.ts`: listCalendarPages, createCalendarPage, updateCalendarPage, deleteCalendarPage, listBookings, cancelBooking
- [x] `web/AdminBrands.tsx`: Google Calendar connect/disconnect row per brand card; google_calendar URL param handling + toasts
- [x] `web/AdminCalendar.tsx` (new): full scheduling page — booking page CRUD, duration/timezone/slug config, booking list with cancel
- [x] `web/AdminLayout.tsx`: Scheduling nav item added (Business section)
- [x] `web/App.tsx`: /admin/calendar route added
- [x] `web/AdminConnectors.tsx`: major rewrite — read-only OAuth connection summary with "Manage in Brands →" link; plugin connectors unchanged below
- [x] BUG FIX: `_GOOGLE_CALENDAR_SCOPES` included `gmail.send` — Google silently rejects Calendar redirect URI when Gmail scopes are included; fixed by removing `gmail.send`, leaving only `calendar openid email`
- [x] BUG FIX: `AdminCalendar.tsx` unused `pageBookings` variable causing tsc build failure
- [x] BUG FIX: web static build not hot-reloading — documented `docker compose build web && docker compose up -d web` rebuild requirement in CLAUDE.md
- [ ] SETUP REQUIRED: Add `https://hq.klaroha.com/social/google-calendar/callback` to Google Cloud Console authorized redirect URIs before production use
- [ ] FUTURE: `calendar.py` `_send_confirm()` uses Gmail API to send booking confirmations — Calendar token lacks `gmail.send` scope; wire through brand's Gmail SocialConnection token instead

### Native Booking Widget + Timezone Fixes (2026-05-17)
**Architecture:** BOS-native public booking UI served from API. No third-party (Calendly etc.). Google Calendar FreeBusy API for availability, Calendar Events API to create confirmed bookings. Universal embed via `widget.js` + `data-klaroha-booking` attribute.
- [x] `api/routers/calendar.py`: restored full booking system from git history — `GET /calendar/availability/{slug}` (public slots), `POST /calendar/book/{slug}` (public booking), `GET /calendar/book/{slug}` (standalone widget HTML)
- [x] `api/routers/calendar.py`: `GET /calendar/book/{slug}` returns `Content-Security-Policy: frame-ancestors *` so any external site can iframe the booking page
- [x] `api/routers/calendar.py`: `GET /calendar/widget.js` — vanilla JS injector; finds `[data-klaroha-booking="slug"]` containers and appends iframe to BOS booking page; replaces `__API_BASE__` at serve time with correct hostname
- [x] `api/main.py`: added `CORSMiddleware` (`allow_origins=["*"]`, GET/POST/OPTIONS) so widget requests work from external domains
- [x] `public/index.html`: CTA section replaced with `<div data-klaroha-booking="intro"></div>` embed + `<script src="/api/calendar/widget.js" async></script>`
- [x] BUG FIX: `_widget_html` JS — `fmtSlot` was ignoring the host timezone; slots now convert from host tz → visitor local tz using `Intl.DateTimeFormat`
- [x] BUG FIX: booking submission was sending browser local time instead of UTC; added `slotToUTC(isoDate, hhmm, hostTz)` helper that uses `Intl` API for DST-safe conversion
- [x] BUG FIX: `fmtDate` used `T00:00:00` (midnight, wrong day in negative-offset zones); changed to `T12:00:00`
- [x] BUG FIX: confirmation showed only host timezone, not visitor's local time; now shows both when they differ
- [x] `web/AdminCalendar.tsx`: timezone dropdown expanded from 9 hardcoded zones to ~80 IANA zones covering all regions including `Asia/Manila`
- [x] `web/AdminCalendar.tsx`: `browserTz()` auto-detects browser timezone; form defaults to detected tz instead of hardcoded `America/New_York`
- [x] `web/AdminCalendar.tsx`: `tzLabel(tz)` renders human-readable labels with UTC offset — `Asia/Manila (GMT+8)`
- [x] `web/AdminCalendar.tsx`: timezone select pins detected browser timezone first; remaining zones follow in alphabetical regional order

### Channel Cleanup + CMO Architecture (2026-05-12)
- [x] ARCH: Removed all Facebook capabilities — capabilities/, plugins/facebook/, providers/facebook.py, FacebookPageOAuthHandler, config fields, social router endpoints (/facebook/callback, /facebook/publish, select-page), connector registry entry, 7 test files
- [x] ARCH: Removed all Twitter capabilities — capabilities/marketing/channel/twitter/, related test files
- [x] ARCH: Removed all Meta capabilities — capabilities/marketing/channel/meta/, capabilities/marketing/meta_ads/, capabilities/marketing/campaign_structure/
- [x] ARCH: Removed all Google Ads channel capabilities — capabilities/marketing/channel/google/, capabilities/marketing/google_ads/, capabilities/internal/client_onboarding/google_business_profile/
- [x] ARCH: Cleaned skills/router.py — removed _explicit_platforms(), _skill_platform(), _is_broad_sample_ads_request(), broad sample ads block, debug print; only deterministic SKILL.md-driven routing remains
- [x] ARCH: Cleaned routers/chat.py — removed _has_generation_intent(), _has_revision_intent(), _is_question(), _has_diagnostic_intent(), _requests_all_ad_modules(), _requested_module_ids(); only security boundary check remains
- [x] FEATURE: Created api/capability_manifest.py — single source of truth for CMO-dispatchable capabilities; generated from installed SKILL.md files; CapabilityEntry dataclass; format_manifest_for_prompt() for system prompt injection
- [x] ARCH: _build_system_prompt() no longer accepts modules list parameter — capability manifest is self-contained via capability_manifest.py
- [x] ARCH: Removed BOS Skill Catalog from CMO system prompt — was causing prose catalog responses instead of module dispatch
- [x] ARCH: CMO system prompt "Deployable capabilities" section now populated entirely from capability_manifest.py; each entry shows exact RUN: directive the LLM should copy
- [x] ARCH: _strip_run_directives() now replaces RUN: lines with [Dispatched: Label] markers in visible reply so LLM can track what it already ran in conversation history
- [x] DOC: Updated CLAUDE.md — added "CMO Chat — Non-Negotiable Rules" section with 5 rules covering hardcoding prohibition, SKILL.md ownership, manifest authority, security boundary, and reply generation
- [x] DOC: Updated PROJECT_BRIEF.md to v3.8 — channel table, CMO Capability Registry section, version/status, decision log
- [x] DOC: Updated BACKLOG.md with all 2026-05-12 architectural changes

### Meta Plugin — Phase 1: Facebook Page + Posts (2026-05-18)
**Architecture:** Plugin-native Meta integration. `api/plugins/meta/` follows same channel plugin pattern as ClickUp/Gmail. OAuth uses `FacebookOAuthHandler` in provider_auth.py. Credentials injected via `inject_channel_credentials` from `social_connections` table. No providers/facebook.py — all API calls are in module.py files using urllib.request only.
- [x] Migration 026: widen `provider_login_sessions.verifier_encrypted` from VARCHAR(1024) to Text (needed for multi-page JSON storage in OAuth session)
- [x] `api/config.py`: add `meta_app_id`, `meta_app_secret`, `meta_redirect_uri` settings
- [x] `api/provider_auth.py`: `FacebookOAuthHandler` — step 1: exchange code → short-lived token; step 2: exchange → long-lived user token (60d); step 3: GET /me/accounts for pages + IG account IDs; registered as "facebook" in _OAUTH_HANDLERS
- [x] `api/routers/social.py`: `_admin_brands_redirect()` helper; `GET /social/facebook/callback` — auto-selects if 1 page, stores pages in session if multiple; `GET /social/facebook/pending-pages` — returns page list for session; `POST /social/facebook/select-page` — completes connection for selected page
- [x] `api/plugins/meta/channel.json`: plugin manifest v0.1.0, `requires_social_connection: ["facebook"]`, 4 capability IDs
- [x] `api/plugins/meta/capabilities/.../pages/read/`: `module.py` + `SKILL.md` — read-only page inventory via GET /{page_id}?fields=name,category,fan_count,...
- [x] `api/plugins/meta/capabilities/.../posts/read/`: `module.py` + `SKILL.md` — GET /{page_id}/posts, last 25 posts with engagement metrics
- [x] `api/plugins/meta/capabilities/.../posts/draft/`: `module.py` + `SKILL.md` + `template.j2` — LLM drafts post copy using brand voice/tone; returns `fb_page_post_draft` via `_build_block`
- [x] `api/plugins/meta/capabilities/.../posts/publish/`: `module.py` + `SKILL.md` — approval-gated POST /{page_id}/feed; returns `fb_page_post_result`
- [x] `.env.example`: Meta OAuth vars documented with setup instructions and redirect URI examples
- [x] `web/src/pages/admin/AdminBrands.tsx`: Facebook connect/disconnect row per brand card; multi-page picker modal; callback param handling (`facebook=connected/denied/error/select_page`)
- [x] `web/src/api/client.ts`: `facebookPendingPages()`, `facebookSelectPage()` methods
- [x] SETUP REQUIRED: Create Meta Developer App at developers.facebook.com → add Facebook Login → register redirect URI → add META_APP_ID + META_APP_SECRET to .env; go through App Review for production publish scope (`pages_manage_posts`)
- [x] Migration 026 run on staging: `cd api && alembic upgrade head`
- [x] BUG RESOLVED: "Invalid Scopes: pages_read_engagement" — root cause was permission not enabled in Meta Developer App use case (not deprecated). Fix: enable `pages_read_engagement` + `pages_read_user_content` in Manage Pages use case. Correct scope: `pages_show_list,pages_read_engagement,pages_manage_posts`. All 3 Graph API endpoints verified in Graph API Explorer: /me/accounts ✅, /{page_id}?fields=... ✅, POST /{page_id}/feed ✅
- [x] TEST: connect a brand's Facebook page end-to-end — OAuth → page selection → SocialConnection row stored
- [x] TEST: CMO chat → "show my facebook page" → `meta_page_inventory` artifact ✅ Klarohahq page returned
- [x] TEST: CMO chat → "say hi from mactan group" → pages/read + posts/read + posts/draft all dispatched correctly ✅
- [ ] TEST: approve draft → "publish this" → `fb_page_post_result` artifact, post live on page
- [x] BUG RESOLVED: `posts/draft` and `posts/publish` SKILL.md used invalid `requires_intent` values (`"sample"`, `"action"`) not in `IntentType` Literal — Pydantic validation silently dropped both skills from the manifest; neither appeared in `allowed_module_ids` or the CMO capability list. Fix: changed to valid values `[discussion, generation]` for draft, `[discussion, generation]` for publish. Also added `post in facebook` trigger to cover "in" vs "on" preposition variation.
- [x] BUG RESOLVED: `posts/read` and `posts/draft` rendered as ad creative (`FacebookFeedPreview`) because `channel.includes('facebook')` matched all Meta platform hints. Fix: added block-type-specific renderers for `fb_page_post_draft` (organic post preview, no "Creative Placeholder"), `meta_page_posts` (posts list or failure card), `meta_page_inventory` (pages list). Also fixed `self_check` in `posts/read` to return "fail" when execution failed ("failed to" in content).
- [x] BUG RESOLVED: `artifactTitle` didn't recognise Meta module IDs — showed "Facebook Posts Read Draft" instead of "Facebook Posts". Fix: added explicit cases for `meta.pages.read`, `meta.posts.draft`, `meta.posts.publish`, `meta.posts.read`.
- [x] BUG RESOLVED: Image generation returns HTTP 401 on staging — `IMAGE_GEN_API_KEY` and `IMAGE_GEN_WORKER_URL` plugin vars set in Admin → Plugins → media.image on staging. Image gen now working.
- [ ] ARCH GAP (documented, not building yet): Multi-plugin image→Facebook post handoff — CMO dispatches each `RUN:` independently with isolated briefs; no inter-module data handoff exists. image gen outputs `image_data_b64` in block; Facebook `posts/publish` posts to `/feed` (text+link only) — no base64 upload path. Full path requires two-step: (1) `POST /{page_id}/photos?published=false` with image binary → `media_fbid`; (2) `POST /{page_id}/feed` with `attached_media=[{media_fbid}]`. Design options: (A) `posts/draft` block carries `image_prompt`; `posts/publish` calls image gen + photo upload inline; (B) a future pipeline/handoff mechanism threads artifacts between modules. Option A is simpler for Phase 1. Option B is the right agentic architecture but requires pipeline primitives not yet built. Defer to Phase 6 pipeline work.
- [ ] ARCH GAP (documented, not building yet): CMO dispatches Meta capabilities without checking if brand has a Facebook connection. When brand has no Facebook connection, modules fail at execution time with "Facebook page token not connected" rather than being blocked at dispatch. Fix options: (A) surface connected channels per brand in CMO system prompt so LLM self-selects; (B) pre-dispatch credential gate in the orchestrator that returns a clear user-facing message before running the module. Option A is lower friction and follows the LLM-first architecture. Defer with option A as the planned approach.
- [x] BUG RESOLVED: `localStorage` quota crash — `image_data_b64` (multi-MB base64 PNG) stored in pending run blocks exhausted the 5 MB quota. Fix: `writePendingRuns()` strips `image_data_b64` and other large fields before writing; caps stored runs at 50; catches `QuotaExceededError` and falls back to trimming to 10 entries. `readPendingRuns()` validates each entry has `module_id: string` and `run_id: string` to prevent stale corrupt entries from crashing `undefined.toLowerCase()` calls.
- [x] BUG RESOLVED: `undefined.toLowerCase()` random crash — stale localStorage runs without `module_id` passed to `artifactTitle` and friends. Fix: `if (!run?.module_id) return 'Artifact'` guard added in `ApprovalBundle.tsx`, `artifacts.ts`, `WorkspacePanel.tsx`, `Stream.tsx`, and `Layout.tsx`.
- [x] BUG RESOLVED: `capability_manifest.py` never included plugin SKILL.md files — `build_dispatchable_manifest()` called `list_skill_manifests()` before the registry scan ran, so `_extra_skill_roots` was empty and plugin capabilities were invisible to the CMO. Fix: `build_dispatchable_manifest()` now calls `_ensure_plugins_registered()` (wraps `registry._ensure()`) before reading skills, guaranteeing registry scan runs first. All 4 Meta skills + all other plugin skills now appear in the CMO system prompt.
- [x] BUG RESOLVED: Inline RUN params not extracted — CMO outputs `task_name:` / `message:` on lines after `RUN: <module_id>` but the dispatch loop only parsed the `RUN:` directive and ignored those lines. Fix: added `_RUN_PARAMS_RE` regex + `_parse_run_inline_params()` in `chat.py`; dispatch loop now merges per-module params into each brief. Also fixed regex with negative lookahead `(?![ \t]*RUN\s*:)` to prevent the next `RUN:` directive from being absorbed as a param of the previous module.

## Phase 6 — Full-Stack Marketing Automation
> Goal: replace every role in a marketing department. CMO orchestrates. Plugins are the specialists. Owner approves decisions. BOS remembers what worked.

### Two-Cycle System Architecture

BOS operates in two cycles that form a flywheel. Every client starts at Cycle 1. Once metrics exist, Cycle 2 begins and feeds back into Cycle 1 indefinitely.

```
CYCLE 1 — Setup to Market
  Brand Brief
    → GTM Plan generated (marketing angles, channels, omni-channel stack)
    → BL selects which channels to invest in
    → Per-plugin onboarding checklists generated and dumped to PM
    → Agentic loop handles automatable setup; manual tasks go to human via ClickUp
    → Once onboarding complete: each channel generates first artifacts
    → Artifacts surface on Stream for BL review and approval
    → Approved artifacts deployed; plugins update their own PM tasks

CYCLE 2 — Intelligence to Optimization
  Channel metrics flood in on cadence (EOD / EOW / EOM)
    → Each channel plugin runs its own analyst capability
    → Channel reports submitted to CMO
    → CMO synthesizes marketing snapshot and reports to BL
    → BL approves optimization plan
    → New campaign brief issued across all active channels
    → Cycle 1 execution restarts for new campaign
```

**Business Leader's day:**
- Morning: checks Stream on phone — pending reviews, needs attention, newly published
- Issues campaign brief or approves pending artifacts from Stream
- Midday: published asset status visible in Stream
- On cadence: CMO surfaces marketing snapshot → BL approves optimization plan
- CMO dispatches approved plan to all specialists → drafts surface → BL approves → deployed

**Key architectural pieces needed (sections 6.10–6.15 below):**
- GTM Plan capability — strategic output from brand brief, BL selects channels
- Plugin onboarding manifest — `channel.json` declares onboarding checklist per plugin
- Onboarding orchestrator — aggregates manifests, creates PM tasks, auto-completes what it can
- Campaign brief cascade — approved plan dispatches to all active channels simultaneously
- Per-channel analyst capabilities — each plugin's `*.analyze` module, runs on cadence
- CMO snapshot aggregator — synthesizes channel reports into one executive summary
- Stream panel upgrade — BL decision surface: priority-sorted, approve-in-place, digest mode
- Digest notification — loop sends summary to BL after each run (email or Slack)

---

### 6.0 — CMO Agent Harness (pi model)
> Direct execution surface for agents — read, execute, write. No LLM routing. Agents call capabilities directly; result always lands at pending_review for human approval.
- [x] `api/routers/agent.py` — 5-endpoint harness: GET /agent/state, GET /agent/context/{brand_id}, GET /agent/capabilities, POST /agent/execute, PATCH /agent/review/{run_id}
- [x] POST /agent/execute calls existing `_execute_module()` in runs.py — same code path as CMO chat, no duplicate execution logic
- [x] PATCH /agent/review triggers PM (ClickUp) sync on approve/reject
- [ ] Frontend: Agent Activity panel in Admin — live view of agent-initiated runs and their review queue
- [x] Agent loop script: `api/agents/cmo_loop.py` — monitor → prioritize → delegate → surface (runs on cron or webhook trigger)

### 6.1 — Visual Production (image gen)
> Force multiplier. Feeds every channel. Build before social.
- [x] `api/plugins/media-image/` — provider-agnostic image generation plugin (`media.image.generate`); currently backed by Cloudflare Workers AI (Stable Diffusion XL). Plugin ID `media.image`, module ID stable regardless of backend provider.
- [x] Credentials stored via `POST /plugins/media.image/credentials` (URL + API key encrypted in DB); swapping providers = updating credentials only, zero code changes
- [x] Auto-builds image prompt from brand brief (brand name, product, audience, tone) when no explicit `image_prompt` is provided
- [x] Executor pre-generation hook in `runs.py` — any module that sets `image_prompt` in its brief gets `_image_data_b64` / `_image_mime` injected before dispatch; no cross-plugin imports needed
- [x] Frontend renders `image_asset` block inline in artifact card (base64 PNG with prompt caption)
- [x] CMO dispatches via `RUN: media.image.generate`; skill manifest includes Google Ads image ads, display ads, social creatives, hero images as triggers
- [x] Image Generation card on Specialists page with Configure button
- [ ] Reads Campaign Brand Kit for style constraints (colors, tone, visual identity) before generating — brief-driven today, brand kit injection planned
- [ ] Quality gate: brand compliance check (color palette, no banned elements) before surfacing
- [ ] Paired output: copy + image as a single `creative_bundle` artifact for ads and social

### 6.2 — Email Campaign Infrastructure
> Moves email from placeholder to full marketing.execute + marketing.optimize channel.
- [ ] Deploy Listmonk on VDS (Docker, shares PostgreSQL instance)
- [ ] Configure Amazon SES or Mailgun as SMTP relay — never send directly from Contabo IP
- [ ] `api/plugins/listmonk/` — implements `marketing.execute` (push approved campaign) and `marketing.optimize` (pull open/click/bounce data back as workspace document)
- [ ] Per-brand contact lists + unsubscribe compliance (CAN-SPAM/GDPR)
- [ ] HTML email template per brand generated from Campaign Brand Kit + image gen plugin output
- [ ] Performance data feeds back into BOS optimization memory automatically

### 6.3 — Social Publishing Channels
> Requires image gen complete first — text-only social posts are weak.
- [ ] `api/plugins/meta/` — Facebook + Instagram organic publishing and paid ads (`marketing.execute` + `marketing.optimize`)
- [ ] `api/plugins/linkedin/` — organic posts + sponsored content
- [ ] `api/plugins/tiktok/` — organic posts (video-dependent; stub until video gen is ready)
- [ ] Agency app model: one platform developer app, brands authorize via OAuth, system holds long-lived tokens per brand — same pattern as existing Facebook/Gmail auth
- [ ] Scheduling: CMO sets publish time, plugin queues and executes
- [ ] Engagement monitoring: comments, replies, DMs surfaced as inbox intelligence artifacts

### 6.4 — Paid Channels Beyond Google
- [ ] `api/plugins/meta-ads/` — Meta paid campaigns, creative, audience targeting (`marketing.execute` + `marketing.optimize`)
- [ ] `api/plugins/tiktok-ads/` — TikTok paid campaigns
- [ ] `api/plugins/linkedin-ads/` — LinkedIn sponsored content
- [ ] All follow Google Ads plugin contract: read/draft first, approval-gated mutations, audit trail

### 6.5 — Analytics Unification
> Closes the analyst role. Unified signal across all channels.
- [ ] `api/plugins/ga4/` — session data, conversion events, traffic sources (`marketing.optimize`)
- [ ] Cross-channel attribution: GA4 + Google Ads + Search Console + email + social in one optimization view
- [ ] Unified performance workspace document generated on cadence (weekly/monthly)
- [ ] CMO can ask "what's working?" and get a cross-channel answer from BOS memory, not a dashboard

### 6.6 — Landing Page Generation + Deployment
> Closes the web dev role for campaign-specific pages.
- [ ] BOS generates HTML/copy landing page from campaign brief and Campaign Brand Kit
- [ ] Deploys to brand subdomain (Cloudflare Pages or nginx-served static)
- [ ] A/B variant generation: two versions approved by CMO, traffic split tracked via GA4
- [ ] Approval gate before any page goes live

### 6.7 — Audio / Voice
- [ ] `api/plugins/audio/` — TTS for ad voiceovers, podcast intros, short-form audio (`marketing.execute`)
- [ ] Backends: ElevenLabs, OpenAI TTS (provider-routed)
- [ ] Output: reviewable `audio_artifact` — approve before use in ads or social

### 6.8 — Video Generation
> Model-dependent. Hold until output quality is reliable for brand use.
- [ ] `api/plugins/video-gen/` — short-form video for social and ads (`marketing.execute`)
- [ ] Backends: Sora, Runway Gen-3, Kling (provider-routed when ready)
- [ ] Prerequisite: audio plugin complete (voiceover pairs with video)

### 6.9 — Optimization Memory Loop (cross-cutting)
> The thing that makes BOS better than hiring back all these roles over time.
- [ ] Approved learnings from every channel (email open rates, ad CTR, social engagement, GA4 conversions) flow automatically into CMO planning brief for next campaign
- [ ] Dismissed variants and rejected artifacts stored as negative memory — CMO doesn't repeat mistakes
- [ ] `Outcomes` section in Admin surfaces approved learnings, measured results, and trend signals per brand
- [ ] Next campaign `marketing.plan` call loads prior outcomes as a memory slot automatically

---

### 6.10 — GTM Plan Capability (Cycle 1 entry point)
> First thing generated after brand brief is submitted. BL uses this to decide which channels to activate. All downstream work — onboarding, artifacts, deployment — flows from the channels the BL selects here.
- [ ] `api/capabilities/marketing/planning/gtm_plan/` — `marketing.planning.gtm_plan` capability
- [ ] Reads brand brief (voice, tone, values, products, audiences, domain) and generates full omni-channel GTM plan: recommended channels, marketing angles per channel, messaging priorities, suggested budget allocation ranges, rationale per channel
- [ ] Output is a structured `gtm_plan` artifact: channel list with BL toggle (invest / skip / defer) + narrative summary
- [ ] BL approves plan from Stream; selected channels become the active channel set for this brand
- [ ] Approved channel selection stored in `brand_json["active_channels"]` — all downstream orchestration reads from this
- [ ] CMO can regenerate plan when brand brief is updated (new product, new market, new budget)
- [ ] Rejected channel stays in plan as `deferred` — BL can activate later without regenerating

### 6.11 — Plugin Onboarding Manifest + Orchestrator
> Each plugin declares what it needs to go live. The system aggregates all requirements, automates what it can, and sends the rest to the PM for human coordination. Onboarding is complete when all tasks are marked done.
- [ ] Add `onboarding` block to `channel.json` manifest schema — each plugin declares its checklist: `{task, description, auto: true|false, requires_credential: bool}`
- [ ] Example: Google Ads plugin declares `[{task: "Link MCC account", auto: false}, {task: "Create conversion action", auto: true, module: "google_ads.setup.conversion"}]`
- [ ] `api/capabilities/onboarding/channel_onboarding/` — `onboarding.channel_onboarding` capability: reads all active channel manifests for a brand, generates unified onboarding task list
- [ ] Automated tasks dispatched immediately via agent harness; manual tasks created in ClickUp under a dedicated onboarding list per brand
- [ ] Onboarding status tracked per channel: `not_started / in_progress / complete / blocked`
- [ ] Admin UI: onboarding progress view per brand — channel rows with completion status
- [ ] Agent loop checks onboarding status on each run; once all channels complete, triggers first-artifact generation automatically

### 6.12 — Campaign Brief Cascade
> When BL approves a campaign plan, the loop dispatches briefs to all active channels simultaneously. No manual trigger per channel. The CMO calls its army of specialists in one action.
- [ ] `api/capabilities/marketing/planning/campaign_brief/` — `marketing.planning.campaign_brief` capability: generates a structured brief per channel from the campaign objective + GTM plan + brand context
- [ ] Brief cascade: when BL approves a campaign plan artifact, agent loop reads `brand_json["active_channels"]` and dispatches `campaign_brief.generate` for each active channel in parallel
- [ ] Each channel brief becomes a `pending_review` artifact in Stream — BL or brand manager reviews per-channel brief before execution begins
- [ ] Approved channel brief triggers the channel's draft capability automatically (e.g., approved Google Ads brief → dispatches `google_ads.draft`)
- [ ] ClickUp task created per channel at cascade time: tracks brief → draft → approved → deployed lifecycle
- [ ] Cascade summary artifact shows BL which channels were briefed, which are awaiting brief approval, which are blocked

### 6.12b — Channel-Sovereign Campaign Execution
> Plan approved → all enabled channel plugins fire simultaneously with the campaign brief. Strategy is channel-agnostic. Each plugin owns its own tactical execution and image generation.

**Architecture rule:** `marketing.plan` produces positioning + message frame + market segment + offer. No channel logic lives here. On approval, dispatch fires to all enabled channels in parallel via `RUN:` directives. Each channel plugin reads its own `channel.json` to know which sub-capabilities are enabled, handles its own image gen call with channel-correct dimensions, and returns channel-native artifacts for Stream review.

**Image gen contract:** channel modules include `image_format: {width, height, channel}` in brief → `media.image.generate` (already installed) respects dimensions. No sequential loop needed — copy and image both derive from the shared campaign brief independently.

- [ ] Campaign execution SKILL.md (`marketing.execute.campaign`) — activated when approved plan brief is present; dispatches `RUN:` to all enabled channel plugins; zero channel-specific logic in the SKILL itself
- [ ] Plan approval trigger — when a plan artifact is approved, fire the campaign execution dispatch; currently approval updates status only; needs `on_approve` hook that fires the execution cascade
- [ ] Google Ads plugin: campaign execution mode — on campaign brief, dispatch search ads (always), display banners (if `display` in enabled sub-caps, calls image gen at 300×250 + 728×90), video brief (if `video` enabled)
- [ ] Meta plugin: campaign execution mode — on campaign brief, dispatch post copy + square image (1080×1080) if post enabled; carousel copy + per-item images (1080×1080 × N) if carousel enabled; each calls `media.image.generate` with format spec
- [ ] Email plugin: campaign execution mode — email copy + header image (600×200); calls image gen for header
- [ ] Image gen format field — add `image_format: {width: int, height: int, channel: str}` to `media.image.generate` brief contract; plugin uses dimensions when generating
- [ ] Creative bundle artifact — paired copy + image as single `creative_bundle` block per channel; both surface in one Stream card for approval instead of separate copy and image cards
- [ ] ARCH GAP (Option A — planned): `posts/draft` block carries `image_prompt`; `posts/publish` calls image gen + `POST /{page_id}/photos` (unpublished) → `media_fbid` → `POST /{page_id}/feed` with `attached_media`; defers Option B pipeline primitives to Phase 7
- [ ] ARCH GAP credential pre-check (Option A — planned): surface `brand_json["active_channels"]` with connection status in CMO system prompt; LLM self-selects only connected channels before dispatching

### 6.13 — Per-Channel Intelligence (Analyst Capabilities)
> Each channel plugin owns its own analyst. Reports are submitted to the CMO, not to the BL directly. BL sees the synthesized snapshot, not raw channel data.
- [ ] Analyst module pattern: each plugin adds a `*.analyze` capability alongside its `*.execute` and `*.optimize` modules
- [ ] `google_ads.analyze` — pulls campaign metrics (impressions, clicks, CTR, CPA, ROAS), produces structured `performance_report` artifact
- [ ] `meta.analyze` — Facebook/Instagram reach, engagement, cost-per-result
- [ ] `email.analyze` (Listmonk) — open rate, click rate, unsubscribe rate, revenue per send
- [ ] `ga4.analyze` — sessions, conversions, channel attribution, goal completions
- [ ] Each analyst capability runs on cadence: EOD for active campaigns, EOW for always-on channels, EOM for full-funnel review
- [ ] Cadence stored per brand per channel in `brand_json["channel_cadence"]`
- [ ] Agent loop checks cadence on each run and dispatches the right analyst capabilities

### 6.14 — CMO Snapshot + Optimization Plan
> The CMO's report to the BL. Not raw data — synthesized signal. One artifact per cadence period that tells the BL what happened, what's working, and what to do next.
- [ ] `api/capabilities/marketing/planning/cmo_snapshot/` — `marketing.planning.cmo_snapshot` capability
- [ ] Reads all channel `performance_report` artifacts for a brand within the cadence window
- [ ] Produces: executive summary (3-5 bullets), channel performance comparison, top-performing creative, underperforming channels flagged, recommended optimization actions with rationale
- [ ] BL reviews snapshot artifact from Stream — not individual channel reports
- [ ] BL can approve, reject, or annotate optimization recommendations inline
- [ ] Approved optimization plan triggers brief cascade for affected channels (Cycle 2 → Cycle 1)
- [ ] CMO snapshot stored as workspace document — feeds Optimization Memory Loop (6.9)

### 6.15 — Stream Panel: BL Decision Surface
> Stream is the only interface the BL needs. Everything else is for the CMO and team. Stream must work on mobile and surface the right things at the right time.
- [ ] Priority sort: needs-attention items first (overdue, flagged, blocked), then pending review, then published
- [ ] Digest mode: artifacts grouped by brand and campaign — not one card per artifact
- [ ] Approve / reject / flag in-place from Stream card — no navigation to workspace required
- [ ] Campaign thread view: all artifacts for a campaign in one expandable thread
- [ ] Status indicators: onboarding progress, active campaigns, pending approvals count per brand
- [ ] Mobile-first layout: thumb-reachable approve/reject actions, single-column card stack
- [ ] Digest notification: loop sends summary to BL after each run — email or Slack with direct approve links (see 6.16)

### 6.16 — Digest Notification
> BL should not have to open BOS to know something needs their attention. The loop pushes to them; they pull only when they want detail.
- [ ] `api/plugins/notify/` — lightweight notification plugin: email (SMTP) and/or Slack (webhook)
- [ ] `notify.digest` capability: formats pending review items as a digest and sends to configured recipient
- [ ] cmo_loop.py calls `notify.digest` at end of each run if any items are pending review
- [ ] Email digest: brand-grouped list of pending artifacts with direct approve/reject links (token-authenticated, no login required for single-action approvals)
- [ ] Slack digest: one message per brand with artifact count and link to Stream
- [ ] Notification preferences stored per workspace: channel (email/Slack), cadence (immediate/batched), recipient list

## Phase 5 — Hardening + Second Vertical
### Hardening
- [ ] Retry with structured feedback (BITE failure-feedback loop)
- [ ] Rate limiting (per API key)
- [ ] Cost quotas (configurable per workspace)
- [ ] Provider circuit breaker
- [ ] Structured logging
### New Surfaces (candidates)
- [ ] FullScreenSurface: give PerformanceReport its own dedicated screen with full chart rendering
- [ ] Slack message renderer (new surface, zero component changes)
- [ ] PDF export surface (new surface, zero component changes)
- [ ] TikTok-style MobileCardSurface: full-screen per-block with swipe gesture (new surface variant)
### Second Vertical
- [ ] Vertical chosen (finance or HR)
- [ ] 2-3 modules implemented
- [ ] Proves: adding a vertical = adding files, no core changes
### Deployment Docs
- [ ] One-command VPS setup (Ubuntu 22.04 + Docker)
- [ ] .env.example fully documented
- [ ] SSL via nginx + certbot
- [ ] PostgreSQL backup strategy
## Parking Lot
- Multi-tenancy (SaaS mode)
- Workflow chaining between modules
- Agentic orchestration inside BOS
- A/B variant generation per module
- Fine-tuning infrastructure
- Native mobile app
- Enterprise billing and reporting
- Automated provider model catalog refresh
- **klaroha.com public marketing site (Astro):** Static site at klaroha.com built with Astro. BOS generates copy/landing pages as approved artifacts; a `api/plugins/klaroha-site/` plugin commits markdown content to the Astro repo and triggers a GitHub Actions rebuild. Design and aesthetics live in the Astro repo; BOS only touches content. Prerequisite: hq.klaroha.com move complete, multi-dev CI/branch setup done.
- **CMS publish plugins (WordPress, Webflow, Shopify, etc.):** Each client CMS is a plugin publish target — same model as Gmail/Google Ads. WordPress uses Application Passwords (built-in since WP 5.6); credentials stored per brand in `social_connections` table. BOS generates and approves content artifacts; plugin pushes via CMS REST API. One plugin per CMS type, serves all clients on that platform. Prerequisite: plugin dev workflow and staging environment live first.
- Email campaign infrastructure: Listmonk (self-hosted, Go + PostgreSQL) for list management, campaign orchestration, unsubscribe compliance, and open/click tracking; Listmonk (self-hosted, Go + PostgreSQL) for list management, campaign orchestration, unsubscribe compliance, and open/click tracking; Amazon SES or Mailgun as SMTP relay (Contabo IPs are untrusted by Gmail/Outlook — never send directly from VDS). BOS plugin: `api/plugins/listmonk/` implementing `marketing.execute` (push approved campaign) and `marketing.optimize` (pull performance data back as workspace document). Closes the "BOS remembers what worked" loop for email. Prerequisite: Email Specialist MVP (v3.12 decision) must be complete first.
- **Meta Ads CLI (Phase 4 dev tool):** Meta released a Python CLI (`pip install meta-ads-cli`, Python 3.12+) that wraps the Marketing API — auth, pagination, error handling — for campaigns, ad sets, creatives, performance metrics, catalogs, and pixels. JSON output, automation-ready. **Not for production plugin code** (subprocess in Docker + version drift + Python 3.12+ vs our 3.11+ = bad fit). Use it during Phase 4 development for manual API testing and debugging before writing `ads/campaigns/read` + `ads/performance/read` module.py calls. Install: `pip install meta-ads-cli`. Docs: developers.facebook.com/blog/post/2026/04/29/introducing-ads-cli
- **Cloudflare Tunnel for local Facebook OAuth:** Facebook enforces HTTPS-only redirect URIs — `http://localhost` is rejected. This means Facebook OAuth (connect, token refresh) can only happen on staging or production, making local dev a staging-dependent workflow for all Facebook-touching features. Fix: set up a named Cloudflare Tunnel (`dev.klaroha.com` → localhost:80), register `https://dev.klaroha.com/social/facebook/callback` as a third redirect URI in the Meta Developer App, and store it as `META_REDIRECT_URI` in local `.env`. Once done, Facebook can be connected locally and local dev becomes fully self-contained for Meta plugin work. Steps: (1) `cloudflared tunnel create bos-dev` in Cloudflare dashboard; (2) point `dev.klaroha.com` CNAME at the tunnel; (3) add redirect URI to Meta App; (4) add `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI=https://dev.klaroha.com/social/facebook/callback` to local `.env`; (5) connect Facebook at `http://localhost/admin/brands`.
## Decisions Log
| Date | Decision | Rationale |
|---|---|---|
| 2026-05-15 | Self-contained HTML is the portable artifact format for landing pages and campaigns | Works on every host (S3, Cloudflare Pages, Netlify, bare VPS) with no build step. Injects into WordPress via a blank/no-theme page template without touching page builders. Drops into `public/` on an Astro site as a static file. BOS owns the edit workflow; clients do not edit the HTML directly — they revise in Klaroha, approve, and republish. |
| 2026-05-15 | BOS generates content artifacts; CMS publish plugins deploy them — separation is non-negotiable | BOS must never become a CMS. The artifact record (content, approval state, publish audit) lives in BOS. The platform-specific deploy step lives in a plugin. Same plugin contract as channel plugins: `channel.json` + `ChannelModule` + `SKILL.md`. The approval gate sits between generation and publish; no artifact reaches a live site without an approved status. |
| 2026-05-15 | WordPress is the first CMS publish plugin target | Most clients are on WordPress with custom themes and page builders (Elementor, Divi, Beaver). Safe path: create/update a page using a blank/no-theme template via WP REST API (`POST /wp-json/wp/v2/pages`), inject the self-contained HTML, tag managed pages with `_klaroha_managed: true` meta. Application Passwords (native WP 5.6+) make auth straightforward; no OAuth dance. Plugin must never touch the theme, other pages, or plugins. |
| 2026-05-15 | Landing page plugin build order: HTML generation → WordPress → static host → Astro/GitHub | Stage 1 (now): `marketing.execute.landing_page` first-party capability — brand brief + copy intent → self-contained HTML artifact → Workspace for review. Stage 2: WordPress publish plugin. Stage 3: static host plugin (SFTP/S3). Stage 4: Astro/GitHub plugin for `klaroha.com` once it exits Parking Lot. All stages share the same approved artifact record. |
| 2026-05-15 | Klaroha public landing page deployed as `public` docker service on port 3000 (local only) | Self-contained HTML at `public/index.html`, served by `nginx:alpine` on port 3000. Not routed through Cloudflare or any public domain. This is the first artifact produced by the landing page generation flow — the template/sample before the capability module exists. |
| 2026-05-13 | Search Console is a custom native plugin-owned marketing optimization specialist | It follows the Google Ads pattern: sample first, plugin-only capability package, read-only intelligence artifacts first, no CMO router logic, and no BOS core Search Console behavior. It is custom-built for BOS using native Google Search Console APIs only — no Membrane, Rube, Composio, or arbitrary MCP sidecar. |
| 2026-05-13 | Native Marketing Planning Specialist owns campaign plan artifacts | Approved sample `sample/marketing_planning_specialist_v1.md` establishes the target: CMO chat stays short, `@klar plan` calls a first-party planning Transform, and Workspace owns the reviewable `plan_artifact` layout. |
| 2026-05-13 | CMO replies are mobile-first short-line messages by default | Approved sample `sample/mobile_cmo_reply_style_v1.md` establishes the target: 1–4 short lines, one idea per line, bullets for choices, one question max, and no dense paragraphs unless the user asks for detail. |
| 2026-05-13 | Google Ads direction is full-control via plugin-owned, approval-gated capabilities | Approved sample `sample/google_ads_full_control_v1.md` establishes the target: read diagnostics, draft recommendations, apply selected approved changes, require second confirmation for destructive actions, and audit every mutation. BOS core remains the harness; Google Ads behavior belongs in the plugin. |
| 2026-05-13 | Workspace Artifacts are the canonical artifact plane; CMO chat shows artifact references only | Keeps chat conversational and stable while plugins/capabilities produce native artifacts. Workspace owns native preview, approval, revision, and system details; Stream reads the same persisted artifacts for mobile. |
| 2026-05-14 | CMO hard rules belong in the base system prompt, not only in skill context | Skill context is injected after potentially thousands of tokens of brand/product/audience context; LLM weights brand context over skill guidance; invariants that must hold on every turn (no inline artifacts, dispatch-first, one question max) must appear in the base prompt before any brand data so they cannot be overridden by generative instincts. |
| 2026-05-14 | Web container runs a production nginx build, not Vite dev server | Vite dev server caused full page reloads on every navigation, wiping localStorage and clearing the API key session; production build (multi-stage Dockerfile: node build → nginx static serve) eliminates HMR and serves the SPA correctly with react-router fallback to index.html |
| 2026-05-15 | BOS Command Hub lives at hq.klaroha.com; klaroha.com is reserved for the public Astro marketing site | Keeps internal tooling off the marketing domain; allows klaroha.com to be a standalone static site later without disrupting the running BOS instance; subdomain separation also simplifies SSL and Cloudflare routing |
| 2026-05-15 | CMS platforms (WordPress, Webflow, Shopify) are plugin publish targets, not BOS core integrations | Same model as Gmail/Google Ads: credentials per brand in social_connections, content pushed via CMS REST API on artifact approval, one plugin per CMS type serves all clients on that platform; parked until multi-dev workflow and staging are live |
| 2026-05-15 | Per-capability dev notes (`*_notes.md`) are the regression prevention system | Co-located with the file they cover (e.g. api/routers/chat_notes.md, api/plugins/google-ads/plugin_notes.md); capture invariants, fixed bug patterns, do-nots, and a local backlog; master BACKLOG.md stays core BOS only; plugin regressions stay in their plugin's notes file |
| 2026-05-19 | Meta Ads CLI is a dev/debug tool for Phase 4, not a production plugin dependency | CLI wraps Marketing API (auth, pagination, error handling) with JSON output — useful for manually probing ad account data during Phase 4 development. Not wrapped in plugin code: subprocess in Docker + Python 3.12+ requirement + CLI version drift are all bad fits for server-side module.py. Phase 4 ads modules write direct urllib.request calls like all other plugins. |
| 2026-05-19 | Meta AI Business Assistant is a closed competitor, no BOS integration needed | Meta's own AI chat assistant (in Business Suite, Ad Center, Instagram Boost) handles ad performance Q&A, recommendations, and account issue resolution inside Meta's UI. No public API — can't integrate. BOS differentiation is cross-channel intelligence and brand workspace context that Meta's assistant can't access. No action required. |
| 2026-05-19 | CMO streaming uses SSE not WebSocket; nginx requires dedicated location block or X-Accel-Buffering response header | WebSocket requires connection upgrade and bi-directional protocol — overkill for a server-push-only stream. SSE is HTTP/1.1, works through nginx reverse proxy with `proxy_buffering off` on the location block (belt) and `X-Accel-Buffering: no` response header (suspenders). Both are required: nginx config alone doesn't survive container restarts without reload; response header alone doesn't override global buffering config on some nginx builds. |
| 2026-05-19 | `_run_modules_streaming()` is the single source of truth for module dispatch; both /chat and /chat/stream use it | Eliminated copy-paste divergence between the legacy `/chat` endpoint's dispatch loop and the new streaming endpoint. Any dispatch logic change goes in one place. `_run_modules_streaming()` yields typed dicts (`module_start`, `module_result`); callers consume the generator and decide what to do with results. |
| 2026-05-19 | Step log persists as completed (greyed ✓) after reply arrives — not removed | Removing the step log when the reply arrived made the experience look like the old mechanical single-response pattern. The step log is the agentic loop trace — it shows what ran and in what order. Keeping it (faded, complete) proves the pipeline executed. This is the agreed sample: [step_log(✓ all)] → [artifact_card] → [reply_text]. |
| 2026-05-14 | Staging lives at staging.klaroha.com on the same VDS as production | Separate Docker stack on different ports, separate database; plugin dev PRs target staging branch first, reviewed by main dev before merging to main/production; keeps costs low while maintaining isolation |
| 2026-05-14 | Plugin dev (Dev 2) has GitHub repo access only — no server SSH | Internal junior dev scoped to api/plugins/ via branch protection; pushes to plugin/* branches, PRs to staging; main dev reviews before any code reaches production; server deploy is webhook-triggered on merge, not manual |
| 2026-05-14 | Database is not in the git repo — each server deployment is a clean install | postgres_data Docker volume stays on the server across restarts; only docker compose down -v wipes it; this makes each new client/server deployment a clean isolated instance by default |
| 2026-05-17 | Import Brief scope is determined by UI step 0, not inferred from nav state alone | Before: arriving at `/admin/onboarding` without `brand_id` in nav state silently wrote to workspace-level. Now: no-brand-id path always shows a scope selector first — org vs brand (first import) or brand picker (brands exist). Update mode (brand_id in nav state) is locked and shows a scope badge. Prevents workspace-level data from being overwritten by a misrouted import. |
| 2026-05-17 | New brand imports create the Brand row before calling ingest | Frontend calls `POST /brands` first, then passes the new `brand_id` to `POST /onboarding/ingest`. Workspace-level slot (`brand_id=NULL`) is never written in new-brand or update-brand flows. Ensures every brand import is always scoped and traceable to a Brand row. |
| 2026-05-17 | Getting Started banner uses `campaign_brand_kit_approved`, not `all_ready` | `all_ready` from `GET /onboarding/status` requires every registered module to have a routable provider — it can be false even when all 5 UI checklist steps pass. Banner condition is `workspace_configured && campaign_brand_kit_approved`; if the kit is approved the core onboarding is done regardless of module routing state. |
| 2026-05-17 | Public booking widget is BOS-native, not a third-party embed | Google Calendar appointment scheduler requires a paid Workspace subscription and blocks iframes. Calendly is an external dependency. BOS serves its own booking page HTML (`/calendar/book/{slug}`), checks availability via Google Calendar FreeBusy API, and creates events via Calendar Events API. Universal embed is a 2-line snippet (`widget.js` + `data-klaroha-booking` attribute) that works on WordPress, Webflow, plain HTML with no build step. |
| 2026-05-17 | `widget.js` uses iframe, not inline injection, so embed works on CORS-restricted hosts | Inline DOM injection from an external script requires CORS-permissive hosts and can conflict with host CSP. An iframe to our own domain sidesteps both constraints. `Content-Security-Policy: frame-ancestors *` on the booking widget endpoint allows any external site to embed it. |
| 2026-05-17 | `brand_profile_configured` in onboarding status checks Brand row `brand_json`, not only `ws.brand_json` | In multi-brand workspaces the workspace-level `brand_json` may be empty while Brand rows are fully populated. Updated check: if `ws.brand_json` is falsy, query Brand rows and accept any row with `brand_json` set. Products and audiences are already workspace-wide counts so no change there. |
| 2026-05-12 | Capability questions may produce capability artifacts, but not execution artifacts | Fixes the email CMO failure without banning artifacts. `what can you do with email` should produce an Email Specialist capability card; it must not read Gmail, send Gmail, plan a campaign, or draft email unless the user asks for that work |
| 2026-05-12 | Email Specialist MVP is the next optimization focus | Email should implement `marketing.plan`, `marketing.execute`, and `marketing.optimize` as one owner-facing specialist: setup/readiness, plan artifacts, draft artifacts, approval-gated send/test, inbox reply intelligence, and optimization learnings. Gmail/module IDs remain internal tool details |
| 2026-05-12 | Lean hierarchy is `Org → Brand/Client → Market Unit → Campaign`; no Portfolio layer | Keeps architecture lean while supporting agencies, ecommerce multi-brand, multi-location services, and broker/agent networks. The Org acts as portfolio/control plane; Market Unit handles location/agent/territory/marketplace/SKU/service-line scope only when needed |
| 2026-05-12 | CMO-facing marketing surface collapses to `marketing.plan`, `marketing.execute`, and `marketing.optimize` | Prevents BOS from exposing a thousand-entry channel/task catalog; preserves the promise that a small business owner gets a CMO in their pocket, whose specialists use tools and produce artifacts while the owner approves decisions and BOS remembers what worked |
| 2026-05-12 | `BITE.md` elevated to BOS architecture constitution | Keeps governing policy in one mandatory-read file; codifies pi-inspired minimal core, package/plugin extensibility, SKILL.md ownership, live capability manifests, MCP-as-connector, lifecycle hooks, and command registration so new capabilities do not require chat/pipeline edits |
| 2026-05-01 | PostgreSQL from day one, no SQLite | Avoid migration cost; per-VPS deployment makes this feasible |
| 2026-05-01 | Frontend is first-class, not a dashboard HTML file | User needs to test the product, not just the API |
| 2026-05-01 | BYOK alongside platform routing | Lowers barrier; users with own keys shouldn't pay markup |
| 2026-05-01 | Chat agent is a client, not a BOS service | Keeps interface layer decoupled; BOS is agnostic to caller |
| 2026-05-01 | One workspace per deployment (no multi-tenancy yet) | Simplifies auth, data model, deployment |
| 2026-05-01 | FastAPI for BOS core | Async, typed, OpenAPI generation |
| 2026-05-01 | Alembic for migrations, manual version files | Portable and explicit; autogenerate requires running DB |
| 2026-05-01 | Seed capabilities + model_options in migration 004 | Capabilities are config, not user data |
| 2026-05-01 | Module registry via directory scan (importlib) | File = module; no registry file to edit; vertical isolation is directory-level |
| 2026-05-01 | Brief resolution: workspace fills gaps, run payload overrides | "Diff not repeat yourself" thesis |
| 2026-05-01 | Mock executor generates realistic content, correct cost math | Phase 1 gate passes without a live API key |
| 2026-05-02 | OpenAICompatAdapter base class; Gemini + NVIDIA are thin subclasses | All three speak same OpenAI chat completions protocol |
| 2026-05-02 | No-key fallback to mock rather than error | Dev experience stays clean |
| 2026-05-02 | Candidate waterfall: try in score order, store failed attempts | Handles provider rate limits without surfacing errors |
| 2026-05-02 | React + Vite for frontend | Hot reload via Docker volume mount; nginx proxies |
| 2026-05-02 | GET /runs returns RunListResponse envelope (runs + total + limit + offset) | Pagination controls need total count |
| 2026-05-02 | Auth connect is synchronous: setApiKey() then navigate() | Async + navigate() caused state update on unmounted component in StrictMode |
| 2026-05-02 | 401/403 redirects to /auth?error=1 | URL param carries error feedback across redirect without sessionStorage |
| 2026-05-02 | extractMessage() in client.ts unwraps FastAPI detail nesting | FastAPI wraps HTTPException as { detail: { error: { message } } } |
| 2026-05-02 | BITE layers explicitly separated | BOS thinks, modules execute, bridge clients translate |
| 2026-05-02 | Module tests mock at provider adapter boundary only | Module runs full logic; only provider HTTP call faked |
| 2026-05-02 | Bridge clients live in clients/ outside BOS core | Adding a bridge = new directory, zero BOS changes |
| 2026-05-02 | Evaluate layer embedded in modules for now; dedicated api/evaluate/ deferred | Deferred until module count justifies shared validators |
| 2026-05-02 | Baileys (WhatsApp Web WebSocket) is valid bridge client option | No browser required; deferred until claude/ client validated |
| 2026-05-03 | UI rebuilt as 3-tab mobile-first shell (Stream / CMO / Workspace) | Aligns with wireframe v0.4 |
| 2026-05-04 | UI wireframe files renamed with DON'T_USE prefix | Prefix does not mean "don't use" — these ARE the intended wireframes |
| 2026-05-04 | UI objective: replicate wireframes as single responsive React app; strip dark palette | One responsive web app; web wireframe → desktop; mobile wireframe → mobile |
| 2026-05-03 | CMO tab implements intent-parse dispatch: user message → module_id → POST /runs | No dedicated /chat endpoint yet; full LLM routing deferred to bridge client |
| 2026-05-06 | CMO is center stage on web (full-width chat, not a rail or tab) | Business owner's primary action is directing and reviewing, not navigating; organizational metaphor holds |
| 2026-05-06 | Left sidebar = conversation history (Claude.ai model) + pending decisions pill | Familiar pattern; pending pill gives always-visible count of unresolved decision_needed blocks |
| 2026-05-06 | Stream surfaces through CMO messages on web; not a separate tab | Eliminates context switch between reading a performance block and acting on it via CMO |
| 2026-05-06 | Workspace = sliding right panel (420px), not a full page | Keeps CMO in view; Workspace is reference material, not a destination |
| 2026-05-06 | Settings = modal overlay (not a page) with three tabs: BYOK / Usage / Run History | Administration is infrequent; modal keeps it out of the primary flow |
| 2026-05-06 | Collateral bundles render inline in CMO conversation as platform-accurate cards | Business owner needs to see exactly what goes out to the world; approval happens in the same moment as review |
| 2026-05-06 | Approvals are per-channel bundles (copy + creative as one unit) | Copy and creative are one decision; you never approve copy without seeing its creative |
| 2026-05-06 | Frontend components are surface-agnostic: data in, render out, no container knowledge | Component that knows its container cannot be reused across surfaces without rewriting |
| 2026-05-06 | SurfaceContext system: panel / full-screen / chat-inline / mobile-card | New surface = new wrapper, zero component changes; new component = one file, zero surface changes |
| 2026-05-06 | BriefingBlock.layout_hint drives component selection; SurfaceContext drives layout constraints | Clean separation: what renders vs. how it lays out |
| 2026-05-06 | Headless rendering contract: same BriefingBlock renderable by CLI, chat, web, mobile | No client-specific logic in components; renderer decides surface; component adapts |
| 2026-05-06 | New surfaces (Slack, PDF, TikTok-style mobile) deferred to Phase 5 | Architecture supports them from day one; implementation deferred until Phase 3 surface system is stable |
| 2026-05-06 | UIContext (React context) holds workspace panel + settings modal state at Layout level | Single source of truth; any component can trigger panels without prop drilling |
| 2026-05-06 | bos-shell CSS scope: new CMO shell uses monospace font scoped under .bos-shell class | Admin section and auth remain on system-ui; no global font change |
| 2026-05-06 | Old page routes (/ops, /intelligence, /history, /settings) preserved but unlinked | Accessible via direct URL; not removed until Phase 4 cleanup confirms they're fully superseded |
| 2026-05-06 | POST /chat placed in api/routers/ (BOS core), not clients/ | Requires direct DB access for workspace context, BYOK decryption, and run persistence; revisit at Phase 4 when clients/claude/ is built — that client will call POST /chat |
| 2026-05-06 | Chat provider order: BYOK (gemini → nvidia) then platform keys then mock | Matches module execution priority; ensures workspace with own keys never silently falls back to a billable platform call |
| 2026-05-06 | complete_messages() added to OpenAICompatAdapter only; complete() delegates to it | All subclasses inherit without protocol changes; supports multi-turn history for chat without touching module execution path |
| 2026-05-06 | ChatResponse returns runs[] (list) + run (first result, backward compat) | Single POST /chat resolves context once and dispatches all triggered modules; partial failure does not abort remaining modules |
| 2026-05-06 | System prompt rule: RUN: scoped to current user message only, not conversation history | LLM was re-triggering channels mentioned in prior turns; explicit rule prevents re-dispatch of already-run modules |
| 2026-05-06 | isMounted pattern removed from CmoChat send() | React 18 handles stale updates on unmounted components gracefully; the guard was silently discarding responses in Strict Mode's double-mount cycle, leaving typing indicator stuck |
| 2026-05-06 | GET /onboarding/status checks workspace + providers + per-module capability routing | Gives a single deployability signal; used during client setup or project handoff to verify all keys are wired before first run |
| 2026-05-06 | onboarding.brand_setup is a module triggered via POST /runs, not a dedicated route | Needs same capability routing, BYOK selection, billing, and self_check as any other module; writing output back to workspace is caller's responsibility (BITE: transform and persist are separate) |
| 2026-05-06 | onboarding vertical is a first-class vertical alongside marketing | Proves vertical = directory; no core changes needed to add a new one |
| 2026-05-06 | Provider auth mirrors pi harness: providers may authenticate via login/OAuth or direct API key | Separates provider credential acquisition from BOS/API auth; enables pi-style interactive connect flow with encrypted token storage and refresh |
| 2026-05-06 | OpenAI Chat is the single enabled login-auth provider in BOS | Keeps provider-login scope narrow while proving the auth flow end-to-end for a real product-relevant provider |
| 2026-05-06 | Admin UX should be setup-first, not ops-dashboard-first | New deployments need a guided path to connect OpenAI, import brand context, review extraction, and verify readiness before billing/run metrics matter |
| 2026-05-06 | `/admin` defaults to Getting Started; Operations Dashboard is a later step | Fresh deployments should see setup status and next actions before cost/run metrics |
| 2026-05-07 | Module fan-out: POST /campaigns/{id}/run dispatches all marketing modules | Single brief can trigger facebook + twitter + google + email modules simultaneously |
| 2026-05-07 | Approval tracking: Run model extended with approval_status, feedback, parent_run_id | Enables full round-trip: run → review → approve/reject → revise |
| 2026-05-07 | Approval endpoints: PATCH /runs/{id}/approve, /reject, POST /revise | Backend support for approval workflow complete; frontend integration pending |
| 2026-05-07 | marketing.email.cold_outreach module added | Completes the planned marketing modules from system shape sample |
| 2026-05-07 | Templates use richer workspace context (brand values, demographics, pain_points) | Better personalization; templates now use all available workspace data |
| 2026-05-07 | Export endpoint: GET /runs/{id}/export returns copy-paste ready format | Enables users to easily copy content to each platform |
| 2026-05-07 | Campaign summary: GET /campaigns/{id}/summary shows module pass/fail + costs | Gives overview of campaign performance and spending |
| 2026-05-07 | onboarding.brand_guidelines module added under onboarding vertical | Brand/design guideline generation is part of project onboarding, uses existing onboarding.brand_profiling capability |
| 2026-05-07 | Campaign Brand Kit is required onboarding, stored as tagged workspace document | Brand/design rules are long-lived and expandable; avoid brittle columns like primary_color/headline_font/platform_rule |
| 2026-05-07 | Frontend GET requests use short in-flight de-dupe/cache | React StrictMode and repeated admin panels were issuing duplicate GETs; short cache improves perceived speed without hiding mutations |
| 2026-05-07 | Copywriting skills are internal BOS modules invoked by content modules via declared skill stacks | Copy styles need to grow and combine without copying long prompt rules into every ad/email module |
| 2026-05-07 | Campaign Brand Kit contents are surfaced as a latest document endpoint and Admin Workspace tab | The kit is a long-lived brand artifact; users need a canonical read/edit/copy location after onboarding, not only a short onboarding preview |
| 2026-05-07 | Draft Campaign Brand Kits surface as pending decisions in the primary Workspace panel | Approval must happen where the operator reviews work, not only inside admin onboarding |
| 2026-05-08 | CMO chat is discussion-first and intent-gated for execution | A user asking what the project is about should get business context, not silent module fan-out; module runs require explicit generation/revision intent. |
| 2026-05-08 | CMO system prompt includes workspace brand profile, products, audiences, and Campaign Brand Kit excerpt | The BOS thesis requires the CMO to use already-ingested brand brief context and not ask the user to repeat it. |
| 2026-05-08 | Generated module outputs are persistent pending decision tasks | Approval work must survive navigation/reload and link to the exact run requiring review. |
| 2026-05-08 | Modify is LLM-backed per-run revision, not a generic local UI action | Revision feedback must return through the CMO LLM with the prior draft, channel, and thread context before creating a linked child run. |
| 2026-05-08 | Workspace approval panel replaces the current task on revision/approval instead of nesting threads | The right panel is a task workspace; chat can preserve conversational history, but Workspace must stay uncluttered. |
| 2026-05-08 | BOS adopts `SKILL.md` principles as operating contracts around modules | Skills declare when to activate, what memory/resources to hydrate, workflow rules, and quality gates; modules remain executable transforms. |
| 2026-05-08 | Initial skills are file-backed under `api/skills/` before any DB-backed skill registry | Local Markdown keeps implementation simple and auditable while preserving a future migration path to database-backed skills/resources. |
| 2026-05-08 | CMO memory is skill-declared, not transcript-first | Conversation history is short-term context only; durable brand/project knowledge comes from workspace resources hydrated through activated skill memory slots. |
| 2026-05-08 | Onboarding skills are not normal chat-dispatchable skills | Brand setup and Campaign Brand Kit generation are explicit onboarding/workspace flows; normal CMO chat may reference their outputs but should not accidentally run them. |
| 2026-05-08 | No hardwired CMO responses except provider failure/error handling | Routing, validation, directive stripping, and permission checks may be deterministic; ordinary CMO replies must be LLM-generated from activated skills and hydrated resources. |
| 2026-05-08 | Skills should be atomic need-to-know folders with explicit inheritance | Prevents broad channel/vertical context from leaking into narrow tasks; resources load only for the smallest activated operational node. |
| 2026-05-08 | SOP ingestion is a governed change-proposal pipeline | Uploaded SOPs must be extracted, matched, diffed, approved, versioned, and source-linked across skills/resources/modules/memory/config instead of blindly overwriting skills. |
| 2026-05-08 | BOS models Agent Skills progressive disclosure but keeps harness-owned governance | Skills are discovered by `SKILL.md`, cataloged by metadata, activated only when eligible, resources are listed not eagerly loaded, and BOS controls activation/module permissions rather than relying on raw model file reads. |
| 2026-05-08 | Canonical BOS skills use descriptions as activation policy and output formats as evaluation contracts | Samples show mature skills encode routing phrases, exclusions, related-skill handoffs, intake questions, caveats, lazy references, and expected output shape rather than only prompt instructions. |
| 2026-05-08 | Email sequence gets a module first; SEO audit and analytics tracking remain skill-only for now | Email sequence is an executable content artifact like existing marketing copy modules; SEO/analytics need external data/tool contracts before module execution should be trusted. |
| 2026-05-08 | Modules may be nested under business operating domains | Service-provider deployments need expandable internal capabilities; discovery recurses under each vertical while module IDs stay globally stable, e.g. `internal.client_onboarding.google_business_profile`. |
| 2026-05-08 | BOS organizes capabilities by operating function, not artifact format | A client onboarding email belongs under internal/client_onboarding, not marketing/email, because its purpose is service delivery after a client is won. |
| 2026-05-08 | Google Business Profile has both internal and marketing operating nodes | GBP client onboarding is internal service delivery, while GBP post ideas are organic/local marketing content; both can share the GBP domain but must route to different skills/modules. |
| 2026-05-08 | Klaroha is the external product brand; BOS remains the internal architecture | Klaroha means make it clear / it is very clear in Cebuano and better expresses the product promise: marketing, engineered for clarity by raising confidence, reducing delay, and removing operational drag. |
| 2026-05-08 | Operator model routing is environment-configured, not exposed in the CMO UX | The CMO should never see provider/model plumbing, but deployments need a safe way to pin the main chat and individual action modules to different models. |
| 2026-05-08 | Omnichannel MOS uses BITE as the handoff contract, not strategy modules | CEO/CMO collaboration defines versioned Intent; Bridge envelopes pass need-to-know payloads to specialist Transform modules; Evaluate gates align outputs back to Intent and route pass/fail/escalate before context returns to the CMO. |
| 2026-05-08 | Execution backend routing is modality-aware and target-scoped | The CMO brain, Transform modules, and future Evaluate gates may require different text/image/audio/video/data-analysis backends; provider/model/tool selection stays infrastructure-level and hidden from CMO product language. |
| 2026-05-08 | Backend override editing starts in Admin Module Browser | Operators need to assign the CMO brain model and each module's backend where they inspect module capability, policy, platform, and constraints; deeper Settings pages can later reuse the same API. |
| 2026-05-08 | Google Ads MCP starts as a mock read-only connector behind a tool module | We can build the CMO analytics workflow, skill routing, report block shape, and tests without live Google Ads access; later the connector can swap to the official MCP sidecar while preserving the BOS module contract. |
| 2026-05-08 | CMO operational connector context is registry-driven | Omnichannel BOS will have many MCP/API connectors; the CMO prompt should receive a connector catalog generated from registry/config, not one-off hardcoded Google Ads prose. |
| 2026-05-08 | CMO chat backend override is preferred-first, not outage-strict | A bad selected CMO model should not take the executive chat offline when other live credentials are available; BOS tries the configured backend first, then falls back through the normal provider waterfall. |
| 2026-05-08 | CMO Workspace panel stays execution-focused; Brand Kit, Modules, and Reports live in Admin Workspace | The right panel should support current campaign/approval work without becoming an admin dashboard. Brand governance, installed module inventory, and reporting references are lower-frequency administrative views. |
| 2026-05-08 | Brand Guidelines are the long-form source; Campaign Brand Kit is the short execution summary | Brand-plane strategy needs a durable, visible source of truth for positioning, visual identity, logo concept, and voice. Campaign Brand Kit remains the practical campaign-ready summary derived from it. |
| 2026-05-09 | Meta starts with an MCP sidecar-compatible read-only connector path | Speed-to-market matters while Meta API/OAuth/write permissions mature; BOS owns stable capability/module contracts, approval gates, and audit surfaces so MCP can later be swapped for native API without product lock-in. |
| 2026-05-10 | Org → Brand → Campaign hierarchy; Org = one company/agency deployment, Brand = distinct client or business unit | Mirrors J&J (one org, many product brands) and agency (one org, each client is a brand); avoids multi-tenancy while supporting multi-brand scale |
| 2026-05-10 | @klar is the explicit CMO command prefix; bare messages are discussion-only | Explicit prefix creates unambiguous intent signal; prevents accidental module dispatch during conversational turns |
| 2026-05-10 | No active brand + @klar directive → "Which brand are we working on?" | One direct question, no list, no syntax instructions; matches conversational CMO persona |
| 2026-05-10 | "Tell me about Klaroha" answers about the product system, not the Klaroha brand account | System identity (product knowledge) is baked into cmo_context skill; brand data is deployment-specific and loads only via @klar check brand X |
| 2026-05-10 | @klar plan injects PLAN MODE instruction into LLM turn; DB write deferred until user confirms | Keeps plan creation conversational; prevents orphaned IntentContracts from unconfirmed plans |
| 2026-05-10 | intent_ref FK on runs is live now; @klar evaluate is a stub until Phase 5 | The data hook costs nothing to add now and avoids a painful retrofit when Evaluate gate scoring is implemented |
| 2026-05-10 | Campaign = organizing unit for Stream; modules/employees are invisible execution | CMO thinks in campaigns and channels, not in which module ran; employee personas removed from output surface |
| 2026-05-10 | Capability transparency surfaces at @klar plan time, not on output cards | CMO sees the full delivery plan before committing; results arrive without operational noise |
| 2026-05-10 | campaign_id added directly to runs (not derived through intent_contracts join) | Stream needs cheap grouping on every page load; indirect join through intent_contracts is too expensive at frequency |
| 2026-05-10 | @klar org clears active brand and returns to org-level CMO context | Mirrors sidebar ✕ button; allows staying in chat flow without reaching for the mouse |
| 2026-05-10 | @klar brief redirects to Stream tab; not an active LLM command | Stream is the brief — daily signals, approvals, campaign status in one TikTok-scroll surface |
| 2026-05-10 | Capability-centric layout: `api/capabilities/{vertical}/{domain}/{task}/` replaces split `api/modules/` + `api/skills/` + `api/templates/` | One directory = one capability; compatible with Claude Code SKILL.md discovery and MCP tool/resource/prompt registration; adding a capability = adding one directory |
| 2026-05-10 | GBP is a marketing channel only; internal client onboarding is a workflows/ checklist | GBP capabilities belong under `marketing/channel/google_business_profile/`; the old `internal.client_onboarding.google_business_profile` module is replaced by a stateful checklist workflow |
| 2026-05-10 | @klar plan uses the CMO's active LLM with extended thinking enabled — no separate model config | Plan mode calls `_complete_cmo_messages(plan_mode=True)` which passes `thinking=True` to the adapter; OpenRouter+Claude gets `{"thinking":{"type":"enabled","budget_tokens":8000},"temperature":1}`; Gemini upgrades to `gemini-2.5-pro`; others use same model with strong no-dispatch instruction. Module dispatch is hard-zeroed in plan mode regardless of LLM output. |
| 2026-05-10 | Channel plugins are third-party code installed into `api/plugins/`, not `api/capabilities/` | Clear separation: first-party capabilities are Klaroha-owned; plugins are external. Plugin developers import only from `klaroha_sdk`. Host scans both roots identically at startup. |
| 2026-05-10 | Plugin credential injection at `inject_channel_credentials()` in runs.py — plugins never call `get_settings()` or query the DB | The brief dict is the plugin's only interface to host state. Credentials are resolved by the host from social_connections or env vars and injected before `build_prompt`. This is the trust boundary. |
| 2026-05-10 | `_load_file()` in registry.py takes `root_dir` + `prefix` args — plugin modules load as `bos_ext_*` | Prevents module name collisions between first-party (`bos_mod_*`) and plugin (`bos_ext_*`) Python modules. Same registry, same routing, different namespace. |
| 2026-05-10 | `register_template_root()` in module_base.py resets Jinja2 env on new root — plugins bring their own templates | Plugin templates are co-located in the plugin directory. Adding a root resets `_templates_env` so all future `build_prompt` calls use the updated search path. |
| 2026-05-11 | Gmail OAuth uses SocialConnection table (same as Facebook) with platform="gmail", page_id=email | Reuses existing brand-scoped credential storage; no new table or model needed; get_page_token() works unchanged for Gmail |
| 2026-05-11 | `_store_connection()` takes platform: str — not hardcoded | Any social platform can now be stored without code changes to the helper; Facebook caller sites pass "facebook" explicitly |
| 2026-05-11 | Plugin SKILL.md discovery mirrors register_template_root pattern | Plugins get skill routing at startup for free; CMO chat activates plugin skills identically to first-party capabilities; no SDK change needed |
| 2026-05-11 | scope: execution is invalid in SKILL.md; was a platform SDK documentation bug | SkillScope Literal does not include "execution"; Pydantic silently drops skills with unknown scope; fixed in SDK template and all deployed plugin files |
| 2026-05-11 | Google Gmail MCP server does not fit Klaroha's multi-brand model | MCP server uses the current user's Google account, not a brand's; no direct send (draft only); no brand-scoped token storage; custom OAuth per brand is the correct path |
| 2026-05-11 | mcp-headless-gmail not needed — gmail-auth plugin already implements direct Gmail API calls | send/receive modules use execute_tool_result with urllib; adding an MCP sidecar would be an extra hop for the same result; existing implementation is sufficient |
| 2026-05-11 | inject_channel_credentials must be called before execute_tool_result, not only before build_prompt | tool modules bypass the LLM path entirely; credentials were never reaching plugin tool modules before this fix |
| 2026-05-11 | FRONTEND_URL must match the actual serving URL, not the Vite dev server port | nginx proxies frontend on :80; OAuth callbacks redirect to FRONTEND_URL; if set to :3000 the redirect 404s; document this in .env.example and project brief |
| 2026-05-11 | Gmail-auth SKILL.md requires explicit module_id field, not only related_modules | _chat_modules() filters on s.module_id — None means the skill never reaches the dispatch list regardless of allowed_from_chat |
| 2026-05-11 | Platform hints must be distinct per module when multiple modules share a channel | shared platform_hint="gmail" caused both send and receive to fire on any "gmail" mention; distinct hints ("gmail send" / "gmail inbox") route correctly |
| 2026-05-12 | `api/capabilities/marketing/channel/` deleted — all channel Transform nodes are plugins | BOS owns the pipeline (Bridge + Intent + Evaluate); plugins own the channel (Transform nodes). First-party channel capabilities couple channel logic to BOS internals, preventing independent versioning and third-party ownership. |
| 2026-05-12 | Broad sample ads fallback is registry-driven, not hardcoded module IDs | Hardcoded IDs break silently when modules are removed or renamed; registry-driven fallback matches whatever `paid.ads.copy` skills are actually installed |
| 2026-05-12 | Pipeline-first before new channel capabilities | Facebook plugin has draft + publish nodes; pipeline wiring (approve → publish) must be validated before adding scheduled posts, image posts, analytics, or comments |
| 2026-05-12 | `POST /social/facebook/publish/{run_id}` is the pipeline connector | Approve + publish in one atomic action; reads approved run content, resolves page credentials, fires publish Transform, returns result block — no separate approve + run calls from client |
| 2026-05-12 | Facebook, Twitter, Meta, Google Ads channel capabilities removed — Gmail is the only active channel | Product focus: Gmail outreach and copywriting are the proven use case; Facebook/Twitter/Google Ads added complexity and mechanical routing that conflicted with the LLM-driven capability model |
| 2026-05-12 | CMO capability dispatch is fully LLM-driven from a manifest, not mechanically routed | No platform-specific routing rules in CMO chat code; SKILL.md owns activation policy; CMO reads capability_manifest.py at prompt time and decides when to invoke each module |
| 2026-05-12 | api/capability_manifest.py is the single source of truth for CMO-dispatchable capabilities | Centralizes manifest generation; decouples system prompt building from the module registry internals; enables GET /capabilities/manifest endpoint in future without changing CMO chat logic |
| 2026-05-12 | _build_system_prompt() takes no modules parameter — manifest is self-contained | capability_manifest.py generates the list; chat.py only needs the security boundary set (allowed_module_ids) which comes from list_skill_manifests() directly |
| 2026-05-12 | CMO operating instructions live in capabilities/workspace/cmo_context/SYSTEM_PROMPT.md, not chat.py | Hardcoding instructions in chat.py creates a path for capability-specific behavioral drift into core; externalizing to a governed file keeps chat.py logic-only and lets instructions be updated without any core edit |
| 2026-05-17 | Image gen plugin is `media.image` (generic), not `cloudflare-image` | Provider is an implementation detail; callers reference `media.image.generate` forever; swapping providers = updating stored credentials only, no module ID changes anywhere |
| 2026-05-17 | Image gen credentials stored via plugin vars API (`POST /plugins/media.image/credentials`), not env vars | Allows UI-driven credential management without server access; same encrypted ProviderKey storage used by other plugins |
| 2026-05-17 | Executor pre-generates images before channel dispatch via `_inject_generated_image` in runs.py | Any brief with `image_prompt` gets `_image_data_b64` injected before the channel module runs; no cross-plugin imports; image gen module is independently replaceable |
| 2026-05-17 | SKILL.md must include explicit `module_id:` field matching the module's `id` attribute | `capability_manifest.py` filters on `skill.module_id`; skills without it are discovered but never dispatched by CMO — silent routing failure |
| 2026-05-17 | CMO system prompt hard rule 9: RUN lines must use ONLY exact module IDs from the manifest | Llama 3.3 70B hallucinated `marketing.channel.google_ads.image_ad.draft` repeatedly; explicit prohibition added to HARD RULES block in `_build_system_prompt` |
| 2026-05-17 | Cloudflare Workers AI blocks Python-urllib user-agent from Docker (error 1010) | Add `User-Agent: Mozilla/5.0 (compatible; BOS/1.0)` header to all requests from the media-image module; curl from host works but Docker outbound IP triggers CF bot detection |
| 2026-05-18 | CMO agent harness uses pi model: read/execute/write primitives only; everything else is plugins | Claude Code and multi-agent frameworks are over-engineered for bounded CMO tasks; agents that know what to run don't need LLM routing. `GET /agent/state`, `GET /agent/context`, `GET /agent/capabilities`, `POST /agent/execute`, `PATCH /agent/review` |
| 2026-05-18 | BOS operates in two cycles: Setup-to-Market (Cycle 1) and Intelligence-to-Optimization (Cycle 2) | Cycle 1 runs once per client onboarding; Cycle 2 runs on cadence after metrics exist. Both cycles use the same agent harness. The flywheel: deploy → measure → optimize → redeploy. BL is the only human approver; CMO coordinates; plugins are the specialists. Stream is the BL's only interface. |

## BITE Methodology (Phase 3)

- [x] FEATURE: Create BITE.md (Business Implementation by Example methodology)
- [x] UPDATE: PROJECT_BRIEF.md now requires reading BITE.md before any system update
- [x] FEATURE: Fix Google Ads template to prevent truncated headlines ("Route Serious Convers" → complete words)
- [x] FIX: google_ad.j2 template - added "COMPLETE words" constraint to prevent partial words like "Convers" instead of "Conversations"

### Skill System Fixes (Phase 3)

- [x] FIX: Remove hardcoded skill names from chat.py prompt (Rules #1, #9)
- [x] FEATURE: Add BOS Skill Catalog to prompt for "what can you do" questions
- [x] FIX: YAML `>` syntax in 4 new skill files (parser compatibility)
- [x] FEATURE: Add `_build_block()` to Twitter module for platform-native rendering
- [x] FIX: Chat.py Rule #4 - samples now dispatch actual modules (not generic prose)

### New Skills Created (Phase 3)

- [x] `marketing.google_ads.analysis` v1.0.0 - GAQL performance analysis
- [x] `marketing.launch.sequencing` v1.0.0 - PLF launch orchestration
- [x] `marketing.launch.execution` v1.0.0 - Launch checklists and coordination
- [x] `marketing.launch.strategy` v1.0.0 - Launch strategy and channel planning

### Architecture Migration — Capability-Centric Layout (2026-05-10)

- [x] ARCH: Adopt capability-centric directory layout compatible with Claude Code skills discovery and MCP tool/resource/prompt registration
- [x] ARCH: Create `api/capabilities/` — every capability is one directory with SKILL.md + module.py + template.j2 co-located
- [x] ARCH: Update `registry.py` — scan for `module.py` under `api/capabilities/` instead of `*.py` under `api/modules/`
- [x] ARCH: Update `skills/loader.py` — `_SKILLS_ROOT` now points to `api/capabilities/`; added `knowledge` scope; fixed `related_skills` list→dict coercion
- [x] ARCH: Update `module_base.py` — Jinja2 `FileSystemLoader` root now `api/capabilities/`; all module `template` attributes updated to capability-relative paths
- [x] ARCH: GBP moved to `marketing/channel/google_business_profile/` — no more internal/client_onboarding module
- [x] ARCH: Create `api/capabilities/workflows/client_onboarding/google_business_profile.md` — operational task checklist replacing the old GBP onboarding module
- [x] ARCH: Update CLAUDE.md directory layout and code standards
- [x] ARCH: Update PROJECT_BRIEF.md with section 0 Architecture Directive
- [x] CLEANUP: Remove `api/modules/` and `api/templates/` legacy directories after confirming no remaining imports
- [x] ARCH: Update legacy flat SKILL.md IDs (`marketing.facebook_ad`, `marketing.google_ad`, `marketing.twitter_ad`, `marketing.cold_email`) to canonical channel paths
- [ ] ARCH: Implement `workflows/` task tracking — CMO command activates a checklist template, creates live trackable task items
- [x] BUG: @klar plan dispatched ad modules instead of returning strategic plan — dispatch decision tree re-added modules from conversation history execution intent; fixed by gating entire dispatch tree on `not pending_plan_action`
- [x] FEATURE: @klar plan — full CMO strategic planner skill (workspace.plan_mode v1.0.0); consumes brand_guidelines, campaign_brand_kit, product_catalog, audience_profiles, marketing_reports, campaign_reports, competitor_profiles, industry_data; omnichannel output contract; extended thinking enabled; expandable resource drop-in for competitors and industry reports
- [x] BUG: Brand isolation — CMO chat dispatched modules with workspace-scoped brief even when an active Brand was set; `_resolve_brief(db, ws)` always pulls `ws.name`, `ws.brand_json`, and `Product/Audience` rows by `workspace_id`; fixed: CMO module dispatch (chat.py:820) and revise endpoint (chat.py:924+898) now use `_brand_scoped_brief(db, ws, active_brand)` so products, audiences, documents, and identity are scoped to the correct brand
- [x] BUG: CMO LLM compliance failures — three violations observed in live MotorMoto session: (1) "what can you do" returned product list instead of CMO capability card; (2) "lets make a marketing plan" asked 6 clarifying questions instead of dispatching `RUN: marketing.plan.campaign_strategy`; (3) "give me sample ad copies" generated inline Headline/Description blocks violating Rule 6. Root cause: `_build_system_prompt` placed brand/product/audience context before skill rules, causing the LLM to weight brand context over artifact boundary constraints. Fixed: added HARD RULES block (5 rules: no inline native content, dispatch-first, ambiguous→one question, one question max, capability card format) at top of system prompt before brand context in `api/routers/chat.py:_build_system_prompt`.
- [x] FEATURE: Streaming agentic loop — CMO pipeline now streams via SSE; steps appear live as modules run, artifact refs land one at a time before the reply, step log persists as completed (greyed ✓) so the user sees the full execution trace. Backend: `POST /chat/stream` StreamingResponse endpoint + `_generate_chat_stream()` async generator + `_run_modules_streaming()` as single dispatch source of truth. Frontend: `api.chatStream()` async generator in client.ts consumes SSE; `CmoChat.tsx` renders step labels with pulse animation during execution and ✓ on completion. Nginx: dedicated `/api/chat/stream` location block with `proxy_buffering off` + `X-Accel-Buffering: no` response header.
- [x] BUG: CMO mass-dispatched all 25 capabilities on "trigger all your capability" test command — LLM followed user instruction literally; no system-level protection against blanket dispatch. Fix: added hard rule #10 to CMO system prompt: never emit more than 3 RUN lines per turn unless user explicitly named each capability; "trigger all / test all / showcase all" commands must respond with capability summary + clarifying question instead of dispatching.
- [x] BUG: "For which brand is this?" follow-up question triggered a new Campaign-Strategy-Planner run — SKILL.md excluded_triggers did not cover follow-up question patterns. Fix: added `for which brand`, `which brand`, `what brand`, `update?`, `which one`, `trigger`, `test all`, `showcase` to campaign_strategy excluded_triggers.
- [x] BUG: posts/publish dispatched without approved message text during mass-dispatch test — module code already guards against empty message (returns failure artifact), but the module still ran and created a failure artifact. Fix: added pre-dispatch guard in `_run_modules_streaming()`: if module_id is `marketing.channel.meta.posts.publish` and no `message` param is present in inline params, skip dispatch entirely with a warning log.

### Production Deployment — hq.klaroha.com (2026-05-14)

**Domain structure:** `hq.klaroha.com` = BOS Command Hub (internal). `klaroha.com` = reserved for public Astro marketing site (Parking Lot). `staging.klaroha.com` = staging stack.

- [x] INFRA: VDS provisioned — Contabo Virtual Dedicated Server M, Ubuntu 22.04 LTS, 194.233.76.143
- [x] INFRA: DNS on Cloudflare — klaroha.com A record → 194.233.76.143, proxied (orange cloud), TLS handled by Cloudflare
- [x] INFRA: Docker installed (v29.4.3) on VDS
- [x] INFRA: Private GitHub repo created (github.com/itsborj/bos), deploy key added to server
- [x] INFRA: BOS stack deployed — api, db, web, nginx running via docker compose
- [x] INFRA: Alembic migrations applied on production DB
- [x] INFRA: Web container switched from Vite dev server to production build (nginx serving static files) — fixes session wipe on navigation
- [x] INFRA: Workspace initialized, bootstrap API key created
- [~] INFRA: Move live to hq.klaroha.com — vite.config.ts updated; pending: add `hq` A record on Cloudflare, update server .env FRONTEND_URL=https://hq.klaroha.com, git pull + docker compose up --build on server
- [ ] INFRA: Create non-root user + lock down SSH (root login still enabled)
- [x] INFRA: staging.klaroha.com — docker-compose.staging.yml created (ports 8080/8001/5174, separate DB bos_staging); .env.staging live on server; first deploy confirmed working
- [x] BUG FIX: staging ENCRYPTION_KEY not picked up — staging uses `env_file: .env.staging` (not `.env`); `docker compose restart` does not re-read env_file, must use `--force-recreate`; fixed by writing clean .env.staging and running `docker compose -p staging -f docker-compose.staging.yml up -d --force-recreate api`
- [x] INFRA: GitHub Actions CI — .github/workflows/ci.yml created; runs pytest + banned-pattern guardrails on PR; deploys to staging on staging branch push, production on main branch push
- [x] INFRA: CODEOWNERS — created; api/plugins/ owned by @itsborj + @kibanu; core paths owned by @itsborj only
- [ ] INFRA: GitHub secrets — add VDS_HOST, VDS_USER, VDS_DEPLOY_KEY, STAGING_PATH, PROD_PATH to repo secrets before CI deploy steps work; generate a deploy SSH key pair (ssh-keygen -t ed25519), add public key to server authorized_keys, private key to GitHub secret VDS_DEPLOY_KEY
- [ ] INFRA: Branch protection — configure in GitHub repo settings: `main` require CI green + 1 review; `staging` require CI green only
- [x] INFRA: Plugin dev access — @kibanu added as repo collaborator (Write); CODEOWNERS updated with real handle; SSH key added to GitHub; local stack fully operational on staging branch
- [x] INFRA: Agent harness — GET /agent/state, /context, /capabilities, POST /agent/execute, PATCH /agent/review; pi model (read/execute/write), no LLM routing; scripts/validate_connection.sh for connection testing
- [x] INFRA: Dev 2 pipeline verified — hello world plugin built, discovered, executed, approved end-to-end; `module_id` confirmed required in SKILL.md for capability manifest registration
- [ ] INFRA: Demo API key — separate named key for walkthrough sessions
- [ ] INFRA: SSL via nginx + certbot (currently Cloudflare proxy handles TLS; needed if Cloudflare proxy ever bypassed)
- [ ] INFRA: PostgreSQL backup strategy
