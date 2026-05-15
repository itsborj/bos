# google-ads plugin — Dev Notes

Covers: `api/plugins/google-ads/`
Primary capability with known issues: `capabilities/marketing/channel/google_ads/search_text/draft/module.py`
Related: `api/plugins/PLUGIN_SDK.md`, `api/capability_manifest.py`

---

## Invariants (must always be true)

1. **Plugin never touches BOS core.** The only klaroha import allowed is `from klaroha_sdk import ChannelModule`. No access to `get_settings()`, `db`, or any `api/` internal module.

2. **Read/draft only — no mutations.** No campaigns, ads, keywords, bids, or budgets may be changed. `changed_resources` must always be `[]`. Risk level must be `requires_approval`.

3. **All headlines ≤ 30 chars, all descriptions ≤ 90 chars.** `self_check()` enforces this. Any template change must re-verify character limits.

4. **`self_check()` must pass before any output is accepted.** Minimum: 10 headlines, 4 descriptions, required boundary text present, no banned phrases, no over-length strings.

5. **Module is deterministic (`execute_tool_result`).** It does not call an LLM. `template.j2` exists for context only. The `_draft()` method builds all content from brief fields directly.

---

## Fixed Bugs

### Phase 2 — RSA headlines truncated mid-word with long product names
**Observed:** "Multi-Brand Motorcycle Sales F", "Find Multi-Brand Motorcycle Sa", "Built For First-time Motorcycl" — exactly 30 chars, cut mid-word.
**Root cause:** `_clip()` did `clean[:limit]` then `.rstrip()`. This produces a clean hard cut at 30 chars regardless of word boundaries. Product names like "Multi-Brand Motorcycle Sales" + template prefix exceed 30 chars and get sliced mid-word.
**Fix:** `_clip()` now finds the last space within `limit` using `rfind(" ")` and truncates there. Results: "Multi-Brand Motorcycle Sales", "Find Multi-Brand Motorcycle", "Built For First-time".
**Rule:** `_clip()` is the single truncation point for all headline and description text. Never truncate with raw slicing elsewhere. All template string construction in `_draft()` must go through `_dedupe()` → `_clip()`.

### Phase 2 — Previous: RSA headlines repetitive/generic ("Route Serious Convers")
**Pattern:** Template strings constructed headlines that were generic across all brands, and truncation made them indistinguishable.
**Fix (prior):** Added `_dedupe()` to eliminate duplicate headlines after clipping. Added self_check constraint for minimum 10 distinct headlines.

### Phase 2 — Google Ads performance run rendered as raw JSON
**Pattern:** Performance read module returned JSON blob; frontend ApprovalBundle rendered it as copy content.
**Fix (prior):** Performance module returns `layout_hint: "table"` block; BlockRenderer routes to PerformanceReport component.

---

## Do Not

- **Do not import anything from `api/` internals.** Plugin boundary is `klaroha_sdk` only.
- **Do not hardcode brand names, product names, or entity-specific copy.** All content must derive from brief fields.
- **Do not add write/mutation capabilities** (campaign create, bid change, budget change) without a full approval-gated capability following `FULL_CONTROL_SPEC.md`.
- **Do not add capabilities to CMO chat routing or BOS core.** All routing goes through `channel.json` + `SKILL.md` + capability manifest.
- **Do not use raw `[:N]` slicing on headline or description text.** Always go through `_clip()`.

---

## Backlog

- [x] BUG: RSA headlines cut mid-word on long product/brand names — fixed word-boundary truncation in `_clip()` (2026-05-15)
- [ ] IMPROVEMENT: `_draft()` templates still produce repetitive headlines when product name dominates (e.g., 3 of 15 headlines all contain "Multi-Brand Motorcycle"). Consider a `short_product` variant capped at ~20 chars for templates with long prefixes.
- [ ] FEATURE: Full-control approval-gated mutations per `FULL_CONTROL_SPEC.md` — read diagnostics, draft recommendations, approved mutations, destructive second-confirmation
- [ ] FEATURE: Account discovery and campaign report read expansion (account.discover, campaigns.read capabilities already scaffolded)

---

## Current State (2026-05-15)

- `search_text.draft`: correct — word-boundary clipping, 10+ headlines, 4+ descriptions, self_check enforced
- `performance.read`: correct — returns table block, rendered by PerformanceReport
- `account.discover`: scaffolded, read-only
- `campaigns.read`: scaffolded, read-only
- Write/mutation capabilities: not built — FULL_CONTROL_SPEC.md defines the target
