# Klaroha Specialist Plugin SDK

This document is the complete contract for building a Klaroha/BOS specialist plugin. Read it, comply with it, ship. No channel-specific instructions exist beyond this document.

BOS product language is job-first, not channel-first. Plugins implement one or more durable CMO-facing marketing jobs:

```text
marketing.plan
marketing.execute
marketing.optimize
```

A plugin may be channel/vendor-specific internally (Gmail, Google Ads, Search Console, Amazon PPC), but the owner-facing UX should remain: the CMO has specialists, specialists use tools, tools produce artifacts, the owner approves decisions, and BOS remembers what worked.

---

## How discovery works

Klaroha scans `api/plugins/` at startup. Every immediate subdirectory is one plugin. The scanner reads `channel.json` from the root of that directory, validates it, and registers all declared modules and skills. No restart needed if Klaroha reloads — but a full restart is required on first install.

Your plugin directory name is your install name. There is no copy step inside the directory.

```
api/plugins/
└── your-channel/        ← this is your plugin root
    ├── channel.json     ← must be at this exact level
    ├── providers/       ← your platform API code (optional)
    └── capabilities/    ← your modules and skills
```

---

## 1. channel.json — manifest contract

```json
{
  "plugin_id": "channel.your_channel",
  "name": "Your Specialist Name",
  "version": "1.0.0",
  "klaroha_min_version": "3.5",
  "capabilities_root": "capabilities/",
  "implements": ["marketing.execute"],
  "specialty": ["paid_search", "email_outreach"],
  "platforms": ["your_platform"],
  "connector_protocol": "oauth2_or_api",
  "risk_policy": "read_and_draft_only",
  "output_contracts": ["artifact_type"],
  "requires_social_connection": [],
  "requires_platform_vars": [],
  "capability_ids": []
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `plugin_id` | string | Yes | Unique dot-namespaced ID. Convention: `channel.{platform}` |
| `name` | string | Yes | Human-readable display name |
| `version` | string | Yes | Semver |
| `klaroha_min_version` | string | Yes | Plugin will be rejected if host version is lower |
| `capabilities_root` | string | Yes | Path to capability tree, relative to plugin root |
| `implements` | string[] | No | CMO-facing jobs supported: `marketing.plan`, `marketing.execute`, `marketing.optimize` |
| `specialty` | string[] | No | Specialist tags such as `paid_search`, `cold_email`, `local_seo`, `budget_efficiency` |
| `platforms` | string[] | No | Vendor/tool/platform names used behind the specialist boundary |
| `connector_protocol` | string | No | `oauth2`, `api_key`, `mcp`, `native_api`, `smtp_or_env`, etc. |
| `risk_policy` | string | No | `read_only`, `draft_only`, `read_and_draft_only`, `send_requires_explicit_approval`, etc. |
| `output_contracts` | string[] | No | Artifact/block contracts emitted by the plugin |
| `requires_social_connection` | string[] | No | Platform names. Klaroha resolves OAuth tokens per brand and injects them |
| `requires_platform_vars` | string[] | No | Env var names. Klaroha reads from host environment and injects them |
| `capability_ids` | string[] | Yes | Every internal module ID declared in `module.py` files, listed exactly |

`capability_ids` must exactly match the `id` attribute in every `module.py`. A mismatch causes silent routing failure — the module loads but is never dispatched.

---

## 2. Outcome Contract v1 — native artifacts, not inline CMO copy

Every capability must have an outcome contract. This is the boundary that prevents the CMO from freewriting final platform content and keeps artifacts native to their distribution platform.

Rule:

```text
CMO generates intent.
Capabilities generate artifacts.
Plugins enforce native platform contracts.
```

A plugin declares supported output contracts in `channel.json`:

```json
"output_contracts": ["email_draft", "google_ads_data_pull"]
```

Each capability `SKILL.md` must then document the specific contract. Important: `SKILL.md` is an activation contract for the CMO, not a prompt that tells the CMO to write the artifact inline. Output formats described in `SKILL.md` belong to the module/plugin result.

```yaml
output_contract:
  - email_draft
