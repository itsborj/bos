# User Journey Map — BOS / Klaroha

> **Audience:** Engineering and architecture team.
> **Purpose:** Map real operator workflows to the system components that must exist to support them. Use this as a test against feature designs, schema decisions, and acceptance criteria.
> **Source:** [`docs/agency_day_in_life.md`](./agency_day_in_life.md)
> **Version:** v0.2 — 2026-06-12
> **Scope note:** This map focuses the broader agency-operator day-in-the-life on the beachhead ICP: the strategic marketing consultant / micro-agency operator. P2 and P3 remain validation personas, but P1 is the default design target.

---

## Personas

| ID | Name | Description | Beachhead Priority |
|---|---|---|---|
| **P1** | Strategic Marketing Consultant (Archetype B) | Solo or micro-agency (1–3 people), 4–8 retainer clients, $4k–$15k/month revenue ceiling. PH-based, serving AU/UK/US clients. They are simultaneously strategist, account lead, creative director, and PM. | **Primary** |
| **P2** | Marketing Agency Owner / Operator | Manages a team + client portfolio. Delegates execution but owns strategy, account relationships, and approval authority. | Secondary |
| **P3** | Ecom Store Owner | Owns 2+ brands directly. No external approval layer. Speed and brand isolation are the primary requirements. | Secondary |

> Secondary personas share journeys with P1 except where noted. Architecture decisions must satisfy P1 first.
>
> This document intentionally goes beyond the current plugin-host MVP. Treat it as the north-star operating journey. Features in `specs/001-thin-core-proof/plan.md` mostly support the integration/plugin readiness layer that later journeys depend on.

---

## Aha Moments (P1 Activation Gates)

These are the exact moments that convert a trial user to a paying customer. Architecture must make these work end-to-end with zero friction.

| # | Aha Moment | What must work | Invariant risk | Journey stage |
|---|---|---|---|---|
| AH-1 | **Strategy generation** — Input URL + one-line brief → full campaign strategy in 4 minutes | Brand profile extraction, CMO dispatch, strategy capability, artifact creation | I-01, I-12 | Stage 0 + Stage 2, step 2.2 |
| AH-2 | **Context memory** — Switch brand → CMO already knows the client | Brand-scoped context hydration, `_brand_scoped_brief()`, brand kit load | I-03, I-04 | Stage 2, steps 2.1 / 2.7 |
| AH-3 | **Approval loop** — Client reviews in BOS, approves, one-click publish | Artifact lifecycle states, client approver role, explicit publish action | I-05, I-07, I-08 | Stage 3, steps 3.1–3.3 |

### Activation Success Metrics

| Metric | Target | Why it matters |
|---|---:|---|
| Time to first strategy artifact | < 4 minutes from URL + brief | Proves BOS can compress strategy work |
| Time to first brand-scoped CMO answer | < 30 seconds after brand switch | Proves context memory works |
| Time from shared artifact to approval action | < 2 clicks for client | Proves approval loop is simpler than email |
| First publish safety | 100% approved + auditable | Proves BOS can be trusted with external channels |

---

## Stage 0 — First Value / Brand Onboarding

**The operator's problem:** They will not pay for another tool unless BOS proves it can hold client context and create useful strategy faster than their current manual workflow.

| Step | Operator Action | BOS Surface | System Requirement | DB / Code Layer |
|---|---|---|---|---|
| 0.1 | Create/select workspace | Onboarding | Workspace exists before any brand data is stored | `Workspace`, owner role |
| 0.2 | Add first client brand | Brand onboarding | Brand row created; active brand becomes explicit | `Brand`, `brand.created` event |
| 0.3 | Paste URL + one-line brief | Onboarding / CMO Chat | Extract profile, offers, audiences, voice, channel hints | Brand profile, `Product`, `Audience` |
| 0.4 | Generate first strategy | CMO Chat | Strategy capability creates a campaign/strategy artifact | `Campaign`, `Artifact`, `run.dispatched` |
| 0.5 | Review Brand Kit / strategy | Artifact card | Operator can approve, edit, or request revision | `Approval`, artifact lifecycle |
| 0.6 | Connect Drive + first channel when needed | Integration setup | Setup blockers are surfaced only at the action that requires them | `ChannelConnection`, plugin readiness |

**Exit criteria:** P1 has one brand with usable memory, one strategy artifact with lineage, and a clear next action. Publishing integrations may still be incomplete, but missing setup must be explicit, typed, and recoverable.

