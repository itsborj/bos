# Campaign V2 — Unified Campaign Source of Truth

> Status: working replacement contract
> Date: 2026-07-10
> Supersedes the wrong assumption in `docs/campaign.md` that campaign truth can be assembled from separate memory, brief, report, run, and snapshot surfaces.
>
> Core correction: if someone wants to know about a campaign, they should open/query **Campaign**. They should not hunt through CampaignMemory, daily brief payloads, reports, run traces, chat history, or specialized helper functions.

---

## 1. Campaign is the source of truth

A campaign is the shared operating record used by CMO, senior marketers, junior marketers, data validators, and operators.

The campaign record must hold the same practical structure a real marketing team would keep in its shared campaign spreadsheet:

```text
Campaign
+ Objective
+ Distribution Channel
+ Time Period
+ Snapshot
+ Verdict
```

This is the campaign memory, whether or not the code calls it memory.

Do not bury campaign truth under specialized services or derived artifacts. Those can feed or render the campaign, but they are not the place people should have to search for campaign truth.

---

## 2. One shape for lean launch and omni-channel scale

A lean validation campaign and a mature omni-channel campaign use the same rows and columns.

The only difference is row volume:

- lean launch: fewer distribution channels, fewer snapshots
- full omni-channel campaign: more distribution channels, more snapshots
- long-running campaign: deeper history

The data shape does not change.

```text
Lean campaign
  campaign + objective + 2-4 channels + dated snapshots + verdicts

Mature omni-channel campaign
  campaign + objective + many channels + dated snapshots + verdicts

5-year effective campaign
  same campaign + objective history + many dated snapshots + verdicts over time
```

---

## 3. Universal campaign row/column contract

Every campaign must expose a stable sheet-like operating structure.

Minimum campaign operating-sheet columns:

```text
period / date / week
brand
campaign
market
channel / distribution_channel
objective / business_objective
primary_kpi
target
actual
reach_metric
engagement_metric
action_metric
spend / cost
efficiency_metric
value_metric
top_learning
what_changed
recommended_action
decision_needed
next_action
owner
note
source / producer
last_updated
```

The sheet may also keep comparable numeric columns where useful:

```text
reach
impressions
engagement
engagement_rate
clicks
leads
calls
qualified_calls
conversions
budget
revenue
```

Those numeric columns are optional supporting columns, not the universal meaning
of every campaign. For one campaign, `action_metric` may mean bookings; for
another it may mean orders, demos, partner signups, pipeline, or sell-through.
The provider/channel must validate and report the metric; Campaign stores the
reported management update.

The exact physical schema may split durable identity fields across Campaign,
Objective, Activation, and Snapshot tables, but the operating sheet must expose
one stable Campaign row shape. Daily, weekly, monthly, and quarterly campaign
views are filters or rollups over these same rows, not separate truth models.

If a CMO, operator, validator, dashboard, or client meeting view filters, sorts,
compares, verifies, or decides on the value, it cannot live only in JSON or
prose. Strategic interpretation belongs to the CMO synthesis layer unless
recorded deliberately as `top_learning`, `recommended_action`, `decision_needed`,
`next_action`, or `note` on the operating sheet. Campaign must not process raw
channel complexity; providers and channel owners validate their own data and
write the normalized reported update.

The key field is:

```text
objective_verdict = true | false | inconclusive | needs_data
```

Every campaign row exists to help answer:

> Is this campaign, through this channel and period, helping us hit the business objective?

---

## 4. What the campaign must answer

For a CMO managing hundreds of brands and thousands of campaigns, the campaign
source must answer quickly in the language of a daily marketing report:

1. What changed since the last pull, meeting, or reporting period?
2. Which campaigns, markets, and channels are carrying the objective?
3. Which campaigns, markets, and channels need a decision or next move?
4. What is the primary KPI, target, actual result, and meaningful action metric?
5. What was the top learning and recommended action?
6. Who owns the next action and by when?

For junior marketing and channel operators, the same source must answer:

1. Which rows need today’s provider/channel update?
2. Which campaign/market/channel rows are missing a provider-validated update?
3. Which notes, learnings, recommendations, and decisions must be cleaned up before the CMO meeting?
4. Which evidence/report/source produced the update if someone asks for proof?
5. What must be fixed before the CMO can discuss the campaign intelligently?

Same campaign data. Different views/filters.

### 4a. CMO client-meeting operating brief

For an agency CMO managing hundreds of brands and thousands of campaigns, the
Campaign source must produce a meeting-ready operating brief without requiring
the CMO to reconstruct truth from reports, chat history, dashboards, memory, or
raw channel tools.

Before a client meeting, the CMO should be able to pull:

```text
brand / client context
active campaigns for that brand
period / date / week
campaign objective
market
channel / distribution_channel
primary KPI
target
actual
reach metric
engagement metric
action metric
spend / cost where applicable
efficiency metric where applicable
value metric where applicable
top learning
what changed since last pull or last meeting
recommended action
decision needed
next action
owner
note
source / producer
last updated
```

The meeting payload should answer:

