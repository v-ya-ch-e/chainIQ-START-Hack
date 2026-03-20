"""Final pipeline output models matching example_output.json."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequestInterpretationOutput(BaseModel):
    """Output section: request_interpretation."""

    category_l1: str | None = None
    category_l2: str | None = None
    quantity: int | None = None
    unit_of_measure: str | None = None
    budget_amount: float | None = None
    currency: str | None = None
    delivery_country: str | None = None
    required_by_date: str | None = None
    days_until_required: int | None = None
    data_residency_required: bool = False
    esg_requirement: bool = False
    preferred_supplier_stated: str | None = None
    incumbent_supplier: str | None = None
    requester_instruction: str | None = None


class ValidationIssueOutput(BaseModel):
    """Single validation issue in the output."""

    issue_id: str
    severity: str
    type: str
    description: str
    action_required: str


class ValidationOutput(BaseModel):
    """Output section: validation."""

    completeness: str = "pass"
    issues_detected: list[ValidationIssueOutput] = Field(default_factory=list)
    llm_used: bool = False
    llm_fallback: bool = False


class ApprovalThresholdOutput(BaseModel):
    """Output section: policy_evaluation.approval_threshold."""

    rule_applied: str | None = None
    basis: str | None = None
    quotes_required: int | None = None
    approvers: list[str] = Field(default_factory=list)
    deviation_approval: str | None = None
    note: str | None = None


class PreferredSupplierOutput(BaseModel):
    """Output section: policy_evaluation.preferred_supplier."""

    supplier: str | None = None
    status: str | None = None
    is_preferred: bool = False
    covers_delivery_country: bool = False
    is_restricted: bool = False
    policy_note: str | None = None


class RestrictionEvalOutput(BaseModel):
    """Output section: policy_evaluation.restricted_suppliers.{key}."""

    restricted: bool = False
    note: str = ""


class PolicyEvaluationOutput(BaseModel):
    """Output section: policy_evaluation."""

    approval_threshold: ApprovalThresholdOutput = Field(default_factory=ApprovalThresholdOutput)
    preferred_supplier: PreferredSupplierOutput = Field(default_factory=PreferredSupplierOutput)
    restricted_suppliers: dict[str, RestrictionEvalOutput] = Field(default_factory=dict)
    category_rules_applied: list[dict] = Field(default_factory=list)
    geography_rules_applied: list[dict] = Field(default_factory=list)


class ExcludedSupplierOutput(BaseModel):
    """Output section: suppliers_excluded entry."""

    supplier_id: str
    supplier_name: str
    reason: str


class EscalationOutput(BaseModel):
    """Output section: escalations entry."""

    escalation_id: str
    rule: str
    trigger: str
    escalate_to: str
    blocking: bool


class RecommendationOutput(BaseModel):
    """Output section: recommendation."""

    status: str
    reason: str
    preferred_supplier_if_resolved: str | None = None
    preferred_supplier_rationale: str | None = None
    minimum_budget_required: float | None = None
    minimum_budget_currency: str | None = None
    confidence_score: int = 0
    llm_used: bool = False
    llm_fallback: bool = False


class AuditTrailOutput(BaseModel):
    """Output section: audit_trail."""

    policies_checked: list[str] = Field(default_factory=list)
    supplier_ids_evaluated: list[str] = Field(default_factory=list)
    pricing_tiers_applied: str = ""
    data_sources_used: list[str] = Field(default_factory=list)
    historical_awards_consulted: bool = False
    historical_award_note: str = ""


class PipelineOutput(BaseModel):
    """Top-level pipeline response matching example_output.json."""

    request_id: str
    processed_at: str
    run_id: str = ""
    status: str = "processed"

    request_interpretation: RequestInterpretationOutput = Field(
        default_factory=RequestInterpretationOutput
    )
    validation: ValidationOutput = Field(default_factory=ValidationOutput)
    policy_evaluation: PolicyEvaluationOutput = Field(default_factory=PolicyEvaluationOutput)
    supplier_shortlist: list[dict] = Field(default_factory=list)
    suppliers_excluded: list[ExcludedSupplierOutput] = Field(default_factory=list)
    escalations: list[EscalationOutput] = Field(default_factory=list)
    recommendation: RecommendationOutput = Field(
        default_factory=lambda: RecommendationOutput(status="cannot_proceed", reason="")
    )
    audit_trail: AuditTrailOutput = Field(default_factory=AuditTrailOutput)
