---
id: marketing.launch.execution
name: launch-execution
description: "Launch coordination skill for managing launch checklists, stakeholder alignment, and day-of execution for product and feature launches. Use when user requests "launch checklist," "launch coordination," or is ready to execute a planned launch. BOS provides checklists and coordination frameworks only — actual execution requires external tools and human coordination."
scope: knowledge
status: active
allowed_from_chat: true
requires_intent:
  - diagnostic
  - generation
triggers:
  - launch checklist
  - launch coordination
  - launch execution
  - launch day
  - pre-launch checklist
  - go no-go
  - launch readiness
  - stakeholder alignment
  - war room
  - rollback plan
excluded_triggers:
  - create launch strategy
  - plan a launch
  - gtm planning
  - go-to-market strategy
memory_slots:
  - brand_profile
  - product_catalog
quality_gates:
  - explicit_generation_or_revision_intent
  - no_visible_control_directives
related_skills:
  - marketing.launch.strategy
  - marketing.launch.sequencing
metadata:
  version: 1.0.0
---

# Launch Execution

Launch coordination including checklists, stakeholder alignment, and day-of execution management.

**HARD GATE:** GTM plan MUST be completed before launch execution. If the user hasn't planned their launch yet, direct them to `launch-strategy` first.

## Purpose

Launch execution ensures smooth transition from planning to market:

- Coordinates all stakeholders and dependencies
- Manages pre-launch checklist completion
- Orchestrates day-of activities
- Establishes post-launch monitoring

---

## Phase 1: Launch Readiness Assessment

Evaluate launch prerequisites before proceeding:

### GTM Prerequisites Checklist

| Prerequisite | Status | Owner | Notes |
|--------------|--------|-------|-------|
| Market Analysis Complete | DONE/IN PROGRESS/NOT STARTED | [Owner] | [Link] |
| Positioning Approved | DONE/IN PROGRESS/NOT STARTED | [Owner] | [Link] |
| Messaging Framework Final | DONE/IN PROGRESS/NOT STARTED | [Owner] | [Link] |
| Pricing Approved | DONE/IN PROGRESS/NOT STARTED | [Owner] | [Link] |
| GTM Plan Approved | DONE/IN PROGRESS/NOT STARTED | [Owner] | [Link] |

### Product Prerequisites

| Prerequisite | Status | Owner | Notes |
|--------------|--------|-------|-------|
| Product/Feature Ready | DONE/IN PROGRESS/NOT STARTED | [Owner] | [Version] |
| QA Complete | DONE/IN PROGRESS/NOT STARTED | [Owner] | [Sign-off] |
| Documentation Ready | DONE/IN PROGRESS/NOT STARTED | [Owner] | [Link] |
| Support Trained | DONE/IN PROGRESS/NOT STARTED | [Owner] | [Date] |

### Readiness Score

| Category | Score | Threshold | Status |
|----------|-------|-----------|--------|
| GTM Readiness | X/Y | Y | GO/NO-GO |
| Product Readiness | X/Y | Y | GO/NO-GO |
| Sales Readiness | X/Y | Y | GO/NO-GO |
| Ops Readiness | X/Y | Y | GO/NO-GO |
| **OVERALL** | **X/Y** | **Y** | **GO/NO-GO** |

**If OVERALL = NO-GO:** Stop and address gaps before proceeding.

---

## Phase 2: Pre-Launch Checklist

Complete by category:

### Marketing Assets (Due: T-14 days)
- [ ] Website updates staged
- [ ] Landing pages live (stealth if needed)
- [ ] Email sequences loaded
- [ ] Social media posts scheduled
- [ ] Press release approved
- [ ] Blog posts drafted
- [ ] Paid media campaigns created
- [ ] Launch video/demo complete

### Sales Enablement (Due: T-7 days)
- [ ] Sales deck updated
- [ ] Product demo environment ready
- [ ] Pricing sheet updated
- [ ] FAQ document complete
- [ ] Competitive battlecards updated
- [ ] Sales team briefed
- [ ] First-call script updated
- [ ] Commission/compensation updated (if applicable)

### Customer Success (Due: T-7 days)
- [ ] Support documentation updated
- [ ] Knowledge base articles published
- [ ] Support team trained
- [ ] Escalation paths defined
- [ ] Customer communication drafted
- [ ] Onboarding materials updated

### Technical (Due: T-3 days)
- [ ] Feature flags configured
- [ ] Monitoring dashboards ready
- [ ] Rollback plan documented
- [ ] Performance baseline established
- [ ] Security review complete

### Legal/Compliance (Due: T-7 days)
- [ ] Terms of service updated (if needed)
- [ ] Privacy policy updated (if needed)
- [ ] Compliance requirements met
- [ ] Contract templates updated

### Communications (Due: T-1 day)
- [ ] Internal announcement drafted
- [ ] Customer announcement drafted
- [ ] Partner notification drafted
- [ ] Press contacts briefed
- [ ] Social media team briefed

---

## Phase 3: Stakeholder Alignment

Ensure all stakeholders are aligned:

### RACI Matrix

| Activity | Responsible | Accountable | Consulted | Informed |
|----------|-------------|-------------|-----------|----------|
| Go/No-Go Decision | [Name] | [Name] | [Names] | [Names] |
| Launch Day Execution | [Name] | [Name] | [Names] | [Names] |
| Customer Communications | [Name] | [Name] | [Names] | [Names] |
| Escalation Response | [Name] | [Name] | [Names] | [Names] |