```text
What is the campaign supposed to accomplish?
What is the campaign supposed to accomplish?
What happened this period in reach, engagement, and action terms as defined by this campaign?
Which markets/channels are carrying the objective?
Which markets/channels need a move?
What changed since the last client conversation?
What did we learn?
What can the agency recommend now?
What decision does the client/operator need to make?
Who owns the next action?
```

The CMO answer may be conversational and strategic. The underlying data must be
structured Campaign rows. The CMO should synthesize interpretation,
recommendations, and optimization next steps from Campaign rows against the
business objective, not search separate systems and invent a narrative from
partial memory.

### 4b. Portfolio-scale attention

Campaign must also support portfolio-level triage across many brands and
campaigns. The CMO needs to know what deserves attention before the client asks.

Required portfolio filters and rollups include:

```text
brand
campaign
market
channel
status
primary_kpi
target
actual
action_metric
spend / cost
efficiency_metric
value_metric
top_learning
recommended_action
owner
due_date
decision_needed
last_updated
```

Useful rollups include:

```text
active_campaign_count
campaigns_updated_today
campaigns_missing_period_update
open_decisions_count
upcoming_due_actions
markets_or_channels_needing_action
top_reach_movers
top_engagement_movers
top_action_movers
budget_or_cost_exceptions
```

These rollups are views over Campaign truth. They are not a separate truth
surface.

---

## 5. Campaign-centric BOS

BOS is campaign-centric.

Campaign is the unified source of truth for marketing execution and validation. Plugins, channels, creative tools, reports, staff updates, call-center feeds, and app surfaces are contributors or consumers — not competing sources of campaign truth.

The operating model is:

```text
campaign/ owns Campaign truth and row contracts.
plugins/* own channel execution/evidence.
artifacts/ owns artifact lifecycle/evidence objects if foundational.
cmo/ owns synthesis and recommendations.
api/ only mounts vertical APIs.
Campaign is where campaign-relevant output lands as normalized rows.
```

A plugin should never become the source of truth for marketing work. Meta, Google Ads, YouTube, Postcraft, Drive, email, analytics, call-center imports, and future channels are distribution/evidence contributors. They may be installed, removed, disabled, replaced, or fail entirely; Campaign persists.

The operator should not think:

```text
go to Meta for Meta truth
go to Postcraft for creative truth
go to daily brief for summary truth
go to memory for historical truth
go to Stream for artifact truth
```

They should think:

```text
Open Campaign.
Everything campaign-relevant is there.
```

---

## 6. Inputs and views

Campaign is the truth surface.

Everything else is either an input or a view.

### Inputs that feed Campaign

```text
channel reports
manual data pulls
chat updates
published artifact proof
call center data
CRM data
operator decisions
client feedback
run outputs
plugin outputs
staff/operator updates
source freshness checks
verification notes
```

Every input should answer, when applicable:

```text
Which campaign does this serve?
Which objective does it support?
Which distribution channel did it affect?
Which time period does it belong to?
What snapshot/evidence did it produce?
What is the verdict against the objective, or why is verdict still needs_data/inconclusive?
```

If an input cannot answer those questions, it remains one of:

```text
unassigned brand-foundation work
draft/raw artifact
raw channel evidence
setup/admin activity
```

It is not campaign truth yet.

### Views that read Campaign

```text
daily brief
CMO chat answer
campaign overview
junior verification board
Q4 pacing dashboard
report artifact
prompt context
Stream artifact grouping
```

None of these views should become a separate source of campaign truth.

---

## 7. Existing BOS surfaces demoted

The following are not the campaign source of truth:

- `CampaignMemory`
- `memory_events`
- `campaigns.memory_snapshot`
- `daily_briefs.payload`
- report JSON
- run traces
- chat history

Their correct roles after the 2026-07-15 delete-test cutover:

```text
CampaignMemory            = removed from active runtime; do not recreate
memory_events             = append-only audit/history input, not Campaign truth
campaigns.memory_snapshot = removed from active runtime; do not recreate
daily_briefs.payload      = removed from active runtime; do not recreate as campaign truth
reports                   = evidence inputs
runs/run_results          = artifact and execution evidence
chat                      = input/output surface
```

The user-facing and product-facing answer to “where does campaign data live?” must be:

```text
Campaign.
```

---

## 8. Campaign objective persistence

A campaign can persist for years if it continues to serve the business objective.

Do not split a campaign just because channels, assets, or time periods change. The durable spine is:

```text
campaign
→ business objective
→ distribution/channel rows
→ dated snapshots
→ verdicts against objective
```

If the business objective changes materially, preserve objective history. The campaign should remain understandable at week 1, Q4, or year 5 by reading the same campaign source.

---

## 9. Decision rule

The campaign record must support fast true/false assessment against the business objective:

```text
true         = evidence supports the objective
false        = evidence does not support the objective
inconclusive = evidence is partial or mixed
needs_data   = source freshness/verification is insufficient
```

Missing data is not zero performance. It is a source/freshness/verification state.

---

## 10. Scale stress test — Nike and the dentist use the same shape

The campaign source-of-truth shape must work for both a multinational brand and a small local business.

