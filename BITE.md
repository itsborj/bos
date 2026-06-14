# BITE Methodology — Business Implementation by Example

> **MANDATORY READING**: This file defines the BOS development methodology.  
> **REQUIRED**: Read this file before any new system update, feature build, or architectural change.

---

## The One Rule

**Generate a sample output before generating a spec.**

The output is the requirement. If asked to write a PRD or architecture doc before a sample exists and has been agreed on, stop and produce the sample first.

---

## BOS Architecture Constitution

This section is constitutional policy for BOS. If any project document, backlog item, implementation shortcut, or local convention conflicts with this section, this section wins until the human explicitly changes it.

### Prime Architecture Statement

The CMO should not be restricted by router logic. It should be guided by a live, truthful, registry-generated capability contract.

System boundary:

```text
LLM judgment decides intent.
SKILL.md declares capability contract.
BOS validates safety.
Bridge executes.
Transform produces.
Evaluate gates.
CMO explains result.
```

### Minimal Core Policy

BOS core is a BITE harness, not a channel platform and not an agent framework.

Core owns only:
1. capability discovery
2. memory/resource hydration from declared contracts
3. Bridge envelope creation and persistence
4. Transform execution orchestration
5. security, credential, and approval boundaries
6. Evaluate gates and run trace/audit persistence
7. live capability/readiness manifest generation

Core must not own channel behavior, platform routing, prompt examples for specific channels, MCP tool semantics, provider-specific workflow logic, or UI assumptions for one capability.

### Everything is a Package

There is no module concept in BOS. Everything is a package.

BOS core owns only the five host primitives (load / resolve / inject / dispatch / persist). All capability behavior — whether Klaroha-maintained or operator-installed — ships as a package following the same contract. This follows the pi.dev agent harness model: the runner stays thin; capabilities are loaded resources, not core branches.

**Why packages, not special-cased modules?**

Every org that deploys BOS will need capabilities the Klaroha team did not build. A retailer adds a Shopify connector. An agency adds a branded checklist capability. A franchise operator adds a multi-location reporting package. These should not require submitting a PR to BOS core. The package contract is the extension point — and it must be the same contract Klaroha uses internally, or third-party packages become second-class citizens that lag every core change.

This also means Klaroha's own built-in capabilities are replaceable. If an org has a better planning module, they install it with the same module ID and it takes precedence. Core does not protect its own packages.

**Two concepts, one contract: Core and Plugin.**

There are no tiers.

```text
Core    Location:  api/capabilities/workspace/, api/capabilities/onboarding/
        Activates: auto, org-wide, cannot be deactivated
        Contains:  CMO primitives — context loading, scope resolution, approval
                   gating, deliberation, brand setup. Without these BOS does
                   not function. Equivalent to pi.dev's Read / Write / Edit / Bash.

Plugin  Location:  api/plugins/ (bundled) or ~/bos-plugins/ (operator-installed)
        Activates: bundled plugins auto-activate org-wide; operator-installed
                   plugins require explicit per-brand activation
        Contains:  every other capability — channels, analytics, tools, media,
                   creative, and marketing skill packages
```

Both use the identical package contract. Core vs Plugin governs activation model only — not contract format, not API access, not dispatch priority.

**The BOS Core primitives:**

```text
workspace.cmo_context        context loading — what the CMO knows about the brand/workspace
workspace.scope_resolution   brand scoping — which brand is active for this conversation
workspace.approval_review    approval gate — approve / revise / dismiss artifact decisions
workspace.council            deliberation — multi-perspective reasoning for high-stakes decisions
workspace.marketing_jobs     job model — maps owner language to CMO-facing job taxonomy
onboarding.brand_setup       brand initialization — extract brand profile from supplied materials
onboarding.campaign_brand_kit  brand execution kit — visual identity, voice, campaign defaults
```

These primitives cannot be removed from a running BOS deployment. They are the reason `api/capabilities/workspace/` and `api/capabilities/onboarding/` are never treated like ordinary installed packages.

**Two source roots, one contract:**

