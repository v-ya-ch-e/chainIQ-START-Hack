"""Convert free-text rule descriptions into structured DynamicRuleCreate JSON via Anthropic.

Uses tool_use for guaranteed structured output instead of raw JSON extraction.
The LLM receives all existing active rules so it can decide whether to create
a new rule or update an existing one.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
from pydantic import BaseModel, Field

from app.schemas.dynamic_rules import (
    VALID_ACTIONS,
    VALID_EVAL_TYPES,
    VALID_PIPELINE_STAGES,
    VALID_RULE_CATEGORIES,
    VALID_SCOPES,
    VALID_SEVERITIES,
)

logger = logging.getLogger(__name__)

ANTHROPIC_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Pydantic model for structured tool_use output
# ---------------------------------------------------------------------------

class ParsedRuleOutput(BaseModel):
    """Schema the LLM must fill via tool_use. Validated by Pydantic on return."""

    action: str = Field(description="'create' for a new rule, 'update' to modify an existing rule")
    rule_id: str = Field(description="For create: next available ID (e.g. ER-011). For update: the existing rule_id being changed.")
    rule_name: str = Field(max_length=200)
    description: str
    rule_category: str = Field(description="hard_rule | policy_check | escalation")
    eval_type: str = Field(description="compare | required | threshold | set_membership | custom_llm")
    scope: str = Field(description="request | supplier")
    pipeline_stage: str = Field(description="validate | comply | policy | escalate")
    eval_config: dict[str, Any]
    action_on_fail: str = Field(description="exclude | warn | escalate | info")
    severity: str = Field(description="critical | high | medium | low")
    is_blocking: bool
    escalation_target: str | None = None
    fail_message_template: str | None = None
    is_skippable: bool = False
    priority: int = Field(ge=1, le=200)


# ---------------------------------------------------------------------------
# System prompt — teaches the domain, not the JSON schema (tool_use does that)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a procurement rule engine expert. You translate plain-language requests \
into executable rule definitions for the ChainIQ dynamic rule engine.

You will receive a list of every active rule already in the system, followed by \
a user request. Decide whether the user wants to CREATE a new rule or UPDATE an \
existing one, then fill the structured_output tool accordingly.

## How the rule engine works

The procurement pipeline evaluates purchase requests in 4 stages. At each stage \
the engine iterates over active rules whose pipeline_stage matches, builds a \
flat context dict, and evaluates each rule against it.

A rule PASSES when its condition is satisfied (good state). \
A rule FAILS when the condition is NOT satisfied (problem detected). \
On failure the engine executes the rule's action_on_fail.

## The 5 eval_type evaluators

### compare
Tests: context[left_field] <operator> context[right_field] (or right_constant).
PASSES when the comparison is true. FAILS when false.
Example — "budget must cover total price":
  left_field="budget_amount", operator=">=", right_field="total_price"
  → passes when budget >= total, fails when budget < total.

IMPORTANT for escalation rules: the compare expression must describe the \
DESIRED (good) state. When the good state is violated, the rule fails and \
the escalation fires.
Example — "escalate when no compliant supplier":
  left_field="compliant_supplier_count", operator=">", right_constant=0
  → passes when count > 0 (good), fails when count == 0 (escalate).

### required
Checks that listed fields are not null / empty. Fails if any are missing.

### threshold
Checks context[field] is within [min, max]. Fails if outside bounds.
Use a condition to limit when the check applies.

### set_membership
Checks if context[field] is in context[set_field]. expected_in_set=true \
means membership is desired; false means non-membership is desired.

### custom_llm
Sends context fields to an LLM sub-call. Use only when no deterministic \
evaluator can express the logic.

## Precondition (condition field)
Optional guard on compare / threshold rules. If the condition evaluates false \
the rule is SKIPPED (not failed). Format:
{"field": "...", "operator": "==", "value": ..., "and": {nested...}}

## Pipeline stages and conventions

| stage     | scope    | typical rule_category | typical action_on_fail | notes |
|-----------|----------|-----------------------|------------------------|-------|
| validate  | request  | hard_rule / policy_check | warn                | Input quality checks |
| comply    | supplier | hard_rule             | exclude / info         | Per-supplier compliance; exclude removes from shortlist |
| policy    | request  | policy_check          | info / warn            | Documents policy for audit |
| escalate  | request  | escalation            | escalate               | Triggers human review; set escalation_target |

- rule_id prefix: VAL- (validate), HR- (comply hard rules), PC- (policy checks), ER- (escalate)
- is_blocking=true → pipeline cannot proceed without human review. Only for critical escalations.
- fail_message_template supports {field_name} placeholders filled from context at runtime.

## Context fields available at each stage

### validate (scope=request)
request_id, category_l1, category_l2, budget_amount, quantity, currency, \
required_by_date, delivery_countries, country, days_until_required, \
data_residency_constraint, preferred_supplier_mentioned, request_text, \
request_language, min_total_price, min_expedited_lead_time

### comply (scope=supplier) — all validate fields plus:
supplier_id, supplier_name, quality_score (0-100, higher=better), \
risk_score (0-100, lower=better), esg_score (0-100, higher=better), \
preferred_supplier (bool), data_residency_supported (bool), \
capacity_per_month, unit_price, total_price, moq, \
standard_lead_time_days, expedited_lead_time_days, is_restricted, \
restriction_reason

### policy (scope=request)
request_id, category_l1, category_l2, budget_amount, currency, country, \
compliant_supplier_count, quotes_required, preferred_supplier_mentioned, \
preferred_in_compliant, category_rule_categories, geography_rule_countries

### escalate (scope=request)
request_id, category_l1, category_l2, budget_amount, quantity, currency, \
country, data_residency_constraint, preferred_supplier_mentioned, \
compliant_supplier_count, min_ranked_total, max_supplier_capacity, \
has_residency_supplier, preferred_is_restricted, has_contradictions, \
has_lead_time_issue, has_budget_issue, has_unregistered_supplier, \
single_supplier_capacity_risk, approval_tier_requires_strategic

## Decision: create vs update
- If the user mentions a specific existing rule_id (e.g. "change ER-004"), or \
clearly describes modifying the behaviour of a rule that already exists, \
set action="update" and use the existing rule_id.
- Otherwise set action="create" and pick the next available number for the \
appropriate prefix.\
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ("rule_id", "rule_name", "rule_category", "eval_type", "pipeline_stage", "eval_config")

DEFAULTS: dict[str, object] = {
    "scope": "request",
    "action_on_fail": "warn",
    "severity": "medium",
    "is_blocking": False,
    "is_active": True,
    "is_skippable": False,
    "priority": 100,
}

ENUM_VALIDATORS: dict[str, tuple[str, ...]] = {
    "eval_type": VALID_EVAL_TYPES,
    "rule_category": VALID_RULE_CATEGORIES,
    "scope": VALID_SCOPES,
    "pipeline_stage": VALID_PIPELINE_STAGES,
    "action_on_fail": VALID_ACTIONS,
    "severity": VALID_SEVERITIES,
}


def _anthropic_client() -> anthropic.Anthropic:
    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is missing in organisational-layer environment")
    return anthropic.Anthropic(api_key=api_key)


def _validate_and_fill(data: dict) -> dict:
    for field, default in DEFAULTS.items():
        if field not in data or data[field] is None:
            data[field] = default

    for field, valid_values in ENUM_VALIDATORS.items():
        if field in data and data[field] is not None:
            if data[field] not in valid_values:
                data[field] = DEFAULTS.get(field, valid_values[0])

    if not isinstance(data.get("eval_config"), dict):
        data["eval_config"] = {}

    return data


def _is_complete(data: dict) -> bool:
    for field in REQUIRED_FIELDS:
        val = data.get(field)
        if val is None:
            return False
        if isinstance(val, str) and val.strip() == "":
            return False
        if isinstance(val, dict) and len(val) == 0:
            return False
    return True


def _build_existing_rules_summary(existing_rules: list[dict]) -> str:
    if not existing_rules:
        return "No existing rules in the system."
    compact = []
    for r in existing_rules:
        entry: dict[str, Any] = {
            "rule_id": r.get("rule_id"),
            "rule_name": r.get("rule_name"),
            "description": r.get("description"),
            "eval_type": r.get("eval_type"),
            "scope": r.get("scope"),
            "pipeline_stage": r.get("pipeline_stage"),
            "severity": r.get("severity"),
            "is_blocking": r.get("is_blocking"),
        }
        if r.get("escalation_target"):
            entry["escalation_target"] = r["escalation_target"]
        compact.append(entry)
    return json.dumps(compact, indent=None, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_rule_text(text: str, existing_rules: list[dict]) -> dict:
    """Convert free-text into a structured dynamic rule definition.

    Uses Anthropic tool_use for guaranteed structured output.

    Returns ``{"complete": bool, "rule": dict, "is_update": bool,
    "target_rule_id": str | None}``.
    """
    client = _anthropic_client()

    rules_summary = _build_existing_rules_summary(existing_rules)
    user_message = (
        f"## Existing rules in the system\n{rules_summary}\n\n"
        f"## User request\n{text}"
    )

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        tools=[
            {
                "name": "structured_output",
                "description": "Return the rule definition matching the user's request.",
                "input_schema": ParsedRuleOutput.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "structured_output"},
    )

    tool_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if tool_block is None:
        raise ValueError("LLM response contained no tool_use block")

    parsed = ParsedRuleOutput.model_validate(tool_block.input)

    action = parsed.action
    is_update = action == "update"
    target_rule_id = parsed.rule_id if is_update else None

    data = parsed.model_dump(exclude={"action"})
    data["is_active"] = True
    data = _validate_and_fill(data)

    return {
        "complete": _is_complete(data),
        "rule": data,
        "is_update": is_update,
        "target_rule_id": target_rule_id,
    }