The shape stays the same:

```text
Campaign + Objective + Distribution Channel + Time Period + Snapshot + Verdict
```

Only the number of rows, users, permissions, channels, regions, and history depth changes.

### Multinational example

For a brand like Nike:

```text
Campaign: Air Max Q4 Global Push
Objective: Increase sell-through of Air Max line in Q4
Success metric: regional sell-through, ecommerce conversion, store traffic, brand lift
```

Distribution/snapshot rows might include:

```text
North America / Meta Paid / Week 42
North America / TikTok Organic / Week 42
North America / Retail Partner / Week 42
EMEA / YouTube / Week 42
Japan / Influencer / Week 42
SEA / Email / Week 42
Global / Website / Week 42
Retail / Foot Locker / Week 42
```

Inputs come from many producers:

```text
paid media plugins
retail sell-through CSVs
regional agency uploads
influencer reports
CRM/email systems
ecommerce analytics
operator decisions
junior data validation
```

The campaign can roll up to:

```text
Q4 forecast: on track globally
Gap: EMEA underperforming by 8%
Cause: high reach, low conversion
Decision: localize offer and shift spend from YouTube to search/retail retargeting
Owner: EMEA growth lead
```

Nike needs more rows, regions, permissions, rollups, and verification states — not a different campaign model.

### Local business example

For a dentist across the street:

```text
Campaign: New Patient Whitening Promo
Objective: Book 30 qualified new patient appointments this quarter
Success metric: confirmed appointments
```

Distribution/snapshot rows might include:

```text
Google Search / Week 1
Meta Local / Week 1
Website Form / Week 1
Phone Calls / Week 1
Front Desk Notes / Week 1
```

Inputs are simpler:

```text
Google Ads pull
Meta lead/reach pull
receptionist call notes
website form submissions
owner lead-quality feedback
```

The campaign can say:

```text
Google Search: true — 8 booked appointments
Meta Local: false — cheap leads but low quality
Phone Calls: true — call volume up
Website Form: needs_data — form tracking broken

Decision: keep Google Search, pause Meta lead form, fix website tracking, create one testimonial post.
```

The dentist sees fewer rows and simpler language. The model is the same.

### Product principle

Campaign should behave like a spreadsheet with infinite scale:

```text
Dentist gets 5 rows.
Nike gets 50,000 rows.
Both know where campaign truth lives.
```

Enterprise does not need a different truth model; it needs rollups, permissions, regions, ownership, and volume handling. Small business does not need a different truth model; it needs the same campaign source rendered simply.

---

## 11. Channel reports, raw datasets, and consolidated snapshots

Channels and humans can produce data at very different levels of cleanliness.

Examples:

```text
Meta paid performance report
Meta organic performance report
Google Ads report
Search Console / SEO report
GA4 website report
email report
call-center export
CRM lead-quality export
manual junior data pull
client/operator correction
```

Each channel should be allowed to generate its own report artifact. A channel report is the channel's best account of what happened on that platform/source. It is evidence, not campaign truth by itself.

A produced or uploaded dataset may be:

```text
small and clean: 10 rows x 10 columns, ready for insight
large and raw: millions of rows requiring processing by a specialist system
partial: only reach/engagement, no conversion data
messy: duplicated rows, missing attribution, mixed campaigns
blocked: source unavailable or stale
```

BOS should not force all producers to emit perfect campaign rows immediately. The campaign-centric rule is that every input eventually moves through a normalization path:

```text
raw source data / channel report / human update
→ source-owned report artifact
→ optional consolidator/cleaning snapshot
→ campaign row: Campaign + Objective + Channel + Period + Snapshot + Verdict
```

### Channel-owned report

A channel/plugin report owns source-specific detail:

```text
platform metrics
raw rows or files
source account/page/campaign ids
API freshness
platform-specific warnings
raw evidence refs
```

This report may be rich and platform-native. It can include data that Campaign does not store directly.

### Consolidator snapshot

A consolidator may be created to clean, normalize, and organize metrics so rows are easier to compare across channels.

Its job is not to create a competing truth surface. Its job is to turn messy source evidence into the campaign sheet shape:

```text
standard metric names
period alignment
channel labels
campaign/objective binding
source health
verification status
confidence
comparable row shape
```

The consolidator can handle either:

```text
a simple 10-row channel report
or
a million-row raw dump that requires processing by another specialist
```

In both cases, the final normalized output feeds Campaign.

### Campaign impact

Once normalized, the data affects Campaign by appending or updating a campaign snapshot row:

```text
campaign_id
objective_id
distribution_channel
time_period
planned_activity
actual_activity
metrics
source_health
verification_status
what_changed
objective_verdict
confidence
blocker
decision_needed
next_action
```

The campaign source then becomes the place where CMO, juniors, validators, clients, operators, and other systems see the consequence of that data.

### Anti-reversion rule

Do not make channel reports, raw data files, or consolidator outputs the place users must search for campaign truth. They are evidence and processing artifacts. Campaign is where the normalized consequence lands.

---

## 12. Daily brief demotion — Campaign snapshot is already the brief

