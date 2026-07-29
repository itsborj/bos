# Meta Channel Ownership Note

## Insight

Generators such as Postcraft, Imprint, Storyboard, media-image, and future creative modules should not post to Meta directly.

Their job is to produce reviewable, approved artifacts:

```text
generator draft/render -> approved artifact -> channel module publishes
```

Meta owns Meta publishing.

That means `plugins/meta` is responsible for taking an approved artifact as input and turning it into the correct Facebook / Instagram Graph API mutation. Generator modules should remain platform-neutral and should not know Meta credentials, page IDs, Graph endpoints, or publish mechanics.

## Boundary

### Generators own

- Creative generation
- Draft/revision/render approval gates
- Final artifact metadata (`image_asset`, video asset, copy fields, Drive refs, thumbnails)
- No platform mutation

### Meta owns

- Facebook / Instagram credentials
- Page / account selection
- Graph API endpoints
- Text, link, image, and video posting
- Platform-specific result artifacts
- Approval-gated publish execution

## Handoff Contract

The generic artifact action endpoint should hand the approved artifact block to a Meta publish module. Meta should accept common artifact fields, including:

- `message`, `caption`, `post_text`, `approved_post_text`
- `headline`, `subheadline`, `body_copy`, `body`, `cta_text`
- `drive_file_id`, `drive_file_mime`
- `_image_data_b64`, `image_data_b64`, `_image_mime`, `mime_type`
- `image_url`, `link`

If Drive is involved, core may pre-resolve the file into `_image_data_b64`; Meta should also tolerate inline image data for legacy/generator artifacts.

## Rule

Do not move Meta API calls into Postcraft or any generator. If a generated artifact needs to be published to Facebook or Instagram, route it through `marketing.channel.meta.*.publish`.

---

## Reporting / Insights Ownership

Meta may read Meta channel facts, but it must not pretend those facts are a complete campaign evaluation by themselves.

`docs/campaign.md` is the controlling product contract for evaluations:

```text
1. What are we trying to make happen?
2. What changed since the last decision?
3. What needs to happen next?
```

Meta reports should feed those questions only when a real campaign context is bound. A page-level snapshot is useful, but it is not the same thing as campaign performance.

Meta reporting is an evidence source for the daily brief, not the daily brief itself. The correct flow is:

```text
Meta readable facts
→ Meta page snapshot / campaign-bound Meta evidence
→ coverage-bounded signals
→ daily brief / weekly production guidance
→ operator decision
```

A Meta report may say what was readable, what themes appeared, what is missing, and what next operational step is safe. It must not independently rewrite campaign strategy or claim campaign performance without the campaign layer and sufficient metrics.

## Report Types

### 1. Meta Page Snapshot

No campaign required. Read-only channel state.

Should show:

- connected Page / account
- follower count
- scheduled post count
- last-published / recent activity when permissions allow
- coverage / permission status
- freshness timestamp

Operator framing:

```text
This is a Meta channel snapshot, not a campaign evaluation.
```

Actions:

- Refresh
- Open Meta setup
- View scheduled queue

Do not show creative-review language such as `Self-check passed. Waiting for your review.`

### 2. Meta Scheduled Queue

No campaign required for read-only list. Campaign binding is required for campaign attribution.

Should show:

- scheduled post ID
- scheduled time
- caption preview
- source artifact / campaign when known

Future actions:

- Cancel scheduled post
- Reschedule
- Open source artifact

### 3. Meta Permission Readiness

No campaign required. This is an operator setup/readiness report.

Should clearly separate:

```text
Readable:
- Page profile
- follower count
- scheduled queue

Blocked:
- recent post engagement
- page insights metrics

Fix:
- Reconnect Meta with pages_read_engagement / required app review feature.
```

Absence and permission blocks are values, not generic failures. Do not hide them behind a red creative artifact card.

### 4. Campaign Evaluation

Requires explicit campaign binding.

A campaign evaluation may use Meta facts as evidence, but the evaluation itself belongs to the campaign layer. It must anchor to:

- campaign objective
- audience / actor
- offer / product
- message focus
- current work and approved artifacts
- published proof
- recent signals
- blockers
- one recommended next action

If no campaign is selected or inferable, Meta should return the channel snapshot plus a plain handoff:

```text
I can show the Meta page snapshot, but I need a campaign to evaluate performance.
```

## Current Failure Ledger — 2026-07-05

### Failure: report summary is too shallow for strategy work

Observed live on Golden Gate Memorial Garden Cebu:

```text
Followers: 2,031
Scheduled posts: 0
Recent posts: 10
Insight metrics: 0
Coverage: partial
```

The report now correctly pulls readable page activity from Meta when the richer `/posts` engagement edge is blocked, including recent post copy such as:

- “Secure Your Family's Future / Plan with Peace of Mind”
- “Be the Trusted Guide Families Remember”
- “Empower Your Community with Dignity”
- funeral-cost / family-preparedness messaging

But the CMO reply still collapses this into a generic list and closes with “let me know if you need further insights.” That is not useful strategic analysis. It fails the campaign contract because it does not answer:

```text
1. What are we trying to make happen?
2. What changed since the last decision?
3. What needs to happen next?
```

Root cause:

