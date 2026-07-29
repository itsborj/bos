# Campaign — Database-Persisted Source of Truth

> Status: reroute cleanup and database ownership refactor implemented; local PostgreSQL migration and Campaign API smoke validation passed
> Contract: `docs/campaign_v2.md`
> Decision: Campaign is database-persisted. This document does not authorize deleting or replacing the Campaign database model with memory, JSON, reports, prompts, or artifacts.

## 1. Locked direction

Campaign is the canonical database-backed operating record:

```text
Campaign identity/lifecycle
+ dated Campaign operating rows
+ objective
+ distribution channel
+ period
+ normalized producer-reported metrics
+ verdict
+ learning / decision / next action
+ evidence references
```

The `campaign` vertical (`api/campaign/` in the repository and `campaign/` in the API runtime image) owns this data and its read/write/edit behavior. CMO,
plugins, onboarding, runs, Admin, Stream, and reports are callers, producers, or
views. They are not alternative Campaign truth stores.

The relational database is protected. The cleanup target is competing routing
and competing truth paths—not Campaign persistence.

## 2. Assessment

The current implementation contains the new `campaign_rows` operating table and
Campaign-owned database helpers, but runtime behavior is split:

The assessment found a split runtime: Campaign V2 writes used `campaign_rows`, while selection, run enrichment, foreign-key identity, Daily Brief signals, and creative alignment could use other paths. The refactor has now:

- moved Campaign identity ORM ownership from `api/models/workspace.py` into
  `api/campaign/table.py` beside `CampaignRow`;
- routed active selection, run enrichment, run-list naming, and brand claiming
  through `campaign/db.py`;
- retained `campaigns` as durable relational identity/lifecycle and
  `campaign_rows` as dated operating truth;
- removed disabled deterministic Campaign/report/social renderers and backup or
  duplicate prompt files;
- replaced `daily_brief_signal` with persisted `campaign_signal`;
- removed Postcraft `campaign_context` and Brand Kit Campaign-truth fallbacks;
- removed silent append-time Campaign creation and invalid-ID broad fallbacks;
- made edits lock the current row, create one replacement, and supersede the prior row;
- validates explicit run/creative Campaign IDs against workspace, brand, and active status before execution;
- resolves active Campaign identity from `campaigns`, not from a limited window of recent operating rows;
- made Alembic create `campaign_rows` before migration `054` consumes it;
- preserves legacy snapshots, results, activations/run lineage, memory snapshots, and daily briefs as Campaign rows or audit evidence before deleting old truth surfaces;
- placed the Campaign package inside the API build context without changing the
  GitHub workflow.

Both an existing local database upgrade and a clean empty-database Alembic upgrade through migration `056` passed. A seeded legacy-data migration test proved preservation of snapshots, results, activations with run IDs, memory snapshots, and daily briefs before the old tables were removed. Create → append → superseding edit → lifecycle guard → read → delete API smoke validation also passed. Deployed-environment and live CMO model validation remain required.

## 3. What must be removed

Remove code that can bypass Campaign-owned DB access:

1. Retired deterministic Campaign inventory/context/mutation/report/social
   renderers and phrase routers in `api/routers/chat_v2.py`.
2. `api/routers/chat.py.bak`.
3. Unused duplicate CMO prompt policy in `api/routers/cmo_prompt.py`.
4. Dead Campaign render helpers and unused phrase-based patch filters in
   `api/routers/cmo_tools.py`.
5. `daily_brief_signal` producer contracts and tests.
6. `campaign_context` and Brand Kit payload fallbacks as current Campaign truth.
7. automatic `Untitled Campaign` creation from append/action operations.
8. invalid Campaign IDs silently falling back to a different campaign or a
   portfolio read.
9. direct Campaign table queries outside the Campaign vertical.
10. duplicate unmanaged raw SQL migration paths once Alembic owns the schema.

Historical Alembic migrations remain database history. Removing a runtime path
does not mean deleting migration history.

