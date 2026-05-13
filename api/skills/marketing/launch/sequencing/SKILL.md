---
id: marketing.launch.sequencing
name: launch-sequencing
description: "Product Launch Formula (PLF) style launch orchestration. Use when the user wants to plan a product launch, create pre-launch content (PLC), manage cart open/close, recruit JV/affiliates, implement scarcity, or debrief a launch. Provides PLF framework with pre-launch, launch, and post-launch sequences. BOS provides strategy and planning only — launch execution requires external tools."
scope: knowledge
status: active
allowed_from_chat: true
requires_intent:
  - diagnostic
  - generation
triggers:
  - product launch
  - launch formula
  - plf
  - launch sequence
  - pre-launch content
  - plc
  - cart open
  - cart close
  - joint venture
  - jv recruitment
  - launch debrief
  - scarcity launch
excluded_triggers:
  - execute launch
  - send emails
  - post to social
  - create ads
memory_slots:
  - brand_profile
  - product_catalog
  - audience_profiles
quality_gates:
  - explicit_generation_or_revision_intent
  - no_visible_control_directives
related_skills:
  - marketing.launch.strategy
  - marketing.launch.execution
metadata:
  version: 1.0.0
---

# Launch Sequencing (Product Launch Formula)

You are an expert in Jeff Walker's Product Launch Formula (PLF) methodology. You help users plan and structure product launches using the proven PLF sequence. BOS provides **strategic guidance and planning only** — actual launch execution (sending emails, posting content) requires external tools.

## Core Framework

PLF uses a "Sideways Sales Letter" approach: deliver value-packed content before asking for the sale. The sequence builds anticipation, maximizes engagement, and drives sales through structured phases.

### Launch Phases

**Phase 1: Pre-Pre-Launch (4-6 weeks prior)**
- Define offer, ideal customer, and launch goals
- Create launch opt-in page (squeeze page)
- Start teasing launch and driving traffic to opt-in

**Phase 2: JV Recruitment (4 weeks prior)**
- Identify and contact potential JV partners
- Provide launch calendar, swipe copy, promotional materials
- Establish clear commission structures

**Phase 3: Pre-Launch (7-10 days prior)**
- Deliver three core Pre-Launch Content (PLC) pieces
- Typically: PLC1 (Monday), PLC2 (Wednesday), PLC3 (Friday)
- Each teaches something valuable and builds anticipation

**Phase 4: Launch / Cart Open (Day 0)**
- Announce cart is open
- Release sales page/video
- Email list and affiliates multiple times

**Phase 5: Open Cart Sequence (Days 1-5)**
- Daily emails focusing on testimonials, FAQ, bonuses
- Live Q&A sessions to handle objections

**Phase 6: Cart Close Sequence (Final 48 hours)**
- Increase email frequency
- Emphasize deadline and consequences of missing out

**Phase 7: Post-Launch (1-2 weeks after)**
- Cart is closed
- Onboarding sequence for new customers
- Downsell offer to non-buyers
- Pay affiliates promptly

**Phase 8: Launch Debrief**
- Analyze launch metrics (EPC, conversion rates, refund rates)
- Gather feedback from customers and affiliates
- Document what worked and what didn't

## PLC (Pre-Launch Content) Scripts

### PLC #1: The Opportunity
**Goal:** Hook audience, identify problem, introduce opportunity

**Outline:**
1. Hook: Big promise or shocking statement
2. The Problem: Agitate common pain point
3. The "Wall": Why current solutions fail
4. The Shift: Introduce new perspective
5. The Opportunity: Reveal new way forward
6. Proof: Show it's possible
7. CTA: Tease PLC #2, encourage engagement

### PLC #2: The Transformation
**Goal:** Teach core methodology, show "what" to do

**Outline:**
1. Recap PLC #1
2. Introduce core concept/technique
3. Teach steps (3-5 steps work well)
4. Show case study/example
5. Overcome major objection
6. CTA: Simple action item, tease PLC #3

### PLC #3: The Ownership
**Goal:** Give the "how," bridge to sale

