# Google Search Console Channel Plugin

Custom BOS/Klaroha plugin for Google Search Console.

This plugin is native/API-only. It does **not** use Membrane, Rube, Composio, or an MCP sidecar.

## Current capabilities

| Capability ID | Job | Artifact | Mutates Search Console/site? |
|---|---|---|---|
| `marketing.channel.search_console.specialist.overview` | `marketing.optimize` | `search_console_capability_card` | No |
| `marketing.channel.search_console.properties.list` | `marketing.optimize` | `search_console_property_inventory` | No |
| `marketing.channel.search_console.performance.query` | `marketing.optimize` | `search_console_performance_report` | No |
| `marketing.channel.search_console.url.inspect` | `marketing.optimize` | `search_console_url_inspection` | No |
| `marketing.channel.search_console.sitemaps.read` | `marketing.optimize` | `search_console_sitemap_report` | No |
| `marketing.channel.search_console.opportunities.plan` | `marketing.optimize` | `search_console_opportunity_plan` | No |

## Required environment variables

```text
GOOGLE_SEARCH_CONSOLE_CLIENT_ID=
GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET=
GOOGLE_SEARCH_CONSOLE_REFRESH_TOKEN=
GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL=sc-domain:example.com
```

`GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL` may be a domain property (`sc-domain:example.com`) or URL-prefix property (`https://www.example.com/`).

## Boundaries

V1 is read-only.

It must not:

- edit website content
- submit or delete sitemaps
- add or delete Search Console sites
- request indexing
- claim ranking improvements
- expose OAuth tokens or credentials
- require Search Console-specific BOS core or chat-router changes

See:

- `SEARCH_CONSOLE_SPEC.md`
- `CAPABILITY_CONTRACTS.md`
- `sample/search_console_plugin_output_v1.md`
