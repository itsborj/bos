# DB Bug Indicators Task List

Generated: 2026-06-12  
Source: live local PostgreSQL database from `.env` (`alembic_version=043_cmo_usage_mode`, 37 public tables). No destructive changes were made.

## Snapshot

- Rows with likely fuzzer / invalid domain data were found after migration `039_cleanup_fuzzer_data_stream_dedupe`.
- Alembic reports latest migration, but one expected plugin activation partial unique index is missing.
- Run history shows persistent provider/model routing failures and media credential failures.
- Plugin activation DB state contains stale rows for plugins that are not installed in the external plugin set.

---

## P0 — Stop fuzzer / invalid operator data from persisting

- [ ] Add stricter create/update validation for operator-facing names and statuses.
  - Evidence:
    - `brands`: 8 total; 7 created on 2026-06-11 with blank default profiles and suspicious names (`''`, `0`, `°`, etc.).
    - `campaigns`: 18 total; 18 have `brand_id IS NULL`; 13 have empty/1-char names or invalid status (`status='0'`).
    - `products`: 92 total; 40 have empty/1-char names.
    - `audiences`: 58 total; 15 have empty/1-char names.
    - `calendar_pages`: 19 total; 19 have empty/1-char slug/title.
    - `council_sessions`: 47 total; 25 have `length(brief) < 2`.
  - Suspect code areas:
    - `api/schemas/brands.py` currently allows `name` with `min_length=1`.
    - `api/schemas/campaigns.py` has no `min_length` and no status enum.
    - Related create endpoints should reject empty/garbage values before commit.
  - Acceptance SQL:
    ```sql
    SELECT count(*) FROM campaigns
    WHERE name = '' OR length(name) < 2
       OR status NOT IN ('draft','active','complete','paused','archived');
    ```
    should return `0` for non-test DBs.

- [ ] Add a cleanup migration for fuzzer rows missed by migration 039.
  - Include at least: `brands`, `campaigns`, `products`, `audiences`, `calendar_pages`, `council_sessions`, `execution_backend_overrides`.
  - Do not rely only on list-time filtering; invalid rows currently remain in DB.

---

## P0 — Remove invalid backend override row and harden DB constraints

- [ ] Delete/quarantine the invalid `execution_backend_overrides` row and add DB-level validation.
  - Evidence: 1 of 7 backend override rows has invalid `target`, `provider`, `model_id`, and `modality` from fuzz input.
  - Current API list filters invalid rows, but resolver paths should not have to tolerate corrupted rows.
  - Acceptance SQL:
    ```sql
    SELECT count(*)
    FROM execution_backend_overrides
    WHERE provider NOT IN ('openai','openrouter','gemini','nvidia','bytedance','anthropic')
       OR modality NOT IN ('text','image','video','data_analysis')
       OR target !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$';
    ```
    should return `0`.

---

## P1 — Fix plugin activation schema drift

- [ ] Add/fix migration for missing org-scope partial unique index.
  - Evidence: `alembic_version=043_cmo_usage_mode`, but expected index from `038_plugin_activations.py` is absent:
    - missing: `uq_plugin_activations_plugin_org`
    - present: `uq_plugin_activations_plugin_brand`, `ix_plugin_activations_status`, `ix_plugin_activations_brand`
  - Risk: PostgreSQL normal unique constraints allow multiple `(plugin_id, NULL)` rows; duplicate org-scope activation rows can be inserted.
  - Acceptance SQL:
    ```sql
    SELECT exists (
      SELECT 1 FROM pg_indexes
      WHERE tablename = 'plugin_activations'
        AND indexname = 'uq_plugin_activations_plugin_org'
    );
    ```
    should return `true`.