If Campaign owns the concise operating snapshot, then a separate daily brief is not required as a truth artifact.

The campaign source itself should be compact enough to support daily decision-making:

```text
campaign
objective
channel / period
latest snapshot
source health
verification status
objective verdict
what changed
blocker
next action
owner
```

A daily brief may still exist as a rendered view, notification, email, or chat summary, but it must not be a separate campaign data product. It should simply read the current Campaign snapshot and phrase it for the operator.

```text
Campaign = truth / operating sheet
Daily brief = optional rendering of Campaign
```

### Producer-owned truth

Campaign should not need to understand or validate every producer's raw complexity.

Each producer is responsible for validating its own data before reporting to Campaign:

```text
Meta plugin validates Meta pull complexity.
Google Ads plugin validates Google Ads pull complexity.
SEO plugin validates Search Console / SEO complexity.
Call-center importer validates call data complexity.
Junior marketer validates manual pull complexity.
Consolidator validates normalization complexity.
```

The producer reports its best truth to Campaign:

```text
up 12%
down 15%
null / unavailable
source stale
blocked
verified
unverified
confidence low / medium / high
```

Campaign records that reported truth with provenance. It does not re-process every raw source by default. If a producer reports `null`, that is the campaign truth for that source/period until a later producer correction or replacement snapshot supersedes it. If a producer reports `-15%`, Campaign treats that as the current reported truth with the attached source health, verification status, confidence, and evidence reference.

This keeps Campaign thin while preserving accountability:

```text
Producer owns source complexity.
Campaign owns unified operating truth.
Consumers read Campaign.
```

---

## 13. Database-first truth directive

Campaign memory must be database-first, not JSON-only.

Campaign V2 has one source of truth:

```text
canonical Campaign DB tables / rows
```

JSON is allowed only as supporting payload:

```text
raw source evidence
plugin-specific details
producer metadata
cached/rendered view payloads
```

It is not a second source of truth.

Rule:

```text
If CMO, junior marketer, operator, validator, dashboard, or chat filters/sorts/compares/verifies/decides on it, it must be a first-class DB column.
If only the producer/plugin understands it, it may live in JSON as evidence.
```

Example canonical Campaign row fields:

```text
campaign_id
objective_id
time_period
market
distribution_channel
business_objective
primary_kpi
target
actual
reach_metric
engagement_metric
action_metric
spend
efficiency_metric
value_metric
top_learning
what_changed
recommended_action
decision_needed
owner
next_action
note
producer
source_ref
```

Comparable numeric fields such as `reach`, `impressions`, `engagement`,
`clicks`, `leads`, `calls`, `qualified_calls`, `conversions`, `budget`, and
`revenue` may exist for dashboards, but they are supporting columns. The daily
CMO meeting shape is the provider-validated campaign report row above.

Example supporting JSON:

```text
raw_meta_response
post_breakdown
platform_api_warnings
producer_native_payload
```

Conflict rule:

```text
Canonical DB columns win.
JSON explains where the reported truth came from.
```

The architecture is:

```text
Producer validates data
→ Producer writes canonical campaign row columns
→ Producer may attach raw JSON evidence
→ Consumers read canonical campaign rows
```

Not:

```text
Campaign DB columns sometimes
JSON sometimes
daily brief sometimes
memory snapshot sometimes
```

One truth:

```text
Campaign.
```

---

## 14. What is not migrating from `campaign.md`

The old `campaign.md` contains useful history, but several assumptions do not migrate into Campaign V2.

### Not migrating as source of truth

These may remain only as legacy evidence stores, rendered views, or historical implementation details until removed. They must not become compatibility shims for Campaign behavior, and they are not campaign truth:

```text
CampaignMemory as campaign truth owner
memory_events as the place to reconstruct current campaign truth
campaigns.memory_snapshot as active truth
daily_briefs.payload as a campaign data product
cmo_working_context@v1 as a truth document
campaign_overview@v1 assembled from many surfaces as truth
report JSON / run traces / chat history as truth surfaces
```

Campaign V2 replaces the hunt across those surfaces with one Campaign operating sheet.

### Not migrating as product architecture

Do not migrate these old patterns as the new product center:

```text
daily brief as the authoritative attention/router layer
hot/warm/cold memory retrieval as the primary campaign model
primitive taxonomy as the campaign data model
append-only memory → prompt snapshot → daily projection as the source-of-truth path
weekly production_guidance as a separate durable truth layer
Campaign Zero / brand foundation as a pseudo-campaign
manual dropdown/global selected campaign as the default operating model
LLM or keyword phrase matching as campaign resolver
```

Some of the ideas remain useful only after translation:

```text
hot/warm/cold      → filters/views over Campaign history
memory events      → audit/provenance inputs
production guidance → a campaign row/verdict/decision field or producer report output
daily brief        → optional rendering of Campaign
working context    → prompt view over Campaign
campaign overview  → UI view over Campaign
brand foundation   → input for unassigned drafts, not campaign truth
```

### Not migrating as data ownership

Do not make BOS Campaign responsible for understanding every raw platform schema.

