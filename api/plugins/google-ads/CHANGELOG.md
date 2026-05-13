# Google Ads Plugin Changelog

## 0.4.0 — Read expansion: account discovery and campaign report

### Added

- Added `marketing.channel.google_ads.account.discover`.
- Added `google_ads_account_inventory` read-only artifact.
- Added `marketing.channel.google_ads.campaigns.read`.
- Added `google_ads_campaign_report` read-only artifact with campaign rows, totals, status, budget, cost, clicks, conversions, CTR, CPA, and review flags.
- Added plugin tests for account/campaign routing and read-only output parsing.

### Boundaries

- No mutation capability added.
- Account discovery and campaign reports return `read_only: true` and `changed_resources: []`.
- Campaign list/report requests route to the campaign report capability instead of the generic performance pull.

## 0.3.0 — Full-control direction and manifest alignment

### Added

- Added `FULL_CONTROL_SPEC.md`, reverse-specified from approved sample `sample/google_ads_full_control_v1.md`.
- Documented the Google Ads control ladder: read/diagnose, draft/recommend, approved write/edit, and destructive/high-risk second-confirmation actions.
- Documented mutation audit requirements: selected change IDs, changed resources, failures, before/after snapshots, and rollback notes.

### Changed

- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` is no longer listed as a required platform var in `channel.json`; it remains optional for MCC/manager-account setups.
- `channel.json` risk policy now states current capabilities are read/draft only while future mutations must be approval-gated.

### Boundaries

- No new mutation capability is shipped in 0.3.0.
- No BOS core/router/skill-loader changes.
- Existing read and draft capabilities remain no-mutation.

## 0.2.0 — Google Ads copy draft capability

### Added

- Added `marketing.channel.google_ads.search_text.draft` as a plugin-local capability.
- Added structured `google_search_ad_draft` draft artifact output:
  - `format: responsive_search_ad`
  - `headlines[]`
  - `descriptions[]`
  - `display_url`
  - `changed_resources: []`
  - `risk_level: requires_approval`
- Added plugin-local tests under `api/plugins/google-ads/tests/`.

### Fixed

- Fixed routing behavior for:

  ```text
  can you generate a google ads copy
  ```

  Expected result is now a Google Ads draft artifact from:

  ```text
  marketing.channel.google_ads.search_text.draft
  ```

  It must not invoke the read-only performance capability:

  ```text
  marketing.channel.google_ads.performance.read
  ```

  because that produces a Marketing Intelligence artifact.

### Boundaries

- No BOS core/router/skill-loader changes.
- No MCP runtime added.
- No Google Ads mutation endpoints added.
- Copy draft artifacts are reviewable drafts only; they do not create, publish, pause, enable, or edit campaigns/ads/keywords/budgets.

## 0.1.0 — Read-only performance data pull

### Added

- Added `marketing.channel.google_ads.performance.read`.
- Added `google_ads_data_pull` intelligence artifact.
- Added OAuth refresh-token based Google Ads API data pull.
- Added no-mutation/read-only contract.
