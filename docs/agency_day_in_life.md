# Day in the Life: Marketing Agency Operator

> Living business-requirements guide for BOS architecture decisions.
> Use this document to evaluate whether product, backend, plugin, data-model, and UI decisions support how a real agency operator runs their business.
>
> Version history:
> - v0.1 — 2026-06-11 initial draft
> - v0.2 — 2026-06-11 expanded operator workflows, architecture requirements, coverage map, and prioritization
> - v0.3 — 2026-06-11 added ecom store owner persona (§4b), state machines (§20), event catalog (§21), architectural invariants (§22)
> - v0.4 — 2026-06-12 added §4c Beachhead ICP persona — Archetype B: Strategic Marketing Consultant

---

## 1. Purpose

BOS is not just a chat UI or content generator. For an agency operator, it must become an operating layer across:

1. **Client brand context** — who each client is, what they sell, and how they communicate.
2. **Campaign execution** — planning, producing, approving, storing, publishing, and reporting work.
3. **Agency operations** — deadlines, team capacity, approvals, client communication, profitability, and risk.
4. **Business growth** — pipeline, proposals, referrals, case studies, upsells, and retention.

This document describes the operator's day/week/month/quarter/year so architecture can be designed around actual work, not isolated features.

---

## 2. Primary Persona

### Marketing Agency Owner / Operator

A marketing agency owner or business leader managing a portfolio of client brands, a delivery team, and their own business growth.

They are simultaneously:

- Chief strategist
- Account lead / client relationship owner
- Creative director
- Delivery manager
- Sales leader
- Finance reviewer
- Team manager
- CEO

They do not experience the business as separate modules. They experience it as a constant stream of questions:

- What is on fire?
- What is due?
- What needs my approval?
- What client is at risk?
- What work is profitable?
- What can we reuse?
- What should the team do next?
- What should we sell next?

### Secondary Personas

| Persona | Needs | BOS implication |
|---|---|---|
| Account manager | Know client status, approvals, risks, upcoming deliverables | Brand/account workspace, client timeline, approval state, communication summaries |
| Strategist | Turn brand context into campaigns, offers, briefs, and positioning | CMO Brain, strategy artifacts, reusable brand memory |
| Creative team | Produce on-brand copy/images/videos without chasing context | Brand kit, asset library, artifact generation, Drive integration |
| Media buyer | Launch, monitor, and optimize paid campaigns | Channel connections, performance data, pacing alerts |
| Reporting specialist | Build client-ready reports and decks | Analytics connectors, report artifacts, Drive export |
| Finance/admin | Track invoice risk, margin, scope creep | Client profitability and billing signals |
| Client approver | Review and approve work with minimal friction | Approval links/cards, artifact history, publish controls |

---

## 3. Core Operating Model

The agency operator moves through five overlapping loops.

| Loop | Main question | System requirement |
|---|---|---|
| Firefighting loop | What needs attention now? | Unified inbox of alerts, failed runs, blocked approvals, overdue deliverables |
| Delivery loop | Are we shipping promised work? | Calendar, work queue, campaign/artifact status, ownership |
| Quality loop | Is work good enough and on-brand? | Brand kit, approval workflow, review tools, reusable assets |
| Performance loop | Are campaigns working? | Analytics ingestion, KPIs, reports, optimization recommendations |
| Business loop | Is the agency healthy and growing? | Pipeline, revenue, margin, churn, capacity, renewal signals |

Architecture should not treat these as unrelated pages. They should share common primitives:

- Brand
- Client/account
- Campaign
- Artifact
- Approval
- Channel connection
- External asset
- Task/deliverable
- Metric
- Event
- Risk
- Recommendation

---

## 4. Daily Operator Journey

### 4.1 Morning Command Center — 8:00–10:00am

The operator starts the day needing immediate situational awareness.

#### Jobs to be Done

- Scan overnight client messages and emergencies.
- Check campaign failures, broken integrations, missed posts, or ad account issues.
- Identify approvals blocking delivery.
- Review what is due today.
- See team capacity and blockers.
- Check revenue/cash alerts.
- Decide top priorities for the day.

#### Questions the Operator Asks

- Which clients need attention today?
- What campaigns are broken, late, or underperforming?
- What content is ready for approval?
- What did clients ask for overnight?
- What work is blocked by missing assets, credentials, or approvals?
- Which deadlines are at risk?
- What is the one thing I must not miss today?

#### Required BOS Experience

A **daily command center** should show:

| Section | Requirement |
|---|---|
| Critical alerts | Failed publishes, disconnected integrations, expired tokens, rejected assets, overdue deliverables |
| Approval queue | Artifacts waiting on operator/client approval, sorted by urgency/client tier |
| Today’s deliverables | Work due today by client, campaign, owner, and status |
| Campaign health | Red/yellow/green indicators for active campaigns |
| Client messages | Summaries from connected communication channels where available |
| Team blockers | Tasks blocked by missing info/assets/approval |
| Revenue/cash snapshot | Optional later: invoices due, overdue, MRR movement |

#### Architecture Implications

- Event model must record failures, approvals, deadline changes, publish status, and integration health.
- Runs/artifacts need lifecycle states beyond success/failure: draft, review, approved, scheduled, published, rejected, stale, superseded.
- Brand-scoped context is mandatory. A daily view must not bleed artifacts or metrics between brands.
- Integrations must expose health state: connected, needs reauth, missing root folder, missing page/channel, inactive plugin.
- Chat should be able to summarize the command center and answer follow-up questions against the same source of truth.

---

### 4.2 Midday Execution — 10:00am–3:00pm

The operator shifts from diagnosis to moving work forward.

#### Jobs to be Done

- Join client calls.
- Review work in progress before it reaches clients.
- Assign or reassign tasks.
- Generate missing campaign assets.
- Give feedback on creative/copy/video.
- Approve ready-to-publish work.
- Answer team questions.
- Handle client changes without losing context.

#### Common Workflows

| Workflow | Example operator request | BOS must support |
|---|---|---|
| Generate social post | “Make a Facebook post for Brand A about this promo.” | Brand-scoped CMO dispatch, `creative.post.image`, image generation, Drive storage, approval card |
| Generate video | “Create a 15-second YouTube/Facebook video from this campaign angle.” | ByteDance video generation, Drive storage, publish actions |
| Revise asset | “Make it more premium, less salesy.” | Revision lineage, previous artifact context, same brand/campaign |
| Publish approved work | “Publish this to Facebook.” | Explicit approval/action, Meta token, Drive reload, publish result |
| Prepare client update | “Summarize what shipped this week for Client B.” | Runs/artifacts/task history summarized by brand/client/date |
| Triage blocker | “Why didn’t this post go out?” | Trace, credential status, module failure reason, recommended fix |

#### Required BOS Experience

- Every generated artifact must have an owner, brand, campaign, source prompt, creation time, and current state.
- Every artifact should be reviewable and reusable.
- Generated image/video assets must be stored in the brand’s connected Google Drive folder when configured.
- Publish actions must reload assets from durable storage, not rely on temporary local files.
- The operator should be able to continue from chat, artifact cards, brand pages, or campaign pages without losing context.

#### Architecture Implications

- CMO chat, artifact generation, Drive storage, approval UI, and channel publishing must use one artifact contract.
- “Generate” and “publish” must remain separate unless the user explicitly approves publishing.
- The system needs action permissions and explicit action provenance: who approved, what was published, to which platform, and when.
- Drive file IDs, web links, MIME types, and folder paths should be first-class artifact fields.
- Media providers should be replaceable by backend override/plugin configuration, not hard-coded lists.

