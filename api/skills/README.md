# BOS Skills

File-backed `SKILL.md` contracts define how the CMO activates expertise, hydrates workspace resources, and governs module execution. BOS aligns with the **AgentSkills specification** (progressive disclosure, SKILL.md contract, lazy resource loading) while preserving BOS-owned governance over activation, security, and module dispatch.

---

## AgentSkills Spec Alignment

BOS implements the AgentSkills progressive disclosure pattern:

1. **Discovery** — reads frontmatter/metadata only; builds the compact skill catalog at startup.
2. **Activation** — loads the full Markdown body for the smallest eligible skill node when a matching intent+trigger is found.
3. **Resource support** — lists bundled files relative to the skill directory; resources are **never** read unless explicitly needed for the active turn.
4. **Execution** — hydrates declared memory slots, compiles protected skill context, optionally dispatches `RUN:` directives, and enforces quality gates.

Activated skill context is wrapped in `<activated_skill ...>` tags with version, path, available resources, and related skills so BOS can trace, deduplicate, and preserve operating contracts during context compaction.

---

## Canonical SKILL.md Frontmatter

Every SKILL.md starts with YAML frontmatter. The full BOS-canonical field set:

```yaml
id: workspace.email_specialist         # Stable skill ID; inferred from path if omitted
name: email-specialist                # Slug-style name matching AgentSkills spec
description: Use when...              # Activation/routing contract — drives discovery and LLM routing
version: 1.0.0                        # Semantic version
status: active                        # active | experimental | deprecated
license: proprietary                  # or open-source SPDX identifier for plugins
compatibility:
  bos: ">=3.0.0"                     # BOS version constraint
metadata:
  author: BOS Core                   # or plugin developer name
  updated: "2026-05-13"              # ISO date of last meaningful change
scope: workspace                     # workspace | module | diagnostic | atomic_task | atomic_workflow | onboarding | workflow
allowed_from_chat: true              # Whether normal CMO chat may activate it
module_id: null                      # Executable module ID, or null for non-execution skills
related_modules:                     # Additional executable surfaces this skill governs
  - marketing.channel.email.draft
requires_intent:                     # Intent types required before activation
  - discussion
  - generation
triggers:                            # Cheap keyword phrase hints for the skill router
  - email
  - send an email
excluded_triggers:                   # Phrases that should route to a more specific skill
  - facebook
  - google ads
memory_slots:                        # Workspace resources to hydrate after activation
  - brand_profile
  - product_catalog
  - audience_profiles
  - campaign_brand_kit
resources:                           # Supporting files (lazy-loaded on demand)
  - references/EMAIL_JOBS.md
  - assets/sample_output.md
related_skills:                      # Explicit routing handoffs to sibling skills
  email_sequence: "email sequence drafting — multi-step nurture and cold outreach sequences"
required_context:                    # Ask only for what BOS memory does not already provide
  - campaign_goal
output_contract:                     # Expected output shape / future eval target
  - four_jobs_always_described_for_info_questions
  - draft_artifacts_go_to_workspace_not_inline
quality_gates:                       # Checks required before output is returned
  - no_inline_email_copy
  - no_automatic_send_without_approval
  - no_visible_control_directives
```

---

## Skill Directory Structure

A skill lives as a capability sub-directory under `api/capabilities/{vertical}/{domain}/`:

```
api/capabilities/workspace/
├── cmo_context/
│   ├── SKILL.md                  # Required — activation contract + full body
│   └── SYSTEM_PROMPT.md          # Optional reference resource (lazy-loaded)
├── plan_mode/
│   ├── SKILL.md
│   ├── references/
│   │   └── PLAN_FORMAT.md        # Lazy-loaded format spec
│   └── assets/
│       └── sample_plan_output.md # Few-shot sample
├── approval_review/
│   ├── SKILL.md
│   └── references/
│       └── ARTIFACT_TYPES.md     # Lazy-loaded artifact action contracts
├── email_specialist_overview/    # Full email specialist package
│   ├── SKILL.md
│   └── references/
│       └── EMAIL_JOBS.md         # Lazy-loaded four-job reference
├── cmo_artifact_boundary/
│   └── SKILL.md                  # Artifact surface enforcement skill
└── marketing_jobs/
    └── SKILL.md                  # Three-job CMO capability card skill
```

**Rules:**
- `SKILL.md` is required. Everything else is optional.
- `references/` — lazy-loaded supporting documents. Listed in `resources:` frontmatter field.
- `assets/` — few-shot examples, sample outputs. Listed in `resources:` frontmatter field.
- Resources are **never** read at startup. Load only when the skill is activated AND the resource is needed.
- Plugin skills install into `api/plugins/{plugin-name}/capabilities/` and are discovered by the same loader via `register_skill_root()`.

---

## Installed CMO Chat Skills

| ID | Name | Scope | Chat? | Purpose |
|---|---|---|---|---|
| `workspace.cmo_context` | answering-workspace-context | workspace | ✅ | Brand/project context answers + core reply contract |
| `workspace.cmo_artifact_boundary` | cmo-artifact-boundary | workspace | ✅ | Enforces no-inline-native-content rule |
| `workspace.marketing_jobs` | marketing-jobs | workspace | ✅ | Three-job capability card (Plan/Execute/Optimize) |
| `workspace.plan_mode` | cmo-strategic-planner | workspace | ❌ | `@klar plan` — omnichannel plan artifact |
| `workspace.scope_resolution` | brand-scope-resolution | workspace | ✅ | Separates conversation Brand, execution Brand, and comparison scope via hidden `SCOPE:` directive |
| `workspace.approval_review` | reviewing-and-revising-approvals | workspace | ✅ | Approval/revision round-trip |
| `workspace.email_specialist_overview` | email-specialist | workspace | ✅ | Full Email Specialist four-job package |

