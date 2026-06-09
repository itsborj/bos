from __future__ import annotations

from routers.chat import _marketing_plan_module_id
from capabilities.marketing.planning.strategy_workflow.module import StrategyWorkflowModule


SAMPLE_STRATEGY_WORKFLOW = """# Strategy Workflow — Klaroha

## COMPONENT: archetype
Direct-sales is the closest fit because the trust gap is the main blocker.

Archetype selected: direct_sales

## COMPONENT: buyer_map
Awareness level: problem_aware
Buyer type: early_majority
Push forces:
- overloaded marketing approvals
Pull forces:
- one operating loop for plan, execute, and optimize
Blocking forces: anxiety, habit
Anxiety sources:
- fear that automation will publish the wrong thing
Trust gap: proof that BOS keeps human approval before external action.
Buyer language:
- "I need control without becoming the bottleneck"
Decision roles:
- Champion: operator who owns marketing throughput
- Economic buyer: business owner
- Veto: compliance or brand owner
Confidence: inferred

## COMPONENT: strategic_thesis
Primary motion: founder-led
Secondary motion: content-led
Secondary unlock: once one proof story exists
Wedge: Klaroha can own approval-gated marketing automation for overloaded operators.
Decision: focus on trust-building strategy workflows before channel execution.
Not doing:
- broad paid spend before proof exists
Motion rationale: Founder-led trust building fits a high-anxiety buyer. The failure mode is promising automation before proving approval control.

## COMPONENT: offer_architecture
Audience need: a safer way to coordinate marketing work without losing control
Resource: Strategy Workflow diagnostic
Micro commitment: review one workflow plan
Macro activation: approve a scoped implementation sprint
Offer ladder:
- read the diagnostic
- review the strategy workflow
- approve one work order
- activate the operating loop
Anxiety treatment: each rung keeps approval before execution
Proof required: one visible artifact trail from plan to approval

## COMPONENT: channel_stack
Do now:
**Founder Email**
Role: acquisition
Buyer map signal: blocking_forces: anxiety
Proof required to scale: approved workflow artifact example
Rationale: direct founder outreach can explain the approval boundary clearly.

Hold:
- Paid social — hold until proof story exists — unlock after first approved case study

Avoid:
- broad automation messaging — avoid because anxiety is high

## COMPONENT: tactical_funnel
Reach:
Tactic: founder email to overloaded operators
Parallel track: practical strategy workflow content

Engage:
Resource: Strategy Workflow diagnostic
Sequence: email points to diagnostic, then asks for one review call
Objection surface: fear of losing control

Action:
CTA: review one Strategy Workflow
Commitment level: micro
Next step after: convert accepted workflow into approved work orders

Patronage and learning:
Response categories: anxiety, trust proof, timing
Proof capture: save accepted workflow and objections as proof assets
Learning loop: use objections to revise the next workflow

## COMPONENT: work_orders
1. Founder Outreach Brief
Purpose: start qualified conversations around the approval-gated workflow.
Contents:
- audience list criteria
- outreach angle
Gate: brand owner approves the workflow

2. Diagnostic Landing Page
Purpose: give prospects one place to understand the workflow.
Contents:
- wedge section
- approval boundary proof
Gate: workflow messaging approved

3. Proof Artifact
Purpose: show the plan-to-approval trail.
Contents:
- strategy workflow screenshot
- approval note
Gate: first approved workflow exists

4. Sales One-Pager
Purpose: help calls convert into scoped implementation.
Contents:
- offer ladder
- next step CTA
Gate: diagnostic page approved

Approval note: This is a draft strategy for review. Execution artifacts, outreach, publishing, spend, and external platform actions require separate approval before any action is taken.
"""


def test_klar_plan_selects_strategy_workflow_contract() -> None:
    assert _marketing_plan_module_id() == "marketing.planning.strategy_workflow"


def test_strategy_workflow_module_block_matches_chat_artifact_contract() -> None:
    module = StrategyWorkflowModule()
    verdict, failures = module.self_check(SAMPLE_STRATEGY_WORKFLOW, {"brand_name": "Klaroha"})
    block = module._build_block(SAMPLE_STRATEGY_WORKFLOW)

    assert verdict == "pass", failures
    assert block["type"] == "strategy_workflow"
    assert block["artifact_type"] == "plan_artifact"
    assert block["status"] == "pending_review"
    assert block["components"][0]["type"] == "buyer_map"
    assert {c["type"] for c in block["components"]} == {
        "buyer_map",
        "strategic_thesis",
        "offer_architecture",
        "channel_stack",
        "tactical_funnel",
        "work_orders",
    }
    assert block["components"][3]["data"]["do_now"][0]["channel"] == "Founder Email"
    assert block["components"][5]["data"]["briefs"][0]["title"] == "Founder Outreach Brief"
    assert block["not_wired_components"] == [
        "market_context",
        "framework_lenses",
        "channel_content_matrix",
        "measurement_model",
    ]
    assert block["allowed_actions"] == ["approve", "revise", "dismiss"]
    assert block["risk_level"] == "draft_only"
