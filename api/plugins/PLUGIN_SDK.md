# Klaroha Specialist Plugin SDK

> **Note — `api/plugins/` is SDK examples only.**
> The directory you are reading this from (`api/plugins/`) is bundled reference code — not a plugin install location.
> Do not copy files from here to `api/plugins/` and expect them to run in production.
> **Production and staging plugins belong in `./plugins/` inside the BOS repo (`~/bos/plugins/`)**. Docker mounts this directory into the container as `/external_plugins`.
> See `specs/001-thin-core-proof/plugin-dev-onboarding.md` for the full authoring workflow.

This document is the complete contract for building a Klaroha/BOS plugin. Read it, comply with it, ship.

## Everything is a plugin

There is no special category of "built-in module" with a different contract. Every capability in BOS — whether shipped by Klaroha or installed by an operator — is a package following the same contract: `channel.json` + `SKILL.md` + `module.py`.

There are two concepts: **Core** and **Plugin**.

```text
Core    api/capabilities/workspace/, api/capabilities/onboarding/
        Auto-activate. Cannot be deactivated. CMO primitives only.
        Not what you are building.

Plugin  ./plugins/ inside the BOS repo, mounted at /external_plugins/
        Inactive until explicitly activated per brand.
        This is what you are building.
```

Klaroha's own bundled plugins (in `api/plugins/`) and your installed plugin run through exactly the same contract, the same activation system, and the same dispatch path. There is no privileged API for Klaroha packages.

**The plugin directory is the install bundle.**

The atomic unit is the directory — install it, remove it, upgrade it as one action. Capability-level `SKILL.md` files guide dispatch where the runtime/prompt system consumes them. A root-level `SKILL.md` is optional human/operator guidance unless runtime support is added later.

For BOS: when an operator installs your plugin, they get everything your capability needs in one directory. When they remove it, nothing is left behind. Design your plugin so that deleting its directory is a complete uninstall — no orphaned skills in `api/capabilities/`, no cross-plugin dependencies.

## Plugin namespace taxonomy

Your `plugin_id` in `channel.json` must follow the namespace that matches what your plugin does:

```text
channel.*        distributes or reads from an external platform (Gmail, Meta, YouTube, TikTok, LinkedIn)
analytics.*      read-only data connector — performance, audience, or search data
                 (Google Ads, Google Analytics, Search Console)
tool.*           generic cross-vertical tool — not tied to marketing distribution
                 (Google Drive, ClickUp, Google Calendar)
media.*          creative primitive generator — image or video production
creative.*       creative orchestration — blueprints, brand-locked supply chain, factory
scheduling.*     booking and calendar management
```

Use `channel.*` only if your plugin publishes or sends to an external distribution platform. Google Drive is `tool.google_drive` — it is storage infrastructure, not a distribution channel. ClickUp is `tool.clickup` — it is a project management tool. The namespace is a contract signal: it tells the CMO manifest, the Admin UI, and future plugin authors what category this package belongs to.

**Wrong:** `"plugin_id": "channel.google_drive"`
**Right:**  `"plugin_id": "tool.google_drive"`

## Job model

BOS product language is job-first. Plugins implement one or more durable CMO-facing jobs:

```text
marketing.plan
marketing.execute
marketing.optimize
```

A plugin may be vendor/platform-specific internally (Gmail, Google Ads, Shopify, custom CRM), but the owner-facing UX should remain: the CMO has specialists, specialists use tools, tools produce artifacts, the owner approves decisions, and BOS remembers what worked.

---

## How discovery works

Klaroha scans the installed plugin root at startup. In this repo, Docker mounts `./plugins/` as `/external_plugins` and sets `EXTERNAL_PLUGINS_DIR=/external_plugins`.

Bundled `api/plugins/` directories are SDK examples / deprecated first-party packages. They are **not installed plugins** and are skipped by default. Loading them requires the explicit local compatibility flag `KLAROHA_LOAD_INTERNAL_PLUGINS=true`.

This matches WordPress / VS Code style extension boundaries: core may ship examples or default packages, but the runtime plugin list comes from the install directory / registry, not from core source folders. If no plugins are installed in the external root, a restart should produce no plugin capabilities.

### UX/readiness contract