---

### 4.3 End-of-Day Closeout — 3:00–6:00pm

The operator needs confidence that nothing is silently slipping.

#### Jobs to be Done

- Confirm what shipped.
- Confirm what did not ship and why.
- Send status updates.
- Update pipeline/deals.
- Queue tomorrow’s priorities.
- Capture risks before they become client escalations.

#### Required BOS Experience

An **end-of-day closeout** should answer:

- What deliverables shipped today?
- What was approved but not published?
- What failed and needs human action?
- Which clients have overdue approvals?
- Which campaigns need tomorrow morning attention?
- What follow-up messages should be sent?

#### Architecture Implications

- BOS needs an activity ledger/event stream per brand and across the workspace.
- Runs and artifacts must be queryable by date, brand, campaign, module, channel, owner, and status.
- The CMO should be able to generate a daily summary from structured state, not only chat history.

---

## 4b. Ecom Store Owner — Daily Journey

This persona owns 2+ brands directly (e.g. Klaroha + Motormoto). No client portfolio, no external approver — they are the operator, the creative director, and the approver simultaneously. BOS acts as a one-person marketing department.

**Key difference from agency owner:** No external approval layer. The "pending approval" queue means pending their own review. Publishing decisions are faster and more direct. Brand isolation still matters — mixing Motormoto creative with Klaroha campaigns is a confusion failure, not a compliance failure.

---

### 4b.1 Morning Quick Scan — 8:00–9:00am

#### Jobs to Be Done

- See what is scheduled to go out today across all owned brands.
- Confirm no overnight failures (publish errors, Drive problems, expired tokens).
- Decide which brand needs attention first.
- Check yesterday's post performance quickly.

#### Questions the Operator Asks

- Did anything fail overnight?
- What goes out today and is it ready?
- How did yesterday's posts perform?
- Which brand needs creative work today?

#### Required BOS Experience

A **per-brand overview** showing:

| Section | Requirement |
|---|---|
| Scheduled for today | Content queued per brand with status and channel |
| Overnight failures | Failed publishes, token expirations, Drive errors |
| Yesterday's performance | Reach, engagement, clicks — quick read, not deep analytics |
| What needs approval | Operator's own review queue across brands |

#### Architecture Implications

- Brand switcher must be the primary navigation concept — this user jumps between brands constantly throughout the day.
- Stream and approval queue must be filterable by brand; a mixed feed causes direct confusion when brand identities are distinct.
- Scheduled-for-today view requires artifact `status=scheduled` + `scheduled_at` fields queryable by brand.
- Integration health per brand (token expiry, missing Drive root) must surface without requiring a page visit to settings.

---

### 4b.2 Content Production — 9:00am–4:00pm

#### Jobs to Be Done

- Generate on-brand content for a specific brand.
- Review, adjust, and approve quickly without delegating.
- Schedule or publish immediately.
- Switch brands mid-session without losing context.

#### Common Workflows

| Workflow | Operator request | BOS must support |
|---|---|---|
| Generate social post | "Make a Motormoto Facebook post about the weekend sale." | Brand-scoped CMO dispatch, asset generation, approval card in Stream |
| Quick revision | "Make the image darker and the copy punchier." | Revision with artifact lineage, same brand/campaign context preserved |
| Schedule for tomorrow | "Approve this and schedule it for 9am tomorrow." | Explicit approval + scheduled_at, Drive asset durable reload at post time |
| Publish now | "Post this to Klaroha Facebook now." | Explicit publish action, Drive reload, result recorded with external post ID |
| Brand switch | "Now do the same thing but for Motormoto." | Clear brand context switch — no context bleed between brands |
| Asset reuse | "Use the image from the last Motormoto campaign." | Drive browser, artifact search by brand/campaign, reuse without regeneration |

#### Architecture Implications

- The active brand must be displayed prominently at all times. There must be no ambiguity about which brand's CMO session is active.
- Revision must preserve `brand_id` from the original artifact — a revision of a Motormoto artifact must stay Motormoto.
- `scheduled_at` on an artifact requires the publish action to reload the asset from Drive at execution time, not cache the temp file.
- Asset reuse requires Drive file IDs to be first-class fields on artifacts, not optional annotations.

---

### 4b.3 End-of-Day Performance Check — 4:00–6:00pm

#### Jobs to Be Done

- Check what went out and how it performed.
- Queue tomorrow's content.
- Note anything that underperformed for brief adjustment.

#### Questions the Operator Asks

- What published today and where?
- Any posts performing unusually well or poorly?
- What creative should I queue for tomorrow?
- Any campaign spending outside expected range?

#### Required BOS Experience

- Per-brand daily activity summary: published artifacts, channels, times, and early performance signals.
- A "queue for tomorrow" surface — artifacts in `approved` state with a simple schedule action.
- CMO accessible to ask "how did today's Motormoto content perform?" against structured event data.

#### Architecture Implications

- Performance metrics must attach back to specific artifacts (post → drive_file_id → artifact record).
- Daily activity summary is only meaningful if every publish emits a structured event with `artifact_id`, `channel`, `external_id`, and `published_at`.
- "Queue for tomorrow" is just setting `scheduled_at` on an already-approved artifact — no new CMO session needed; this should be a one-action UI gesture.

---

### 4b.4 Ecom vs. Agency Persona — Key Architecture Differences

| Dimension | Agency Owner | Ecom Store Owner |
|---|---|---|
| Approval layer | Operator reviews → client approves → publish | Operator reviews and approves (self) |
| Brand switching | Switch between client accounts | Switch between owned brands |
| Team size | Staff + contractors + client contacts | Solo or 1–2 person team |
| Reporting audience | External (client decks, account reviews) | Internal (personal performance review) |
| Risk of brand bleed | Reputational / client trust failure | Operational confusion |
| Campaign planning | Tied to client deadlines and contracts | Tied to product launches and promotions |
| Primary urgency driver | Client approval delays, missed deliverables | Missed post windows, underperforming ads |

---

## 4c. Beachhead ICP — Archetype B: Strategic Marketing Consultant

> **GTM note:** This is Klaroha's primary beachhead persona. The product architecture (multi-brand workspace, CMO chat, strategy workflows, brand memory, approval loop) is more aligned to this operator than to any other segment. Acquisition starts here before expanding to distributed networks or enterprise.

---

### 4c.1 Persona Snapshot

| Field | Detail |
|---|---|
| **Role** | Freelance marketing consultant or micro-agency owner (1–3 person team) |
| **Location** | Philippines-based (or Southeast Asia); clients in AU, UK, and/or US |
| **Client roster** | 4–8 active retainer clients simultaneously |
| **Billing model** | Monthly retainer, $800–$3,000 AUD/USD per client |
| **Monthly revenue** | $4,000–$15,000 USD; approaching or stuck at the $10k ceiling |
| **Primary services** | Marketing strategy, content planning, social media management, email campaigns, paid ads oversight, performance reporting |
| **Team structure** | Solo or with 1–2 VA/execution contractors |
| **Time zone reality** | Works PH daytime (8am–6pm PHT) which overlaps: AU morning, UK/EU late evening, US not at all during the day |
| **Why they chose this path** | Escape from agency employment; own client relationships; work from home; income ceiling in local employment is low |