quality_gates:
  - native_fields_present
  - no_fake_proof
  - approval_policy_present
metadata:
  implements: marketing.execute
  artifact_type: draft_artifact
  platform: gmail
  risk_policy: draft_only_until_approved
```

The CMO supplies an intent/container through the normal brief/context path:

```json
{
  "job": "marketing.execute",
  "artifact_type": "email_draft",
  "platform": "gmail",
  "objective": "draft a follow-up email",
  "audience": "high-value service business owner",
  "source_context": "user asked for a sample email",
  "risk_policy": "draft_only_until_approved"
}
```

The capability/plugin must return a structured block with native fields:

```json
{
  "type": "email_draft",
  "platform": "gmail",
  "subject": "Turn inquiries into conversations",
  "preview_text": "A concise follow-up for prospects exploring demand capture.",
  "body": "...",
  "cta": "Would you be open to a quick call?",
  "allowed_actions": ["revise", "dismiss", "approve", "send_test"],
  "risk_policy": "draft_only_until_approved"
}
```

For read-only connectors:

```json
{
  "type": "google_ads_data_pull",
  "platform": "google_ads",
  "customer_id": "3421112541",
  "date_range": "LAST_30_DAYS",
  "campaigns": [],
  "read_only": true,
  "changed_resources": []
}
```

### Outcome contract rules

- The CMO visible reply should summarize intent/result; final native content belongs in the returned artifact block.
- CMO chat renders artifact references only. Native previews, approval controls, and revisions belong to Workspace Artifacts and Stream, using the persisted run/artifact ID.
- Broad sample/example requests must not be satisfied by inline CMO prose. If the request is ambiguous, the CMO should ask which reviewable artifact to create. If it names this plugin's installed artifact type, the CMO dispatches the plugin and links the Workspace artifact.
- If the user asks for a platform output that is not installed, the CMO should state the limitation and offer an installed alternative.
- Read-only capabilities must not fabricate draft, publish, budget, status, or optimization outputs.
- Draft capabilities must not claim sends/publishes happened.
- Write/action capabilities must return `changed_resources` and require explicit approval policy.
- Self-check must validate native required fields and risk boundaries.
- Do not invent proof, customer results, discounts, budgets, targeting, or performance claims unless provided in approved context or API data.

Reference BITE sample: `sample/capability_outcome_contract_v1.md`.

---

## 3. Capability directory structure

Each capability is one directory. The path encodes the module ID.

```
capabilities/
└── {vertical}/
    └── channel/
        └── {platform}/
            └── {task}/
                └── {variant}/
                    ├── module.py
                    ├── template.j2
                    └── SKILL.md
```

Path convention may remain platform-specific internally for audit/dispatch stability:

```text
capabilities/marketing/channel/{platform}/{task}/{variant}/
```

However, do not expose these internal IDs as the product architecture. The plugin manifest declares which CMO-facing job(s) the specialist implements, while `module.py` IDs remain execution details.

Example:
```text
capabilities/marketing/channel/linkedin/organic/post/
→ internal module id: marketing.channel.linkedin.organic.post
→ implements: marketing.execute
```

---

## 4. module.py — module contract

### Minimal required attributes

```python
from klaroha_sdk import ChannelModule

class YourModule(ChannelModule):
    id = "marketing.channel.your_channel.task.variant"  # must match channel.json
    name = "Human Readable Name"
    vertical = "marketing"
    capability = "marketing.copywriting"   # see capability keys below
    platform_hint = "your_channel"
    template = "marketing/channel/your_channel/task/variant/template.j2"

    max_chars = 0          # 0 = no limit
    must_mention = []      # brief field names whose values must appear in output
    banned_phrases = []    # strings that must not appear in output

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        # your validation logic
        return ("fail" if failures else "pass"), failures
