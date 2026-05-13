from __future__ import annotations

from klaroha_sdk import ChannelModule


class TestStubPingModule(ChannelModule):
    id = "marketing.channel.test_stub.ping"
    name = "Test Stub Ping"
    vertical = "marketing"
    capability = "marketing.channel"
    platform_hint = "test_stub"
    policy_default = "balanced"
    template = "marketing/channel/test_stub/ping/template.j2"

    def build_prompt(self, brief: dict) -> str:
        from module_base import _get_env
        return _get_env().get_template(self.template).render(**brief)

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        return ("pass", [])