---

## Progressive Disclosure — What Loads When

| Stage | What is loaded | Token cost |
|---|---|---|
| Startup | `id`, `name`, `description`, `scope`, `triggers` from all SKILL.md frontmatter | ~10–20 tokens/skill |
| Intent match | Full SKILL.md body for the matched skill | <5000 tokens |
| Resource request | Named file from `references/` or `assets/` | File size only |
| Memory hydration | Declared `memory_slots` from DB | Varies |

---

## Memory Slots

Memory slots are hydrated by `skills/memory.py:hydrate_memory_slots()`. With no active Brand, hydration is workspace/org-scoped. With an active Brand, hydration is **strictly brand-scoped** and must not fall back to workspace rows, because workspace rows may belong to another Brand.

| Slot | Source with no active Brand | Source with active Brand |
|---|---|---|
| `brand_profile` | `Workspace.name` + `Workspace.brand_json` | `Brand.name` + `Brand.brand_json` |
| `product_catalog` | `Product` rows filtered by `workspace_id` | `Product` rows filtered by `brand_id` |
| `audience_profiles` | `Audience` rows filtered by `workspace_id` | `Audience` rows filtered by `brand_id` |
| `campaign_brand_kit` | Latest `WorkspaceDocument` with `doc_type=campaign_brand_kit`, filtered by `workspace_id` | Same doc type filtered by `brand_id` |
| `brand_guidelines` | `WorkspaceDocument` with `doc_type=brand_guideline`, filtered by `workspace_id` | Same doc type filtered by `brand_id` |
| `recent_approved_runs` | Approved `Run` + `RunResult` rows filtered by `workspace_id` | Approved rows filtered by `brand_id` |
| `recent_rejected_runs` | Rejected/revised `Run` + `RunResult` rows filtered by `workspace_id` | Rejected/revised rows filtered by `brand_id` |
| `current_run_result` | Run-specific review context for approval threads | Same run context filtered by `brand_id` |
| `marketing_reports` | `WorkspaceDocument` with `doc_type=marketing_report`, filtered by `workspace_id` | Same doc type filtered by `brand_id` |
| `campaign_reports` | `WorkspaceDocument` with `doc_type=campaign_report`, filtered by `workspace_id` | Same doc type filtered by `brand_id` |
| `competitor_profiles` | `WorkspaceDocument` with `doc_type=competitor_profile`, filtered by `workspace_id` | Same doc type filtered by `brand_id` |
| `industry_data` | `WorkspaceDocument` with `doc_type=industry_report`, filtered by `workspace_id` | Same doc type filtered by `brand_id` |

### Brand isolation for module execution

Memory slot hydration and module execution briefs both honor active Brand scope:

- **No active brand + no Brand rows yet** → `_resolve_brief(db, ws, overrides)` — legacy workspace-scoped identity, products, audiences
- **No active brand + Brand rows exist** → org-level only; list available Brands, do not load workspace brand facts, and do not dispatch artifact modules until `workspace.scope_resolution` produces a valid hidden `SCOPE.execution_brand`
- **Active brand set** → `_brand_scoped_brief(db, ws, brand, overrides)` — identity, products, audiences, and documents scoped to `brand.id`

`_brand_scoped_brief` must not call `_resolve_brief` first. Workspace fallback can inject another Brand's first product/audience before brand-specific rows are inspected. Any code that builds a module brief must use `_brand_scoped_brief` when `active_brand` is available.

---

## Artifact and Sample Boundary

`SKILL.md` output contracts describe module/plugin artifacts — not prose the CMO pastes into chat. If a skill owns a platform-native output (email, ad, post, plan, report, inbox readout, send result), the CMO dispatches the skill/module and Workspace renders the artifact.

Broad sample/example request handling:

| Request | Correct CMO behavior |
|---|---|
| `what can you do?` | Capability card (Plan/Execute/Optimize); no execution |
| `let me see samples` | Ask which reviewable artifact to create; no inline native samples |
| `show me a sample email` | Dispatch installed email draft capability; no inline Subject/Body |
| `show me sample Google Ads` | Dispatch draft artifact capability; no inline Headline/Description |
| `change my Google Ads budget` | State that budget changes require an approval-gated capability; do not mutate |

---

## The Governing Rule

> **Skills govern. Existing workspace resources ground. Resources support on a need-to-know basis. Modules execute. Organize by business operating function, not artifact format. Chat copy remains LLM-generated except provider failure/error handling. Platform-native artifacts render through Workspace/Stream, not inline CMO chat.**

A capability that needs different behavior must encode it in `SKILL.md` frontmatter/body and output contract. **Do not patch `routers/chat.py` or `skills/router.py` with phrase matching.**

---

## Adding a New Skill

1. Create a directory under `api/capabilities/{vertical}/{domain}/`.
2. Write `SKILL.md` with the canonical frontmatter above.
3. Add `references/` and `assets/` as needed — list them in the `resources:` field.
4. The skill is auto-discovered at next startup — no registry file to edit.
5. For plugins, call `register_skill_root()` in `registry._scan()`.
