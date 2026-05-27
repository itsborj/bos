---
id: marketing.messaging.architecture
name: messaging
version: 1.0.0
description: >
  Generate a structured message architecture from the buyer intelligence map and
  brand brief. Translate what the buyer believes, fears, and wants into the exact
  words that meet them at their current awareness level, address their dominant
  switching force, and move them toward the conversion action. Feed all downstream
  copy artifacts from this message architecture. Do not write landing page copy,
  outreach sequences, ad copy, or sales collateral without a message architecture.
scope: strategy
status: active
allowed_from_chat: false
module_id: marketing.messaging.architecture
requires_intent: []
triggers: []
excluded_triggers: []
depends_on:
  - reasoning.buyer_intelligence
  - brand_brief
required_upstream:
  - buyer_map.v1
input_minimum: buyer_map (any confidence level) + company_description + product_service_desc
outputs:
  - message_architecture.v1
memory_slots:
  - brand_profile
  - product_catalog
  - audience_profiles
  - campaign_brand_kit
  - brand_guidelines
load_policy: explicit_dependency_only
quality_gates:
  - buyer_map_required
  - awareness_level_matched
  - no_fabricated_proof
  - message_hierarchy_preserved
  - message_dont_list_present
metadata:
  author: bos-core
  artifact_type: intelligence_artifact
  output_contract: message_architecture
  risk_policy: no_external_action
  stage: strategic_substrate
---

# Messaging Skill

## Purpose

Messaging is the translation layer between two things that don't naturally speak the same language: what the company knows about its product, and what the buyer needs to hear before they trust it.

The brand brief contains company language — features, mechanisms, categories, and claims the company believes are true. The buyer map contains buyer language — the problem as they experience it, the alternatives they've already tried, the fear that makes them hesitate, the outcome they actually want.

Messaging is not the company's description of the product. It is the company's description of the buyer's situation — with the product as the resolution.

This skill generates a complete message architecture: a hierarchy of messages, from the single core statement down to specific objection responses, calibrated to the buyer's awareness level and dominant switching force. Every downstream copy artifact reads from this architecture. Nothing is written from scratch.

---

## Input Contract

### Required inputs

```text
buyer_map               — Output of reasoning.buyer_intelligence (any confidence level).
                          If buyer_map is fully inferred, messaging carries the same
                          inferred flag. If buyer_map has been calibrated, messaging
                          inherits the validated fields.
company_description     — From brand brief. What the company does, how it operates,
                          who it serves.
product_service_desc    — From brand brief. What is being sold, what problem it solves,
                          how it works, what it replaces.
```

### Optional enrichment inputs

```text
brand_voice             — Tone, personality, and communication style guidelines.
existing_taglines       — Current messaging the client uses, for reference or contrast.
proof_assets            — Case studies, testimonials, data, named clients.
category_language       — Terms, comparisons, or vocabulary common in this industry.
```

### Industry inference layer

When brand brief context is thin or proof assets are absent, activate the industry inference layer. Using LLM knowledge of the product category, infer:

- The typical trust deficit the buyer carries into this category
- The language patterns buyers in this category commonly use to describe their problem
- The message formats that perform best in this category
- The objection types most common in this category
- The proof formats most credible in this category

All industry-inferred elements are flagged `source: industry_inference`. Client-provided proof and calibration answers override industry inference wherever they conflict.

---

## Messaging Architecture

Messages are built in a hierarchy. Higher levels must be true and approved before lower levels are written. Lower levels are expressions of higher levels — never contradictions.

```text
Level 1 — Core message         One sentence. The irreducible truth.
Level 2 — Positioning frame    Who, what, for whom, against what, why now.
Level 3 — Proof arc            Before → trigger → failed path → shift → after.
Level 4 — Role messages        Calibrated versions for each decision-maker role.
Level 5 — Objection responses  Direct answers to the dominant switching forces.
Level 6 — Proof points         Specific evidence mapped to specific trust gaps.
Level 7 — CTAs                 Next-step language calibrated to awareness level.
```

Each level is an output field in the message architecture schema. Downstream artifacts pick the fields they need. Nothing is rewritten for each artifact — it is assembled from this architecture.

---

## Level 1 — Core Message

Definition: one sentence. If the buyer heard nothing else from this company, this is the sentence that would make them want to know more.

Structure:

```text
[The buyer's problem named precisely] + [the shift the product makes possible]
```

Not a tagline. Not a slogan. A statement of what is true about the buyer's situation and what changes when they use this product.

Generation rule: read `buyer_map.real_outcome.deepest_motivation` and `buyer_map.jobs.dominant_job`. The core message names the dominant job in buyer language and gestures at the outcome without describing the mechanism.

Awareness override:

- Unaware/problem aware: name only the problem; no solution reference.
- Solution/product aware: name the problem and category of shift.
- Most aware: name the specific product and outcome.

Industry fallback: if buyer jobs are fully inferred, generate from category knowledge, flag `source: industry_inference`, and ask: "What did your best customer say changed for them after working with you?"

