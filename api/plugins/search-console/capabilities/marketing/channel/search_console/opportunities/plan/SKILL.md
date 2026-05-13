---
id: marketing.channel.search_console.opportunities.plan
name: Search Console SEO Opportunity Plan
description: Build a read-only SEO opportunity plan from Google Search Console query/page performance. Use when the user asks to find organic search opportunities, SEO opportunities, low CTR queries, page-two keywords, declining search visibility, organic growth ideas, or what to improve from Search Console data. This returns recommendations only and never edits the website or Search Console.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.search_console.opportunities.plan
requires_intent:
  - diagnostic
  - generation
  - discussion
triggers:
  - search console opportunities
  - organic search opportunities
  - seo opportunities
  - find organic search opportunities
  - find seo opportunities
  - low ctr queries
  - page two keywords
  - improve organic search
  - search visibility opportunities
excluded_triggers:
  - what can you do
  - search console capabilities
  - submit sitemap
  - delete sitemap
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.search_console.opportunities.plan
output_contract:
  - search_console_opportunity_plan
quality_gates:
  - read_only_only
  - no_site_or_sitemap_mutation
  - no_ranking_guarantees
metadata:
  version: 0.1.0
  plugin_id: channel.search_console
  implements: marketing.optimize
  artifact_type: decision_artifact
  platform: google_search_console
  output_contract: search_console_opportunity_plan
  risk_policy: read_only_recommendations_only
---

# Search Console SEO Opportunity Plan

Creates review-only SEO recommendations from Search Console performance data.

Never auto-edit website content, submit sitemaps, request indexing, or guarantee ranking improvements.
