# Contract: klaroha_sdk Public API (v1)

**Package**: `klaroha-sdk`
**Version**: `1.0.0`
**Stability**: v1 — all exports below are stable. Safe changes: add new exports,
add optional fields. Breaking changes require `2.0.0`.

---

## Installation

```bash
# Plugin developer (third-party repo)
pip install klaroha-sdk          # from PyPI (future)
pip install -e /path/to/bos/packages/klaroha_sdk  # local dev

# BOS container (Dockerfile)
RUN pip install -e packages/klaroha_sdk
```

---

## Exports

```python
from klaroha_sdk import (
    ChannelModule,       # base class all plugins extend
    ArtifactBlock,       # the output unit plugins return
    BridgeEnvelope,      # the input envelope plugins receive
    RunResult,           # the result plugins return from execute()
    HookPayload,         # payload passed to hook subscribers
    CredentialPayload,   # structured credential dict
    hook_subscriber,     # decorator for declaring hook handlers
)
```

---

## ChannelModule (base class)

```python
class ChannelModule:
    module_id: str                 # must match channel.json capability_ids entry
    requires_generated_image: bool = False
    requires_generated_video: bool = False

    async def execute(self, brief: dict) -> RunResult:
        """
        Main execution entry point. Receives the enriched brief (after all
        brief.before_dispatch hooks have run). Returns a RunResult.

        brief["_channel_credentials"] contains resolved credentials.
        brief["brand_name"], brief["brand_json"] contain brand context
        (populated by the system brand-scope hook subscriber).

        Do NOT import or call anything from api.* — only klaroha_sdk.
        """
        raise NotImplementedError

    def build_prompt(self, brief: dict) -> str:
        """
        Optional: build the LLM prompt from the brief.
        Default implementation renders the co-located template.j2.
        Override for custom prompt construction.
        """
        ...
```

---

## ArtifactBlock

```python
@dataclass
class ArtifactBlock:
    block_type: str
    # Common block_types: "email_draft", "image_asset", "video_asset",
    #   "pipeline_test_result", "capability_card", "setup_blocker"
    
    content: dict
    # Block-type-specific fields. email_draft example:
    # { "subject": "...", "body": "...", "to": "...", "preview_text": "..." }
    
    renderer_hint: str
    # "approval_bundle" — full Approve/Revise/Dismiss surface
    # "stream_card"     — lightweight Stream card
    # "narrative"       — text-only CMO reply segment
    # "setup_blocker"   — error/setup-required state
    
    allowed_actions: list[str]
    # Subset of: ["approve", "revise", "dismiss", "configure"]
```

---

## RunResult

```python
@dataclass
class RunResult:
    run_id: str                             # assigned by host, pass through
    status: Literal["success", "failed", "pending_review"]
    artifact_blocks: list[ArtifactBlock]
    self_check: Literal["pass", "fail"] | None = None
    error: str | None = None               # populated when status="failed"
    metadata: dict = field(default_factory=dict)
```

---

## hook_subscriber decorator

Declare a hook handler on a ChannelModule method:

```python
from klaroha_sdk import ChannelModule, HookPayload, hook_subscriber

class GmailPlugin(ChannelModule):
    module_id = "marketing.channel.gmail.outreach.draft"

    @hook_subscriber("brief.before_dispatch")
    async def inject_credentials(self, payload: HookPayload) -> HookPayload:
        """Inject Gmail credentials into the brief before dispatch."""
        creds = payload.context.get("gmail_credentials", {})
        payload.brief.setdefault("_channel_credentials", {})
        payload.brief["_channel_credentials"].update(creds)
        return payload

    async def execute(self, brief: dict) -> RunResult:
        ...
```

The host reads `hook_subscriptions` from `channel.json` and wires decorated methods
at activation time. The decorator is metadata only — it does not call the host.

---

## What plugins MUST NOT import

```python
# FORBIDDEN — BOS internals not on plugin Python path
from api.routers import anything
from api.models import anything
from api.routers.runs import inject_channel_credentials
from config import get_settings
from db import get_db

# ALLOWED — only klaroha_sdk
from klaroha_sdk import ChannelModule, ArtifactBlock, RunResult, HookPayload
```
