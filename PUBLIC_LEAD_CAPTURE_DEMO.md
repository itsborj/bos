# Public Lead Capture Demo — Mini Project Brief

**Date:** 2026-06-04  
**Status:** Parked — discovery/sample only; do not build until revisited and approved through BITE  
**Related sample:** `sample/public_website_to_plan_demo_klaroha.html`  
**Critical correction:** the sample is close visually, but it incorrectly recreates the marketing-plan capability instead of calling the internal Strategy Workflow capability. That must not become the product architecture.

---

## 1. Purpose

Create a public-facing lead-capture demo for Klaroha that turns a visitor's supplied website/company material into:

1. a **Business Profile Draft**
2. a lightweight public correction/enrichment chat
3. a **Marketing Plan Preview** using the same internal planning capability BOS already uses
4. an email / waitlist capture CTA

The demo should prove Klaroha's promise before login:

> Klaroha reads what your business already says publicly, shows what it understands, then turns that understanding into a marketing plan you can save.

---

## 2. Non-Negotiable Architecture

The public demo must **call the existing internal planning capability**. It must not recreate the Strategy Workflow, duplicate its prompts, duplicate its output structure, or maintain a second public-only marketing-plan generator.

Correct shape:

```text
Public visitor
  → public intake wrapper
  → exact-URL scraper / text extractor
  → provisional Brand Profile draft
  → public correction chat updates provisional profile only
  → server-side call into existing BOS planning capability
  → marketing plan preview rendered publicly
  → email / waitlist capture
```

Incorrect shape:

```text
Public visitor
  → standalone public HTML/app
  → separately authored marketing plan sections
  → manually recreated Strategy Workflow logic
```

Why this matters:

- One capability should own planning quality.
- Improvements to `marketing.planning.strategy_workflow` should automatically improve the public demo.
- The public demo should be a wrapper/intake/onboarding funnel, not a second product brain.
- Avoid maintaining two versions of the same planning methodology.

---

## 3. Public Inputs

### Required

1. **About Us page URL**
   - Example: `https://company.com/about`
   - Purpose: company narrative, mission, positioning, credibility language

2. **Product / Service page URL(s)**
   - Repeatable field
   - Minimum: 1
   - Recommended: 1–5
   - V1 hard cap: 10
   - Purpose: understand what the company sells without crawling the whole site

### Optional

3. **Homepage URL**
   - Purpose: hero claim, CTA, top-level offer, lead-capture path

4. **PDF / text upload or pasted company material**
   - PDF text
   - TXT
   - brochure copy
   - company profile
   - pitch deck text export

5. **Extra context**
   - Prompt: “Anything your website does not explain clearly?”

### Minimal Planning Context

These reduce bad extrapolation without turning the public demo into full onboarding:

- Primary marketing goal
  - generate leads
  - book consultations
  - sell products online
  - launch a new offer
  - improve positioning
  - other
- Business type
  - local service
  - professional service
  - ecommerce
  - SaaS/software
  - agency
  - education/training
  - other
- Primary market / location
- Optional: priority product/service
- Optional: plan focus
  - fast lead capture
  - trust building
  - content strategy
  - paid acquisition readiness
  - sales funnel cleanup
  - launch sequence

---

## 4. Scraping / Extraction Rules

The public demo is intentionally constrained.

Allowed:

- Fetch only URLs explicitly supplied by the visitor.
- Extract visible page text and basic metadata.
- Read pasted text / uploaded PDF text.
- Summarize product/service pages supplied by the user.
- Label evidence as found, inferred, or needs confirmation.

Forbidden:

- No whole-site crawl.
- No sitemap crawl.
- No ecommerce inventory crawl.
- No category-tree crawling.
- No social scraping in V1.
- No private/internal URL access.
- No localhost, RFC1918/private IP, metadata IP, or file URL fetches.
- No connector actions, publishing, ad spend, or external account reads.

Ecommerce rule:

> If the company has hundreds of products, do not scrape the inventory. Ask the visitor to provide the specific product/service URLs they want included. If they provide a category page, summarize only what is visible on that page and mark product coverage as incomplete.

---

## 5. First Deliverable — Business Profile Draft

Before any plan is generated, Klaroha should show the visitor what it understood.

The profile draft should include:

- Company name
- Company summary
- Products/services detected
- Likely audiences
- Current positioning
- Brand voice/tone
- Proof/trust signals found
- Current CTA / lead capture path
- Clear points
- Missing or unclear information
- Assumptions made

Every claim should carry confidence:

- **Found on supplied page/material**
- **Inferred from supplied page/material**
- **Needs confirmation**

This is the first public value moment and the seed for eventual onboarding.

---

## 6. Public Correction Chat

The public chat is not the BOS CMO chat and should not expose logged-in workspace behavior.

Allowed:

- Correct the provisional profile.
- Add missing products/services.
- Change audience priority.
- Remove outdated claims found on supplied pages.
- Clarify location, market, business model, offer priority, or voice.

Forbidden:

- No internal workspace access.
- No connector reads/writes.
- No platform-native artifact generation.
- No publishing.
- No capability catalog exposure.
- No separate marketing-plan logic.

The correction chat output is an updated provisional Brand Profile object used as input to the internal planning call.

---

## 7. Marketing Plan Preview

The plan should attempt the full internal marketing plan format even when inputs are incomplete.

Important framing:

> This plan is generated from only the pages and material you provided. Thin or missing inputs are labeled instead of guessed as fact.

Plan behavior:

- Structurally complete, because the existing internal planning capability owns the output shape.
- Honest about weak inputs.
- Uses confidence labels in the public rendering.
- Does not reveal internal capability IDs, prompts, provider details, or BOS mechanics.
- Does not duplicate the planning capability outside BOS.

Expected preview sections should mirror the existing Strategy Workflow rendering when possible:

- Market context
- Buyer map
- Strategic thesis
- Framework lenses, when available
- Offer architecture
- Channel stack
- Tactical funnel
- Channel/content matrix, when available
- Measurement model, when available
- Work orders

If internal components are not wired yet, the public demo should reflect that through normal capability output/status, not a separate handcrafted replacement.

---

## 8. Lead Capture CTA

The public demo should not require login to see value. Capture happens at the save/continue moment.

Primary CTA:

> Email this marketing plan to me

Fields:

- Work email
- Name
- Company name, if not confidently extracted

Secondary CTA:

> Join the Klaroha waitlist

Fields:

- Email
- Optional: “I want early access for…”

Email content should include:

- Business Profile Draft
- Marketing Plan Preview
- Missing-information checklist
- Link/CTA to continue onboarding when available

---

## 9. Onboarding Handoff — Future

When the user later joins/logs in, the public demo can become the first onboarding step.

Claimed demo should create or prefill:

- Draft Brand record
- Source URLs
- Extracted profile
- Correction transcript
- Strategy Workflow / plan preview reference
- Missing-context checklist

Then logged-in onboarding continues:

1. Confirm company facts
2. Confirm products/services
3. Approve Campaign Brand Kit
4. Generate/review the full internal Strategy Workflow
5. Connect specialists/channels

---

## 10. Security Boundary

Public endpoints should be constrained wrappers, not public BOS access.

Requirements:

- No public BOS API key in browser.
- No direct public access to `/strategy-workflows/:id` unless intentionally exposed through a safe public share layer.
- No workspace data access.
- No connector access.
- No capability IDs required in public UI.
- Server-side URL validation and SSRF protections.
- Upload size limits.
- Fetch timeouts.
- Rate limits.
- Store data only after email consent or explicit save/claim action.

---

## 11. Current Sample Status

A self-contained HTML page exists at:

- `sample/public_website_to_plan_demo_klaroha.html`
- Served during discussion at: `http://localhost:8787/public_website_to_plan_demo_klaroha.html`

