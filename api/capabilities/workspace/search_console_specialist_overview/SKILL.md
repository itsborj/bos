---
id: workspace.search_console_specialist_overview
name: search-console-specialist
description: Explains the Google Search Console Specialist — read-only organic search performance, query/page reports, URL inspection, sitemap monitoring, indexing signals, and SEO opportunity planning. Use for informational questions about Search Console capabilities, setup requirements, access needed, or what the specialist can do. Never dispatches Search Console tools.
version: 1.0.0
status: active
license: proprietary
compatibility:
  bos: ">=3.0.0"
metadata:
  author: BOS Core
  updated: "2026-05-20"
scope: workspace
allowed_from_chat: true
module_id: null
requires_intent:
  - discussion
  - generation
triggers:
  - what can you do with search console
  - what can search console do
  - search console capabilities
  - google search console capabilities
  - gsc capabilities
  - search console specialist
  - google search console specialist
  - what do i need for search console
  - what is needed for search console
  - search console setup
  - google search console setup
  - connect search console
  - connect google search console
excluded_triggers:
  - check search console performance
  - show search console performance
  - pull search console performance
  - search console queries
  - search console pages
  - search console properties
  - inspect url
  - url inspection
  - check my sitemaps
  - submit sitemap
  - delete sitemap
memory_slots:
  - brand_profile
quality_gates:
  - no_module_execution
  - no_search_console_read_from_info_question
  - no_site_or_sitemap_mutation
  - no_module_ids_in_reply
  - no_connector_secrets_in_reply
output_contract:
  - capability_card_not_execution
  - setup_requirements_when_asked
  - read_only_boundaries_stated
---

# Google Search Console Specialist

## Purpose

This skill answers informational questions about the Google Search Console Specialist. It is a capability card and setup guide, not a data-pull capability.

The specialist supports **marketing.optimize** by helping the CMO understand organic search visibility and SEO opportunities from Search Console data.

## Jobs Covered

1. **Property inventory** — list connected Search Console properties and permission levels.
2. **Performance reporting** — read query/page clicks, impressions, CTR, and average position.
3. **URL inspection** — inspect one important URL for indexing, crawl, canonical, robots, and rich-result signals.
4. **Sitemap monitoring** — review sitemap status, warnings, errors, submitted URLs, and indexed counts.
5. **SEO opportunity planning** — surface low-CTR queries, page-two keywords, declining visibility, and indexing gaps as review-only recommendations.

## Capability Card

When the user asks what Search Console can do, answer in this shape:

```
Search Console can help Optimize organic search:

• Properties — confirm which sites are connected
• Performance — queries, pages, clicks, impressions, CTR, average position
• URL inspection — indexing/crawl/canonical signals for a URL
• Sitemaps — status, warnings, errors, submitted/indexed counts
• SEO opportunities — low CTR, page-two terms, visibility drops, indexing gaps

Default: read-only. I do not edit the website, submit/delete sitemaps, request indexing, or change Search Console settings without a future approval-gated action.
```

## Setup Requirements

When the user asks what is needed, include:

- A verified Google Search Console property for the site.
- OAuth access for a Google account with permission to that property.
- Required environment/config values: `GOOGLE_SEARCH_CONSOLE_CLIENT_ID`, `GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET`, `GOOGLE_SEARCH_CONSOLE_REFRESH_TOKEN`, and `GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL`.
- The default site URL must be either a domain property like `sc-domain:example.com` or an exact URL-prefix property like `https://www.example.com/`.
- Brand/site mapping so the selected property matches the brand being analyzed.

Do not ask users to paste secrets into chat. Direct them to the secure admin/brand connection flow or operator environment setup.

## Routing Guidance

For informational/setup questions: answer directly from this skill. Append no `RUN:` line.

For explicit work requests:

- “check connected properties” → Search Console properties list
- “show performance / queries / pages / clicks / CTR” → Search Console performance report
- “inspect this URL” → URL inspection
- “check sitemaps” → sitemap report
- “find SEO/organic opportunities” → SEO opportunity plan

## Hard Boundaries

- Do not run Search Console tools from capability/setup questions.
- Do not edit website content.
- Do not submit or delete sitemaps in v1.
- Do not add/delete Search Console sites.
- Do not request indexing.
- Do not guarantee ranking improvements.
- Do not expose OAuth tokens, refresh tokens, client secrets, API keys, connector IDs, or backend logs.
