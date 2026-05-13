# Google Ads Plugin Testing

Run plugin-focused tests from the API container:

```bash
PYTHONPATH=/app pytest -q plugins/google-ads/tests/test_google_ads_channel_plugin.py
```

Optional compatibility check against existing Google Ads plugin routing tests:

```bash
PYTHONPATH=/app pytest -q tests/test_google_ads_plugin_outcome_routing.py plugins/google-ads/tests/test_google_ads_channel_plugin.py
```

## Expected routing assertions

| Prompt | Must route to | Must not route to |
|---|---|---|
| `show me google ads` | `marketing.channel.google_ads.performance.read` | `marketing.channel.google_ads.search_text.draft` |
| `check google ads performance` | `marketing.channel.google_ads.performance.read` | `marketing.channel.google_ads.search_text.draft` |
| `can you generate a google ads copy` | `marketing.channel.google_ads.search_text.draft` | `marketing.channel.google_ads.performance.read` |

## Expected artifact contracts

### Performance read

- Artifact type: `intelligence_artifact`
- Output contract: `google_ads_data_pull`
- `read_only: true`
- `changed_resources: []`

### Search text draft

- Artifact type: `draft_artifact`
- Output contract: `google_search_ad_draft`
- Responsive search ad fields:
  - `headlines[]`, max 30 characters each
  - `descriptions[]`, max 90 characters each
  - `display_url`
- `changed_resources: []`
- `risk_level: requires_approval`

## Manual smoke test

In CMO chat:

```text
show me google ads
```

Expected: short read-only data-pull reply and a Marketing Intelligence artifact.

Then:

```text
can you generate a google ads copy
```

Expected: short draft-copy reply and a Google Ads draft artifact. It must not create another Marketing Intelligence artifact.
