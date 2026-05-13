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

*(none)*

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
