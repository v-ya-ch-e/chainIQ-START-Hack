"""Pydantic models for the processing pipeline request/response."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Request
# ------------------------------------------------------------------


class ProcessRequest(BaseModel):
    """Incoming payload from n8n — the minimum needed to kick off processing."""

    request_id: str = Field(
        ..., description="Purchase request ID, e.g. REQ-000004", examples=["REQ-000004"]
    )


# ------------------------------------------------------------------
# Response sub-models (mirrors example_output.json structure)
# ------------------------------------------------------------------


class RequestInterpretation(BaseModel):
    category_l1: str
    category_l2: str
    quantity: float | None
    unit_of_measure: str | None
    budget_amount: float | None
    currency: str
    delivery_country: str
    required_by_date: str | None
    days_until_required: int | None
    data_residency_required: bool
    esg_requirement: bool
    preferred_supplier_stated: str | None = None
    incumbent_supplier: str | None = None
    requester_instruction: str | None = None


class ValidationIssue(BaseModel):
    issue_id: str
    severity: str
    type: str
    description: str
    action_required: str


class Validation(BaseModel):
    completeness: str
    issues_detected: list[ValidationIssue] = []


class ApprovalThresholdEval(BaseModel):
    rule_applied: str | None = None
    basis: str | None = None
    quotes_required: int | None = None
    approvers: list[str] = []
    deviation_approval: str | None = None
    note: str | None = None


class PreferredSupplierEval(BaseModel):
    supplier: str | None = None
    status: str | None = None
    is_preferred: bool | None = None
    covers_delivery_country: bool | None = None
    is_restricted: bool | None = None
    policy_note: str | None = None


class PolicyEvaluation(BaseModel):
    approval_threshold: ApprovalThresholdEval | None = None
    preferred_supplier: PreferredSupplierEval | None = None
    restricted_suppliers: dict[str, Any] = {}
    category_rules_applied: list[Any] = []
    geography_rules_applied: list[Any] = []


class SupplierShortlistEntry(BaseModel):
    rank: int
    supplier_id: str
    supplier_name: str
    preferred: bool
    incumbent: bool
    pricing_tier_applied: str | None = None
    unit_price: float | None = None
    total_price: float | None = None
    standard_lead_time_days: int | None = None
    expedited_lead_time_days: int | None = None
    expedited_unit_price: float | None = None
    expedited_total: float | None = None
    quality_score: int | None = None
    risk_score: int | None = None
    esg_score: int | None = None
    policy_compliant: bool = True
    covers_delivery_country: bool = True
    recommendation_note: str | None = None


class SupplierExcluded(BaseModel):
    supplier_id: str
    supplier_name: str
    reason: str


class Escalation(BaseModel):
    escalation_id: str
    rule: str
    trigger: str
    escalate_to: str
    blocking: bool


class Recommendation(BaseModel):
    status: str = Field(
        ...,
        description="One of: proceed, proceed_with_conditions, cannot_proceed",
    )
    reason: str
    preferred_supplier_if_resolved: str | None = None
    preferred_supplier_rationale: str | None = None
    minimum_budget_required: float | None = None
    minimum_budget_currency: str | None = None


class AuditTrail(BaseModel):
    policies_checked: list[str] = []
    supplier_ids_evaluated: list[str] = []
    pricing_tiers_applied: str | None = None
    data_sources_used: list[str] = []
    historical_awards_consulted: bool = False
    historical_award_note: str | None = None


# ------------------------------------------------------------------
# Top-level response
# ------------------------------------------------------------------


class ProcessingResult(BaseModel):
    request_id: str
    processed_at: datetime
    request_interpretation: RequestInterpretation
    validation: Validation
    policy_evaluation: PolicyEvaluation
    supplier_shortlist: list[SupplierShortlistEntry] = []
    suppliers_excluded: list[SupplierExcluded] = []
    escalations: list[Escalation] = []
    recommendation: Recommendation
    audit_trail: AuditTrail
