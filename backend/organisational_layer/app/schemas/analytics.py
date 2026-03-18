from decimal import Decimal
from pydantic import BaseModel


class CompliantSupplierOut(BaseModel):
    supplier_id: str
    supplier_name: str
    country_hq: str
    currency: str
    quality_score: int
    risk_score: int
    esg_score: int
    preferred_supplier: bool
    data_residency_supported: bool


class PricingLookupOut(BaseModel):
    pricing_id: str
    supplier_id: str
    supplier_name: str
    region: str
    currency: str
    min_quantity: int
    max_quantity: int
    unit_price: Decimal
    expedited_unit_price: Decimal
    total_price: Decimal
    expedited_total_price: Decimal
    standard_lead_time_days: int
    expedited_lead_time_days: int
    moq: int


class ApprovalTierOut(BaseModel):
    threshold_id: str
    currency: str
    min_amount: Decimal
    max_amount: Decimal | None
    min_supplier_quotes: int
    policy_note: str | None
    managers: list[str]
    deviation_approvers: list[str]


class RestrictionCheckOut(BaseModel):
    supplier_id: str
    is_restricted: bool
    restriction_reason: str | None = None
    scope_values: list[str] = []


class PreferredCheckOut(BaseModel):
    supplier_id: str
    is_preferred: bool
    policy_note: str | None = None
    region_scopes: list[str] = []


class ApplicableRulesOut(BaseModel):
    category_rules: list[dict]
    geography_rules: list[dict]


class SpendByCategoryOut(BaseModel):
    category_l1: str
    category_l2: str
    total_spend: Decimal
    award_count: int
    avg_savings_pct: Decimal


class SpendBySupplierOut(BaseModel):
    supplier_id: str
    supplier_name: str
    total_spend: Decimal
    award_count: int
    avg_savings_pct: Decimal


class SupplierWinRateOut(BaseModel):
    supplier_id: str
    supplier_name: str
    total_evaluations: int
    wins: int
    win_rate: Decimal


class RequestOverviewOut(BaseModel):
    request: dict
    compliant_suppliers: list[CompliantSupplierOut]
    pricing: list[PricingLookupOut]
    applicable_rules: ApplicableRulesOut
    approval_tier: ApprovalTierOut | None
    historical_awards: list[dict]
