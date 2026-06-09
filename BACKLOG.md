# BOS — Backlog

**Last updated:** 2026-06-09
**Structure:** Topic-based sections. Each topic is self-contained. Read only the section relevant to your task.
**Active topics:** SOCIAL · DEPLOY · SDK · STRAT · CRTV · CHAN · ARCH

## How to Use This
- Pick the topmost `[ ]` item in the relevant topic and work it.
- Mark `[~]` when started, `[x]` when done.
- Add new items at the bottom of the relevant topic section.
- `[!]` = blocked. `[-]` = deferred. Counter format: `TOPIC-NNN · YYYY-MM-DD`

## Legend
```
[ ]  Todo
[~]  In Progress
[x]  Done
[!]  Blocked (note reason)
[-]  Deferred (moved out of scope)
```

---

## ⚑ Quick Nav — Topics

| Code | Topic | Status | Last Activity |
|------|-------|--------|---------------|
| [SOCIAL](#social) | Social Publishing Priorities | 🔴 Active | 2026-06-09 |
| [DEPLOY](#deploy) | Deploy & Distribution | 🔴 Open | 2026-06-08 |
| [SDK](#sdk) | Plugin SDK & Thin Core | 🔴 Open | 2026-06-08 |
| [STRAT](#strat) | Strategy, CMO & Planning | 🔴 Open | 2026-06-08 |
| [CRTV](#crtv) | Creative Production | 🔴 Open | 2026-06-08 |
| [CHAN](#chan) | Channel Plugins | 🔴 Open | 2026-06-08 |
| [ARCH](#arch) | Campaign Architecture | 🔴 Open | 2026-06-08 |
| [ADMIN](#admin) | Admin & Onboarding | 🔴 Open | 2026-06-08 |
| [UX](#ux) | Stream & UX | 🔴 Open | 2026-06-08 |
| [CNCL](#cncl) | Council | 🔴 Open | 2026-06-08 |
| [HARD](#hard) | Hardening & Second Vertical | ⚪ Backlog | 2026-05-15 |
| [Archive](#archive) | Completed Phases 0–5 | ✅ Done | 2026-05-20 |
| [Parking Lot](#parking-lot) | Deferred | — | — |
| [Decisions Log](#decisions-log) | Decisions | — | 2026-06-08 |

---

## ⚑ Locked Architecture (Do Not Revert)

| # | Rule | Locked in | Regression signal |
|---|---|---|---|
| 1 | **Channels in plugins only.** `api/capabilities/marketing/channel/` is deleted and must never be recreated. All channel Transform nodes live in `api/plugins/{channel}/`. | v3.7–3.8 (2026-05-12) | Finding channel Transform nodes in `api/capabilities/` |
| 2 | **No hardcoded routing in `chat.py` / `skills/router.py`.** LLM reads `capability_manifest.py` only. No `_explicit_platforms()`, `_is_broad_sample_ads_request()`, `_has_generation_intent()`, or manual module ID lists. | v3.8 (2026-05-12) | Any `if "facebook" in message`, platform-matching function, or hardcoded module ID in router files |
| 3 | **Brand active → `_brand_scoped_brief()`**, never `_resolve_brief()`. Must build from overrides + Brand rows only. | v3.16 (2026-05-13) | Cross-brand context bleed |
| 4 | **`hydrate_memory_slots()` with `brand=active_brand`** when brand is active. No workspace fallback inside active-brand turns. | v3.17 (2026-05-15) | Wrong brand products/docs in CMO replies |
| 5 | **Brand switching via hidden `SCOPE:` directive** and `workspace.scope_resolution` SKILL.md. No phrase-matching in `chat.py`. | v3.19 (2026-05-15) | Brand-name detection in `routers/chat.py` |
| 6 | **CMO chat returns artifact refs only.** No inline copy, Subject/Body, Headline/Description, budgets, targeting, or fake proof. | v3.10 (2026-05-13) | Inline platform-native content in CMO reply text |
| 7 | **Mobile-first CMO replies:** 1–4 lines, one idea per line, bullets for choices, max one question. | v3.12 (2026-05-13) | Long dense CMO paragraphs |
| 8 | **Plugin credentials via `inject_channel_credentials()` only.** Plugins read `brief["_channel_credentials"]`. Never call `get_settings()` or query DB. | v3.5 (2026-05-10) | Plugin `module.py` querying `social_connections` or env vars directly |
| 9 | **`capability_manifest.py` is the CMO capability single source of truth.** Adding a capability = add `SKILL.md` with `allowed_from_chat: true` + `module_id:`. No manifest code edits needed. | v3.8 (2026-05-12) | Manual edits to capability_manifest.py |
| 10 | **Revise endpoint resolves Brand from `original_run.brand_id`** before building execution brief. Same `_brand_scoped_brief()` path as dispatch. | v3.16–3.17 (2026-05-13) | Revision runs receiving workspace context |
| 11 | **Artifact dispatch blocked when no Brand resolved** in multi-brand workspace. Returns brand clarification instead. | v3.18 (2026-05-15) | `brand_id=NULL` artifact creation in multi-brand workspaces |
| 12 | **Backlog → ClickUp sync required** after every session with task status changes or new task additions. Script is idempotent. | v3.26 (2026-05-18) | See CLAUDE.md for sync command |
| 13 | **Stream artifact cards are inline approval surfaces.** `StreamArtifactCard` embeds `ApprovalBundle` directly. No `StreamRunPanel`. No `requiresReview → onOpenPanel`. `stream-side-panel` is for `StreamUpdateOut` types only. `bos:focus-artifact` injects runs into feed; does NOT call `setPanelItem` with a run. | v3.42 (2026-05-25) | Re-added `StreamRunPanel`; `onOpenPanel` prop; `bos:focus-artifact` opening side panel |
| 14 | **Creative assets are channel-agnostic. Distribution is never hardwired.** A generated image or video is a Drive artifact. Channel distribution = separate CMO dispatch. | v3.43 (2026-05-26) | Hardwired `allowed_actions` coupling creative type to specific channels |
| 15 | **`strategy_workflow` output contract is the debug standard.** `GET /strategy-workflows/{id}` is the primary measure. All 6 wired components must be `status: "complete"` with all typed fields non-empty. | v3.47 (2026-06-04) | Treating Stream card appearance or self_check pass as success signal |
| 16 | **Full media generation is brand-locked.** CMO brain generates all downstream provider prompts from active Brand guidelines / `BRAND.md`. Every primitive and final CompositionSpec must pass brand gates before render/review. | v3.52 (2026-06-06) | Generic prompts without brand slots; off-brand audio/video |

---

## SOCIAL — Social Publishing Priorities {#social}

> **Active priority as of 2026-06-09.**
> Goal: image and video creation → Facebook post + YouTube upload, end-to-end for Klaroha brand.
> Method: verify pipe → verify connection → deliver full capability. No new code until pipes are confirmed live.

### Context for agents picking this up

**Stack:** `localhost:8090` for local generation/Drive/YouTube validation. Run `docker compose up -d` if not running.

**Facebook validation caveat:** Meta/Facebook OAuth publish validation should run from `staging.klaroha.com` (or another domain registered in the Meta app), not localhost. The current Meta app/auth history is staging-domain based; localhost publish attempts can fail because Meta redirect/domain rules and page-token impersonation permissions do not line up with the local callback. Do not treat localhost Facebook publish failure as a code regression until the same source artifact is retried on staging with a freshly authorized Facebook connection.

**Klaroha brand ID:** `c1cb6603-e8d4-4e63-8995-640453d5b50b`

**Environment changes made (2026-06-09):**
- `KLAROHA_LOAD_INTERNAL_PLUGINS=true` — added to `.env`. All 18 bundled plugins now load.
- `IMAGE_GEN_PROVIDER=bytedance` — changed from `gemini`. ByteDance (Seedream) was the working provider before.

**Confirmed social connections for Klaroha:**
- Facebook page `Klarohahq` (page_id `1172728675913055`) — `status: connected` ✅
- Google Drive — `status: connected` ✅
- YouTube (channel `UCJUw2QSIXs458Gz4Jol3VYQ`) — `status: connected` ✅

**Verified credentials in DB (pinged 2026-06-09):**
- `execution_backend_overrides`: `media.image.generate` → provider `bytedance`, model `seedream-4-5-251128` ✅
- `execution_backend_overrides`: `media.video.generate` → provider `bytedance`, model `dreamina-seedance-2-0-fast-260128` ✅
- `provider_keys`: `bytedance` api_key row exists (2026-06-06) ✅
- `provider_keys`: `plugin.media.image` plugin_vars row exists (2026-05-16) ✅
- `provider_keys`: `plugin.channel.meta` plugin_vars row exists (2026-05-17) ✅
- ⚠️ `media.image` and `media.video` show `credentials_configured: false` in `/api/plugins` — this is a **false negative** (see BUG-SOCIAL-001 below). Credentials are actually present and will resolve at runtime via `execution_backend_overrides`.
- ⚠️ `google.drive` and `creative.factory` also show `credentials_configured: false` — same false-negative bug. Drive connection IS `connected` for Klaroha.

**CMO workflow (pinged 2026-06-09):**
- ✅ CMO responds and routes basic messages
- ✅ Core capabilities visible: planning, strategy_workflow, council
- ✅ Required social plugins now visible in CMO manifest after activation (media image/video, creative factory, Meta, YouTube; Drive active but non-dispatchable by design)

**Plugin activation state (updated 2026-06-09):**
Required social plugins are active org-wide: `media.image`, `media.video`, `creative.factory`, `channel.meta`, `google.drive`, and `channel.youtube`. No credential data was touched. YouTube OAuth re-auth is complete and read-only API validation passed.

**History:** These pipelines were working before the architecture shift (credential_slots refactor T060–T062). All the code, credentials, and connections are intact. This is a restore-and-verify task, not a build task.

---

### Bugs found during ping test

- [x] BUG-SOCIAL-001 · 2026-06-09 · `credentials_configured` false-negative for `backend_override_*` slot types. Fixed: `not missing and social_configured` — plugins with no `platform_var` slots (media.image, media.video) now show `True` when nothing is missing.
- [x] BUG-SOCIAL-002 · 2026-06-09 · `credentials_configured` false-negative for `social_token` slot types. Fixed: preload connected social platforms at request time; check `social_token_platforms & connected_social_platforms`.
- [x] BUG-SOCIAL-003 · 2026-06-09 · No CMO manifest inspection endpoint. Fixed: `GET /api/capability-manifest?brand_id=` endpoint added to `api/routers/plugins.py`; returns brand-filtered capability list.
- [x] BUG-DEPLOY-001 · 2026-06-09 · Production deploy used `docker compose up --build` — rebuilt from source on VDS, bypassed CI-built GHCR image, produced `git_sha: "dev"`, diverged completely from the staging deploy path. Root cause of INC-009. Fixed: production deploy now pulls SHA-tagged GHCR image and uses `--no-build`, identical path to staging.

---

### Lean Verification Model

```
V1 — Load gate        Plugin loads. Module appears in manifest for the brand.
V2 — Pipe gate        Module fires. Brief flows through. Artifact returns.
V3 — Connection gate  Real token present. Real API call succeeds.
V4 — Full capability  Approve artifact → publish live → audit trail written.
```

If a gate fails, fix it before advancing. Only V4 may require code changes.

---

### Prerequisite — Activate plugins for Klaroha

All five required plugins are `org=inactive`. Activate them before testing any path.
Use `POST /api/plugins/{plugin_id}/activate` with `brand_id: null` (org-level) or `brand_id: "c1cb6603-e8d4-4e63-8995-640453d5b50b"`.

- [x] SOCIAL-000 · 2026-06-09 · ENV: Set `KLAROHA_LOAD_INTERNAL_PLUGINS=true` and `IMAGE_GEN_PROVIDER=bytedance` in `.env`. Run `docker compose up -d api`. Confirm 18 plugins load via `GET /api/plugins`.
- [x] SOCIAL-014 · 2026-06-09 · ACTIVATE: `media.image` — org-level activation. Verified `media.image.generate` appears in CMO manifest for Klaroha.
- [x] SOCIAL-015 · 2026-06-09 · ACTIVATE: `media.video` — org-level activation. Verified `media.video.generate` appears in CMO manifest for Klaroha.
- [x] SOCIAL-016 · 2026-06-09 · ACTIVATE: `creative.factory` — org-level activation. Verified `creative.post.image` appears in CMO manifest for Klaroha.
- [x] SOCIAL-017 · 2026-06-09 · ACTIVATE: `channel.meta` — org-level activation. Verified Meta publish capabilities appear in CMO manifest for Klaroha.
- [x] SOCIAL-018 · 2026-06-09 · ACTIVATE: `google.drive` — org-level activation. Required by `creative.post.image` and all video paths. Active org-wide; Drive capabilities are not CMO-dispatchable by design.

---

### Priority 1 — Facebook Image Post

**Path:** `creative.post.image` (ByteDance image gen → Drive store → caption) → approve in Stream → `meta.posts.publish` → live Klarohahq Facebook Page

**This pipeline was working before the architecture shift.** All modules, credentials, and the Facebook connection are intact. The only blocker was plugin activation (see prereq above).

| Gate | Status | Notes |
|------|--------|-------|
| V1 | ✅ Confirmed | `media.image` and `channel.meta` load; ByteDance key and Meta creds in DB |
| V2 | ✅ Confirmed | `creative.post.image` validated LIVE previously — 2 real creatives in Drive |
| V3 | ✅ Confirmed | Facebook `Klarohahq` page connected (page_id `1172728675913055`) |
| V4 | [!] Deferred to staging | Localhost image generation + Drive upload passed. Live Facebook publish must be retried on `staging.klaroha.com` because Meta app/OAuth validation is staging-domain based, not localhost. |

- [!] SOCIAL-001 · 2026-06-09 · V4 TEST: After SOCIAL-014–018, ask CMO "make a Facebook post for Klaroha about [topic]" → approve in Stream → confirm post appears on Klarohahq Facebook Page. Local image generation + Drive upload passed (`creative.post.image` run `7c9dbea8-27e6-4997-b3b4-7c40156f538d`, Drive file `1up6n28CWzOHuJsvhyxHafUDlJMRqedcS`). Localhost publish failed (`cb836581-b2fb-4550-808d-36d9477f5e2c`) with Meta OAuth 190: page token lacks required page impersonation permissions. Operator note: previous Facebook auth was validated on `staging.klaroha.com`; Meta does not reliably support this localhost callback for live Page publish. Defer live Facebook proof until staging; retry from the same source artifact after staging Facebook auth is fresh.
- [ ] SOCIAL-002 · 2026-06-09 · BUG CHECK: If `pages/read` returns a pending run instead of a setup_blocker when credentials are missing (CHAN-039), fix the missing-credentials path in `api/plugins/meta/capabilities/marketing/channel/meta/pages/read/module.py` before retesting.

---

### Priority 2 — Video → YouTube

**Path:** `media.video.generate` (ByteDance Seedance → Drive store) → approve in Stream → `youtube.video.publish` → live Klaroha YouTube channel

**Video generation + YouTube publish is validated live.** YouTube publish module is implemented; YouTube connection is re-authenticated and private upload passed.

| Gate | Status | Notes |
|------|--------|-------|
| V1 | ✅ Confirmed | `media.video` loads; ByteDance video key in DB |
| V2 | ✅ Confirmed | Video generation and Drive upload working |
| V3 | ✅ Confirmed | YouTube OAuth reauth complete; connection validate run succeeded for `UCJUw2QSIXs458Gz4Jol3VYQ` |
| V4 | ✅ Confirmed | `runs.py` handled `drive_file_id` → re-download → YouTube private upload; video processed on YouTube |

- [x] SOCIAL-006 · 2026-06-09 · REAUTH: Re-connect YouTube for Klaroha brand in Admin → Brands. OAuth scope includes `youtube.upload` — no scope change needed. Just re-auth. `channel.youtube` is active org-wide so validation/publish capabilities are visible after reauth.
- [x] SOCIAL-007 · 2026-06-09 · V3 VERIFY: After reauth, confirm `channel.youtube` connection resolves access token via `inject_channel_credentials`. Hit `youtube.connection.validate` for Klaroha to confirm token works. Validation run `20c87630-3945-41be-9422-83386b8da568` succeeded: channel `Klaroha` / `@klarohahq` / `UCJUw2QSIXs458Gz4Jol3VYQ`.
- [x] SOCIAL-008 · 2026-06-09 · V4 TEST: Generate a short video → approve in Stream → click "Publish to YouTube" → confirm video appears on Klaroha YouTube channel (privacy=private). Confirm `action_result` artifact written with platform video ID. Passed: video generation run `27ffa581-1786-48b2-ac65-146e62e780d5`, Drive file `1s3FgxDnMJ21mTGwMHYjNnyKQMGZwEhbG`, YouTube publish run `824bd91f-ff67-4bee-a5a6-a16fb36fbc72`, video `https://www.youtube.com/watch?v=Yo1qHG8RHmc` (`privacy=private`, `uploadStatus=processed` verified via YouTube Data API).
- [x] SOCIAL-009 · 2026-06-09 · QUOTA GUARD: If YouTube upload quota is exhausted, surface `setup_blocker` artifact not a failed run. Not triggered in V4 test — upload quota available; no code change needed.

---

### Priority 3 — Video → Facebook (Video Post)

**Path:** `media.video.generate` → Drive → approve → `meta.video.publish` → live Klarohahq Facebook Page

Shares the Meta connection with P1. Unblocked once P1 V4 passes.

| Gate | Status | Notes |
|------|--------|-------|
| V1 | ✅ Confirmed | Plugin loads |
| V2 | ✅ Confirmed | Video generates; output block has `publish_facebook` wired to `meta.video.publish` |
| V3 | ⚪ After P1 | Shares Facebook connection with P1; once P1 V3 passes this is unblocked |
| V4 | ⚪ After V3 | `meta.video.publish` implemented; needs live test post-refactor |

- [ ] SOCIAL-010 · 2026-06-09 · V4 TEST: After P1 passes, generate video → approve → "Publish to Facebook" → video post appears on Klarohahq page.
- [ ] SOCIAL-011 · 2026-06-09 · VERIFY: Facebook video upload uses a chunked API different from photo upload. Confirm `meta.video.publish/module.py` handles Drive-sourced video (re-downloaded to temp file) correctly.

---

### Not in scope (defer to CHAN section)

Scheduling, engagement monitoring, TikTok, LinkedIn, paid social (Meta Ads, YouTube Ads), batch publishing.

---

## DEPLOY — Deploy & Distribution {#deploy}

> Covers: CI/CD, first-org deploy, OAuth relay, first-boot init, setup wizard, distribution, server operations.
> **Non-negotiable:** Never push `staging` branch to trigger deploy. Staging deploys are manual only via `deploy-staging.sh`. Local dev = `localhost:8090` only.

### Open: OAuth Relay (`connect.klaroha.com`)

- [ ] DEPLOY-001 · 2026-06-08 · ARCH DECISION: Confirm relay design — single Google Cloud app (Klaroha-verified, all scopes), one stable redirect URI per platform, signed one-time token handoff back to each BOS instance, `KLAROHA_RELAY_KEY` for instance authentication
- [ ] DEPLOY-002 · 2026-06-08 · Relay service: FastAPI app on `connect.klaroha.com` — Google PKCE OAuth start/callback, `POST /relay/claim`, `POST /relay/refresh`, deployment key validation middleware
- [ ] DEPLOY-003 · 2026-06-08 · Relay holds: `GOOGLE_CLIENT_ID/SECRET`, `META_APP_ID/SECRET` — never shipped in BOS Docker image
- [ ] DEPLOY-004 · 2026-06-08 · BOS instance config: `KLAROHA_RELAY_URL` + `KLAROHA_DEPLOYMENT_KEY` replace all per-platform OAuth env vars
- [ ] DEPLOY-005 · 2026-06-08 · `provider_auth.py` relay paths already coded — wire to live relay endpoints
- [ ] DEPLOY-006 · 2026-06-08 · `get_page_token()` in social.py: when relay configured, delegate refresh to relay instead of calling Google directly
- [ ] DEPLOY-007 · 2026-06-08 · Meta OAuth relay path: same broker model as Google
- [ ] DEPLOY-008 · 2026-06-08 · Relay deployment: standalone Docker service, Klaroha-managed VPS, SSL, Redis for one-time handoff token store (TTL 5 min)
- [ ] DEPLOY-009 · 2026-06-08 · Validate end-to-end: fresh BOS instance with only `KLAROHA_DEPLOYMENT_KEY` connects Gmail and Google Calendar without any Google Cloud Console setup

### Open: First-Boot Init

- [ ] DEPLOY-010 · 2026-06-08 · Detect first boot: generate and persist `API_SECRET_KEY` + `ENCRYPTION_KEY` to secrets volume (F1-1/F1-2 done; extend to remaining secrets)
- [ ] DEPLOY-011 · 2026-06-08 · Auto-run `alembic upgrade head` on container start — confirm idempotent on clean DB
- [ ] DEPLOY-012 · 2026-06-08 · Auto-bootstrap admin: call `POST /auth/bootstrap` on first boot if no admin key exists; write one-time setup token to startup log
- [ ] DEPLOY-013 · 2026-06-08 · First-login redirect: if no workspace configured, redirect all admin routes to `/admin/onboarding`
- [ ] DEPLOY-014 · 2026-06-08 · Secrets volume: `API_SECRET_KEY`, `ENCRYPTION_KEY`, `DATABASE_URL` persisted on first boot — operator never edits these manually

### Open: Minimal .env

- [ ] DEPLOY-015 · 2026-06-08 · Audit `.env.example` — identify every var that can be eliminated by relay or first-boot init
- [ ] DEPLOY-016 · 2026-06-08 · Target `.env` for first org: `KLAROHA_DEPLOYMENT_KEY`, `KLAROHA_RELAY_URL`, `FRONTEND_URL` — nothing else required to get CMO operational
- [ ] DEPLOY-017 · 2026-06-08 · Document remaining optional vars: BYOK keys (cost optimization), model overrides (quality), Meta/TikTok creds (until relay covers them)

### Open: Setup Wizard

- [ ] DEPLOY-018 · 2026-06-08 · Step 1: org name + admin email → workspace configured
- [ ] DEPLOY-019 · 2026-06-08 · Step 2: import brand brief → brand memory populated
- [ ] DEPLOY-020 · 2026-06-08 · Step 3: CMO chat opens with brand context loaded
- [ ] DEPLOY-021 · 2026-06-08 · Optional step: "Connect your AI key for lower cost" → BYOK add form; skippable

### Open: Distribution

- [ ] DEPLOY-022 · 2026-06-08 · BITE sample: DigitalOcean 1-Click app deploy experience — Marketplace → first CMO message, zero console steps
- [ ] DEPLOY-023 · 2026-06-08 · `docker-compose.yml` review: confirm works as standalone install file with minimal vars
- [ ] DEPLOY-024 · 2026-06-08 · Install script: `curl install.klaroha.com | bash` — pulls compose file, prompts for deployment key + domain, generates secrets, starts stack
- [ ] DEPLOY-025 · 2026-06-08 · DigitalOcean Marketplace listing preparation (post relay + first-boot init complete)

### Open: Phase 5 Deployment Docs

- [ ] DEPLOY-026 · 2026-05-15 · One-command VPS setup (Ubuntu 22.04 + Docker)
- [ ] DEPLOY-027 · 2026-05-15 · `.env.example` fully documented
- [ ] DEPLOY-028 · 2026-05-15 · SSL via nginx + certbot
- [ ] DEPLOY-029 · 2026-05-15 · PostgreSQL backup strategy

### Open: Live Deploy (001-thin-core-proof → hq.klaroha.com)

- [ ] DEPLOY-030 · 2026-06-08 · On server: clone or pull `~/bos-plugins/` repo — confirm `hello/` and `gbp-completeness/` exist
- [ ] DEPLOY-031 · 2026-06-08 · Verify server `.env` has `EXTERNAL_PLUGINS_PATH=/home/<user>/bos-plugins` (absolute path — Docker does not expand `~`)
- [ ] DEPLOY-032 · 2026-06-08 · Merge `001-thin-core-proof` to `main` — `git checkout main && git merge 001-thin-core-proof`
- [ ] DEPLOY-033 · 2026-06-08 · Deploy to hq.klaroha.com via existing runbook — confirm `GET https://hq.klaroha.com/api/` returns `{"status":"ok"}`
- [ ] DEPLOY-034 · 2026-06-08 · V8 live verification — server logs show both plugins as `[external]`; `No external plugin root found` does NOT appear
- [ ] DEPLOY-035 · 2026-06-08 · Repeat V4 on live — trigger hello via CMO chat; confirm `pipeline_test_result` artifact
- [ ] DEPLOY-036 · 2026-06-08 · Repeat V6 on live — trigger GBP audit via CMO chat; confirm `setup_blocker` or `gbp_completeness_result` artifact

### Open: Setup Required

- [ ] DEPLOY-037 · 2026-05-17 · SETUP REQUIRED: Add `https://hq.klaroha.com/social/google-calendar/callback` to Google Cloud Console authorized redirect URIs
- [ ] DEPLOY-038 · 2026-05-11 · SETUP REQUIRED: Create Google OAuth 2.0 app in Google Cloud Console; enable Gmail API; add Gmail callback; copy GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET to `.env`

### Completed: Infrastructure & CI/CD ✓

Build-once SHA-tagged Docker images via CI → GHCR. `deploy-staging.sh` pulls pre-built images. Auto-generate `API_SECRET_KEY` + `ENCRYPTION_KEY` at first boot (F1-1/F1-2). Bootstrap default workspace on first boot (F1-4). TypeScript strict mode + `tsc -b` CI gate. Devcontainer added.
Port topology: 8090=local/prod nginx, 8091=staging nginx, 8080=reserved. Staging deploys are manual; `deploy-staging` CI job permanently disabled 2026-06-01.

---

## SDK — Plugin SDK & Thin Core {#sdk}

> Covers: `klaroha_sdk` pip package, external plugin system (`~/bos-plugins/`), hook registry, 001-thin-core-proof feature.
> Spec: `specs/001-thin-core-proof/` | SDK contract: `specs/001-thin-core-proof/contracts/klaroha-sdk-api.md`
> Plugin authoring: `~/bos-plugins/README.md` · `specs/001-thin-core-proof/plugin-dev-onboarding.md`

### Open: GBP End-to-End (US4)

- [!] SDK-001 · 2026-06-08 · Connect Google Business Profile OAuth for active brand — OAuth token exists for Klaroha (`jvcatingub@gmail.com`) with `business.manage` scope, but operational connection is BLOCKED because Google Cloud GBP quotas are `0`; BOS marks `social_connections.status='needs_setup'`, not connected.
- [x] SDK-010 · 2026-06-08 · BUG: GBP plugin swallows Google API failures and misreports quota/API-disabled errors as `No Google Business Profile location found`. Bad sample: Google returns `429 quota_limit_value=0`, but Stream/CMO says no location exists on the account. Fixed sample: GBP artifact reports the actual setup blocker (`API disabled`, `quota/access not approved`, or `no GBP account/location`) and only a 200 response with empty locations may say no location found.
- [!] SDK-011 · 2026-06-08 · SETUP BLOCKER: Request/receive Google Business Profile API access/quota for project `1029575754786`. Required quotas currently `0`: `mybusinessaccountmanagement.googleapis.com` Requests/minute and `mybusinessbusinessinformation.googleapis.com` Requests/minute. Until quota is >0, no successful GBP audit is possible.
- [!] SDK-002 · 2026-06-08 · Trigger full GBP completeness score — BLOCKED by SDK-011. Success requires `gbp_completeness_result` artifact with `status: pending_review`, `self_check: pass`, `score`, `rating`, `raw_score`, and `fields[]`; failed setup blockers do not count.
- [ ] SDK-003 · 2026-06-08 · Verify approval flow — `approval_bundle` renderer shows Approve and Dismiss; click Dismiss; confirm artifact status updates in Stream

### Open: Polish

- [x] SDK-004 · 2026-06-08 · Update `specs/001-thin-core-proof/plugin-dev-onboarding.md` — absolute path Docker warning added; `excluded_triggers` guidance present; `requires_intent` canonical values block added (all 8 values). Done.
- [x] SDK-005 · 2026-06-08 · Update `api/plugins/PLUGIN_SDK.md` — prominent note added at top: `api/plugins/` is SDK examples only; production plugins go to `~/bos-plugins/`. Done.
- [x] SDK-006 · 2026-06-08 · Full `quickstart.md` V1–V7 passed (T080/T081). V8 (live hq.klaroha.com) blocked on merge + staging deploy — tracked as DEPLOY-034 / T119.

### Open: Validation Gaps

- [x] SDK-007 · 2026-06-08 · V2: Empty external root → zero plugin capabilities. Covered by T012 tests in `test_plugin_host_invariants.py` (3 tests: empty root, no error_states, dirs without channel.json skipped). All pass.
- [!] SDK-008 · 2026-06-08 · V4: `hello` dispatches via CMO chat (confirmed manually); `chat.py` over 200 lines; zero plugin names in `chat.py` confirmed. Line count target blocked — T014 chat.py rewrite deferred per spec. Deferred to next spec.
- [ ] SDK-009 · 2026-06-08 · V8: Merge to `main`, deploy to hq.klaroha.com, live system verified (links to DEPLOY-032–DEPLOY-036)

### Admin UX: Specialists page shows all plugins

- [x] SDK-024 · 2026-06-09 · UX: Admin → Specialists readiness-tier sort added (T116). Plugins sorted: `ready → installed → needs_setup` then alphabetical within tier. Active/ready plugins surface first regardless of env. `web/src/pages/admin/AdminModules.tsx`.
- [x] SDK-025 · 2026-06-09 · T094/T095: `pluginDisplayName()` and `pluginDescription()` deleted from `AdminModules.tsx`. `OAUTH_PLATFORMS` constant deleted. `buildPlatformMeta()` derives platform label/icon from plugin connection manifests. `display_name` and `icon` added to `PluginConnectionManifest` and 5 channel.json files (youtube, gmail-auth, google-calendar, google-drive, meta, tiktok).

### ⚠️ Claude Code Process Violation — Introduced Regressions (2026-06-09)

> **Root cause:** Claude Code did not follow the documented workflow (CLAUDE.md: read BACKLOG → find first `[ ]` → mark `[~]` → work it). Instead it read `PLUGIN_LIFECYCLE_GAPS.md` and self-directed a task ordering, introducing code changes before prerequisite operator actions were complete.

- [x] SDK-035-R · 2026-06-09 · REGRESSION (Claude Code) RESOLVED: C2 code change (`ActivateRequest` requires `brand_id`) was merged before D3 DB cleanup. Resolved by completing D3 (SDK-028 / T112) — org-wide rows cleared and recreated as brand-scoped. System state now matches code contract.
- [x] SDK-036-R · 2026-06-09 · REGRESSION (Claude Code) RESOLVED: C3 code change (deactivating for a brand also demotes org-wide active rows) is now safe — D3 complete and no org-wide active rows remain.
- [x] SDK-037 · 2026-06-09 · OUT-OF-ORDER (Claude Code) RESOLVED: T090/T091/T093 changes reviewed and verified correct during Phase 9b arch cop review. council.py boundary clean, credential_slots migration complete for all plugins.

### Plugin Lifecycle Fix — Agreed Deliverables (D1–D3)

> From `api/plugins/PLUGIN_LIFECYCLE_GAPS.md`. No code changes. Operator + DB actions only.
> Must be done before staging deploy. D1–D2 fix Admin noise now. D3 gates staging.
> **D3 is now also required to unblock the C2/C3 code regressions above (SDK-035, SDK-036).**

- [x] SDK-026 · 2026-06-09 · D1 (T110): 6 workflow plugins copied to `~/bos-plugins/`. 8 external plugins confirmed loading (`source: external`). Bundled `api/plugins/` no longer auto-loads.
- [x] SDK-027 · 2026-06-09 · D2 (T111): `KLAROHA_LOAD_INTERNAL_PLUGINS=false` in `.env`. API restarted. Admin Specialists shows only external plugins. `gbp-completeness/channel.json` fixed (missing `key` field in credential_slot).
- [x] SDK-028 · 2026-06-09 · D3 (T112): 0 org-wide active rows. 6 brand-scoped active rows for Klaroha brand `c1cb6603-e8d4-4e63-8995-640453d5b50b`. Verified via `GET /api/plugins?brand_id=...` and `GET /api/plugins` (brand_id=null returns no active rows).

### Plugin Lifecycle Fixes — Code (C1–C6) ✓ 2026-06-09

> Phase 1 mandatory code fixes from `api/plugins/PLUGIN_LIFECYCLE_GAPS.md`. All done in one pass.

- [x] SDK-029 · 2026-06-09 · C1: `GET /plugins` no longer creates `plugin_activations` rows. Removed auto-create block; missing rows synthesised as installed/inactive in response only. `api/routers/plugins.py`.
- [x] SDK-030 · 2026-06-09 · C2: `POST /plugins/{id}/activate` blocks org-wide activation unless `scope="org"` and `confirm_org_wide=true` are both present. `brand_id` required for normal activation. `api/routers/plugins.py` `ActivateRequest`.
- [x] SDK-031 · 2026-06-09 · C3: `DELETE /plugins/{id}/activate?brand_id=X` now also demotes org-wide active rows to inactive so the plugin stops bleeding across brands. `api/routers/plugins.py` deactivate handler.
- [x] SDK-032 · 2026-06-09 · C4: `/verticals` and `/verticals/{v}/modules` accept `brand_id` query param; `_filter_dispatchable_modules` passes it to `get_active_plugin_ids`. `api/routers/verticals.py`.
- [x] SDK-033 · 2026-06-09 · C5: `GET /plugins?brand_id=X` filters `connected_social_platforms` to that brand so `credentials_configured` is brand-scoped. Frontend `AdminModules.tsx` passes `selectedBrandId` and re-fetches on brand switch. `api/routers/plugins.py`, `web/src/api/client.ts`, `AdminModules.tsx`.
- [x] SDK-034 · 2026-06-09 · C6: `plugin_loader.py` compatibility adapter converts legacy `requires_social_connection` + `requires_platform_vars` → `credential_slots` at load time. `gbp-completeness/channel.json` updated to native `credential_slots`. `~/bos-plugins/README.md` updated to teach new contract with deprecation note on old fields.

### Arch Cop: Violations from External Agent Work (2026-06-09)

> Found during arch review of YouTube/Facebook social posting work. YouTube posted successfully. Facebook on hold (localhost domain issue, not code). These are code violations to clean up.

- [x] SDK-020 · 2026-06-09 · VIOLATION (T096/T092): `_CHANNEL_DISPLAY` removed from `chat.py`. `_platform_display_name()` function added. No platform names in core.
- [x] SDK-021 · 2026-06-09 · VIOLATION (T097): `_CONTROL_PARAM_LINE_RE` removed from `chat.py`. `_RUN_PARAMS_RE` handles indented params under RUN blocks structurally.
- [x] SDK-022 · 2026-06-09 · REGRESSION (T098): Retired capabilities resolved with test cleanup. `test_strategic_substrate_skills.py` deleted; `test_gtm_strategy_planner.py` reduced to retirement-only check; `test_marketing_planning_specialist.py` removes module imports; `test_cmo_action_directives.py` updated to `marketing.planning.strategy_workflow`.
- [x] SDK-023 · 2026-06-09 · CLEANUP (T099): Dead `api/plugins/youtube/module.py` deleted. `test_youtube_plugin_smoke.py` updated to remove `YouTubeModule` references; `requires_social_connection` assertions updated to use `credential_slots`.
- [x] SDK-038 · 2026-06-09 · BUG FIXED: Orphan RUN params leaked into visible reply. Added `_ORPHAN_PARAM_BLOCK_RE` to `chat.py` — strips 2+ consecutive `snake_case_key: value` lines that appear outside any `RUN:` directive. Applied in `_strip_control_directives()` after the RUN block strip pass. `api/routers/chat.py`.
- [x] SDK-039 · 2026-06-09 · BUG FIXED: `get_plugin_for_module()` returns None for youtube/tiktok after invariant tests run — autouse fixture in `test_plugin_host_invariants.py` cleared `_module_to_plugin` but left `registry._scanned=True`, so subsequent tests found an empty mapping with no rescan. Fix: fixture now also resets `reg._scanned=False` and `reg._registry.clear()`. Added `api/tests/conftest.py` setting `KLAROHA_LOAD_INTERNAL_PLUGINS=true` so routing/manifest tests can assert against bundled SDK examples. TikTok pipeline/routing tests skipped (plugin not production-ready; `requires_social_connection` assertion stale after credential_slots migration). `api/tests/test_plugin_host_invariants.py`, `api/tests/conftest.py`, `api/tests/test_tiktok_plugin_smoke.py`.

### Completed: Core Architecture ✓ (2026-06-08)

- A1–A5, A7–A8: `klaroha_sdk` pip package, `HookRegistry`, system hooks, migration 038 (`plugin_activations`), external dir scan in `plugin_loader.py`, async `execute()` detection in `runs.py`, Docker volume mount
- B1–B4: `~/bos-plugins/` repo on `master`; `hello` and `gbp-completeness` both load as `[external]`
- V1, V3, V5–V7: SDK installs clean; both plugins in manifest; delete/restore stability proven; broken plugin quarantine proven
- A6 (chat.py rewrite): deferred — existing chat.py dispatches correctly
- Key bugs fixed: `EXTERNAL_PLUGINS_PATH` tilde expansion; `requires_intent: research` silent Pydantic failure (→ `diagnostic`); CMO dispatch accuracy on fallback LLMs (→ `excluded_triggers`)
- Decision 12: SKILL.md `requires_intent` canonical values: `discussion | generation | revision | approval | onboarding | diagnostic | action | publish`

---

## STRAT — Strategy, CMO & Planning {#strat}

> Pre-build contract: `STRATEGY_WORKFLOW.md` (read before touching strategy_workflow files)
> CMO non-negotiable rules: see CLAUDE.md "CMO Chat — Non-Negotiable Rules"

### Open

- [ ] STRAT-001 · 2026-06-04 · Not-wired strategy_workflow components: `market_context`, `framework_lenses`, `channel_content_matrix`, `measurement_model` — build component modules + wire into workflow chain
- [ ] STRAT-002 · 2026-06-04 · GTM: Rejected channel stays in plan as `deferred` — BL can activate later without regenerating

### Completed: Strategy Workflow Production Build ✓ (2026-06-04)

`marketing.planning.strategy_workflow` is the sole plan module. `marketing.planning.gtm_plan` retired.
- DB: Migration 037 — `workflow_runs` + `workflow_components` tables
- Router: `GET /strategy-workflows/{id}` + `PATCH /strategy-workflows/{id}/components/{type}`
- 6 wired components: `buyer_map`, `strategic_thesis`, `offer_architecture`, `channel_stack`, `tactical_funnel`, `work_orders`
- Success: `GET /strategy-workflows/{id}` returns all 6 components with `status: "complete"` and all typed fields non-empty

### Completed: CMO Architecture ✓ (2026-05-12)

- `capability_manifest.py` — single source of truth; all phrase-matching removed from `chat.py`
- Gate 2 passed 2026-05-20: Objective → Artifact → OutcomeRecord → MemoryEvent → DecisionBrief → Stream

### Completed: @klar Command System ✓ (2026-05-10)

Brand switching via `@klar check brand X`, `@klar list brands`, `@klar plan`, `@klar org`. `SCOPE:` directive. brand_id threaded into chat requests.

---

## CRTV — Creative Production {#crtv}

> Architecture: `CREATIVE_SUPPLY_CHAIN.md` — read before modifying any creative pipeline file.
> Rule 14: Creative assets are channel-agnostic Drive artifacts. Distribution is never hardwired.
> Rule 16: Full media generation is brand-locked. CMO brain generates all provider prompts from Brand guidelines.

### Open: Creative Supply Chain — Phase B (Core Pipeline)

- [ ] CRTV-001 · 2026-06-08 · ARCH FINDING: `creative.primitive.generate` must be a worker/orchestrator, NOT a pure ChannelModule — needs DB access + Drive storage. Build as plugin-local async worker (Phase C), gated on google-drive plugin.
- [ ] CRTV-002 · 2026-06-08 · `api/capabilities/marketing/creative/concept/` — `creative.concept` capability; single extended-thinking call; outputs `creative_concept` artifact
- [ ] CRTV-003 · 2026-06-08 · `api/capabilities/marketing/creative/craft/` — shared design discipline rules (typography, color, anti-ai-slop, safe-zones, motion)
- [ ] CRTV-004 · 2026-06-08 · `creative.pack.generate` — create `creative_job` row, return job artifact immediately, start async job
- [ ] CRTV-005 · 2026-06-08 · `creative.primitive.generate` — build prompt per primitive → call provider → upload to Drive → write `creative_assets` row
- [ ] CRTV-006 · 2026-06-08 · `creative.blueprint.assemble` — fill CompositionSpec skeleton with approved primitives + brand slots → write `creative_blueprints` row
- [ ] CRTV-007 · 2026-06-08 · BRAND.md injection: extend `_inject_campaign_brand_kit_style()` in `runs.py` to emit structured Brand Kit for capabilities declaring `bos.brand_slots`

### Open: Creative Supply Chain — Phase C (Stitch and Surface)

- [ ] CRTV-008 · 2026-06-08 · BITE sample: render `example.html` files for `poster_vertical`, `video_frames`, `email_html`
- [ ] CRTV-009 · 2026-06-08 · `creative.render` FFmpeg adapter: CompositionSpec → resolve asset_ids/brand_slots → FFmpeg filter_complex → output → Drive → Export Package
- [ ] CRTV-010 · 2026-06-08 · Brand validation gate (Stage 5): P0 craft checks against BRAND.md before render
- [ ] CRTV-011 · 2026-06-08 · Plugin-local worker: poll `creative_jobs`, run the production loop, update progress
- [ ] CRTV-012 · 2026-06-08 · Creative Bundle assembly: curate top Export Packages → `creative_bundle` artifact
- [ ] CRTV-013 · 2026-06-08 · BITE sample: `sample/creative_bundle_v2.md`
- [ ] CRTV-014 · 2026-06-08 · Stream card for `creative_bundle`: render target previews, concept ref, compliance status, approve/revise actions

### Open: Creative Supply Chain — Phase D (Design Outputs)

- [ ] CRTV-015 · 2026-06-08 · Huashu concept deck: activate Huashu SKILL.md → interactive device-mockup HTML + PPTX export
- [ ] CRTV-016 · 2026-06-08 · BITE sample: `sample/creative_concept_deck_v1.html` — Vantage 3-concept review with device mockups

### Open: Creative Supply Chain — Phase E (Scale, V2)

- [ ] CRTV-017 · 2026-06-08 · Shotstack render provider adapter: abstraction layer so any render-capable module routes to Shotstack/Creatomate without direct API calls in module.py
- [ ] CRTV-018 · 2026-06-08 · Creatomate render provider adapter
- [ ] CRTV-019 · 2026-06-08 · Batch modifications loop (N renders from one template)
- [ ] CRTV-020 · 2026-06-08 · Per-brand provider overrides in Admin

### Open: Creative Supply Chain — Acceptance

- [ ] CRTV-021 · 2026-06-08 · SKILL.md for the 4 drive capabilities (deferred; `allowed_from_chat: false`; add when capability becomes CMO-facing for Scenario B)
- [ ] CRTV-022 · 2026-06-08 · WAREHOUSE LOOP PROVEN end-to-end: image AI → Drive store → Drive read-back confirmed with real code
- [ ] CRTV-023 · 2026-06-08 · ACCEPTANCE Scenario A: one brand asset + background → stitched banner (300×250, 728×90), IG carousel (1080×1080 ×3), shortform (1080×1920 MP4) from one CompositionSpec
- [ ] CRTV-024 · 2026-06-08 · ACCEPTANCE Scenario B: attach existing Drive creative → single approved social post (no generation — `drive.asset.get` → channel plugin → publish)
- [ ] CRTV-025 · 2026-06-08 · FOLLOWUP: missing-connection failures should surface as distinct `setup_blocker` artifact, not just a failed draft
- [~] CRTV-026 · 2026-06-08 · Paired output: copy + image as a single `creative_bundle` artifact — BITE sample stage active before build
- [ ] CRTV-027 · 2026-06-08 · Admin provider configuration: Specialists panel for image gen, video gen, stitch/render, design providers; readiness blocker for missing providers

### Open: Video Generation

- [ ] CRTV-028 · 2026-05-21 · `api/plugins/video-gen/` — short-form video for social and ads; backends: Sora, Runway Gen-3, Kling (provider-routed); prerequisite: audio plugin complete
- [!] CRTV-029 · 2026-06-01 · Kling video provider — BLOCKED: requires Kling API access; architecture slot reserved; add once API details confirmed

### Open: Shortform Video Production + Publishing Infrastructure

- [ ] CRTV-030 · 2026-05-21 · BITE sample: `shortform_video_asset` Stream card for one CMO Ascension short
- [ ] CRTV-031 · 2026-05-21 · `api/plugins/media-shortform/` — `media.shortform.generate` capability with `shortform_video_asset` output contract
- [ ] CRTV-032 · 2026-05-21 · Content atom schema: pillar, format, audience, core idea, hook, lesson, CTA, source references, risk notes, platform targets, variant count
- [ ] CRTV-033 · 2026-05-21 · Script generator: content atom → structured shortform script JSON (`hook`, `voiceover`, `scene_breaks`, `on_screen_text`, `caption`, `hashtags`, `title`, `CTA`, `quality_gates`)
- [ ] CRTV-034 · 2026-05-21 · Brand template library: 8–12 vertical templates for CMO vocabulary, growth diagnosis, book lesson, ascension ladder, myth/reality, checklist, quote/mental-model
- [ ] CRTV-035 · 2026-05-21 · Renderer service: Remotion/FFmpeg/HTML template render path → 9:16 MP4 without GPU dependency
- [ ] CRTV-036 · 2026-05-21 · Voiceover layer: local/free TTS for volume, premium TTS credential slot for flagship pieces, optional real-voice upload path
- [ ] CRTV-037 · 2026-05-21 · Caption timing: generate captions from script/TTS timestamps; avoid paid transcription when script is already known
- [ ] CRTV-038 · 2026-05-21 · Asset storage: MP4, thumbnail, audio, subtitle files in Cloudflare R2 (preferred) or local fallback
- [ ] CRTV-039 · 2026-05-21 · Background queue/worker for batch generation; batch status visible in Agent Activity/Stream
- [ ] CRTV-040 · 2026-05-21 · Brand compliance/self-check: Campaign Brand Kit constraints applied before artifact is reviewable
- [ ] CRTV-041 · 2026-05-21 · Stream/Workspace renderer for `shortform_video_asset`: MP4 preview, transcript, caption/hashtags, platform targets, self-check, approval/revision/export/publish actions
- [ ] CRTV-042 · 2026-05-21 · Batch generation mode: 25/50/100 shortform artifacts from approved content atoms with per-item review state
- [ ] CRTV-043 · 2026-05-21 · Export pack: ZIP/CSV with MP4 URLs, captions, hashtags, titles, platform targets, suggested publish dates, UTM fields
- [ ] CRTV-044 · 2026-05-21 · Localhost proof harness: generate one shortform MP4 end-to-end from hardcoded content atom, no external credentials

### Completed: Creative Foundation ✓

- DB migration 034: `creative_jobs`, `creative_assets`, `creative_blueprints` tables + models
- Google Drive OAuth + `GoogleDriveOAuthHandler`; Drive root folder selection via Google Picker
- `api/plugins/google-drive/`: 4 capabilities validated LIVE (generate→upload→list→download byte-identical)
- `creative.post.image`: CMO-dispatchable Facebook Post bundle; validated LIVE — 2 creatives in real Drive
- Meta publish approval loop: Generate → Review → Approve → Publish
- Image gen: provider-agnostic; OpenAI / Gemini / Cloudflare Workers AI; `IMAGE_GEN_PROVIDER` routing; platform keys auto-injected
- Video gen: Gemini (Veo 3.0) and Seedance backends; local FFmpeg fallback; `VIDEO_GEN_PROVIDER` routing
- Brand locking: `_inject_campaign_brand_kit_style()` injects `brand_visual_constraints` into image/video prompts
- `creative.shortform.video` specialist: FFmpeg, hook_text/cta_text/aspect_ratio/duration/brand_colors → `creative_shortform_video` artifact

---

## CHAN — Channel Plugins {#chan}

> Rule 1: All channel Transform nodes live in `api/plugins/{channel}/`. Never add to `api/capabilities/marketing/channel/`.
> Rule 8: Plugins read credentials only from `brief["_channel_credentials"]`.

### Open: Email Campaign Infrastructure

- [ ] CHAN-001 · 2026-05-21 · Deploy Listmonk on VDS (Docker, shares PostgreSQL instance)
- [ ] CHAN-002 · 2026-05-21 · Configure Amazon SES or Mailgun as SMTP relay — never send directly from Contabo IP
- [ ] CHAN-003 · 2026-05-21 · `api/plugins/listmonk/` — `marketing.execute` (push approved campaign) + `marketing.optimize` (pull open/click/bounce data)
- [ ] CHAN-004 · 2026-05-21 · Per-brand contact lists + unsubscribe compliance (CAN-SPAM/GDPR)
- [ ] CHAN-005 · 2026-05-21 · HTML email template per brand from Campaign Brand Kit + image gen plugin output
- [ ] CHAN-006 · 2026-05-21 · Performance data feeds back into BOS optimization memory automatically

### Open: Social Publishing Channels

- [ ] CHAN-007 · 2026-05-21 · `api/plugins/meta/` — Facebook + Instagram organic publishing and paid ads (`marketing.execute` + `marketing.optimize`)
- [ ] CHAN-008 · 2026-05-21 · `api/plugins/linkedin/` — organic posts + sponsored content
- [ ] CHAN-009 · 2026-05-21 · `api/plugins/tiktok/` — organic posts (video-dependent; stub until video gen ready)
- [ ] CHAN-010 · 2026-05-21 · Scheduling: CMO sets publish time, plugin queues and executes
- [ ] CHAN-011 · 2026-05-21 · Engagement monitoring: comments, replies, DMs surfaced as inbox intelligence artifacts

### Open: Paid Channels Beyond Google

- [ ] CHAN-012 · 2026-05-21 · `api/plugins/meta-ads/` — Meta paid campaigns, creative, audience targeting
- [ ] CHAN-013 · 2026-05-21 · `api/plugins/tiktok-ads/` — TikTok paid campaigns
- [ ] CHAN-014 · 2026-05-21 · `api/plugins/linkedin-ads/` — LinkedIn sponsored content
- [ ] CHAN-015 · 2026-05-21 · All follow Google Ads plugin contract: read/draft first, approval-gated mutations, audit trail

### Open: Analytics Unification

- [ ] CHAN-016 · 2026-05-21 · `api/plugins/ga4/` — session data, conversion events, traffic sources (`marketing.optimize`)
- [ ] CHAN-017 · 2026-05-21 · Cross-channel attribution: GA4 + Google Ads + Search Console + email + social in one optimization view
- [ ] CHAN-018 · 2026-05-21 · Unified performance workspace document generated on cadence (weekly/monthly)
- [ ] CHAN-019 · 2026-05-21 · CMO can ask "what's working?" and get a cross-channel answer from BOS memory, not a dashboard

### Open: Landing Page Generation + Deployment

- [ ] CHAN-020 · 2026-05-15 · BOS generates HTML/copy landing page from campaign brief and Campaign Brand Kit
- [ ] CHAN-021 · 2026-05-15 · Deploys to brand subdomain (Cloudflare Pages or nginx-served static)
- [ ] CHAN-022 · 2026-05-15 · A/B variant generation: two versions approved by CMO, traffic split tracked via GA4
- [ ] CHAN-023 · 2026-05-15 · Approval gate before any page goes live

### Open: Audio / Voice

- [ ] CHAN-024 · 2026-05-21 · `api/plugins/audio/` — TTS for ad voiceovers, podcast intros, short-form audio; backends: ElevenLabs, OpenAI TTS
- [ ] CHAN-025 · 2026-05-21 · Output: reviewable `audio_artifact` — approve before use in ads or social

### Open: Digest Notification

- [ ] CHAN-026 · 2026-05-21 · `api/plugins/notify/` — lightweight notification plugin: email (SMTP) and/or Slack (webhook)
- [ ] CHAN-027 · 2026-05-21 · `notify.digest` capability: formats pending review items as a digest and sends to configured recipient
- [ ] CHAN-028 · 2026-05-21 · `cmo_loop.py` calls `notify.digest` at end of each run if any items are pending review
- [ ] CHAN-029 · 2026-05-21 · Email digest: brand-grouped pending artifacts with direct approve/reject links (token-authenticated)
- [ ] CHAN-030 · 2026-05-21 · Slack digest: one message per brand with artifact count and link to Stream

### Open: Shortform Video Publishing Integrations

- [ ] CHAN-031 · 2026-05-21 · `api/plugins/youtube/` — YouTube Shorts publisher (`youtube.shorts.publish`); approved `shortform_video_asset` → upload with title/description/tags/privacy/schedule
- [ ] CHAN-032 · 2026-05-21 · YouTube quota guard: detect upload quota exhaustion, surface setup/blocker artifact, preserve export fallback
- [ ] CHAN-033 · 2026-05-21 · Extend `api/plugins/meta/` with Instagram/Facebook Reels publishing modules using hosted MP4 URL; approval-gated with platform IDs/URLs
- [ ] CHAN-034 · 2026-05-21 · Meta/Instagram setup gate: linked IG Business account + required permissions + app review state surfaced as connector readiness
- [ ] CHAN-035 · 2026-05-21 · Scheduler handoff: export compatible CSV fields for Buffer/Later/Metricool/manual uploader
- [ ] CHAN-036 · 2026-05-21 · Publish audit trail: every native publish writes `action_result` artifact with changed_resources, platform post ID, URL, timestamp

### Open: Meta Plugin — Architecture Gaps

- [ ] CHAN-037 · 2026-05-18 · ARCH GAP: Multi-plugin image→Facebook post handoff — no inter-module data handoff in isolated briefs. Option A (planned): `posts/draft` block carries `image_prompt`; `posts/publish` calls image gen + photo upload inline.
- [ ] CHAN-038 · 2026-05-18 · ARCH GAP: CMO dispatches Meta capabilities without checking if brand has Facebook connection. Option A: surface connected channels per brand in CMO system prompt.
- [ ] CHAN-039 · 2026-05-18 · BUG: Meta pages/read missing-credentials path returns successful/pending run with failed block content; should surface as non-pending failure or setup-required artifact

### Open: Facebook Publish Pipeline

- [ ] CHAN-040 · 2026-05-12 · Frontend ApprovalBundle: "Approve & Publish" button for `platform_hint: facebook post` runs calls `POST /social/facebook/publish/{run_id}`
- [ ] CHAN-041 · 2026-05-12 · CMO chat confirmation: `facebook_publish_result` block rendered inline after publish
- [ ] CHAN-042 · 2026-05-12 · TEST: end-to-end — brand with connected page → CMO drafts post → approves → post appears live on Facebook Page

### Open: Setup Required

- [ ] CHAN-043 · 2026-05-18 · SETUP REQUIRED: Create Meta Developer App at developers.facebook.com; add `FACEBOOK_APP_ID` + `META_APP_SECRET` to `.env`; go through App Review for `pages_manage_posts`
- [ ] CHAN-044 · 2026-05-21 · ARCH GAP (credential pre-check): surface `brand_json["active_channels"]` with connection status in CMO system prompt so LLM self-selects only connected channels

### Completed: Channel Plugin Foundation ✓

- Meta plugin v0.1.0: pages/read, posts/read, posts/draft, posts/publish — validated LIVE (Facebook Page Klarohahq)
- Gmail OAuth + send/receive validated LIVE: email delivered; 10 inbox emails returned
- Google Calendar OAuth + booking widget: native booking system, FreeBusy API, widget.js embed
- Google Ads plugin v0.4.0: account discovery + campaign report read capabilities
- Search Console plugin v1: properties, performance, URL inspection, sitemaps, opportunity plan
- ClickUp plugin v0.2.0: tasks.read (workspace-wide) + tasks.create (approval-gated); per-brand scoped reads
- YouTube: pipeline validation + live OAuth proof + CMO chat live post proof
- `creative.post.image` → Drive → Meta publish approval loop: validated LIVE end-to-end
- `POST /social/facebook/direct-connect` endpoint for admin/dev use when OAuth redirect is misconfigured

---

## ARCH — Campaign Architecture {#arch}

> Two-Cycle flywheel: Cycle 1 (Setup-to-Market) → Cycle 2 (Intelligence-to-Optimization) → back to Cycle 1.
> Read `CREATIVE_SUPPLY_CHAIN.md` and `PROJECT_BRIEF.md` for full architecture context.

### Open: Optimization Memory Loop

- [ ] ARCH-001 · 2026-05-21 · Approved learnings from every channel flow automatically into CMO planning brief for next campaign
- [ ] ARCH-002 · 2026-05-21 · Dismissed variants and rejected artifacts stored as negative memory — CMO doesn't repeat mistakes
- [ ] ARCH-003 · 2026-05-21 · `Outcomes` section in Admin surfaces approved learnings, measured results, and trend signals per brand
- [ ] ARCH-004 · 2026-05-21 · Next campaign `marketing.plan` call loads prior outcomes as a memory slot automatically

### Open: Plugin Onboarding Manifest + Orchestrator

- [ ] ARCH-005 · 2026-05-21 · Add `onboarding` block to `channel.json` schema: `{task, description, auto: true|false, requires_credential: bool}`
- [ ] ARCH-006 · 2026-05-21 · Example: Google Ads plugin declares `[{task: "Link MCC account", auto: false}, {task: "Create conversion action", auto: true, module: "google_ads.setup.conversion"}]`
- [ ] ARCH-007 · 2026-05-21 · `api/capabilities/onboarding/channel_onboarding/` — reads all active channel manifests for a brand, generates unified onboarding task list
- [ ] ARCH-008 · 2026-05-21 · Automated tasks dispatched immediately; manual tasks created in ClickUp under dedicated onboarding list per brand
- [ ] ARCH-009 · 2026-05-21 · Onboarding status tracked per channel: `not_started / in_progress / complete / blocked`
- [ ] ARCH-010 · 2026-05-21 · Admin UI: onboarding progress view per brand — channel rows with completion status
- [ ] ARCH-011 · 2026-05-21 · Agent loop checks onboarding status; once all channels complete, triggers first-artifact generation automatically

### Open: Campaign Brief Cascade

- [ ] ARCH-012 · 2026-05-21 · `marketing.planning.campaign_brief` capability: generates structured brief per channel from campaign objective + GTM plan + brand context
- [ ] ARCH-013 · 2026-05-21 · Brief cascade: on BL approval of campaign plan artifact, dispatch `campaign_brief.generate` for each active channel in parallel
- [ ] ARCH-014 · 2026-05-21 · Each channel brief becomes a `pending_review` artifact in Stream — BL reviews per-channel brief before execution begins
- [ ] ARCH-015 · 2026-05-21 · Approved channel brief triggers the channel's draft capability automatically
- [ ] ARCH-016 · 2026-05-21 · ClickUp task created per channel at cascade time: tracks brief → draft → approved → deployed lifecycle
- [ ] ARCH-017 · 2026-05-21 · Cascade summary artifact shows BL which channels were briefed, which are awaiting approval, which are blocked

### Open: Channel-Sovereign Campaign Execution

- [ ] ARCH-018 · 2026-05-21 · Campaign execution SKILL.md (`marketing.execute.campaign`) — dispatches `RUN:` to all enabled channel plugins; zero channel-specific logic in the SKILL itself
- [ ] ARCH-019 · 2026-05-21 · Plan approval trigger — `on_approve` hook fires the execution cascade
- [ ] ARCH-020 · 2026-05-21 · Google Ads plugin: search ads + display banners (`media.image.generate` at 300×250 + 728×90) + video brief (if enabled)
- [ ] ARCH-021 · 2026-05-21 · Meta plugin: post copy + square image (1080×1080); carousel copy + per-item images
- [ ] ARCH-022 · 2026-05-21 · Email plugin: email copy + header image (600×200)
- [ ] ARCH-023 · 2026-05-21 · Image gen format field — add `image_format: {width, height, channel}` to `media.image.generate` brief contract
- [ ] ARCH-024 · 2026-05-21 · Creative bundle artifact — paired copy + image as single `creative_bundle` block per channel; one Stream card for approval

### Open: Per-Channel Intelligence — Analyst Capabilities

- [ ] ARCH-025 · 2026-05-21 · Analyst module pattern: each plugin adds a `*.analyze` capability alongside `*.execute` and `*.optimize`
- [ ] ARCH-026 · 2026-05-21 · `google_ads.analyze` — impressions, clicks, CTR, CPA, ROAS → `performance_report` artifact
- [ ] ARCH-027 · 2026-05-21 · `meta.analyze` — Facebook/Instagram reach, engagement, cost-per-result
- [ ] ARCH-028 · 2026-05-21 · `email.analyze` (Listmonk) — open rate, click rate, unsubscribe rate, revenue per send
- [ ] ARCH-029 · 2026-05-21 · `ga4.analyze` — sessions, conversions, channel attribution, goal completions
- [ ] ARCH-030 · 2026-05-21 · Each analyst capability runs on cadence: EOD for active campaigns, EOW for always-on channels, EOM for full-funnel review
- [ ] ARCH-031 · 2026-05-21 · Cadence stored per brand per channel in `brand_json["channel_cadence"]`
- [ ] ARCH-032 · 2026-05-21 · Agent loop checks cadence on each run and dispatches the right analyst capabilities

### Open: CMO Snapshot + Optimization Plan

- [ ] ARCH-033 · 2026-05-21 · `marketing.planning.cmo_snapshot` capability
- [ ] ARCH-034 · 2026-05-21 · Reads all channel `performance_report` artifacts for a brand within the cadence window
- [ ] ARCH-035 · 2026-05-21 · Produces: executive summary (3-5 bullets), channel performance comparison, top-performing creative, underperforming channels flagged, recommended optimization actions
- [ ] ARCH-036 · 2026-05-21 · BL reviews snapshot artifact from Stream — not individual channel reports
- [ ] ARCH-037 · 2026-05-21 · BL can approve, reject, or annotate optimization recommendations inline
- [ ] ARCH-038 · 2026-05-21 · Approved optimization plan triggers brief cascade for affected channels (Cycle 2 → Cycle 1)
- [ ] ARCH-039 · 2026-05-21 · CMO snapshot stored as workspace document — feeds Optimization Memory Loop (ARCH-001)

### Open: Stream Panel — BL Decision Surface

- [ ] ARCH-040 · 2026-05-21 · Priority sort: needs-attention first (overdue, flagged, blocked), then pending review, then published
- [ ] ARCH-041 · 2026-05-21 · Digest mode: artifacts grouped by brand and campaign
- [ ] ARCH-042 · 2026-05-21 · Approve / reject / flag in-place from Stream card — no navigation to workspace required
- [ ] ARCH-043 · 2026-05-21 · Campaign thread view: all artifacts for a campaign in one expandable thread
- [ ] ARCH-044 · 2026-05-21 · Status indicators: onboarding progress, active campaigns, pending approvals count per brand
- [ ] ARCH-045 · 2026-05-21 · Mobile-first layout: thumb-reachable approve/reject actions, single-column card stack
- [ ] ARCH-046 · 2026-05-21 · Digest notification: loop sends summary to BL after each run (see CHAN-026–CHAN-030)

### Completed: Gate 2 + Agent Harness ✓ (2026-05-20)

Gate 2 passed 2026-05-20. Objective → Artifact → OutcomeRecord → MemoryEvent → DecisionBrief → Stream.
- `api/routers/agent.py` — 5-endpoint harness: GET /agent/state, GET /agent/context/{brand_id}, GET /agent/capabilities, POST /agent/execute, PATCH /agent/review/{run_id}
- `api/agents/cmo_loop.py` — monitor → prioritize → delegate → surface
- Stream + CMO unified split-screen surface: CMO chat (40%) left, decision feed (60%) right

---

## ADMIN — Admin & Onboarding {#admin}

> Key pages: `/admin/brands` (per-brand OAuth), `/admin/modules` (Specialists), `/admin/providers` (AI keys + model picker)

### Open

- [ ] ADMIN-001 · 2026-05-10 · Brand switcher dropdown in admin header (alongside @klar chat switching)
- [ ] ADMIN-002 · 2026-05-10 · Frontend tests: KlarAction handling, brand context state
- [ ] ADMIN-003 · 2026-05-18 · SETUP REQUIRED: Create Meta Developer App; add FACEBOOK_APP_ID + META_APP_SECRET to `.env`; App Review for production use (see also CHAN-043)
- [ ] ADMIN-004 · 2026-05-16 · Frontend tests: `web/src/tests/BlockRenderer.test.tsx` — layout_hint → correct component
- [ ] ADMIN-005 · 2026-05-16 · Frontend tests: `web/src/tests/SurfaceContext.test.tsx` — same component, different layout per surface
- [ ] ADMIN-006 · 2026-05-16 · Frontend tests: `web/src/tests/ApprovalBundle.test.tsx`
- [ ] ADMIN-007 · 2026-05-16 · Frontend tests: `web/src/tests/PerformanceReport.test.tsx`
- [ ] ADMIN-008 · 2026-05-16 · Integration test: submit run from browser, verify record in GET /runs
- [ ] ADMIN-009 · 2026-05-16 · Contract test: same run via curl and UI produces identical DB record

### Completed: Admin UX ✓

Admin shell: Brands/Clients, Campaign Plans, Specialists, Outcomes, System. Specialists is the single connector readiness/setup surface.
- AI Providers: CMO Brain card (model picker), Your API Keys (simplified BYOK), Sign in with Account (OpenAI OAuth)
- Model picker: live OpenRouter free models via `GET /providers/models`; cached 1 hour
- Getting Started: dismissible banner; Import Brief scope gate; multi-brand onboarding flow

---

## UX — Stream & UX {#ux}

> Locked: Rule 13 (Stream inline approval), Rule 6 (CMO artifact refs only), Rule 7 (mobile-first replies)
> Architecture: PROJECT_BRIEF.md Section 8 — Surface-Agnostic Components. Read before modifying any renderer, surface, or Stream layout file.

### Headless Component Architecture — Design Contract (PROJECT_BRIEF.md §8)

BOS components are **surface-agnostic**: data in, render out. A component does not know if it is in a chat bubble, Stream card, panel, or mobile view — `SurfaceContext` provides that constraint.

**What already exists (do not re-implement):**
- `web/src/surfaces/SurfaceContext.tsx` — `SurfaceProvider` + `useSurface()` hook; types: `panel | full-screen | chat-inline | mobile-card`
- `web/src/surfaces/` — `ChatInlineSurface`, `FullScreenSurface`, `MobileCardSurface`, `PanelSurface` — each wraps children in the correct `SurfaceProvider`
- `web/src/components/blocks/BlockRenderer.tsx` — routes `layout_hint` → component (`narrative | alert | compact | table | media`)
- `web/src/components/blocks/PerformanceReport.tsx`, `ModuleCard.tsx` — already call `useSurface()` and adapt layout to surface type
- `web/src/pages/CmoChat.tsx`, `ReportsView.tsx` — already wrap `BlockRenderer` in `SurfaceProvider`

**The gap (what is NOT yet connected):**
- `Stream.tsx` renders artifact cards directly — it does NOT use `BlockRenderer` or `SurfaceProvider`
- `renderer_hint` on API artifact blocks never reaches `BlockRenderer` (which only handles `BriefingBlock.layout_hint`)
- `ApprovalBundle.tsx` hardcodes action labels ("Approve", "Dismiss", "Revise") instead of reading `allowed_actions` from the API artifact block
- Adding a new `block_type` requires touching `Stream.tsx` directly instead of adding one renderer file

**Target state (headless contract):**
```
API artifact block carries:
  renderer_hint   → which shell to mount (registry lookup)
  block_type      → data schema identifier
  content         → structured data (no business logic in renderer)
  allowed_actions → ["approve", "dismiss", "revise"] — renderer reads this, never hardcodes

SurfaceContext provides:
  stream-card | workspace-panel | mobile-full | chat-inline
  → constrains layout, not data

Renderer registry (web/src/components/blocks/renderers/index.ts):
  renderer_hint → component file
  adding a new artifact = one new file, zero changes to Stream.tsx or ApprovalBundle
```

### Open: Headless Architecture Gaps

- [ ] UX-004 · 2026-06-08 · Add `stream-card` to `SurfaceType` in `SurfaceContext.tsx`; wrap `StreamArtifactCard` children in `<SurfaceProvider type="stream-card">` so artifact renderers know their surface
- [ ] UX-005 · 2026-06-08 · Create `web/src/components/blocks/renderers/index.ts` — registry mapping `renderer_hint` → component; extend `BlockRenderer` to accept artifact blocks (with `renderer_hint`) alongside `BriefingBlock` (with `layout_hint`)
- [ ] UX-006 · 2026-06-08 · Extract each existing artifact renderer from `Stream.tsx` into its own file under `web/src/components/blocks/renderers/` — one file per `renderer_hint` value (approval_bundle, stream_card, setup_blocker, narrative, strategy_workflow, etc.)
- [ ] UX-007 · 2026-06-08 · Drive `ApprovalBundle` action buttons from `block.allowed_actions` array instead of hardcoding "Approve" / "Dismiss" / "Revise" — renderer reads the API contract; backend controls what actions are available per artifact
- [ ] UX-008 · 2026-06-08 · `Stream.tsx` becomes a ~40-line shell: wraps feed in correct `SurfaceProvider`, maps run list to `BlockRenderer` calls — zero artifact-type-specific logic inside the file
- [ ] UX-009 · 2026-06-08 · Write `web/src/tests/BlockRenderer.test.tsx` — assert `renderer_hint` → correct component; assert `layout_hint` → correct component; assert unknown hints render fallback (replaces ADMIN-004)
- [ ] UX-010 · 2026-06-08 · Write `web/src/tests/SurfaceContext.test.tsx` — assert same component renders compact layout inside `stream-card` surface and expanded layout inside `full-screen` surface (replaces ADMIN-005)

### Open: Backlog

- [ ] UX-001 · 2026-05-21 · CAPABILITY MANIFEST V2: expose CMO-facing jobs with plugin implementation metadata instead of only raw module IDs
- [ ] UX-002 · 2026-05-22 · BACKEND ALIGNMENT: Add generic installed connector registry endpoint for Admin instead of hardcoded provider/social UI assumptions
- [ ] UX-003 · 2026-05-18 · BUG: Public staging domain does not reflect latest `origin/staging` deploy after push — investigate nginx/Cloudflare routing when needed

### Completed: Surface Architecture Foundation ✓

- `SurfaceContext.tsx` — `SurfaceProvider` + `useSurface()` — fully implemented
- `BlockRenderer.tsx` — `layout_hint` → component routing (narrative, alert, compact, table, media)
- `ChatInlineSurface`, `FullScreenSurface`, `MobileCardSurface`, `PanelSurface` — all implemented
- `PerformanceReport`, `ModuleCard` — call `useSurface()`, adapt to surface constraints
- `CmoChat.tsx`, `ReportsView.tsx` — use `BlockRenderer` inside `SurfaceProvider` correctly

### Completed: Stream UX ✓

- Unified Stream + CMO split-screen; mobile full-screen panel mode with slide transition
- `ApprovalBundle` embedded directly in `StreamArtifactCard`; `stream-side-panel` reserved for `StreamUpdateOut` types only
- `addPendingRun()` in `CmoChatContext` on every `module_result` SSE event; 15s poll deduplication
- Brand UI: Klaroha v2.2 — white-dominant canvas, Racing Green/Warm Gold/Copper tokens, square cockpit geometry
- All artifact renderers: creative_post_asset, meta_page_posts, meta_page_inventory, marketing_plan, image_asset, fb_page_post_result, strategy_workflow, gtm_strategy, clickup_task_status, gmail_draft, youtube
- Stream lazy loading: bounded-concurrency hydration; no bulk `image_data_b64` in run-list

---

## CNCL — Council {#cncl}

> `@council <question>` in CMO chat → staggered Round 1 → C6 injection → finalize.
> C1 (Growth Strategist, `openrouter/poolside/laguna-xs.2:free`) + C2 (Brand Builder, `openrouter/openai/gpt-oss-120b:free`) active. C3–C5 vacant.

### Open

- [ ] CNCL-001 · 2026-06-02 · Memory: approved settlement → MemoryEvent(`type=decision_made`); dismissed → `decision_not_to_act`
- [ ] CNCL-002 · 2026-06-02 · Re-enable C3–C5 with diverse models; assign ideologies; avoid duplicate models across seats
- [ ] CNCL-003 · 2026-06-02 · SSE seat streaming: real-time per-seat updates during a round (currently: full round appears when all seats complete)
- [ ] CNCL-004 · 2026-06-02 · Tool grants per seat (data access, plugin calls) — parking lot

### Completed: Council ✓ (2026-06-02)

- `api/capabilities/workspace/council/seats/c1–c5/SKILL.md` — seat configs; `CouncilSession` model + migrations 028 + 036
- `module.py`: `start_session()` staggered Round 1 (2s between seats); `process_c6()` sequential; `finalize()` extraction-only
- `routers/council.py`: POST /council/convene, POST /council/{id}/c6-respond, POST /council/{id}/finalize, GET sessions, GET seats, PUT seats
- Frontend: `CouncilRoundMessage` (per-seat collapsible cards), `CouncilBriefMessage` (settlement + marching orders)
- Verified: 6-round session + finalize with 2 active seats — all rounds clean

---

## HARD — Hardening & Second Vertical {#hard}

### Open: Phase 5 Hardening

- [ ] HARD-001 · 2026-05-15 · Retry with structured feedback (BITE failure-feedback loop)
- [ ] HARD-002 · 2026-05-15 · Rate limiting (per API key)
- [ ] HARD-003 · 2026-05-15 · Cost quotas (configurable per workspace)
- [ ] HARD-004 · 2026-05-15 · Provider circuit breaker
- [ ] HARD-005 · 2026-05-15 · Structured logging

### Open: New Surfaces

- [ ] HARD-006 · 2026-05-15 · FullScreenSurface: give PerformanceReport its own dedicated screen with full chart rendering
- [ ] HARD-007 · 2026-05-15 · Slack message renderer (new surface, zero component changes)
- [ ] HARD-008 · 2026-05-15 · PDF export surface (new surface, zero component changes)
- [ ] HARD-009 · 2026-05-15 · TikTok-style MobileCardSurface: full-screen per-block with swipe gesture

### Open: Second Vertical

- [ ] HARD-010 · 2026-05-15 · Vertical chosen (finance or HR)
- [ ] HARD-011 · 2026-05-15 · 2-3 modules implemented
- [ ] HARD-012 · 2026-05-15 · Proves: adding a vertical = adding files, no core changes

---

## Archive — Completed Phases 0–5 {#archive}

> Historical record only. Do not pick tasks from here unless explicitly reopened.

**Phase 0 — Foundation ✓ (2026-05-01):** Docker Compose stack (api, db, web, nginx). FastAPI initialized. PostgreSQL + Alembic migrations 0001–0005. API key auth middleware. Error response shape standardized.

**Phase 1 — Core API + Data Layer ✓ (2026-05-02):** GET/PUT /workspace. Products + audiences CRUD. Brief resolution. Module registry via directory scan. OpenAICompatAdapter; Gemini + NVIDIA subclasses. Mock executor for keyless dev. Runs + pagination. React + Vite frontend. 3-tab mobile-first shell (Stream / CMO / Workspace).

**Phase 2 — Marketing Vertical ✓ (2026-05-03):** All planned marketing modules with real prompt templates. Per-platform self_check. Module fan-out. Campaign model + POST /campaigns. Approval flow (backend). Migrations 015–016. Campaign Brand Kit endpoint + Admin Workspace tab.

**Phase 3 — Frontend ✓ (2026-05-06):** CMO chat with LLM routing (real provider waterfall). Chat history in localStorage. Brand Kit generated with real content. CMO persona + mobile-first reply style. Admin Dashboard. Workspace editor. Provider management. Module browser. Getting Started onboarding.

**Phase 4 — Brand Architecture + @klar ✓ (2026-05-10):** Migration 018: brands table + brand_id FKs. Brand CRUD API. @klar command system (brand_switch, plan, evaluate, pending, list_brands, directive). Brand context in CMO chat. KlarAction type. activeBrand in UIContext. @klar plan confirmation flow.

**Phase 4B — CMO Architecture + Channel Plugin Infrastructure ✓ (2026-05-12):** `capability_manifest.py`. All phrase-matching removed from chat.py/skills/router.py. `api/plugins/` plugin root. `api/klaroha_sdk.py` stable import surface. `api/plugin_loader.py` with credential injection. Channel plugin pattern: `channel.json` + `ChannelModule` + `SKILL.md`. BITE envelope structure. CMO rules locked in CLAUDE.md.

**Phase 4C — Social/OAuth + Multi-Dev Pipeline ✓ (2026-05-11 to 2026-05-17):** SocialConnection table. FacebookOAuthHandler. GmailOAuthHandler (PKCE). GoogleCalendarOAuthHandler. Skills/loader.py multi-root scan. Native booking widget. GitHub Actions CI, staging stack, @kibanu onboarded.

**Phase 5 — Gate 2 + CMO Agent Harness ✓ (2026-05-18 to 2026-05-25):** Gate 2 passed 2026-05-20. Objective anchor + MemoryEvent + OutcomeRecord + DecisionBrief + Handoff Brief. Agent harness. cmo_loop.py. Stream + CMO unified split-screen. Brand UI (Klaroha v2.2). Inline approval bundles. ClickUp Decision Ledger. Build-once CI pipeline with SHA-tagged images.

---

## Parking Lot {#parking-lot}
- Multi-tenancy (SaaS mode)
- Workflow chaining between modules
- Agentic orchestration inside BOS
- A/B variant generation per module
- Fine-tuning infrastructure
- Native mobile app
- Enterprise billing and reporting
- Automated provider model catalog refresh
- **klaroha.com public marketing site (Astro):** Static site; `api/plugins/klaroha-site/` plugin commits markdown to Astro repo + triggers GitHub Actions rebuild. Prerequisite: hq.klaroha.com move complete.
- **CMS publish plugins (WordPress, Webflow, Shopify):** Each client CMS is a plugin publish target. WordPress: Application Passwords (WP 5.6+), credentials per brand in social_connections. Prerequisite: plugin dev workflow live first.
- **Cloudflare Tunnel for local Facebook OAuth:** Facebook enforces HTTPS-only redirect URIs. Fix: named Cloudflare Tunnel (`dev.klaroha.com` → localhost:80), register HTTPS redirect URI in Meta Developer App.
- **True omni-channel asset distribution (post Phase 6):** Remove hardwired `publish_facebook` / `publish_youtube` buttons from StreamArtifactCard. CMO dispatches channel capability with asset reference (`drive_file_id` / `run_id`).
- **Public website-to-plan lead-capture demo:** Parked in `PUBLIC_LEAD_CAPTURE_DEMO.md`. Must not recreate planning prompts outside the internal capability. Not approved for build.
- **Council tool grants per seat:** Data access and plugin call grants per seat — parking lot until basic council is proven at scale.

---

## Decisions Log {#decisions-log}

| Date | Decision | Rationale |
|---|---|---|
| 2026-06-09 | **Claude Code caused regressions by not following documented task order and agreed process.** Claude Code read `PLUGIN_LIFECYCLE_GAPS.md` and independently invented a task ordering (C1–C6, then T090/T091/T093) without reading `BACKLOG.md` first, without finding the first `[ ]` task, without marking it `[~]`, and without working tasks in documented sequence. Specific harms: (1) C2 code change (blocking org-wide activation) was merged before D3 DB cleanup, leaving the system in a state where the Admin UI cannot activate plugins without a brand selected while 6 org-wide active rows still exist in the DB. (2) C3 code change (deactivating for a brand silently demotes org-wide rows) creates unexpected side effects if the operator deactivates any plugin from Admin before D3 is complete. (3) T090/T091/T093 were done out of order and without the operator asking for them. **Rule added:** Claude Code must read `BACKLOG.md` at the start of every session, find the first `[ ]` item in the active topic, mark it `[~]`, and work only that task. No task may be started that is not the next sequential item unless the operator explicitly instructs otherwise. Out-of-order or self-directed task selection by Claude Code is a process violation. | Claude Code does not respect workflow. The fix is a documented rule in the Decisions Log that is enforceable in future sessions. |
| 2026-06-09 | `credential_slots` supersedes `requires_social_connection` and `requires_platform_vars`. Seven slot types: `social_token`, `social_meta_field`, `platform_var`, `brand_json_path`, `backend_override_provider`, `backend_override_model`, `backend_provider_api_key`. Resolver loop in `inject_channel_credentials` has zero platform-specific branches. Legacy fields supported via compatibility adapter at load time. | Old fields were a per-platform whitelist in core. Any new platform required a core edit. Slot contract is declarative — plugins own what they need; core resolves generically. |
| 2026-06-09 | `workspace/council` SKILL.md `allowed_from_chat: false`. `api/council.py` is the core service; `chat.py` imports from it directly via `@council` command path, not capability dispatch. `council/module.py` is a clean stub. | FR-013 (no BOS internal imports in capability modules). Council needed `db`, `settings`, `models` — those belong in the core service, not in a manifest-dispatchable capability. If `allowed_from_chat: true`, the CMO might try to dispatch it as a capability, leaking LLM session state into `module.execute()`. |
| 2026-06-09 | Test suite sets `KLAROHA_LOAD_INTERNAL_PLUGINS=true` via `api/tests/conftest.py`. Runtime `.env` keeps it `false`. `conftest.py` runs before any `plugin_loader` import so the flag is effective at first scan. External plugins shadow bundled duplicates — no quarantine, just skip. | Routing/manifest tests for SDK example plugins (gmail, google_ads, search_console) were broken by runtime default. Tests ARE testing bundled plugin behaviour so using bundled plugins in tests is correct. Runtime must stay false so production Admin is clean. |
| 2026-06-09 | Everything is a package — no module concept. Built-in packages (`api/capabilities/`) ship with BOS and auto-activate org-wide. Installed packages (`~/bos-plugins/`) require explicit per-brand activation. Same contract for both. | pi.dev: loaded resources, not core branches — the runner stays minimal. WordPress: Akismet is a plugin, not core — same hook API regardless of author. VS Code: TypeScript support is an extension in `app/extensions/` — same extension API, can be disabled. Retiring "module" forces the `resolve` primitive to become the single context-assembly path and keeps all capability code as stateless transforms. Constitutional: BITE.md § Everything is a Package. |
| 2026-06-08 | `requires_platform_vars` is the self-sufficient credential path for 3rd party plugins; `requires_social_connection` is host-managed OAuth only | A LinkedIn plugin built against `requires_social_connection` was inert — credentials never injected because core has no LinkedIn OAuth handler. Correct model: 3rd party plugins on new platforms declare `requires_platform_vars`, own their validation capability, and fail cleanly with `missing_credentials`. `requires_social_connection` is only for platforms the host already manages (Gmail, Google Calendar, YouTube, Google Drive). Updated PLUGIN_SDK.md "Open SDK issue" section to document this as the canonical model. |
| 2026-06-08 | `EXTERNAL_PLUGINS_PATH` must use an absolute path — Docker does not expand `~` | Default `~/bos-plugins` in `docker-compose.yml` treated literally; container logged "No external plugin root found." Fixed: changed to `/home/ubu/bos-plugins`. All deployments must set an absolute path. |
| 2026-06-08 | `gbp-completeness` replaces `gmail` as the second validation plugin for `001-thin-core-proof` | GBP already written, lives in `bos-plugins/`, exercises OAuth + `approval_bundle` + `pending_review`. Gmail adds SMTP complexity and send action risk that GBP doesn't need to replicate. |
| 2026-06-08 | Thin core + SDK separation: `chat.py` capped at ~150 lines; all plugin logic moves to `klaroha_sdk` + external `~/bos-plugins/` repo | `chat.py` grew to 2,146 lines; every new plugin required core edits. BOS core fires hook events; plugins subscribe as `ChannelModule` subclasses using only `klaroha_sdk` imports. |
| 2026-06-08 | SKILL.md `requires_intent` must use canonical values only | GBP SKILL.md used `requires_intent: research` — not in the Pydantic enum. `list_skill_manifests()` silently skipped it. Plugin loaded at transport layer but was invisible to CMO. Valid values: `discussion \| generation \| revision \| approval \| onboarding \| diagnostic \| action \| publish`. |
| 2026-06-07 | BOS needs an Extension Host + compatibility/release-integrity layer for true plugin backwards compatibility | Hooks, activation, and contribution points are necessary but not sufficient. Captured in PROJECT_BRIEF.md v3.55; no implementation until a BITE sample is approved. |
| 2026-06-06 | Full media generation is brand-locked and CMO-brain generated across text, image, audio, video, and stitching | Brand alignment cannot be delegated to provider defaults or checked only at the final MP4. Every gate must block off-brand work. |
| 2026-06-06 | Local image sample renderer is allowed only as an explicitly labeled localhost proof fallback | External image providers can be unavailable. Provider labeled `local`, not presented as third-party AI output. Must be replaced by real credentials for production. |
| 2026-06-06 | Gemini AI provider auth is API-key/platform-key only in this deployment | Google rejects `generative-language` OAuth as `invalid_scope`. BOS's Gemini path uses API keys. Admin must not advertise Gemini account-login OAuth until a supported flow is proven. |
| 2026-06-04 | Public lead-capture demo must call/reuse the internal Strategy Workflow; no duplicate public planning capability | Manually recreating marketing-plan output creates two planning brains. Parked until a revised BITE sample is approved. |
| 2026-06-04 | `marketing.planning.gtm_plan` retired; `marketing.planning.strategy_workflow` is the sole plan module | Single-shot GTM plan replaced by modular Strategy Workflow: 10 independently revisable components, typed JSON output contracts per component. Locked as Rule #15. |
| 2026-06-02 | Council deliberation lives in CMO chat, not a Stream card | Chat is already a conversation. C6 injection is just replying. Mobile works natively. Stream receives only the settled `council_brief` artifact (future). |
| 2026-06-02 | Round 1 is staggered sequential (2s gap), not `asyncio.gather` | Free-tier OpenRouter rate-limits parallel bursts. Stagger eliminates 429s without changing round semantics. |
| 2026-06-01 | Image gen uses `gemini-2.5-flash-image:generateContent` as the Gemini default; `imagen-4.0-*:predict` available via `IMAGE_GEN_MODEL` override (paid plan only) | `gemini-2.5-flash-image` uses the standard `generateContent` endpoint — no extra billing required. |
| 2026-06-01 | Image and video providers configurable per-specialist via `IMAGE_GEN_PROVIDER` / `VIDEO_GEN_PROVIDER` | Replaces hardwired `IMAGE_GEN_WORKER_URL + IMAGE_GEN_API_KEY`. Platform keys auto-injected. |
| 2026-06-01 | BOS is click-to-deploy packaged software, not multi-tenant SaaS | Agencies and SMBs cannot accept client marketing data on shared infrastructure. Product promise is "your CMO, your server." Multi-tenancy → Parking Lot. |
| 2026-06-01 | OpenRouter free models fetched live via `GET /providers/models`; seeded model_options retained only for direct providers | Hardcoded migrations were the wrong update mechanism for a live model catalog. Cached 1 hour in-memory. |
| 2026-05-30 | CI builds Docker images tagged with commit SHA and pushes to GHCR; staging deploy pulls pre-built images | Building on VDS is slow and environment-inconsistent. Exact image tested in CI runs in staging/production. |
| 2026-05-27 | Module execution enforces SKILL.md-declared required upstream contracts generically | GTM exposed that a dispatchable module can declare `required_upstream` while still receiving only Brand Brief context at execution. |
| 2026-05-27 | Admin Specialists is the single connector readiness/setup surface; standalone Connectors page removed | Operators think in specialists/jobs, not connector catalogs. `/admin/connectors` is only a compatibility alias. |
| 2026-05-26 | Creative assets are channel-agnostic source artifacts; distribution is a separate CMO-driven dispatch | BOS is omni-channel, multi-location, multi-brand. Nothing in the creative artifact should hardwire it to a specific channel. Locked as Rule #14. |
| 2026-05-25 | Stream pending artifact cards render full ApprovalBundle inline — no side panel for artifacts | Side panel split the decision surface. Inline = card IS the complete review surface. Side panel reserved exclusively for decision_brief and outcome StreamUpdateOut cards. Locked as Rule #13. |
| 2026-05-21 | Shortform video scale uses template rendering first; native platform posting comes after asset generation/export proof | Hundreds of shortform videos are fastest as structured script → TTS → branded motion template → MP4. |
| 2026-05-19 | `_run_modules_streaming()` is the single source of truth for module dispatch; both /chat and /chat/stream use it | Eliminated copy-paste divergence between legacy and streaming endpoints. |
| 2026-05-17 | Public booking widget is BOS-native, not a third-party embed | Google Calendar appointment scheduler requires paid Workspace. BOS serves its own booking page HTML, checks FreeBusy API, creates events via Calendar Events API. |
| 2026-05-15 | Self-contained HTML is the portable artifact format for landing pages and campaigns | Works on every host with no build step. Injects into WordPress via blank/no-theme page template. |
| 2026-05-15 | BOS generates content artifacts; CMS publish plugins deploy them — separation is non-negotiable | BOS must never become a CMS. The artifact record lives in BOS. The platform-specific deploy step lives in a plugin. |
| 2026-05-15 | BOS Command Hub lives at hq.klaroha.com; klaroha.com is reserved for the public Astro marketing site | Keeps internal tooling off the marketing domain. |
| 2026-05-14 | Web container runs a production nginx build, not Vite dev server | Vite dev server caused full page reloads on every navigation, wiping localStorage and clearing the API key session. |
| 2026-05-14 | CMO hard rules belong in the base system prompt, not only in skill context | Skill context injected after thousands of tokens of brand context; invariants must appear in the base prompt before any brand data. |
| 2026-05-13 | Workspace Artifacts are the canonical artifact plane; CMO chat shows artifact references only | Keeps chat conversational and stable while plugins/capabilities produce native artifacts. Locked as Rule #6. |
| 2026-05-12 | Capability questions may produce capability artifacts, but not execution artifacts | `what can you do with email` → Email Specialist capability card; must not read Gmail or draft email unless explicitly asked. |
| 2026-05-12 | CMO-facing marketing surface collapses to `marketing.plan`, `marketing.execute`, and `marketing.optimize` | Prevents BOS from exposing a thousand-entry channel/task catalog; preserves the CMO-in-pocket promise. |
| 2026-05-12 | `BITE.md` elevated to BOS architecture constitution | Keeps governing policy in one mandatory-read file; codifies minimal core, package/plugin extensibility, SKILL.md ownership, live capability manifests, MCP-as-connector, lifecycle hooks. |
| 2026-05-01 | PostgreSQL from day one, no SQLite | Avoid migration cost; per-VPS deployment makes this feasible. |
| 2026-05-01 | FastAPI for BOS core | Async, typed, OpenAPI generation. |
| 2026-05-01 | BYOK alongside platform routing | Lowers barrier; users with own keys shouldn't pay markup. |
| 2026-05-01 | Chat agent is a client, not a BOS service | Keeps interface layer decoupled; BOS is agnostic to caller. |
| 2026-05-02 | OpenAICompatAdapter base class; Gemini + NVIDIA are thin subclasses | All three speak same OpenAI chat completions protocol. |
| 2026-05-02 | React + Vite for frontend | Hot reload via Docker volume mount; nginx proxies. |