---

## Journey Overview (Daily)

```
08:00                10:00               13:00               15:00               18:00
  │                    │                   │                   │                   │
  ▼                    ▼                   ▼                   ▼                   ▼
[MORNING           ] [DEEP WORK         ] [APPROVALS &      ] [ADMIN &           ]
[Context Reload    ] [Strategy & Gen    ] [Client Comms     ] [Own-Biz Work      ]
  │                    │                   │                   │
  ├─ Overnight scan    ├─ Campaign strategy ├─ Client calls      ├─ Invoicing
  ├─ Ad account alerts ├─ Copy drafting     ├─ Approval chasing  ├─ Pipeline updates
  ├─ Failed posts      ├─ Asset generation  ├─ Revision cycles   ├─ Own-agency content
  ├─ Approval queue    ├─ Brand switching   └─ Status updates    └─ Strategic thinking
  └─ Priority setting  └─ Report prep
```

---

## Journey Stage Detail

---

### Stage 1 — Morning: Client Context Reload (08:00–10:00)

**The operator's problem:** 2 hours spent just getting oriented before a single billable thing is done.

#### Step-by-Step

| Step | Operator Action | BOS Surface | System Requirement | DB / Code Layer |
|---|---|---|---|---|
| 1.1 | Open BOS | Command Center | Load today's alerts for all brands in workspace | `Event` table, indexed by `workspace_id + occurred_at` |
| 1.2 | Scan overnight failures | Alert panel | Show: failed publishes, expired tokens, disconnected integrations, overdue deliverables | `integration.token_expired`, `artifact.publish_failed` events |
| 1.3 | Check review + approval queues | Review / approval panels | Show `ready` artifacts needing operator review separately from `needs_review` artifacts awaiting an approval decision | `Artifact.status IN (ready, needs_review)`, `Approval.status`, joined to `Brand` |
| 1.4 | See what is due today | Today's deliverables | Deliverables due today with owner, campaign, and status | `Task/Deliverable` table, `Campaign` |
| 1.5 | Check active campaign health | Campaign health indicators | Red/yellow/green per campaign | `Campaign.status`, `Metric`, `Artifact` states |
| 1.6 | Ask CMO for the daily brief | CMO Chat | "What needs my attention today?" → structured answer from events, not chat memory | `Event` query → CMO context |
| 1.7 | Decide priorities | — | BOS has surfaced enough signal; operator makes judgment call | — |

#### Architecture Requirements

- Event model must record failures, approval state changes, deadline changes, publish status, and integration health.
- Command center query must run in **< 500ms** for current-day events (§21.5).
- All alerts must be **brand-scoped**. A Motormoto failure must not appear in a Klaroha session.
- Integration health state (`connected`, `needs_reauth`, `missing_page`, `missing_root`, `disconnected`, `error`) must surface without requiring a settings page visit.
- The command center must distinguish **work ready for operator review** (`ready`) from **approval decisions pending** (`needs_review` + pending `Approval`). Mixing these queues hides bottlenecks.
- CMO summarizing the command center must query **structured state**, not chat history (chat history is volatile; §22.4).

#### Invariants at risk

- **I-02**: Approval queue and campaign health must not bleed artifacts from other brands.
- **I-07**: Any publish failure from overnight must appear as a typed event — no silent failures.

---

### Stage 2 — Deep Work: Strategy and Asset Generation (10:00–13:00)

**The operator's problem:** Highest-value work compressed by context-switching and starting from zero every time.

#### Step-by-Step