```

### Registered capability keys

Use the key that matches the type of work your module does:

| Key | Use for |
|---|---|
| `marketing.copywriting` | Any text generation: posts, emails, ads, scripts |
| `marketing.analytics` | Reports, performance summaries, data interpretation |
| `marketing.campaign` | Campaign planning, structure, strategy outputs |

If none fit, use `marketing.copywriting` as the default.

### Execution pattern A — LLM generation (default)

Klaroha renders your template via `build_prompt`, routes it through a provider LLM, and stores the result. Use this for content generation.

Override `build_prompt` only if you need to inject credentials or extra context into the template:

```python
def build_prompt(self, brief: dict) -> str:
    creds = brief.get("_channel_credentials", {})
    context = dict(brief)
    context["api_key"] = creds.get("your_platform_api_key", "")
    from module_base import _get_env
    return _get_env().get_template(self.template).render(**context)
```

`from module_base import _get_env` is the only internal import allowed, and only inside `build_prompt`.

### Execution pattern B — direct tool execution (bypass LLM)

Use this when your module calls an external API directly rather than generating text. Klaroha detects `execute_tool_result` on the class and skips the provider waterfall entirely.

```python
def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
    creds = brief.get("_channel_credentials", {})
    start = time.perf_counter()

    # your API call here
    result = your_api.do_something(creds.get("access_token"), brief)

    latency_ms = round((time.perf_counter() - start) * 1000)

    attempt_data = {
        "provider": "your_channel",
        "model_id": "api_v1",
        "mode": "tool",
        "status": "succeeded",
        "tokens_input": 0,
        "tokens_output": 0,
        "provider_cost": 0.0,
        "latency_ms": latency_ms,
        "error": None,
    }

    result_data = {
        "content": "Human-readable summary of what happened",
        "sell_price": None,
        "block": {
            # structured data for frontend rendering
            # shape is yours to define per module
        }
    }

    return attempt_data, result_data
```

`self_check` still runs after `execute_tool_result`. It receives `result_data["content"]` as the `content` argument.

### self_check rules

- Never raise an exception. Catch everything and append to failures.
- Return exactly `("pass", [])` or `("fail", ["reason_code", ...])`.
- Reason codes are dot-free strings: `missing_subject_line`, `exceeds_max_chars`, `api_call_failed`.

---

## 5. template.j2 — template contract

Used only with execution pattern A. Jinja2 template rendered with the full brief dict as context.

- All variables must use `or` fallbacks: `{{ brand_name or "the company" }}`
- Do not use `{% raw %}...{% endraw %}` — it disables all variable substitution
- Path in `module.py` is relative to `capabilities_root`, not the plugin root

```jinja2
You are a {{ platform }} copywriter for {{ brand_name or "the company" }}.

Write a {{ task_type or "post" }} for {{ audience or "general audience" }}.

...
```

---

## 6. SKILL.md — skill contract

One `SKILL.md` per module. Controls when the CMO activates the skill and dispatches the module.

```yaml
---
id: marketing.channel.your_channel.task.variant   # must match module id
name: your-channel-task
description: <one-line inline string — no YAML block scalar, no multiline>
scope: module
status: active
version: 1.0.0
allowed_from_chat: true
requires_intent:
  - generation
triggers:
  - your channel name
  - action phrases the CMO would say
excluded_triggers:
  - phrases that should NOT trigger this skill
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.your_channel.task.variant
quality_gates:
  - your_check_name
metadata:
  version: 1.0.0
  author: your-name
  plugin_id: channel.your_channel
---

## Body