- Meta has readable channel facts, but no campaign-evaluation frame is attached.
- The response summarizes page activity instead of classifying it against campaign objective, audience, offer, message focus, and next action.
- Permission coverage is partial: `recent_posts_engagement` is blocked, so we can read recent post copy but not reliable likes/comments/shares/reach.
- Page Insights metrics currently return no rows for the tested metric set, so “Insight Metrics: 0” must be treated as coverage absence, not performance absence.

Correct current framing:

```text
This is a partial Meta page snapshot. It shows what has recently been posted and whether anything is scheduled. It cannot yet evaluate performance because engagement/reach metrics are unavailable. It can still support a strategist by identifying message themes, posting cadence, campaign alignment gaps, and next data needed.
```

### What the report should synthesize even with partial coverage

When only recent post text is readable, the report can still produce **content intelligence**, not performance intelligence:

- message themes currently being used
- audience implied by the copy
- offer / CTA consistency
- repetition or drift across recent posts
- whether scheduled queue is empty
- whether posts map to an active campaign message focus
- what data is missing before making performance claims

It must not claim:

- reach improved or declined
- engagement improved or declined
- audience demographics or interests
- best/worst posts
- conversion impact

unless those facts are present from Meta or campaign result rows.

### Implemented reporting optimization — 2026-07-05

`marketing.channel.meta.pages.insights.report` now renders report output in coverage-labeled strategist sections instead of a flat metric list:

```text
Readable facts
- Page profile / follower count
- Scheduled queue
- Recent post copy and source
- Insight metric count

Content intelligence
- Themes in readable copy
- Audiences implied
- Offer/CTA consistency
- Scheduled queue state

Not available yet
- Reach / impressions / engagement when permissions or metrics are missing
- Lead, message, call, form, or revenue attribution
- Campaign-bound evaluation when no campaign evidence is bound

Strategist next step
- One safe recommendation based on readable facts only
```

The result block also carries `coverage`, `coverage_label`, `report_scope`, `campaign_binding`, `metrics_overview`, `insight_bullets`, `content_intelligence`, `not_available`, `recommended_next_step`, and `daily_brief_signal` so future daily-brief producers can consume the report as omni-channel evidence. Metrics are shown as overview only; the artifact's value is the bulleted insight layer. If a campaign is selected via the execution context or campaign alignment, insight bullets anchor to that existing campaign. If no campaign is selected but the host provides active campaign candidates, the report marks itself as `campaign_candidate`/`campaign_candidates` and names the existing campaigns that should be used for binding. Otherwise it remains a `channel_snapshot`, says it is unanchored, and stops short of campaign evaluation.

ChatV2 should return the report artifact content directly for report turns instead of asking the LLM to re-summarize it. The report artifact owns the insight bullets; the CMO reply should not collapse it back into counts plus a generic "let me know" closer.

## Strategist Input Requirements

From a marketing strategist perspective, useful Meta optimization requires more than page facts. The minimum planning inputs are:

### Campaign frame

- active campaign ID / name
- objective: what are we trying to make happen?
- audience / actor
- offer / product
- current message focus
- current channel role for Meta: awareness, education, trust-building, lead capture, retargeting, community proof, etc.
- time window / cadence expectation

### Content inventory

- recent posts with copy, format, media type, CTA, link, publish time
- scheduled posts queue
- source artifact / campaign link for each post when known
- whether each post is campaign-bound or brand-foundation/unassigned

### Performance evidence

Required for optimization claims:

- reach / impressions
- engagement totals and rates
- reactions, comments, shares, saves when available
- link clicks / landing-page visits
- leads / messages / calls / forms if tracked
- spend and paid/organic split if boosted or ads are involved
- comparison window: previous 7/28 days, prior campaign period, or baseline

### Qualitative signals

- comment themes / audience questions
- objections appearing in comments or messages
- repeated language from prospects
- client/operator feedback
- rejected claims or compliance constraints

### Decision constraints

- what cannot be claimed
- budget / posting frequency limits
- creative asset availability
- brand tone/visual constraints
- approval/publish risk level

### Output expected from strategist

A strategist report should produce:

```text
What is happening:
- readable factual state

What it means:
- interpretation bounded by available evidence

What is missing:
- coverage gaps that prevent stronger claims

What to do next:
- one safe next action

What to test next:
- one message/format hypothesis for the weekly review, not daily creative churn
```

## Cadence Rule

Follow `docs/campaign.md`:

```text
Daily steers distribution.
Weekly refines production.
```

Daily Meta data may trigger distribution and operational actions:

- publish/schedule decision
- scheduled queue check
- response or moderation follow-up
- permission/connectivity fix
- failed publish recovery

Daily Meta data must not directly rewrite creative strategy. Creative/production changes come from the weekly review / `production_guidance`, where signals are distilled into durable campaign guidance.

## Report UI Rule

Meta read-only reports should render as reports, not as creative artifacts.

Use labels like:

```text
Read-only report
Coverage: Full / Partial / Blocked
Fresh as of: <timestamp>
```

Use actions like:

```text
Refresh
Export
Open Meta setup
Use in campaign review
```

Avoid actions like:

```text
Approve
Revise
Publish
```

unless the report is explicitly attached to a downstream approval-gated campaign action.
