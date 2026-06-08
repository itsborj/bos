# Agent Marketplace — Concept Brief

**Status:** Parked concept. No implementation until BITE sample approved.
**Origin:** Conversation 2026-06-09 — Stripe business model ported to AI agent workflows.

---

## The Core Principle

Stripe looked at payments and said: "This should not be a destination. It should be a line of code."

This concept applies the same move to marketing execution:

> **Marketing micro-tasks should not be projects. They should be function calls.**

Agencies charge retainers for tasks that could be composable primitives — each with a defined input schema, structured output, approval gate, and price. The platform absorbs the complexity (who built the workflow, what model it uses, how output is structured) and exposes a clean callable surface.

---

## The Marketplace Model

**"Upwork/Fiverr for AI agents"** — but the unit being sold is not labor. It is a **configured capability**: a human-supervised AI workflow with a published interface. The seller's value is their specific prompt architecture, tool chain, agent logic, and quality filter. Payment is released on approved delivery, not on time or subscription.

| Layer | What it is |
|---|---|
| Seller | Operator who built and maintains a configured AI workflow |
| Buyer | Operator who needs the output, invoked directly or via API |
| Platform | Trust layer: schema registry, escrow, approval, versioning |
| Revenue | Transaction fee on approved delivery — platform earns only when value is delivered |

---

## The Stripe API Port

### Invocation pattern

```http
POST /agents/competitive-analysis
{
  "company": "Acme Corp",
  "depth": "deep",
  "output_format": "executive_brief"
}
→ { "job_id": "job_abc123" }
```

```http
GET  /jobs/job_abc123          # poll or webhook on completion
POST /jobs/job_abc123/approve  # triggers payment release (escrow capture)
POST /jobs/job_abc123/reject   # triggers dispute or revision
```

This mirrors Stripe's **authorize → fulfill → capture** payment intent loop.

### SDK experience

```javascript
const agent = await platform.agents.invoke('competitive-analysis', {
  company: 'Acme Corp',
  depth: 'deep'
})

await agent.onComplete((result) => {
  if (meetsStandard(result)) {
    await agent.approve()
  }
})
```

The web UI is a fallback and sales tool. API invocation is the primary interface. That is the inversion from Fiverr.

---

## The Marketing Primitives

Atomic marketing tasks that become callable functions:

```
icp_profile()               → structured ICP definition
positioning_statement()     → positioning doc from ICP
competitor_analysis()       → competitive landscape brief
ad_angle_generator()        → angle variants from positioning
email_sequence()            → full drip from brief
content_brief()             → creative brief per format
hook_variants()             → scroll-stop hooks from angles
offer_critique()            → offer evaluation + gaps
funnel_audit()              → conversion analysis
seo_gap_analysis()          → keyword opportunity map
```

Each primitive:
- Takes a defined input schema
- Returns structured output
- Has an approval gate
- Has a price

---

## Composability Is the Product

Individual primitives are useful. The unlock is when they chain:

```
icp_profile()
  → positioning_statement(icp)
    → ad_angle_generator(positioning)
      → hook_variants(angles)
```

A full top-of-funnel build from four composed primitives, each seller paid for their leg. The buyer assembled a workflow without hiring an agency.

**Agent-calls-agent:** A "market research report" agent internally invokes a "company background" agent + "competitive landscape" agent + "executive summary" agent — each from different sellers, each paid on delivery. This is a **composable agent supply chain with payment rails embedded**.

---

## Infrastructure Requirements

### 1. Standardized Agent Interface (schema contract)
Every agent needs a defined:
- Input schema — what parameters it accepts
- Output schema — what it returns and in what format
- SLA — expected delivery time (sync vs async)
- Approval hook — how the buyer signals acceptance

### 2. Async Delivery Infrastructure
- `POST /invoke` → returns `job_id` immediately
- `GET /jobs/{id}` → polling or webhook on completion
- `POST /jobs/{id}/approve` → payment release
- `POST /jobs/{id}/reject` → dispute or revision

### 3. Escrow as Infrastructure
Payment authorized on invocation; captured on approval. The platform holds funds between invoke and approve. This is where platform trust and revenue live.

### 4. Versioning and Stability
API-embedded agents need semantic versioning, deprecation notices, and stability tiers (experimental / stable / deprecated). Infrastructure has SLAs. Marketplaces do not.

---

## The Moat

| Layer | What it creates |
|---|---|
| API-invocable agents | Buyers embed in their own products — switching cost grows |
| Escrow + approval loop | Platform owns the trust layer — can't be disintermediated |
| Schema registry | Network effect — more defined agents = more composable workflows |
| Versioning + SLAs | Enterprise buyers can depend on it — unlocks bigger contracts |

The platform becomes load-bearing infrastructure in buyers' pipelines.

---

## Relationship to BOS

BOS is the first-party implementation of this model for marketing operations:
- BOS plugins are pre-built, operator-controlled versions of these composable primitives
- The `marketing.plan / .execute / .optimize` job model is the collapsed owner-facing surface over many underlying primitives
- The BITE pipeline (Bridge → Transform → Evaluate) is the internal execution contract that would power agent-to-agent composition
- The Extension Host / plugin contract is the internal equivalent of the platform's schema registry and activation model

A marketplace version of this idea would externalize the plugin/capability model: third-party operators publish their workflows as invocable agents; buyers call them via API; the platform handles schema validation, escrow, approval, versioning, and trust.

**This is a parked concept.** No implementation until the BOS core plugin lifecycle, Extension Host, and composable pipeline are proven in production.
