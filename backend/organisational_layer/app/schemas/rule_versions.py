"""Pydantic schemas for rule definitions and rule versions."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RuleDefinitionOut(BaseModel):
    rule_id: str
    rule_type: str
    rule_name: str
    is_skippable: bool
    source: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RuleVersionOut(BaseModel):
    version_id: str
    rule_id: str
    version_num: int
    rule_config: dict[str, Any]
    valid_from: datetime
    valid_to: datetime | None
    changed_by: str | None
    change_reason: str | None

    model_config = {"from_attributes": True}


class RuleVersionCreate(BaseModel):
    rule_id: str
    rule_config: dict[str, Any]
    changed_by: str | None = None
    change_reason: str | None = None


class RuleVersionWithDefinitionOut(RuleVersionOut):
    rule_name: str | None = None
    rule_type: str | None = None


class RuleCheckOut(BaseModel):
    """Single rule check (hard or policy) with version traceability."""

    check_id: str
    rule_id: str
    version_id: str
    supplier_id: str | None
    result: str
    evidence: dict[str, Any] | None = None
    skipped: bool | None = None
    skip_reason: str | None = None
    checked_at: datetime

    model_config = {"from_attributes": True}


class HardRuleCheckOut(RuleCheckOut):
    """Hard rule check with full fields."""

    run_id: str | None = None
    actual_value: dict[str, Any] | None = None
    threshold: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class PolicyCheckOut(RuleCheckOut):
    """Policy check with override fields."""

    run_id: str | None = None
    override_by: str | None = None
    override_at: datetime | None = None
    override_reason: str | None = None

    model_config = {"from_attributes": True}


class PolicyCheckOverrideBody(BaseModel):
    """Payload for PATCH policy check override."""

    changed_by: str
    new_result: str  # passed, warned, failed
    override_reason: str | None = None
    new_evidence: dict[str, Any] | None = None


class EvaluationRunLogOut(BaseModel):
    log_id: str
    run_id: str
    changed_at: datetime
    changed_by: str
    change_type: str
    old_status: str | None
    new_status: str | None
    old_outcome: str | None
    new_outcome: str | None
    note: str | None

    model_config = {"from_attributes": True}


class EscalationLogOut(BaseModel):
    log_id: str
    escalation_id: str
    changed_at: datetime
    changed_by: str
    change_type: str
    field_changed: str | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    note: str | None

    model_config = {"from_attributes": True}


class PolicyChangeLogOut(BaseModel):
    log_id: str
    escalation_id: str
    changed_at: datetime
    changed_by: str
    change_type: str
    policy_rule_id: str | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    note: str | None

    model_config = {"from_attributes": True}


class PolicyCheckLogOut(BaseModel):
    log_id: str
    check_id: str
    run_id: str
    changed_at: datetime
    changed_by: str
    change_type: str
    old_result: str | None
    new_result: str | None
    override_reason: str | None

    model_config = {"from_attributes": True}


class RuleChangeLogOut(BaseModel):
    log_id: str
    rule_id: str
    old_version_id: str | None
    new_version_id: str
    changed_at: datetime
    changed_by: str
    change_reason: str | None
    affected_runs: list[str] | None

    model_config = {"from_attributes": True}


class SupplierRuleBreakdownOut(BaseModel):
    """Per-supplier breakdown of which rules passed/failed."""

    supplier_id: str
    supplier_name: str | None = None
    hard_rule_checks: list[RuleCheckOut] = []
    policy_checks: list[RuleCheckOut] = []
    excluded: bool = False
    exclusion_rule_id: str | None = None
    exclusion_reason: str | None = None


class EvaluationDetailOut(BaseModel):
    """Full evaluation detail with rule version traceability per supplier."""

    run_id: str
    request_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    supplier_breakdowns: list[SupplierRuleBreakdownOut] = []


# --- Create schemas for persisting evaluations ---


class HardRuleCheckCreate(BaseModel):
    rule_id: str
    version_id: str
    supplier_id: str | None = None
    skipped: bool = False
    skip_reason: str | None = None
    result: str | None = None
    actual_value: dict[str, Any] | None = None
    threshold: dict[str, Any] | None = None


class PolicyCheckCreate(BaseModel):
    rule_id: str
    version_id: str
    supplier_id: str | None = None
    result: str  # passed, warned, failed
    evidence: dict[str, Any]


class SupplierEvaluationCreate(BaseModel):
    supplier_id: str
    rank: int | None = None
    total_score: float | None = None
    price_score: float | None = None
    quality_score: float | None = None
    esg_score: float | None = None
    risk_score: float | None = None
    hard_checks_total: int = 0
    hard_checks_passed: int = 0
    hard_checks_skipped: int = 0
    hard_checks_failed: int = 0
    policy_checks_total: int = 0
    policy_checks_passed: int = 0
    policy_checks_warned: int = 0
    policy_checks_failed: int = 0
    excluded: bool = False
    exclusion_rule_id: str | None = None
    exclusion_reason: str | None = None
    pricing_snapshot: dict[str, Any] | None = None


class EscalationCreate(BaseModel):
    """Escalation entity for evaluation trigger workflow."""

    escalation_id: str | None = None
    rule_id: str
    version_id: str
    escalation_target: str
    escalation_reason: str
    trigger_table: str = "policy_checks"
    trigger_check_id: str = ""
    event_type: str = "escalation"
    event_status: str = "pending"
    status: str = "open"


class EvaluationRunCreate(BaseModel):
    """Create an evaluation run with checks. Used by logical layer after processing."""

    run_id: str
    request_id: str
    triggered_by: str = "agent"
    agent_version: str = "1.0"
    status: str = "completed"
    final_outcome: str | None = None
    output_snapshot: dict[str, Any] | None = None
    parent_run_id: str | None = None
    trigger_reason: str | None = None
    hard_rule_checks: list[HardRuleCheckCreate] = []
    policy_checks: list[PolicyCheckCreate] = []
    supplier_evaluations: list[SupplierEvaluationCreate] = []


class FullEvaluationTriggerCreate(EvaluationRunCreate):
    """Full evaluation trigger with escalations. Uses ACID workflow with audit trail."""

    escalations: list[EscalationCreate] = []


class PipelineEvaluationInput(BaseModel):
    """Pipeline output for persisting evaluation. Backend maps to checks from output_snapshot."""

    request_id: str
    run_id: str
    triggered_by: str = "agent"
    agent_version: str = "1.0"
    trigger_reason: str | None = "manual_recheck"
    output_snapshot: dict[str, Any] | None = None  # Full PipelineOutput.model_dump()
