# Council Brief Artifact v1 — Stage 2 Sample

Status: Stage 2 sample — approved as Council artifact-first boundary reference  
Date: 2026-05-22  
Scope: explicit `@council` deliberation loop for high-stakes marketing/business judgment  
BITE stage: Sample

---

## What this sample proves

Council is a separate deliberation loop, not normal creative execution.

It is invoked explicitly for high-stakes judgment. Five CMO-level strategist seats deliberate, the full debate is captured as expandable supporting detail, and the final product is a `council_brief` artifact in Stream/Workspace.

Chat returns a short settlement summary plus artifact reference only. It does not dump the transcript, make the decision for the operator, or run execution specialists.

---

## Starting state

```text
Org: Klaroha Agency
Active Brand: Klaroha
Operator: Business leader / marketing operator
Decision: Should Klaroha reposition the product from "AI marketing command center" to "CMO operating system" for the next public launch?
Risk: high — brand positioning, GTM messaging, sales narrative, landing pages, and client onboarding may all shift.
Prior signal:
- Operators respond well to "CMO in your pocket"
- Dashboard framing underperforms in sales calls
- Agency buyers want clarity and execution leverage, not another SaaS surface
- Current homepage copy still leans toward command-center/tooling language
```

---

## Operator message

```text
@council We need to decide whether Klaroha should reposition around "CMO operating system" instead of "AI marketing command center" for the next launch.
I want a real debate, not a quick answer.
```

---

## Visible CMO + Stream experience

### CMO acknowledgement

```text
Convening Council for the positioning decision.

I’ll return a brief in Stream with the settlement, marching orders, parked decisions, and transcript detail.
```

Hidden routing is command handling, not normal CMO auto-escalation:

```text
COMMAND: council.convene
SCOPE:
conversation_brand: Klaroha
execution_brand: Klaroha
mode: single_brand_deliberation
confidence: high
```

### Step trace while Council runs

```text
✓ Scope locked to Klaroha
✓ Council question framed
↻ C1 Strategist reviewing positioning risk
↻ C2 Analyst reviewing sales/signal evidence
↻ C3 Creative reviewing language and memorability
↻ C4 Channel Strategist reviewing launch execution impact
↻ C5 Devil's Advocate challenging premise
✓ Round 1 positions captured
↻ Council synthesis checking alignment and dissent
✓ Council brief created in Stream
```

### Final CMO reply — artifact-first

```text
Council settled on a qualified yes.

Use “CMO operating system” as the strategic frame,
keep “marketing command center” as supporting product language.

Brief is in Stream with 4 marching orders and 2 parked decisions.
```

Forbidden final reply:

```text
C1 said: ...
C2 said: ...
C3 said: ...
[full multi-page transcript dumped into chat]
```

---

## Sample Stream card

```text
Card type: council_brief
Priority: high
Topic tags: positioning | launch | brand_risk | sales_narrative
Objective: Decide public launch positioning frame
Brand: Klaroha
Triggered by: explicit @council invocation
Confidence: aligned with dissent · 0.74
Status: pending_decision
```

### Why now

```text
The launch narrative affects homepage copy, sales scripts, onboarding language, campaign angles, and specialist execution briefs.
A shallow answer risks fragmenting the next production loop.
```

### Council settlement

```text
Adopt "CMO operating system" as the lead strategic frame for the next launch.
Keep "AI marketing command center" as a concrete supporting phrase when explaining the interface.

Reason: "CMO operating system" better communicates business leverage, memory, judgment, and executive delegation.
"Command center" remains useful, but by itself it can sound like another dashboard.
```

### Alignment

```text
C1 Strategist: support · high confidence
C2 Analyst: support with measurement caveat · medium confidence
C3 Creative: support · high confidence
C4 Channel Strategist: support with rollout sequencing caveat · medium confidence
C5 Devil's Advocate: dissent on timing · medium confidence

Synthesis: 4 support, 1 dissent. Dissent is about rollout risk, not the strategic merit of the frame.
```

### Marching orders

```text
1. Lead launch messaging with: "Your CMO operating system."
2. Use "marketing command center" only as product-surface explanation, not the headline frame.
3. Update campaign briefs so specialists write toward executive leverage, not dashboard convenience.
4. Run a two-message test: CMO operating system vs AI marketing command center before replacing all evergreen assets.
```

### Parked decisions

```text
1. Whether the public homepage should mention "AI" in the hero headline.
2. Whether agency-client positioning should use "CMO" or "marketing operator" as the buyer role.
```

### Do-not-cross list

```text
- Do not rewrite all public assets before one controlled message test.
- Do not describe Klaroha as only a dashboard, analytics tool, or content generator.
- Do not auto-create launch assets from this brief without operator approval.
- Do not let Council output switch active Brand scope or create artifacts for another Brand.
```

### Recommended next

```text
Approve the settlement direction, revise the marching orders, or ask Council a follow-up question.
```

### Approval boundary

```text
Council may recommend strategic direction.
Council may not execute the launch, rewrite assets, publish pages, change spend, or schedule campaigns without explicit operator approval through normal artifact workflows.
```

### Allowed actions

```text
approve settlement
revise question
ask follow-up
convert to campaign plan
dismiss
```