Installed plugin capabilities are the only capabilities that should appear in the runtime CMO manifest or normal Specialists UI. Do not show WordPress-style plugin capabilities before the plugin is installed, and do not show VS Code-style extension commands before the extension is enabled.

Recommended UI split:

```text
Specialists / Installed
  shows installed plugins only
  shows active/readiness/connector status per brand
  exposes configure, validate, activate, deactivate, uninstall

Marketplace / Available
  optional catalog of installable packages
  not dispatchable
  not included in the CMO capability manifest
  no RUN lines, no approval actions, no connector prompts until installed
```

A bundled SDK example under `api/plugins/` must not create a Specialist card, CMO manifest entry, setup prompt, or missing-credentials warning unless it has been installed into the external plugin root and activated. This prevents fake capabilities and noisy setup debt.

Every immediate subdirectory of the installed plugin root is one plugin. The scanner reads `channel.json` from the root of that directory, validates it, and registers all declared modules, skills, connections, and credential requirements. No restart needed if Klaroha reloads — but a full restart is required on first install unless hot reload is enabled.

Your plugin directory name is your install name. There is no copy step inside the directory.

```
./plugins/ or /external_plugins/
└── your-channel/        ← this is your plugin root
    ├── channel.json     ← must be at this exact level
    ├── capabilities/    ← your modules and skills
    ├── clients/         ← optional platform API clients
    └── adapters/        ← optional mapping/transformation layer
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
  "credential_slots": [],
  "connections": [],
  "capability_ids": []
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `plugin_id` | string | Yes | Unique dot-namespaced ID. See namespace taxonomy above. |
| `name` | string | Yes | Human-readable display name |
| `version` | string | Yes | Semver |
| `klaroha_min_version` | string | Yes | Plugin will be rejected if host version is lower |
| `capabilities_root` | string | Yes | Path to capability tree, relative to plugin root |
| `implements` | string[] | No | CMO-facing jobs: `marketing.plan`, `marketing.execute`, `marketing.optimize` |
| `specialty` | string[] | No | Specialist tags such as `paid_search`, `cold_email`, `local_seo`, `budget_efficiency` |
| `platforms` | string[] | No | Vendor/tool/platform names used behind the specialist boundary |
| `connector_protocol` | string | No | `oauth2`, `api_key`, `mcp`, `native_api`, `smtp_or_env`, etc. |
| `risk_policy` | string | No | `read_only`, `draft_only`, `read_and_draft_only`, `send_requires_explicit_approval`, etc. |
| `output_contracts` | string[] | No | Artifact/block contracts emitted by the plugin |
| `credential_slots` | object[] | No | Declarative credential requirements — see section 7 |
| `connections` | object[] | No | Plugin-owned generic OAuth2/API connection declarations for platforms not built into core |
| `capability_ids` | string[] | Yes | Every internal module ID declared in `module.py` files, listed exactly |

`capability_ids` must exactly match the `id` attribute in every `module.py`. A mismatch causes silent routing failure — the module loads but is never dispatched.

### Third-party connector model

Plugins are self-sufficient. A plugin on a new platform does not depend on the host implementing platform-specific OAuth code. Three mechanisms exist — use the one that fits:

**`requires_platform_vars`** — for any platform where the operator supplies credentials as environment variables (API keys, long-lived tokens, organization IDs). The host reads each declared var from the environment and injects it lowercased into `brief["_channel_credentials"]`. This is the correct path for a third-party plugin on a platform the host has no built-in OAuth flow for.

```json
"requires_platform_vars": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_ORGANIZATION_ID"]
```

Injected as: `creds["linkedin_access_token"]`, `creds["linkedin_organization_id"]`.

**`connections`** — for third-party plugins that need the host to run a generic OAuth2 setup flow without platform-specific core code. The plugin declares auth/token/userinfo endpoints, credential var names, scopes, and field paths; core performs generic OAuth2, stores the resulting brand-scoped `SocialConnection`, then injects credentials exactly like any other managed connection.

```json
"connections": [
  {
    "platform": "linkedin",
    "type": "oauth2",
    "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
    "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
    "scopes": ["openid", "profile", "email"],
    "client_id_var": "LINKEDIN_CLIENT_ID",
    "client_secret_var": "LINKEDIN_CLIENT_SECRET",
    "redirect_uri_var": "LINKEDIN_REDIRECT_URI",
    "userinfo_url": "https://api.linkedin.com/v2/userinfo",
    "id_path": "sub",
    "name_path": "name",
    "email_path": "email",
    "validate_capability": "marketing.channel.linkedin.connection.validate"
  }
]
```

`requires_social_connection` — for platforms where the host can already resolve a brand-scoped OAuth connection. This includes built-in managed providers and plugin-declared `connections`. The host resolves stored per-brand OAuth tokens and injects them. Declare this for every platform token your module needs at execution time.

Current project-known built-in managed social connection examples: `facebook`, `gmail`, `google_calendar`, `google_drive`, and other Google/Facebook connections already proven by the host. For a new third-party OAuth platform such as `linkedin` or `tiktok`, declare a `connections` entry first, then include that same platform in `requires_social_connection` for capabilities that need the token. Use `requires_platform_vars` instead only when the operator supplies static tokens/API keys.

Keep requirements minimal. Do not declare a plugin-level managed connection unless every active capability in that plugin needs it, or the capability can safely fail with a setup blocker. Example: a Facebook posting plugin should not require `google_drive` globally if its normal page-read/post-read/draft/publish flows only need Facebook credentials.

**Validation is the plugin's responsibility.** Declare a validation capability in your plugin (e.g. `connection.validate`) that checks injected credentials by calling the platform API. Surface the result as a `setup_blocker` or `action_result` artifact so the operator knows whether the connection is live before running downstream capabilities. Downstream capabilities must fail early with a connection/setup block when required credentials are missing; they must not perform expensive generation or publish attempts first.

The plugin owns: credential declaration, validation logic, and failure messaging.
The host owns: reading env vars, injecting into brief, rendering setup status from the validation result.

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

### Execution pattern C — image pre-generation (consume a generated image)

Use this when your module needs an image asset as part of its output (ad creative, social post with image, email header, etc.).

**How it works:** The executor detects `image_prompt` in the brief and calls `media.image.generate` before dispatching your module. The result is injected into the brief as `_image_data_b64` and `_image_mime`. Your module reads these fields — no imports, no cross-plugin calls.

**Step 1 — set `image_prompt` in your brief** (in `build_prompt` or `execute_tool_result`):

```python
def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
    # The executor pre-generates the image if image_prompt is set.
    # Set it here if not already in the brief from the CMO.
    if not brief.get("image_prompt"):
        brand = brief.get("brand_name", "the brand")
        product = brief.get("product_name", "")
        brief = {**brief, "image_prompt": f"A display ad creative for {product or brand}"}
    
    image_b64 = brief.get("_image_data_b64")  # populated by executor pre-generation
    image_mime = brief.get("_image_mime", "image/png")
    # use image_b64 in your result block