| Step | Operator Action | BOS Surface | System Requirement | DB / Code Layer |
|---|---|---|---|---|
| 2.1 | Switch to a client brand | Brand switcher (prominent, always visible) | Load brand-scoped CMO context without re-reading brief | `_brand_scoped_brief()`, `BrandKit`, `Product`, `Audience` |
| 2.2 | Open strategy workflow | CMO Chat | "Build a Q3 campaign strategy for [Brand A] targeting [segment]" | Strategy capability SKILL.md, `Campaign` artifact creation |
| 2.3 | Review strategy artifact | Artifact card / Stream | Artifact starts `ready`; when sent for a human decision it becomes `needs_review` and opens/uses a pending approval | `Artifact.status`, `Approval` |
| 2.4 | Generate post/ad creative | CMO Chat | "Make a Facebook post about this promo" → dispatches `creative.post.image` | Capability manifest → module dispatch → ByteDance provider |
| 2.5 | Generated asset stored in Drive | Background / notification | Asset stored under brand Drive root folder, `drive_file_id` written to artifact | `Asset`, `artifact.stored_in_drive` event |
| 2.6 | Request revision | CMO Chat / Artifact card | "Make it more premium, less salesy" | Revision run dispatched with source artifact context; new artifact created; original → `superseded` |
| 2.7 | Switch to second client brand | Brand switcher | Full context reset — no bleed from previous session | `_brand_scoped_brief()` called fresh; previous brand context not carried |
| 2.8 | Generate content for second brand | CMO Chat | Same generation flow, different brand context | Brand-scoped dispatch, brand-scoped artifact |

#### Architecture Requirements

- **Active brand must be displayed prominently at all times.** No UI state where it is ambiguous which brand is active.
- `_brand_scoped_brief()` must never call `_resolve_brief()` — this bleed is the source of brand context failures (I-03).
- Revision creates a **new artifact**; never mutates original. Original transitions to `superseded`, linked via `superseded_by_artifact_id` (I-13).
- ByteDance/BytePlus provider must be resolved from `brief["_channel_credentials"]` via `inject_channel_credentials()`, not read directly from env (I-11).
- If configured provider is unreachable, the module fails with a typed error (`provider_unreachable`, `key_invalid`, `model_unavailable`) — no silent fallback (I-10).
- `drive_file_id` is a first-class artifact field, not an annotation. Artifact must not be publishable without it if Drive is connected.

#### Invariants at risk

- **I-01**: Every dispatched run under Brand A must produce an artifact with `brand_id = Brand A`.
- **I-03**: Active brand dispatch must use `_brand_scoped_brief()`.
- **I-10**: No silent provider fallback.
- **I-11**: Credentials via brief injection only.
- **I-13**: Revision creates new artifact; never mutates.

#### Artifact State Machine (at this stage)

```
pending → generating → ready → needs_review
               ↓
             failed → pending (retry)
```

---

### Stage 3 — Midday: Client Approvals and Comms (13:00–15:00)

**The operator's problem:** Approval loop takes 40–60% of a week on a single piece of content. Feedback arrives in email, Slack, WhatsApp. Approvals tracked mentally.

#### Step-by-Step

| Step | Operator Action | BOS Surface | System Requirement | DB / Code Layer |
|---|---|---|---|---|
| 3.1 | Share artifact for client review | Artifact card → share link or approval surface | Client approver receives link; artifact is `needs_review`; a pending approval exists or is created atomically | `Approval.status=pending`; client approver role |
| 3.2 | Client reviews artifact | Client-facing approval surface | Client can view artifact and leave a decision + feedback | `Approval.status`, `Approval.feedback` |
| 3.3 | Client approves | Approval surface | Artifact transitions to `approved`; publish action unlocked | `Artifact.status = approved`, `Approval.status = approved` |
| 3.4 | Client requests revision | Approval surface | Feedback attached; operator notified; revision dispatched | `Approval.status = revision_requested`; new run with source artifact context |
| 3.5 | Operator follows up on pending approvals | Approval queue | Show artifacts in `needs_review` sorted by age + client | `Artifact`, `Approval` |
| 3.6 | Operator prepares status update | CMO Chat | "Summarize what shipped this week for [Client B]" | Structured query: artifacts, events, publish records by brand + date range |

#### Architecture Requirements

- A pending approval request is created when an artifact enters `needs_review` for a specific approver/audience. Sharing a review link must not create duplicate pending requests for the same artifact + approver.
- Approval decisions are **append-only**. Implement either as immutable `Approval` decision rows or as an `ApprovalRequest` resolved exactly once into an immutable terminal decision. A new decision on a revision creates a new record — the original stands (I-14).
- A **publish action must never execute without a recorded approval decision** in `approved` state (I-05).
- Client approver is a distinct role from operator. Permissions must distinguish: operator, staff, contractor, client approver.
- CMO status summaries must query structured events and artifact state, not chat logs.

#### Approval State Machine

```
pending → approved → [unlocks publish]
        → rejected → [new artifact created]
        → revision_requested → [new run dispatched]
```

#### Invariants at risk

- **I-05**: No publish without recorded approval.
- **I-14**: Approval decisions are append-only and immutable once terminal.

