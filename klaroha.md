# Agentic Development Map

## Temporary Implementation Note — Remove When Addressed

CMO tools currently has three unresolved architecture smells:

1. **CMO tools logic hug** — the CMO tool layer is holding operational logic that should belong to the actual capability/tool owners.
2. **API dump monolith** — too much product/domain logic is being placed under `api/` because it is convenient, not because the Agentic Development Map assigned ownership there.
3. **Campaign V2 database-first violation** — architecture/refactor discussion and code paths drift toward prompt context, JSON, summaries, working context, memory, or tool prose as campaign truth even though Campaign V2 explicitly requires canonical DB rows/columns as the source of truth.

Use this note as a warning during the CMO chat tools and Campaign V2 refactor. Remove it once ownership boundaries are corrected and documented in the proper vertical owners.

## Universal Admin Prerequisite Rule

Any Admin surface that blocks, warns, disables a primary action, or states that setup is required must register that prerequisite in the shared readiness checklist logic (`web/src/utils/streamActivationChecklist.ts`) unless it is purely one-off form validation or a runtime incident.

The checklist is the universal setup gate for Stream/Admin readiness. Stream, Admin → Stream Setup, and future readiness surfaces must consume the shared checklist instead of duplicating local prerequisite logic.

Runtime incidents such as failed runs, pending approvals, and open pending decisions belong in operational health/attention surfaces, not the setup checklist.

## Minimal Brand Workflow Contract

Keep the brand setup model minimal:

```text
Onboarding → Integrations → Readiness → use CMO
```

Only three surfaces own setup/readiness logic:

1. **Onboarding**
   - owns brand setup truth
   - brand profile configured
   - Brand Creative Brief / Brand Kit approved
   - live campaign present

2. **Integrations**
   - owns connector truth
   - Google Drive connected / needs reauth
   - Drive root selected
   - brand mark/logo present
   - Gmail connected
   - Google Calendar connected
   - publish channels connected

3. **Readiness**
   - owns only the aggregate health decision
   - reads canonical outputs from Onboarding + Integrations
   - does not re-check locally
   - decides blocker ordering and next action routing

Supporting rules:

- **Brands / Clients** is an index and entry point, not a readiness engine.
- **Setup Checklist / Stream Setup** must consume canonical readiness inputs and must not invent alternate setup truth.
- **Onboarding** may guide the user into Integrations when Drive/channel setup is required, but it must not duplicate connector ownership.
- **Integrations** may display connection state and validation state, but it must not decide aggregate readiness.
- **Readiness** is the only surface allowed to say a brand is ready/blocked for CMO use.

If a bug concerns:

- profile / brief / live campaign truth → fix **Onboarding**
- drive / OAuth / folder / logo / channel connection truth → fix **Integrations**
- blocked / ready labels, blocker ordering, next-action routing → fix **Readiness**

## Architecture Clarification — Vertical Owners, Platform, Agents

Use vertical ownership, but do not force every product area into a removable plugin.

In this project, a removable capability/plugin-style unit is validated by the
**delete test**:

```text
delete plugins/youtube/
```

means YouTube behavior disappears, but BOS still stands. The same applies to
Meta, Google Drive, Postcraft, Storyboard, Previs Motion, and future removable
capabilities.

A removable plugin owns its local API adapter, tools, schemas/contracts, tests,
docs, UI hooks if needed, and implementation. Its HTTP/API file is still owned
by the plugin folder, not by a central `api/routers` bucket.

But not everything is removable.

**CMO does not belong in plugins.** CMO is an agent/orchestration surface. It
interprets context, chooses tools, and explains recommendations. It should not
own channel internals or Campaign truth.

**Campaign does not belong in plugins or the fat `api/` dump.** Campaign is
authoritative product state. Channels and creative tools can be removed;
Campaign remains the operating source of truth. If Campaign exposes HTTP routes,
those route files belong to the Campaign vertical, e.g. `campaign/api.py`, and
the host app only mounts them.