### Communication Plan

| Audience | Message | Channel | Timing | Owner |
|----------|---------|---------|--------|-------|
| Internal Team | [Key points] | [Channel] | [When] | [Owner] |
| Sales Team | [Key points] | [Channel] | [When] | [Owner] |
| Customers | [Key points] | [Channel] | [When] | [Owner] |
| Partners | [Key points] | [Channel] | [When] | [Owner] |
| Press | [Key points] | [Channel] | [When] | [Owner] |

### Escalation Matrix

| Issue Type | Level 1 | Level 2 | Level 3 |
|------------|---------|---------|---------|
| Technical | [Name] | [Name] | [Name] |
| Customer | [Name] | [Name] | [Name] |
| PR/Comms | [Name] | [Name] | [Name] |
| Executive | [Name] | [Name] | [Name] |

---

## Phase 4: Day-of Execution Plan

Orchestrate launch day:

### Launch Day Timeline

| Time | Activity | Owner | Status |
|------|----------|-------|--------|
| 06:00 | Pre-launch check | [Owner] | PENDING |
| 07:00 | Activity | [Owner] | PENDING |
| 08:00 | Feature flip | [Owner] | PENDING |
| 09:00 | Public announcement | [Owner] | PENDING |
| 10:00 | PR embargo lifts | [Owner] | PENDING |
| 12:00 | Social media push | [Owner] | PENDING |
| 14:00 | Check-in meeting | [Owner] | PENDING |
| 17:00 | End-of-day review | [Owner] | PENDING |

### War Room Setup

**Location/Channel:** [Physical room or Slack channel]

**Participants:**
- [Name]: [Role]
- [Name]: [Role]
- [Name]: [Role]

**Communication Cadence:**
- Hourly status updates
- Immediate escalation for blockers
- EOD summary

### Rollback Triggers

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Error rate | >X% | [Specific rollback action] |
| Customer complaints | >X in Y minutes | [Escalation action] |
| System down | Any duration | [Immediate action] |

### Success Metrics (Day 1)

| Metric | Target | Tracking Location |
|--------|--------|-------------------|
| [Metric 1] | [Target] | [Dashboard/Tool] |
| [Metric 2] | [Target] | [Dashboard/Tool] |
| [Metric 3] | [Target] | [Dashboard/Tool] |

---

## Phase 5: Post-Launch Monitoring

Establish monitoring cadence:

### Monitoring Schedule

| Timeframe | Focus | Meeting/Review | Owner |
|-----------|-------|----------------|-------|
| Day 1 | Issues, initial metrics | War room | [Owner] |
| Day 2-3 | Stabilization, feedback | Daily standup | [Owner] |
| Week 1 | Early adoption, bugs | Weekly review | [Owner] |
| Week 2-4 | Trends, optimization | Weekly review | [Owner] |
| 30-Day | Launch retrospective | Full review | [Owner] |

### Metrics Dashboard

| Metric | Target | Day 1 | Day 7 | Day 30 |
|--------|--------|-------|-------|--------|
| [Metric 1] | [Target] | [Actual] | [Actual] | [Actual] |
| [Metric 2] | [Target] | [Actual] | [Actual] | [Actual] |
| [Metric 3] | [Target] | [Actual] | [Actual] | [Actual] |

### Retrospective Questions

1. What went well?
2. What didn't go well?
3. What should we do differently next time?
4. What surprised us?
5. What would we repeat?

---

## Output Format

```markdown
# Launch Execution Plan: [Product/Feature]

## Executive Summary
- **Launch Date:** [Date]
- **Launch Type:** [Tier 1/2/3]
- **Go/No-Go Status:** [GO/NO-GO/PENDING]
- **Launch Owner:** [Name]

## Readiness Assessment
[Phase 1 output]

## Pre-Launch Checklist
[Phase 2 output]

## Stakeholder Alignment
[Phase 3 output]

## Day-of Execution
[Phase 4 output]

## Post-Launch Monitoring
[Phase 5 output]

## Dependencies
- GTM Plan: [Link]
- Messaging: [Link]
- Product Release: [Link]
```

---

## Blocker Criteria

| Blocker | Action |
|---------|--------|
| GTM plan not approved | STOP. Cannot execute without approved plan. |
| Product not ready | STOP. Escalate to product team. |
| Readiness score below threshold | STOP. Address gaps before proceeding. |
| Key stakeholder unavailable | STOP. Reschedule or delegate authority. |

---

## Anti-Rationalization Table

| Rationalization | Why It's WRONG | Required Action |
|-----------------|----------------|-----------------|
| "We can skip the checklist" | Skipped items cause launch failures | Complete every checklist item |
| "Everyone knows their role" | Assumptions cause coordination failures | Document RACI explicitly |
| "We'll handle issues as they come" | Reactive handling causes escalation | Pre-define escalation paths |
| "Rollback won't be needed" | Every launch needs rollback plan | Document rollback triggers |

---

## Related Skills

- **launch-strategy**: For planning GTM strategy before execution
- **launch-sequencing**: For PLF-style launch orchestration
- **email-sequence**: For launch email sequences

---

**Note:** BOS provides launch coordination frameworks and checklists. Actual execution (sending emails, flipping feature flags, posting announcements) requires external tools and human coordination.