```text
Core packages      api/capabilities/workspace/, api/capabilities/onboarding/
                   Cannot be deactivated. Always present.
Bundled plugins    api/plugins/
                   Ships with BOS. Auto-activated org-wide.
Installed plugins  ~/bos-plugins/ mounted at /external_plugins/
                   Operator-installed. Inactive until explicitly activated per brand.
```

This follows VS Code and WordPress directly. VS Code's built-in TypeScript support ships in `app/extensions/` as a standard extension package — same `package.json`, same extension API as any third-party extension, can be disabled. WordPress ships Akismet as a regular plugin — same plugin header, same hook API, can be deactivated. The package contract does not change based on who wrote it or where it ships from. The host has a loader; packages are loaded resources.

**Why per-domain skill bundles:**

Anthropic's Claude Code skills use the same SKILL.md concept. A Claude Code skill is a directory: `SKILL.md` is the entry point, and everything the capability needs — references, scripts, assets, examples — lives alongside it as siblings. The atomic unit is the directory: install, remove, or upgrade it as one action.

```text
# Claude Code skills — the reference model
summarize/
  SKILL.md         minimal frontmatter + prose instructions. That's it.

huashu-design/
  SKILL.md         entry point
  references/      knowledge files the LLM reads
  assets/          supporting media
  scripts/         executable scripts
  demos/           example outputs
```

BOS applies this directly. A plugin directory is the skill bundle. Everything the capability needs lives inside it. **The boundary of the plugin directory is the boundary of what an operator installs, removes, or upgrades.** This is the organizing principle — not namespace taxonomy alone.

When an operator deletes `api/plugins/email/`, all email capability disappears cleanly: campaign planning, draft generation, inbox intelligence, approved sends. No orphaned SKILL.md files scattered elsewhere. No partial state after removal.

This is why the marketing capabilities currently in `api/capabilities/marketing/` are migrating into their owning plugins:

```text
Current location                         → Target plugin bundle
api/capabilities/marketing/email/        → api/plugins/email/
                                           (merges: gmail + gmail-auth + email planner)
api/capabilities/marketing/seo/          → api/plugins/search-console/
                                           (data connector + SEO audit = one install)
api/capabilities/marketing/analytics/    → api/plugins/google-analytics/
                                           (GA data + GTM + tracking = one install)
api/capabilities/marketing/launch/       → api/plugins/marketing-launch/
                                           (platform-agnostic launch skill bundle)
api/capabilities/marketing/planning/     → api/plugins/marketing-planning/
                                           (platform-agnostic planning skill bundle)
```

After this consolidation, `api/capabilities/` contains only Core: `workspace/` and `onboarding/`.

**Package content:**

```text
SKILL.md         operating/activation contract — when to activate, memory slots, triggers
module.py        Transform node — capability code; imports only klaroha_sdk
channel.json     package identity, credential slots, connections, risk policy, capability IDs
template.j2      prompt or tool template
resources/       lazy references, SOPs, examples, scripts
sample/          BITE sample outputs for this capability
```

**Package namespace taxonomy:**

Every package has a dot-namespaced `plugin_id` in `channel.json`. The namespace signals what kind of package it is:

```text
workspace.*      Core: CMO primitives and pipeline contracts
onboarding.*     Core: brand initialization and setup
channel.*        Plugin: distribution — publishes or sends to an external platform
                 (Gmail, Meta, YouTube, TikTok, LinkedIn)
analytics.*      Plugin: read-only data connectors — performance, audience, search data
                 (Google Ads, Analytics, Search Console)
tool.*           Plugin: generic cross-vertical tools — not tied to marketing distribution
                 (Google Drive, ClickUp, Google Calendar)
media.*          Plugin: creative primitive generators — image and video production
creative.*       Plugin: creative orchestration, blueprints, brand-locked supply chain
scheduling.*     Plugin: booking and calendar management
```

The namespace is a human contract, not enforced by the scanner. It communicates intent: a package named `channel.meta` is a distribution channel. A package named `tool.clickup` is a cross-vertical project tool. Anyone reading the ID immediately knows what kind of capability it is.

