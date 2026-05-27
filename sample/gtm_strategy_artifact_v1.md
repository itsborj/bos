# GTM Strategy Artifact v1 — Stage 2 Sample

Status: approved 2026-05-27  
Purpose: upgraded Klaroha strategy generation so a Business Leader can provide minimal input after Brand Brief onboarding and receive an opinionated GTM launch strategy artifact.

## User → CMO flow

Brand state:
```text
Brand Brief exists and includes company, products/services, audience, positioning, tone, and basic business context.
Campaign Brand Kit may exist.
Performance history may or may not exist.
```

User:
```text
Plan a launch for our new done-for-you onboarding service.
```

CMO visible reply:
```text
I’ll build the GTM launch strategy now.

I’ll infer from the Brand Brief and flag only the assumptions that could change the plan.
```

Tool action:
```text
RUN: marketing.planning.gtm_plan
```

## Workspace / Stream artifact

```text
GTM Launch Strategy
Klaroha — Done-For-You Onboarding Service

Best current motion
Founder-led demand capture + proof-building launch.

Why this motion
The Brand Brief points to a high-trust B2B service where buyers need confidence before they act. The fastest path is not broad awareness; it is showing the right operators a clear before/after, then converting interest into consultations or setup calls.

Primary audience
Small agency owners and overloaded business leaders who know marketing execution is fragmented but do not have the time or team to coordinate tools, channels, approvals, and reporting.

Positioning angle
“Launch your marketing operating system without becoming the integrator.”

Core promise
Klaroha turns scattered marketing tools, specialists, approvals, and performance signals into one operating loop the business leader can steer.

Launch sequence
1. Proof setup — collect screenshots, process examples, current workflow pain, and any early customer language.
2. Demand-capture page — publish one focused landing page for the onboarding service.
3. Founder-led outreach — send direct, high-context messages to warm agency/operator contacts.
4. Authority content — publish 2–3 posts showing the fragmented-before / operating-system-after shift.
5. Consultation conversion — route qualified interest to a short diagnostic call or booking page.
6. Post-launch learning — capture objections, replies, and call notes into memory before scaling channels.

Channel stack
Do now
• Website / Landing Page — Active — conversion hub — needed before sending traffic anywhere.
• Founder Email / Direct Outreach — Active — first qualified conversations — best fit for a trust-heavy offer with limited proof.
• LinkedIn or Existing Founder Social — Active if already used — authority and warm demand — use founder perspective, not generic brand posting.
• Google Business Profile / Local SEO — Hold unless the offer is local-service oriented — useful only if buyers search locally.

Hold
• Paid social — no proof or winning message yet.
• Broad community launch — too slow unless a community already exists.
• Affiliate/referral program — useful after the first happy customers exist.
• Product Hunt — weak fit for a service-led B2B onboarding offer unless packaged as a software/product launch.

Avoid for now
• Multi-channel content calendar — creates work before the conversion path is proven.
• Large ad budget — premature without customer language, proof, and tracking.

Conversion path
Visitor sees pain-aware landing page
→ books diagnostic / setup call
→ receives short problem summary + onboarding recommendation
→ approves onboarding package
→ BOS stores objections, decisions, and outcomes as future GTM memory.

First proof assets needed
• Before/after workflow example
• One operator pain quote or testimonial
• Simple “what happens in week 1” onboarding outline
• Screenshot or diagram of the command-center experience

Assumptions I made
• The Brand Brief is enough to infer this is a trust-heavy B2B service launch.
• The goal is qualified conversations, not high-volume self-serve signup.
• Budget is lean until proof and conversion data exist.
• Existing warm network is more reliable than cold paid traffic.

Critical gaps
• Customer proof — unlocks stronger landing page, outreach, and objection handling.
• Primary conversion action — diagnostic call vs. paid setup checkout changes the page and CTA.
• Existing warm audience — determines whether founder-led outreach starts from email, LinkedIn, partners, or direct calls.

Useful later
• Monthly budget
• Target launch date
• Current traffic baseline
• Referral incentive structure
• Sales deck needs

Next artifacts BOS should create
• Landing page copy — convert launch interest into calls or setup inquiries.
• Founder outreach sequence — direct messages/emails for the first qualified conversations.
• Sales one-pager — help the business leader explain the offer quickly.
• Objection handling sheet — capture price, timing, trust, and “why not just use tools?” objections.
• Launch content angles — 3–5 proof-building posts from the positioning angle.

Approval note
This is a draft strategy for review. Execution artifacts, publishing, sending, spend, and external platform actions require separate approval.
```