Old direction sometimes implied that campaign memory/daily brief would extract, interpret, promote, and own normalized insight. Campaign V2 assigns that responsibility to the producer or specialist:

```text
producer validates source complexity
producer reports its best truth
Campaign records the reported truth with provenance
Campaign exposes the current operating truth
consumers read Campaign
```

If Meta, Google Ads, SEO, CRM, call center, or a human validator reports `up 12%`, `down 15%`, `null`, `stale`, `blocked`, or `verified`, Campaign records that reported truth for the relevant objective/channel/period. A later correction supersedes it; Campaign does not silently re-derive it from raw data.

### Not migrating as code agenda

The detailed old-session agenda in `campaign.md` remains historical. Do not treat these as V2 marching orders unless revalidated against this document:

```text
expanding update_campaign_memory as the primary write surface
building more daily_brief sections
making campaign_alignment@v1 the campaign truth envelope
patching phrase allowlists for campaign lookup
adding more prompt-injection rules to preserve entity fidelity
repairing old POST /campaigns/{id}/run flows
```

The V2 build path should start from simple Campaign table access instead:

```text
campaign.read   # read dated rows
campaign.write  # write dated rows
campaign.edit   # correct/verify/supersede dated rows
```

---

## 15. Strict vertical implementation direction

Implementation must follow `klaroha.md` vertical ownership. Database-first does
not mean placing Campaign DB logic under the fat `api/` dump.

The work should be organized around one principle:

> Build one Campaign vertical that owns the Campaign tables, row contract,
> read/write primitives, tools, and API adapter. Then make daily brief, CMO
> context, campaign overview, verification boards, Stream grouping, and report
> artifacts read from Campaign.

Do not expand specialized memory functions first. Do not add another parallel
campaign truth store. Do not require users or developers to know which subsystem
contains the latest campaign fact.

Campaign must be treated as a non-removable product vertical, not a specialized
API feature function. Channels can be plugins. Creative tools can be plugins.
Analytics sources can be plugins. Campaign remains the durable center that
records transitions from staff, operators, marketing channels, plugins, and
system events.

### Strict vertical refactor slice

The first code slice should establish Campaign as an isolated database-owned
vertical, with no Campaign behavior added to `api/routers`, `api/services`,
`api/schemas`, mixed `api/models` files, CMO files, plugin files, or generic UI
shell files.

The implementation should stay intentionally small:

```text
api/
  campaign/               = isolated Campaign vertical; runtime package name is `campaign`
    table.py              = Campaign identity + dated Campaign row definitions / indexes
    db.py                 = direct database read/write/edit/filter helpers
    api.py                = optional thin HTTP adapter for browser/external access only
    tests/                = verifies persistence, isolation, history, and reroute removal
  main.py                 = host app mounts campaign/api.py only when HTTP access is needed
```

The repository path is inside `api/` so the existing API Docker build context
packages the vertical. This does not make Campaign part of the generic API dump:
Campaign remains its own import package and owns its tables, behavior, adapter,
and tests.

Current Campaign-owned HTTP adapter surface:

```text
GET    /api/campaigns
POST   /api/campaigns
GET    /api/campaigns/rows
POST   /api/campaigns/rows
PATCH  /api/campaigns/rows/{row_id}
GET    /api/campaigns/{campaign_id}
PATCH  /api/campaigns/{campaign_id}
DELETE /api/campaigns/{campaign_id}
GET    /api/campaigns/{campaign_id}/sheet
POST   /api/campaigns/{campaign_id}/rows
```

`/api/campaigns/{campaign_id}/snapshots` is intentionally not part of the
current contract. A dated Campaign fact is a Campaign row. If product language
says "snapshot", it refers to a dated row in `campaign_rows`, not a separate
`campaign_snapshots` runtime path.

Internal BOS systems such as CMO, onboarding, producers, and plugins should use
`campaign/db.py` directly. They should not call Campaign through HTTP unless
they are actually crossing a network/client boundary.

A Campaign is a dated operating table. The useful system behavior in `campaign/db.py` is:

```text
read rows
write rows
edit/supersede rows
filter by brand / campaign / objective / channel / date range / period type
return rows to whichever system needs them
```

Daily, weekly, monthly, quarterly, and client-meeting views are filters over the
same dated table rows. They are not separate services, prompt files, memory
systems, or summary products.

Do not implement Campaign V2 as:

```text
api/models/workspace.py
api/services/campaign_source.py
api/services/campaign_alignment.py
api/services/campaign_activations.py
api/schemas/campaigns.py
api/routers/campaigns.py
api/tests/test_campaign_*.py
web/src/pages/admin/AdminCampaigns.tsx as the Campaign owner
campaign/context.py
campaign/prompt.md
campaign/meeting_brief.py
campaign/attention.py
campaign/overview.py
campaign/alignment.py
campaign/signal.py
campaign/verdicts.py as recommendation logic
Campaign logic inside campaign/api.py beyond thin HTTP adaptation
CMO/onboarding/plugins calling Campaign through HTTP when direct DB access is available
```

