# Dynamic Rule Engine

## Overview

The Dynamic Rule Engine replaces hardcoded procurement rules with a data-driven system. Rules are stored in MySQL, managed via REST API, and evaluated dynamically by the pipeline. You can add, edit, and delete rules without code changes.

## Architecture

```
┌─────────────────────────────────────┐    ┌─────────────────────────────────────┐
│  Organisational Layer (port 8000)   │    │    Logical Layer (port 8080)        │
│                                     │    │                                     │
│  ┌─────────────────────────────┐    │    │  ┌────────────────────────────┐     │
│  │  /api/dynamic-rules/ CRUD   │◀───┼────┼──│  Pipeline Runner           │     │
│  └─────────┬───────────────────┘    │    │  │  1. fetch active rules     │     │
│            │                        │    │  │  2. pass to each step      │     │
│  ┌─────────▼───────────────────┐    │    │  └────────┬───────────────────┘     │
│  │  dynamic_rules table        │    │    │           │                         │
│  │  dynamic_rule_versions      │    │    │  ┌────────▼───────────────────┐     │
│  │  rule_evaluation_results    │    │    │  │  Rule Engine               │     │
│  └─────────────────────────────┘    │    │  │  • compare evaluator       │     │
│                                     │    │  │  • required evaluator      │     │
└─────────────────────────────────────┘    │  │  • threshold evaluator     │     │
                                           │  │  • set_membership evaluator│     │
                                           │  │  • custom_llm evaluator    │     │
                                           │  └──────────────────────────────┘   │
                                           └─────────────────────────────────────┘
```

### Flow

1. **Pipeline Runner** fetches all active rules once from `GET /api/dynamic-rules/active`
2. Groups them by `pipeline_stage` (validate, comply, policy, escalate)
3. Each pipeline step receives its subset of rules and a `RuleEngine` instance
4. The step builds a **context dict** (flat key-value map of all relevant data)
5. `RuleEngine.evaluate_rules(rules, context)` evaluates each rule against the context
6. The step interprets results (exclude suppliers, add warnings, trigger escalations)
7. If no dynamic rules are available, steps fall back to hardcoded logic

## Rule Types (eval_type)

### `compare`

Compares two values using an operator. Covers budget checks, capacity, lead time, boolean flags.

```json
{
    "left_field": "budget_amount",
    "operator": ">=",
    "right_field": "total_price",
    "right_constant": null,
    "condition": null
}
```

| Field | Description |
|-------|-------------|
| `left_field` | Context key for the left operand |
| `operator` | One of `<`, `<=`, `>`, `>=`, `==`, `!=` |
| `right_field` | Context key for the right operand (mutually exclusive with `right_constant`) |
| `right_constant` | Literal value for the right operand |
| `condition` | Optional precondition: `{"field": "...", "operator": "==", "value": ...}`. Supports `and` nesting. |

### `required`

Asserts that fields are present (not null, not empty string, not empty list).

```json
{
    "fields": [
        {"name": "category_l1", "severity": "critical"},
        {"name": "budget_amount", "severity": "high"}
    ]
}
```

### `threshold`

Asserts a numeric value is within `[min, max]` bounds.

```json
{
    "field": "risk_score",
    "min": null,
    "max": 30,
    "condition": {"field": "preferred_supplier", "operator": "==", "value": false}
}
```

### `set_membership`

Asserts a value is (or is not) in a set resolved into the context.

```json
{
    "field": "supplier_id",
    "set_field": "restricted_supplier_ids",
    "expected_in_set": false
}
```

### `custom_llm`

Sends context fields to an LLM with a prompt template and interprets the structured response.

```json
{
    "system_prompt": "You are a procurement compliance checker...",
    "user_prompt_template": "Analyze: {request_text}\nQuantity: {quantity}",
    "input_fields": ["request_text", "quantity"],
    "pass_when": "verdict == 'pass'",
    "max_tokens": 1000
}
```

## Database Tables

### `dynamic_rules`

Primary table storing all rule definitions.