- [ ] Clean stale plugin activation rows for plugins not installed.
  - Evidence:
    - DB has 20 activation rows / 18 unique plugin IDs.
    - Installed external plugin IDs found under `~/bos-plugins`: 8.
    - Stale DB-only plugin IDs: `channel.clickup`, `channel.gmail`, `channel.gmail_auth`, `channel.google_ads`, `channel.google_analytics`, `channel.google_calendar`, `channel.linkedin`, `channel.search_console`, `channel.test_stub`, `channel.tiktok`.
  - Acceptance: activation rows should exist only for currently installed plugins, unless intentionally retained in a separate uninstall history table.

---

## P1 — Provider/model routing failures are visible in run history

- [ ] Triage provider/model availability and disable broken defaults/overrides.
  - Evidence:
    - `runs`: 867 total; 28 `failed`; 170 `partial`.
    - `run_results`: 171 have `self_check_verdict='fail'`.
    - `run_attempts`: 63 failed attempts.
    - Top failure classes:
      - 22 × OpenRouter `402 Payment Required`
      - 10 × NVIDIA `404 Not Found` for `https://integrate.api.nvidia.com/v1/chat/completions`
      - 8 × Gemini/OpenAI-compatible endpoint `429 Too Many Requests`
      - 5 × `missing_credentials`
      - 12 × unsupported OpenAI Codex model errors (`gpt-4o`, `gpt-4o-mini`, `gpt-5.3-codex`)
  - Tasks:
    - Mark providers unhealthy after repeated 402/404/429 and avoid them until revalidated.
    - Remove or guard unsupported Codex model options.
    - Verify backend overrides for `cmo.main`, onboarding, and media modules match available credentials.
    - Ensure failed runs always record a useful result/error artifact.

- [ ] Fix media generation credential/setup-blocker behavior.
  - Evidence: recent `media.image.generate` / `media.video.generate` runs are `partial` with `missing_credentials` or `api_call_failed` despite active media plugin rows for brand `7b4c97aa-ee5c-42cd-8932-5779ed0f4590`.
  - Acceptance: missing media credentials should produce a clear setup blocker before dispatch, not a partial run with failed self-check.

---

## P2 — Add provider login session expiry/cleanup

- [ ] Expire and delete stale OAuth/login sessions.
  - Evidence: `provider_login_sessions`: 94 total; 89 older than 1 day.
  - Tasks:
    - Add TTL/expiry column or cleanup job.
    - Prevent old states from accumulating indefinitely.
    - Add index if cleanup scans by `created_at`.

---

## P2 — Enforce brand isolation on new campaign data

- [ ] Make campaign creation brand-aware.
  - Evidence: all 18 `campaigns` rows have `brand_id IS NULL`; `api/routers/campaigns.py:create_campaign` does not set brand context.
  - Current plan requires Brand-scoped activation and CMO behavior; campaign/run data should avoid new workspace-level ambiguity unless explicitly intentional.
  - Acceptance: new campaign APIs either require `brand_id` or derive it from active brand context.

---

## Suggested verification bundle

Run these after fixes:

```sql
-- migration/index integrity
SELECT version_num FROM alembic_version;
SELECT indexname FROM pg_indexes WHERE tablename='plugin_activations' ORDER BY indexname;

-- invalid operator data counts
SELECT count(*) FROM execution_backend_overrides
WHERE provider NOT IN ('openai','openrouter','gemini','nvidia','bytedance','anthropic')
   OR modality NOT IN ('text','image','video','data_analysis')
   OR target !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$';

SELECT count(*) FROM campaigns
WHERE name = '' OR length(name) < 2
   OR status NOT IN ('draft','active','complete','paused','archived');

SELECT count(*) FROM products WHERE name='' OR length(name)<2;
SELECT count(*) FROM audiences WHERE name='' OR length(name)<2;
SELECT count(*) FROM calendar_pages WHERE slug='' OR title='' OR length(slug)<2 OR length(title)<2;
SELECT count(*) FROM council_sessions WHERE length(brief)<2;

-- run health trend
SELECT status, count(*) FROM runs GROUP BY 1 ORDER BY 2 DESC;
SELECT status, left(error, 120), count(*) FROM run_attempts GROUP BY 1,2 ORDER BY 3 DESC;
```
