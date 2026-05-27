---
id: marketing.planning.gtm_plan
name: gtm-plan
version: 1.0.0
description: >
  Generate a structured go-to-market plan from the buyer intelligence map and
  message architecture. Also use for shorthand requests like "GTM", "another GTM",
  "new GTM", or "do another GTM" when the conversation is about go-to-market
  planning rather than Google Tag Manager containers. Select the right motion for the product, buyer, and
  company stage. Produce a dependency-ordered launch sequence, a channel stack
  with do-now/hold/avoid logic, a conversion path, a proof-building plan, and
  a leading-indicator measurement frame. All execution artifacts, publishing,
  spending, and external actions require separate approval. The GTM plan is a
  strategy artifact — not an execution order.
scope: module
status: active
allowed_from_chat: true
module_id: marketing.planning.gtm_plan
requires_intent:
  - discussion
  - generation
triggers:
  - gtm
  - gtm strategy
  - gtm plan
  - launch strategy
  - plan a launch
  - market entry
  - another gtm
  - new gtm
  - do another gtm
  - go to market
  - go-to-market
  - launch plan
  - plan a launch
  - market entry
  - new product launch
  - new service launch
  - first channels
  - first users strategy
  - demand capture strategy
  - launch motion
  - product launch strategy
  - service launch strategy
excluded_triggers:
  - draft email
  - write email
  - write ad
  - draft facebook post
  - create a facebook post
  - social post
  - generate image
  - matching visual
  - publish
  - send email
  - check performance
  - check inbox
  - capability question
  - what can you do
memory_slots:
  - brand_profile
  - product_catalog
  - audience_profiles
  - campaign_brand_kit
  - brand_guidelines
  - marketing_reports
  - campaign_reports
  - competitor_profiles
  - industry_data
depends_on:
  - reasoning.buyer_intelligence
  - marketing.messaging.architecture
  - brand_brief
required_upstream:
  - buyer_map.v1
  - message_architecture.v1
input_minimum: buyer_map + message_architecture + company_description
outputs:
  - gtm_plan.v1
quality_gates:
  - buyer_map_required
  - message_architecture_required
  - single_motion_selected
  - dependency_ordered_launch_sequence
  - max_three_do_now_channels
  - no_hallucinated_metrics
  - stage_gates_present
  - no_execution_without_approval
  - no_inline_chat_plan
metadata:
  version: 1.0.0
  author: bos-core
  implements: marketing.plan
  specialist: gtm_planning
  risk_policy: draft_only
  artifact_type: plan_artifact
  output_contract: gtm_strategy
  upstream_contracts:
    - buyer_map.v1
    - message_architecture.v1
  platform: planning
---

# GTM Plan Skill

## Purpose

The GTM plan answers one question: given what we know about the buyer, the message, and the company's current state — what is the fastest path from "product exists" to "we know what's working and why"?

It is not a marketing calendar. It is not a channel list. It is a dependency chain — a sequence of moves where each step unlocks the next, and skipping a step creates a failure the company will pay for later.

The buyer intelligence map tells the agent who the buyer is and what blocks them. The message architecture tells the agent what to say and at what awareness level. The GTM plan tells the agent where to say it, in what order, with what proof, and how to know if it's working.

---

## Input Contract

### Required inputs

```text
buyer_map               — Full output of reasoning.buyer_intelligence.
                          Confidence level propagates: inferred map produces
                          inferred GTM plan. All assumptions flagged.
message_architecture    — Full output of marketing.messaging.architecture.
                          Core message, positioning frame, proof arc, and
                          dominant blocking force are minimum required fields.
company_description     — From brand brief. Stage, team size, existing channels,
                          current traction if any.
```

### Optional enrichment inputs

```text
proof_assets            — Existing case studies, testimonials, named clients,
                          data. Determines how far into the channel stack the
                          company can operate today.
budget_signal           — Any indication of available spend. Absence defaults
                          the plan to lean-budget assumptions.
existing_audience       — Email list, LinkedIn following, community, partner
                          network. Presence changes launch sequence.
sales_motion            — Current sales path: inbound, outbound, referral,
                          self-serve, hybrid.
target_launch_date      — If present, compress sequence with explicit trade-offs.
```

### Industry inference layer

When company stage, proof assets, or budget signal are absent, infer from product category:

- Typical GTM motion for this category at this ACV
- Channel stack that reaches this buyer type at this awareness level
- Proof format most credible in this category
- Conversion path most common for this deal type
- Leading indicators that precede revenue in this category

Flag inferred elements as `source: industry_inference`. Client context overrides inference.

---

## Motion Selection

The motion is the single most important strategic decision in the GTM plan. Select the motion before generating anything else.