Adding or removing a capability must not require edits to `routers/chat.py`, `skills/router.py`, `routers/runs.py`, or other core pipeline code. If a capability requires a core edit, the correct fix is a generic extension point, not capability-specific logic.

### `SKILL.md` Contract Policy

`SKILL.md` is Documentation-as-Code and is the single source of truth for CMO activation behavior.

A dispatchable skill declares:
- what it does
- when to use it
- when not to use it
- required intent class
- required memory slots
- required inputs
- related modules/capability IDs
- output contract
- quality gates
- approval/risk policy
- connector requirements when applicable

The CMO reads a registry-generated manifest derived from installed `SKILL.md` files. Chat code may enforce security boundaries, strip hidden control directives, and handle provider errors. Chat code must not second-guess the LLM with platform phrase matching or hardcoded capability rules.

### Live Manifest Policy

BOS must expose a live capability/readiness manifest generated from installed packages, not hand-written prompt text.

The manifest should answer:

```text
What can be done?
How is it invoked?
What context does it need?
What credentials/connectors are required?
Is it ready, disabled, or missing setup?
Is it read-only, write-capable, or approval-gated?
What output block/contract will it produce?
```

The CMO may answer capability questions from this manifest, but it only dispatches when the user asks it to do work.

### Artifact Taxonomy Policy

Artifacts are first-class conversation objects. Do not confuse "do not execute tools" with "do not produce artifacts."

### Workspace Artifact Plane Policy

Workspace Artifacts are the canonical artifact plane. CMO chat is the narrative/control surface, not the native artifact renderer.

Correct surface split:

```text
CMO chat      -> concise explanation + artifact reference/link
Workspace     -> canonical artifact detail, native preview, approval/revision/dismissal, system details
Stream/mobile -> feed over the same persisted artifact records
Plugin/module -> structured artifact block/native fields, validation, risk policy
```

For platform-native work, generated content must not exist only inside a chat message. Chat may mention that an artifact was created or ask which artifact to create, but final native content belongs in the persisted artifact/run result and is rendered in Workspace/Stream.

Broad sample/example requests are artifact-boundary tests:

```text
"let me see samples"       -> ask which reviewable artifact to create; no inline samples
"show me sample email"     -> dispatch installed email draft capability; no inline email body
"sample email + Google Ads"-> dispatch installed email draft; state Google Ads drafting is not installed if true; no invented ad copy
```

Forbidden in CMO chat:

```text
Subject: ...
Body: ...
Headline: ...
Description: ...
Targeting: ...
Budget: ...
Product-card copy: ...
```

unless the message is explicitly an informational capability card and not pretending to be a final platform-native artifact. When in doubt, create or reference a Workspace artifact instead of pasting native content inline.

Reference sample: `sample/workspace_artifact_plane_v1.md`.

### Capability Outcome Contract Policy

The CMO generates intent; capabilities generate artifacts; plugins enforce native platform contracts.

For platform-native work, the CMO should not freewrite final artifacts inline when an installed capability owns that artifact type. The CMO supplies a job/container with objective, audience, offer, source context, risk policy, and requested artifact type. The capability/plugin fills native fields, validates constraints, and returns a structured artifact block.

Required contract shape:

```text
CMO intent/container
- job: marketing.plan | marketing.execute | marketing.optimize
- artifact_type: capability_card | plan_artifact | draft_artifact | intelligence_artifact | action_result
- platform/specialist
- objective/source_context
- risk_policy
- required inputs, if known

Capability/plugin return
- artifact_type/block type
- native platform fields
- preview/summary
- validation/self_check
- allowed_actions
- risk/approval policy
- changed_resources for external actions
```

If the user asks for a platform artifact whose capability is not installed, the CMO must state the limitation and offer an installed alternative. It must not invent native platform content, fake proof, budgets, keywords, targeting, or action results.

`SKILL.md` is an activation contract, not an inline writing prompt for the CMO. Output formats described inside `SKILL.md` belong to the module/plugin result unless the skill is explicitly informational and non-dispatchable.

Reference sample: `sample/capability_outcome_contract_v1.md`.

BOS recognizes at least these artifact types:

```text
capability_card       # explains what a specialist can do; no tool action
plan_artifact         # strategy, sequence, budget, scope, or measurement plan
draft_artifact        # copy, creative, email, landing page, ad, or script for review
intelligence_artifact # inbox, performance, market, search, analytics, or reply signal summary
decision_artifact     # recommendation requiring approve/revise/dismiss
action_result         # result of an explicitly approved external action
```

Capability questions may produce capability cards or other explanatory artifacts. They must not produce execution artifacts, external reads/writes, failed tool-result artifacts, or approval queue items unless the user asked for that work.

Example distinction:

```text
"what can you do with email" → Email Specialist capability card; no RUN lines
"plan an email campaign"    → Email Campaign Plan artifact
"draft email 1"             → Email Draft artifact
"check replies"             → Inbox Intelligence artifact; read-only connector action
"send approved email"       → approval-gated send action result
```

### CMO-Facing Marketing Jobs Policy

BOS must not expose the corporate marketing org chart or a thousand-entry channel/task catalog as product architecture.

The durable CMO-facing marketing jobs are:

```text
marketing.plan      # decide what to do
marketing.execute   # make or prepare the work
marketing.optimize  # learn what is working and improve it
```

Channel/vendor/platform details such as Gmail, Google Ads, Search Console, Meta, Amazon PPC, GTM, or future MCP tools are specialist/plugin implementation metadata behind those jobs. Internal executable IDs may remain specific for audit and dispatch, but user-facing UX, admin IA, and capability answers should stay job-oriented.

### Lean Scope Policy

BOS scales by changing scope, not by adding product layers or capability categories.

Canonical hierarchy:

```text
Org → Brand / Client → Market Unit (optional) → Campaign
```

There is no separate Portfolio layer; the Org is the portfolio/control plane. `Market Unit` is optional and can represent a location, service area, branch, agent, office, territory, marketplace, SKU group, region, service line, or audience segment. A request remains one of the three marketing jobs with richer scope.

### Thin-Core Host Primitives

BOS core exposes exactly five host-level primitives. These are the stable, generic contracts that must not grow platform-specific branches.

```text
load      → plugin_loader           discover, validate, quarantine external plugin packages
resolve   → _resolve_brief /        assemble execution context (brand, credentials, docs)
              _brand_scoped_brief
inject    → inject_channel_         enrich brief["_channel_credentials"] before dispatch
              credentials
dispatch  → _execute_module         run module_id + brief through executor → artifact
persist   → Run / artifact storage  save result, stream event to client
```

These are the BOS execution contract in order:

```text
CMO intent
  ↓ resolve   (brand context + brief)
  ↓ inject    (credentials into brief["_channel_credentials"])
  ↓ dispatch  (module_id + brief → executor → LLM / tool)
  ↓ persist   (Run row + artifact result)
  ↓ stream    (SSE event to client)
```

**These five primitives are the stable surface area of BOS core. If new behavior cannot be expressed through load, resolve, inject, dispatch, or persist — it is a new primitive and requires an explicit constitutional decision before implementation.**

Plugin behavior arrives through `load` and changes what `dispatch` can call. It never requires changes to the dispatch contract, the persist contract, or the resolve logic.

The pi.dev corollary: add loaded resources, not core branches. The manifest tells the CMO what is available; the primitives execute it. No new primitive should be added for a specific platform, workflow, or plugin.

---

### Spec Kit Update Protocol

When BITE.md changes, spec kits must be updated before implementation continues. This is not optional and not an afterthought.

**Chain of authority — top overrides bottom:**

```text
BITE.md                                        ← constitution; always wins
  └─ PLUGIN_ARCHITECTURE_RECOMMENDATION.md    ← implementation guide; agrees with BITE
       └─ spec.md                             ← feature contract; derived from above
            ├─ plan.md                        ← design artifacts
            ├─ tasks.md                       ← actionable implementation tasks
            └─ data-model.md, contracts/      ← supporting reference artifacts
```

**Update trigger rules:**

