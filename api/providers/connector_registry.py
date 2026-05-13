from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectorStatus:
    id: str
    name: str
    protocol: str
    channel: str
    status: str
    mode: str
    capabilities: tuple[str, ...]
    module_ids: tuple[str, ...]
    account_label: str | None = None
    notes: str | None = None


# Registry-driven connector catalog. Add future MCP/API connectors here or move
# this list to DB-backed integration settings when connector setup becomes UI-managed.
_CONNECTORS: tuple[ConnectorStatus, ...] = ()


def list_connector_statuses() -> tuple[ConnectorStatus, ...]:
    return _CONNECTORS


def format_connector_status_for_prompt() -> str:
    connectors = list_connector_statuses()
    if not connectors:
        return "No external connectors are registered yet."

    lines = ["Registered connector catalog:"]
    for c in connectors:
        capabilities = ", ".join(c.capabilities) or "none declared"
        modules = ", ".join(c.module_ids) or "none"
        account = f"; account: {c.account_label}" if c.account_label else ""
        notes = f"; notes: {c.notes}" if c.notes else ""
        lines.append(
            f"- {c.name} [{c.protocol}] channel={c.channel}; status={c.status}; "
            f"mode={c.mode}; capabilities={capabilities}; modules={modules}{account}{notes}"
        )
    return "\n".join(lines)
