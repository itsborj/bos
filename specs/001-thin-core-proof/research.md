# Research: Thin Core + SDK Plugin Architecture

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08

---

## Decision 1: Hook System Design

**Decision**: Simple synchronous registry — `HookRegistry` with `subscribe(event, handler)`
and `fire(event, payload)`. No external dependency (no Celery, no Redis pub/sub,
no message broker). Handlers are async callables registered at startup.

**Rationale**: The pipeline is request-scoped. Hooks fire inline within the HTTP
request lifecycle — they are not background tasks. A simple in-process registry
is sufficient, zero-dependency, and testable. External message brokers introduce
latency and operational complexity that is not needed for synchronous pipeline hooks.

**Alternatives considered**:
- Django signals (synchronous, Django-only, adds framework dependency)
- Celery tasks (async, out-of-process, overkill for inline enrichment)
- FastAPI background tasks (fire-and-forget, cannot enrich the brief synchronously)

---

## Decision 2: klaroha_sdk as a Local pip Package

**Decision**: `packages/klaroha_sdk/` in the BOS repo. Installed with
`pip install -e packages/klaroha_sdk` (editable) in development, and as a built
wheel in Docker. Third-party plugin repo installs via `pip install klaroha-sdk`
(PyPI, future) or local path reference.

**Rationale**: A Python package is the natural SDK boundary. Plugin code in a
separate repo physically cannot import BOS internals — only what `klaroha_sdk`
exports. The editable install during development means SDK changes are reflected
immediately without reinstalling.

**Alternatives considered**:
- Copying types into each plugin (no version contract, brittle)
- A separate SDK git repo (correct long-term, premature now — monorepo approach
  is faster and still produces a real package)
- FastAPI dependency injection (does not enforce boundary for plugins in a
  separate repo)

---

## Decision 3: External Plugin Directory via Volume Mount

**Decision**: Docker volume mount `~/bos-plugins:/external_plugins`. Scanner reads
`/external_plugins/` first, then `api/plugins/` (deprecated). `EXTERNAL_PLUGINS_DIR`
env var overrides the external path for non-Docker environments.

**Rationale**: Volume mount is the standard Docker pattern for injecting external
content into a container. The plugin repo on the host is a plain directory — no
sidecar, no API, no registry service needed. Deleting a plugin folder from the
host and restarting the container produces an updated manifest automatically.

**Alternatives considered**:
- Plugin registry service (correct at SaaS scale, premature for single-tenant
  self-hosted model)
- Git submodule inside BOS repo (couples plugin repo lifecycle to BOS repo)
- HTTP plugin catalog endpoint (network dependency during startup, complicates
  offline/air-gapped deploys)

---

## Decision 4: Plugin Activation State in PostgreSQL

**Decision**: New `plugin_activations` table. Columns: `plugin_id` (str),
`brand_id` (UUID, nullable — null = org-level), `status` (`active`/`inactive`/`error`),
`error_reason` (text, nullable), `activated_at` (timestamp). Only active rows
contribute to the manifest.

**Rationale**: Activation state must survive container restarts. An in-memory
registry resets on restart — plugins would silently re-activate on every boot,
removing the safety gate. PostgreSQL gives us persistence, per-brand scoping,
and a queryable audit trail.

**Alternatives considered**:
- JSON file on disk (survives restarts but is not queryable, race conditions on write)
- Environment variable list (not per-brand, not dynamic, requires restart to change)
- In-memory (resets on restart — unusable)

---

## Decision 5: First-Party System Hooks for Brand Scope + Memory

**Decision**: `api/pipeline/system_hooks.py` registers brand scoping and memory
hydration as first-party subscribers on `brief.before_dispatch`. These use the
identical hook API that third-party plugins use.

**Rationale**: Proves the hook API is sufficient for real cross-cutting concerns
from day one. If brand scoping — the most complex cross-cutting concern in the
current codebase — can be expressed as a hook subscriber, any plugin concern can
be. This is the existence proof.

**Alternatives considered**:
- Keep brand scoping in chat.py, only extract credential injection (partial win,
  core is still not thin)
- Abstract base class injection (tight coupling, not event-based)

---

## Decision 6: channel.json v2 — Additive Extension

**Decision**: Add optional fields to existing `channel.json` schema:
`sdk_version` (str), `hook_subscriptions` (list of event names),
`credential_injectors` (list of credential key names). All new fields are
optional — existing v1 plugins continue loading without changes.

**Rationale**: Additive schema evolution is the compatibility principle stated in
PROJECT_BRIEF.md v3.55. Existing internal plugins in `api/plugins/` keep working
without modification during the deprecation period. New external plugins in
`~/bos-plugins/` use v2 fields.

**Alternatives considered**:
- New `channel.json` v2 schema, v1 rejected (breaks all existing plugins instantly)
- Separate `hooks.json` file (splits plugin declaration across two files,
  complicates the scanner)

---

## Decision 7: chat.py Rewrite Boundary

**Decision**: `chat.py` is rewritten from scratch to ~150 lines. The 7-step
contract is: receive → load context → LLM call → strip directives → dispatch →
persist → return. `@klar` and `@council` command parsers stay in `chat.py` as
deterministic step-1 utilities (they are parsing, not plugin logic).