### Motion types

**Founder-led / direct outreach**
Best fit when ACV is high, proof is limited, trust is the primary barrier, the founder or seller has a relevant network, and the buyer needs a human relationship before committing.
Signals: `buyer_type: early_majority`, weak/no social proof, high anxiety, weak perceived likelihood.

**Product-led**
Best fit when ACV is low-to-mid, the product delivers value before commitment, self-serve activation is possible, and the buyer can experience outcome without sales.
Signals: solution/product aware, single decision-maker, low effort/sacrifice friction.

**Sales-led**
Best fit when ACV is high, sale involves multiple stakeholders, buyer needs diagnosis, and product requires configuration or implementation.
Signals: champion + economic buyer + veto players, early majority, high effort/sacrifice friction.

**Content-led**
Best fit when buying cycle is long, buyer is unaware/problem-aware/solution-aware, category requires education, and company can publish consistently.
Constraint: slow burn. Do not recommend as primary motion for companies needing near-term revenue.

**Partner / referral-led**
Best fit when buyers trust peer recommendations over brand claims and first successful customers exist.
Constraint: viable after the first wave of successful customers.

**Community-led**
Best fit when the product creates network value, buyers learn from each other, and the category is being defined.
Constraint: high effort and long timeline; rarely right before core offer validation.

### Motion selection rule

Select the single motion that best matches buyer-map signals, company stage, and proof level. If two motions are viable, select the one requiring less proof to activate. Mixed motions are labeled as primary motion plus secondary motion that activates only after a defined proof threshold.

ACV directional filter:

```text
< $1,000 ACV          → product-led or content-led primary
$1,000–$10,000 ACV    → founder-led or hybrid product + sales
$10,000–$50,000 ACV   → sales-led, founder-led, or content-led
> $50,000 ACV         → sales-led primary, content as trust layer
```

Override with buyer-map signals when they contradict the ACV filter.

---

## Launch Sequence

The launch sequence is a dependency chain. Each step has what gets done, what it unlocks, and the completion signal that clears advancement. Do not generate a calendar. Generate a sequence.

### Stage 0 — Foundation

What gets done:

- Conversion asset exists: landing page, booking page, or proposal template
- Core message is approved and reflected in the conversion asset
- Proof arc is embedded in the conversion asset
- Primary CTA matches awareness level and buyer type
- Tracking is in place on the conversion action

Unlocks: Stage 1. Nothing moves before foundation is complete.

Completion signal: conversion asset is live, CTA functional, and at least one ICP-match person confirms the proof arc sounds like their situation.

### Stage 1 — Proof and first conversations

Generate first qualified conversations through the lowest-friction channel available at this proof level.

- Founder-led: high-context warm/direct outreach, not mass email.
- Product-led: free trial, freemium tier, or diagnostic tool that delivers value before commitment.
- Sales-led: tightly scoped ICP outbound led by founder/seller with category credibility.
- Content-led: publish the proof arc as one high-value piece that the ICP recognizes.

Unlocks: real buyer language, objection data, first proof assets.

Completion signal: minimum three qualified conversations; one buyer describes problem in their own words; one objection documented.

### Stage 2 — Conversion path validation

Test whether the full path works from first touch to closed deal. Do not add channels or increase volume before this stage.

Validate: first message response, conversation to next step, next step to proposal/commitment, proposal to close, closed deal delivers promised outcome.

Completion signal: one full conversion cycle completed end-to-end; conversion rate at each step known; at least one proof asset exists.

### Stage 3 — Proof-building and message refinement

Update buyer map, message architecture, and conversion path from Stages 1–2. Collect proof assets in this order:

1. One specific outcome in buyer words
2. One before/after mapped to proof arc
3. One objection overcome and documented as proof point
4. One referral from a successful first customer

Completion signal: one proof asset per primary trust gap.

### Stage 4 — Channel expansion

Activate hold channels only after proof and conversion path validation exist. Each new channel has a 30-day leading-indicator target defined before activation and is paused if not met.

### Stage 5 — Scale

Increase investment only where leading indicators and conversion data confirm the path is working.

---

## Channel Stack Logic

The stack is a ranked decision set: do now, hold until condition, or avoid.

### Do-now criteria

A channel belongs in do-now if all three are true:

1. Buyer at this awareness level is reachable there
2. Company has proof required to be credible there
3. Conversion path exists to receive traffic

### Hold criteria

A channel belongs in hold if it fits the buyer but proof, conversion path, budget, or message validation is not ready. Always specify the unlock condition precisely.

### Avoid criteria

Avoid if the buyer is not reachable there at this awareness level, ACV does not justify CAC, channel requires proof/maturity the company lacks, or it attracts the wrong buyer.

