import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class CriterionIn(BaseModel):
    id: str
    field: str
    rule: str
    threshold: Any = None
    type: str = "soft"
    owner: Optional[str] = None
    severity: str = "warning"


class ScoringIn(BaseModel):
    method: str = "all_hard_must_pass"
    soft_pass_cutoff: float = 0.7


class IntentContractIn(BaseModel):
    contract_type: str = "campaign"
    version: str = "1.0.0"
    description: Optional[str] = None
    evaluator: Optional[str] = None
    criteria: list[CriterionIn] = []
    scoring: ScoringIn = ScoringIn()
    on_pass: str = "advance"
    on_fail: str = "retry"
    on_escalate: Optional[str] = None
    max_attempts: int = 3


class IntentContractOut(BaseModel):
    id: uuid.UUID
    contract_type: str
    version: str
    description: Optional[str]
    evaluator: Optional[str]
    criteria_json: list
    scoring_json: dict
    on_pass: str
    on_fail: str
    on_escalate: Optional[str]
    max_attempts: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvaluateIn(BaseModel):
    payload: dict
    overrides: Optional[dict] = None


class EvaluateOut(BaseModel):
    verdict: str
    results: list[dict]
    hard_failures: list[dict]
    soft_failures: list[dict]
