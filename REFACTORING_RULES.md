# Data-Driven Rules Refactoring Plan

This document is the complete specification for making all procurement rules in the ChainIQ system data-driven — stored in the database, manageable via API, and evaluable at runtime without code changes.

---

## 1. Current State

Every rule in the system is currently hardcoded in Python. There are four categories spread across two services.

### A. Escalation Rules — Org Layer (`backend/organisational_layer/app/services/escalations.py`)

8 rules with explicit `if` blocks in `compute_escalations_for_rule_input()`, plus one dynamic AT-conflict check. The `escalation_rules` DB table stores only labels and targets — the trigger logic is entirely in code.

| Current ID | Hardcoded condition |
|---|---|
| ER-001 | `missing_required_information == True` |
| ER-002 | `preferred_supplier_restricted == True` |
| ER-003 | CPO or Head of Strategic Sourcing in threshold managers/deviation approvers |
| ER-004 | `not missing_required_information and not has_compliant_priceable_supplier` |
| ER-005 | `not missing_required_information and has_residency_compatible_supplier == False` |
| ER-006 | `not missing_required_information and single_supplier_capacity_risk` |
| ER-007 | `category_label == "Marketing / Influencer Campaign Management"` |
| ER-008 | `preferred_supplier_unregistered_usd == True` |
| AT-conflict | `threshold_quotes_required >= 2 and has_single_supplier_instruction in request_text` |

### B. Validation Rules — Logical Layer (`backend/logical_layer/app/pipeline/steps/validate.py`)

10 deterministic checks plus one LLM-powered contradiction detection pass, all hardcoded in `validate_request()`.

| ID (implicit) | Hardcoded condition | Severity | Blocks pipeline? |
|---|---|---|---|
| VR-001 | `category_l1` is empty | critical | yes |
| VR-002 | `category_l2` is empty | critical | yes |
| VR-003 | `currency` is empty | critical | yes |
| VR-004 | `budget_amount` is null | high | no |
| VR-005 | `quantity` is null | high | no |
| VR-006 | `required_by_date` is empty | medium | no |
| VR-007 | no delivery countries | high | no |
| VR-008 | `required_by_date` is in the past | critical | no |
| VR-009 | budget < minimum supplier total price | critical | no |
| VR-010 | days_until_required < fastest expedited lead time | high | no |
| VR-LLM | contradictions between `request_text` and structured fields | varies | no |

### C. Supplier Compliance Rules — Logical Layer (`backend/logical_layer/app/pipeline/steps/comply.py`)

4 per-supplier checks in `_check_supplier()`, one of which calls the Org Layer API.

| ID (implicit) | Hardcoded condition |
|---|---|
| CR-001 | `request.data_residency_constraint and not supplier.data_residency_supported` |
| CR-002 | `quantity > supplier.capacity_per_month` |
| CR-003 | `not supplier.preferred_supplier and supplier.risk_score > 30` |
| CR-004 | supplier is restricted (Org Layer `check-restricted` API call) |

### D. Pipeline Escalation Rules — Logical Layer (`backend/logical_layer/app/pipeline/steps/escalate.py`)

6 checks in `_discover_pipeline_issues()` that fire enriched escalations based on pipeline state from steps 2-5.

| ID (implicit) | Hardcoded condition |
|---|---|
| PE-001 | validation has budget_insufficient issue + ranked suppliers exist |
| PE-002 | validation has lead_time_infeasible issue |
| PE-003 | data_residency required but no compliant supplier supports it |
| PE-004 | no suppliers remain after compliance |
| PE-005 | preferred supplier was excluded as restricted |
| PE-LLM | LLM found requester instruction conflicting with policy |

---

## 2. Target State

A single `procurement_rules` table replaces all hardcoded logic. Each rule has an `evaluation_mode` flag:

- **`expression`** — evaluated by `simpleeval` against a context dictionary. Fast, deterministic, auditable.
- **`llm`** — evaluated by sending context + the rule's `llm_prompt` to Claude. Returns a boolean + natural-language justification. Slower, non-deterministic, logged with justification in audit trail.
- **`hardcoded`** — escape hatch for rules that require async I/O or complex logic that cannot be expressed as a simple expression. Code handles these by `rule_id`.

Rules are fetched from the Org Layer at the start of each pipeline step. The Logical Layer's `rule_evaluator.py` iterates rules, evaluates them against the step's context, and produces results.

```
┌──────────────────────────────────────────────────────────┐
│                   procurement_rules table                  │
│  ER-001..008, VR-001..010, CR-001..004, PE-001..005       │
│  + VR-LLM, PE-LLM, AT-conflict                           │
│  Each row: condition_expr OR llm_prompt + evaluation_mode  │
└───────────────────────────┬──────────────────────────────┘
                            │ GET /api/rules/procurement
                            ▼
┌──────────────────────────────────────────────────────────┐
│                 Logical Layer Pipeline                     │
│  Step 2 (validate): fetch rules where scope=request,      │
│    rule_type=validation → evaluate each                    │
│  Step 4 (comply): fetch rules where scope=supplier,       │
│    rule_type=supplier_compliance → evaluate per-supplier   │
│  Step 7 (escalate): fetch rules where scope=pipeline,     │
│    rule_type=pipeline_escalation → evaluate each           │
│  Org Layer escalation engine: fetch rules where            │
│    scope=request, rule_type=escalation → evaluate each     │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Table Schema

```sql
CREATE TABLE procurement_rules (
    rule_id             VARCHAR(20)  PRIMARY KEY,
    rule_type           VARCHAR(30)  NOT NULL,
    -- 'escalation'          — fires an escalation (ER-xxx)
    -- 'validation'          — creates a validation issue (VR-xxx)
    -- 'supplier_compliance' — excludes a supplier (CR-xxx)
    -- 'pipeline_escalation' — enriched escalation from pipeline state (PE-xxx)

    scope               VARCHAR(20)  NOT NULL,
    -- 'request'    — evaluated against request-level context
    -- 'supplier'   — evaluated per-supplier against supplier+request context
    -- 'pipeline'   — evaluated against full pipeline state

    evaluation_mode     VARCHAR(20)  NOT NULL DEFAULT 'expression',
    -- 'expression' — simpleeval against context dict
    -- 'llm'        — send context + llm_prompt to Claude
    -- 'hardcoded'  — code handles it (escape hatch)

    condition_expr      TEXT         NULL,
    -- Python-safe expression for simpleeval.
    -- Required when evaluation_mode = 'expression'.

    llm_prompt          TEXT         NULL,
    -- Instruction for Claude.
    -- Required when evaluation_mode = 'llm'.

    severity            VARCHAR(10)  NOT NULL DEFAULT 'high',
    -- 'critical', 'high', 'medium', 'low'

    is_blocking         BOOLEAN      NOT NULL DEFAULT TRUE,
    -- For escalation/validation: blocks pipeline if true
    -- For supplier_compliance: always excludes the supplier

    breaks_completeness BOOLEAN      NOT NULL DEFAULT FALSE,
    -- For validation rules only: if true, sets completeness=fail

    action_type         VARCHAR(30)  NOT NULL DEFAULT 'escalate',
    -- 'escalate'         — create an escalation entry
    -- 'validation_issue' — create a validation issue
    -- 'exclude_supplier' — exclude the supplier from the shortlist
    -- 'informational'    — log to audit trail only

    action_target       VARCHAR(120) NULL,
    -- For escalate: who to escalate to
    -- For others: null

    trigger_template    TEXT         NOT NULL,
    -- Human-readable message template with {field} placeholders.
    -- For LLM rules: overridden by Claude's justification.

    action_required     TEXT         NULL,
    -- For validation_issue: what the requester must do

    field_ref           VARCHAR(50)  NULL,
    -- For validation rules: the field this rule checks

    description         TEXT         NULL,
    -- Admin-facing description

    enabled             BOOLEAN      NOT NULL DEFAULT TRUE,
    sort_order          INT          NOT NULL DEFAULT 100,
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 4. Rule Mapping — Every Existing Rule as a Row

### 4a. Escalation Rules (rule_type: `escalation`, scope: `request`)

| rule_id | evaluation_mode | condition_expr | action_target | is_blocking | severity | trigger_template |
|---|---|---|---|---|---|---|
| ER-001 | expression | `missing_required_information == True` | Requester Clarification | true | critical | Missing required request information (budget, quantity, or category). |
| ER-002 | expression | `preferred_supplier_restricted == True` | Procurement Manager | true | critical | Preferred supplier is restricted for this request context. |
| ER-003 | expression | `strategic_tier == True` | Head of Strategic Sourcing | false | medium | Contract value falls into strategic sourcing approval tier. |
| ER-004 | expression | `not missing_required_information and not has_compliant_priceable_supplier` | Head of Category | true | critical | No compliant supplier with valid pricing found. |
| ER-005 | expression | `not missing_required_information and has_residency_compatible_supplier == False` | Security and Compliance Review | true | critical | Data residency requirement cannot be satisfied. |
| ER-006 | expression | `not missing_required_information and single_supplier_capacity_risk == True` | Sourcing Excellence Lead | true | high | Only one supplier can satisfy quantity/capacity constraints. |
| ER-007 | expression | `category_label == "Marketing / Influencer Campaign Management"` | Marketing Governance Lead | true | high | Brand-safety review required for influencer campaigns. |
| ER-008 | expression | `preferred_supplier_unregistered_usd == True` | Regional Compliance Lead | true | critical | Preferred supplier not registered for delivery countries in USD request. |
| ER-AT | expression | `threshold_quotes_required >= 2 and has_single_supplier_instruction == True` | *(dynamic)* | true | critical | Requester instruction conflicts with {threshold_id}: {threshold_quotes_required} quotes required. |

Notes:
- **ER-003** requires a pre-computed `strategic_tier` boolean added to the request context (derived from checking if threshold_managers or deviation_approvers contains "cpo" or "head of strategic sourcing").
- **ER-AT** `action_target` is dynamic (comes from `threshold_deviation_approvers[0]` or `threshold_managers[0]`). The evaluator handles this as a special case after expression evaluation.
- **ER-AT** also requires `has_single_supplier_instruction` as a pre-computed boolean (the multi-language regex check runs before expression evaluation).

### 4b. Validation Rules (rule_type: `validation`, scope: `request`)

| rule_id | evaluation_mode | condition_expr | severity | breaks_completeness | field_ref | trigger_template | action_required |
|---|---|---|---|---|---|---|---|
| VR-001 | expression | `category_l1 is None or category_l1 == ""` | critical | true | category_l1 | category_l1 is missing. | Requester must specify L1 category. |
| VR-002 | expression | `category_l2 is None or category_l2 == ""` | critical | true | category_l2 | category_l2 is missing. | Requester must specify L2 category. |
| VR-003 | expression | `currency is None or currency == ""` | critical | true | currency | currency is missing. | Requester must specify currency. |
| VR-004 | expression | `budget_amount is None` | high | false | budget_amount | budget_amount is null. Pipeline continues with degraded capability. | Requester should provide a budget. |
| VR-005 | expression | `quantity is None` | high | false | quantity | quantity is null. Pricing comparison limited to quality-only ranking. | Requester should provide a quantity. |
| VR-006 | expression | `required_by_date is None or required_by_date == ""` | medium | false | required_by_date | required_by_date is not specified. | Requester should specify a delivery date. |
| VR-007 | expression | `delivery_countries_count == 0` | high | false | delivery_countries | No delivery countries specified. | Requester must specify at least one delivery country. |
| VR-008 | expression | `days_until_required is not None and days_until_required < 0` | critical | false | required_by_date | Required by date is in the past ({days_until_required} days ago). | Requester must provide a future delivery date. |
| VR-009 | expression | `budget_amount is not None and quantity is not None and min_supplier_total is not None and budget_amount < min_supplier_total` | critical | false | budget_amount | Budget of {currency} {budget_amount} cannot cover {quantity} units. Minimum: {currency} {min_supplier_total}. | Requester must increase budget or reduce quantity. |
| VR-010 | expression | `days_until_required is not None and days_until_required >= 0 and min_expedited_lead_time is not None and days_until_required < min_expedited_lead_time` | high | false | required_by_date | All suppliers' expedited lead times exceed the {days_until_required}-day window. | Requester must confirm whether the delivery date is a hard constraint. |
| VR-LLM | llm | *(null)* | varies | false | *(null)* | *(overridden by Claude)* | Review and resolve the contradiction before proceeding. |

**VR-LLM** `llm_prompt`:

> You are a procurement validation assistant. You receive a purchase request with both free-text and structured fields. Your job is to find CONTRADICTIONS between the text and the structured data, and to extract any explicit requester instructions.
>
> RULES:
> 1. Only flag two issue types: "missing_info" and "contradictory"
> 2. A contradiction exists ONLY when: quantity in text differs from quantity field, budget in text differs from budget_amount field, date in text differs from required_by_date field, currency in text differs from currency field, category in text clearly doesn't match category_l1/category_l2
> 3. These are NOT contradictions: preferred_supplier_mentioned vs incumbent_supplier, urgency language without a specific date, policy concerns expressed in text
> 4. Be CONSERVATIVE. When in doubt, do NOT flag.
> 5. The request_text may be in any language (en, fr, de, es, pt, ja). Analyze it in its original language.
> 6. Extract any explicit requester instruction (e.g., "no exception", "single supplier only", "must use X").

### 4c. Supplier Compliance Rules (rule_type: `supplier_compliance`, scope: `supplier`)

| rule_id | evaluation_mode | condition_expr | trigger_template |
|---|---|---|---|
| CR-001 | expression | `req_data_residency_constraint == True and sup_data_residency_supported == False` | Does not support data residency in {delivery_country}. |
| CR-002 | expression | `req_quantity is not None and sup_capacity_per_month is not None and req_quantity > sup_capacity_per_month` | Quantity {req_quantity} exceeds monthly capacity {sup_capacity_per_month}. |
| CR-003 | expression | `sup_preferred_supplier == False and sup_risk_score > 30` | Risk score {sup_risk_score} exceeds threshold (30). Excluded on risk grounds. |
| CR-004 | hardcoded | *(null)* | Restricted: {restriction_reason}. |

CR-004 stays `hardcoded` because it requires an async HTTP call to the Org Layer's `check-restricted` endpoint. Alternative: pre-fetch all restriction statuses in batch before the rule loop and add `sup_is_restricted` + `sup_restriction_reason` to the supplier context, then convert to `expression` mode with `sup_is_restricted == True`.

### 4d. Pipeline Escalation Rules (rule_type: `pipeline_escalation`, scope: `pipeline`)

| rule_id | evaluation_mode | condition_expr | action_target | trigger_template |
|---|---|---|---|---|
| PE-001 | expression | `has_budget_insufficient_issue == True and min_ranked_total is not None` | Requester Clarification | Budget insufficient. Budget {currency} {budget_amount}, minimum total {currency} {min_ranked_total}. |
| PE-002 | expression | `has_lead_time_issue == True` | Head of Category | Lead time infeasible: delivery in {days_until_required} days, fastest supplier needs {min_expedited_lead_time} days. |
| PE-003 | expression | `req_data_residency_constraint == True and compliant_residency_count == 0 and compliant_count > 0` | Data Protection Officer | No compliant supplier supports data residency in {country}. |
| PE-004 | expression | `compliant_count == 0 and initial_supplier_count > 0` | Head of Category | No supplier remains after compliance checks. |
| PE-005 | expression | `preferred_supplier_excluded_restricted == True` | Procurement Manager | Preferred supplier was excluded as restricted. |
| PE-LLM | llm | *(null)* | Procurement Manager | *(overridden by Claude)* |

**PE-LLM** `llm_prompt`:

> The requester gave this instruction: "{requester_instruction}". Does this instruction conflict with the procurement policy that requires {threshold_quotes_required} quotes for this value tier? Only return true if there is a clear conflict between the requester's stated preference and the policy requirement.

---

## 5. Evaluation Contexts

Each `scope` defines what fields are available for expression evaluation or LLM context building.

### 5a. Request Context (scope: `request`)

Used by validation rules and escalation rules.

```python
request_context = {
    # Request fields
    "category_l1": str | None,
    "category_l2": str | None,
    "currency": str | None,
    "budget_amount": float | None,
    "quantity": int | None,
    "required_by_date": str | None,
    "days_until_required": int | None,
    "delivery_countries_count": int,
    "data_residency_constraint": bool,
    "esg_requirement": bool,
    "request_text": str,
    "request_language": str,

    # Computed booleans (from EscalationRuleInput)
    "missing_required_information": bool,
    "preferred_supplier_restricted": bool,
    "has_compliant_priceable_supplier": bool,
    "has_residency_compatible_supplier": bool | None,
    "single_supplier_capacity_risk": bool,
    "preferred_supplier_unregistered_usd": bool,
    "strategic_tier": bool,                    # NEW: pre-computed
    "has_single_supplier_instruction": bool,   # NEW: pre-computed from regex

    # Threshold context
    "threshold_id": str | None,
    "threshold_quotes_required": int,
    "category_label": str,

    # Pricing aggregates (for VR-009, VR-010)
    "min_supplier_total": float | None,
    "min_expedited_lead_time": int | None,
}
```

### 5b. Supplier Context (scope: `supplier`)

Used by compliance rules. Built per-supplier.

```python
supplier_context = {
    # Request fields (prefixed with req_)
    "req_data_residency_constraint": bool,
    "req_quantity": int | None,
    "req_category_l1": str | None,
    "req_category_l2": str | None,
    "delivery_country": str,

    # Supplier fields (prefixed with sup_)
    "sup_supplier_id": str,
    "sup_supplier_name": str,
    "sup_preferred_supplier": bool,
    "sup_data_residency_supported": bool,
    "sup_capacity_per_month": int | None,
    "sup_risk_score": int,
    "sup_esg_score": int,
    "sup_quality_score": int,
    "sup_is_restricted": bool,              # NEW: pre-fetched from Org Layer
    "sup_restriction_reason": str | None,   # NEW
}
```

### 5c. Pipeline Context (scope: `pipeline`)

Used by pipeline escalation rules. Built after validation + compliance + ranking.

```python
pipeline_context = {
    # From validation
    "has_budget_insufficient_issue": bool,
    "has_lead_time_issue": bool,
    "days_until_required": int | None,
    "min_expedited_lead_time": int | None,

    # From compliance
    "compliant_count": int,
    "initial_supplier_count": int,
    "compliant_residency_count": int,
    "preferred_supplier_excluded_restricted": bool,

    # From ranking
    "min_ranked_total": float | None,

    # From request
    "req_data_residency_constraint": bool,
    "budget_amount": float | None,
    "currency": str,
    "country": str,
    "requester_instruction": str | None,
    "threshold_quotes_required": int,
}
```

---

## 6. LLM Evaluation

When `evaluation_mode == "llm"`:

### 6a. Flow

1. The evaluator serializes the relevant context dict into a readable text summary.
2. Calls Claude via the existing `LLMClient.structured_call()`:
   - **System prompt**: the rule's `llm_prompt` field
   - **User prompt**: the serialized context
   - **Response model**:

```python
class LLMRuleResult(BaseModel):
    triggered: bool
    justification: str
    confidence: float  # 0.0 to 1.0
```

3. If Claude fails (timeout, error, parse failure): the rule is treated as **not triggered** and a warning is logged to the audit trail.
4. The `justification` replaces the `trigger_template` in the output, so the escalation/validation issue has a natural-language explanation written by Claude.
5. The audit trail records: `rule_id`, `evaluation_mode=llm`, `triggered=True/False`, `justification`, `confidence`, `latency_ms`.

### 6b. Concurrency

All LLM rules within the same step are evaluated in parallel using `asyncio.gather()`, capped at 5 concurrent calls to avoid rate limits.

### 6c. Fallback

If the LLM is not configured (`ANTHROPIC_API_KEY` is empty), all `evaluation_mode: llm` rules are skipped and a warning is logged. The system remains fully functional with just the expression-based rules.

---

## 7. File Changes

### Org Layer

| File | Changes |
|---|---|
| `database_init/migrate.py` | Add `procurement_rules` table DDL. Seed all rules with expressions. Keep existing `escalation_rules` table for backward compatibility but mark it as legacy. |
| `backend/organisational_layer/requirements.txt` | Add `simpleeval` |
| `backend/organisational_layer/app/models/policies.py` | Add `ProcurementRule` ORM model |
| `backend/organisational_layer/app/schemas/policies.py` | Add `ProcurementRuleOut`, `ProcurementRuleCreate`, `ProcurementRuleUpdate` schemas |
| `backend/organisational_layer/app/routers/rules.py` | Add full CRUD for procurement rules (GET list with filters, GET by id, POST with expression validation, PUT, DELETE, GET context/{scope}) |
| `backend/organisational_layer/app/services/escalations.py` | Replace 8 hardcoded `if` blocks with generic evaluator loop. Add `strategic_tier` and `has_single_supplier_instruction` to `EscalationRuleInput`. Keep AT-conflict as hardcoded special case. |
| `backend/organisational_layer/app/services/rule_evaluator.py` | **New file**: `evaluate_rules(rules, context)` function using `simpleeval` for expression mode |

### Logical Layer

| File | Changes |
|---|---|
| `backend/logical_layer/app/clients/organisational.py` | New method `get_procurement_rules(scope, rule_type)` to fetch rules from Org Layer |
| `backend/logical_layer/app/services/rule_evaluator.py` | **New file**: async version that handles `expression`, `llm`, and `hardcoded` modes |
| `backend/logical_layer/app/pipeline/steps/validate.py` | Replace hardcoded validation checks with rules fetched from Org Layer (scope=request, rule_type=validation). Keep LLM contradiction detection as VR-LLM rule. |
| `backend/logical_layer/app/pipeline/steps/comply.py` | Replace hardcoded checks with rules fetched from Org Layer (scope=supplier, rule_type=supplier_compliance). Pre-fetch restriction status for all suppliers. |
| `backend/logical_layer/app/pipeline/steps/escalate.py` | Replace `_discover_pipeline_issues()` with rules (scope=pipeline, rule_type=pipeline_escalation). Merge with Org Layer escalations unchanged. |

### Not Changed

| File | Why |
|---|---|
| `backend/logical_layer/app/pipeline/steps/rank.py` | Ranking is a scoring algorithm, not a rule |
| `backend/logical_layer/app/pipeline/steps/policy.py` | Policy evaluation assembles data, does not make pass/fail decisions |
| `backend/logical_layer/app/pipeline/steps/assemble.py` | Assembly logic, not rules |
| `backend/logical_layer/app/pipeline/steps/recommend.py` | Recommendation is derived from escalations, not a rule itself |
| `backend/logical_layer/app/pipeline/steps/fetch.py` | Data fetching, not rules |

---

## 8. New API Endpoints

On the Org Layer (`/api/rules/procurement`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/rules/procurement` | List all rules. Query params: `rule_type`, `scope`, `enabled`, `evaluation_mode` |
| GET | `/api/rules/procurement/{rule_id}` | Get a single rule |
| POST | `/api/rules/procurement` | Create a new rule. Validates expression at write time. |
| PUT | `/api/rules/procurement/{rule_id}` | Update an existing rule |
| DELETE | `/api/rules/procurement/{rule_id}` | Delete a rule |
| GET | `/api/rules/procurement/context/{scope}` | Returns the list of available field names and their types for a given scope (for UI expression builders) |

Expression validation on POST/PUT: run `simple_eval(condition_expr, names=DUMMY_CONTEXT)` with safe test values. Return 422 if it fails.

---

## 9. Execution Phases

### Phase 1: Schema + Evaluator (Org Layer only)

1. Add `procurement_rules` table to `migrate.py`
2. Add `ProcurementRule` model + schemas
3. Create `rule_evaluator.py` with `evaluate_rules()`
4. Refactor `escalations.py` to use the evaluator
5. Add CRUD endpoints to `rules.py`
6. Seed all 8 ER rules + AT-conflict as expressions
7. **Test**: existing escalation behavior unchanged

### Phase 2: Validation Rules (Logical Layer)

8. Seed VR-001 through VR-010 + VR-LLM in the migrator
9. Add `get_procurement_rules()` to `OrganisationalClient`
10. Create Logical Layer `rule_evaluator.py` (async, supports LLM mode)
11. Refactor `validate.py` to fetch rules and evaluate
12. **Test**: existing validation behavior unchanged

### Phase 3: Compliance Rules (Logical Layer)

13. Seed CR-001 through CR-004 in the migrator
14. Pre-fetch restriction status in the comply step
15. Refactor `comply.py` to fetch rules and evaluate per-supplier
16. **Test**: existing compliance behavior unchanged

### Phase 4: Pipeline Escalations (Logical Layer)

17. Seed PE-001 through PE-005 + PE-LLM in the migrator
18. Refactor `escalate.py` to fetch rules and evaluate
19. **Test**: existing escalation behavior unchanged

### Phase 5: Demo-Ready

20. Test adding a new rule via API and seeing it fire
21. Test adding an LLM rule and seeing Claude's justification in the audit trail
22. Update `CLAUDE.md` and `AGENTS.md` with new rule system documentation

---

## 10. Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| `simpleeval` cannot handle list operations needed for ER-003 | ER-003 would not fire | Pre-compute `strategic_tier` boolean before expression evaluation and add to context |
| LLM rules are slow (1-2s each) | Pipeline latency increases | Evaluate all LLM rules in parallel with `asyncio.gather`. Cap at 5 concurrent. |
| LLM rules are non-deterministic | Same input could produce different results | Log Claude's justification + confidence in audit trail. Flag LLM-evaluated results differently in the UI. |
| CR-004 restriction check requires HTTP call | Cannot be an expression | pre-fetch restriction status in batch and add to supplier context |
| Bad expression saved to DB causes runtime failure | Rule silently fails | Validate expressions at write time (POST/PUT). On runtime error, treat as not triggered + log warning. |
| Breaking existing behavior | Pipeline produces different results | Each phase ends with regression testing. Expression translations are direct 1:1 mappings of existing `if` blocks. |
| `simpleeval` security | Malicious expressions | Use `simple_eval()` with explicit `names=context` and no `functions` parameter. `simpleeval` blocks `__import__`, builtins, and attribute access by default. |
| Schema migration on production DB | Existing data lost | DB is bootstrapped from scratch via `migrate.py` each deployment. No ALTER TABLE needed — just update DDL. |
| Org Layer and Logical Layer rule evaluation can drift | Different results from same rule | Org Layer evaluator is synchronous (no LLM support). Logical Layer evaluator is async (supports LLM). Both use the same `simpleeval` library and context structure. |
