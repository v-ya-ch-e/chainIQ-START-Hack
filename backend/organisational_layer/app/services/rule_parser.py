"""Convert free-text rule descriptions into structured DynamicRuleCreate JSON via Anthropic.

The LLM receives all existing active rules so it can decide whether to create
a new rule or update an existing one.
"""

from __future__ import annotations

import json
import os

import anthropic

from app.schemas.dynamic_rules import (
    VALID_ACTIONS,
    VALID_EVAL_TYPES,
    VALID_PIPELINE_STAGES,
    VALID_RULE_CATEGORIES,
    VALID_SCOPES,
    VALID_SEVERITIES,
)

ANTHROPIC_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a procurement rule engine expert for the ChainIQ platform. You convert \
natural-language rule descriptions into structured JSON rule definitions that \
the dynamic rule engine can evaluate automatically.

You will receive:
1. A list of ALL existing rules currently in the system
2. A user request describing a new rule OR a change to an existing rule

Your job:
- If the user is describing a MODIFICATION to an existing rule, return the \
complete updated rule with the SAME rule_id and set "_action": "update".
- If the user is describing a NEW rule, pick the next available ID for the \
appropriate prefix and set "_action": "create".

Respond with ONLY a valid JSON object. No markdown fencing, no explanation.

## JSON Schema

{
  "_action": "create" | "update",
  "rule_id": string (max 20 chars),
  "rule_name": string (max 200 chars),
  "description": string,
  "rule_category": "hard_rule" | "policy_check" | "escalation",
  "eval_type": "compare" | "required" | "threshold" | "set_membership" | "custom_llm",
  "scope": "request" | "supplier",
  "pipeline_stage": "validate" | "comply" | "policy" | "escalate",
  "eval_config": object (structure depends on eval_type — see below),
  "action_on_fail": "exclude" | "warn" | "escalate" | "info",
  "severity": "critical" | "high" | "medium" | "low",
  "is_blocking": boolean,
  "escalation_target": string or null,
  "fail_message_template": string (supports {context_field} interpolation),
  "is_active": true,
  "is_skippable": boolean,
  "priority": integer (10-100, lower runs first)
}

## Field semantics

rule_category:
  - "hard_rule": pass/fail compliance check (e.g. capacity limits, budget ceiling)
  - "policy_check": softer compliance documentation (e.g. quote count, preferred status)
  - "escalation": triggers human review when condition is met

scope:
  - "request": rule evaluates request-level data (one evaluation per request)
  - "supplier": rule evaluates per-supplier data (one per supplier in shortlist)

pipeline_stage + typical pairings:
  - "validate": input validation (scope=request, category=hard_rule or policy_check)
  - "comply": supplier compliance (scope=supplier, category=hard_rule)
  - "policy": policy documentation (scope=request, category=policy_check)
  - "escalate": escalation triggers (scope=request, category=escalation, \
action_on_fail=escalate)

action_on_fail:
  - "exclude": removes a supplier from shortlist (only for scope=supplier)
  - "warn": flags an issue but does not exclude
  - "escalate": triggers escalation to escalation_target
  - "info": documents for audit without flagging

is_blocking: true means the pipeline CANNOT proceed without human review. \
Use sparingly — only for escalation rules where autonomous decision is impossible.

rule_id conventions:
  - VAL-NNN for validate stage
  - HR-NNN for hard rules in comply stage
  - PC-NNN for policy checks
  - ER-NNN for escalation rules

## eval_config by eval_type

### compare — field-vs-field or field-vs-constant comparison
{
  "left_field": "<context field name>",
  "operator": "<" | "<=" | ">" | ">=" | "==" | "!=",
  "right_field": "<context field name>" or null,
  "right_constant": <literal value> or null,
  "condition": <precondition object> or null
}
Either right_field OR right_constant, never both.

### required — assert fields are present (not null/empty)
{
  "fields": [
    {"name": "<context field>", "severity": "critical" | "high" | "medium" | "low"}
  ]
}

### threshold — numeric range check
{
  "field": "<context field name>",
  "min": <number> or null,
  "max": <number> or null,
  "condition": <precondition object> or null
}

### set_membership — check if value is in a set
{
  "field": "<context field to check>",
  "set_field": "<context field containing the list/set>",
  "expected_in_set": true | false
}

### custom_llm — LLM-based evaluation (use sparingly)
{
  "system_prompt": "<instructions for evaluation LLM>",
  "user_prompt_template": "<template with {field} placeholders>",
  "input_fields": ["field1", "field2"],
  "pass_when": "no_contradictions" | "verdict",
  "max_tokens": <integer>
}

## Precondition object (used in compare/threshold condition field)
{
  "field": "<context field>",
  "operator": "==" | "!=" | "<" | "<=" | ">" | ">=",
  "value": <expected value>,
  "and": <nested precondition> (optional)
}
If the precondition is false, the rule is skipped (not failed).

## Available context fields by pipeline stage

### validate stage (scope: request)
request_id, category_l1, category_l2, budget_amount (float|null), \
quantity (int|null), currency, required_by_date, delivery_countries (list|null), \
country, days_until_required (int|null), data_residency_constraint (bool), \
preferred_supplier_mentioned (string|null), request_text, request_language, \
min_total_price (float|null), min_expedited_lead_time (int|null)

### comply stage (scope: supplier)
All validate fields plus: \
supplier_id, supplier_name, quality_score (0-100), risk_score (0-100, lower=better), \
esg_score (0-100), preferred_supplier (bool), data_residency_supported (bool), \
capacity_per_month (int), unit_price (float|null), total_price (float|null), \
moq (int|null), standard_lead_time_days (int|null), \
expedited_lead_time_days (int|null), is_restricted (bool), restriction_reason (string)

