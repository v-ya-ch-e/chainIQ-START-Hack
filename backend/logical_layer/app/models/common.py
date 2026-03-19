"""Shared Pydantic models representing data from the Organisational Layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequestData(BaseModel):
    """Purchase request as returned by the Org Layer overview endpoint."""

    request_id: str
    created_at: str | None = None
    request_channel: str | None = None
    request_language: str | None = None
    business_unit: str | None = None
    country: str | None = None
    site: str | None = None
    requester_id: str | None = None
    requester_role: str | None = None
    submitted_for_id: str | None = None
    category_id: int | None = None
    category_l1: str | None = None
    category_l2: str | None = None
    title: str | None = None
    request_text: str | None = None
    currency: str | None = None
    budget_amount: str | float | None = None
    quantity: str | float | int | None = None
    unit_of_measure: str | None = None
    required_by_date: str | None = None
    preferred_supplier_mentioned: str | None = None
    incumbent_supplier: str | None = None
    contract_type_requested: str | None = None
    delivery_countries: list = Field(default_factory=list)
    data_residency_constraint: bool = False
    esg_requirement: bool = False
    status: str | None = None
    scenario_tags: list = Field(default_factory=list)

    model_config = {"extra": "allow"}


class SupplierData(BaseModel):
    """Compliant supplier from the overview endpoint."""

    supplier_id: str
    supplier_name: str = ""
    country_hq: str | None = None
    currency: str | None = None
    quality_score: int | float = 0
    risk_score: int | float = 0
    esg_score: int | float = 0
    preferred_supplier: bool = False
    data_residency_supported: bool = False
    capacity_per_month: int | None = None

    model_config = {"extra": "allow"}


class PricingData(BaseModel):
    """Pricing tier from the overview endpoint."""

    pricing_id: str | None = None
    supplier_id: str
    supplier_name: str | None = None
    category_id: int | None = None
    region: str | None = None
    currency: str | None = None
    pricing_model: str | None = None
    min_quantity: int | float = 0
    max_quantity: int | float = 999999
    unit_price: str | float = 0
    expedited_unit_price: str | float | None = None
    total_price: str | float | None = None
    expedited_total_price: str | float | None = None
    standard_lead_time_days: int | None = None
    expedited_lead_time_days: int | None = None
    moq: int | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    notes: str | None = None

    model_config = {"extra": "allow"}


class CategoryRule(BaseModel):
    """Category-specific procurement rule."""

    rule_id: str
    category_id: int | None = None
    rule_type: str | None = None
    rule_text: str = ""

    model_config = {"extra": "allow"}


class GeographyRule(BaseModel):
    """Geography-specific procurement rule."""

    rule_id: str
    country: str | None = None
    region: str | None = None
    rule_type: str | None = None
    rule_text: str = ""
    countries: list = Field(default_factory=list)
    applies_to_categories: list = Field(default_factory=list)

    model_config = {"extra": "allow"}


class RulesData(BaseModel):
    """Applicable rules bundle from the overview endpoint."""

    category_rules: list[CategoryRule] = Field(default_factory=list)
    geography_rules: list[GeographyRule] = Field(default_factory=list)


class ApprovalTierData(BaseModel):
    """Approval threshold tier from the overview endpoint."""

    threshold_id: str | None = None
    currency: str | None = None
    min_amount: str | float | None = None
    max_amount: str | float | None = None
    min_supplier_quotes: int | None = None
    policy_note: str | None = None
    managers: list[str] = Field(default_factory=list)
    deviation_approvers: list[str] = Field(default_factory=list)
    deviation_approval_required: bool = False

    # USD schema aliases
    min_value: str | float | None = None
    max_value: str | float | None = None
    quotes_required: int | None = None
    approvers: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    def get_quotes_required(self) -> int:
        """Normalize quotes_required across EUR/CHF and USD schemas."""
        return self.min_supplier_quotes or self.quotes_required or 1

    def get_approvers(self) -> list[str]:
        """Normalize approvers across schemas."""
        return self.managers or self.approvers or []

    def get_deviation_approvers(self) -> list[str]:
        """Normalize deviation approvers across schemas."""
        return self.deviation_approvers

    def get_min_amount(self) -> float:
        """Normalize min amount across schemas."""
        val = self.min_amount if self.min_amount is not None else self.min_value
        return float(val) if val is not None else 0.0

    def get_max_amount(self) -> float:
        """Normalize max amount across schemas."""
        val = self.max_amount if self.max_amount is not None else self.max_value
        return float(val) if val is not None else 999_999_999.0


class AwardData(BaseModel):
    """Historical award entry."""

    award_id: str
    request_id: str | None = None
    award_date: str | None = None
    category_id: int | None = None
    country: str | None = None
    business_unit: str | None = None
    supplier_id: str | None = None
    supplier_name: str | None = None
    total_value: str | float | None = None
    currency: str | None = None
    quantity: str | int | None = None
    required_by_date: str | None = None
    awarded: bool = False
    award_rank: int | None = None
    decision_rationale: str | None = None
    policy_compliant: bool | None = None
    preferred_supplier_used: bool | None = None
    escalation_required: bool | None = None
    escalated_to: str | None = None
    savings_pct: str | float | None = None
    lead_time_days: int | None = None
    risk_score_at_award: int | None = None
    notes: str | None = None

    model_config = {"extra": "allow"}


class EscalationData(BaseModel):
    """Escalation from the Org Layer engine."""

    rule_id: str = ""
    rule_text: str | None = None
    trigger: str = ""
    escalate_to: str = ""
    blocking: bool = True
    request_id: str | None = None

    model_config = {"extra": "allow"}