Those are architecture violations, not compatibility shims. If existing route
paths must remain stable, `campaign/api.py` owns those paths and the host app
mounts them. If Campaign-specific UI exists, it belongs under the Campaign
vertical, with `web/` acting only as the shell/mount point.

### Strict vertical delete-test rule

The architecture test is strict:

```text
delete plugins/youtube/
```

means no meaningful YouTube behavior, schemas, routes, tools, prompts, tests,
or UI remain elsewhere in the system.

Campaign is non-removable, so apply the inverse test:

```text
Campaign-specific behavior should be findable under campaign/.
api/ and web/ may mount Campaign surfaces, but they must not contain Campaign
implementation.
```

After verticalization, grepping `api/` or generic `web/` shell files should find
only mount/import references, not Campaign business logic, schemas, tools,
prompt policy, or tests.

Validation must include the CMO chat consumer path, not only backend unit helpers. If Campaign is the truth source, CMO chat must prove it reads Campaign rows rather than daily brief or memory JSON.

### Database, CMO, and Campaign-related artifact interaction

Campaign-related artifacts are evidence or outputs, not Campaign truth by
themselves. Examples include reports, run results, creative drafts, published
proof, source exports, call-center files, client uploads, and Stream cards.

Ownership and flow:

```text
producer/plugin/human creates or imports an artifact
→ artifact owner stores artifact lifecycle/evidence details
→ producer validates source-specific complexity
→ producer writes/edits dated Campaign table rows with normalized fields
→ campaign/ stores canonical Campaign DB columns and evidence refs
→ CMO or any other system reads Campaign table rows
→ LLM brain synthesizes interpretation/recommendation from the rows when needed
→ accepted decisions/actions are written back as dated Campaign rows or row edits
```

Database rule:

```text
Campaign DB columns = operating truth.
Artifact DB rows/files = evidence, proof, or generated output.
JSON/artifact payloads = explanation/provenance, not controlling truth.
```

CMO rule:

```text
The CMO does not search artifacts to reconstruct campaign truth.
The CMO reads Campaign rows first.
The CMO may inspect artifact refs only to explain evidence or verify provenance.
The CMO's reasoning is not Campaign code.
```

A campaign-related artifact becomes Campaign-relevant only when it is bound to a
dated Campaign row with:

```text
campaign_id
objective_id when available
distribution_channel
time_period or period_start/period_end
source_health
verification_status
objective_verdict or reason for needs_data/inconclusive
evidence_ref to the artifact
```

If an artifact cannot be bound this way, it remains raw/unassigned evidence or a
draft. It is not Campaign truth yet.

### CMO access to Campaign

CMO chat should access Campaign as table read/write/edit, not as a Campaign
reasoning framework:

```text
campaign_read   = read dated Campaign rows with filters
campaign_write  = write producer/operator-reported Campaign rows
campaign_edit   = correct, verify, or supersede Campaign rows
```

If product language keeps names such as `campaign_create`, `campaign_append`,
`campaign_patch`, or `campaign_act`, they must remain thin aliases over table
read/write/edit. They must not grow into separate Campaign brains.

These tools must write/read the canonical Campaign DB rows first. Legacy `update_campaign_memory`, daily brief, memory snapshot, CampaignActivation, and CampaignSnapshot paths are not Campaign compatibility layers; they must stay removed from active runtime rather than being rewritten as parallel campaign truth.

Capability expectations:

```text
campaign_read
  Use when any system needs Campaign rows filtered by brand, campaign, market, channel, date range, period type, primary KPI, owner, decision, action, or update state.

campaign_write
  Use when a human, plugin, channel, report, validator, or CMO-approved action reports a new provider-validated daily/weekly Campaign row: target, actual, reach metric, engagement metric, action metric, cost/spend, efficiency, value, learning, recommendation, decision, next action, owner, and note.

campaign_edit
  Use when correcting a row, adding a note, changing a recommendation/decision/action, or superseding previous reported row data. Preserve audit; do not silently rewrite history.
```

CMO chat validation rule:

```text
A Campaign refactor is not accepted until the CMO proves it can read/write/edit Campaign DB rows and synthesize from those rows without Campaign-owned reasoning code.
```

### CMO chat campaign response guidance

Campaign DB rows are the truth; the CMO model owns the marketing conversation. CMO chat must not pre-render campaign, report, daily-brief, draft, approval, or inventory answers before the model sees the turn. Deterministic rendering is acceptable for low-level API/view responses only.

Operator prompts such as these should enter the CMO loop with Campaign row access available:

```text
read the brand profile, then let's discuss the campaign
what do you think about this campaign?
where should we take this next?
what campaigns are running?
what needs attention today?
```

Grounding guidance:

```text
Use campaign_read for campaign/account truth.
For broad portfolio/account discussion with no selected campaign, campaign_read may read all active campaigns.
Do not use legacy inventory/context fallbacks, daily brief payloads, memory snapshots, report JSON, or chat history as campaign truth.
If the CMO fails to call the right tool or ignores context, fix tool descriptions, schemas, working context, or model routing — not phrase gates or server prose.
```