---

### 4c.2 Their Business Problem in One Sentence

> They are the strategy, the account manager, the creative director, the project manager, and the operations admin — simultaneously — for 5 different businesses they do not own, using 8 different tools, with no persistent memory between client sessions.

This is not an efficiency problem. It is a **structural capacity problem**. They have hit the ceiling not because they lack skill, but because the mental overhead of context-switching across clients, rebuilding context from scratch, and managing approval and delivery cycles manually consumes all the time they would otherwise use to add more clients or do better work.

---

### 4c.3 Day in the Life — Archetype B

#### Morning: The Client Context Reload (8:00am–10:00am PHT)

The first hour of every day is not strategy — it is **context reconstruction**.

Before a single piece of work is done, this operator must:

- Open each client's Notion or Google Doc brief and re-read it to remember where things stand.
- Check each client's Slack or email for overnight messages (AU clients were active during their own business day while PH was asleep).
- Check Meta Ads Manager for any overnight ad account alerts, disapprovals, or budget pacing issues across multiple client accounts — each in a separate browser tab or profile.
- Check Google Analytics or Search Console for any anomalies.
- Check scheduled posts to make sure nothing failed overnight.
- Decide what fires need attention before the day's planned work starts.

**The problem:** There is no unified view. Everything requires a tab switch, a login, a context-switch. A client's brief is in Notion. Their campaign is in Meta. Their email campaign is in Mailchimp. Their Google Ads are in a separate MCC account. Their approved assets are in a shared Google Drive with a folder structure only the operator fully understands. None of this talks to each other.

By 10am, the operator has already spent 2 hours just getting oriented — before doing a single billable thing.

#### Mid-Morning: Deep Work (10:00am–1:00pm PHT)

This is the productive window. The operator does their highest-value work:

- Writing campaign strategy documents or content plans for clients.
- Drafting copy: Facebook ads, email sequences, landing page text.
- Reviewing creative from VAs or contractors before it goes to clients.
- Building or updating Google Ads or Meta Ads campaigns.
- Preparing a client presentation or monthly performance report.

**The problem:** Strategy work is the highest-value thing they do — the thing clients pay the most for and the thing competitors cannot easily replicate. But it is also the thing most often interrupted or compressed. Every context switch between clients costs 15–20 minutes of recovery time. A Slack message from Client B disrupts a strategy document being written for Client A. The operator cannot protect this block.

Additionally: generating strategy from scratch for every new client or campaign is exhausting and non-reusable. A campaign strategy written for a real estate client in Brisbane cannot be easily adapted for a mortgage broker in Sydney without manual reformatting, rebriefing, and context translation. Everything starts at zero.

#### Midday: Client Communication and Approvals (1:00pm–3:00pm PHT)

- Client calls (AU clients often book 12–2pm PHT for their 2–4pm AEST slots).
- Email responses and status updates.
- Sharing work for client review and chasing approvals.
- Revising work based on client feedback.

**The problem:** The approval loop is slow and manual. The operator emails or Slacks a draft. The client reviews it over 1–3 days. The operator follows up. The client gives vague feedback ("make it more exciting"). The operator revises and resubmits. This loop can consume 40–60% of a week on a single piece of content across all clients.

There is no structured approval surface. The feedback arrives in an email thread, or a voice note, or a comment on a Google Doc, or a WhatsApp message. The operator manually tracks what is approved, what is pending, and what needs revision — in their head or in a notes file.

#### Afternoon: Admin and Own-Business Work (3:00pm–6:00pm PHT)

- Invoicing and payment follow-ups (cross-border payments via Payoneer or Wise).
- Updating project trackers.
- Own-agency marketing: LinkedIn posts, proposals for prospective clients, case studies.
- Strategic thinking: which clients to grow, which to exit, what to offer next.

**The problem:** "Own-agency" work — the business development and marketing that should be growing their revenue — is always the last thing on the list. By 3pm the operator is cognitively depleted from client work. The work that would grow their business (content that demonstrates expertise, outreach to warm leads, referral cultivation) gets consistently deprioritized or done poorly because there is no energy left.

The operator knows this is the bottleneck. They read the LinkedIn posts about "working on your business vs. in your business." They simply have no capacity left to act on it.

---

### 4c.4 Current Tool Stack

| Category | Tools used | Pain |
|---|---|---|
| Client briefs & context | Google Docs, Notion | No memory between sessions; must re-read manually |
| Project management | Trello, Asana, ClickUp, or just Notion | Client context not connected to project tasks |
| Social scheduling | Buffer, Later, Metricool | Each client account is separate; no unified view |
| Ad management | Meta Ads Manager (separate Business Manager per client), Google Ads MCC | Tab-switching hell; no cross-client visibility |
| Email marketing | Mailchimp, ActiveCampaign, Klaviyo — varies per client | Separate logins; context in each platform only |
| Reporting | Manual — screenshot from each platform, paste into Google Slides or Canva | 2–5 hours per client per month |
| Creative | Canva, sometimes Adobe | Not connected to briefs or brand memory |
| Communication | Slack (some clients), email (most), WhatsApp (some) | Fragmented; feedback arrives in multiple channels |
| Storage | Google Drive (separate folder per client) | Works, but unstructured and requires context to navigate |
| Strategy documents | Google Docs | Not connected to execution; context resets per document |
| Payments | Payoneer, Wise | Works; friction on receiving side |

**The pattern:** Every tool is a silo. The operator is the connective tissue. When the operator's attention shifts, the system falls apart.

---

### 4c.5 Specific Pain Points (Ranked by Frequency and Severity)

| # | Pain | Frequency | Severity | What the operator says |
|---|---|---|---|---|
| 1 | **Context collapse between clients** | Daily | Critical | "I spent 45 minutes just re-reading briefs before I could start working." |
| 2 | **Rebuilding brand voice/tone every time** | Weekly | High | "I wrote great copy for Client A but I have to start from scratch for Client B even though the brief is similar." |
| 3 | **Approval loop latency** | Weekly | High | "I'm waiting on 3 client approvals for work I finished 5 days ago." |
| 4 | **Manual reporting** | Monthly | High | "Reports take me a full day every month and clients barely read them." |
| 5 | **Strategy work compressed by execution firefighting** | Daily | High | "I'm so busy doing the work that I can't think about whether we're doing the right work." |
| 6 | **Can't add more clients without dropping quality** | Ongoing | Critical | "I want to take on one more client but I literally don't have the hours." |
| 7 | **No persistent memory of what worked per client** | Ongoing | Medium | "I know what worked for Client C last quarter but it's somewhere in an email thread." |
| 8 | **Own-business development always last** | Ongoing | Medium | "My own LinkedIn hasn't had a post in 6 weeks." |
| 9 | **Time zone fatigue** | Daily | Medium | "AU clients expect morning replies. US clients send messages at midnight my time." |
| 10 | **Context-switching between browser profiles** | Daily | Low-Medium | "I have 4 Chrome profiles open — one per client — to keep Meta logins separate." |

---

### 4c.6 The Revenue Ceiling Problem

Archetype B is approaching or stuck at $8,000–$12,000 USD/month. They know why:

- They are billing time, not outcomes.
- Each new client adds roughly equal overhead to their cognitive load.
- Hiring contractors to "scale" just shifts the problem: now they are managing contractors plus clients, which adds more overhead.
- Raising rates helps but also increases the expectation of output and strategic depth.