Explain when to activate, when not to activate, and the output contract.
```

`description` must be a single inline string. Do not use `>` or `|` YAML block scalars — the parser does not support them.

For empty list fields (`excluded_triggers`, `memory_slots`, `quality_gates`, etc.), omit the key entirely rather than writing `key: []`. The frontmatter parser does not handle inline `[]` — it is passed as a literal string, which fails Pydantic validation and silently drops the skill from discovery.

`triggers` drive CMO intent matching. Be specific. Broad triggers like "write" or "create" conflict with first-party skills.

---

## 7. Credential injection contract

Klaroha injects credentials into `brief["_channel_credentials"]` before calling `build_prompt` or `execute_tool_result`. Your plugin reads from this dict — it never calls `get_settings()` or queries the database.

### Social connection credentials

Declared via `requires_social_connection` in `channel.json`. Klaroha resolves stored OAuth tokens per brand.

```python
creds = brief.get("_channel_credentials", {})

# First declared platform — convenience aliases
page_token = creds.get("page_token")
page_id = creds.get("page_id")

# By platform name — when multiple platforms declared
fb_token = creds.get("facebook_page_token")
fb_page = creds.get("facebook_page_id")
```

### Platform var credentials

Declared via `requires_platform_vars` in `channel.json`. Env var names are lowercased as dict keys.

```python
# channel.json: "requires_platform_vars": ["TWITTER_API_KEY"]
api_key = creds.get("twitter_api_key")
```

### Missing credentials

Always handle `None` gracefully. If a required credential is absent, return a `self_check` failure — do not raise.

```python
if not creds.get("page_token"):
    return "fail", ["no_social_connection"]
```

---

## 8. Compliance rules

A plugin is compliant if all of the following are true:

1. `channel.json` is valid JSON and passes schema validation
2. Every ID in `capability_ids` matches the `id` in a `module.py` exactly
3. `module.py` imports only `from klaroha_sdk import ChannelModule` at module level
4. `from module_base import _get_env` is used only inside an overridden `build_prompt`, nowhere else
5. No import of `config`, `db`, `models`, `auth`, `executor`, `registry`, or any router
6. `self_check` never raises — all exceptions caught
7. `template.j2` does not contain `{% raw %}` or `{% endraw %}`
8. `SKILL.md` description is an inline string — no YAML block scalar
9. `execute_tool_result` returns both `attempt_data` and `result_data` dicts with all required keys

---

## 9. Self-verification checklist

Run these against Klaroha before shipping:

```bash
# Structure check
find api/plugins/your-channel -type f | grep -v __pycache__ | sort

# Plugin discovered
docker compose exec api python -c "
from plugin_loader import scan_plugins
print([p.manifest.plugin_id for p in scan_plugins()])
"

# Module registered
docker compose exec api python -c "
from plugin_loader import scan_plugins; scan_plugins()
from registry import get_module
print(get_module('your.module.id'))
"

# Template renders (pattern A only)
docker compose exec api python -c "
from plugin_loader import scan_plugins; scan_plugins()
from registry import get_module
m = get_module('your.module.id')()
prompt = m.build_prompt({'product_name': 'Test', '_channel_credentials': {}})
assert '{{' not in prompt, 'unrendered variables'
print('OK')
"

# self_check
docker compose exec api python -c "
from plugin_loader import scan_plugins; scan_plugins()
from registry import get_module
m = get_module('your.module.id')()
v, f = m.self_check('your valid output', {'product_name': 'Test'})
print(v, f)
"

# Skill registered and activatable from chat
docker compose exec api python -c "
from registry import _scan; _scan()
from skills.loader import get_skill
s = get_skill('your.module.id')
assert s is not None, 'skill not found — check SKILL.md scope and status fields'
assert s.allowed_from_chat, 'allowed_from_chat is false'
print('skill OK:', s.id, s.scope)
"
```

All checks must pass before the plugin is considered integrated.

---

## Reference implementation

`api/plugins/gmail/` — Gmail outreach draft plugin (v0.1). LLM generation pattern, single module, credential injection via `requires_platform_vars`. Use as a working reference for the directory structure and file contents.
