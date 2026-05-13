# Search Console Plugin — Stage 2 Sample Output v1

**Date:** 2026-05-13  
**Status:** Draft sample for human approval  
**BITE stage:** Stage 2 — sample before spec/build  
**Source learnings:** Google Search Console API overview and workflow/action boundaries. Third-party automation layers such as Membrane, Rube, or Composio are explicitly out of scope for BOS Search Console.

## Direction

Google Search Console should become a plugin-owned `marketing.optimize` specialist.

It helps the CMO understand how Google sees the site and where organic visibility can improve:

- properties/sites
- sitemaps
- URL inspection
- search analytics/performance reports
- indexing/coverage signals
- SEO opportunity recommendations

It must not become BOS core behavior and must not add Search Console-specific logic to CMO chat routing.

## Connector posture

The Search Console plugin must be custom-built for BOS.

Allowed implementation:

1. Plugin-local connector code under `api/plugins/search-console/`.
2. Native Google Search Console APIs only.
3. BOS host-injected credentials via plugin manifest/connection contract.
4. Plugin-owned `SKILL.md`, `module.py`, templates, tests, and docs.

Explicitly out of scope:

- Membrane
- Rube MCP
- Composio
- arbitrary MCP tool execution
- Search Console behavior in BOS core/chat/router code

BOS shape remains:

```text
CMO → BOS capability manifest → Search Console plugin Transform → plugin-local Google Search Console connector → Workspace artifact
```

Not:

```text
CMO → Membrane/Rube/Composio/Search Console tool directly
```

## Native API surfaces learned

Read/diagnostic surfaces:

- sites/properties list and get
- search analytics query
- URL inspection
- sitemaps list and get
- mobile-friendly test only if supported by the selected native API surface and still available

Write/control surfaces that must be separate approval-gated capabilities later:

- add site
- delete site
- submit sitemap
- delete sitemap

Current v1 target should be read-only intelligence and recommendation artifacts first.

---

## 1. Capability Card

User asks:

```text
what can you do with search console?
```

Tool action: none.

Expected artifact/card:

```json
{
  "artifact_type": "capability_card",
  "block_type": "search_console_capability_card",
  "status": "needs_setup",
  "title": "Search Console Specialist",
  "summary": "I can inspect organic search visibility, find query/page opportunities, detect CTR or ranking issues, and surface indexing or sitemap signals.",
  "jobs_supported": [
    "marketing.optimize"
  ],
  "current_access_levels": {
    "discover_properties": true,
    "read_query_performance": true,
    "read_page_performance": true,
    "read_indexing_signals": true,
    "read_sitemaps": true,
    "inspect_url": true,
    "draft_seo_opportunities": true,
    "submit_sitemap": false,
    "delete_sitemap": false,
    "add_or_delete_site": false,
    "change_site_or_search_console_settings": false
  },
  "allowed_next_steps": [
    "Check connected Search Console properties",
    "Pull query/page performance",
    "Inspect an important URL",
    "Review sitemap status",
    "Find SEO growth opportunities"
  ],
  "forbidden_outcomes": [
    "No Search Console tool runs from a capability question",
    "No website edits",
    "No Search Console setting changes",
    "No sitemap submission or deletion without a future approval-gated action capability",
    "No fake ranking claims",
    "No SEO fixes applied automatically"
  ]
}
```

---

## 2. Property Inventory Artifact

Target capability:

```text
marketing.channel.search_console.properties.list
```

User asks:

```text
check search console properties
```

Native API action:

- Search Console `sites.list`.

Expected artifact:

```json
{
  "artifact_type": "intelligence_artifact",
  "block_type": "search_console_property_inventory",
  "status": "succeeded",
  "read_only": true,
  "changed_resources": [],
  "connector": {
    "protocol": "google_search_console_api",
    "connection_status": "active",
    "host_injected_credentials": true
  },
  "properties": [
    {
      "site_url": "sc-domain:motormoto.com",
      "permission_level": "siteOwner",
      "property_type": "domain"
    },
    {
      "site_url": "https://www.motormoto.com/",
      "permission_level": "siteFullUser",
      "property_type": "url_prefix"
    }
  ],
  "recommended_property": "sc-domain:motormoto.com",
  "warnings": [
    "URL-prefix properties require exact protocol and trailing slash. Domain properties use sc-domain:example.com."
  ],
  "forbidden_outcomes": [
    "Do not add or delete sites from property inventory",
    "Do not auto-select a property for a different brand",
    "Do not expose OAuth tokens or connection secrets"
  ]
}
```

---

## 3. Query/Page Performance Artifact

Target capability:

```text
marketing.channel.search_console.performance.query
```

User asks:

```text
show me search console performance for the last 28 days
```

