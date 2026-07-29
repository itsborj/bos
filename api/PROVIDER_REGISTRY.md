# BOS Provider Registry

`ai_provider_registry.py` is the **single source of truth** for every AI provider in BOS.

All static provider facts — identity, auth method, API base URL, default model, routing flags — live here and only here. No module, plugin, or router is allowed to hardcode a provider URL, a model ID, or a credential lookup outside this registry and the credential resolution stack that sits on top of it.

---

## What belongs in the registry

| Field | Examples |
|---|---|
| `provider` | `"openai"`, `"anthropic"`, `"bytedance"` |
| `label` | Human-readable name shown in Admin UI |
| `api_key_setting` | The `Settings` attribute that holds the platform key |
| `auth_supported` | `("api_key",)` or `("api_key", "oauth")` |
| `base_url` | Full chat-completions endpoint for LLM providers |
| `header_key` / `header_prefix` | Auth header name and prefix |
| `header_version` / `version_value` | API version header (Anthropic requires this) |
| `extra_headers` | Static headers always sent (e.g. OpenRouter referer) |
| `default_model` | Fallback model ID when no override is configured |
| `dominant_text` | `True` only for first-class CMO text LLM providers |
| `order` | Sort priority in the Admin UI |

Model IDs are **not** stored here. They are fetched live from each provider's catalog at runtime via `_fetch_*_models()` in `routers/providers.py`.

---

## Credential resolution stack

Keys are never stored in code or env files by modules. The full resolution chain is:

```
Admin → AI Providers (UI)
  └─► DB: provider_keys table (encrypted BYOK key per workspace/brand)
        └─► plugin_loader.inject_channel_credentials()
              └─► brief["_channel_credentials"] injected at run time
                    └─► module reads from brief — never from os.environ directly
```

For platform-managed keys (Klaroha-hosted):

```
Settings (loaded from environment at startup)
  └─► get_platform_key(provider, settings)   ← registry lookup
        └─► cmo_providers / executor adapter
```

---

## How to use it — the right way

### Getting provider metadata

```python
from ai_provider_registry import (
    get_ai_provider,
    get_provider_api_config,
    get_default_model,
    get_platform_key,
    list_dominant_text_provider_ids,
)

cfg = get_ai_provider("anthropic")          # AIProviderConfig dataclass
api = get_provider_api_config("anthropic")  # dict ready for call_cmo()
model = get_default_model("openai")         # "gpt-4o-mini"
key = get_platform_key("gemini", settings)  # platform key or None
```

### Making LLM calls (CMO / text completions)

Use `cmo_providers.resolve_provider()` + `call_cmo()`. Do not build your own HTTP client for LLM text calls.

```python
# In a router or capability module
from routers.cmo_providers import resolve_provider, call_cmo

provider_cfg = await resolve_provider(db, workspace, settings)
response = await call_cmo(provider_cfg, messages, tools=tools)
```

### Making video/image generation calls (BytePlus ModelArk)

Use `ByteDanceAdapter` from `providers/bytedance.py`. Do not instantiate your own `httpx` or `urllib` client against ModelArk.

```python
from providers.bytedance import ByteDanceAdapter

adapter = ByteDanceAdapter(api_key)
result = await adapter.generate_video(prompt, model_id=model, ...)
```

Keys come from `brief["_channel_credentials"]`, injected by `plugin_loader` before your module's `execute_tool_result` is called. Read them from the brief — never from `os.environ` or hardcoded files.

---

## What NOT to do

```python
# ✗ hardcoded base URL
requests.post("https://api.openai.com/v1/chat/completions", ...)

# ✗ reading keys from environment directly inside a module
api_key = os.environ.get("ARK_API_KEY")

# ✗ building your own poll loop against ModelArk
urllib.request.urlopen("https://ark.ap-southeast.bytepluses.com/api/v3/...")

# ✗ new provider added anywhere except ai_provider_registry.py
PROVIDERS = {"my_provider": {"base_url": "..."}}  # in some random file
```

---

## Adding a new provider

1. Add one `AIProviderConfig` entry to `_AI_PROVIDERS` in `ai_provider_registry.py`.
2. Add a `platform_<provider>_key: str = ""` field to `api/config.py` (Settings).
3. Create `api/providers/<provider>.py` extending `OpenAICompatAdapter` or `ProviderBase`.
4. Register the adapter in `executor.py`'s provider adapter map.
5. If the provider returns models from a live catalog, add a `_fetch_<provider>_models()` function in `routers/providers.py`.
6. Do not add any credential, URL, or model ID anywhere else.

---

## Known gap — plugin video modules

`plugins/previs-motion` currently makes its own `urllib` calls to BytePlus ModelArk using keys from `brief["_channel_credentials"]`. It predates `ByteDanceAdapter`. This module must be migrated to use `ByteDanceAdapter` directly so all ModelArk calls go through the single adapter. Until that migration is done, do not introduce any additional direct-HTTP video generation calls in new plugins — use the adapter.