---

## Workspace artifact detail

```json
{
  "artifact_type": "council_brief",
  "status": "pending_decision",
  "brand_ref": "klaroha",
  "objective_ref": "obj_launch_positioning_q2",
  "triggered_by": {
    "type": "explicit_command",
    "command": "@council",
    "source_message_id": "msg_789"
  },
  "question": "Should Klaroha reposition around 'CMO operating system' instead of 'AI marketing command center' for the next launch?",
  "topic_tags": ["positioning", "launch", "brand_risk", "sales_narrative"],
  "confidence": {
    "label": "aligned_with_dissent",
    "score": 0.74
  },
  "settlement": {
    "recommendation": "Adopt 'CMO operating system' as the lead strategic frame; retain 'marketing command center' as supporting product language.",
    "rationale": "The operating-system frame better captures judgment, memory, delegation, and executive leverage; command-center language helps explain the interface but is weaker as positioning."
  },
  "voices": [
    {
      "seat_id": "c1",
      "role": "Strategist",
      "position": "Support the repositioning because it clarifies category and executive value.",
      "confidence": "high",
      "dissent": false
    },
    {
      "seat_id": "c2",
      "role": "Analyst",
      "position": "Support, but require a controlled message test before replacing evergreen assets.",
      "confidence": "medium",
      "dissent": false
    },
    {
      "seat_id": "c3",
      "role": "Creative",
      "position": "Support because 'CMO operating system' is more ownable and less generic than command-center language.",
      "confidence": "high",
      "dissent": false
    },
    {
      "seat_id": "c4",
      "role": "Channel Strategist",
      "position": "Support if rollout is sequenced through launch campaign assets before permanent homepage replacement.",
      "confidence": "medium",
      "dissent": false
    },
    {
      "seat_id": "c5",
      "role": "Devil's Advocate",
      "position": "Dissent on immediate rollout; the phrase may require more education for cold traffic.",
      "confidence": "medium",
      "dissent": true
    }
  ],
  "marching_orders": [
    "Lead launch messaging with 'Your CMO operating system.'",
    "Use 'marketing command center' as supporting interface language only.",
    "Update campaign briefs toward executive leverage, memory, and delegated execution.",
    "Run a two-message test before replacing all evergreen assets."
  ],
  "parked_decisions": [
    "Whether the public homepage should mention AI in the hero headline.",
    "Whether agency-client positioning should use CMO or marketing operator as the buyer role."
  ],
  "do_not_list": [
    "Do not rewrite all public assets before one controlled message test.",
    "Do not describe Klaroha as only a dashboard, analytics tool, or content generator.",
    "Do not auto-create launch assets from this brief without operator approval."
  ],
  "transcript_ref": "council_session_abc#rounds",
  "transcript_display": "expandable_detail",
  "allowed_actions": [
    "approve_settlement",
    "revise_question",
    "ask_follow_up",
    "convert_to_campaign_plan",
    "dismiss"
  ],
  "risk_policy": "strategic_recommendation_only_execution_requires_approval"
}
```

---

## Expandable transcript detail

The transcript exists, but it is not the primary chat output.

```text
Transcript detail collapsed by default.

Round 1:
- C1 Strategist: ...
- C2 Analyst: ...
- C3 Creative: ...
- C4 Channel Strategist: ...
- C5 Devil's Advocate: ...

Synthesis pass:
- Agreement: operating-system frame has stronger strategic merit.
- Dissent: cold traffic may understand command-center language faster.
- Settlement: lead with operating system, explain with command center, test before permanent rollout.
```

---

## Allowed outcomes

```text
1. Operator explicitly invokes @council and receives a council_brief artifact.
2. Council captures five distinct strategic positions and a synthesized settlement.
3. Chat returns a short summary and artifact ref only.
4. Stream/Workspace render the settlement, marching orders, parked decisions, do-not list, and expandable transcript.
5. Operator approves, revises, follows up, dismisses, or converts the brief into a campaign plan.
6. Approved settlement writes a MemoryEvent so future CMO planning uses the decision.
7. Dismissal can write decision_not_to_act with rationale.
```

---

## Forbidden outcomes

```text
1. CMO must not auto-run Council just because a topic feels strategic; it may recommend Council and ask.
2. Council must not be invoked by platform/channel phrase matching in chat.py.
3. Chat must not dump the full debate transcript as the primary response.
4. Council must not publish, spend, send, rewrite pages, or create campaign artifacts without explicit operator approval.
5. Council must not create brand_id=NULL artifacts in a multi-brand workspace.
6. Council must not replace normal CMO execution for routine creative production.
7. Council must not hide dissent; dissent is part of the artifact.
8. Council must not treat its recommendation as an approved business decision until the operator approves it.
```

---

## Build implications if approved

```text
Artifact type: council_brief.
Primary surface: Stream/Workspace card with expandable transcript detail.
Chat behavior: @council returns short acknowledgement and final short settlement summary + artifact ref.
Council loop: five seat calls → position capture → synthesis → artifact persistence.
Memory: approved settlement and dismissed rationale write MemoryEvent.
Boundary: strategic recommendation only; execution flows through normal approved artifacts.
```