| When this changes | Update these immediately |
|---|---|
| BITE.md — any Architecture Constitution section | spec.md FRs + SCs + Architecture Tests; tasks.md T082 checklist; CLAUDE.md if agent behavior is affected |
| BITE.md — Thin-Core Host Primitives | Any spec that touches chat.py, runs.py, executor.py, or plugin_loader.py |
| PLUGIN_ARCHITECTURE_RECOMMENDATION.md | spec.md scope and deliverables; plan.md architecture rules; research.md decisions |
| spec.md — FR or SC added or changed | tasks.md affected phase tasks; data-model.md if data shape changed |
| tasks.md — task status only | No upward propagation required |

**The verbatim-match rule:**

The architecture test checklist in `tasks.md` (T082) must be a verbatim copy of the Architecture Tests block in `spec.md`. The `spec.md` Architecture Tests must include all questions from BITE.md's Architecture Violation Test.

If any of the three diverge — stop. Update the documents before writing code.

---

### Package Policy

BOS follows the pi harness lesson: keep core small; make workflows installable, discoverable, reloadable, inspectable, and removable. There is no "module" concept — every capability is a package.

Packages are first-class extension units. They may register capabilities, connector adapters, prompt fragments, block renderers, quality gates, commands, and lifecycle hooks through stable public interfaces.

No package — including Klaroha-maintained built-in packages — may import BOS internals such as database models, settings, routers, executor internals, or private registries. Host-provided context and credentials arrive through declared contracts. The `resolve` primitive assembles everything a package needs into the brief before dispatch; packages are stateless transforms that receive a brief and return a result.

### BITE Lifecycle Hook Policy

BOS extensibility happens at generic lifecycle points, not through pipeline forks.

Core should expose stable hooks such as:

```text
capability.discovered
intent.created
bridge.before_transform
transform.before_execute
transform.after_execute
evaluate.before
evaluate.after
run.persisted
approval.requested
approval.resolved
```

A package can extend behavior by registering for these hooks. It cannot rewrite the pipeline for itself.

### MCP Policy

MCP is a connector protocol, not BOS architecture.

Correct shape:

```text
CMO → BOS capability → plugin Transform → MCP/API/OAuth connector
```

Incorrect shape:

```text
CMO → arbitrary MCP tool
```

BOS owns stable capability IDs, Intent/Bridge/Evaluate contracts, approval gates, audit trails, and credential policy. MCP tools/resources/prompts may accelerate implementation behind a capability, but they do not replace capability contracts.

### Command Policy

Commands are registered handlers, not permanent chat-router branches.

Long-term shape:

```text
@klar capabilities  → capability manifest handler
@klar reload        → capability reload handler
@klar plan          → planning capability handler
@klar evaluate      → evaluation capability handler
```

New commands should be added through a command registry or package extension point. Avoid growing `chat.py` as a command monolith.

### Pi Lessons Adopted by BOS

From the pi agent harness, BOS adopts these architectural principles:

1. **Small kernel, large extension surface** — core stays minimal; workflow opinion lives outside core.
2. **Resource loader pattern** — one loader discovers capabilities, skills, prompts, resources, connectors, and renderers.
3. **Live loaded-resource awareness** — the CMO sees what is actually installed and ready, not stale hardcoded examples.
4. **Reloadability** — skills, plugins, prompts, templates, and manifests should be reloadable without code edits.
5. **Packages over built-ins** — features that differ by workflow ship as packages.
6. **Hooks over rewrites** — extensions subscribe to lifecycle events instead of changing the pipeline.
7. **Protocol humility** — MCP, OAuth, native APIs, and local tools are implementation protocols behind BOS capabilities.
8. **No feature bloat in core** — if a feature can be a package, it should be a package.
9. **Built-in vs installed, not first-party vs third-party** — the package contract is identical for Klaroha-maintained built-in packages (`api/capabilities/`) and operator-installed packages (`~/bos-plugins/`). The only difference is source location and default activation state. This is the WordPress and VS Code model: WordPress does not have a privileged hook API for Automattic plugins; VS Code does not have a privileged extension API for Microsoft extensions. The host has a loader. Packages are loaded resources.

### Architecture Violation Test