---

### Stage 4 — Afternoon: Admin and Own-Business Work (15:00–18:00)

**The operator's problem:** By 3pm, cognitively depleted. Own-business development (LinkedIn, proposals, referrals) always gets zero energy.

#### Step-by-Step

| Step | Operator Action | BOS Surface | System Requirement | DB / Code Layer |
|---|---|---|---|---|
| 4.1 | Publish approved artifact | Artifact card → Publish action | Reload asset from Drive; post to Facebook/YouTube | `Artifact.drive_file_id` → Drive download → Meta/YouTube API |
| 4.2 | Publish result recorded | Background / notification | `artifact.published` event emitted with `external_id`, `external_url`, `published_at` | `artifact.published` or `artifact.publish_failed` event (always one or the other) |
| 4.3 | Schedule artifact for tomorrow | Artifact card → Schedule action | Set `scheduled_at`; artifact transitions to `scheduled` | `Artifact.status = scheduled`, `Artifact.scheduled_at` |
| 4.4 | Review end-of-day summary | CMO Chat / Command Center | "What shipped today and what didn't?" | `artifact.published` + `artifact.publish_failed` events for the day |
| 4.5 | Check nothing is silently broken | Command Center | Alert panel shows pending failures, blocked items, overdue approvals | Event stream, Integration health state |
| 4.6 | Generate own-agency content | CMO Chat (own brand) | LinkedIn post, proposal, case study for own workspace | Same CMO flow, own-brand context |

#### Architecture Requirements

- `scheduled_at` on an artifact means the **publish action reloads asset from Drive at execution time**, not from a cached temp path (I-06).
- Every publish attempt — success or failure — must emit a typed event. **Silent publish failures are the most trust-destroying failure mode** (I-07).
- Channel credential must be re-evaluated at publish time, not assumed valid from activation time (I-08).
- "Queue for tomorrow" is a single gesture: set `scheduled_at` on an already-approved artifact. No new CMO session required.

#### Artifact State Machine (at this stage)

```
approved → scheduled → published
         → published (immediate)
                ↓
           superseded (if replaced by revision after publish)
```

```
published (attempt) → artifact.published OR artifact.publish_failed
                      (no silent outcome allowed — I-07)
```

#### Invariants at risk

- **I-06**: Drive reload on publish if temp file gone.
- **I-07**: Every publish attempt emits event.
- **I-08**: Credential re-evaluated at publish time.

---

## End-to-End Critical Workflows

These workflows cut across the daily stages and are the primary acceptance test surfaces.

---

### Workflow A — Brand Onboarding to First Publish

**Trigger:** New client added. Must go from zero context to first published artifact.

```
Step  Operator Action                          System Behavior
────  ───────────────────────────────────────  ─────────────────────────────────────────────────
 1    Create Brand in workspace                brand.created event emitted
 2    Import brand brief / fill profile        brand.profile_updated; brand memory seeded
 3    BOS extracts brand profile               Products, Audiences, voice, handles stored
 4    Generate Campaign Brand Kit              brand_kit.generated event; artifact pending → ready
 5    Operator approves Brand Kit              brand_kit.approved; CMO readiness gate cleared
 6    Connect Google Drive, pick root folder   integration.connected; Drive root stored
 7    Connect Facebook and/or YouTube          integration.connected per platform
 8    Ask CMO to create a post/video           CMO dispatch; capability manifest resolved
 9    Module generates media via ByteDance     Asset created via configured provider
10    Asset stored in Drive                    artifact.stored_in_drive; drive_file_id written
11    Operator reviews → approves artifact     Artifact: ready → needs_review → approved; pending Approval resolved
12    Operator explicitly publishes            Credential re-checked; Drive reload if needed
13    Publish result recorded                  artifact.published (external_id, url, timestamp)
```

**Acceptance criteria:**
- No brand context leaks from another brand at any step.
- Missing Drive/Facebook/YouTube connections surface a typed `setup_blocker`, not a generic error.
- CMO does not invent module IDs.
- Images/videos use configured ByteDance/BytePlus provider only (no silent fallback).
- Artifact survives container restart (loaded from `drive_file_id`, not temp path).
- Publish is explicit and auditable.

**Architectural invariants tested:** I-01, I-03, I-05, I-06, I-07, I-08, I-10, I-11, I-12.

---