---

## Level 2 — Positioning Frame

Definition: the four-part structure that tells the buyer who this is for, what it does, what it replaces, and why it matters now.

Structure:

```text
For [specific buyer in specific situation]
who [has this specific problem or desire]
[product name] is [category or approach]
that [delivers this specific outcome]
unlike [the primary alternative]
which [fails in this specific way].
```

This is internal positioning, not customer-facing copy.

Generation rule: read `customer_roles.who_controls_yes`, `jobs.functional_job`, `jobs.emotional_job`, `real_outcome.upstream_outcome`, `comparison_set.primary_alternative`, and `comparison_set.what_better_means_vs_each`.

Competitive frame rule: write against the comparison set the buyer actually uses, not the competitor the client wants to beat.

---

## Level 3 — Proof Arc

Definition: the narrative structure that maps the buyer's experience onto a before/after story.

Structure:

```text
Before state    — The specific situation the buyer is in right now.
Trigger         — The moment that makes the current situation intolerable.
Failed path     — What the buyer has already tried that didn't work.
The shift       — What becomes possible with this product that wasn't possible before.
After state     — What the buyer's life or business looks like once the shift is made.
```

Generation rule: read `switching_forces.push_source`, `comparison_set.primary_alternative`, `real_outcome.upstream_outcome`, and `real_outcome.deepest_motivation`.

Narrative rule: the buyer is the main character. The company is the guide. The product is the mechanism. Any message that positions the company as the main character loses buyer identification.

Industry fallback: if comparison set is inferred, use category knowledge of failed paths and flag `source: industry_inference`.

---

## Level 4 — Role Messages

For each role in `buyer_map.customer_roles`:

- User message: lead with friction removed and day made easier.
- Champion message: lead with internal credibility and safe recommendation.
- Economic buyer message: lead with return relative to cost and downside protection.
- Veto player message: lead with risk reduction and compliance with their concerns.

If the buyer map shows a single B2C/SMB decision-maker, skip role splitting and write one message for the person who has the problem, approves the spend, and uses the product.

---

## Level 5 — Objection Responses

Generate direct, pre-emptive answers to forces keeping the buyer from switching. Use `buyer_map.switching_forces.dominant_blocking_force`.

### Anxiety responses

Format:

```text
Acknowledge the concern directly.
Provide the specific mechanism that removes the risk.
Offer a commitment that reduces the cost of being wrong.
```

Examples: similar-situation proof, week-one implementation clarity, mechanism differentiation, or reciprocity offer.

### Habit responses

Format:

```text
Validate the existing approach — don't attack it.
Name the specific cost it's creating that the buyer may not have quantified.
Show the path from current state to new state without requiring a full break.
```

### Weak push responses

Do not manufacture urgency. Quantify honest cost of inaction: compounding cost, what becomes harder six months from now, and opportunity lost while the current approach continues.

Industry fallback: if switching forces are inferred, use category knowledge and flag `source: industry_inference`.

---

## Level 6 — Proof Points

Proof points are specific evidence mapped to specific trust gaps in `buyer_map.trust_signals`, not a general claim list.

Proof hierarchy:

1. Specific named outcome for a named client in a named situation
2. Specific unnamed outcome for a described client type in a described situation
3. Process transparency — show exactly what happens and why it works
4. Credentials, methodology, or framework that signals expertise
5. Social proof volume — number of customers, reviews, cohorts
6. Founder or team credibility signal
7. Category authority signal — press, recognition, partnerships

Generation rule: read `trust_signals.trust_gap_summary` and `adoption_stage.proof_format_required`. If proof assets do not exist, generate proof templates to collect; do not fabricate proof.

Proof gap template:

```text
To close [trust gap], you need: [specific proof format]. Example structure:
[Client type] used [product] to [specific action] and got [specific outcome]
in [specific timeframe].
```

Proof format by adoption stage:

- Innovators/early adopters: mechanism transparency and founder credibility
- Early majority: peer reference in exact context, specific measurable outcome
- Late majority: category dominance signals, risk reversal, guarantees

---

## Level 7 — CTAs

CTA language moves the buyer from awareness to action, calibrated to awareness level. Avoid generic CTAs.

| Awareness level | CTA intent | CTA language pattern |
|---|---|---|
| Unaware | Introduce the problem | "See why [problem] costs more than most [role] realize" |
| Problem aware | Validate and open | "Find out if [your situation] is fixable without [failed alternative]" |
| Solution aware | Differentiate entry | "See how [this approach] is different from [category default]" |
| Product aware | Remove last barrier | "Talk to someone before you decide" / "See it in your context" |
| Most aware | Reduce friction | "Start today" / "Get set up in [specific timeframe]" |

CTA by buyer type:

- Earlyvangelist: action-forward, first-mover framing.
- Early majority: safety-forward, social proof framing.

CTA by dominant switching force:

- High anxiety: commitment-reducing CTA.
- Strong habit: low-disruption CTA.
- Weak push: honest urgency-building CTA.

---

## Awareness-Level Calibration Rules

1. Never open above the buyer's awareness level.
2. Awareness levels are surface-specific: cold social may be L1–L2; search landing page may be L3–L4; warm intro may be L4–L5.
3. Advance one level per surface. One ad, email, or landing section moves the buyer one awareness level at a time.

---

## Generation Protocol

1. Load buyer_map, company_description, and product_service_desc.
2. Set messaging confidence to match the lowest-confidence consumed field.
3. Read awareness level and make it the entry point for all messages.
4. Identify dominant job and deepest motivation.
5. Identify dominant blocking force and choose desire-led, reassurance-led, or proof-led strategy.
6. Generate levels 1 through 7 in sequence. Do not skip levels.
7. Apply industry inference where brand brief is thin; flag it.
8. Output the structured message architecture and top three priority calibration questions.
9. Do not generate downstream copy artifacts in the same operation.

---

## Output Schema

```json
{
  "message_architecture": {
    "version": "1.0",
    "confidence": "inferred | partial | validated",
    "awareness_level_target": "unaware | problem_aware | solution_aware | product_aware | most_aware",
    "dominant_job": "",
    "dominant_blocking_force": "anxiety | habit | weak_push | weak_pull",
    "lead_message_strategy": "desire_led | reassurance_led | proof_led",
    "core_message": {
      "statement": "",
      "buyer_language_used": true,
      "awareness_level_match": "",
      "confidence": "inferred | partial | validated",
      "source": "client_signal | industry_inference | buyer_map"
    },
    "positioning_frame": {
      "for_whom": "",
      "problem": "",
      "product_category": "",
      "outcome": "",
      "primary_alternative": "",
      "alternative_failure": "",
      "confidence": "inferred | partial | validated"
    },
    "proof_arc": {
      "before_state": "",
      "trigger": "",
      "failed_path": "",
      "the_shift": "",
      "after_state": "",
      "confidence": "inferred | partial | validated",
      "source": "client_signal | industry_inference | buyer_map"
    },
    "role_messages": [
      {
        "role": "user | champion | economic_buyer | veto_player",
        "value_definition": "",
        "message": "",
        "language_register": "",
        "confidence": "inferred | partial | validated"
      }
    ],
    "objection_responses": [
      {
        "force_type": "anxiety | habit | weak_push",
        "objection": "",
        "response": "",
        "proof_required": "",
        "confidence": "inferred | partial | validated",
        "source": "client_signal | industry_inference"
      }
    ],
    "proof_points": [
      {
        "trust_gap_addressed": "",
        "proof_type": "named_outcome | process_transparency | credential | social_proof | template",
        "proof_content": "",
        "proof_format_if_template": "",
        "confidence": "available | needs_collection"
      }
    ],
    "ctas": {
      "awareness_matched_cta": "",
      "buyer_type_matched_cta": "",
      "force_matched_cta": "",
      "primary_cta": "",
      "secondary_cta": ""
    },
    "message_dont_list": [],
    "critical_assumptions": [
      {"assumption": "", "if_wrong": "", "calibration_question": ""}
    ],
    "priority_calibration": [
      {"question": "", "field_it_validates": "", "why_priority": ""}
    ]
  }
}
```

---

## The Message Don't List

Always generate a `message_dont_list` specific to this buyer map:

- Claims the buyer will not believe at their current awareness level
- Language that positions the company as the hero
- Metrics or results unsupported by proof assets
- Competitive claims against alternatives not in the real comparison set
- Manufactured urgency
- Jargon buyers at this awareness level do not yet use
- Category-level claims buyers have already heard and discount

---

## Downstream Handoff

| Downstream artifact | Fields consumed |
|---|---|
| Landing page hero | core_message, proof_arc.before_state, proof_arc.after_state, ctas.primary_cta |
| Landing page body | proof_arc, objection_responses, proof_points, role_messages |
| Founder outreach subject line | core_message, awareness_matched_cta |
| Founder outreach body | proof_arc.before_state, proof_arc.trigger, proof_arc.failed_path, ctas.force_matched_cta |
| Social content angles | proof_arc, core_message, message_dont_list |
| Sales one-pager | positioning_frame, role_messages, proof_points, objection_responses |
| Objection handling sheet | objection_responses, proof_points |
| Ad copy when proof exists | core_message, ctas, proof_points |
| Email nurture sequence | proof_arc, objection_responses, ctas by awareness level |

No copy artifact is written from scratch. Every artifact is assembled from message architecture fields for its surface and buyer moment.

---

## Forbidden Behaviors

1. Do not write at the wrong awareness level.
2. Do not position the company as the hero.
3. Do not fabricate proof.
4. Do not write generic objection handling disconnected from the dominant switching force.
5. Do not write all levels simultaneously without hierarchy.
6. Do not skip the message don't list.
7. Do not treat industry inference as client-validated signal.
