---
id: workspace.council
name: council
description: >
  Convene the Council — 5 senior CMO peers who deliberate on a multi-layered
  strategic question in an agentic loop until they reach alignment.
  Triggered exclusively by @council <question>. Manual invocation only.
  Access is operator-gated.
version: 1.0.0
status: active
license: proprietary
compatibility:
  bos: ">=3.0.0"
metadata:
  author: BOS Core
  updated: "2026-05-20"
scope: workspace
allowed_from_chat: true
module_id: workspace.council

triggers:
  - "@council"

excluded_triggers: []

requires_intent: []

# Council configuration
council:
  seats:
    - c1
    - c2
    - c3
    - c4
    - c5
  max_rounds: 5
  convergence_threshold: 5   # seats that must signal ALIGNED to settle
  synthesis_provider: openrouter
  synthesis_model: openai/gpt-4o

output_contract:
  - council_brief artifact with marching_orders and parked_decisions
  - rounds logged to council_sessions table
  - each round streamed as C1: C2: C3: C4: C5: labelled blocks
---

# Council Capability

The Council is a hidden, high-value deliberation move available to select operators.

When `@council <question>` is sent, BOS convenes 5 senior CMO council members.
Each member is defined by their own `seats/cN/SKILL.md` — their ideology,
model assignment, and granted tools. The council runs an agentic loop in which
members see each other's positions and converge through peer deliberation.

The operator can inject context between rounds. The loop ends when all seats
signal alignment or `max_rounds` is reached.

Settlement produces:
- **Marching orders** — numbered, concrete actions
- **Parked decisions** — unresolved items with tags, pending operator decision

Council output is not CMO chat output. It is a `council_brief` artifact.