The ceiling is not a skill ceiling. It is a **systems ceiling**. The operator who can hold 5 clients' context, produce strategy-level artifacts consistently, and reduce the approval cycle will be the one who breaks through to $15,000–$20,000/month without adding headcount.

**Klaroha's thesis for this operator:** Give them the operating system that holds the context, so they can focus on the judgment.

---

### 4c.7 The Klaroha "Aha Moment"

The moment Archetype B becomes a paying user is **not** when they see a feature list. It is when one of these things happens:

1. **Strategy generation moment:** They input a client's website URL and a one-line brief. Klaroha produces a strategy workflow with buyer map, messaging architecture, channel stack, and tactical funnel — work that previously took half a day. They think: *"This would have taken me until 2pm. It took 4 minutes."*

2. **Context memory moment:** They switch to a different client brand in BOS and the entire CMO context — brand voice, products, past campaigns, what the client approved and rejected — is already loaded. They type their first message and the response already knows the client. They think: *"I didn't have to re-read anything."*

3. **Approval loop moment:** They send a client an artifact from BOS. The client reviews and approves it in the same surface. The approved artifact is one click from publishing. The operator thinks: *"That usually takes a week of email back-and-forth."*

Any one of these three moments is sufficient. All three in the first week makes them a long-term customer.

---

### 4c.8 Pricing Rationale

| Tier | Price | How operator justifies it |
|---|---|---|
| Starter | $299/month | One client billing at $1,000–1,500/month. Klaroha needs to save 3–4 hours of strategy/admin time to justify itself. That is a conservative expectation. |
| Growth | $499/month | Operator has 4–6 clients. Klaroha needs to save 1 hour per client per month — easily cleared by context memory alone. |

**The operator does not think in subscription terms.** They think: *"If I can take on one extra client because BOS handles the overhead, that's $1,200/month in new revenue for $299/month in cost."* Frame pricing in terms of client capacity, not features.

---

### 4c.9 Acquisition Signals — How to Find This Person

| Signal | Where to look |
|---|---|
| PH-based, AU/UK/US clients | Upwork ("Philippines" + marketing + English clients), LinkedIn (PH location + digital marketing consultant) |
| Co-op member profile | Already inside the Klaroha cooperative structure — direct deployment path |
| Talks about context-switching or client management pain | Reddit r/marketing, r/freelance, r/PPC — specific threads about "managing multiple clients" |
| Posts about "hitting a ceiling" or "scaling without hiring" | LinkedIn posts from marketing consultants with 500–5,000 followers |
| Organizes work by client in Notion/Google Docs | Screams from their tool stack that they need a unified context system |
| Uses "CMO" in their own title or describes themselves as a "fractional CMO" | Direct match to Klaroha's positioning |

---

### 4c.10 Archetype B vs. Other Personas — Key Differences

| Dimension | Archetype B: Strategic Consultant | Archetype A: Execution Freelancer | Agency Owner (§2) |
|---|---|---|---|
| Primary value from Klaroha | Context memory + strategy acceleration | Output volume + scheduling | Team coordination + delivery ops |
| Willingness to pay | $299–$499/month | $99–$199/month | $499–$1,499/month |
| Decision speed | Days (individual decision) | Days (individual decision) | Weeks (may need to justify to team) |
| Time to first value | First strategy workflow output | First scheduled post | First client-approved artifact |
| Primary bottleneck | Cognitive overhead and context collapse | Execution speed and scheduling | Team coordination and approval loops |
| Risk of churn | Low if context memory works as expected | High if cheaper tools appear | Low if ROI is visible in reports |
| Beachhead fit | **Primary** | Secondary | Tertiary |

---

## 5. Weekly Operating Rhythm

### 5.1 Monday Planning

#### Operator Jobs

- Set week priorities.
- Review deliverable calendar.
- Confirm team ownership.
- Identify overloaded team members.
- Identify clients needing proactive communication.

#### BOS Requirements

- Weekly planner by brand/client/campaign.
- Work queue with due dates, owner, status, and blocker reason.
- Campaign plan artifacts connected to execution artifacts.
- Ability to ask: “What needs to happen this week for all active clients?”

#### Architecture Implications

- Need a deliverable/task object or plugin-backed task abstraction.
- Calendar and project-management plugins must connect to artifact and campaign state.
- Campaigns need planned deliverables, not only generated runs.

---

### 5.2 Midweek Health Check

#### Operator Jobs

- Detect churn signals.
- Review campaign pacing/performance.
- Check approvals and client responsiveness.
- Review pipeline and proposals.
- Reallocate team capacity if needed.

#### BOS Requirements

- Account health indicators:
  - Low client engagement
  - Slow approvals
  - Campaign underperformance
  - Repeated revision cycles
  - Missed deliverables
  - Scope creep
  - Payment/invoice risk when available
- Recommended actions:
  - Send proactive update
  - Schedule strategy call
  - Adjust creative
  - Escalate internally
  - Prepare upsell/renewal conversation

#### Architecture Implications

- Need cross-signal risk scoring.
- Need client/brand event timeline.
- Need campaign metrics ingestion from Meta/Google/YouTube/etc.
- Need explainable recommendations, not black-box scores.

---

### 5.3 Friday Close

#### Operator Jobs

- Review what shipped and slipped.
- Draft client reports.
- Document lessons learned.
- Check morale/blockers.
- Prepare Monday priorities.

#### BOS Requirements

- Weekly client report draft from actual activity and performance.
- Slippage report with reasons.
- Team workload summary.
- Case-study candidates from wins.

#### Architecture Implications

- Report generation should use structured campaign metrics, artifact history, and operator notes.
- Artifacts should be exportable to Drive as docs/decks/PDFs later.
- BOS should separate internal operator notes from client-facing content.

---

## 6. Monthly Operating Rhythm

### 6.1 Client Performance Review

#### Operator Jobs

- Review campaign results across all clients.
- Compare KPIs against targets.
- Identify underperforming accounts before clients do.
- Recommend next-month changes.

#### KPIs by Channel

| Channel | Common KPIs |
|---|---|
| Facebook/Instagram organic | Post volume, engagement, reach, clicks, follower growth |
| Facebook/Instagram ads | Spend, ROAS, CPA, CPL, CTR, CPM, frequency, conversion volume |
| YouTube | Views, watch time, retention, subscribers, CTR, engagement |
| Google Ads | Spend, CPC, conversions, CPA, search terms, impression share |
| Email | Sends, opens, clicks, replies, unsubscribes, conversions |
| SEO/content | Rankings, traffic, leads, content shipped, technical issues |

#### BOS Requirements

- Monthly report builder per client/brand.
- KPI targets stored per campaign/client.
- Automated insight generation:
  - What improved?
  - What declined?
  - Why might it have happened?
  - What should change next?
- Client-ready narrative with charts/tables.

#### Architecture Implications

- Need normalized metric ingestion by channel.
- Need a metric warehouse table keyed by brand, campaign, channel, date, and metric name.
- Need report artifacts with source data references.
- Need confidence/source annotations for AI-written insights.

---

### 6.2 Agency Business Health

#### Operator Jobs

- Review revenue vs. target.
- Review client profitability.
- Check utilization.
- Identify overdue invoices.
- Decide where to hire or reduce workload.

#### BOS Requirements

Initially this may be outside BOS, but architecture should leave room for:

