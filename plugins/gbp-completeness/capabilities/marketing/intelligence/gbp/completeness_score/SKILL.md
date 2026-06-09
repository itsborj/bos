---
id: marketing.intelligence.gbp.completeness_score
name: gbp-completeness-score
description: Score the brand's Google Business Profile on the 8 critical ranking fields — primary category, additional categories, business name, address, phone, website, hours, and verification status. Returns a 0-100 completeness score with field-level gaps. Use when a local brand asks how complete their Google profile is, wants a GBP audit, or asks why they're not showing up in local search.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.intelligence.gbp.completeness_score
requires_intent:
  - diagnostic
triggers:
  - gbp audit
  - google business profile score
  - how complete is my google profile
  - local seo audit
  - google listing audit
  - check my google business profile
  - gbp completeness
  - why am i not showing up in local search
  - google business profile completeness
  - google maps listing
  - local search ranking
excluded_triggers:
  - google analytics
  - ga4
  - analytics report
  - traffic data
  - sessions
  - pageviews
  - search console
  - search performance
  - indexing
  - crawl errors
  - google ads
  - paid search
  - ad campaign
  - keywords
  - tag manager
  - gtm
  - on-page seo
  - meta tags
  - schema markup
  - page speed
  - core web vitals
output_contract:
  - gbp_completeness_result
quality_gates:
  - no_external_action
  - structured_block_present
metadata:
  version: 0.1.0
  plugin_id: channel.gbp-completeness
  implements: marketing.execute
  artifact_type: intelligence_result
  platform: google_business
  risk_policy: read_only_external_api
---

## What this capability does

Fetches the brand's Google Business Profile via the GBP API and scores
the 8 critical fields that directly impact local search ranking:

1. Primary category
2. Additional categories (optimized: 3–5)
3. Business name
4. Physical address
5. Phone number (optimized: local, not toll-free)
6. Website URL
7. Business hours (optimized: all 7 days set)
8. Verified status (flagged as manual check — not exposed via API)

Scoring: Present + Optimized = 2pts, Present = 1pt, Missing = 0pts.
Max 16 pts, normalized to 0–100.

## When to invoke

- Brand asks about their Google Business Profile completeness or score
- Operator wants to identify GBP gaps before a local SEO campaign
- Brand asks why they're not showing in local search or Google Maps

## When NOT to invoke

- Request is about on-page SEO (meta tags, schema markup, page speed)
- Request is about Google Ads or paid local campaigns
- Brand has no physical location and is not a service-area business

## Output contract

Returns a `gbp_completeness_result` artifact block:
- `score` — integer 0–100
- `rating` — "Excellent" | "Good" | "Needs Work" | "Poor" | "Critical"
- `raw_score` — points earned out of 16
- `fields` — list of field objects: name, status, points, note
- `data_source` — "Google Business Profile API v1"