## Structured artifact block shape

```json
{
  "type": "gtm_strategy",
  "artifact_type": "plan_artifact",
  "title": "GTM Launch Strategy — Klaroha Done-For-You Onboarding Service",
  "status": "pending_review",
  "best_current_motion": "Founder-led demand capture + proof-building launch.",
  "primary_audience": "Small agency owners and overloaded business leaders...",
  "positioning_angle": "Launch your marketing operating system without becoming the integrator.",
  "core_promise": "Klaroha turns scattered marketing tools, specialists, approvals, and performance signals into one operating loop.",
  "launch_sequence": [
    {"step": "Proof setup", "purpose": "Collect screenshots, pain, examples, and customer language."},
    {"step": "Demand-capture page", "purpose": "Publish one focused landing page."},
    {"step": "Founder-led outreach", "purpose": "Start qualified conversations."}
  ],
  "channel_stack": {
    "do_now": [
      {"channel": "Website / Landing Page", "role": "conversion hub", "reason": "needed before sending traffic anywhere"},
      {"channel": "Founder Email / Direct Outreach", "role": "first qualified conversations", "reason": "best fit for a trust-heavy offer with limited proof"}
    ],
    "hold": [
      {"channel": "Paid social", "reason": "no proof or winning message yet"}
    ],
    "avoid_for_now": [
      {"channel": "Large ad budget", "reason": "premature without proof, customer language, and tracking"}
    ]
  },
  "conversion_path": [
    "Landing page",
    "Diagnostic / setup call",
    "Problem summary + recommendation",
    "Approved onboarding package",
    "Outcome memory"
  ],
  "assumptions": [
    "Trust-heavy B2B service launch",
    "Qualified conversations over self-serve signup",
    "Lean budget until proof exists"
  ],
  "critical_gaps": [
    {"gap": "Customer proof", "unlocks": "landing page, outreach, objection handling"},
    {"gap": "Primary conversion action", "unlocks": "CTA and page structure"}
  ],
  "next_artifacts": [
    {"artifact": "Landing page copy", "purpose": "convert launch interest"},
    {"artifact": "Founder outreach sequence", "purpose": "start qualified conversations"},
    {"artifact": "Sales one-pager", "purpose": "explain the offer quickly"}
  ],
  "allowed_actions": ["approve", "revise", "dismiss"]
}
```

## Required behavior

- Use the Brand Brief as the minimum viable strategy context.
- Infer a strong first-draft strategy from available context.
- Ask only when a missing input would materially change the strategy.
- Label assumptions instead of blocking generation.
- Rank gaps by strategic risk: `critical_gaps` vs `useful_later`.
- Recommend a narrow channel stack, not every possible channel.
- Create a Workspace/Stream artifact; keep CMO chat short.
- Preserve approval boundaries for execution, publishing, sending, spending, and external actions.

## Forbidden outcomes

### Forbidden 1 — questionnaire wall

```text
Before I can create a GTM plan, please answer:
1. What is your ICP?
2. What is your CAC?
3. What is your LTV?
4. What is your sales cycle?
5. What is your activation rate?
6. What is your onboarding flow?
7. What is your referral strategy?
8. What is your paid budget?
```

Why forbidden: the Brand Brief exists so the Business Leader can provide minimal input. The CMO should infer and label assumptions.

### Forbidden 2 — generic channel soup

```text
Recommended channels:
Facebook, Instagram, TikTok, LinkedIn, YouTube, Google Ads, SEO, podcasting, influencer marketing, affiliate marketing, webinars, PR, Reddit, Discord, email, SMS.
```

Why forbidden: Klaroha should make a strategic call. Too many channels creates work and weakens execution.

### Forbidden 3 — hallucinated proof or metrics

```text
This launch should generate 300 qualified leads, 15% conversion, and $50K in revenue because similar brands perform well with this strategy.
```

Why forbidden: numeric targets, proof, budgets, and performance claims must come from user input or loaded memory.

### Forbidden 4 — inline mega-plan in chat

```text
CMO pastes the full GTM artifact into the chat thread.
```

Why forbidden: chat is the mobile control surface. Workspace/Stream owns the reviewable artifact.

### Forbidden 5 — execution without approval

```text
CMO creates the strategy and immediately sends emails, publishes posts, or launches ads.
```

Why forbidden: GTM strategy is a plan artifact. Execution artifacts and external actions require separate approval.
