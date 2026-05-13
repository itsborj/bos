---
id: marketing.analytics.tracking
name: analytics-tracking
description: Use when the user wants to set up, audit, or optimize analytics tracking, GA4, event tracking, conversion tracking, attribution, data layer, gtag, User ID tracking, or CTA attribution. For traffic source insights and performance interpretation, use traffic-analysis.
scope: atomic_task
status: active
allowed_from_chat: true
requires_intent:
  - diagnostic
  - generation
  - discussion
triggers:
  - analytics
  - google analytics
  - ga4
  - event tracking
  - conversion tracking
  - attribution
  - gtag
  - data layer
  - user id tracking
  - cta attribution
memory_slots:
  - brand_profile
  - product_catalog
  - audience_profiles
  - campaign_brand_kit
  - analytics_summary
related_skills:
  traffic-analysis: Use for interpreting traffic trends and source attribution after tracking exists.
  google-search-console: Use for GSC analysis and SEO query/page data.
  seo-monitoring: Use for SEO article database and monitoring workflows.
required_context:
  - website_or_app
  - analytics_property_status
  - key_conversions
  - implementation_method
output_contract:
  - Event List
  - Implementation Notes
  - Conversion Mapping
  - Testing Checklist
quality_gates:
  - event_names_snake_case_under_40_chars
  - avoid_tracking_everything
  - include_testing_validation_steps
metadata:
  version: 1.3.1
---

# Analytics: Tracking

Guide analytics implementation for GA4 setup, event tracking, conversions, attribution, and data quality across web/app marketing channels.

## Scope

- GA4 web data stream and Google tag setup.
- User ID for cross-device/session identification.
- CTA attribution for content ROI.
- Recommended and custom events.
- Key events/conversions.
- Naming, testing, validation, and data quality.

## GA4 Setup

Prerequisites: GA4 property, web data stream, Google tag on all pages, and measurement ID. Enable enhanced measurement for page views, scrolls, outbound clicks, site search, file downloads, and YouTube video engagement when appropriate.

## Event Tracking

Event naming rules:

- <=40 characters.
- snake_case, lowercase.
- Verb first: `download_pdf`, `submit_form`, `video_play`.
- Include context when meaningful: `pricing_cta_click` instead of generic `click`.

Focus on 15-25 meaningful KPI-aligned events. Avoid tracking everything.

## Conversion Mapping

Mark important events as GA4 key events/conversions. Typical conversions: purchase, sign_up, lead, contact, demo_request, trial_start.

## Attribution

Clean UTMs plus reliable conversion events enable attribution reports. Inconsistent UTMs fragment data. Multi-touch attribution requires reliable touchpoint data.

## Testing & Validation

Use GA4 Realtime, DebugView, GTM Preview, or debug mode. Verify event names, parameters, duplicate events, missing values, conversion marking, and UTM consistency before launch.

## Output Format

- **Event list** — name, trigger, parameters.
- **Implementation notes** — gtag/GTM/data layer guidance.
- **Conversion mapping** — which events become key events.
- **Testing checklist** — validation steps before and after launch.
