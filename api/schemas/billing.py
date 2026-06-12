from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BillingSummary(BaseModel):
    total_runs: int
    successful_runs: int
    total_provider_cost: float
    total_sell_price: float
    total_tokens: int
    # Mode split keeps agency/platform spend separate from client-owned BYOK usage.
    platform_provider_cost: float = 0.0
    byok_provider_cost: float = 0.0
    oauth_provider_cost: float = 0.0
    external_provider_cost: float = 0.0
    platform_tokens: int = 0
    byok_tokens: int = 0
    oauth_tokens: int = 0
    gross_margin: float = 0.0
    missing_sell_price_runs: int = 0
    missing_sell_price_provider_cost: float = 0.0


class BillingRunItem(BaseModel):
    run_id: str
    module_id: str
    created_at: datetime
    provider: str
    model_id: str
    mode: str
    tokens_input: int
    tokens_output: int
    provider_cost: float
    sell_price: Optional[float] = None