- Client revenue and retainer data.
- Estimated delivery cost/time.
- Gross margin by client.
- Scope creep indicators.
- Renewal and churn forecast.

#### Architecture Implications

- Brand/client objects should eventually support commercial metadata:
  - retainer amount
  - contract start/end
  - renewal date
  - service package
  - account owner
  - strategic tier
- Task/deliverable history should support profitability analysis later.

---

### 6.3 People and Team

#### Operator Jobs

- Review workload.
- Run 1:1s.
- Identify skill gaps.
- Decide hiring needs.

#### BOS Requirements

- Owner assignment on deliverables/artifacts/tasks.
- Workload view by person.
- Bottleneck detection.
- Optional notes from team check-ins.

#### Architecture Implications

- Users/team members need roles and assignment relationships.
- Permissions must distinguish operator, staff, contractor, and client approver.

---

## 7. Quarterly Operating Rhythm

### 7.1 Strategy Review

#### Operator Jobs

- Check annual revenue progress.
- Review service-line performance.
- Review best/worst client verticals.
- Decide where to focus next quarter.

#### BOS Requirements

- Portfolio dashboard by client tier, revenue potential, performance, margin, and risk.
- Campaign/program retrospectives.
- Service-line reporting.
- Strategic recommendation brief.

#### Architecture Implications

- Need portfolio-level aggregation across brands.
- Need tags/categories for vertical, service line, package, and strategic priority.
- Need historical snapshots so the operator can compare quarter over quarter.

---

### 7.2 Client Portfolio Audit

#### Operator Jobs

- Tier clients by value and effort.
- Identify clients to upsell, right-size, or exit.
- Prepare renewal or renegotiation plans.

#### BOS Requirements

- Client tiering workflow.
- Client health scorecards.
- Renewal date tracking.
- Upsell recommendations based on gaps/wins.

#### Architecture Implications

- Client/account metadata must not be buried only in brand JSON.
- Need explicit account health/renewal objects or fields.
- Need CRM/project-management integration eventually.

---

### 7.3 Operations Review

#### Operator Jobs

- Identify process bottlenecks.
- Review tool stack.
- Decide hiring plan.
- Decide what services/processes to standardize.

#### BOS Requirements

- Delivery analytics:
  - average time from request to first draft
  - average time to approval
  - revision count
  - publish failure rate
  - blocked time by reason
- Plugin/integration health view.
- Process recommendations.

#### Architecture Implications

- Every lifecycle transition should emit an event.
- Integration failures should be typed and reportable.
- Artifact lineage should allow measuring rework and reuse.

---

## 8. Annual Operating Rhythm

### 8.1 Financial and Business Close

#### Operator Jobs

- Review annual P&L.
- Collect outstanding invoices.
- Review client profitability.
- Decide pricing changes.

#### BOS Requirements

Future-facing:

- Exportable annual client/account summary.
- Pricing/renewal recommendation support.
- Profitability notes by account.

---

### 8.2 Annual Client Review

#### Operator Jobs

- Build year-end performance decks.
- Prepare renewal conversations.
- Identify clients to grow or exit.

#### BOS Requirements

- Year-end report/deck generation.
- Campaign timeline of major wins, launches, and learnings.
- Asset gallery of best work.
- Renewal brief.

#### Architecture Implications

- Artifact and report storage must be durable and searchable.
- Drive export matters: client-facing decks/reports should land in the brand/client folder.
- Metrics and artifacts need long-term retention strategy.

---

### 8.3 Annual Team and Strategy Review

#### Operator Jobs

- Performance reviews.
- Compensation adjustments.
- Headcount planning.
- Annual goals and initiatives.

#### BOS Requirements

Later-stage:

- Team contribution summaries.
- Workload and bottleneck analytics.
- Strategic planning artifacts.

---

## 9. Critical End-to-End Workflows

These workflows should guide system architecture and acceptance tests.

### 9.1 Brand Onboarding to First Publish

1. Operator creates/selects a Brand.
2. Operator imports brand brief or fills brand profile.
3. BOS extracts brand profile, products, audiences, voice, values, handles, and site.
4. BOS generates Campaign Brand Kit.
5. Operator approves Brand Kit.
6. Operator connects Google Drive and picks root folder.
7. BOS creates/uses brand Drive subfolders.
8. Operator connects Facebook and/or YouTube.
9. Operator asks CMO to create a post/video.
10. CMO dispatches the correct capability.
11. Media provider generates asset.
12. Asset stores in Drive.
13. Operator reviews and approves artifact.
14. Operator explicitly publishes to Facebook/YouTube.
15. BOS reloads asset from Drive if temp file is gone.
16. Publish result is recorded with external post/video ID and link.

#### Acceptance Criteria

- No brand context leaks from another brand.
- Missing Drive/Facebook/YouTube connections produce clear setup blockers.
- CMO does not invent module IDs.
- CMO uses configured OpenAI premier/released model for reasoning/chat.
- Images/videos use configured ByteDance/BytePlus provider when selected.
- Artifact survives reload/browser refresh/container temp cleanup.
- Publish action is explicit and auditable.

---

### 9.2 Campaign Plan to Multi-Channel Assets

1. Operator asks for a campaign plan for a brand/objective.
2. BOS creates strategy/campaign artifact.
3. Operator approves or revises.
4. BOS derives creative briefs/assets for Facebook, YouTube, email, etc.
5. Assets are generated, stored, reviewed, and published/scheduled.
6. Performance metrics later attach back to the campaign.

#### Architecture Requirements

- Campaign plan artifact should be parent of downstream artifacts.
- Artifacts need lineage: source plan, source prompt, source run, revision history.
- Channel-specific outputs should share campaign metadata.
- Reporting should connect performance back to campaign objectives.

---

### 9.3 Client Weekly Report

1. Operator asks: “Prepare this week’s report for Client X.”
2. BOS loads brand, campaign, published artifacts, metrics, and notes.
3. BOS drafts report narrative.
4. Operator reviews and edits.
5. Report exports to Drive/client portal/email.

#### Architecture Requirements

- Weekly reporting should not rely on chat memory alone.
- Must query structured events, artifacts, and metrics.
- Report artifacts need status, approval, export location, and client-facing/internal distinction.

---

### 9.4 Failure Recovery

1. Publish fails or media generation fails.
2. BOS records structured failure reason.
3. Operator sees alert in command center/artifact card.
4. BOS recommends next action:
   - reconnect platform
   - select Drive root
   - add provider key
   - regenerate media
   - retry publish
5. Operator fixes and retries.

#### Architecture Requirements

- Failures need typed error codes, not only raw text.
- Credential and plugin readiness must be testable before execution.
- Retry should reuse the same artifact context when safe.

---

## 10. Data Model Requirements

The following entities should be first-class or intentionally mapped to existing tables.

