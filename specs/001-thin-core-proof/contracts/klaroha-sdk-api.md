# Klaroha SDK API Contract — MVP Boundary

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08

---

## Scope

This MVP requires only the stable plugin boundary needed by existing plugin modules:

```python
from klaroha_sdk import ChannelModule
```

Do not expand the SDK as part of this plugin-host MVP unless required to preserve current plugin execution.

---

## Host Primitive Boundary

This contract sits at the `inject` primitive of the BOS host contract (see BITE.md → Thin-Core Host Primitives):

```text
load → resolve → inject → dispatch → persist
                   ↑
         brief["_channel_credentials"] is assembled here
         and is the ONLY channel through which plugin modules
         receive credentials and host-provided context.
```

Plugin `module.py` files must not import BOS internals:

```text
config
db
models
auth
executor
registry
routers
settings
```

Credentials arrive through:

```python
brief["_channel_credentials"]
```

---

## Required MVP Symbol

### ChannelModule

Minimum expectations:

```python
class ChannelModule:
    id: str
    name: str
    vertical: str
    capability: str
    platform_hint: str
    template: str

    def build_prompt(self, brief: dict) -> str: ...
    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]: ...
    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]: ...
```

This preserves the current plugin execution contract.

---

## Deferred SDK Symbols

Do not require these for the plugin-host MVP:

```text
BridgeEnvelope
RunResult
ArtifactBlock
HookPayload
hook_subscriber
SDK ABI adapter types
subprocess execution APIs
```

They may be added in later specs when hooks, adapters, or sandboxing are implemented.