| Column | Type | Description |
|--------|------|-------------|
| `rule_id` | VARCHAR(20) PK | Unique rule identifier (e.g., HR-001, VAL-001) |
| `rule_name` | VARCHAR(200) | Human-readable name |
| `description` | TEXT | Detailed description |
| `rule_category` | VARCHAR(20) | `hard_rule`, `policy_check`, or `escalation` |
| `eval_type` | VARCHAR(20) | `compare`, `required`, `threshold`, `set_membership`, `custom_llm` |
| `scope` | VARCHAR(10) | `request` or `supplier` |
| `pipeline_stage` | VARCHAR(20) | `validate`, `comply`, `policy`, `escalate` |
| `eval_config` | JSON | Parameters for the evaluator (schema depends on eval_type) |
| `action_on_fail` | VARCHAR(20) | `exclude`, `warn`, `escalate`, `info` |
| `severity` | VARCHAR(10) | `critical`, `high`, `medium`, `low` |
| `is_blocking` | BOOLEAN | Whether failure blocks the pipeline |
| `escalation_target` | VARCHAR(200) | Who to escalate to (for escalation rules) |
| `fail_message_template` | TEXT | Message template with `{field_name}` interpolation |
| `is_active` | BOOLEAN | Soft-delete flag |
| `priority` | INT | Evaluation order (lower = first) |
| `version` | INT | Auto-incremented on update |

### `dynamic_rule_versions`

Audit trail of every rule change.

### `rule_evaluation_results`

Stores the outcome of evaluating each rule during a pipeline run.

## API Endpoints