Native API action:

- Search Console Search Analytics `query`
- Parameters: `site_url`, `start_date`, `end_date`, `dimensions`, `search_type`, `row_limit`, `start_row`, `aggregation_type`, `data_state`

Expected artifact:

```json
{
  "artifact_type": "intelligence_artifact",
  "block_type": "search_console_performance_report",
  "status": "succeeded",
  "site_url": "sc-domain:motormoto.com",
  "date_range": {
    "start_date": "2026-04-15",
    "end_date": "2026-05-13",
    "data_delay_note": "Search Console data can lag by 2–3 days; fresh data may still change."
  },
  "search_type": "web",
  "dimensions": [
    "query",
    "page"
  ],
  "read_only": true,
  "changed_resources": [],
  "totals": {
    "clicks": 1840,
    "impressions": 92400,
    "ctr": 1.99,
    "average_position": 12.7
  },
  "top_queries": [
    {
      "query": "used motorcycles near me",
      "clicks": 320,
      "impressions": 10400,
      "ctr": 3.08,
      "position": 5.8,
      "signal": "strong"
    },
    {
      "query": "motorcycle financing",
      "clicks": 42,
      "impressions": 8800,
      "ctr": 0.48,
      "position": 8.9,
      "signal": "ctr_opportunity"
    }
  ],
  "top_pages": [
    {
      "page": "https://www.motormoto.com/used-motorcycles",
      "clicks": 510,
      "impressions": 18600,
      "ctr": 2.74,
      "position": 6.2,
      "signal": "core_visibility_page"
    }
  ],
  "pagination": {
    "row_limit": 1000,
    "start_row": 0,
    "max_rows_per_request": 25000
  },
  "forbidden_outcomes": [
    "Do not claim rankings improved from this report alone",
    "Do not fabricate conversion or revenue data not present in Search Console",
    "Do not edit titles, pages, schemas, sitemaps, or site content"
  ]
}
```

---

## 4. URL Inspection Artifact

Target capability:

```text
marketing.channel.search_console.url.inspect
```

User asks:

```text
inspect https://www.motormoto.com/used-motorcycles
```

Native API action:

- URL Inspection API `index.inspect`
- Parameters: `inspection_url`, `site_url`, `language_code`

Expected artifact:

```json
{
  "artifact_type": "intelligence_artifact",
  "block_type": "search_console_url_inspection",
  "status": "succeeded",
  "site_url": "sc-domain:motormoto.com",
  "inspection_url": "https://www.motormoto.com/used-motorcycles",
  "read_only": true,
  "changed_resources": [],
  "indexing": {
    "verdict": "PASS",
    "coverage_state": "Submitted and indexed",
    "robots_txt_state": "ALLOWED",
    "indexing_state": "INDEXING_ALLOWED",
    "last_crawl_time": "2026-05-10T14:20:00Z",
    "google_canonical": "https://www.motormoto.com/used-motorcycles",
    "user_canonical": "https://www.motormoto.com/used-motorcycles"
  },
  "rich_results": {
    "detected": true,
    "items": [
      "Breadcrumb",
      "Product"
    ]
  },
  "warnings": [
    "Inspection URL must belong under the selected Search Console property."
  ],
  "recommended_next_step": "No indexing action needed. Review CTR opportunities for this page instead.",
  "forbidden_outcomes": [
    "Do not claim the page was submitted or reindexed",
    "Do not request indexing unless a future approved action capability exists",
    "Do not inspect URLs outside the selected property"
  ]
}
```

---

## 5. Sitemap Report Artifact

Target capability:

```text
marketing.channel.search_console.sitemaps.read
```

User asks:

```text
check my sitemaps
```

Native API actions:

- Search Console `sitemaps.list`
- Search Console `sitemaps.get`

Expected artifact:

```json
{
  "artifact_type": "intelligence_artifact",
  "block_type": "search_console_sitemap_report",
  "status": "succeeded",
  "site_url": "sc-domain:motormoto.com",
  "read_only": true,
  "changed_resources": [],
  "sitemaps": [
    {
      "feedpath": "https://www.motormoto.com/sitemap.xml",
      "type": "WEB",
      "is_pending": false,
      "is_sitemaps_index": true,
      "last_submitted": "2026-04-20T08:00:00Z",
      "last_downloaded": "2026-05-12T03:12:00Z",
      "warnings": 0,
      "errors": 0,
      "contents": [
        {
          "type": "web",
          "submitted": 420,
          "indexed": 392
        }
      ],
      "signal": "healthy"
    }
  ],
  "allowed_next_steps": [
    "inspect_problem_urls",
    "draft_sitemap_fix_notes",
    "dismiss"
  ],
  "forbidden_outcomes": [
    "Do not submit a sitemap from a read report",
    "Do not delete a sitemap from a read report",
    "Do not claim all submitted URLs are indexed unless Search Console data confirms it"
  ]
}
```

