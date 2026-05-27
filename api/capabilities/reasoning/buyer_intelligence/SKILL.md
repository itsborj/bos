---
id: reasoning.buyer_intelligence
name: buyer-intelligence
version: 1.0.0
description: >
  Generate a structured buyer intelligence map from minimal client input — a company
  description and product/service description. Apply the 10-seat council of business
  and marketing thinkers to infer how the buyer thinks, decides, and switches.
  Produce a calibrated buyer map with explicit assumption flags and calibration
  questions. Feed all downstream GTM artifacts from this map. Do not proceed to
  messaging, positioning, channel selection, or launch planning without a buyer map.
scope: reasoning
status: active
allowed_from_chat: false
module_id: reasoning.buyer_intelligence
requires_intent: []
triggers: []
excluded_triggers: []
memory_slots:
  - brand_profile
  - product_catalog
  - audience_profiles
  - campaign_brand_kit
  - brand_guidelines
load_policy: explicit_inheritance_only
input_minimum: company_description + product_service_desc
outputs:
  - buyer_map.v1
quality_gates:
  - all_ten_lenses_applied
  - inferred_fields_flagged
  - calibration_questions_present
  - no_downstream_strategy_without_buyer_map
  - no_numeric_claims_without_client_data
metadata:
  author: bos-core
  artifact_type: intelligence_artifact
  output_contract: buyer_map
  risk_policy: no_external_action
  stage: strategic_substrate
---

# Buyer Intelligence Skill

## Purpose

This skill exists because downstream GTM artifacts — messaging, positioning, channel stack, conversion path, launch sequence — are only as accurate as the buyer model they're built on. Without this skill, the agent generates plausible strategy. With it, the agent generates accurate strategy.

The LLM has consumed buyer language, reviews, objections, forum complaints, sales conversations, and purchasing patterns across virtually every category that exists. That intelligence is latent and unanchored. This skill anchors it to a specific client, product, and market by applying ten structured inference lenses, then flags every output as either inferred from training data or validated by client signal.

The client does not need to know what buyer intelligence is. They answer plain questions. The intelligence is generated. The map is produced.

---

## Input Contract

### Required inputs

```text
company_description     — What the company does, who it serves, how it operates.
product_service_desc    — What is being sold, what problem it solves, how it works.
```

### Optional enrichment inputs

```text
customer_signals        — Real quotes, objections, referral language from actual buyers.
sales_observations      — What comes up on calls, what kills deals, what closes them.
competitive_context     — Who buyers consider instead, what they choose when they don't buy.
best_customer_profile   — Description of the buyer who got the most value and stayed longest.
lost_deal_behavior      — What the buyer did or said when they walked away.
```

### Minimum viable operation

The skill runs on required inputs alone. Optional inputs increase fidelity. When optional inputs are absent, the agent infers from category knowledge and flags every inference explicitly. Missing optional inputs become calibration questions surfaced after the first-draft map.

---

## The Council — Ten Inference Lenses

Apply all ten sequentially. Each lens populates a specific field in the buyer map output schema.

### Lens 1 — Theodore Levitt | The Outcome Layer

Question: What is the buyer actually purchasing — and how far upstream from the product does the real desired outcome live?

Inference rule: identify the functional output, then ask what that output makes possible, then what that makes possible. The answer two levels upstream is usually the real purchase motivation.

Signals: verbs describing what the product does; pain language; time or money language. Thin input: infer from category knowledge and flag as inferred.

Populates: `buyer_map.real_outcome`

Calibration: "What does life or business look like for your best customer six months after working with you — that they couldn't have articulated before they bought?"

### Lens 2 — Peter Drucker | The Real Customer

Question: In a complex sale, who is the real customer — the user, buyer, or economic decision-maker — and what does each define as value?

Inference rule: determine B2C, B2B SMB, B2B mid-market, or B2B enterprise. Users value daily ease. Budget holders value return. Approvers value reduced personal risk. Enterprise adds procurement, legal, IT, and security as veto players.

Signals: served audience, pricing, stakeholder language.

Populates: `buyer_map.customer_roles`

Calibration: "In a typical sale, who first feels the problem, who champions the solution internally, and who has final approval to spend?"

### Lens 3 — Clayton Christensen | The Job

Question: What functional, emotional, and social job is the buyer hiring this solution to do — and which job drives the purchase?

Inference rule: infer functional, emotional, and social jobs from product, problem, and buyer role. The functional job is usually explicit; emotional/social jobs are usually inferred from category patterns. The decision is often driven by emotional or social job even when the buyer describes the functional job.

Populates: `buyer_map.jobs`

Calibration: "When your best customer talks about working with you, what do they say it did for them personally — not just for the business?"