### Workflow B — Campaign Plan → Multi-Channel Assets

**Trigger:** Operator needs a multi-channel campaign for a client brand.

```
Step  Operator Action                          System Behavior
────  ───────────────────────────────────────  ─────────────────────────────────────────────────
 1    "Build a Q3 campaign for [Brand A]"      Strategy capability dispatched; Campaign artifact created
 2    Operator approves/revises plan           Campaign: draft → briefed → approved
 3    "Generate Facebook + email assets"        Derived artifacts created; parent = Campaign artifact
 4    Each asset: generated → reviewed         Artifact lineage: source_run, source_module, campaign_id
 5    Approved assets published/scheduled       Publish events emitted with campaign_id attached
 6    Performance metrics ingest later          Metrics keyed by brand_id, campaign_id, channel, date
```

**Architectural requirements:**
- Campaign plan artifact is the **parent** of all downstream artifacts.
- Artifacts need lineage: `source_run_id`, `source_module_id`, `campaign_id`, `brand_id` at generation time (I-12, I-15).
- Reporting must connect performance metrics back to campaign objectives.

**Acceptance criteria:**
- Campaign artifact is created before any derived assets; assets carry `campaign_id` from birth.
- Operator can filter the artifact stream by campaign and see only assets for that campaign.
- Metrics ingested later attach to the correct campaign via `campaign_id` + `brand_id` — no manual re-linking.
- Multi-channel assets for the same campaign never bleed into a different brand's stream.

**Architectural invariants tested:** I-01, I-02, I-12, I-15.

---

### Workflow C — Failure Recovery

**Trigger:** Publish failed or media generation failed overnight.

```
Step  Event                                    System Behavior
────  ───────────────────────────────────────  ─────────────────────────────────────────────────
 1    Publish fails                            artifact.publish_failed emitted (typed error code)
 2    Morning command center                   Alert surfaced: error_code + recommended fix
 3    Operator sees recommended action         Options: reconnect platform / pick Drive root /
                                               add provider key / regenerate / retry
 4    Operator fixes → retries                 Retry reuses same artifact context and drive_file_id
 5    Retry succeeds                           artifact.published emitted; failure alert resolved
```

**Architectural requirements:**
- Failures have **typed error codes**, not only raw text (`token_expired`, `provider_unreachable`, `missing_drive_root`, etc.).
- Credential and plugin readiness must be **testable before execution** (pre-flight check).
- Retry must reuse the same artifact, not create a new one, unless the operator explicitly generates a revision.

---

## P2 Marketing Agency Owner — Key Differences

| Dimension | P1 Strategic Consultant | P2 Agency Owner |
|---|---|---|
| Team size | Solo / 1–3 | Manages a team |
| Role in BOS | Operator + executor | Operator; delegates execution to staff/contractors |
| Approval layer | Operator → client | Staff creates → Operator approves → client approves |
| Brand portfolio | 4–8 retainer clients | Larger portfolio; requires cross-brand command center |
| Morning focus | Per-client triage | Team workload view + bottleneck identification |
| Urgency driver | Approval delays, missed deliverables | Team idle time, client escalation, overdue SLAs |
| Permission model | Single operator role | Needs: operator, staff, contractor, client approver roles |
| Architecture delta | — | Staff permission scope: can create artifacts, cannot publish; requires role-based dispatch |

> Architecture satisfies P2 only if the role model is in place. Staff generating content under P2's workspace must produce artifacts scoped to the assigned brand — same invariants (I-01, I-03), different actor.

---

## P3 Ecom Store Owner — Key Differences

| Dimension | P1 Strategic Consultant | P3 Ecom Store Owner |
|---|---|---|
| Approval layer | Operator reviews → client approves | Operator reviews and approves (self) |
| Brand switching | Switch between client accounts | Switch between owned brands |
| Urgency driver | Client approval delays, missed deliverables | Missed post windows, underperforming ads |
| Morning focus | Client-wide triage | Per-brand scheduled content + overnight failures |
| Publishing pattern | Explicit approval → publish | Same, but faster cycle (no client gating) |
| Architecture delta | External approver role required | Approval is always `actor = operator`; same state machine |

> Architecture does not change for P3. The state machine and invariants are identical. The difference is operational cadence and who holds the approver role.

---

## State Machine Summary

### Artifact States