```

**Step 2 — include the image in your result block:**

```python
result_data = {
    "content": "Ad creative generated with image asset.",
    "sell_price": None,
    "block": {
        "type": "your_artifact_type",
        "image_data_b64": image_b64,
        "image_mime": image_mime,
        # ... your other fields
    }
}
```

**Rules:**
- Never import `media.image.generate` or call it directly from your module.
- If `_image_data_b64` is absent (image gen failed or not configured), handle gracefully — return a text-only artifact rather than failing.
- The executor skips pre-generation for `media.image.generate` itself (no recursion).
- Image gen credentials are separate from your plugin's credentials — no need to declare `IMAGE_GEN_API_KEY` in your `channel.json`.

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

Klaroha injects credentials into `brief["_channel_credentials"]` before calling `build_prompt` or `execute_tool_result`. Your plugin reads from this dict — it never calls `get_settings()`, queries the database, or imports BOS internals.

You declare what credentials you need in `channel.json` as `credential_slots`. The host resolves each slot generically by type. No platform-specific code lives in core; new platforms declare their own slots.

### credential_slots — declarative credential requirements

Each slot declares a `key` (the dict key your module reads), a `type` (how the host resolves it), and type-specific parameters:

```json
"credential_slots": [
  { "key": "access_token",  "type": "social_token",  "platform": "gmail" },
  { "key": "api_key",       "type": "platform_var",  "var": "MY_SERVICE_API_KEY" },
  { "key": "account_id",    "type": "brand_json_path","path": "crm_config.account_id" }
]
```

Your module reads:

```python
creds = brief.get("_channel_credentials", {})
token  = creds.get("access_token")
api_key = creds.get("api_key")
account = creds.get("account_id")
```

### Slot types

**`social_token`** — resolves a brand-scoped OAuth connection.

```json
{ "key": "access_token", "type": "social_token", "platform": "gmail" }
```

The host queries `SocialConnection(brand_id, platform)`, calls token refresh if needed, and injects:
- `creds["access_token"]` = OAuth token (your declared key)
- `creds["{platform}_page_token"]` = same token (platform-prefixed alias)
- `creds["{platform}_page_id"]` = connected page / account ID
- `creds["{platform}_page_name"]` = display name (if stored)
- `creds["{platform}_page_handle"]` = handle (if stored)

Use one `social_token` slot per OAuth platform. If your plugin connects to two platforms (e.g. Meta + Google Drive), declare two slots with different `key` values.

**`social_meta_field`** — reads a specific metadata field stored at connect time.

```json
{ "key": "drive_root_folder_id", "type": "social_meta_field", "platform": "google_drive", "field": "drive_root_folder_id" }
```

The host reads `SocialConnection.token_meta_json[field]` and injects it under your `key`. Used for platform-specific data stored during OAuth (e.g. the Drive folder an operator picked during setup).

**`platform_var`** — env var with DB-stored fallback.

```json
{ "key": "clickup_api_token", "type": "platform_var", "var": "CLICKUP_API_TOKEN" }
```

The host reads the env var first, then falls back to the DB-stored plugin var (configured in Admin UI). Injected under your declared `key`. Use this for API tokens, organization IDs, and any credentials the operator supplies as configuration rather than OAuth.

**`brand_json_path`** — reads a value from the active brand's `brand_json` at a dotted path.

```json
{ "key": "clickup_team_id", "type": "brand_json_path", "path": "pm_config.team_id" }
```

Use this for per-brand configuration stored in the brand profile — project IDs, account IDs, or any setting that varies per brand rather than per org.

**`backend_override_provider`** — resolves the AI provider configured for this module in Specialists → Configure AI.

```json
{ "key": "image_gen_provider", "type": "backend_override_provider", "module": "media.image.generate", "fallback_var": "IMAGE_GEN_PROVIDER" }
```

Use this only for capabilities where the operator selects which AI provider to use (image generation, video generation). Falls back to the `fallback_var` env var if no backend override is set.

**`backend_override_model`** — resolves the model ID configured for this module.

```json
{ "key": "image_gen_model", "type": "backend_override_model", "module": "media.image.generate" }
```

**`backend_provider_api_key`** — resolves the API key for the provider already resolved by a `backend_override_provider` slot. This is a second-pass slot — it runs after all other slots so it can read which provider was resolved.

```json
{ "key": "provider_api_key", "type": "backend_provider_api_key", "module": "media.image.generate" }
```

The `module` field must match the `module` value in the corresponding `backend_override_provider` slot.

### Credential examples from bundled plugins

OAuth platform (Gmail Auth):
```json
"credential_slots": [
  { "key": "access_token", "type": "social_token", "platform": "gmail" }
]
```

Platform API key (Google Ads):
```json
"credential_slots": [
  { "key": "google_ads_developer_token", "type": "platform_var", "var": "GOOGLE_ADS_DEVELOPER_TOKEN" },
  { "key": "google_ads_refresh_token",   "type": "platform_var", "var": "GOOGLE_ADS_REFRESH_TOKEN" }
]
```

Per-brand config path (ClickUp):
```json
"credential_slots": [
  { "key": "clickup_api_token", "type": "platform_var",    "var": "CLICKUP_API_TOKEN" },
  { "key": "clickup_team_id",   "type": "brand_json_path", "path": "pm_config.team_id" },
  { "key": "pm_list_id",        "type": "brand_json_path", "path": "pm_config.list_id" }
]
```

AI provider routing (Image generation):
```json
"credential_slots": [
  { "key": "image_gen_provider", "type": "backend_override_provider", "module": "media.image.generate", "fallback_var": "IMAGE_GEN_PROVIDER" },
  { "key": "image_gen_model",    "type": "backend_override_model",    "module": "media.image.generate" },
  { "key": "provider_api_key",   "type": "backend_provider_api_key",  "module": "media.image.generate" }
]
```

Multi-platform (Meta — Facebook + Google Drive):
```json
"credential_slots": [
  { "key": "access_token",         "type": "social_token",      "platform": "facebook" },
  { "key": "drive_access_token",   "type": "social_token",      "platform": "google_drive" },
  { "key": "drive_root_folder_id", "type": "social_meta_field", "platform": "google_drive", "field": "drive_root_folder_id" },
  { "key": "meta_app_id",          "type": "platform_var",      "var": "META_APP_ID" }
]
```

### Missing credentials

Always handle `None` gracefully. If a required credential is absent, return a `self_check` failure — do not raise.

```python
creds = brief.get("_channel_credentials", {})
if not creds.get("access_token"):
    return "fail", ["no_social_connection"]