Non-removable foundations should be owned by explicit vertical/platform owners,
not hidden in `api/` because it is convenient:

```text
api/campaign/          # isolated Campaign package: identity, product truth, and row contract
artifacts/             # artifact lifecycle/state if foundational
cmo/                   # CMO prompt/loop contracts and behavior
platform/auth          # auth/session/permissions
platform/db            # DB/session/migrations foundation
platform/tools         # generic tool registry/dispatch contracts
platform/providers     # provider resolution/adapters
platform/observability
```

The source repository keeps the isolated runtime `campaign` package at
`api/campaign/` so the existing API image includes it. That directory is a
vertical package, not part of the generic router/service/model dump.

`api/` is otherwise the host/transport shell. It may mount `campaign/api.py`, `cmo/api.py`,
or `plugins/youtube/api.py`, but it must not own their domain behavior.

Rule of thumb:

```text
If it is removable, channel-specific, or specialist-owned → plugin vertical.
If it is authoritative product truth → non-removable product vertical.
If it is shared runtime infrastructure → platform.
If it interprets and orchestrates → agent vertical.
If it is just HTTP/app boot/mounting → api host shell.
```

Ownership includes API files. `campaign/api.py` is Campaign-owned.
`plugins/youtube/api.py` is YouTube-owned. `cmo/api.py` is CMO-owned. Central
`api/routers/*` must not be used as a compatibility home for vertical behavior.
If an old route path must be preserved, the vertical-owned API keeps that path
while the host app mounts it.

## Proper Vertical Folder Structure

The repository should move away from horizontal technical buckets where one capability is scattered across:

```text
api/routers
api/services
api/schemas
api/models
api/tests
web/src
plugins
```

That structure violates vertical ownership because deleting a capability folder does not remove the capability.

The target shape is vertical by product/capability ownership:

```text
api/
  host runtime / transport shell only
  - app boot
  - route mounting from vertical owners
  - auth/session dependencies
  - db/session wiring
  - config
  - middleware
  - generic error handling
  - provider registry / plugin loading hooks
  - generic tool registry shell

  It does not own Campaign, CMO, plugin, or artifact behavior.
  It imports/mounts APIs owned by their vertical folders.
```

```text
api/campaign/  # runtime package: campaign
  non-removable product truth
  - Campaign relational identity/lifecycle (`campaigns`)
  - dated Campaign operating truth (`campaign_rows`)
  - Campaign tools: read/create/append/patch/act
  - Campaign API adapter, if any, e.g. campaign/api.py
  - Campaign status/verdict fields and validation boundaries
  - Campaign schemas/contracts
  - Campaign tests

  Campaign API is Campaign-owned. Do not put Campaign API behavior in
  api/routers/campaigns.py. If `/campaigns/...` paths must remain stable,
  campaign/api.py defines those paths and api/main.py mounts them.

  Current Campaign API write/read language is rows, not snapshots:
  `/api/campaigns/{campaign_id}/rows` is valid;
  `/api/campaigns/{campaign_id}/snapshots` is not part of the active contract.
```

```text
cmo/
  non-removable agent surface
  - CMO chat behavior
  - CMO prompt
  - CMO tool-use policy
  - CMO loop contracts
  - CMO response guidance
```

```text
plugins/google-drive/
plugins/meta/
plugins/youtube/
plugins/postcraft/
plugins/storyboard/
plugins/previs-motion/
  removable capability/plugin units
  - local API routes
  - tools
  - schemas/contracts
  - service/client implementation
  - tests
  - docs
  - UI hooks if needed
```

```text
web/
  frontend shell
  - app shell
  - shared navigation
  - generic surfaces
  - plugin/vertical UI mounting points
```

```text
packages/
  reusable SDK/package code

relay/
  separate relay runtime

docs/
  documentation and decision records

# specs/ was removed from the active product map.
# Feature plans belong in docs/ or issue/task tracking unless they become
# executable product-owned artifacts.
```

