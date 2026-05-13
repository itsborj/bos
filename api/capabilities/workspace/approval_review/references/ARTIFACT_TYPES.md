# Artifact Types — Reference

This file is a lazy-loaded resource for the `approval_review` skill.
Loaded only when the skill is active and the user takes a review action.

---

## BOS Artifact Types

Every artifact produced by a CMO capability belongs to one of these types.
Each type has a defined set of allowed actions.

---

### `email_draft`

A complete email artifact ready for review.

**Fields:** subject, preheader (optional), body, CTA, from_name, recipient_context
**Allowed actions:**
- ✅ Approve — marks artifact as approved in Workspace
- ✅ Reject with feedback — triggers revision run
- ✅ Revise — user provides feedback; revision run creates child artifact
- ✅ Dismiss — removes from pending decisions
- ✅ Send (requires Gmail connector + explicit send confirmation)

**CMO reply on approval:** `"Approved — marked ready in Workspace."`
**CMO reply on revision:** `"Got it. Revising with that feedback now."`

---

### `google_ads_draft`

A Google Ads search text creative or RSA draft.

**Fields:** headlines (list, ≤30 chars each), descriptions (list, ≤90 chars each), final_url, path_fields
**Allowed actions:**
- ✅ Approve — marks artifact as approved
- ✅ Reject with feedback — triggers revision run
- ✅ Revise — creates child revision artifact
- ✅ Dismiss
- ✅ Publish (requires Google Ads connector + Tier 1/2 approval confirmation)

**CMO reply on approval:** `"Approved — ready for Google Ads when you confirm."`

---

### `facebook_post_draft`

An organic Facebook Page post draft.

**Fields:** copy, hashtags (optional), media_description (placeholder), link (optional)
**Allowed actions:**
- ✅ Approve
- ✅ Reject with feedback
- ✅ Revise
- ✅ Dismiss
- ✅ Publish (requires Facebook Page connection)

---

### `campaign_plan`

A structured omnichannel marketing plan artifact (produced by `@klar plan`).

**Fields:** mission, channel_cards (list), gaps_list, confidence_signals
**Allowed actions:**
- ✅ Approve / Confirm (`@klar confirm`) — creates Campaign + IntentContract in DB
- ✅ Revise (`@klar plan [change]`) — regenerates with updated direction
- ✅ Dismiss
- ❌ Publish (plans are not published; execution runs create publishable artifacts)

**CMO reply on confirmation:** `"Plan confirmed. Ready to start execution when you are."`

---

### `performance_report`

A read-only intelligence artifact from a data-pull capability (Google Ads, Search Console, etc.).

**Fields:** channel, date_range, metrics (varies by channel), opportunities_list
**Allowed actions:**
- ✅ Dismiss
- ❌ Approve / Reject / Revise / Publish (reports are informational only)

**CMO reply on viewing:** Answer questions about the data. Surface the top opportunity in 1–2 lines.

---

### `capability_card`

An informational artifact describing what a specialist or capability can do. Not an execution artifact.

**Fields:** specialist_name, jobs (list), hard_boundaries
**Allowed actions:**
- ✅ Dismiss
- ❌ All other actions (capability cards are reference-only)

---

## Revision vs. New Run

| Scenario | What happens |
|---|---|
| User gives feedback on an existing draft | Revision run — child artifact linked to parent via `parent_run_id` |
| User asks to "do it again" or "try a different angle" | New run with updated brief context |
| User approves then asks to change mind | New revision run; approval status updated to `rejected` |

---

## Approval Status Values

| Status | Meaning |
|---|---|
| `pending_review` | Default — artifact awaiting operator action |
| `approved` | Operator approved; no further action unless revision requested |
| `rejected` | Operator rejected; revision run has been triggered |
| `dismissed` | Operator dismissed; removed from pending decisions |
| `sent` | Artifact was dispatched to channel (email, ads, social) |
