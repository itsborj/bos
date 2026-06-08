# klaroha-sdk

SDK for building Klaroha BOS plugins. Provides the stable public interface
for third-party channel plugins. BOS internals may change — this SDK does not.

## Install

```bash
pip install -e /path/to/bos/packages/klaroha_sdk
```

## Exports

```python
from klaroha_sdk import (
    ChannelModule,       # base class — extend this
    ArtifactBlock,       # the output unit your plugin returns
    RunResult,           # the result wrapper execute() returns
    HookPayload,         # payload for hook subscribers
    CredentialPayload,   # structured credential dict
    hook_subscriber,     # decorator for hook handler methods
)
```

---

## `ChannelModule`

Base class for all plugins. Extend it and implement `execute()`.

```python
class ChannelModule:
    # Set these on your subclass:
    id: str              # must match channel.json capability_ids entry
    vertical: str        # "marketing"
    capability: str      # "marketing.execute"
    platform_hint: str   # short platform name, e.g. "gmail", "hello"

    async def execute(self, brief: dict) -> RunResult:
        """
        Called by BOS before module execution. The brief contains:
          brief["brand_name"]              — active brand name
          brief["brand_json"]              — brand settings dict
          brief["_channel_credentials"]    — resolved credentials dict

        Credential keys (populated by BOS from channel.json declarations):
          For requires_platform_vars: brief["_channel_credentials"][var.lower()]
          For requires_social_connection: brief["_channel_credentials"]["{platform}_page_token"]
                                          brief["_channel_credentials"]["page_token"]  (first platform alias)
        """
        raise NotImplementedError
```

---

## `ArtifactBlock`

The output unit. One `RunResult` can contain multiple blocks; the first is
the canonical Stream artifact.

```python
@dataclass
class ArtifactBlock:
    block_type: str          # e.g. "email_draft", "pipeline_test_result"
    content: dict            # block-specific fields — whatever your plugin outputs
    renderer_hint: str       # controls how Stream renders it (see below)
    allowed_actions: list[str]  # subset of ["approve", "revise", "dismiss", "publish_*"]
```

**`renderer_hint` values:**

| Value | Effect |
|---|---|
| `"stream_card"` | Lightweight card in Stream. No action buttons needed. |
| `"approval_bundle"` | Full Approve / Revise / Dismiss surface. Use for drafts. |
| `"narrative"` | Plain text segment added to CMO chat reply. |
| `"setup_blocker"` | Error/setup-required state card. |

---

## `RunResult`

Return this from `execute()`.

```python
@dataclass
class RunResult:
    run_id: str                                          # pass through from brief["run_id"]
    status: Literal["success", "failed", "pending_review"]
    artifact_blocks: list[ArtifactBlock]
    self_check: Literal["pass", "fail"] | None = None   # "pass" by default
    error: str | None = None                             # set when status="failed"
    metadata: dict = field(default_factory=dict)         # optional extras
```

**Status meanings:**

| Status | Effect |
|---|---|
| `"success"` | Run complete. Auto-approved in Stream if no publish action needed. |
| `"pending_review"` | Puts artifact in the operator's approval queue. |
| `"failed"` | Marks run as failed. Set `error` field. |

---

## `hook_subscriber`

Declare a method as a handler for a BOS hook event.

```python
from klaroha_sdk import ChannelModule, HookPayload, hook_subscriber

class MyPlugin(ChannelModule):
    id = "marketing.channel.myplugin.task"
    ...

    @hook_subscriber("brief.before_dispatch")
    async def inject_credentials(self, payload: HookPayload) -> HookPayload:
        # Enrich payload.brief before execute() is called.
        # payload.context is read-only.
        api_key = payload.context.get("my_api_key", "")
        payload.brief.setdefault("_channel_credentials", {})
        payload.brief["_channel_credentials"]["my_api_key"] = api_key
        return payload

    async def execute(self, brief: dict) -> RunResult:
        key = brief["_channel_credentials"].get("my_api_key")
        ...
```

Also declare the subscription in `channel.json`:
```json
"hook_subscriptions": ["brief.before_dispatch"]
```

**Hook events (v1):**

| Event | When fired | Payload mutatable? |
|---|---|---|
| `brief.before_dispatch` | Before `execute()` is called | Yes — enrich `payload.brief` |
| `run.after_complete` | After run is persisted to DB | No — react only |
| `plugin.activated` | When plugin is activated for a brand | No |
| `plugin.deactivated` | When plugin is deactivated | No |

---

## `HookPayload`

```python
@dataclass
class HookPayload:
    event: str
    brief: dict    # mutable — enrich this in brief.before_dispatch
    context: dict  # read-only — turn context (brand, workspace, credentials)
    metadata: dict
```

---

## What you MUST NOT import

```python
# These are BOS internals and are not on your plugin's Python path.
from api.routers import anything        # FORBIDDEN
from api.models import anything         # FORBIDDEN
from config import get_settings         # FORBIDDEN
from db import get_db                   # FORBIDDEN
from module_base import ModuleBase      # FORBIDDEN — use ChannelModule from SDK
```

Any import outside of `klaroha_sdk` and the Python standard library will fail
at runtime when BOS loads your plugin.

---

## Version policy

This SDK follows semantic versioning. Once a symbol is exported from `klaroha_sdk`,
it will not be removed or have its signature changed without a major version bump.
Adding new optional fields to dataclasses is a minor version change.

---

## Known gaps — coming in a future SDK release

> **Note for BOS core team:** These are blockers for third-party developer experience.
> Plugin devs currently have no way to validate their plugin without a running BOS stack.

### 1. No local test runner

There is no way to call `execute()` against a mock brief without running BOS.
The planned CLI:

```bash
klaroha-sdk run ./my-plugin/ \
  --brief '{"brand_name": "Acme", "_channel_credentials": {"page_token": "ya29.xxx"}}'
```

Should call `execute()` directly, print the `RunResult` as JSON, and exit.
This would let plugin devs iterate without a Docker stack.

### 2. No `validate` command

There is no tool to catch structural errors before BOS sees the plugin.
The planned CLI:

```bash
klaroha-sdk validate ./my-plugin/
```

Should check:
- `channel.json` parses and required fields are present
- `capability_ids` in `channel.json` matches `id` on the `ChannelModule` subclass
- `module.py` imports nothing outside `klaroha_sdk` and stdlib
- `SKILL.md` is co-located with `module.py` and has `id`, `module_id`, `allowed_from_chat`

### 3. `brief` shape is not fully documented

The `execute()` docstring covers the common keys. The full brief shape —
including what fields appear inside `brand_json`, `run_id`, `workspace_id`,
and any CMO-injected context — is not yet published.

Until it is, build defensively: always use `.get()` with a fallback,
never assume a key is present.

### 4. Supported social connections not published

Plugin devs can declare `requires_social_connection: ["google_business"]` in
`channel.json`, but there is no published list of which connection types BOS
natively supports. If you declare an unsupported platform, credentials will
never be injected and your plugin will silently receive an empty `_channel_credentials`.

A supported connections reference will be added to the plugin developer docs.
