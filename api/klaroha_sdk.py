"""
Klaroha Channel Plugin SDK
--------------------------
The complete import surface for external channel plugin developers.

Usage in your module.py:
    from klaroha_sdk import ChannelModule

    class MyChannelModule(ChannelModule):
        id = "marketing.channel.mychannel.organic.post"
        ...

Do NOT import from any other klaroha module. This file is the stable
boundary. Everything inside klaroha may change without notice.
"""
from module_base import ModuleBase as ChannelModule

__all__ = ["ChannelModule"]