### Vertical Ownership Rule

A capability owns its API, tools, schemas, tests, docs, and UI hooks.

Example of wrong horizontal ownership:

```text
api/routers/youtube.py
api/services/youtube.py
api/schemas/youtube.py
plugins/youtube/
web/src/youtube/
api/tests/youtube/
```

Example of correct vertical ownership:

```text
plugins/youtube/
  api.py
  tools.py
  service.py
  schemas.py
  tests/
  docs/
  ui/
```

Then:

```text
delete plugins/youtube/
```

means YouTube is gone and the rest of BOS still stands. This delete test applies
to ownership of API files too: YouTube API behavior belongs in
`plugins/youtube/api.py`, not `api/routers/youtube.py`.

### Active Plugin API Ownership Map

Installed plugin HTTP behavior must live in the plugin folder and be mounted by
the host shell. Stable legacy URL paths may remain for compatibility, but the
file that defines the route must be plugin-owned.

Current expected ownership:

```text
plugins/google-drive/api.py
  GET  /social/google-drive/callback
  GET  /social/drive/picker-config
  GET  /social/drive/folders
  GET  /social/drive/images
  GET  /social/drive/thumbnail/{file_id}
  POST /social/drive/reference-upload
  POST /social/drive/attachment-upload
  POST /social/drive/root

plugins/postcraft/api.py
  POST /postcraft/runs/{run_id}/render
  POST /postcraft/runs/{run_id}/revise
  GET  /postcraft/campaign-alignment

plugins/storyboard/api.py
  POST /storyboard/runs/{run_id}/render
  POST /storyboard/runs/{run_id}/revise

plugins/previs-motion/api.py
  POST /previs-motion/runs/{run_id}/generate-video
  POST /previs-motion/runs/{run_id}/regenerate
  POST /previs-motion/runs/{run_id}/revise
```

CMO Chat must not call generic run-action endpoints for these plugin-specific
workflow transitions when a plugin-owned endpoint exists. Inline CMO Chat review
cards use `ApprovalBundle`, and those buttons must call the owner endpoints:

```text
Postcraft draft approval   → /postcraft/runs/{run_id}/render
Postcraft revision         → /postcraft/runs/{run_id}/revise
Storyboard draft approval  → /storyboard/runs/{run_id}/render
Storyboard revision        → /storyboard/runs/{run_id}/revise
Storyboard image → video   → /previs-motion/runs/{run_id}/generate-video
Previs Motion revision     → /previs-motion/runs/{run_id}/revise
```

`/runs/{run_id}/actions/{action}` remains only a generic compatibility/action
primitive. It must not be the primary CMO Chat path for Postcraft, Storyboard,
Previs Motion, Google Drive, or other concrete plugin-owned operations once the
plugin exposes its own API adapter.

The same ownership rule applies to non-removable verticals even though they are
not deletable:

```text
campaign/api.py belongs to campaign/
cmo/api.py belongs to cmo/
artifacts/api.py belongs to artifacts/
```

The central `api/` shell mounts those APIs; it does not own their behavior.

### Non-Plugin Areas

Do not force everything into plugins.

```text
campaign/  # not optional; owns product truth, including campaign/api.py
cmo/       # not optional; owns agent/orchestration behavior, including cmo/api.py
api/       # not a domain; host/transport shell and route mounting only
```

### Better Direction

The best version is:

```text
api/ becomes tiny.
plugins/ become truly removable.
campaign/ owns campaign truth.
cmo/ owns agent behavior.
web/ becomes a shell, not a place where every feature gets hardcoded.
```

This prevents the API dump monolith from returning.

## System Architecture / Behavior Violation Indicators

Use these as warning signs that the architecture is drifting away from the Agentic Development Map.

### Ownership Violations

