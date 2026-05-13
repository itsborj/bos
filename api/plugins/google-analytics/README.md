# Google Analytics Read-Only Plugin MVP

Third-party plugin for BOS/Klaroha. This plugin lives entirely under:

```text
api/plugins/google-analytics/
```

It is intentionally read-only. It reads GA4 performance, Admin setup metadata, and realtime tracking signals, then returns Workspace intelligence artifacts. It does **not** create audiences, edit GA properties, create data streams, alter conversions/key events, mutate tags, change campaigns, or write to any external system.

## Current version

```text
0.3.0
```

## Required Google APIs

Enable these in the Google Cloud project attached to the OAuth client:

```text
Google Analytics Data API        analyticsdata.googleapis.com
Google Analytics Admin API       analyticsadmin.googleapis.com
```

Do not use Analytics Hub API for this plugin; it is unrelated to GA4 reporting/setup reads.

## Required OAuth scope

```text
https://www.googleapis.com/auth/analytics.readonly
```

The plugin exchanges the configured refresh token for short-lived access tokens at execution time.

## Required environment variables

Declared in `channel.json` as plugin-local platform vars:

```text
GOOGLE_ANALYTICS_CLIENT_ID=
GOOGLE_ANALYTICS_CLIENT_SECRET=
GOOGLE_ANALYTICS_REFRESH_TOKEN=
GOOGLE_ANALYTICS_PROPERTY_ID=
```

Notes:

- `GOOGLE_ANALYTICS_PROPERTY_ID` may be either `123456789` or `properties/123456789`.
- The OAuth Google user must have access to the GA4 property.
- This MVP does not add core OAuth UI/support for Google Analytics. The plugin must work or fail via the published plugin SDK contract only.

## Capabilities

| Capability ID | Purpose | Output contract |
|---|---|---|
| `marketing.channel.google_analytics.performance.read` | Pull GA4 performance summary, traffic sources, and landing pages. | `google_analytics_data_pull` |
| `marketing.channel.google_analytics.admin.read` | Inspect GA4 property metadata, data streams, Measurement IDs, and setup readiness. | `google_analytics_admin_readiness` |
| `marketing.channel.google_analytics.realtime.read` | Check whether GA4 realtime tracking appears to be firing right now. | `google_analytics_realtime_check` |

CMO-facing job:

```text
marketing.optimize
```

## Example CMO requests

```text
check google analytics for the last 30 days
check ga setup
check if google analytics tracking is live right now
test analytics tracking
```

Expected internal dispatches:

```text
RUN: marketing.channel.google_analytics.performance.read
RUN: marketing.channel.google_analytics.admin.read
RUN: marketing.channel.google_analytics.realtime.read
```

## Optional brief fields

```text
google_analytics_property_id=
google_analytics_date_range=LAST_30_DAYS
```

Supported date ranges for the performance pull:

```text
TODAY, YESTERDAY, LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS, LAST_90_DAYS, THIS_MONTH, LAST_MONTH
```

## Output shapes

### Data pull

```json
{
  "type": "google_analytics_data_pull",
  "status": "succeeded",
  "property_id": "123456789",
  "date_range": "LAST_30_DAYS",
  "summary": {
    "sessions": 18420,
    "users": 12980,
    "engaged_sessions": 10450,
    "conversions": 412,
    "session_conversion_rate": 0.0224,
    "engagement_rate": 0.5673
  },
  "traffic_sources": [],
  "landing_pages": [],
  "read_only": true,
  "changed_resources": []
}
```

### Admin readiness

```json
{
  "type": "google_analytics_admin_readiness",
  "status": "succeeded",
  "property_id": "537563339",
  "property": {
    "display_name": "Example Website",
    "time_zone": "Asia/Manila",
    "currency_code": "PHP",
    "industry_category": "AUTOMOTIVE"
  },
  "data_streams": [
    {
      "stream_id": "1234567890",
      "display_name": "Example Web",
      "type": "WEB_DATA_STREAM",
      "default_uri": "https://example.com",
      "measurement_id": "G-ABCD1234"
    }
  ],
  "readiness": {
    "status": "needs_setup",
    "checks": [
      {
        "name": "property_accessible",
        "status": "pass",
        "message": "GA4 property is accessible through the Admin API."
      }
    ]
  },
  "read_only": true,
  "changed_resources": []
}
```

### Realtime check

```json
{
  "type": "google_analytics_realtime_check",
  "status": "succeeded",
  "property_id": "537563339",
  "active_users": 1,
  "event_count": 4,
  "events": [
    {
      "event_name": "page_view",
      "event_count": 3,
      "active_users": 1
    }
  ],
  "pages": [
    {
      "page_or_screen": "Home",
      "active_users": 1,
      "event_count": 3
    }
  ],
  "readiness": {
    "status": "tracking_live",
    "message": "Realtime activity was detected. GA4 tracking appears to be firing."
  },
  "read_only": true,
  "changed_resources": []
}
```

No realtime activity is a successful read, not an API failure:

```json
{
  "type": "google_analytics_realtime_check",
  "status": "succeeded",
  "active_users": 0,
  "event_count": 0,
  "readiness": {
    "status": "no_realtime_activity",
    "message": "No active users or realtime events were detected. Open the website in another tab and retry."
  },
  "read_only": true,
  "changed_resources": []
}
```

## Official Google Analytics MCP comparison

The official Google Analytics MCP server wraps the same GA Admin/Data APIs. This plugin does **not** require the MCP server, but its documented read-only tools inform this roadmap.

| Official MCP tool | Plugin status | BOS/plugin equivalent |
|---|---|---|
| `get_property_details` | Partial | `marketing.channel.google_analytics.admin.read` |
| `run_report` | Partial | `marketing.channel.google_analytics.performance.read` |
| `run_realtime_report` | Implemented | `marketing.channel.google_analytics.realtime.read` |
| `get_account_summaries` | Not yet implemented | Future account/property inventory capability |
| `get_custom_dimensions_and_metrics` | Not yet implemented | Future metadata inventory capability |
| `list_google_ads_links` | Not yet implemented | Future Ads-link readiness capability |
| `list_property_annotations` | Not yet implemented | Future annotation context capability |
| `run_funnel_report` | Not yet implemented | Future funnel analysis capability |

## Recommended next capabilities

1. `marketing.channel.google_analytics.account.inventory.read` — list accessible accounts/properties to prevent wrong property IDs.
2. `marketing.channel.google_analytics.metadata.read` — list custom dimensions and metrics.
3. `marketing.channel.google_analytics.ads_links.read` — inspect Google Ads links read-only.
4. `marketing.channel.google_analytics.funnel.read` — run GA4 funnel reports once traffic/events exist.

## Read-only guarantees

Every capability must return:

```json
{
  "read_only": true,
  "changed_resources": []
}
```

Forbidden outcomes:

- creating/editing/deleting GA properties
- creating/editing/deleting data streams
- creating audiences
- changing conversions/key events
- changing tags/GTM/site code
- changing campaigns, bids, or budgets
- returning or logging OAuth secrets, refresh tokens, or access tokens
