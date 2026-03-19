"""Pydantic models for the pipeline endpoints (check-compliance, evaluate-policy,
check-escalations, generate-recommendation, assemble-output, format-invalid-response,
fetch-request).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Fetch Request
# ------------------------------------------------------------------


class FetchRequestRequest(BaseModel):
    request_id: str = Field(..., description="Purchase request ID, e.g. REQ-000004")


class FetchRequestResponse(BaseModel):
    """Full request object from the Organisational Layer."""

    model_config = {"extra": "allow"}


# ------------------------------------------------------------------
# Check Compliance
# ------------------------------------------------------------------


class CheckComplianceRequest(BaseModel):
    request_data: dict[str, Any] = Field(
        ..., description="Purchase request data with at least category_l1, category_l2, delivery_countries"
    )
    suppliers: list[dict[str, Any]] = Field(
        ..., description="Supplier rows from filter-suppliers output"
    )


class ComplianceSupplierRow(BaseModel):
    """A supplier annotated with compliance result."""

    model_config = {"extra": "allow"}

    supplier_id: str
    compliance_notes: str | None = None
    exclusion_reason: str | None = None


class CheckComplianceResponse(BaseModel):
    compliant: list[dict[str, Any]]
    non_compliant: list[dict[str, Any]]
    total_checked: int
    compliant_count: int
    non_compliant_count: int


# ------------------------------------------------------------------
# Evaluate Policy
# ------------------------------------------------------------------


class EvaluatePolicyRequest(BaseModel):
    request_data: dict[str, Any] = Field(
        ..., description="Full purchase request data"
    )
    ranked_suppliers: list[dict[str, Any]] = Field(
        default=[], description="Ranked compliant suppliers from rank step"
    )
    non_compliant_suppliers: list[dict[str, Any]] = Field(
        default=[], description="Excluded suppliers from compliance check"
    )


class EvaluatePolicyResponse(BaseModel):
    approval_threshold: dict[str, Any]
    preferred_supplier: dict[str, Any]
    restricted_suppliers: dict[str, Any]
    category_rules_applied: list[dict[str, Any]]
    geography_rules_applied: list[dict[str, Any]]


# ------------------------------------------------------------------
# Check Escalations
# ------------------------------------------------------------------


class CheckEscalationsRequest(BaseModel):
    request_id: str = Field(..., description="Purchase request ID, e.g. REQ-000004")


class EscalationItem(BaseModel):
    escalation_id: str
    rule: str
    rule_label: str = ""
    trigger: str
    escalate_to: str
    blocking: bool = False
    status: str = "open"

    model_config = {"extra": "allow"}


class CheckEscalationsResponse(BaseModel):
    request_id: str
    escalations: list[dict[str, Any]]
    has_blocking: bool
    count: int


# ------------------------------------------------------------------
# Generate Recommendation
# ------------------------------------------------------------------


class GenerateRecommendationRequest(BaseModel):
    escalations: list[dict[str, Any]] = Field(
        default=[], description="Escalations from check-escalations step"
    )
    ranked_suppliers: list[dict[str, Any]] = Field(
        default=[], description="Ranked suppliers from rank step"
    )
    validation: dict[str, Any] = Field(
        default={}, description="Validation result from validate step"
    )
    request_interpretation: dict[str, Any] = Field(
        default={}, description="Request interpretation from validate step"
    )


class GenerateRecommendationResponse(BaseModel):
    status: str
    reason: str
    preferred_supplier_if_resolved: str | None = None
    preferred_supplier_rationale: str | None = None
    minimum_budget_required: float | None = None
    minimum_budget_currency: str | None = None


# ------------------------------------------------------------------
# Assemble Output
# ------------------------------------------------------------------


class AssembleOutputRequest(BaseModel):
    """All pipeline step outputs combined."""

    request_id: str = Field(..., description="Purchase request ID")
    request_data: dict[str, Any] = Field(default={}, description="Full request data")
    validation: dict[str, Any] = Field(default={}, description="Validation result")
    request_interpretation: dict[str, Any] = Field(default={}, description="Request interpretation")
    ranked_suppliers: list[dict[str, Any]] = Field(default=[], description="Ranked suppliers")
    non_compliant_suppliers: list[dict[str, Any]] = Field(default=[], description="Excluded suppliers")
    policy_evaluation: dict[str, Any] = Field(default={}, description="Policy evaluation")
    escalations: list[dict[str, Any]] = Field(default=[], description="Escalations")
    recommendation: dict[str, Any] = Field(default={}, description="Recommendation")
    historical_awards: list[dict[str, Any]] = Field(default=[], description="Historical awards (optional)")


class AssembleOutputResponse(BaseModel):
    """Complete pipeline output matching example_output.json."""

    model_config = {"extra": "allow"}

    request_id: str
    processed_at: str
    request_interpretation: dict[str, Any]
    validation: dict[str, Any]
    policy_evaluation: dict[str, Any]
    supplier_shortlist: list[dict[str, Any]]
    suppliers_excluded: list[dict[str, Any]]
    escalations: list[dict[str, Any]]
    recommendation: dict[str, Any]
    audit_trail: dict[str, Any]


# ------------------------------------------------------------------
# Format Invalid Response
# ------------------------------------------------------------------


class FormatInvalidResponseRequest(BaseModel):
    request_data: dict[str, Any] = Field(
        ..., description="Full purchase request data"
    )
    validation: dict[str, Any] = Field(
        ..., description="Validation result from validate step"
    )
    request_interpretation: dict[str, Any] = Field(
        ..., description="Request interpretation from validate step"
    )


class FormatInvalidResponseResponse(BaseModel):
    request_id: str
    processed_at: str
    status: str
    validation: dict[str, Any]
    request_interpretation: dict[str, Any]
    escalations: list[dict[str, Any]]
    recommendation: dict[str, Any]
    summary: str
