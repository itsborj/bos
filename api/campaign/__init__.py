"""Campaign vertical.

Campaign is a dated database table with read/write/edit access. Reasoning,
synthesis, prompts, channel internals, and artifact lifecycle live elsewhere.
"""

from .table import Campaign, CampaignRow

__all__ = ["Campaign", "CampaignRow"]
