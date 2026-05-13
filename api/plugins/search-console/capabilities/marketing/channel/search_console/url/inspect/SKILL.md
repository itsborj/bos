---
id: marketing.channel.search_console.url.inspect
name: Search Console URL Inspection
description: Read-only Search Console URL inspection. Use when the user explicitly asks to inspect a URL, check whether a URL/page is indexed, review indexing status, coverage, canonical, crawl, robots, or rich-result signals for a specific URL. Requires a URL. Never requests indexing or changes site content.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.search_console.url.inspect
requires_intent:
  - diagnostic
  - discussion
triggers:
  - inspect url
  - inspect page
  - url inspection
  - check indexing
  - is this indexed
  - search console inspect
  - google search console inspect
  - gsc inspect
  - indexing status
excluded_triggers:
  - what can you do
  - search console capabilities
  - submit sitemap
  - delete sitemap
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.search_console.url.inspect
output_contract:
  - search_console_url_inspection
quality_gates:
  - read_only_only
  - inspection_url_required
  - no_indexing_request
metadata:
  version: 0.1.0
  plugin_id: channel.search_console
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_search_console
  output_contract: search_console_url_inspection
  risk_policy: read_only_no_mutation
---

# Search Console URL Inspection

Inspects one URL via the native URL Inspection API and returns indexing/crawl/canonical signals.

Never request indexing, submit sitemaps, or edit website content.
