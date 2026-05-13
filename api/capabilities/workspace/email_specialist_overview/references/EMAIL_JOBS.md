# Email Jobs — Reference

This file is a lazy-loaded resource for the `email-specialist` skill.
It is loaded only when the skill is active AND the user asks for detail on a specific job.

---

## Job 1 — Plan

**When to use:** User asks to plan an email campaign, build an email strategy, or map out an email sequence.

**Inputs (auto-loaded from memory):**
- Brand profile (voice, tone, values)
- Product catalog (for offer selection)
- Audience profiles (pain points, demographics)
- Campaign Brand Kit (visual and messaging rules)

**Additional inputs (ask if missing):**
- Campaign goal (sign-ups, demos booked, re-activation, nurture)
- Target segment (which audience profile)
- Approximate send volume
- Timeline / urgency

**Outputs:**
- Campaign plan artifact in Workspace: goal, audience, sequence map (email titles + purpose + send day), success metric
- Plan reviewed and confirmed before any drafting begins

**Example output shape:**

```
Campaign: Cold Outreach — Klaroha Demo Request
Goal: 5 booked demos in 30 days
Audience: B2B founders with distributed seller teams (30–200 employees)
Sequence: 5-email cold outreach
  Email 1 (Day 0): Pain-led hook — fragmented seller ops
  Email 2 (Day 2): Proof-point — how one team cut signal noise by 40%
  Email 3 (Day 4): Social proof + objection handling
  Email 4 (Day 7): Value summary + low-friction CTA
  Email 5 (Day 10): Breakup — last chance
Success metric: Reply rate ≥ 8%, booking rate ≥ 2%
```

---

## Job 2 — Draft / Revise

**Email types covered:**
- Cold outreach (single or sequence)
- Follow-up (post-meeting, post-demo, post-event)
- Newsletter / broadcast
- Announcement (product launch, feature update)
- Reactivation (dormant contacts)
- Welcome / onboarding sequence
- Nurture (long-form educational)
- Referral ask
- Review ask

**Rules:**
- Draft goes to Workspace. Never appear inline in chat.
- Draft includes: Subject line, Preheader (if applicable), Body, CTA.
- Draft uses brand voice/tone from Campaign Brand Kit.
- Draft follows char/word limits appropriate to the email type.
- After draft is in Workspace, CMO confirms: "[Type] draft is in Workspace — ready for review."

**Revision rules:**
- Revision is triggered by user feedback on an existing approved/rejected draft.
- Revision brief = prior draft + user feedback. Never re-draft from scratch unless told to.
- Revision result replaces prior draft in Workspace. Parent draft ID is preserved.

---

## Job 3 — Inbox Intelligence

**When to use:** User asks for inbox monitoring, reply classification, signal analysis, or "what are my replies saying?"

**Requires:** Gmail connector on the active brand (Admin → Brands → Connect Gmail).

**Reply signal categories:**

| Signal | Examples | Recommended action |
|---|---|---|
| Interested | "Tell me more", "Can we chat?", "Sounds relevant" | Book call, move to warm sequence |
| Objection | "We already use X", "Not sure it fits" | Objection-handling reply |
| Pricing concern | "What's the cost?", "Too expensive" | Pricing page + ROI framing |
| Not now | "Reach out in Q3", "On hold" | Archive + follow-up reminder |
| Wrong person | "Not my department", "Try [name]" | Re-route to named contact |
| Unsubscribe | "Remove me", "Stop emailing" | Remove immediately, no reply |
| Booked | "Sent invite", "We're on for Tuesday" | Move to CRM, confirmation email |

**Output:** Classification summary artifact in Workspace. Never outputs raw email content or personal data inline.

---

## Job 4 — Approved Send

**When to use:** User explicitly approves a draft and asks to send it, OR user explicitly asks to send an email (with a connected Gmail account and an approved draft).

**Required pre-conditions (all must be true):**
1. An approved draft exists in Workspace.
2. Gmail connector is present and connected for the active brand.
3. User has explicitly confirmed the send action (not just approved the draft).

**Send types:**
- **Test send** — to a specified test address before real send.
- **Real send** — to the intended recipient list.

**CMO confirmation reply:**
```
Sending to [recipient] now.

Check your inbox for the delivery receipt.
```

**If pre-conditions are not met:**
- No approved draft → "Approve the draft in Workspace first, then I'll send."
- No connector → "A Gmail connection is needed. Go to Admin → Brands → Connect Gmail."
- User didn't explicitly confirm → "Just to confirm — send the approved draft to [recipient]?"