### Lens 4 — Steve Blank | Problem Space vs. Solution Space

Question: Is the buyer in problem space or solution space — and are they an earlyvangelist or mainstream buyer?

Inference rule: problem-space buyers describe symptoms; solution-space buyers compare options. Earlyvangelists have the problem, know it, can act, have tried to solve it, and believe it is solvable. Mainstream buyers need peer references, proof, reduced risk, and ROI clarity.

Populates: `buyer_map.awareness_stage`, `buyer_map.buyer_type`

Calibration: "Who are the first three types of people who would pay for this before it's perfect?" and "What does a buyer have to already believe is true before your solution makes sense to them?"

### Lens 5 — Eugene Schwartz | Awareness Level

Question: What level of awareness does the buyer currently hold — and does the current message meet them there?

Levels: unaware, problem aware, solution aware, product aware, most aware. Write for the awareness level the buyer is at, not where the client assumes they are.

Populates: `buyer_map.awareness_level`

Calibration: "Does your buyer know they have this problem before they find you, or do they realize it during your conversation with them?"

### Lens 6 — Geoffrey Moore | Adoption Stage and Proof Requirements

Question: Where in the adoption curve does this buyer sit — and what whole product must exist before they feel safe?

Inference rule: classify innovator, early adopter, early majority, late majority, or laggard. Early majority requires peer references in exact context, complete solution, implementation path, and support confidence.

Populates: `buyer_map.adoption_stage`

Calibration: "Does your buyer need to see others exactly like them using this before they'll commit — or are they willing to be one of the first?"

### Lens 7 — April Dunford | Competitive Frame and Comparison Set

Question: What is the buyer's real comparison set — and what does "better" mean relative to each alternative?

Alternatives include current process, direct competitors, adjacent solutions, and doing nothing. Never position against competitors the buyer is not considering.

Populates: `buyer_map.comparison_set`

Calibration: "When a buyer doesn't choose you, what do they do instead?" and "What were your last three lost deals going to do after they said no?"

### Lens 8 — Alex Hormozi | Value Equation Diagnosis

Question: Which value-equation variable suppresses conversion?

Value = (Dream Outcome × Perceived Likelihood of Achievement) ÷ (Time Delay × Effort and Sacrifice)

Diagnose weakest variable: dream outcome, perceived likelihood, time delay, or effort/sacrifice. Recommend the primary lever to address first.

Populates: `buyer_map.value_equation`

Calibration: "What makes buyers doubt they'll actually get the result you're promising — even when they want to believe it?"

### Lens 9 — Robert Cialdini | Trust and Proof Signals

Question: What trust, authority, and social proof signals does the buyer need before yes — and which are missing?

Audit reciprocity, commitment/consistency, social proof, authority, liking, and scarcity. High-ticket and trust-deficit categories require higher proof thresholds.

Populates: `buyer_map.trust_signals`

Calibration: "What concern comes up late in a sales conversation that's hard to address — the one that makes things go quiet?"

### Lens 10 — Bob Moesta | The Four Forces of Switching

Question: Why does a buyer who wants to switch still not switch?

Forces: PUSH, PULL, ANXIETY, HABIT. Conversion fails when push + pull are weaker than anxiety + habit. Diagnose each force and dominant blocker.

Populates: `buyer_map.switching_forces`

Calibration: "What finally made your best customer stop tolerating the old way and decide to act?" and "What almost stopped your best customer from buying, even after they'd decided they wanted to?"

---

## Generation Protocol

1. Parse inputs: category, audience, problem, mechanism, stage signals, proof signals.
2. Apply all ten council lenses sequentially.
3. For each lens, assign confidence: `inferred`, `partial`, or `validated`.
4. Synthesize one unified buyer map, not ten separate outputs.
5. Flag all assumptions and gaps.
6. Surface top three critical assumptions and top three priority calibration questions.
7. Do not produce messaging, positioning, channel stack, or launch plan until buyer map exists and has been reviewed or explicitly accepted as inferred.

---

## Output Schema

