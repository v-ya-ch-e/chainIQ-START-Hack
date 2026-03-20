"""Pydantic schemas for the dynamic rule engine."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


VALID_EVAL_TYPES = ("compare", "required", "threshold", "set_membership", "custom_llm")
VALID_RULE_CATEGORIES = ("hard_rule", "policy_check", "escalation")
VALID_SCOPES = ("request", "supplier")
VALID_PIPELINE_STAGES = ("validate", "comply", "policy", "escalate")
VALID_ACTIONS = ("exclude", "warn", "escalate", "info")
VALID_SEVERITIES = ("critical", "high", "medium", "low")


class DynamicRuleCreate(BaseModel):
    rule_id: str = Field(..., max_length=20)
    rule_name: str = Field(..., max_length=200)
    description: str | None = None
    rule_category: str = Field(..., description="hard_rule | policy_check | escalation")
    eval_type: str = Field(..., description="compare | required | threshold | set_membership | custom_llm")
    scope: str = Field(default="request", description="request | supplier")
    pipeline_stage: str = Field(..., description="validate | comply | policy | escalate")
    eval_config: dict[str, Any]
    action_on_fail: str = Field(default="warn", description="exclude | warn | escalate | info")
    severity: str = Field(default="medium", description="critical | high | medium | low")
    is_blocking: bool = False
    escalation_target: str | None = None
    fail_message_template: str | None = None
    is_active: bool = True
    is_skippable: bool = False
    priority: int = 100
    created_by: str | None = None


class DynamicRuleUpdate(BaseModel):
    rule_name: str | None = None
    description: str | None = None
    rule_category: str | None = None
    eval_type: str | None = None
    scope: str | None = None
    pipeline_stage: str | None = None
    eval_config: dict[str, Any] | None = None
    action_on_fail: str | None = None
    severity: str | None = None
    is_blocking: bool | None = None
    escalation_target: str | None = None
    fail_message_template: str | None = None
    is_active: bool | None = None
    is_skippable: bool | None = None
    priority: int | None = None
    changed_by: str | None = None
    change_reason: str | None = None


class DynamicRuleOut(BaseModel):
    rule_id: str
    rule_name: str
    description: str | None
    rule_category: str
    eval_type: str
    scope: str
    pipeline_stage: str
    eval_config: dict[str, Any]
    action_on_fail: str
    severity: str
    is_blocking: bool
    escalation_target: str | None
    fail_message_template: str | None
    is_active: bool
    is_skippable: bool
    priority: int
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: str | None

    model_config = {"from_attributes": True}


class DynamicRuleVersionOut(BaseModel):
    id: int
    rule_id: str
    version: int
    snapshot: dict[str, Any]
    valid_from: datetime
    valid_to: datetime | None
    changed_by: str | None
    change_reason: str | None

    model_config = {"from_attributes": True}


class RuleEvaluationResultCreate(BaseModel):
    result_id: str
    run_id: str
    rule_id: str
    rule_version: int
    supplier_id: str | None = None
    scope: str
    result: str = Field(..., description="passed | failed | warned | skipped | error")
    actual_values: dict[str, Any] | None = None
    expected_values: dict[str, Any] | None = None
    message: str | None = None
    action_taken: str | None = None


class RuleEvaluationResultOut(BaseModel):
    result_id: str
    run_id: str
    rule_id: str
    rule_version: int
    supplier_id: str | None
    scope: str
    result: str
    actual_values: dict[str, Any] | None
    expected_values: dict[str, Any] | None
    message: str | None
    action_taken: str | None
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class BulkEvaluationResultCreate(BaseModel):
    results: list[RuleEvaluationResultCreate]


class RuleParseRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Free-text rule description or change request")


class RuleParseResponse(BaseModel):
    complete: bool
    rule: DynamicRuleCreate
    is_update: bool = False
    target_rule_id: str | None = None
