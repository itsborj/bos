# Search Console Plugin — Reverse Spec v1

**Date:** 2026-05-13  
**BITE source sample:** `sample/search_console_plugin_output_v1.md`  
**Implementation rule:** Custom BOS plugin using native Google Search Console APIs only. No Membrane, Rube, Composio, or arbitrary MCP sidecar.

## Target

Build a plugin-owned `marketing.optimize` specialist for Google Search Console.

V1 is read-only:

- property inventory
- query/page performance
- URL inspection
- sitemap report
- SEO opportunity plan based on Search Console data

## Boundary

Allowed:

- files under `api/plugins/search-console/`
- plugin-local `SKILL.md`, `module.py`, `template.j2`, tests, docs
- native Google Search Console APIs called from plugin-local modules/connectors
- host-injected credentials via `brief["_channel_credentials"]`

Forbidden:

- Search Console logic in `routers/chat.py` or `skills/router.py`
- Search Console code in BOS core providers/routers/models for v1
- third-party automation layers: Membrane, Rube, Composio
- arbitrary MCP tool execution
- website edits or Search Console write actions in v1

## Native API surfaces

| Capability | Native API |
|---|---|
| properties list | Search Console `sites.list` |
| performance query | Search Analytics `searchanalytics.query` |
| URL inspection | URL Inspection `urlInspection.index.inspect` |
| sitemaps read | Search Console `sitemaps.list` and optional `sitemaps.get` |
| opportunities plan | Plugin-generated decision artifact from performance/sitemap/indexing data |

## Credentials

V1 uses plugin-declared environment credentials injected by host:

```text
GOOGLE_SEARCH_CONSOLE_CLIENT_ID
GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET
GOOGLE_SEARCH_CONSOLE_REFRESH_TOKEN
GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL
```

`DEFAULT_SITE_URL` may be `sc-domain:example.com` or URL-prefix form such as `https://www.example.com/`.

## Output contracts

Every v1 module returns:

```json
{
  "read_only": true,
  "changed_resources": []
}
```

V1 must never return write/action-result artifacts for sitemap submit/delete, add/delete site, website edits, or indexing requests.

## Capability IDs

```text
marketing.channel.search_console.properties.list
marketing.channel.search_console.performance.query
marketing.channel.search_console.url.inspect
marketing.channel.search_console.sitemaps.read
marketing.channel.search_console.opportunities.plan
```

## Build order

1. Plugin manifest/docs.
2. Shared plugin-local native connector helpers via module-local code for now.
3. Properties list.
4. Performance query.
5. URL inspect.
6. Sitemaps read.
7. Opportunities plan.
8. Routing/output tests.

## Future v2 actions

Approval-gated only:

- submit sitemap
- delete sitemap
- add site
- delete site
- request indexing if supported/allowed

These require source artifact approval, changed resources, audit metadata, and second confirmation for destructive actions.