| Entity | Purpose | Key fields / relationships |
|---|---|---|
| Workspace | Agency/business instance | name, settings, billing, owner |
| Brand / Client | Client brand/account | workspace_id, profile, commercial metadata, account owner |
| Product / Offer | What brand sells | brand_id, benefits, positioning, price/package later |
| Audience | Who brand sells to | brand_id, segment data, pain points |
| Brand Kit | Approved brand operating contract | brand_id, status, content, approval metadata |
| Campaign | Strategic initiative | brand_id, objective, dates, budget, status, parent plan |
| Artifact | Generated/reviewable output | brand_id, campaign_id, type, status, lineage, Drive refs, action modules |
| Run | Execution attempt | module_id, provider, trace, attempts, status |
| Approval | Human decision | artifact/run, actor, status, feedback, timestamp |
| Channel Connection | External platform credentials | brand_id, platform, status, token metadata |
| Provider Key / Backend Override | AI/media provider config | provider, model, modality, brand/workspace scope |
| Asset | Durable media/file object | Drive file ID, MIME, folder, thumbnail, reusable flag |
| Task / Deliverable | Work management object | owner, due date, status, blocker, source artifact/campaign |
| Metric | Performance datapoint | brand, campaign, channel, metric, date, value, source |
| Event | Timeline/audit item | actor/system, type, entity refs, timestamp, payload |
| Risk | Churn/delivery/performance risk | brand/client, severity, reason, recommended action |
| Report | Client/internal report artifact | period, source metrics, narrative, export path |

---

## 11. Integration Requirements

### 11.1 AI and Media Providers

| Need | Requirement |
|---|---|
| CMO reasoning/chat | First-class BYOK/login providers are OpenAI, Anthropic, and Gemini; model choices come from live provider catalogs and are capped to the top 3 practical text models, not stale hard-coded lists |
| Provider onboarding | Operators may bring API keys or supported login/OAuth; provider availability/auth mode must be discovered from backend provider metadata, not copied into each UI surface |
| Image generation | Use ByteDance/BytePlus when configured; support model override |
| Video generation | Use ByteDance/BytePlus Seedance/ModelArk when configured; support model override |
| Fallbacks | Fail gracefully with setup blockers; avoid silent wrong-provider fallback for media |
| BYOK/platform keys | Resolve workspace and brand-scoped credentials correctly |

### 11.2 Google Drive

| Need | Requirement |
|---|---|
| Root selection | Operator picks brand root folder via Google Picker |
| Asset storage | Generated media/report/deck artifacts store under brand root |
| Asset reload | Publish actions can download from Drive after temp files are gone |
| Browser | UI can navigate nested Drive folders and select images/videos |
| Audit | Artifact stores drive_file_id, link, folder, MIME, reusable flag |

### 11.3 Facebook / Meta

| Need | Requirement |
|---|---|
| Post images | Generate `creative.post.image`, store in Drive, approve, publish via Meta Photos/API |
| Post text | Preserve approved caption/message through publish |
| Video publish | Publish generated/reloaded MP4 to Facebook video endpoint |
| Credentials | Brand-scoped page token and page ID required |
| Safety | No direct publish unless explicit user approval/action |

### 11.4 YouTube

| Need | Requirement |
|---|---|
| Video publish | Publish generated/reloaded MP4 to YouTube |
| Metadata | Title, description, privacy, tags where available |
| Credentials | Brand-scoped YouTube OAuth upload token required |
| Image/community posts | Decide later; not core unless operator explicitly requires it |

### 11.5 Calendar / Project Management / CRM

Future but architecturally important:

- Calendar: deliverables, publish dates, client meetings.
- Project management: tasks, blockers, owners, status sync.
- CRM: leads, proposals, renewals, upsells.
- Finance: invoices, retainers, margin.

---

## 12. UI / Product Surface Requirements

| Surface | Primary job |
|---|---|
| CMO Chat | Natural-language command layer for strategy, generation, troubleshooting, summaries |
| Brand detail | Brand profile, products, audiences, brand kit, integrations, assets, campaigns |
| Command center | Daily priorities, alerts, approvals, deliverables, campaign health |
| Artifact feed | Review, revise, approve, publish, regenerate generated outputs |
| Drive browser | Select and reuse brand assets |
| Campaign workspace | Plan, assets, approvals, metrics, report history |
| Admin providers | Configure OpenAI/ByteDance/etc. by modality and target |
| Admin integrations | Activate plugins, connect channels, pick Drive root |
| Reports | Weekly/monthly/annual client-facing reports |
| Portfolio view | Agency-wide client health, revenue/margin/risk later |

---

## 13. Permissions and Safety Requirements

| Action | Requirement |
|---|---|
| Generate artifact | Staff/operator allowed if brand active and provider configured |
| Approve artifact | Operator/client approver role |
| Publish externally | Explicit approval and channel credential required |
| Change provider keys | Admin/operator only |
| Connect social accounts | Admin/operator, brand-scoped |
| Switch brand context | Must be explicit and visible |
| View client data | Role-scoped later; no cross-client leakage |
| Delete/archive artifact | Audited action |

Safety rules:

- Never publish automatically from a generation request.
- Never use another brand’s assets/context unless explicitly requested and permitted.
- Never hide credential/setup failures behind generic AI responses.
- Always store enough provenance to answer: who asked, what generated, what model/provider, who approved, where it published.

---

## 14. Non-Functional Requirements

| Requirement | Why it matters |
|---|---|
| Brand isolation | Agencies handle many clients; cross-brand leakage destroys trust |
| Durable artifacts | Operators reuse work and publish later; temp files are insufficient |
| Explainable failures | Operators need to fix blockers fast |
| Configurable providers | Media/AI vendor choices change often |
| Plugin architecture | Channels/tools vary by agency and client |
| Auditability | Publish/approval actions must be defensible |
| Fast command center | Morning workflow cannot wait on slow full scans |
| Incremental sync | Metrics/messages/assets should update without blocking UI |
| Graceful degradation | Missing integrations should still allow offline drafts/artifacts |

---

## 15. BOS Coverage Map

> Track which cadence items BOS already covers, partially covers, or is missing.
> Update this as features ship.

| Area | Cadence | BOS Today | Gap / Architecture Need |
|---|---|---|---|
| Brand profile | Onboarding | Partial | Must be strictly brand-scoped in multi-brand workspace |
| Campaign Brand Kit | Onboarding | Partial | Approval is required before full readiness |
| CMO chat | Daily | Partial | Must use configured/live OpenAI premier/released models |
| Plugin activation | Onboarding/Ops | Partial | Brand-scoped activation and readiness must be clean |
| Google Drive root | Onboarding/Ops | Partial | Needs connected Drive + root folder + nested asset discoverability |
| Image generation | Daily | Partial | ByteDance provider/key/model validation needed |
| Video generation | Daily | Partial | ByteDance/ModelArk video provider/key/model validation needed |
| Artifact approval | Daily | Partial | Needs unified artifact lifecycle and explicit approval state |
| Facebook image publish | Daily | Partial | Requires creative.post.image → Drive → approved action path |
| Facebook video publish | Daily | Partial | Requires Drive reload and Meta video action validation |
| YouTube video publish | Daily | Partial | Requires Drive reload and YouTube metadata validation |
| YouTube image/community | Daily | Missing | Decide scope; not currently supported |
| Campaign status | Daily | Partial | Needs at-a-glance health dashboard |
| Client messages | Daily | Missing | Need communication connectors/summaries later |
| Revenue dashboard | Daily/Monthly | Missing | Finance integration or commercial metadata later |
| Deliverable calendar | Weekly | Partial | Calendar plugin exists, not wired to deliverables/artifacts |
| Account health signals | Weekly | Missing | Need event/risk model and churn indicators |
| Pipeline / CRM | Weekly | Missing | CRM integration or lightweight pipeline objects |
| Campaign reporting | Monthly | Missing/Partial | Analytics plugins exist, no unified report generation |
| Business P&L | Monthly | Missing | Future finance/profitability model |
| Client portfolio audit | Quarterly | Missing | Need tiering/health/margin/renewal view |
| Year-end performance decks | Annual | Partial | Creative generation exists; no structured annual report/deck flow |