### Channel-to-buyer-map mapping

| buyer_map field | Channel implication |
|---|---|
| `awareness_level: unaware` | Interruption channels can work; search does not because buyers are not searching yet |
| `awareness_level: problem_aware` | Problem-naming content, symptom SEO, communities |
| `awareness_level: solution_aware` | Comparison content, category SEO, LinkedIn outreach, direct email |
| `awareness_level: product_aware` | Retargeting, direct outreach, case studies, review platforms |
| `buyer_type: earlyvangelist` | Founder outreach, niche communities, early access |
| `buyer_type: early_majority` | Peer references, owned case studies, authority content |
| `adoption_stage: early_majority` | Channels that show peer proof; avoid imagination-heavy channels |
| `switching_forces.anxiety_level: high` | Low-commitment entry: diagnostic, audit, pilot; avoid direct purchase CTAs |
| Multi-stakeholder roles | LinkedIn for champion reach; content for economic buyer; direct founder-to-founder |
| `ACV > $10k` | Human-touch first; self-serve only after path is proven |

---

## Conversion Path Design

The conversion path is the sequence from first buyer contact to closed deal and delivered outcome. Each step has touchpoint, message job, action required, and advance signal.

### Founder-led / sales-led path

```text
Step 1  First message / referral introduction
        Job: name the buyer's situation precisely enough to earn a reply
        Action: buyer replies or books a call
        Signal: response rate above pre-set threshold

Step 2  Discovery or diagnostic call
        Job: confirm problem, establish credibility, identify champion
        Action: buyer agrees to proposal, follow-up, or stakeholder intro
        Signal: buyer says "yes, that's the problem" and identifies stakeholders

Step 3  Proposal or solution presentation
        Job: make outcome concrete, address dominant blocker, reduce effort/risk
        Action: buyer requests commercial terms or asks approval question
        Signal: buyer asks timeline, implementation, or contract questions

Step 4  Commercial close
        Job: remove transaction friction
        Action: contract signed or payment made
        Signal: deal closed

Step 5  Outcome delivery and proof collection
        Job: deliver promised outcome and collect proof assets
        Action: case study, quote, or referral
        Signal: buyer describes outcome in their own words
```

### Product-led path

```text
Step 1  Acquisition → signup/trial activation
Step 2  Activation → first moment of value
Step 3  Habit formation → returns without prompting
Step 4  Conversion to paid → upgrade
Step 5  Expansion and proof → referral, case study, NRR
```

### Conversion path rule

- Anxiety: include low-commitment entry before purchase ask.
- Habit: include side-by-side demonstration alongside existing way.
- Weak push: include honest cost-of-inaction step.
- Weak pull: include specific outcome demonstration before purchase ask.

---

## Proof-Building Plan

Proof unlocks every stage beyond Stage 1. Map proof to trust gaps in `buyer_map.trust_signals`.

Proof priority matrix:

```text
Unknown company             → Founder narrative + process transparency
No social proof             → First customer case narrative, even anonymized
No peer reference           → Named comparable client with permission
Category trust deficit      → Mechanism explanation + before/after
Implementation anxiety      → Explicit rollout map, week-by-week
"Just a deck" concern       → Sample deliverable or pilot offer
High ACV uncertainty        → ROI framing + risk reversal offer
```

Proof collection sequence:

1. Process transparency — generate now
2. Founder credibility narrative — generate now from brand brief
3. First customer quote — requires closed deal
4. Anonymous case narrative — requires completed engagement
5. Named case study — requires permission
6. Peer reference program — requires multiple successful customers

---

## Measurement Frame

Track leading indicators by stage before revenue confirms the strategy.

### Leading indicators by stage

- Stage 0: conversion asset live yes/no; message reviewed by ICP-match yes/no; tracking functional yes/no
- Stage 1: outreach response rate structure; qualified conversations per week; buyer language captured yes/no
- Stage 2: message-to-call, call-to-proposal, proposal-to-close, objections per call
- Stage 3: proof assets collected vs trust gaps; message fields upgraded; buyer calibration answered
- Stage 4: cost per qualified conversation; 30-day leading indicator met; resonance signal
- Stage 5: CAC by channel; payback period; NRR/expansion signal

### Measurement rules

1. Define leading indicator target before activating a channel or stage.
2. Pause and diagnose a channel that misses its leading indicator within 30 days.
3. Revenue is lagging; use path conversion signals in Stages 1–3.
4. Do not generate numeric targets without baseline data.

---

## Stage Gate Logic