Before merging a capability-related change, ask:

```text
Did I touch chat routing for a specific platform?
Did I add a hardcoded module ID outside tests/sample docs?
Did I require a core edit to install a workflow-specific capability?
Did I expose raw connector/tool details instead of a BOS capability?
Did I bypass Intent, Bridge, Transform, or Evaluate boundaries?
Did I build before producing/agreeing on a sample output?
Did I confuse capability artifacts with tool execution artifacts?
Did I ban artifacts when the actual problem was unrequested execution?
Did I add workflow opinion to core that could instead live in a plugin or loaded resource?
Did I add a permanent chat-router branch for plugin-specific behavior?
Did I add a new primitive beyond load / resolve / inject / dispatch / persist without a constitutional decision?
```

A “yes” means stop and redesign around a package, manifest field, hook, or generic extension point.

The last three questions apply specifically to plugin host work. Any change to `plugin_loader.py`, `capability_manifest.py`, `routers/chat.py`, `executor.py`, or `routers/runs.py` must pass all eleven checks.

### Prototype Gate Policy — Non-Negotiable

**`public/frontend-prototype.html` is the living UX contract for BOS.**

Before any new capability, UI pattern, artifact type, or CMO flow change is built or merged, the prototype must be updated to show how it appears in the actual interface. The prototype is not a deliverable or a demo — it is the agreed sample (BITE Stage 2) for every UI-visible feature.

**The rule:**

> **Update the prototype first. Build second. No exceptions.**

This applies to:
- New artifact cards in Stream or CMO (new type, new fields, new actions)
- New chat message patterns (new bubble types, attachment chips, artifact reference chips)
- New CMO input affordances (attach button, brand picker, quick commands)
- New admin pages or specialist cards
- Any change to approval flow, publishing destinations, or system detail panels

**What counts as a prototype update:**
- The prototype renders the new pattern with real-looking sample data
- The new element is visually consistent with established design tokens (see guardrails below)
- A human has seen and accepted the prototype before code implementation begins

**What does not count:**
- A description of what the UI will look like
- A Figma frame or external mockup (the prototype IS the source of truth — not Figma)
- A working implementation without a prior prototype update

**If the prototype has not been updated: do not build.** Return to BITE Stage 2. The prototype update is the Stage 2 sample for UI work.

---

### UI Design Guardrails — Enforced by Prototype

These rules are observed in `public/frontend-prototype.html` and must be maintained across all future UI work:

| Element | Rule |
|---|---|
| CMO reply bubble | Brand green left-edge accent (`var(--brand)`, 3px), white background — not full color fill |
| User (You) bubble | Coral left-edge accent (`var(--coral)`, 3px), white background — not full color fill |
| Sender dot | 6px circle matching bubble accent color; sits left of sender label |
| Attachment chips | Light surface (`bg-sub`), standard border, dark text — border-only accent, no colored fill |
| "Needs review" badge | Solid amber pill: `background:var(--amber); color:var(--brand)` — never amber text on white (light-on-light violation) |
| Artifact reference chip | `bg-sub` fill, standard border, brand-colored text — light on light is never acceptable |
| Stream artifact box (inline in CMO reply) | White card with standard border inside the bubble; forest-colored type label; "Review in Stream →" link chip |
| Approve & Publish | Separate button from plain Approve when publishing destinations are shown; `var(--forest)` background |
| System details | Collapsed by default; toggle shows artifact ID, self-check, capability |
| Light-on-light | **Never.** Any text/badge/chip must have legible contrast against its direct background |

**Color token reference:**
```
--racing-green / --brand: #0b3d2e   ← CMO accent, primary brand
--coral:                  #ef8250   ← User/You accent
--amber:                  #fcc167   ← Warning/needs-review badge background
--forest:                 #4b7c54   ← Secondary green, type labels, success states
--on-dark:                #F5F1E8   ← Text on dark backgrounds
--bg-sub:                 rgba(11,61,46,.04) ← Subtle surface tint
```

---

### Agent Self-Check Before CMO/Skill Edits