---

## 6. SEO Opportunity Artifact

Target capability:

```text
marketing.channel.search_console.opportunities.plan
```

User asks:

```text
find organic search opportunities
```

Expected artifact:

```json
{
  "artifact_type": "decision_artifact",
  "block_type": "search_console_opportunity_plan",
  "status": "pending_review",
  "risk_level": "review_only",
  "site_url": "sc-domain:motormoto.com",
  "summary": "Found 3 organic search opportunities: low-CTR queries, page-two keywords, and pages with declining impressions.",
  "opportunities": [
    {
      "opportunity_id": "seo_001",
      "severity": "high",
      "type": "low_ctr_high_impression_query",
      "evidence": "Query 'motorcycle financing' has 8,800 impressions, position 8.9, but only 0.48% CTR.",
      "recommended_action": "Draft title/meta updates for the financing page around trust, approval speed, and local availability.",
      "proposed_artifact": "seo_title_meta_update_draft",
      "requires_site_change": true,
      "auto_apply": false
    },
    {
      "opportunity_id": "seo_002",
      "severity": "medium",
      "type": "page_two_keyword",
      "evidence": "Query 'beginner motorcycles' averages position 13.4 with 5,200 impressions.",
      "recommended_action": "Draft a beginner-bike buying guide brief and internal-link recommendations.",
      "proposed_artifact": "content_optimization_brief",
      "requires_site_change": true,
      "auto_apply": false
    },
    {
      "opportunity_id": "seo_003",
      "severity": "medium",
      "type": "sitemap_indexing_gap",
      "evidence": "Sitemap shows 420 submitted URLs and 392 indexed URLs.",
      "recommended_action": "Inspect representative non-indexed URLs and draft technical notes before any site change.",
      "proposed_artifact": "indexing_review_brief",
      "requires_site_change": false,
      "auto_apply": false
    }
  ],
  "allowed_actions": [
    "draft_content_brief",
    "draft_title_meta_updates",
    "inspect_selected_urls",
    "dismiss"
  ],
  "forbidden_actions": [
    "auto_edit_website",
    "claim_rankings_will_improve",
    "submit_sitemap_without_approval",
    "request_indexing_without_approval"
  ]
}
```

---

## 7. Future Approval-Gated Action Result — Sitemap Submit

This is **not v1 read-only scope**, but defines the action boundary early.

Target future capability:

```text
marketing.channel.search_console.sitemap.submit
```

User intent after reviewing a sitemap recommendation:

```text
approve submitting the sitemap
```

Expected action-result artifact:

```json
{
  "artifact_type": "action_result",
  "block_type": "search_console_sitemap_action_result",
  "status": "succeeded",
  "approved_by": "operator",
  "source_artifact_id": "run_seo_123",
  "site_url": "sc-domain:motormoto.com",
  "action": "submit_sitemap",
  "feedpath": "https://www.motormoto.com/sitemap.xml",
  "changed_resources": [
    {
      "resource_type": "sitemap",
      "resource_name": "https://www.motormoto.com/sitemap.xml",
      "action": "submitted"
    }
  ],
  "audit_note": "Only the approved sitemap submission was sent. No site content, Search Console properties, or other sitemaps were changed."
}
```

Forbidden if no approval:

```json
{
  "artifact_type": "action_result",
  "block_type": "search_console_sitemap_action_result",
  "status": "blocked",
  "reason_code": "approval_required",
  "changed_resources": [],
  "message": "Sitemap submission requires an approved source artifact. No Search Console changes were made."
}
```

---

## Global Forbidden Outcomes

```json
[
  "No Search Console tool runs from capability questions",
  "No website edits",
  "No sitemap submission unless explicitly approved in a future action capability",
  "No sitemap deletion without second confirmation",
  "No add-site or delete-site actions in v1",
  "No fake ranking guarantees",
  "No claiming Google has indexed something unless API data confirms it",
  "No using the wrong site_url format silently",
  "No CMO router hardcoding",
  "No BOS core Search Console logic",
  "No exposed OAuth tokens, refresh tokens, API keys, or connector secrets"
]
```

## Acceptance Questions

Before reverse-spec/build, confirm:

1. Should v1 be read-only only: properties, performance, URL inspection, sitemaps, and opportunity plan?
2. Confirm native Google Search Console API only — no Membrane, Rube, Composio, or MCP sidecar.
3. Should sitemap submit be deferred to v2 as approval-gated action?
4. Should URL inspection be single-URL only in v1, or support a small batch from an opportunity plan?