```
pending → generating → ready → needs_review → approved → scheduled → published
               ↓                    ↓                                     ↓
             failed               rejected                           superseded
               ↓                    ↓
           pending (retry)      superseded
```

| State | Meaning |
|---|---|
| `pending` | Dispatch queued |
| `generating` | Module actively executing |
| `ready` | Output available; queued for operator review; no external approval decision has been requested yet |
| `needs_review` | A human decision is pending; at least one pending `Approval` record exists |
| `approved` | Explicitly approved; publish unlocked |
| `scheduled` | Approved + `scheduled_at` set |
| `published` | Live on external platform |
| `rejected` | Not accepted; revision creates new artifact |
| `failed` | Module execution failed |
| `superseded` | Replaced by a newer version/revision |

### Campaign States

```
draft → briefed → in_progress → needs_review → approved → live → paused → archived
                                      ↑               ↓
                                      └── revision_requested ──┘
```

### Approval States (immutable records)

```
pending → approved
        → rejected
        → revision_requested
```

Approval requests are created when an artifact enters `needs_review` for an approver/audience. A request is resolved exactly once into `approved`, `rejected`, or `revision_requested`; terminal decisions are append-only facts. A revision creates a new artifact and a new approval request/decision chain.

### Channel Connection States

```
connected | needs_reauth | missing_page | missing_root | disconnected | error
```
> Must be re-evaluated at **publish time**, not assumed valid from activation.

---

## Architectural Invariants Referenced

| ID | Statement | Journeys Affected |
|---|---|---|
| I-01 | No artifact created with `brand_id = NULL` in multi-brand workspace | A, B, all generation steps |
| I-02 | No cross-brand rows in scoped surfaces (Stream, queue, command center) | Stage 1, all views |
| I-03 | Active brand dispatch must use `_brand_scoped_brief()`, never `_resolve_brief()` | Stage 2.1, 2.7 |
| I-04 | Brand Kit from one brand must not load into another brand's CMO session | Stage 2.1 |
| I-05 | Publish action must never execute without recorded approval in `approved` state | Stage 4.1, Workflow A |
| I-06 | Publish must reload asset from Drive if temp file unavailable | Stage 4.1, Workflow A |
| I-07 | Every publish attempt emits `artifact.published` or `artifact.publish_failed` | Stage 4.2, Workflow C |
| I-08 | Channel credential re-evaluated at publish time | Stage 4.1, Workflow A |
| I-09 | Provider API key values never appear in logs, responses, traces, or errors | All provider calls |
| I-10 | No silent provider fallback; typed error required | Stage 2.4, Workflow A |
| I-11 | Plugin modules receive credentials via `brief["_channel_credentials"]` only | Stage 2.4, all module dispatch |
| I-12 | Every artifact has non-null `brand_id`, `source_run_id`, `created_at` at creation | All generation |
| I-13 | Revision creates new artifact; original transitions to `superseded` | Stage 2.6 |
| I-14 | Approval decisions are append-only; terminal decisions are immutable | Stage 3.3, 3.4 |
| I-15 | Artifact lineage stores: source prompt, run, module, brand, campaign at creation | Workflow B, reporting |

---

## Canonical Typed Error Codes

All module and publish failures must use one of these codes. No raw exception text in operator-facing alerts.

| Code | Layer | Meaning | Recovery action to surface |
|---|---|---|---|
| `token_expired` | Channel credential | OAuth access token past expiry | Reconnect platform (one-click re-auth) |
| `token_revoked` | Channel credential | User revoked app permission | Full reconnect required |
| `missing_page` | Channel credential | Ad account / Page ID not set | Configure in brand settings |
| `missing_drive_root` | Drive | Brand Drive root folder not selected | Pick folder in brand settings |
| `provider_unreachable` | AI provider | API returned 5xx / network timeout | Retry; escalate if persistent |
| `key_invalid` | AI provider | API key rejected (401/403) | Update provider key in workspace settings |
| `model_unavailable` | AI provider | Requested model not available for key | Change model in backend settings |
| `quota_exceeded` | AI provider | Rate limit or monthly cap hit | Wait / upgrade plan |
| `setup_blocker` | Plugin readiness | Required credential slot not filled | Complete plugin setup |
| `artifact_not_approved` | Publish gate | Publish attempted without `approved` state | Approve artifact first (I-05) |
| `asset_not_found` | Drive reload | `drive_file_id` present but file deleted/moved | Re-generate asset |
| `publish_platform_error` | Channel API | Platform API returned non-retryable error | Check platform status; contact support |