The following move OUT of `chat.py`:
- `_brand_scoped_brief()` → `system_hooks.py` subscriber on `brief.before_dispatch`
- `hydrate_memory_slots()` call → `system_hooks.py` subscriber on `brief.before_dispatch`
- `_build_system_prompt()` skill context loading → `pipeline/context.py` helper
- `_complete_cmo_messages()` LLM candidate building → `pipeline/llm.py` helper
- `inject_channel_credentials()` call → plugin hook subscriber on `brief.before_dispatch`

**Rationale**: Drawing the line at `@klar` and `@council` in core is pragmatic —
they are simple regex parsers (< 50 lines each) and routing council to a
capability is deterministic, not plugin-specific logic. Everything else is either
brand/memory concern (hooks) or plugin concern (hook subscription).

---

## Decision 8: runs.py — Targeted Extraction, Not Full Rewrite

**Decision**: `runs.py` is NOT fully rewritten. Only `inject_channel_credentials`
is removed from its call site and replaced with a `hooks.fire("brief.before_dispatch")`
call. The rest of `runs.py` remains as-is for this phase.

**Rationale**: `runs.py` contains legitimate execution logic (module routing,
upstream contract resolution, BITE envelope construction, persistence). The coupling
problem is `inject_channel_credentials` specifically. Rewriting all of `runs.py`
in the same phase as `chat.py` and `klaroha_sdk` is too much blast radius for one
branch. `runs.py` cleanup is a follow-on phase.

---

## Decision 9: gbp-completeness Replaces gmail as Second Proof Plugin

**Decision**: `~/bos-plugins/gbp-completeness/` is the second validation plugin
for this proof, not `gmail`. Gmail migration is deferred to a follow-on pass.

**Rationale**: GBP completeness is already written, already in `~/bos-plugins/`,
and uses only `klaroha_sdk` imports. It exercises the same proof paths as Gmail:
OAuth credential injection via `brief["_channel_credentials"]`, `pending_review`
status, and `approval_bundle` renderer. Critically, it is read-only — no send step,
no SMTP, no outbound network write action — making it a lower-risk architecture
proof. A `setup_blocker` artifact (when Google Business Profile is not connected)
still proves the full plugin lifecycle: load → dispatch → credential check →
artifact returned. The CMO dispatch accuracy test against Google Analytics triggers
was also a useful finding that strengthened the SKILL.md contract requirements.

**Alternatives considered**:
- Keep gmail as second proof (adds SMTP complexity, send action risk, OAuth send scopes)
- Use test_stub only (too trivial — does not prove OAuth credential injection)

---

## Decision 10: EXTERNAL_PLUGINS_PATH Must Be an Absolute Path

**Decision**: `EXTERNAL_PLUGINS_PATH` in `.env` and the `docker-compose.yml` default
must use an absolute path (e.g., `/home/ubu/bos-plugins`), not a tilde-relative path
(`~/bos-plugins`). This is a hard deployment constraint.

**Rationale**: Docker does not perform shell tilde expansion in bind mount paths.
The `~/bos-plugins` default in `docker-compose.yml` was treated literally — Docker
looked for a directory named `~` on the host, found none, and the container logged
`No external plugin root found — external plugins disabled` at every startup.
All external plugins silently failed to load. This was identified when testing GBP
dispatch: the plugin was written but never appeared in the manifest.

**Fix applied**: `docker-compose.yml` default changed to `/home/ubu/bos-plugins`;
`.env.example` and `.env` updated to use the absolute path. All deployment
documentation must specify an absolute path.

---

## Decision 11: CMO Dispatch Accuracy Degrades on Fallback LLM Models

**Decision**: The GBP SKILL.md `excluded_triggers` must explicitly enumerate
Google Analytics, Search Console, on-page SEO, and Google Ads phrases to prevent
mis-dispatch on fallback models.

**Rationale**: In live testing, the CMO dispatched Google Analytics instead of
GBP when running on `nvidia/meta/llama-3.3-70b-instruct` (Gemini was 429'd,
OpenAI was 400'd). Both plugins share similar Google OAuth credential patterns
and "google" trigger surface area. The primary Gemini model dispatches correctly;
the fallback model does not discriminate well between overlapping trigger sets.

**Fix**: Add to GBP SKILL.md `excluded_triggers`:
- `google analytics`, `ga4`, `analytics report`, `traffic data`
- `search console`, `search performance`, `indexing`
- `google ads`, `paid search`, `ad campaign`
- `tag manager`, `on-page seo`, `meta tags`, `schema markup`

This is a SKILL.md change only — no core code change required.

---

## Decision 12: SKILL.md `requires_intent` Must Use Canonical Values Only

**Decision**: External plugin SKILL.md files must use only the canonical `requires_intent` values
accepted by the `SkillManifest` Pydantic validator:
`discussion`, `generation`, `revision`, `approval`, `onboarding`, `diagnostic`, `action`, `publish`.

Any other value causes the SKILL.md to fail `model_validate()` silently — the skill is skipped
with no log output, and the capability never appears in the CMO manifest.

**Root cause**: GBP SKILL.md used `requires_intent: research` which is not in the enum.
`list_skill_manifests()` caught the validation error and silently `continue`d past the skill.
The plugin loaded successfully at the transport layer (logs showed `Plugin loaded [external]`)
but the capability was invisible to the CMO.

**Fix**: Changed `requires_intent: research` → `diagnostic` in GBP SKILL.md.

**Impact on plugin authors**: The SDK README and plugin-dev-onboarding.md must document the
allowed intent values. A future `validate` CLI could catch this at authoring time.
