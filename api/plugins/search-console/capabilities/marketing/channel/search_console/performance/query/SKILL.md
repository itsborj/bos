---
id: marketing.channel.search_console.performance.query
name: Search Console Performance Report
description: Read-only Google Search Console search analytics report. Use when the user asks to check, pull, show, query, review, or report organic search performance, queries, pages, clicks, impressions, CTR, average position, SEO visibility, page-two terms, or low-CTR opportunities. Never edits website content or Search Console settings.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.search_console.performance.query
requires_intent:
  - diagnostic
  - generation
triggers:
  - search console performance
  - google search console performance
  - gsc performance
  - search console queries
  - search console pages
  - organic search performance
  - search analytics
  - search console clicks
  - search console impressions
  - search console ctr
  - average position
  - seo visibility
excluded_triggers:
  - what can you do
  - search console capabilities
  - search console properties
  - gsc properties
  - inspect url
  - url inspection
  - sitemap
  - submit sitemap
  - delete sitemap
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.search_console.performance.query
output_contract:
  - search_console_performance_report
quality_gates:
  - read_only_only
  - no_site_or_sitemap_mutation
metadata:
  version: 0.1.0
  plugin_id: channel.search_console
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_search_console
  output_contract: search_console_performance_report
  risk_policy: read_only_no_mutation
---

# Search Console Performance Report

Returns read-only query/page performance: clicks, impressions, CTR, and average position.

Never edit website content, submit/delete sitemaps, add/delete sites, or request indexing.