```json
{
  "buyer_map": {
    "version": "1.0",
    "confidence": "inferred | partial | validated",
    "generated_from": ["company_description", "product_service_desc"],
    "real_outcome": {
      "functional_outcome": "",
      "upstream_outcome": "",
      "deepest_motivation": "",
      "confidence": "inferred | partial | validated"
    },
    "customer_roles": {
      "user": "",
      "champion": "",
      "economic_buyer": "",
      "veto_players": [],
      "who_controls_yes": "",
      "confidence": "inferred | partial | validated"
    },
    "jobs": {
      "functional_job": "",
      "emotional_job": "",
      "social_job": "",
      "dominant_job": "",
      "confidence": "inferred | partial | validated"
    },
    "awareness_stage": {
      "level": "unaware | problem_aware | solution_aware | product_aware | most_aware",
      "evidence": "",
      "message_entry_point": "",
      "confidence": "inferred | partial | validated"
    },
    "buyer_type": {
      "type": "earlyvangelist | early_adopter | early_majority | late_majority",
      "earlyvangelist_signals": [],
      "proof_required_before_purchase": "",
      "confidence": "inferred | partial | validated"
    },
    "adoption_stage": {
      "stage": "innovator | early_adopter | early_majority | late_majority | laggard",
      "whole_product_gaps": [],
      "proof_format_required": "",
      "confidence": "inferred | partial | validated"
    },
    "comparison_set": {
      "primary_alternative": "",
      "secondary_alternatives": [],
      "doing_nothing_cost": "",
      "what_better_means_vs_each": {},
      "confidence": "inferred | partial | validated"
    },
    "value_equation": {
      "dream_outcome_strength": "weak | moderate | strong",
      "perceived_likelihood_strength": "weak | moderate | strong",
      "time_delay_friction": "low | moderate | high",
      "effort_sacrifice_friction": "low | moderate | high",
      "weakest_variable": "",
      "primary_lever": "",
      "confidence": "inferred | partial | validated"
    },
    "trust_signals": {
      "reciprocity_present": false,
      "social_proof_present": false,
      "authority_signals": [],
      "trust_gap_summary": "",
      "highest_trust_barrier": "",
      "confidence": "inferred | partial | validated"
    },
    "switching_forces": {
      "push_strength": "weak | moderate | strong",
      "push_source": "",
      "pull_strength": "weak | moderate | strong",
      "pull_source": "",
      "anxiety_level": "low | moderate | high",
      "anxiety_source": "",
      "habit_strength": "weak | moderate | strong",
      "habit_source": "",
      "dominant_blocking_force": "anxiety | habit | weak_push | weak_pull",
      "confidence": "inferred | partial | validated"
    },
    "buyer_language": {
      "problem_in_buyers_words": "",
      "outcome_in_buyers_words": "",
      "objections_in_buyers_words": [],
      "confidence": "inferred | partial | validated"
    },
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

## Calibration Question Bank

Surface only the top three priority calibration questions first.

- What usually just happened in someone's business right before they first reached out to you?
- What does someone typically try to solve on their own before they decide to look for help?
- What do most buyers try before they come to you — and what goes wrong with that approach?
- When a deal doesn't close, what does the buyer say they're going to do instead?
- What question do buyers ask most before they decide to buy?
- What concern comes up late in a conversation that's hard to address — the one that makes things go quiet?
- What would make a buyer choose someone else over you, even if your product is objectively better?
- What did your best customer say when they referred someone to you? What exact words did they use?
- What did your best customers get from you that they didn't expect when they signed up?
- What does life or business look like for your best customer six months after working with you?
- How do buyers describe what's wrong before they've heard how you describe it? What words do they actually use?
- What do you find yourself explaining most often that you wish the buyer already understood?
- Does your buyer need to see others exactly like them using this before they'll commit?
- Who are the first three types of people who would pay for this before it's perfect?
- What finally made your best customer stop tolerating the old way and decide to act?
- What almost stopped your best customer from buying, even after they'd decided they wanted to?
- What does your industry get blamed for that you think is unfair or outdated?
- What does a new buyer usually assume about working with you that turns out not to be true once they're in?

---

## Downstream Handoff

| Downstream artifact | Fields consumed |
|---|---|
| Core messaging | real_outcome, jobs, awareness_level, buyer_language |
| Positioning statement | comparison_set, jobs, real_outcome |
| Landing page copy | awareness_level, switching_forces, trust_signals, value_equation |
| Founder outreach sequence | buyer_type, jobs, switching_forces, buyer_language |
| Objection handling sheet | switching_forces, trust_signals, comparison_set |
| Channel stack recommendation | buyer_type, adoption_stage, awareness_level |
| Proof and credibility plan | trust_signals, adoption_stage, value_equation |
| GTM launch sequence | buyer_type, switching_forces, awareness_level, adoption_stage |

If the buyer map is inferred only, downstream artifacts carry `inferred_buyer_map: true`.

---

## Forbidden Behaviors

1. Do not generate messaging, positioning, channel recommendations, or launch plans before a buyer map exists.
2. Do not present inferred buyer intelligence as validated fact.
3. Do not generate conversion rate estimates, revenue projections, lead volume targets, or CAC/LTV figures without client baseline data.
4. Do not average earlyvangelist and mainstream buyer profiles into one persona.
5. Do not skip lenses because input is thin.
6. Do not block generation on a questionnaire. Generate first, flag assumptions, then ask the three highest-priority calibration questions.
