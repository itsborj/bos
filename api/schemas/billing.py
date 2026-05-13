from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BillingSummary(BaseModel):
    total_runs: int
    successful_runs: int
    total_provider_cost: float
    total_sell_price: float
    total_tokens: int


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
