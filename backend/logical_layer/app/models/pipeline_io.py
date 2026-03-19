"""Pydantic models for every pipeline step's input and output."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import (
    AwardData,
    ApprovalTierData,
    EscalationData,
    PricingData,
    RequestData,
    RulesData,
    SupplierData,
)


# ── Step 1: Fetch ──────────────────────────────────────────────


class FetchResult(BaseModel):
    """Output of Step 1: all data the pipeline needs."""

    request: RequestData
    compliant_suppliers: list[SupplierData] = Field(default_factory=list)
    pricing: list[PricingData] = Field(default_factory=list)
    applicable_rules: RulesData = Field(default_factory=RulesData)
    approval_tier: ApprovalTierData | None = None
    historical_awards: list[AwardData] = Field(default_factory=list)
    org_escalations: list[EscalationData] = Field(default_factory=list)


# ── Step 2: Validate ───────────────────────────────────────────


class ValidationIssue(BaseModel):
    """A single validation issue detected during Step 2."""

    issue_id: str = ""
    severity: str = "medium"
    type: str = "missing_info"
    field: str | None = None
    description: str = ""
    action_required: str = ""


class RequestInterpretation(BaseModel):
    """Structured interpretation of the request."""

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


class ValidationResult(BaseModel):
    """Output of Step 2: validation."""

    completeness: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)
    request_interpretation: RequestInterpretation = Field(default_factory=RequestInterpretation)
    llm_used: bool = False
    llm_fallback: bool = False


# ── Step 3: Filter ─────────────────────────────────────────────


class EnrichedSupplier(BaseModel):
    """Supplier enriched with pricing and metadata for downstream steps."""

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

    # Pricing fields (None if no tier matched)
    pricing_id: str | None = None
    unit_price: float | None = None
    total_price: float | None = None
    expedited_unit_price: float | None = None
    expedited_total_price: float | None = None
    standard_lead_time_days: int | None = None
    expedited_lead_time_days: int | None = None
    pricing_tier_applied: str | None = None
    has_pricing: bool = True


class FilterResult(BaseModel):
    """Output of Step 3: enriched supplier list."""

    enriched_suppliers: list[EnrichedSupplier] = Field(default_factory=list)
    suppliers_without_pricing: list[str] = Field(default_factory=list)


# ── Step 4: Compliance ─────────────────────────────────────────


class ExcludedSupplier(BaseModel):
    """Supplier excluded during compliance checks."""

    supplier_id: str
    supplier_name: str = ""
    reason: str = ""


class ComplianceResult(BaseModel):
    """Output of Step 4: compliant and excluded suppliers."""

    compliant: list[EnrichedSupplier] = Field(default_factory=list)
    excluded: list[ExcludedSupplier] = Field(default_factory=list)


# ── Step 5: Rank ───────────────────────────────────────────────


class RankedSupplier(BaseModel):
    """Supplier ranked by true cost."""

    rank: int = 0
    supplier_id: str
    supplier_name: str = ""
    preferred: bool = False
    incumbent: bool = False
    pricing_tier_applied: str | None = None
    unit_price: float | None = None
    total_price: float | None = None
    expedited_unit_price: float | None = None
    expedited_total_price: float | None = None
    standard_lead_time_days: int | None = None
    expedited_lead_time_days: int | None = None
    quality_score: int | float = 0
    risk_score: int | float = 0
    esg_score: int | float = 0
    true_cost: float | None = None
    overpayment: float | None = None
    policy_compliant: bool = True
    covers_delivery_country: bool = True
    currency: str | None = None
    recommendation_note: str = ""


class RankResult(BaseModel):
    """Output of Step 5: ranked supplier list."""

    ranked_suppliers: list[RankedSupplier] = Field(default_factory=list)
    ranking_method: str = "true_cost"


# ── Step 6: Policy ─────────────────────────────────────────────


class ApprovalThresholdEval(BaseModel):
    """Approval threshold evaluation result."""

    rule_applied: str | None = None
    basis: str | None = None
    quotes_required: int | None = None
    approvers: list[str] = Field(default_factory=list)
    deviation_approval: str | None = None
    note: str | None = None


class PreferredSupplierEval(BaseModel):
    """Preferred supplier analysis result."""

    supplier: str | None = None
    status: str | None = None
    is_preferred: bool = False
    covers_delivery_country: bool = False
    is_restricted: bool = False
    policy_note: str | None = None


class RestrictionEval(BaseModel):
    """Restriction evaluation for a single supplier."""

    restricted: bool = False
    scope: str | None = None
    note: str = ""


class RuleRef(BaseModel):
    """Reference to an applied rule."""

    rule_id: str
    rule_type: str | None = None
    rule_text: str = ""

    model_config = {"extra": "allow"}


class PolicyResult(BaseModel):
    """Output of Step 6: policy evaluation."""

    approval_threshold: ApprovalThresholdEval = Field(default_factory=ApprovalThresholdEval)
    preferred_supplier: PreferredSupplierEval = Field(default_factory=PreferredSupplierEval)
    restricted_suppliers: dict[str, RestrictionEval] = Field(default_factory=dict)
    category_rules_applied: list[RuleRef] = Field(default_factory=list)
    geography_rules_applied: list[RuleRef] = Field(default_factory=list)


# ── Step 7: Escalations ───────────────────────────────────────


class PipelineEscalation(BaseModel):
    """Escalation discovered by the pipeline (not from Org Layer)."""

    rule_id: str
    trigger: str
    escalate_to: str
    blocking: bool = True
    source: str = "pipeline"


class Escalation(BaseModel):
    """Merged escalation entry."""

    escalation_id: str = ""
    rule: str = ""
    trigger: str = ""
    escalate_to: str = ""
    blocking: bool = True
    source: str = "org_layer"


class EscalationResult(BaseModel):
    """Output of Step 7: merged escalation list."""

    escalations: list[Escalation] = Field(default_factory=list)
    has_blocking: bool = False
    blocking_count: int = 0
    non_blocking_count: int = 0


# ── Step 8: Recommendation ────────────────────────────────────


class RecommendationResult(BaseModel):
    """Output of Step 8: recommendation."""

    status: str = "cannot_proceed"
    reason: str = ""
    preferred_supplier_if_resolved: str | None = None
    preferred_supplier_rationale: str | None = None
    minimum_budget_required: float | None = None
    minimum_budget_currency: str | None = None
    confidence_score: int = 0


# ── LLM Response Models ───────────────────────────────────────


class LLMContradiction(BaseModel):
    """Single contradiction found by LLM."""

    type: str = "contradictory"
    field: str = ""
    description: str = ""
    severity: str = "high"


class LLMValidationResult(BaseModel):
    """Structured response from the LLM validation call."""

    contradictions: list[LLMContradiction] = Field(default_factory=list)
    requester_instruction: str | None = None


class LLMRecommendationText(BaseModel):
    """Structured response from the LLM recommendation call."""

    reason: str = ""
    preferred_supplier_rationale: str | None = None


class LLMIssueEnrichment(BaseModel):
    """Enriched validation issue from LLM."""

    issue_id: str = ""
    severity: str = "medium"
    description: str = ""
    action_required: str = ""


class LLMSupplierNote(BaseModel):
    """Recommendation note for a single supplier from LLM."""

    supplier_id: str = ""
    recommendation_note: str = ""


class LLMEnrichmentResult(BaseModel):
    """Structured response from the LLM enrichment call."""

    enriched_issues: list[LLMIssueEnrichment] = Field(default_factory=list)
    supplier_notes: list[LLMSupplierNote] = Field(default_factory=list)