---

## 16. Suggested Architecture Priorities

### P0 — Trust and Execution Foundation

1. Brand-scoped onboarding and CMO context isolation.
2. Campaign Brand Kit approval as readiness gate.
3. Plugin activation/readiness correctness per brand.
4. AI provider selection from centralized provider metadata, with live top-3 model catalogs for OpenAI, Anthropic, and Gemini.
5. ByteDance/BytePlus provider credential resolution for image/video.
6. Google Drive root connection and durable artifact storage/reload.
7. Safe explicit publish actions for Facebook/YouTube.

### P1 — Operator Command Center

1. Daily alert/approval/work queue.
2. Campaign/artifact status dashboard.
3. Integration health dashboard.
4. End-of-day summary from structured events.

### P2 — Campaign and Reporting Plane

1. Campaign plan → downstream artifact lineage.
2. Metrics ingestion and normalized KPI table.
3. Weekly/monthly report artifacts.
4. Drive export for client-facing reports.

### P3 — Agency Business Operations

1. Client/account health scoring.
2. Deliverable calendar and PM sync.
3. CRM/pipeline integration.
4. Revenue/margin/client tiering.

---

## 17. Architectural Decision Checklist

Before shipping a feature, ask:

1. Is it brand-scoped?
2. Does it preserve artifact lineage?
3. Does it have clear lifecycle states?
4. Does it work after a page refresh/container restart?
5. Does it expose setup blockers clearly?
6. Does it avoid hard-coded provider/model/channel assumptions?
7. Does it emit events useful for daily/weekly/monthly summaries?
8. Can the CMO explain or act on it through chat?
9. Can the operator audit who approved/published what?
10. Does it help the operator answer one of the core operating questions?

---

## 18. The Underlying Rhythm

| Cadence | Core Question | BOS Answer |
|---|---|---|
| Daily | Is anything on fire right now? | Command center, alerts, approvals, failed actions |
| Weekly | Are we delivering what we promised? | Deliverable queue, campaign/artifact status, weekly reports |
| Monthly | Is the business healthy? | Campaign KPIs, client reports, profitability signals later |
| Quarterly | Are we building the right business? | Portfolio audit, service-line trends, client health |
| Annual | Did we become who we set out to be? | Annual reviews, performance decks, strategy planning |

---

## 19. Product North Star

BOS should let an agency operator start the day by asking:

> “What needs my attention across all clients?”

And end the day with confidence that:

- the right work shipped,
- the right work is queued,
- the right clients were updated,
- nothing critical is silently broken,
- generated assets are safely stored and reusable,
- publish actions are explicit and auditable,
- and every recommendation respects the active brand/client context.

---

## 20. State Machines

Formal state machines for the four core lifecycle objects. All state transitions must emit an event (see §21). Architecture decisions about schema, API endpoints, and UI surfaces should be grounded in these machines — not discovered ad hoc during implementation.

---

### 20.1 Campaign States

```
draft ──→ briefed ──→ in_progress ──→ needs_review ──→ approved ──→ live ──→ paused
                                            ↑                ↓                  ↓
                                            └── revision_requested ────────────┘
                                                                                ↓
                                                                           archived
```

| State | Entered when | Who triggers | Allowed exits |
|---|---|---|---|
| `draft` | Campaign row created | Operator | `briefed` |
| `briefed` | Objective and brief finalized | Operator | `in_progress` |
| `in_progress` | First deliverable dispatched | Auto or Operator | `needs_review` |
| `needs_review` | Operator marks ready for review | Operator | `approved`, `revision_requested` |
| `revision_requested` | Feedback attached; work sent back | Approver or Operator | `in_progress` |
| `approved` | Reviewer accepts the campaign | Approver or Operator | `live`, `revision_requested` |
| `live` | First artifact published | Auto on first publish | `paused`, `archived` |
| `paused` | Operator halts campaign | Operator | `live`, `archived` |
| `archived` | Campaign closed | Operator | Terminal |

---

### 20.2 Artifact States

An artifact is the operator-visible output. A run is the execution record behind it. An artifact may have multiple runs (original + revisions).

```
pending ──→ generating ──→ ready ──→ needs_review ──→ approved ──→ scheduled ──→ published
                  ↓                        ↓                                         ↓
               failed                   rejected                               superseded
                  ↓                        ↓
               (retry →                superseded
               pending)
```

| State | Meaning | Allowed exits |
|---|---|---|
| `pending` | Dispatch queued, not yet executing | `generating` |
| `generating` | Module actively executing | `ready`, `failed` |
| `ready` | Output available; not yet reviewed | `needs_review` |
| `needs_review` | Operator has opened it for review | `approved`, `rejected`, `revision_requested` |
| `approved` | Explicitly approved by operator/approver | `scheduled`, `published` |
| `scheduled` | Approved + scheduled for future send | `published` (on schedule), `rejected` (if recalled) |
| `published` | Live on external platform | `superseded` (if replaced by revision) |
| `rejected` | Rejected; revision creates a new artifact | `superseded` |
| `failed` | Module execution failed | `pending` (retry), Terminal (if abandoned) |
| `superseded` | Replaced by a newer version or revision | Terminal |

**Constraints:**
- Artifacts can never transition backward across `approved` → `needs_review`. A new approval decision creates a new artifact.
- `published` is terminal except for `superseded`. You cannot un-publish from within BOS — only the channel platform can remove it.
- A failed artifact must surface a typed failure reason, not only a generic error state.

---

### 20.3 Approval States

Approvals are immutable records. A new decision on a revision creates a new approval record — it does not mutate the prior one.

| State | Set by | Meaning |
|---|---|---|
| `pending` | Auto when artifact reaches `needs_review` | Awaiting operator/client decision |
| `approved` | Operator or designated approver | Work accepted; publish is unlocked |
| `rejected` | Operator or designated approver | Work not accepted; feedback field required |
| `revision_requested` | Operator or designated approver | Accepted with changes; triggers revision run with original artifact context |

---

### 20.4 Channel Connection States

Connection state must be checked at publish time, not only at capability activation.

| State | Meaning | System behavior |
|---|---|---|
| `connected` | Token valid and platform accessible | Allow publish actions |
| `needs_reauth` | Token expired or revoked | Surface `setup_blocker`; block publish |
| `missing_page` | Connected but page/channel/account not selected | Surface `setup_blocker` for platform-specific actions; allow non-publish generation |
| `missing_root` | Drive connected but root folder not set | Block Drive storage; surface picker |
| `disconnected` | Operator explicitly disconnected | Show connect CTA; block all platform actions |
| `error` | Unknown platform error | Surface typed error detail; allow reconnect attempt |

---

## 21. Event Catalog

Every state transition and significant system action must emit a typed event. These events are the data source for: command center alerts, end-of-day summaries, audit trails, CMO memory queries (“what happened with this campaign last week?”), and delivery analytics.

Each event carries: `event_type`, `occurred_at`, `actor` (user_id or “system”), `workspace_id`, and entity refs for the affected objects.

---

### 21.1 Brand and Account Events

