# Search Console Plugin Capability Contracts

This document is plugin-owned. It describes capabilities shipped by `api/plugins/search-console/`.

## Boundary

The Search Console plugin is custom-built for BOS using native Google Search Console APIs only.

No Membrane, Rube, Composio, arbitrary MCP sidecar, BOS core provider, or CMO router changes.

All v1 capabilities are read-only and must return:

```json
{
  "read_only": true,
  "changed_resources": []
}
```

## `marketing.channel.search_console.properties.list`

Purpose: return accessible Search Console sites/properties.

Output contract: `search_console_property_inventory`

Must not add/delete sites or expose credentials.

## `marketing.channel.search_console.performance.query`

Purpose: return query/page performance: clicks, impressions, CTR, position.

Output contract: `search_console_performance_report`

Must not edit titles, pages, content, schema, sitemaps, or Search Console settings.

## `marketing.channel.search_console.url.inspect`

Purpose: inspect a single URL's indexing/crawl/canonical/rich-result signals.

Output contract: `search_console_url_inspection`

Must not request indexing or inspect URLs outside the selected property.

## `marketing.channel.search_console.sitemaps.read`

Purpose: list submitted sitemaps and status signals.

Output contract: `search_console_sitemap_report`

Must not submit or delete sitemaps.

## `marketing.channel.search_console.opportunities.plan`

Purpose: produce a review-only organic search opportunity plan from Search Console data.

Output contract: `search_console_opportunity_plan`

Must not auto-edit the site, submit sitemaps, request indexing, or guarantee rankings.

## Future actions

Future write actions such as sitemap submit/delete or indexing requests require separate approval-gated capabilities, source artifacts, audit metadata, and second confirmation for destructive actions.