* A central orchestrator knows the internal mechanics of a capability.
* A tool layer performs work that the actual tool/capability should own.
* A plugin/channel owns authoritative product state directly instead of writing through the Campaign-owned row contract.
* Deleting a removable capability folder does not remove the capability.
* A domain concept is scattered across routers, services, schemas, tests, UI, and plugins with no single owner.
* A refactor makes a file look lean by moving mixed responsibilities into a differently named runtime/helper file without returning operations to their true owners.
* A caller/orchestrator manually operates the internals of a tool instead of calling the tool and letting the tool own its behavior.

### Campaign V2 Database-First Violations

* CMO chat treats `campaign_json`, memory snapshots, daily briefs, report JSON, run traces, chat history, working context, or prose summaries as campaign truth.
* A value that CMO/operator/dashboard must filter, sort, compare, verify, decide, or report on is stored only in JSON.
* Missing campaign data is converted into fake zero metrics.
* Campaign status is inferred from prompt context instead of canonical Campaign DB rows.
* `campaign_read` returns or feeds prose as the controlling truth instead of typed Campaign rows/fields.
* Campaign architecture discussions focus on prompt wording, tool summaries, or context shaping before confirming the canonical DB fields and transitions.
* Campaign endpoints are treated as the core model instead of transport adapters over Campaign operations such as read, create, append, patch, act, and lifecycle.
* Old Campaign compatibility homes are recreated under `api/routers/campaigns.py`, `api/schemas/campaigns.py`, `api/services/campaign_source.py`, `api/services/campaign_alignment.py`, `api/services/campaign_activations.py`, `api/routers/daily_brief.py`, `api/services/daily_brief.py`, `api/models/daily_brief.py`, or `api/campaign_memory.py` instead of letting the system fail and exposing the gap.
* New code writes to or depends on `campaign_snapshots`, `campaign_activations`, `campaigns.memory_snapshot`, or daily brief payloads as current Campaign truth instead of `campaign_rows`.
* Campaign code tries to process raw Meta, Google, retail, CRM, sales, SEO, email, or creative data. Providers/channels own processing and validation; Campaign stores the normalized daily/weekly report-sheet update.
* Campaign rows bury CMO meeting fields such as `primary_kpi`, `actual`, `reach_metric`, `engagement_metric`, `action_metric`, `efficiency_metric`, `value_metric`, `top_learning`, `recommended_action`, or `note` only in raw JSON.

### Agent Behavior Violations

* Prompt wording is used to compensate for weak state modeling.
* The agent reconstructs current truth from conversation history.
* The agent is asked to enforce deterministic rules that should live in ordinary code.
* The agent is allowed to approve or verify its own output without independent evidence.
* The agent adds special-case behavior or examples that the operator did not ask for, instead of addressing the underlying ownership/modeling problem.
* The agent claims a cleanup is complete when it only changed the appearance of the structure.
* The agent optimizes response style before validating whether the system is supplying the right authoritative truth.

### API Dump Violations

* New product/domain logic is added under `api/` because it is convenient.
* API routes become business/domain owners instead of transport adapters.
* Schemas, services, tests, and UI for one capability are spread horizontally instead of owned vertically.
* Architecture proposals default to `api/...` paths before identifying whether the owner is agent, campaign/product truth, platform, or removable plugin.
* A proposed structure invents new folders or abstractions before mapping the existing repository and current ownership failures.

### Tool Boundary Violations

* Tool descriptions become substitutes for real validation.
* Tool result summaries become substitutes for structured result contracts.
* Retrying a tool is unsafe or unclear.
* Failure is hidden behind another action instead of returned explicitly.
* A generic CMO tool layer owns validation, execution, result shaping, or credential mechanics that should belong to Campaign, Drive, Postcraft, Storyboard, Previs Motion, Meta, YouTube, or another concrete tool owner.
* The system uses the tool caller as the place to encode a tool's motor/operation instead of letting the tool own its own operation.

### Refactor Process Violations