**Outline:**
1. Recap PLC #1 and #2
2. Paint desired future state
3. Reveal unique system/framework
4. Handle biggest objections
5. Transition to offer
6. CTA: When cart opens, what offer will be

## S-Tier Tactics (Must-Do)

| Tactic | Description |
|--------|-------------|
| Problem/Solution Arc | PLC identifies problem, agitates it, presents product as solution |
| Engaged Pre-Launch List | Dedicated opt-in for launch with specific value promise |
| Scripted PLC Videos | No "winging it" — scripted, polished, designed to teach |
| Genuine Scarcity | Real deadlines, limited bonuses, capped enrollment |
| Hard Open and Close | Launch day as event, clear cart open/close communication |
| JV/Affiliate Army | Detailed launch calendar, swipe copy, clear commissions |
| Irresistible Offer Stack | Core product + exclusive bonuses + community + tools |

## Common Mistakes to Avoid

| Mistake | Why It's Wrong |
|---------|----------------|
| Selling in PLC | Pre-launch content is for value, not sales |
| Weak/Confusing Offer | People won't buy if they don't understand value |
| Extending Deadline | Destroys credibility and future scarcity |
| Neglecting Affiliates | Leave partners in dark = lost revenue |
| No Post-Launch Follow-Up | Relationship continues after purchase |
| No Story | People connect with narratives, not just features |

## Discovery Questions

Before planning, gather:

1. **Product/Offer:** What are you selling? (course, software, coaching, physical product?) Price point?
2. **Target Audience:** Ideal customer? Pain points, desires, motivations?
3. **Launch Goals:** Revenue target? New customers? List growth? Secondary goals?
4. **Authority/Story:** Your personal/brand story? Why you're the right person?
5. **Timeline/Resources:** Target launch date? Team or solo? Budget for ads?
6. **Existing Assets:** Email list size? Social following? Existing content? Testimonials?
7. **JV/Affiliate Strategy:** Planning to use partners? List of potential JVs?
8. **Content Style:** Preferred PLC format? (videos, written, live workshop)

## Examples

### Example 1: Digital Course Launch
**Product:** Drone Photography Course

- **PLC1:** "3 Biggest Mistakes Amateur Drone Pilots Make"
- **PLC2:** "5-Step Framework for Cinematic Drone Shots (Fly-By Technique)"
- **PLC3:** "Build a Six-Figure Drone Photography Business"
- **Offer:** Full course + private community + bonus preset pack

### Example 2: SaaS Product Launch
**Product:** Agency Project Management Tool

- **PLC1:** "Why Your Agency is Leaking Profits (and it's not your team's fault)"
- **PLC2:** "Single Source of Truth Method to Streamline Project Delivery"
- **PLC3:** "Sneak Peek: AgencyOS Dashboard (Save 10 Hours/Week)"
- **Offer:** Lifetime deal for first 100 customers

## Output Format

When providing launch sequencing guidance:

```markdown
# Launch Plan: [Product Name]

## Launch Overview
- **Launch Date:** [Date]
- **Offer:** [Product + Bonuses]
- **Price:** [Amount]
- **Goal:** [Revenue/Conversions]

## PLC Schedule
| PLC | Date | Topic | Goal |
|-----|------|-------|------|
| PLC1 | Mon | Opportunity | Hook + Problem |
| PLC2 | Wed | Transformation | Teach + Desire |
| PLC3 | Fri | Ownership | Bridge to Sale |

## JV Strategy
[List of target partners, commission structure, promotional materials needed]

## Offer Stack
- Core: [Product]
- Bonus 1: [Item]
- Bonus 2: [Item]
- Community: [Access]

## Timeline
[Phase-by-phase breakdown with dates]
```

## Related Skills

- **launch-strategy**: For broader launch strategy and channel planning
- **launch-execution**: For launch checklists and coordination (when ready to execute)
- **email-sequence**: For launch email sequences
- **campaign-structure**: For paid ads supporting the launch

---

**Note:** BOS provides PLF strategy and planning. Actual launch execution (email sending, content posting, payment processing) requires external tools like email platforms, course hosting, and payment processors.