| Event | Key payload fields | Consumers |
|---|---|---|
| `brand.created` | brand_id, name | Onboarding trigger |
| `brand.profile_updated` | brand_id, fields_changed | CMO context refresh signal |
| `brand_kit.generated` | brand_id, run_id | Alert operator for review |
| `brand_kit.approved` | brand_id, approval_id | Readiness gate cleared; CMO unlocked |
| `brand_kit.rejected` | brand_id, approval_id, feedback | Revision trigger |
| `integration.connected` | brand_id, platform, connection_id | Capability unlock; setup checklist update |
| `integration.token_expired` | brand_id, platform | Command center alert; publish blocked |
| `integration.disconnected` | brand_id, platform, reason | Capability blocked; setup CTA surface |

---

### 21.2 Campaign Events

| Event | Key payload fields | Consumers |
|---|---|---|
| `campaign.created` | campaign_id, brand_id, objective | Delivery queue item |
| `campaign.status_changed` | campaign_id, from_status, to_status, actor | Activity ledger; command center |
| `campaign.deliverable_added` | campaign_id, artifact_id | Work queue update |
| `campaign.past_due` | campaign_id, due_date, pending_count | Command center alert |

---

### 21.3 Artifact and Run Events

| Event | Key payload fields | Consumers |
|---|---|---|
| `run.dispatched` | run_id, module_id, brand_id, campaign_id | Execution tracking |
| `run.completed` | run_id, artifact_id, duration_ms | Artifact ready alert |
| `run.failed` | run_id, error_code, reason, module_id | Command center error; retry prompt |
| `artifact.reviewed` | artifact_id, actor | Review tracking |
| `artifact.approved` | artifact_id, approval_id, approver_id | Publish unlock; audit trail |
| `artifact.rejected` | artifact_id, approval_id, approver_id, feedback | Revision trigger |
| `artifact.revision_requested` | artifact_id, feedback, source_artifact_id | New run dispatch; lineage link |
| `artifact.scheduled` | artifact_id, scheduled_at, channel | Calendar item |
| `artifact.published` | artifact_id, channel, external_id, external_url, published_at | Publish audit; performance attach point |
| `artifact.publish_failed` | artifact_id, channel, error_code, reason | Command center alert; retry prompt |
| `artifact.stored_in_drive` | artifact_id, drive_file_id, folder_path, mime_type | Drive audit; reload reference |
| `artifact.superseded` | artifact_id, superseded_by_artifact_id | Lineage chain |

---

### 21.4 Credential and Plugin Events

| Event | Key payload fields | Consumers |
|---|---|---|
| `credential.added` | scope (workspace/brand), provider, modality | Capability unlock; manifest refresh |
| `credential.rotated` | scope, provider | Audit trail |
| `credential.removed` | scope, provider | Capability blocked alert |
| `plugin.activated` | plugin_id, brand_id | CMO manifest refresh |
| `plugin.deactivated` | plugin_id, brand_id | CMO manifest refresh |
| `provider.override_set` | brand_id, modality, provider, model | Execution routing change |

---

### 21.5 Event Retention and Query Requirements

- All events must be queryable by: `workspace_id`, `brand_id`, `entity_type + entity_id`, `event_type`, `occurred_at` range.
- Command center queries must run in < 500ms for the current day's events. Index accordingly.
- End-of-day and weekly summary queries may tolerate up to 3s for multi-brand aggregations.
- Events are append-only. No event may be deleted or mutated after creation.

---

## 22. Architectural Invariants

These are conditions that must never be true. Violation of any invariant is an architectural regression requiring review before merge. They are derived directly from the operator journeys and the failure modes that most damage trust.

---

### 22.1 Brand Isolation Invariants

**I-01: No artifact may be created with `brand_id = NULL` in a multi-brand workspace.**
A run dispatched under Brand A must produce an artifact with `brand_id = Brand A`. Null brand_id artifacts are only valid in single-brand workspaces. If brand cannot be resolved at dispatch time, dispatch must be blocked and the CMO must surface a brand clarification request.

**I-02: No query on a scoped surface may return artifacts, runs, metrics, or tasks from a brand the current session is not scoped to.**
The command center, Stream, campaigns view, and approval queue must all be brand-scoped. Cross-brand rows in any of these surfaces constitute a data boundary violation.

**I-03: CMO context hydration with an active brand must never call `_resolve_brief()`.**
`_resolve_brief()` is workspace-scoped and will bleed Brand B's products and audiences into Brand A's session. `_brand_scoped_brief()` is required when a brand is active. This applies to both the initial dispatch and the revise endpoint.

**I-04: Brand Kit from one brand must never be loaded into a CMO session for another brand.**
Brand Kit `brand_id` must be checked before injection. A workspace with Brand Kit A and no Brand Kit B must not let Brand A's kit substitute for Brand B.

---

### 22.2 Publish Safety Invariants

**I-05: A publish action must never execute without a recorded approval.**
Auto-generation + auto-publish in a single round trip is forbidden regardless of module configuration. The artifact must reach `approved` state via an explicit human action before any publish action may run.

**I-06: Publish must reload the asset from Drive if the temp file is unavailable.**
Temp file paths are not durable across container restarts. If `artifact.drive_file_id` is set, the publish module must download from Drive rather than reading a local path. Publishing a blank or missing file silently is a data integrity failure.

**I-07: Every publish attempt — success or failure — must emit `artifact.published` or `artifact.publish_failed`.**
Silent publish failures (no event, no alert, no status update) are the most trust-destroying failure mode for an agency operator. There is no acceptable case where a publish attempt leaves no trace.

**I-08: A channel credential must be in `connected` state at publish time.**
Integration state must be re-evaluated at publish execution, not assumed valid from activation time. A token that expired between activation and publish must surface a typed `needs_reauth` blocker, not a generic API error.

---

### 22.3 Provider and Credential Invariants

**I-09: Provider API key values must never appear in logs, API responses, traces, or error messages.**
Keys must be AES-256 encrypted at rest and redacted at all read/write boundaries.

**I-10: A media module must not silently fall back to a different provider when the configured provider is unavailable.**
Silent fallback means the operator receives media generated by a provider they did not configure or pay for. The module must fail with a typed error: `provider_unreachable`, `key_invalid`, or `model_unavailable`, and surface a setup blocker.

**I-11: Plugin modules must not read credentials from the database or environment variables directly.**
All credentials must arrive via `brief[“_channel_credentials”]` from `inject_channel_credentials()`. A plugin that bypasses this mechanism cannot be audited, rotated, or scoped correctly.

---

### 22.4 Lineage and Audit Invariants

**I-12: Every artifact must have non-null `brand_id`, `source_run_id`, and `created_at` at creation.**
These three fields are the minimum provenance required to answer: who's brand, what execution, when. NULL in any of them means the artifact is untracked and cannot be audited, reported on, or safely reused.

**I-13: A revision creates a new artifact; it never mutates the original.**
The original artifact must be transitioned to `superseded` and linked to the revision via `superseded_by_artifact_id`. Revision history must be traversable forward and backward.

**I-14: Approval records are immutable after creation.**
An approval record cannot be edited. If an operator changes their mind, they submit a new decision on the revised artifact, which creates a new approval record. The original approval record stands as the historical fact.

**I-15: Artifact lineage must include: source prompt, source run, source module, brand at generation time, and campaign if set.**
These fields must be stored at artifact creation, not reconstructed from chat history. Chat history is volatile; artifact lineage is the system of record.