* Moving code is mistaken for improving architecture.
* A compatibility facade is presented as a real boundary while the mixed runtime remains unchanged elsewhere.
* The existing project map and authoritative docs are not checked before proposing new structure.
* A service is restarted or changed before confirming whether the edit addresses the requested concern.
* Verification only proves that the endpoint returns `200`, not that the ownership or truth-source violation was corrected.

If one of these indicators appears, stop and identify the correct owner before adding more code.

## For Prototypes Expected to Grow Into Production Systems

## 1. Product Intent

Define the smallest useful outcome the system must produce.

* Who is it for?
* What problem does it solve?
* What observable result makes it useful?
* What is explicitly outside the current scope?

### Why

An agent cannot reliably work from ambition alone.

Statements such as “build an intelligent platform” or “create an autonomous developer” leave too much room for interpretation. The agent will fill gaps with assumptions, and those assumptions may become embedded in the product.

The product intent creates the first boundary between:

```text
what the product must become
```

and:

```text
what the agent is free to invent
```

---

## 2. Authoritative Product Truth

Identify where accepted requirements, constraints, and decisions live.

The system should distinguish between:

* approved requirements;
* current assumptions;
* proposed ideas;
* unresolved questions;
* rejected decisions.

### Why

Agent conversations contain mixed-quality information.

A conversation may include:

* temporary ideas;
* contradictory instructions;
* abandoned approaches;
* stale assumptions;
* accepted decisions.

Without an authoritative source, the agent cannot reliably determine which information controls the project.

The project must remain understandable even when:

* the conversation is lost;
* a different agent continues the work;
* a developer joins later;
* an old decision is questioned.

---

## 3. System Spine

Describe the smallest end-to-end flow through the product.

Use a simple sequence such as:

```text
input
→ interpretation
→ decision
→ action
→ result
→ feedback
```

The exact stages depend on the product.

### Why

The system spine provides a stable map before implementation expands.

Features, components, and technologies may change, but the team should always know:

* where information enters;
* where decisions occur;
* where state changes;
* where outputs are produced;
* where failures become visible.

Without a spine, teams create isolated features that work independently but do not form a coherent system.

---

## 4. Authoritative State

Define what the system must remember and where that state is stored.

Separate:

* durable product state;
* temporary execution state;
* user-provided context;
* agent working notes;
* historical records.

### Why

An agent’s context is not reliable system memory.

The agent may forget, summarize incorrectly, or receive only part of the previous interaction.

Important state must therefore exist outside the model.

The system should be able to answer:

```text
What is currently true?
```

without asking the agent to reconstruct the answer from memory.

---

## 5. State Transitions

Define how the system moves from one meaningful state to another.

A generic task flow might be:

```text
proposed
→ approved
→ active
→ implemented
→ verifying
→ accepted
```

Failure paths might include:

```text
verifying
→ rejected
→ repair
```

or:

```text
active
→ blocked
→ escalated
```

### Why

Agentic workflows often fail because state changes informally.

A task may be described as:

* almost done;
* mostly working;
* ready;
* fixed;
* complete enough.

These are interpretations, not controlled states.

Explicit transitions make progress visible and prevent incomplete work from quietly becoming accepted work.

---

## 6. Bounded Work Units

Break product growth into small capabilities with clear boundaries.

Each work unit should define:

* one objective;
* required inputs;
* permitted scope;
* prohibited scope;
* expected result;
* validation method;
* completion evidence.

### Why

The longer the task, the more assumptions the agent must preserve.

Large tasks increase the chance of:

* scope drift;
* unrelated changes;
* forgotten constraints;
* partial implementation;
* difficult rollback;
* unclear failure causes.

A bounded work unit gives the agent enough freedom to solve a problem without giving it authority over the entire system.

---

## 7. Agent Authority

Define what the agent may decide independently.

Possible permissions include:

* inspect;
* propose;
* implement;
* test;
* diagnose;
* repair;
* document.

Possible restrictions include:

* changing requirements;
* altering architecture boundaries;
* modifying protected systems;
* approving its own work;
* performing irreversible operations;
* deploying without review.