Before changing CMO behavior, `SKILL.md`, plugin activation, artifact rendering, or capability manifests, an agent must answer:

```text
1. What is the approved sample user → CMO output?
2. Is this a capability question, planning request, drafting request, diagnostic/read request, optimization request, or approved external action?
3. What artifact type should appear, if any?
4. Is a tool action allowed, or should this be a capability/plan/draft/intelligence artifact only?
5. Which SKILL.md contract owns activation?
6. Is the router still only enforcing security, not intent?
7. Has the prototype been updated to show this pattern? (UI changes only)
```

If there is no approved sample, stop at BITE Stage 2 and produce the sample first.
If the change affects any UI-visible pattern, stop until the prototype reflects it.

---

## The Five Stages

### Stage 1: Discuss
- Talk through the problem space
- Understand user intent and business need
- Identify what "good" looks like

### Stage 2: Sample
- **Generate a concrete sample output** that represents the desired end state
- This is the actual output the system should produce (not a description of it)
- Examples:
  - For an ad module: Show the actual ad copy with character counts
  - For a report: Show the actual table/chart format
  - For a skill: Show the actual activated skill text in context

### Stage 3: Agree
- Human reviews and approves the sample
- **No advancement to Stage 4 without explicit approval on the Stage 2 sample**
- If changes needed, revise sample and re-agree

### Stage 4: Reverse-Spec
- Write the specification **backwards from the approved sample**
- The sample defines the requirements, not the other way around
- Document: inputs needed, constraints observed, output format, edge cases

### Stage 5: Build
- Implement to match the approved sample
- Self-check output against the sample
- Iterate until output matches sample quality

---

## How to Use This in BOS

### Before Building Any New System Component

1. **Read this file** (BITE.md) — you must understand the methodology
2. **Find or create a sample** of what the system should output
3. **Get explicit approval** on the sample from the human
4. **Write the spec** based on the approved sample
5. **Build and validate** against the approved sample

### Examples by Component Type

| Component | Sample Format | Where to Store |
|-----------|---------------|----------------|
| Module output | Actual generated copy/table/report | `sample/` directory |
| Skill behavior | Activated skill text + example chat flow | `sample/` directory |
| API response | JSON response body | `sample/` directory |
| UI component | Rendered output screenshot or HTML | `sample/` directory |

---

## Anti-Patterns (DO NOT DO)

| Anti-Pattern | Why It's Wrong |
|--------------|-----------------|
| Writing a spec before seeing output | You're guessing what's needed |
| Building from a vague description | "Make it like X" without seeing X |
| Skipping sample approval | Building something unvalidated |
| Treating the sample as optional | The sample IS the requirement |

---

## Integration with BOS Workflow

### In CLAUDE.md (this project's instructions):
```markdown
## The One Rule (from BITE SOP)
**Generate a sample output before generating a spec.**
The output is the requirement. If asked to write a PRD or architecture doc
before a sample exists and has been agreed on, stop and produce the sample first.
The five stages: Discuss → Sample → Agree → Reverse-spec → Build.
Do not advance to stage 4 without explicit approval from the human on the stage 2 sample.
```

### In BACKLOG.md:
- New tasks should reference the sample they're based on
- Bug fixes should include a "bad sample" and "fixed sample"

### In Code Reviews:
- Ask: "What sample was this based on?"
- Validate: "Does the output match the approved sample?"

---

## Sample Storage Convention

Store samples in the `sample/` directory with clear naming:

```
sample/
  bos_v1.md                    # System shape sample
  google_ads_output_v2.md     # Approved Google Ads output sample
  twitter_ad_sample.md         # Approved Twitter ad sample
  meta_performance_table.md   # Approved Meta performance table sample
```

When updating a system component:
1. Check `sample/` for existing approved samples
2. If none exist, create one and get approval
3. Build/update to match the sample

---

**Last updated:** 2026-06-15
**Enforced from:** Phase 3 onwards
**Constitutional scope:** BITE governs both output methodology and BOS architecture boundaries.
**Violations:** Any build without an approved sample, or any capability change that bypasses the BOS Architecture Constitution, should be rolled back and restarted from Stage 2.