### policy stage (scope: request)
request_id, category_l1, category_l2, budget_amount, currency, country, \
compliant_supplier_count (int), quotes_required (int|null), \
preferred_supplier_mentioned, preferred_in_compliant (bool), \
category_rule_categories (list of rule_ids), geography_rule_countries (list of rule_ids)

### escalate stage (scope: request)
request_id, category_l1, category_l2, budget_amount, quantity, currency, country, \
data_residency_constraint, preferred_supplier_mentioned, \
compliant_supplier_count (int), min_ranked_total (float|null), \
max_supplier_capacity (int|null), has_residency_supplier (bool), \
preferred_is_restricted (bool), has_contradictions (bool), \
has_lead_time_issue (bool), has_budget_issue (bool), \
has_unregistered_supplier (bool), single_supplier_capacity_risk (bool), \
approval_tier_requires_strategic (bool)

## Examples of real rules

Example 1 — threshold eval_type, supplier scope:
{"rule_id":"HR-RISK","rule_name":"Risk score threshold","description":"Non-preferred suppliers with high risk score are excluded","rule_category":"hard_rule","eval_type":"threshold","scope":"supplier","pipeline_stage":"comply","eval_config":{"field":"risk_score","min":null,"max":70,"condition":{"field":"preferred_supplier","operator":"==","value":false}},"action_on_fail":"exclude","severity":"high","is_blocking":false,"escalation_target":null,"fail_message_template":"Non-preferred supplier risk_score={risk_score} exceeds threshold 70","is_active":true,"is_skippable":false,"priority":50}

Example 2 — compare eval_type, escalation:
{"rule_id":"ER-004","rule_name":"No compliant supplier found","description":"Escalate when no supplier remains after compliance checks","rule_category":"escalation","eval_type":"compare","scope":"request","pipeline_stage":"escalate","eval_config":{"left_field":"compliant_supplier_count","operator":">","right_field":null,"right_constant":0,"condition":null},"action_on_fail":"escalate","severity":"critical","is_blocking":true,"escalation_target":"Head of Category","fail_message_template":"No compliant supplier found after compliance checks","is_active":true,"is_skippable":false,"priority":40}

Example 3 — required eval_type, validation:
{"rule_id":"VAL-001","rule_name":"Required fields check","description":"Ensure critical request fields are present","rule_category":"hard_rule","eval_type":"required","scope":"request","pipeline_stage":"validate","eval_config":{"fields":[{"name":"category_l1","severity":"critical"},{"name":"category_l2","severity":"critical"},{"name":"currency","severity":"critical"}]},"action_on_fail":"warn","severity":"critical","is_blocking":false,"escalation_target":null,"fail_message_template":"Required field {field_name} is missing","is_active":true,"is_skippable":false,"priority":10}

## Guidelines
- For escalation rules: pipeline_stage="escalate", action_on_fail="escalate", set escalation_target
- is_blocking=true only for escalation rules where processing truly cannot continue
- fail_message_template supports {field_name} placeholders filled from context at runtime
- If the description is vague, make reasonable assumptions and document them in description
- Prefer compare eval_type — it covers most use cases
- Use threshold for simple numeric range checks
- Use required for null/missing field checks
- Use custom_llm only when no deterministic eval_type can express the logic
- When updating an existing rule, preserve the rule_id and only change what the user asked for\
"""

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


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(raw[start:end])


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
    """Build a compact representation of existing rules for the LLM context."""
    if not existing_rules:
        return "No existing rules in the system."
    compact = []
    for r in existing_rules:
        compact.append({
            "rule_id": r.get("rule_id"),
            "rule_name": r.get("rule_name"),
            "description": r.get("description"),
            "rule_category": r.get("rule_category"),
            "eval_type": r.get("eval_type"),
            "scope": r.get("scope"),
            "pipeline_stage": r.get("pipeline_stage"),
            "severity": r.get("severity"),
            "is_blocking": r.get("is_blocking"),
            "escalation_target": r.get("escalation_target"),
            "eval_config": r.get("eval_config"),
        })
    return json.dumps(compact, indent=None, ensure_ascii=False)


def parse_rule_text(text: str, existing_rules: list[dict]) -> dict:
    """Convert free-text into a structured dynamic rule definition.

    The LLM sees all existing rules and decides whether to create a new rule
    or update an existing one.

    Returns ``{"complete": bool, "rule": dict, "is_update": bool, "target_rule_id": str|None}``.
    """
    client = _anthropic_client()

    rules_summary = _build_existing_rules_summary(existing_rules)

    user_message = (
        f"## Existing rules in the system\n{rules_summary}\n\n"
        f"## User request\n{text}\n\n"
        "Decide: is this a new rule or a modification to an existing one?\n"
        "- If modifying an existing rule, use the same rule_id and return "
        "the complete updated rule with \"_action\": \"update\"\n"
        "- If creating a new rule, pick the next available ID for the "
        "appropriate prefix and set \"_action\": \"create\"\n"
    )

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    data = _extract_json(response.content[0].text)

    action = data.pop("_action", "create")
    is_update = action == "update"
    target_rule_id = data.get("rule_id") if is_update else None

    data = _validate_and_fill(data)

    return {
        "complete": _is_complete(data),
        "rule": data,
        "is_update": is_update,
        "target_rule_id": target_rule_id,
    }
