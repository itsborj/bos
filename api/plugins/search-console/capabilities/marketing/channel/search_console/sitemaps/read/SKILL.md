---
id: marketing.channel.search_console.sitemaps.read
name: Search Console Sitemap Report
description: Read-only Search Console sitemap report. Use when the user asks to check, list, review, or get Search Console sitemaps, sitemap status, sitemap errors, sitemap warnings, submitted URLs, indexed URLs, or sitemap health. Never submits or deletes sitemaps.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.search_console.sitemaps.read
requires_intent:
  - diagnostic
  - generation
triggers:
  - search console sitemap
  - search console sitemaps
  - google search console sitemap
  - gsc sitemap
  - check my sitemaps
  - list sitemaps
  - sitemap status
  - sitemap errors
  - sitemap warnings
excluded_triggers:
  - what can you do
  - search console capabilities
  - submit sitemap
  - delete sitemap
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.search_console.sitemaps.read
output_contract:
  - search_console_sitemap_report
quality_gates:
  - read_only_only
  - no_sitemap_mutation
metadata:
  version: 0.1.0
  plugin_id: channel.search_console
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_search_console
  output_contract: search_console_sitemap_report
  risk_policy: read_only_no_mutation
---

# Search Console Sitemap Report

Returns a read-only report of submitted sitemaps and their errors, warnings, submitted URLs, and indexed URLs.

Never submit or delete sitemaps.
