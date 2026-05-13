# Marketing Planning Specialist v1 — Approved Sample

Status: approved 2026-05-13  
Purpose: native BOS marketing planning specialist that creates reviewable plan artifacts instead of pasting long plans into CMO chat.

## User → CMO flow

User:
```text
@klar plan for motormoto
```

CMO visible reply:
```text
I’ll build a campaign plan for MotorMoto.

It’ll be ready in Workspace for review.
```

Tool action:
```text
RUN: marketing.plan.campaign_strategy
```

## Workspace plan artifact

```text
MotorMoto Plan
Q3 Dependable Mobility

Mission
Become the trusted choice for everyday riders who need practical, reliable mobility.

Focus
1. Demand capture
2. Trust proof
3. Local search readiness

Recommended channels
• Email — nurture warm leads
• GBP — local proof + discovery
• Google Ads — hold until budget is confirmed

Not recommended yet
• X/Twitter — no clear demand signal
• LinkedIn — only if B2B partnerships matter

Missing inputs
• Monthly budget
• Current lead source
• Top offer
• Competitor examples
```

CMO follow-up after artifact exists:
```text
Plan draft is ready.

Main gap: budget.
Want me to revise around a lean/no-ad-spend version?
```

## Structured artifact block shape

```json
{
  "type": "marketing_plan",
  "artifact_type": "plan_artifact",
  "title": "MotorMoto Plan",
  "status": "pending_review",
  "mission": "Become the trusted choice for everyday riders who need practical, reliable mobility.",
  "focus": ["Demand capture", "Trust proof", "Local search readiness"],
  "recommended_channels": [
    {"channel": "Email", "role": "nurture warm leads", "status": "active"},
    {"channel": "GBP", "role": "local proof + discovery", "status": "active"},
    {"channel": "Google Ads", "role": "hold until budget is confirmed", "status": "hold"}
  ],
  "not_recommended_yet": [
    {"channel": "X/Twitter", "reason": "no clear demand signal"},
    {"channel": "LinkedIn", "reason": "only if B2B partnerships matter"}
  ],
  "missing_inputs": ["Monthly budget", "Current lead source", "Top offer", "Competitor examples"],
  "allowed_actions": ["approve", "revise", "dismiss"]
}
```

## Forbidden outcome

```text
CMO pastes a giant markdown plan directly in chat with random channels, generic weekly posting quotas, and confirm syntax inside the user-facing reply.
```

Why forbidden: chat is the mobile control surface; Workspace owns the reviewable plan artifact.