Synthesis guidance:

The CMO should respond like an agency CMO responsible for a client account, not like a database clerk, inventory reader, or support bot. Do not force a rigid template. Let the CMO choose the best conversational structure for the operator's question.

A human agency CMO typically synthesizes campaign status through these data-driven lenses:

```text
business objective      = what the campaign is supposed to move commercially
campaign lane / role    = acquisition, conversion, partner/distribution, proof, retention, reporting, etc.
performance signal      = provider-validated reach_metric, engagement_metric, action_metric, spend/cost, efficiency_metric, value_metric, or explicit missing data
strategic interpretation = what the signal means, what is blocked, what can/cannot be decided
next client/operator decision = the most useful action, owner, or decision now
```

The CMO should use whichever lenses are relevant and available from Campaign rows/context. If data is thin, the CMO should explain the operating implication instead of merely saying `needs_data`:

```text
- no objective recorded   → campaign cannot be evaluated commercially yet
- no channel/period row   → campaign is not reportably anchored yet
- no metrics              → campaign is measurement-dark, not failed
- vague campaign row      → reporting will blur unless the campaign is defined, renamed, split, or archived
- inferred lane/role      → phrase as CMO judgment or recommendation, not recorded Campaign truth
```

Agency-quality interpretation may include whichever of these are relevant:

```text
priority     = which campaign/lane matters first and why
lane         = acquisition, partner/distribution, proof, conversion, retention, reporting, or verification
implication  = what missing or stale data prevents the agency from deciding
decision     = what can be decided now despite missing data
owner/action = the next concrete move for the operator, client, validator, or channel specialist
```

Style guidance:

```text
Prefer natural CMO conversation over checklist formatting.
Use structure only when it helps clarity.
Separate recorded Campaign facts from CMO interpretation/recommendation when that distinction matters.
Do not solve weak synthesis with server-rendered prose, phrase gates, or deterministic campaign summaries.
If the answer is too thin, improve the CMO prompt/tool/context/model path — not hardcoded replies.
```

Live correction captured 2026-07-10: the old phrase-gated shortcut treated “read the brand profile, then lets discuss the campaign” as a deterministic campaign lookup and returned a fixed Campaign Zero / recorded-campaign dump. That is wrong for V2. The prompt now stays on the CMO loop; CMO can inspect tools and then discuss like a marketing operator. Campaign V2 discussion must use `campaign_read` and the campaign primitives, not `get_campaign_context` or other legacy truth fallbacks.

Live correction captured 2026-07-11: `/cmo_v2/chat` and `/cmo_v2/chat/stream` no longer short-circuit daily brief, campaign inventory/context, report status, brand-foundation social drafts, or approval turns into deterministic server prose. Tool results are fed back into the CMO loop instead of stopping on setup blockers, report artifacts, or approval-gated artifacts.

Live correction captured 2026-07-11: CMO Campaign primitives now include `campaign_create`. Live `/api/cmo_v2/chat` through port `8090` proved the CMO can create Campaign records, append Campaign V2 rows, and return the created `campaign_id` from structured tool results. Long model-provided audience/message fields are clipped for display when needed and preserved in Campaign V2 row JSON fields.

Live correction captured 2026-07-11: broad campaign/account discussion with multiple active campaigns no longer requires a selected campaign before the CMO can answer strategically. `campaign_read` can return portfolio-level data (`active_campaign_count`, visible channels, metric totals, verdict counts, primary objectives, per-campaign status/objective summaries). The response guidance above is intentionally not a rigid template; `campaign_read` remains the data primitive and the CMO performs synthesis.

Live correction captured 2026-07-11: onboarding is now expected to create the first live campaign directly from the imported brand profile. That onboarding-extracted active campaign is the default creative execution anchor for new brands. Creative flows should bind to a real active campaign rather than reviving the older `brand_foundation` / `Campaign Foundation (Zero)` fallback for unassigned renders. `postcraft.*`, `storyboard.*`, and `storyboard.motion.*` execution now auto-bind when exactly one active campaign exists for the brand and fail fast when no live campaign or multiple live campaigns make binding ambiguous.

Live correction captured 2026-07-15: the old Campaign runtime stack was deleted instead of hidden behind compatibility facades. Removed paths include `api/routers/campaigns.py`, `api/schemas/campaigns.py`, `api/services/campaign_source.py`, `api/services/campaign_alignment.py`, `api/services/campaign_activations.py`, `api/routers/daily_brief.py`, `api/services/daily_brief.py`, `api/models/daily_brief.py`, and `api/campaign_memory.py`. Old `CampaignActivation`, `CampaignSnapshot`, `campaigns.memory_snapshot`, and `runs.activation_id` model ownership was also removed from active runtime. The surviving runtime source is `campaign/`, mounted by the host API. `/api/campaigns/{campaign_id}/rows` replaced the old snapshot write path; `/api/campaigns/{campaign_id}/snapshots` must fail. Live `8090` validation proved CMO chat and streaming chat read Campaign rows through `campaign_read`, and the Campaign API reads/writes `campaign_rows` through `campaign/db.py`. Legacy database artifacts (`campaign_snapshots`, `campaign_activations`, `daily_briefs`, `campaign_results`, `campaigns.memory_snapshot`, `campaigns.memory_snapshot_at`, and `runs.activation_id`) were retired by migration `054_retire_legacy_campaign_truth` after unmigrated snapshot rows were copied into `campaign_rows`. Remaining mentions in old Alembic migration files are historical database history only, not active Campaign architecture.

