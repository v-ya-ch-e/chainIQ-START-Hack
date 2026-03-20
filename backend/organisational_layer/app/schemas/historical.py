from decimal import Decimal
from datetime import date
from pydantic import BaseModel


class HistoricalAwardBase(BaseModel):
    award_id: str
    request_id: str
    award_date: date
    category_id: int
    country: str
    business_unit: str
    supplier_id: str
    supplier_name: str
    total_value: Decimal
    currency: str
    quantity: Decimal
    required_by_date: date
    awarded: bool
    award_rank: int
    decision_rationale: str
    policy_compliant: bool
    preferred_supplier_used: bool
    escalation_required: bool
    escalated_to: str | None
    savings_pct: Decimal
    lead_time_days: int
    risk_score_at_award: int
    notes: str | None


class HistoricalAwardOut(HistoricalAwardBase):
    model_config = {"from_attributes": True}


class HistoricalAwardListOut(BaseModel):
    items: list[HistoricalAwardOut]
    total: int
    skip: int
    limit: int