## 4. Database ownership after refactor

The Campaign vertical owns both relational concerns:

```text
api/campaign/                 # runtime import package: campaign
  table.py   Campaign identity/lifecycle + CampaignRow operating facts
  db.py      all Campaign queries, writes, edits, lifecycle and filters
  api.py     thin HTTP adapter only
  tests/     persistence, isolation, lifecycle and history behavior
```

The `campaigns` identity table remains the stable relational target for
runs, references, intents, Stream rows, and creative objects. It must be owned
by `campaign/`, not `api/models/workspace.py`, and must not carry a competing
JSON truth model.

`campaign_rows` holds dated operating truth. Supporting JSON may preserve raw
producer evidence, but typed DB columns win.

Outside callers use `campaign/db.py`; they do not import/query Campaign ORM
tables directly.

## 5. Required behavior

### Reads

- Scope by workspace and brand before returning Campaign data.
- Reject invalid explicit IDs; never broaden the query silently.
- Portfolio reads must be explicit.
- Active Campaign selection must come from Campaign DB helpers.
- CMO synthesis may be conversational, but its facts come from Campaign rows.

### Writes

- `campaign_create` is the only operation that creates Campaign identity.
- `campaign_append` requires an existing Campaign owned by the active
  workspace/brand.
- producer outputs append normalized Campaign rows with provenance.
- missing performance stays `NULL`; missing data is not zero.
- a metric-less row defaults to `needs_data` unless an explicit valid verdict is
  supplied.

### Edits and lifecycle

- Verify workspace/brand ownership before mutation.
- preserve correction/supersession history for material changes.
- guarded lifecycle transitions must be enforced by the backend, not only UI.
- Campaign identity updates and operating rows must not drift into contradictory
  statuses or names.

### Producers and consumers

- producer/plugin validates source-specific complexity.
- producer emits `campaign_signal` or directly calls Campaign DB helpers.
- execution persists the normalized signal as a Campaign row.
- artifacts and raw reports remain evidence.
- Postcraft and other consumers resolve current Campaign alignment from the DB.

## 6. Refactor sequence

### Phase A — gut reroutes (implemented)

- delete disabled deterministic response/router code;
- delete backup and duplicate prompt files;
- remove Daily Brief signal contracts;
- remove payload-based Campaign truth fallbacks;
- remove silent auto-create and broad-fallback behavior.

### Phase B — consolidate database ownership (implemented)

- move Campaign identity ORM ownership into `campaign/table.py`;
- expose all identity/row queries through `campaign/db.py`;
- replace direct queries in chat, runs, onboarding, Admin, and plugins;
- preserve existing relational foreign keys while removing alternative truth
  fields and readers.

### Phase C — persistence and deployment (local migration/API validated; deployed validation pending)

- make Alembic create/upgrade `campaign_rows` before migration code uses it;
- package `api/campaign/` in the API image through the existing API build context;
- remove duplicate raw SQL migrations after Alembic is canonical;
- validate a clean database upgrade and live API startup.

### Phase D — enforcement (focused architecture tests added; deployed CMO validation pending)

Add CI architecture checks:

```text
no import of Campaign ORM outside campaign/
no direct select/update/delete against Campaign tables outside campaign/
no daily_brief_signal
no active campaign_context truth fallback
no retired deterministic Campaign router helpers
```

Add persistence tests for:

- create → append → read → edit/supersede;
- brand/workspace isolation;
- invalid ID failure without fallback;
- nullable missing metrics and `needs_data`;
- guarded lifecycle transitions;
- producer `campaign_signal` persistence;
- CMO read/write/edit through canonical Campaign helpers;
- clean Alembic upgrade and API image import/startup.

## 7. Acceptance rule

The refactor is complete when this statement is true:

> Every Campaign identity, status, dated fact, metric, verdict, learning,
> decision, and next action used by BOS is read from or written to the
> Campaign-owned relational database path. Everything else is evidence, input,
> or presentation.