```

### Third-party connector model

For a platform the host has no built-in OAuth flow for, declare a `connections` entry. The host performs a generic OAuth2 flow using your declared endpoints, stores the resulting brand-scoped token, and makes it available via `social_token` slots. The plugin never implements the OAuth handshake itself.

```json
"connections": [
  {
    "platform": "my_platform",
    "type": "oauth2",
    "auth_url": "https://my-platform.com/oauth/authorize",
    "token_url": "https://my-platform.com/oauth/token",
    "scopes": ["read", "write"],
    "client_id_var": "MY_PLATFORM_CLIENT_ID",
    "client_secret_var": "MY_PLATFORM_CLIENT_SECRET",
    "redirect_uri_var": "MY_PLATFORM_REDIRECT_URI",
    "userinfo_url": "https://my-platform.com/api/me",
    "id_path": "id",
    "name_path": "name",
    "email_path": "email",
    "validate_capability": "channel.my_platform.connection.validate"
  }
]
```

Then declare a `social_token` slot for that platform. The host resolves it the same way as any built-in managed connection.

The plugin owns: credential declaration, validation logic, and failure messaging.
The host owns: OAuth flow execution, token storage, token refresh, credential injection.

---

## 8. Provider registry rule — no DIY API clients

**Every AI provider call must go through the BOS provider registry and adapter stack. Never build your own HTTP client.**

`api/ai_provider_registry.py` is the single source of truth for every AI provider in BOS: base URLs, auth headers, model IDs, and credential settings all live there. The adapter classes in `api/providers/` (e.g. `ByteDanceAdapter`, `OpenAICompatAdapter`) are the only approved callers of provider APIs.

**Plugin code must:**
- Read credentials from `brief["_channel_credentials"]` — they are injected by `plugin_loader` before your module is called
- Pass those credentials to the appropriate adapter, not to a raw HTTP call
- Never read from `os.environ` directly for provider keys
- Never hardcode a provider base URL, model ID, or auth header

**Correct pattern — BytePlus/ModelArk (video/image generation):**
```python
from providers.bytedance import ByteDanceAdapter

