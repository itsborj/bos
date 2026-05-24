# ISSUES.md — BOS Issue Tracker

> Running catalog of bugs, regressions, and behavioral problems identified during development.
> Each issue gets a permanent ID. Closed issues stay in the log — never delete.
>
> Status: `open` · `investigating` · `fixed` · `wont-fix` · `deferred`

---

## Format

```
### ISS-NNN — Short title
- **Status:** open | investigating | fixed | wont-fix | deferred
- **Found:** YYYY-MM-DD
- **Fixed:** YYYY-MM-DD (or —)
- **Area:** router | capability | plugin | manifest | prompt | frontend | infra
- **Symptom:** What the user or system observed.
- **Root cause:** Why it happened (fill in during investigation).
- **Resolution:** What changed to fix it (fill in when closed).
```

---

## Open Issues

### ISS-008 — Auth relay unbuilt — blocks one-click client deploy
- **Status:** open
- **Found:** 2026-05-25
- **Fixed:** —
- **Area:** infra · provider_auth
- **Symptom:** BOS OAuth (Google Drive, Gmail, Calendar, YouTube, Meta) runs in dev mode only — each deployment must supply its own `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and registered `GOOGLE_REDIRECT_URI`. New client domains require a manual change to Klaroha's Google Cloud Console and Meta Developer app. One-click consumer deploy is impossible in this state.
- **Root cause:** The central auth relay (`auth.klaroha.com`) has not been built. The architecture is fully specified in `docs/auth-relay-architecture.md`. Dev mode is intentional as a short-term measure for the single internal deployment; it is not acceptable once external clients exist.
- **Resolution:** Build the relay and wire BOS to use it when `KLAROHA_RELAY_URL` is set. Full checklist in `docs/auth-relay-architecture.md § Before first external client`:
  - Build `auth.klaroha.com` relay (~300-line FastAPI app, separate `klaroha/auth-relay` repo, Redis for handoff TTLs)
  - Register `https://auth.klaroha.com/relay/google/callback` + `/relay/meta/callback` in Klaroha's Google and Meta developer consoles
  - Submit Google app for verification (Gmail/Drive scopes) and Meta app for App Review (`pages_manage_posts`, `pages_show_list`, `pages_read_engagement`)
  - [x] Add `klaroha_relay_url` + `klaroha_relay_key` to `config.py` and `.env.example`
  - [x] Add relay-aware paths to `provider_auth.py` (redirect URI delegation, `relay_claim_handoff`, `relay_refresh_token`) and `routers/social.py` (`handoff_token` claim path on all four Google callbacks + relay refresh in `get_page_token`)
  - Write relay onboarding script (registers instance URL, issues `relay_key`)
  - Update one-click deploy docs

---

