---
id: marketing.channel.search_console.properties.list
name: Search Console Property Inventory
description: Read-only Google Search Console property inventory. Use when the user explicitly asks to list, check, discover, verify, or show Search Console properties/sites, site URLs, or connected GSC access. This capability never edits sites, sitemaps, indexing, or website content.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.search_console.properties.list
requires_intent:
  - diagnostic
  - discussion
triggers:
  - search console properties
  - search console sites
  - google search console properties
  - google search console sites
  - gsc properties
  - gsc sites
  - list search console properties
  - check search console properties
  - verify search console access
excluded_triggers:
  - what can you do
  - search console capabilities
  - search console performance
  - search console queries
  - inspect url
  - check indexing
  - sitemap
  - submit sitemap
  - delete sitemap
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.search_console.properties.list
output_contract:
  - search_console_property_inventory
quality_gates:
  - read_only_only
  - no_site_or_sitemap_mutation
metadata:
  version: 0.1.0
  plugin_id: channel.search_console
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_search_console
  output_contract: search_console_property_inventory
  risk_policy: read_only_no_mutation
---

# Search Console Property Inventory

Returns a read-only list of Search Console sites/properties available to the connected account.

Never add/delete sites, submit/delete sitemaps, request indexing, or edit website content.