### Why

An agent should not receive more authority than the workflow can verify.

Autonomy should increase only when:

* the action is reversible;
* the result is measurable;
* the blast radius is limited;
* failure is observable;
* recovery is inexpensive.

Authority is therefore earned through control and evidence, not granted because the model appears capable.

---

## 8. Tool Boundaries

Give each tool one clear responsibility.

A tool should make explicit:

* what it reads;
* what it changes;
* what it returns;
* what permissions it requires;
* whether it is safe to retry;
* how failure is reported.

### Why

Every tool expands the agent’s decision space.

Overlapping or ambiguous tools increase the probability that the agent:

* chooses the wrong operation;
* changes more than intended;
* repeats an unsafe action;
* misinterprets a result;
* hides a failure behind another action.

The best toolset is not the largest one.

It is the smallest set that allows the required work to be completed safely.

### Tool Ownership Insight

A tool should own its own operation.

Use the hand-drill model:

```text
agent / chat loop = the hand
registry / executor = choosing the drill from the tool belt
capability / plugin = the drill
domain service = the material or state being changed
```

The hand should not open the drill and operate the motor manually.

Likewise, the agent layer should not contain the internal logic of Campaign, Drive, Postcraft, Storyboard, Previs Motion, Meta, YouTube, or any other capability.

The ownership rule is:

```text
the caller chooses the tool
the tool owns the operation
the domain owns the state
the agent owns interpretation
```

If a central agent/tool layer starts managing the internal behavior of another capability, the system has not become more agentic. It has moved domain logic into the wrong place.

---

## 9. Deterministic Core

Identify which parts of the system should never depend on model judgment.

Examples may include:

* arithmetic;
* authorization;
* schema validation;
* state transitions;
* access control;
* policy enforcement;
* retries;
* timeouts;
* acceptance rules;
* data integrity checks.

### Why

A model should be used where interpretation or judgment is necessary.

It should not replace exact logic with probabilistic behavior.

The system becomes more reliable when deterministic concerns remain ordinary software and the agent is limited to areas where uncertainty cannot be removed through rules.

---

## 10. Invariants

Define conditions that must never become false.

Generic examples:

* protected state cannot change without authorization;
* accepted work must pass verification;
* one component cannot directly modify another component’s owned state;
* failures must remain reproducible;
* the same valid inputs must produce equivalent results;
* incomplete work cannot become the production baseline;
* irreversible actions require explicit approval.

### Why

Requirements describe what the product should do.

Invariants describe what the system must never violate.

Agents often solve the visible example while unintentionally breaking a broader rule.

Invariants protect the system against local fixes that create global instability.

---

## 11. Independent Verification

Separate production of an output from acceptance of that output.

Verification may include:

* automated tests;
* schema checks;
* policy checks;
* static analysis;
* contract validation;
* replay;
* comparison with known outcomes;
* human approval.

### Why

The agent that creates the output should not be the only authority deciding whether the output is correct.

The agent may provide reasoning and evidence.

The verifier decides whether the work satisfies the contract.

This creates the central control loop:

```text
agent proposes
→ verifier measures
→ control system accepts or rejects
```

---

## 12. Completion Evidence

Require every task to return observable proof.

Evidence might include:

* changed artifacts;
* test results;
* requirement coverage;
* execution logs;
* generated outputs;
* unchanged protected areas;
* known limitations;
* unresolved failures.

### Why

Statements such as these are not sufficient:

* “The task is complete.”
* “Everything works.”
* “The issue should be fixed.”

Evidence allows another system, agent, or human to inspect the result without relying on the original agent’s confidence.

Completion should be a verified state, not a narrative claim.

---

## 13. Atomic Acceptance

Only integrate work that forms a complete, validated unit.

A successful change should produce:

```text
known-good baseline
→ bounded change
→ successful verification
→ new known-good baseline
```

A failed change should produce:

```text
known-good baseline
→ failed change
→ rejection or rollback
→ known-good baseline preserved
```

### Why

Large collections of unverified changes create uncertain project state.

Atomic acceptance ensures that the system always has a recoverable point.

This becomes increasingly important as the product gains:

* more users;
* more modules;
* more developers;
* more integrations;
* more operational dependencies.

---

## 14. Reproducible Failure

When something fails, preserve the smallest reliable reproduction.

Record:

* initial state;
* inputs;
* expected result;
* observed result;
* environment;
* relevant outputs;
* attempted repairs.

### Why

A failure that cannot be reproduced cannot be reliably fixed.

Agents may otherwise repeatedly reinterpret the same problem and apply different patches.

A reproduction case turns a vague defect into durable project knowledge.

Once repaired, it becomes a regression test.

---

## 15. Bounded Repair

Use a controlled repair cycle:

```text
observe failure
→ isolate cause
→ propose smallest change
→ apply change
→ rerun targeted verification
→ rerun regression verification
```

Set limits on repeated attempts.

### Why

Unbounded retries often produce patch accumulation rather than convergence.

The agent may gradually modify more of the system until one example passes, while introducing hidden failures elsewhere.

A retry limit forces the system to recognize when the current approach is not producing reliable progress.

---

## 16. Escalation

Define when the agent must stop and request a higher level of decision.

Escalation triggers may include:

* ambiguous requirements;
* conflicting authoritative sources;
* repeated verification failure;
* protected-system changes;
* security concerns;
* irreversible operations;
* unexpected architecture impact;
* inability to reproduce a defect.

### Why

Escalation is not a workflow failure.

It is a safety mechanism for situations where the system lacks enough authority, evidence, or certainty to proceed responsibly.

A mature agentic workflow knows when not to continue.

---

## 17. Observability

Record enough of the workflow to understand what happened.

Useful observations include:

* task state;
* agent decisions;
* tools used;
* inputs retrieved;
* outputs produced;
* files changed;
* tests run;
* retries performed;
* failure causes;
* cost and duration.

### Why

Agentic systems do not always follow the same execution path.

Without observability, teams see only the final output and cannot explain:

* why the agent chose a path;
* where the failure began;
* which assumption was wrong;
* whether a retry improved the result;
* whether the workflow is becoming less reliable.

Observability turns agent behavior into an inspectable engineering process.

---

## 18. Modular Growth

As the product expands, group related capabilities behind explicit boundaries.

Each module should define:

* responsibility;
* owned state;
* public contract;
* permitted dependencies;
* failure behavior;
* verification rules;
* accountable owner.

### Why

Growth adds complexity through relationships, not merely through code volume.

Modules prevent every new capability from depending on the entire system.

Strong internal boundaries allow the product to grow while keeping changes local.

---

## 19. Compatibility

Assume that different parts of the system may evolve at different speeds.

Growth should preserve:

* backward-compatible interfaces;
* migration paths;
* version awareness;
* rollback support;
* mixed-version operation when necessary.

### Why

Small prototypes can change everything at once.

Production systems cannot.

Users, integrations, data, and dependent components may continue using older behavior while new behavior is introduced.

Compatibility allows the product to evolve without requiring coordinated replacement of the entire system.

---

## 20. Growth Triggers

Define which observations justify architectural expansion.

Possible triggers include:

* one module changes far more frequently than others;
* one capability needs independent scaling;
* different teams require independent release cycles;
* failures need stronger isolation;
* data ownership has become distinct;
* security requirements differ materially;
* deployment coordination is slowing delivery;
* operational load has become specialized.

### Why

Architecture should grow in response to measured pressure.

Without growth triggers, teams either:

* over-engineer too early; or
* remain structurally simple long after the system has outgrown its boundaries.

The system should evolve because evidence justifies the cost.

---

## 21. Controlled Distribution

A module should become an independent service only after its boundary is already clear.

A healthy progression is:

```text
capability
→ internal module
→ stable contract
→ clear data ownership
→ independent operational need
→ service extraction
```

### Why

Distribution does not create modularity.

It magnifies whatever boundaries already exist.

A weak module becomes a weak service with additional network, deployment, data, and observability problems.

Service extraction should be the result of mature boundaries, not a substitute for them.

---

## 22. Decision Records

Record decisions that are expensive to reverse.

Each record should state:

* the situation;
* the decision;
* alternatives considered;
* expected consequences;
* conditions that would justify reconsideration.

### Why

As the system grows, people forget why earlier decisions were made.

Without a record, the team may:

* repeat old debates;
* reverse decisions without understanding consequences;
* preserve outdated choices indefinitely;
* mistake temporary constraints for permanent principles.

Decision records preserve reasoning without requiring large speculative documentation.

---

## 23. Human Ownership

Every important product area should have accountable human ownership.

Humans remain responsible for:

* product intent;
* architecture boundaries;
* risk acceptance;
* security;
* irreversible actions;
* production readiness;
* client commitments;
* exceptions to policy.

### Why

Agents can accelerate engineering work, but they do not carry organizational accountability.

Ownership prevents difficult decisions from being delegated into an automated process without a responsible authority.

---

## 24. Production Readiness

Before a prototype becomes a production system, verify more than feature behavior.

Production readiness includes:

* repeatable deployment;
* rollback;
* monitoring;
* alerting;
* failure recovery;
* security controls;
* data protection;
* operational ownership;
* support procedures;
* capacity expectations;
* incident response.

### Why

A prototype proves that an idea can work.

A production system must prove that it can continue operating when:

* users make unexpected choices;
* dependencies fail;
* deployments go wrong;
* data becomes inconsistent;
* traffic increases;
* operators need to diagnose problems.

Production is an operational commitment, not merely a more polished prototype.

---

# The Agentic Development Spine

```text
PRODUCT INTENT
        ↓
AUTHORITATIVE TRUTH
        ↓
SYSTEM SPINE
        ↓
AUTHORITATIVE STATE
        ↓
EXPLICIT STATE TRANSITIONS
        ↓
BOUNDED WORK UNITS
        ↓
LIMITED AGENT AUTHORITY
        ↓
CLEAR TOOL CONTRACTS
        ↓
DETERMINISTIC CORE
        ↓
SYSTEM INVARIANTS
        ↓
INDEPENDENT VERIFICATION
        ↓
COMPLETION EVIDENCE
        ↓
ATOMIC ACCEPTANCE
        ↓
REPRODUCIBLE FAILURE
        ↓
BOUNDED REPAIR OR ESCALATION
        ↓
OBSERVABILITY
        ↓
MODULAR GROWTH
        ↓
COMPATIBILITY
        ↓
EVIDENCE-BASED EXPANSION
        ↓
PRODUCTION READINESS
```

---

# Living Documentation Protocol

Yes: this map should be treated as live documentation.

It should grow when real implementation work exposes a durable insight, invariant, failure mode, or ownership rule.

Update it when the team discovers:

* a recurring architecture mistake;
* a boundary that must be protected;
* a new invariant;
* a better ownership model;
* a failure pattern worth preventing;
* a decision that should guide future agent work.

Do not update it for every temporary idea or one-off preference. The map should capture lessons that change how the system should be built.

---

# How to Use the Map

For any new product, begin by answering these questions:

* What result must the product produce?
* Where does accepted truth live?
* What is the smallest end-to-end system flow?
* What state must survive outside the agent?
* What work can be safely bounded?
* What may the agent decide?
* What must remain deterministic?
* Which conditions must never be violated?
* How will outputs be verified?
* What evidence is required before acceptance?
* How will failure be reproduced?
* When must the agent stop?
* Which signals will justify architectural growth?
* What must be true before production use?

The concrete repository structure, tools, processes, and documentation should be derived from these answers.

The map should create the structure.

The structure should not be chosen first and justified afterward.