api_key = brief["_channel_credentials"].get("ark_api_key") or brief["_channel_credentials"].get("byteplus_api_key")
adapter = ByteDanceAdapter(api_key)
result = await adapter.generate_video(prompt, model_id=model, ...)
```

**Correct pattern — CMO text completions:**
```python
from routers.cmo_providers import resolve_provider, call_cmo

provider_cfg = await resolve_provider(db, workspace, settings)
response = await call_cmo(provider_cfg, messages)
```

**Never do this:**
```python
# ✗ DIY HTTP to a provider
import urllib.request
urllib.request.urlopen("https://ark.ap-southeast.bytepluses.com/...")

# ✗ Reading provider keys from environment
api_key = os.environ.get("ARK_API_KEY")

# ✗ Hardcoded provider URL
requests.post("https://api.openai.com/v1/chat/completions", ...)
```

See `api/PROVIDER_REGISTRY.md` for the full contract, credential chain, and migration guide.

---

## 9. Compliance rules

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
10. No direct HTTP calls to AI provider APIs — use the provider registry and adapter classes

---

## 9. Self-verification checklist

Run these against Klaroha before shipping:

```bash
# Structure check
find /external_plugins/your-channel -type f | grep -v __pycache__ | sort

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

Bundled examples under `api/plugins/` — for example the Gmail outreach draft plugin — may be used as references for directory structure and file contents. They are examples, not installed runtime plugins, unless copied or packaged into the external installed plugin root and enabled by the operator.