```text
Stage 0 gate  →  Conversion asset live and tracked
Stage 1 gate  →  3+ qualified conversations completed, buyer language captured
Stage 2 gate  →  1 full conversion cycle completed end-to-end
Stage 3 gate  →  1 proof asset per primary trust gap
Stage 4 gate  →  Leading indicator met for each activated channel within 30 days
Stage 5 gate  →  CAC by channel known and payback period acceptable
```

If a gate is not met, diagnose before pivot:

- Message failed → return to message architecture
- Offer failed → return to value equation and dominant blocking force
- Proof failed → accelerate proof collection or lower commitment threshold
- ICP failed → return to buyer map
- Channel failed → swap within do-now stack before changing motion

---

## Output Schema

```json
{
  "gtm_plan": {
    "version": "1.0",
    "confidence": "inferred | partial | validated",
    "inferred_buyer_map": true,
    "inferred_message_architecture": true,
    "generated_from": ["buyer_map", "message_architecture", "company_description"],
    "selected_motion": {
      "primary_motion": "",
      "secondary_motion": "",
      "secondary_motion_unlock_condition": "",
      "motion_rationale": "",
      "confidence": "inferred | partial | validated"
    },
    "launch_sequence": [
      {
        "stage": 0,
        "label": "",
        "what_gets_done": [],
        "what_it_unlocks": "",
        "completion_signal": "",
        "estimated_duration": "",
        "dependencies": []
      }
    ],
    "channel_stack": {
      "do_now": [
        {
          "channel": "",
          "role": "",
          "rationale": "",
          "buyer_map_signal": "",
          "proof_required": "",
          "confidence": "inferred | partial | validated"
        }
      ],
      "hold": [
        {"channel": "", "hold_reason": "", "unlock_condition": "", "confidence": "inferred | partial | validated"}
      ],
      "avoid": [
        {"channel": "", "avoid_reason": "", "confidence": "inferred | partial | validated"}
      ]
    },
    "conversion_path": [
      {"step": 1, "touchpoint": "", "message_job": "", "action_required": "", "advance_signal": "", "blocking_force_addressed": ""}
    ],
    "proof_building_plan": [
      {"trust_gap": "", "proof_format": "", "available_now": true, "unlock_stage": "", "channel_or_artifact": ""}
    ],
    "measurement_frame": {
      "stage_leading_indicators": [
        {"stage": 0, "indicators": [], "numeric_targets": "requires_baseline | [value]", "review_cadence": ""}
      ],
      "stage_gates": [
        {"stage": 0, "gate_condition": "", "if_gate_not_met": ""}
      ]
    },
    "critical_assumptions": [
      {"assumption": "", "if_wrong": "", "calibration_question": ""}
    ],
    "priority_calibration": [
      {"question": "", "field_it_validates": "", "why_priority": ""}
    ],
    "approval_note": "This is a strategy artifact pending review. Execution artifacts, publishing, outreach, spend, and external platform actions require separate approval."
  }
}
```

---

## Downstream Handoff

| Execution artifact | Fields consumed |
|---|---|
| Landing page copy | `selected_motion`, `conversion_path[step 1]`, `channel_stack.do_now` |
| Founder outreach sequence | `selected_motion`, `conversion_path[steps 1–2]`, `launch_sequence[stage 1]` |
| Content calendar | `channel_stack.do_now`, `launch_sequence[stage 3]`, `buyer_map.awareness_level` |
| Paid media brief | `channel_stack.hold or do_now`, `launch_sequence[stage 4]`, `proof_building_plan` |
| Sales one-pager | `conversion_path[steps 2–3]`, `proof_building_plan`, `message_architecture.role_messages` |
| Objection handling sheet | `conversion_path`, `message_architecture.objection_responses`, `measurement_frame` |
| Onboarding / activation plan | `conversion_path[steps 4–5]`, `proof_building_plan`, `measurement_frame` |
| Reporting dashboard | `measurement_frame.stage_leading_indicators`, `measurement_frame.stage_gates` |

---

## Chat behavior

Visible CMO replies stay short and mobile-first. Do not paste the full GTM plan into chat. Workspace/Stream owns the plan artifact and review controls.

Correct visible reply:

```text
I’ll build the GTM plan from the buyer map and message architecture.

It’ll stay strategy-only: no publishing, spend, or outreach without approval.
```

---

## Forbidden Behaviors

1. Do not generate the GTM plan without buyer map and message architecture. If they are inferred, propagate the inferred flags.
2. Do not recommend channel soup. Maximum three do-now channels.
3. Do not skip stage gates or elaborate later stages as ready before gates are met.
4. Do not set numeric targets without baselines.
5. Do not execute outreach, publishing, spend, platform setup, or external actions as part of plan generation.
6. Do not recommend scale before conversion path validation and proof assets exist.
7. Do not average mismatched earlyvangelist and early-majority profiles into one motion.