### Bugs identified during CMO Campaign live validation

These are the failure classes found while validating Campaign V2 through actual CMO chat, not just unit tests.

| Bug | Symptom | Root cause | Status / rule |
|---|---|---|---|
| Deterministic CMO renderers bypassed tools | Campaign/report/daily/draft replies appeared queued or prewritten with `provider=null`, `steps=0`, `tool_calls=[]` | `/cmo_v2/chat` phrase gates returned server-rendered text before the CMO model could call tools | Fixed 2026-07-11. CMO chat must enter the LLM/tool loop; no phrase-gated campaign prose. |
| Missing Campaign create primitive | CMO said it could not create campaign records from chat | Tool set had read/append/patch/act/delete but no `campaign_create` | Fixed 2026-07-11. `campaign_create` is required for “save/start/open/create campaign” requests. |
| Tool result summaries hid IDs | CMO created a campaign but told the operator it could not see the campaign ID | Tool results fed back to the LLM only as summary text, dropping `campaign_id`, row IDs, etc. | Fixed 2026-07-11. Feed structured tool result JSON back into the loop. |
| Long campaign primitive fields crashed DB writes | `StringDataRightTruncationError: value too long for type character varying(255)` when saving rich audience/message details | Legacy `campaigns.audience` and `campaigns.message_angle` are `VARCHAR(255)` but CMO supplied full strategy text | Fixed 2026-07-11. Clip display columns; preserve full detail in JSON / Campaign V2 rows. |
| Failed flush poisoned the CMO turn | After one DB write error, retry failed with `PendingRollbackError` | SQLAlchemy session was not rolled back after campaign tool exception | Fixed 2026-07-11. Campaign V2 tool exceptions must rollback before returning an error tool result. |
| Strategy rows can record fake zero metrics | Concept/strategy Campaign rows showed `reach=0`, `clicks=0`, etc. even though no performance was reported | Model/tool args used zero instead of omitted/null metrics; missing data became numeric zero | Open. Campaign tools should treat absent performance as `NULL` and `needs_data`, never fake zero. Add validation/coercion for strategy/non-performance rows. |
| Active campaign without channel/period row | Inventory/status says active but reporting is not anchored | Campaign exists, but no dated channel/period row has been reported yet | Expected transitional state. Do not create a parallel CampaignActivation truth path. Append Campaign rows with channel, period, source health, verification, and verdict when evidence exists. |
| One-click Admin lifecycle moved live campaigns to History | MotorMoto appeared complete/read-only in Admin while CMO still saw it as active from canonical campaign sheet context | Admin Campaign Board had generic one-click `draft → active → complete → archived`; accidental `PATCH /campaigns/{id}` with `status=complete` removed live CMO context | Fixed 2026-07-11. Backend requires `confirm_status_change=true` for `active → complete` and `complete → archived`; Admin now shows confirmation and uses “Mark complete”. |
| Admin brand/campaign selection could feel inconsistent with CMO brand filter | Campaign Board needed the same explicit brand filter mental model as CMO/Stream, and stale active-campaign selection could survive brand changes | Admin Campaigns had a local board filter UI and incomplete active-campaign clearing behavior | Fixed 2026-07-11. Campaign Board uses shared active brand context, explicit “Brand filter / All brands” selector, clears stale active campaigns on brand changes, and shows current live CMO campaign badge. |

### Admin Campaign Board lifecycle rule

Campaign lifecycle changes are brand-generic and must not rely on accidental one-click actions.

```text
draft → active       = allowed from board (“Start tracking”)
active → complete   = guarded; requires explicit confirmation
complete → archived = guarded; requires explicit confirmation
```

Completing a campaign means:

```text
- move it to History
- remove it from live CMO campaign context
- keep it available for Review / Start new from this
```

Therefore any API or UI path that changes an active campaign to `complete` must make that consequence explicit and pass `confirm_status_change=true`. This guard is generic for all brands, not MotorMoto-specific.

Validation requirement going forward:

```text
Every CMO Campaign change must be tested through the CMO vertical, not through Campaign-in-api shortcuts:
- confirm the CMO reads dated Campaign rows through campaign_read
- confirm write/edit actions change canonical Campaign DB rows
- confirm missing metrics remain NULL / needs_data, not fake zero
- confirm artifact refs are evidence only
- confirm the LLM synthesis is produced by the CMO model, not Campaign code
```

Anti-reversion rule:

```text
Do not reintroduce keyword/phrase renderers or Campaign-specific synthesis code to hide CMO tool-selection bugs.
If the CMO fails to read/write/edit Campaign rows correctly, fix the CMO tool routing or model path. Do not add Campaign reasoning services.
```