All endpoints are under `/api/dynamic-rules/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List all rules (filter: `stage`, `category`, `is_active`) |
| GET | `/active` | List active rules only (filter: `stage`) |
| POST | `/` | Create a new rule (auto-creates version 1) |
| GET | `/{rule_id}` | Get a single rule |
| PUT | `/{rule_id}` | Update a rule (bumps version, snapshots old version) |
| DELETE | `/{rule_id}` | Soft-delete (sets `is_active=false`) |
| GET | `/{rule_id}/versions` | Version history |
| POST | `/evaluation-results` | Store rule evaluation results from pipeline |
| GET | `/evaluation-results/by-run/{run_id}` | Get results by pipeline run |

## Adding a New Rule

### Example: Add a rule that requires ESG score > 50 for all suppliers

```bash
curl -X POST http://localhost:8000/api/dynamic-rules/ \
  -H "Content-Type: application/json" \
  -d '{
    "rule_id": "HR-ESG",
    "rule_name": "ESG minimum threshold",
    "description": "Suppliers must have ESG score above 50",
    "rule_category": "hard_rule",
    "eval_type": "threshold",
    "scope": "supplier",
    "pipeline_stage": "comply",
    "eval_config": {
        "field": "esg_score",
        "min": 50,
        "max": null,
        "condition": null
    },
    "action_on_fail": "exclude",
    "severity": "high",
    "is_blocking": false,
    "fail_message_template": "ESG score {esg_score} is below minimum 50",
    "priority": 45,
    "created_by": "admin"
}'
```

The next pipeline run will automatically pick up this rule and evaluate it for every supplier.

### Example: Add a custom LLM rule for brand safety

```bash
curl -X POST http://localhost:8000/api/dynamic-rules/ \
  -H "Content-Type: application/json" \
  -d '{
    "rule_id": "CUSTOM-BRAND",
    "rule_name": "Brand safety LLM check",
    "rule_category": "policy_check",
    "eval_type": "custom_llm",
    "scope": "request",
    "pipeline_stage": "policy",
    "eval_config": {
        "system_prompt": "Evaluate brand safety risk for the given procurement request.",
        "user_prompt_template": "Category: {category_l2}\nRequest: {request_text}",
        "input_fields": ["category_l2", "request_text"],
        "pass_when": "verdict == '\''pass'\''",
        "max_tokens": 800
    },
    "action_on_fail": "warn",
    "severity": "high",
    "priority": 70,
    "created_by": "admin"
}'
```

## Modifying an Existing Rule

```bash
curl -X PUT http://localhost:8000/api/dynamic-rules/HR-RISK \
  -H "Content-Type: application/json" \
  -d '{
    "eval_config": {
        "field": "risk_score",
        "min": null,
        "max": 25,
        "condition": {"field": "preferred_supplier", "operator": "==", "value": false}
    },
    "changed_by": "admin",
    "change_reason": "Tighten risk threshold from 30 to 25"
}'
```

This bumps the version, snapshots the old state, and applies immediately.

## Deleting a Rule

```bash
curl -X DELETE http://localhost:8000/api/dynamic-rules/HR-ESG
```

This soft-deletes (sets `is_active=false`). The rule remains in the database for audit purposes.

## Seeded Rules

The migration script seeds all existing procurement rules:

| ID | Name | Type | Stage | Scope |
|----|------|------|-------|-------|
| VAL-001 | Required fields check | required | validate | request |
| VAL-002 | Recommended fields check | required | validate | request |
| VAL-003 | Past delivery date check | compare | validate | request |
| VAL-004 | Budget sufficiency check | compare | validate | request |
| VAL-005 | Lead time feasibility check | compare | validate | request |
| VAL-006 | Text/field contradiction detection | custom_llm | validate | request |
| HR-001 | Budget ceiling check | compare | comply | supplier |
| HR-002 | Delivery deadline feasibility | compare | comply | supplier |
| HR-003 | Supplier monthly capacity | compare | comply | supplier |
| HR-004 | Minimum order quantity | compare | comply | supplier |
| PC-008 | Data residency constraint | compare | comply | supplier |
| HR-RISK | Risk score threshold | threshold | comply | supplier |
| PC-004 | Restricted supplier check | compare | comply | supplier |
| ER-001 | Missing required info escalation | compare | escalate | request |
| ER-002 | Preferred supplier restricted | compare | escalate | request |
| ER-003 | Contract value exceeds tier | compare | escalate | request |
| ER-004 | No compliant supplier found | compare | escalate | request |
| ER-005 | Data residency unsatisfiable | compare | escalate | request |
| ER-006 | Quantity exceeds all capacity | compare | escalate | request |
| ER-007 | Brand safety concern | compare | escalate | request |
| PC-001 | Approval tier determination | threshold | policy | request |
| PC-002 | Quote count requirement | compare | policy | request |
| PC-003 | Preferred supplier check | compare | policy | request |
| PC-007 | Category sourcing rules | set_membership | policy | request |
| PC-009 | Geography/delivery compliance | set_membership | policy | request |

## Testing

### Rule Engine Unit Tests

```bash
cd backend/logical_layer
python -m pytest tests/test_rule_engine.py -v
```

Tests all 5 evaluator types with pass/fail/skip/error cases, condition handling, message formatting, priority ordering, and edge cases. **41 tests.**

### Full Logical Layer Tests

```bash
cd backend/logical_layer
python -m pytest tests/ -v
```

Includes all rule engine tests plus existing pipeline step tests. **177 tests.**

### Organisational Layer API Tests

```bash
cd backend/organisational_layer
python -m pytest tests/test_dynamic_rules.py -v
```

Requires a running MySQL database with dynamic_rules tables seeded. Tests CRUD operations, versioning, filtering, validation, evaluation results storage, and seeded rule verification.

### Running the Migration

```bash
cd database_init
python migrate_dynamic_rules.py
```

Creates the 3 new tables and seeds all rules. Idempotent (uses `CREATE TABLE IF NOT EXISTS` and `INSERT IGNORE`).

## Context Fields

### Request-level context (validate, escalate, policy stages)

| Field | Source |
|-------|--------|
| `request_id` | Request |
| `category_l1`, `category_l2` | Request |
| `budget_amount` | Request (coerced to float) |
| `quantity` | Request (coerced to int) |
| `currency` | Request |
| `required_by_date` | Request |
| `days_until_required` | Computed |
| `delivery_countries` | Request |
| `country` | First delivery country |
| `data_residency_constraint` | Request |
| `preferred_supplier_mentioned` | Request |
| `request_text` | Request |
| `min_total_price` | Min across pricing tiers |
| `min_expedited_lead_time` | Min across pricing tiers |
| `compliant_supplier_count` | From comply step |
| `min_ranked_total` | Min total from ranked suppliers |
| `has_residency_supplier` | Any compliant supplier supports residency |
| `has_contradictions` | From validation issues |
| `has_lead_time_issue` | From validation issues |

### Supplier-level context (comply stage)

Extends request context with:

| Field | Source |
|-------|--------|
| `supplier_id`, `supplier_name` | Supplier |
| `quality_score`, `risk_score`, `esg_score` | Supplier |
| `preferred_supplier` | Supplier |
| `data_residency_supported` | Supplier |
| `capacity_per_month` | Supplier |
| `unit_price`, `total_price` | Pricing tier |
| `moq` | Pricing tier |
| `standard_lead_time_days`, `expedited_lead_time_days` | Pricing tier |
| `is_restricted` | Org layer restriction check |

## Backward Compatibility

All pipeline steps fall back to hardcoded logic when no dynamic rules are provided. This means:

- If the org layer is unreachable, the pipeline still works
- If the `dynamic_rules` table is empty, existing behavior is preserved
- You can incrementally migrate rules from hardcoded to dynamic