### ISS-007 — Stream not updated when CMO produces new artifacts
- **Status:** fixed
- **Found:** 2026-05-25
- **Fixed:** 2026-05-25
- **Area:** frontend · router
- **Symptom:** After CMO chat dispatched a module and produced an artifact (e.g. `creative_post_asset`), the Stream page showed no new cards until the user manually navigated away and back. The artifact existed in the DB but the Stream never reflected it live.
- **Root cause:** Two compounding bugs:
  1. `_execute_module` in `routers/runs.py` auto-approved any run where `block.status == "succeeded"`, including `creative_post_asset`. This set `run.approval_status = "approved"` immediately, so `artifact_ref_from_run` returned `status = "approved"` rather than `"pending_review"`.
  2. `CmoChatContext` never called `addPendingRun` at all when a `module_result` arrived from the chat stream. There was no mechanism to push the new artifact into the Stream's `pendingRunItems` state. The artifact appeared only in chat history.
  (A third attempt added a `pending_review` status guard to `addPendingRun`, but that guard always evaluated false because of bug #1 — the artifact was already auto-approved.)
- **Resolution:**
  - `_execute_module`: skip auto-approval when `"publish"` is in `block.allowed_actions` — those artifacts require human review before publishing and must arrive on Stream as `pending`.
  - `CmoChatContext`: on every `module_result` SSE event, fetch the full `RunResponse` via `api.getRun(artifact_id)` and call `addPendingRun`. Guard is `status !== 'failed'` (not `=== 'pending_review'`). This feeds the Stream's `pendingRunItems` immediately, triggering a re-render without a page refresh.

---

## Closed Issues

### ISS-001 — BOS Skill Catalog driving CMO to prose instead of dispatch
- **Status:** fixed
- **Found:** 2026-05-12
- **Fixed:** 2026-05-12
- **Area:** prompt
- **Symptom:** CMO replied with a written description of capabilities ("Here's what I can do: …") instead of dispatching modules when user asked "show me samples."
- **Root cause:** System prompt contained a "BOS Skill Catalog" section listing capabilities as a menu for prose responses. Follow-up turns had an empty module list, so the catalog drove prose-only answers.
- **Resolution:** Removed BOS Skill Catalog from system prompt. Replaced with `format_manifest_for_prompt()` output from `capability_manifest.py` — a live-generated list of `RUN:` directives the LLM uses for dispatch, not description.

---

### ISS-002 — Hardcoded platform routing in CMO chat router
- **Status:** fixed
- **Found:** 2026-05-12
- **Fixed:** 2026-05-12
- **Area:** router
- **Symptom:** CMO dispatched only Facebook ad copy for "show me samples"; re-dispatched it for "anything else?" — module selection was determined by Python phrase-matching, not LLM judgment.
- **Root cause:** `routers/chat.py` and `skills/router.py` contained `_has_generation_intent()`, `_is_broad_sample_ads_request()`, `_explicit_platforms()`, and a hardcoded `"paid.ads.copy"` filter. These overrode the LLM's own decisions.
- **Resolution:** Removed all mechanical routing functions from both files. All capability activation logic now lives in SKILL.md (`triggers`, `excluded_triggers`, `requires_intent`). The CMO LLM reads the manifest and uses its own judgment.

---

### ISS-003 — [Dispatched: X] markers appearing as literal reply text
- **Status:** fixed
- **Found:** 2026-05-12
- **Fixed:** 2026-05-12
- **Area:** router · prompt
- **Symptom:** CMO wrote `[Dispatched: Gmail Inbox]` as plain conversational text in its reply, and both Gmail modules fired, even for a question about capabilities.
- **Root cause:** `_strip_run_directives()` was changed to replace `RUN: module.id` lines with `[Dispatched: Label]` markers in conversation history. The LLM saw these in history and in an instruction referencing them, learned them as a conversational pattern, and began writing them as literal reply text without actual `RUN:` output.
- **Resolution:** Reverted `_strip_run_directives()` to simple removal (no replacement text). Removed the history-tracking instruction that referenced `[Dispatched:]`. Added explicit instruction prohibiting `[Dispatched:]` in visible reply text.

---

### ISS-004 — CMO dispatching modules for capability questions ("what are you capable of")
- **Status:** fixed
- **Found:** 2026-05-12
- **Fixed:** 2026-05-12
- **Area:** prompt
- **Symptom:** User asked "what are you capable of" and CMO dispatched Gmail Inbox + Gmail Outreach Draft modules, treating the question as a deployment request.
- **Root cause:** System prompt instruction said "execute any" and "deploy right now" — LLM interpreted a question about capabilities as an invitation to demonstrate them.
- **Resolution:** Instruction 1 in CMO system prompt now reads: "Deploy a capability only when the user is asking you to DO something. For questions about what you can do, answer conversationally using the list above."

---

### ISS-005 — Facebook / Twitter capability traces in system after channel removal
- **Status:** fixed
- **Found:** 2026-05-12
- **Fixed:** 2026-05-12
- **Area:** capability · plugin · router · config
- **Symptom:** Facebook and Twitter capabilities, plugins, OAuth handlers, and config fields remained in the codebase after the decision to go Gmail-only.
- **Root cause:** No prior cleanup pass; capabilities were added incrementally and never audited against current channel scope.
- **Resolution:** Full sweep — deleted `capabilities/marketing/channel/facebook/`, `twitter/`, `meta/`, `google/`, `google_business_profile/`, `capabilities/marketing/meta_ads/`, `campaign_structure/`, `google_ads/`, `capabilities/internal/`, `plugins/facebook/`, `providers/facebook.py`; removed `FacebookPageOAuthHandler`, all Facebook/Twitter config fields, mock content branches, and 9 test files. Channel scope is now Gmail + copywriting only.

---

### ISS-006 — CMO generating prose instead of dispatching for "show me an email sample"
- **Status:** fixed
- **Found:** 2026-05-12
- **Fixed:** 2026-05-12
- **Area:** prompt · manifest · plugin
- **Symptom:** User asked "let me see a sample" and "show me an email sample." CMO responded with natural-language text ("Checking your inbox now. Sending the email.") without outputting `RUN:` directives or actually dispatching the outreach draft module.
- **Root cause:** `marketing.channel.gmail.outreach.draft` SKILL.md was missing the `module_id` field. Without it, `format_manifest_for_prompt()` excluded the skill (filters on `not skill.module_id`), `_chat_modules()` never added it to the allowed set, and `route_chat_skills()` skipped it in trigger matching. The CMO never saw the capability and had no way to dispatch it. Additionally, the "show me" / "email sample" trigger phrases were absent from the SKILL.md triggers list, and instruction 1 in the system prompt framed "show me a sample" as a demonstration (blocked) rather than a DO request.
- **Resolution:** Added `module_id: marketing.channel.gmail.outreach.draft` to the plugin SKILL.md — this restores the skill to the capability manifest, the allowed-modules gate, and trigger routing. Added "email sample", "sample email", "show me an email", "let me see an email", "email example" to SKILL.md triggers. Tightened SKILL.md description to include "show a sample" pattern. No changes to core router — all fixes are plugin-only per the BOS architecture constitution.