Sample quality note:

- The layout, intake fields, output framing, confidence labels, correction chat, and email/waitlist CTA are close.
- The major flaw is architectural: the marketing plan preview was manually recreated in the sample HTML instead of representing a call into the actual internal planning capability.
- Treat this HTML as a visual/conversation artifact only, not an approved implementation sample.

---

## 12. BITE Status

Current stage: **Discuss / rough sample exploration**

Not yet approved:

- final sample output
- public wrapper contract
- endpoint design
- extraction schema
- plan rendering contract
- onboarding handoff contract

Before build:

1. Produce a revised BITE sample that shows the public page calling/reusing the internal Strategy Workflow output shape.
2. Include allowed and forbidden outcomes.
3. Get explicit approval.
4. Reverse-spec from the approved sample.
5. Build only the wrapper/extraction/handoff surfaces needed — not a duplicate planning capability.

---

## 13. Session Notes — 2026-06-05

### Revised sample

A second prototype exists at:

- `sample/prototypes/lead-capture.html`
- Served at: `http://localhost:8787/lead-capture.html`
- Skip to results state: `http://localhost:8787/lead-capture.html?results`

Uses Klaroha itself as the sample input and output. All 6 wired Strategy Workflow components are populated with Klaroha-specific content. Components 7–10 render as "needs data" — honest about input limits, consistent with the locked not-wired status in the live app.

Same architectural caveat as the previous sample: the plan content is hardcoded in the HTML, not a live call into `marketing.planning.strategy_workflow`. This is a visual/conversation artifact only.

---

### Decisions settled in this session

**Scraping scope — URL-explicit only**

Only scrape URLs the visitor explicitly provides. No sitemap crawl, no followed links, no pagination, no inventory crawl. Ecommerce rule: if they have hundreds of products, ask for specific product page URLs or a category/featured-products page. Only what they gave gets read.

**Input fields confirmed**

Required:
- About Us page URL
- Products / Services page URL (minimum 1)
- Email address

Optional:
- Product / Service URL 2
- Product / Service URL 3 (hard cap at 3 additional — 4 product/service URLs total)
- One social profile URL (tone and audience signal only — not scraped in V1 if behind auth)

The "minimal planning context" dropdowns (goal, business type, market) from Section 3 are deferred. The session decision was to keep intake as short as possible: paste URLs, get plan. Those context fields may be reintroduced if extraction quality proves too low without them.

PDF / text upload is deferred to a future iteration. URL-only for V1.

**Plan output scope**

Attempt the full Strategy Workflow output regardless of input completeness. Thin components render with honest confidence framing ("based on your About Us and 1 product page"). Do not limit to 3 components on thin input — the structural completeness is part of the value signal.

**Public correction chat**

Dropped from V1 scope. The correction step adds friction on a lead magnet without clear conversion benefit. Incompleteness is acceptable — it is implicitly an argument for deploying the full stack. The correction/enrichment experience belongs inside BOS after claim.

**CTA — email first, waitlist second**

Primary: "Email this to me" — captures the lead, delivers value immediately.
Secondary: "Join the waitlist" — signals deployment intent.

Both require only email. No name, no company name field at CTA time (company name is extracted from scraping; if not found it is absent, not re-asked).

**Email delivery content**

Strategy delivered in full. Follow-up sequence (not yet designed):
- Day 1 — strategy document
- Day 3 — what BOS does with this strategy
- Day 7 — waitlist / early access invitation
- Day 14 — first case study (when available)

**Login wall position**

The plan renders publicly without login. Login / claim is triggered only when the user wants to save, execute, or continue. The unclaimed run has a TTL (exact duration not decided — suggest 7 days).

**Architecture constraint (confirmed from Section 2)**

The public wrapper calls the internal `marketing.planning.strategy_workflow` capability server-side. The public UI never exposes capability IDs, prompt structure, provider details, or BOS mechanics. The plan preview is a rendered output only.