> Error codes are stored on the `Event` record. Command center renders the code + recommended fix. Raw exception details go to server logs only (I-09).

---

## Key Event Types (per journey)

| Event | Emitted when | Consumed by |
|---|---|---|
| `brand.created` | New brand row created | Onboarding checklist |
| `brand_kit.approved` | Brand Kit approval | CMO readiness gate |
| `integration.token_expired` | OAuth token expires | Command center alert |
| `artifact.publish_failed` | Publish attempt fails | Command center alert; retry prompt |
| `artifact.published` | Publish succeeds | Audit trail; performance attach point |
| `artifact.ready` | Generated output is available for operator review | Review queue |
| `approval.created` | Artifact enters `needs_review` for an approver/audience | Approval queue; client review link |
| `artifact.stored_in_drive` | Asset saved to Drive | Reload reference; Drive audit |
| `artifact.approved` | Human approves artifact | Publish unlock |
| `artifact.superseded` | Revision replaces artifact | Lineage chain |
| `run.failed` | Module execution fails | Command center error; retry |
| `campaign.past_due` | Campaign missed deadline | Command center alert |

---

## Architecture Decision Checklist

Before shipping any feature, verify:

- [ ] Is it brand-scoped? (I-01, I-02)
- [ ] Does it preserve artifact lineage? (I-12, I-13, I-15)
- [ ] Does it have explicit lifecycle states? (Artifact / Campaign / Approval state machines)
- [ ] Does it survive a page refresh or container restart? (I-06)
- [ ] Does it expose setup blockers clearly with typed error codes? (I-07, I-10)
- [ ] Does it avoid hard-coded provider/model/channel assumptions? (I-10, I-11)
- [ ] Does it emit events useful for daily/weekly/monthly summaries? (§21 event catalog)
- [ ] Can the CMO explain or act on it through chat against structured state? (Stages 1.6, 4.4)
- [ ] Can the operator audit who approved/published what? (I-05, I-07, I-14)
- [ ] Does it help the operator answer one of the eight core operating questions? (See below)

**Eight core operating questions (from the operator's perspective):**

1. What is on fire?
2. What is due?
3. What needs my approval?
4. What client is at risk?
5. What work is profitable?
6. What can we reuse?
7. What should the team do next?
8. What should we sell next?

---

## Coverage Map (Current Status)

Status key: ✅ Done · ⚠️ Partial · ❌ Missing

| Journey Stage | Status | Gap | Phase / Owner |
|---|---|---|---|
| Stage 0 first-value onboarding | ⚠️ Partial | URL/brief extraction, Brand Kit approval gate, first strategy artifact | Phase 3 — onboarding + strategy |
| Morning command center | ⚠️ Partial | Unified alert panel, integration health, review queue, approval queue | Phase 4 — command center sprint |
| Brand context reload (CMO) | ⚠️ Partial | `_brand_scoped_brief()` correctness; Brand Kit approval gate | Phase 3 — brand scoping |
| Campaign strategy generation | ⚠️ Partial | Strategy capability SKILL.md; artifact lineage fields | Phase 3 — strategy capability |
| Asset generation (image/video) | ⚠️ Partial | ByteDance provider validation; Drive storage confirmation | Phase 3 — media plugins |
| Approval loop (client-facing) | ⚠️ Partial | Client approver role; immutable approval records | Phase 4 — approval model |
| Explicit publish (FB/YT) | ⚠️ Partial | Drive reload on publish; typed publish failure events | Phase 4 — publish pipeline |
| End-of-day summary | ❌ Missing | Event query → CMO summary (not chat history) | Phase 4 — event model |
| Weekly/monthly client reports | ❌ Missing | Structured metric ingestion; report artifact type | Phase 5 — reporting |
| Own-agency content | ⚠️ Partial | Same CMO flow; own-brand context isolation | Phase 3 — brand scoping |
| Account health / churn signals | ❌ Missing | Event/risk model; cross-signal scoring | Phase 5 — analytics |
| Staff/contractor role model | ❌ Missing | Role-scoped dispatch; staff cannot publish without approval | Phase 4 — permissions |

---

*Derived from [`docs/agency_day_in_life.md`](./agency_day_in_life.md) v0.4.*
*Update this document alongside any change to persona understanding, state machines, or invariants.*
