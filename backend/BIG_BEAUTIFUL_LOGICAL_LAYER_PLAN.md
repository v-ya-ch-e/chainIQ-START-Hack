# BIG BEAUTIFUL LOGICAL LAYER PLAN

The authoritative design document for the Logical Layer v2 -- the procurement decision engine for ChainIQ @ START Hack 2026. This replaces `PLAN.md` and `backend/PAST_EXPERIENCE.md`.

---

## Table of Contents

1. [Challenge Recap](#1-challenge-recap)
2. [Architecture Overview](#2-architecture-overview)
3. [File Structure](#3-file-structure)
4. [Pipeline Flow](#4-pipeline-flow)
5. [Step-by-Step Specification](#5-step-by-step-specification)
6. [Escalation Handling](#6-escalation-handling)
7. [Confidence Scoring](#7-confidence-scoring)
8. [Logging Strategy](#8-logging-strategy)
9. [API Endpoints](#9-api-endpoints)
10. [Output Format](#10-output-format)
11. [Data Normalization](#11-data-normalization)
12. [LLM Integration](#12-llm-integration)
13. [Org Layer Dependencies](#13-org-layer-dependencies)
14. [Frontend Contract](#14-frontend-contract)
15. [Lessons from v1](#15-lessons-from-v1)
16. [Deployment](#16-deployment)

---

## 1. Challenge Recap

### What the System Must Do

Given a free-text purchase request, the agent must:

1. **Parse** -- extract structured fields (category, quantity, budget, delivery constraints)
2. **Validate** -- detect missing info, contradictions, budget/quantity mismatches
3. **Apply Policy** -- determine approval tier, required quotes, check preferred/restricted suppliers, enforce category and geography rules
4. **Find Suppliers** -- filter to compliant suppliers covering the right category, region, and currency
5. **Price** -- look up correct pricing tier based on quantity, calculate total cost (standard and expedited)
6. **Rank** -- score suppliers on price, quality, risk, ESG, lead time feasibility
7. **Explain** -- produce human-readable rationale for every inclusion, exclusion, and ranking decision
8. **Escalate** -- when the agent cannot make a compliant autonomous decision, trigger the correct escalation rule and name the target

### Judging Criteria

| Criteria | Weight | What Wins |
|----------|--------|-----------|
| Robustness & Escalation Logic | **25%** | Handle every edge case. Never output a confident wrong answer. Escalation accuracy > recommendation accuracy. |
| Feasibility | **25%** | Clean architecture, production-grade code, realistic deployment story. |
| Reachability | **20%** | Solve the actual procurement problem end-to-end, not a toy version. |
| Creativity | **20%** | Confidence scoring, historical context, interactive clarification, audit depth. |
| Visual Design | **10%** | Clean and clear UI. Already covered by the frontend. |

**Key insight**: *"A system that produces confident wrong answers will score lower than one that correctly identifies uncertainty and escalates."* Escalation correctness is the single most important capability.

### Critical Data Quirks

These are baked into the dataset by design. The pipeline must handle all of them:

| Quirk | Detail |
|-------|--------|
| Inconsistent policy schema | EUR/CHF thresholds use `min_amount`/`max_amount`/`min_supplier_quotes`/`managed_by`/`deviation_approval_required_from`. USD uses `min_value`/`max_value`/`quotes_required`/`approvers`/`policy_note`. The Org Layer normalizes this at the DB level. |
| Supplier rows are per-category | SUP-0001 (Dell) appears 5 times in `suppliers.csv`. Join on `(supplier_id, category_l1, category_l2)`. |
| `is_restricted` is unreliable | The boolean in `suppliers.csv` is a hint. Always check `policies.json` restricted_suppliers for actual scope (global, country-scoped, value-conditional). |
| Quantity can be null or contradictory | Some requests have `quantity: null` or a `quantity` field that conflicts with `request_text`. |
| Non-English requests | Languages: `en`, `fr`, `de`, `es`, `pt`, `ja`. The `request_text` is in the stated language. |
| 124 requests have no historical awards | Intentional. Not a data error. |
| `service_regions` is semicolon-delimited | Split on `;`, not `,`. |
| Conditional restrictions | Some suppliers restricted only above a value threshold or only in specific countries. |
| Preferred supplier mismatches | Some requests name a preferred supplier registered for a different category or not covering the delivery country. |
| Budget as string | Org Layer returns `budget_amount` as a string (MySQL decimal serialization). Must `float()`. |
| Quantity as string | Arrives as `"240.0"`. Must `int(float())`. |

---

## 2. Architecture Overview

### Topology

```
Frontend (Next.js :3000)
  |
  | Next.js rewrites /api/* -->
  |
Organisational Layer (FastAPI :8000)        <-- Data + governance
  |                                              CRUD, analytics, escalation engine,
  | pymysql                                      pipeline logging, audit logging
  |
MySQL 8.4 (AWS RDS)                         <-- 25 normalized tables
  
Logical Layer (FastAPI :8080)               <-- Decision engine (THIS SERVICE)
  |                                              Pure Python pipeline, no n8n
  | async httpx                                  Calls Org Layer for all data
  |                                              Uses Anthropic Claude for LLM reasoning
  | anthropic SDK
  |
Claude claude-sonnet-4-6                    <-- LLM (parsing + prose only)
```

### Design Principles

1. **No n8n**. The pipeline runs entirely inside this FastAPI service. Each step is an async Python function. No external orchestrator, no workflow engine, no YAML configs.

2. **Org Layer owns all data**. The Logical Layer never touches MySQL. Every data read goes through the Org Layer's REST API. Every log write goes through the Org Layer's logging endpoints.

3. **LLM for prose, deterministic code for decisions**. Policy evaluation, compliance checks, escalation logic, ranking -- all deterministic Python. Claude is used only for: contradiction detection in free text, requester instruction extraction, recommendation prose, and enrichment of validation issues with severity/action descriptions.

4. **Single HTTP client**. One shared `httpx.AsyncClient` created at app startup, passed via dependency injection. No `urllib`, no hardcoded IPs, no duplicate client instances.

5. **Type-safe pipeline**. Pydantic models for the input/output of every pipeline step. Field name mismatches caught at development time, not production.

6. **Fire-and-forget logging**. Pipeline logging and audit logging never block or crash the pipeline. If the Org Layer is unreachable, the pipeline continues and the logs are lost.

7. **Escalate over guess**. When uncertain, the system escalates. A false escalation is always better than a false clearance.

---

## 3. File Structure

```
backend/logical_layer/
  app/
    __init__.py
    main.py                  # FastAPI app, lifespan (creates httpx + anthropic clients)
    config.py                # Pydantic Settings: ORGANISATIONAL_LAYER_URL, ANTHROPIC_API_KEY, MODEL
    dependencies.py          # FastAPI dependency injection for clients

    clients/
      __init__.py
      organisational.py      # OrganisationalClient -- async httpx wrapper for all Org Layer calls
      llm.py                 # LLMClient -- async Anthropic wrapper with structured output

    models/
      __init__.py
      common.py              # Shared types: RequestData, SupplierData, PricingData, etc.
      pipeline_io.py         # Pydantic models for every pipeline step input/output
      output.py              # Final output model matching example_output.json

    routers/
      __init__.py
      pipeline.py            # POST /api/pipeline/process, POST /api/pipeline/process-batch
      steps.py               # Individual step endpoints for debugging/testing
      status.py              # GET /api/pipeline/status/{request_id}, result, runs, audit

    pipeline/
      __init__.py
      runner.py              # PipelineRunner -- orchestrates all steps, manages logging
      logger.py              # PipelineLogger -- audit log + step-level telemetry via Org Layer

      steps/
        __init__.py
        fetch.py             # Step 1: Fetch request + overview data
        validate.py          # Step 2: Validate request (deterministic + LLM)
        filter.py            # Step 3: Filter & enrich suppliers
        comply.py            # Step 4: Compliance checks per supplier
        rank.py              # Step 5: Rank suppliers by true cost
        policy.py            # Step 6: Evaluate procurement policy
        escalate.py          # Step 7: Compute & merge escalations
        recommend.py         # Step 8: Generate recommendation (deterministic + LLM)
        assemble.py          # Step 9: Assemble final output (+ LLM enrichment)

    utils.py                 # Centralized normalization helpers

  Dockerfile
  requirements.txt
  .env.example
```

### Module Responsibilities

| Module | Responsibility | Touches LLM? | Touches Org Layer? |
|--------|---------------|---------------|-------------------|
| `clients/organisational.py` | HTTP calls to Org Layer. Methods for every endpoint used. | No | Yes (all reads + log writes) |
| `clients/llm.py` | Anthropic API calls with structured output. Retry logic. | Yes | No |
| `pipeline/runner.py` | Orchestrates steps 1-9. Manages parallelism. Handles early exit on invalid requests. | No | No (delegates to steps) |
| `pipeline/logger.py` | Wraps Org Layer logging endpoints. Fire-and-forget. Truncation. | No | Yes (log writes only) |
| `pipeline/steps/fetch.py` | Calls `request-overview` + `escalations/by-request` in parallel. | No | Yes |
| `pipeline/steps/validate.py` | Deterministic field checks + LLM contradiction detection. | Yes | No |
| `pipeline/steps/filter.py` | Starts from overview's compliant suppliers, enriches with names + pricing. | No | No (uses fetched data) |
| `pipeline/steps/comply.py` | Per-supplier restriction, delivery, residency checks. | No | Maybe (targeted check-restricted calls) |
| `pipeline/steps/rank.py` | True-cost ranking formula. | No | No |
| `pipeline/steps/policy.py` | Approval tier, preferred/restricted analysis, rules. | No | No (uses fetched data) |
| `pipeline/steps/escalate.py` | Merges Org Layer escalations with pipeline-discovered issues. | No | No |
| `pipeline/steps/recommend.py` | Deterministic status + LLM prose. | Yes | No |
| `pipeline/steps/assemble.py` | Final output assembly + LLM enrichment of issues and supplier notes. | Yes | No |
| `utils.py` | `normalize_delivery_countries()`, `normalize_scenario_tags()`, `coerce_budget()`, `coerce_quantity()`, `COUNTRY_TO_REGION` dict. | No | No |

---

## 4. Pipeline Flow

### High-Level Diagram

```
Input: { "request_id": "REQ-000004" }
                |
    +-----------v-----------+
    |  Step 1: FETCH        |   GET /api/analytics/request-overview/{id}
    |  + OVERVIEW           |   GET /api/escalations/by-request/{id}     (parallel)
    +-----------+-----------+
                |
    +-----------v-----------+
    |  Step 2: VALIDATE     |   Deterministic checks + LLM contradiction detection
    |                       |   Output: completeness, issues[], interpretation
    +-----------+-----------+
                |
           [BRANCH]
          /         \
    missing_required  valid
         |              |
   format_invalid   +---v---+
   -> return early  | Step 3: FILTER      |   Enrich compliant_suppliers from overview
                    +---+---+
                        |
                    +---v---+
                    | Step 4: COMPLY      |   Per-supplier compliance checks
                    +---+---+
                        |
                    +---v---+
                    | Step 5: RANK        |   True-cost ranking
                    +---+---+
                        |
              +---------+---------+
              |                   |
        +-----v-----+    +-------v-------+
        | Step 6:    |    | Step 7:       |    (parallel)
        | POLICY     |    | ESCALATIONS   |
        +-----+------+    +-------+-------+
              |                   |
              +---------+---------+
                        |
                  +-----v------+
                  | Step 8:    |   Deterministic status + LLM prose
                  | RECOMMEND  |
                  +-----+------+
                        |
                  +-----v------+
                  | Step 9:    |   Combine all + LLM enrichment
                  | ASSEMBLE   |
                  +-----+------+
                        |
                     Output
```

### Parallelism Strategy

| Phase | Steps | Why Parallel |
|-------|-------|-------------|
| Fetch | 1a (overview) + 1b (escalations) | Independent Org Layer calls |
| Sequential | 2 -> 3 -> 4 -> 5 | Each depends on the prior step's output |
| Parallel | 6 (policy) + 7 (escalation merge) | Both need step 5 output, neither needs the other |
| Sequential | 8 -> 9 | Recommendation needs escalations; assembly needs everything |

Implementation: `asyncio.gather()` for parallel phases, `await` for sequential.

---

## 5. Step-by-Step Specification

### Step 1: FETCH & OVERVIEW

**Purpose**: Gather all data the pipeline needs in minimal HTTP calls.

**Calls (parallel)**:
- `GET /api/analytics/request-overview/{request_id}` -- returns request details, compliant suppliers, pricing tiers, applicable rules, approval tier, historical awards
- `GET /api/escalations/by-request/{request_id}` -- returns computed escalations from Org Layer engine

**Output** (`FetchResult`):
```python
class FetchResult(BaseModel):
    request: RequestData           # Full request object
    compliant_suppliers: list[SupplierData]  # Already filtered by category + country
    pricing: list[PricingData]     # Pricing tiers for each compliant supplier
    applicable_rules: RulesData    # Category rules + geography rules
    approval_tier: ApprovalTierData | None  # Null if budget is null
    historical_awards: list[AwardData]
    org_escalations: list[EscalationData]   # From Org Layer engine
```

**Audit logs**:
- `category: "data_access"`, `level: "info"` -- "Fetched request overview: {supplier_count} compliant suppliers, {pricing_count} pricing tiers, {award_count} historical awards"

**Error handling**: If the request is not found (404), return immediately with a structured error. If the Org Layer is unreachable, fail the pipeline with `status: "error"`.

---

### Step 2: VALIDATE

**Purpose**: Check the request for completeness, internal consistency, and contradictions.

**Phase A -- Deterministic checks** (no LLM):

| Check | Type | Severity |
|-------|------|----------|
| `category_l1` is null | `missing_info` | critical |
| `category_l2` is null | `missing_info` | critical |
| `budget_amount` is null | `missing_info` | high |
| `quantity` is null | `missing_info` | high |
| `currency` is null | `missing_info` | critical |
| `required_by_date` is null | `missing_info` | medium |
| `delivery_countries` is empty | `missing_info` | high |
| `days_until_required` < 0 | `lead_time_infeasible` | critical |
| Budget insufficient for any supplier at min pricing | `budget_insufficient` | critical |
| Lead time infeasible at all suppliers (even expedited) | `lead_time_infeasible` | high |

Budget and lead time checks use the pricing data from Step 1 to compute actual minimum costs and minimum lead times across all compliant suppliers.

**Phase B -- LLM contradiction detection**:

Call Claude with the request_text + structured fields. The prompt asks for:
- Contradictions between `request_text` and structured fields (quantity, budget, date, currency, category)
- Extraction of `requester_instruction` (explicit instructions like "no exception", "single supplier only")

**What IS a contradiction**:
- Quantity in text differs from `quantity` field
- Budget in text differs from `budget_amount` field
- Date in text differs from `required_by_date` field
- Currency in text differs from `currency` field
- Category in text doesn't match `category_l1`/`category_l2`

**What is NOT a contradiction**:
- `preferred_supplier_mentioned` vs `incumbent_supplier` (intentionally different)
- Urgency language without a specific date
- Policy concerns expressed in text

**Output** (`ValidationResult`):
```python
class ValidationResult(BaseModel):
    completeness: bool             # True if no missing_required issues
    issues: list[ValidationIssue]  # All issues found
    request_interpretation: RequestInterpretation  # Structured interpretation
    llm_used: bool                 # Whether LLM was called
    llm_fallback: bool             # Whether LLM failed and fallback was used
```

**Audit logs**: One entry per issue found (`category: "validation"`), with `level` matching severity.

**Branch**: If `completeness` is `False` (missing critical required fields like category_l1, category_l2, or currency), format an invalid response and return early. Missing budget or quantity alone does NOT trigger early exit -- the pipeline continues with degraded capability (no pricing, quality-only ranking).

---

### Step 3: FILTER & ENRICH SUPPLIERS

**Purpose**: Take the compliant suppliers from the overview endpoint and enrich them with all metadata needed for subsequent steps.

**Input**: `FetchResult.compliant_suppliers` + `FetchResult.pricing`

**Logic**:
1. Start with compliant suppliers from overview (already filtered by category + delivery country, already excluding restricted suppliers)
2. For each supplier, attach:
   - `supplier_name` (from overview data)
   - Pricing tier (match from `FetchResult.pricing` by `supplier_id`)
   - `preferred_supplier` flag (from overview data)
   - `quality_score`, `risk_score`, `esg_score` (from overview data)
   - `data_residency_supported` (from overview data)
3. Suppliers with no pricing tier for the requested quantity are included but flagged as `no_pricing`
4. Log every inclusion with supplier details

**Output** (`FilterResult`):
```python
class FilterResult(BaseModel):
    enriched_suppliers: list[EnrichedSupplier]
    suppliers_without_pricing: list[str]  # supplier_ids with no tier
```

**Audit logs**: One entry per supplier (`category: "supplier_filter"`):
- Included: "Included SUP-0001 (Dell Enterprise Europe): covers IT > Docking Stations in DE, pricing tier 100-499 units"
- No pricing: "SUP-0003 (Lenovo): no pricing tier covers quantity 240 in EU region"

---

### Step 4: CHECK COMPLIANCE

**Purpose**: Apply detailed compliance rules to each enriched supplier.

**Checks per supplier**:

| Check | How | Exclusion Reason |
|-------|-----|-----------------|
| Restriction (global) | `is_restricted` from overview data + cross-check with `GET /api/analytics/check-restricted` for borderline cases | "Restricted: {restriction_reason}" |
| Restriction (country-scoped) | Check if restriction scope includes the delivery country | "Restricted in {country}: {reason}" |
| Restriction (value-conditional) | Parse conditional threshold (e.g., "only below EUR 75K"), compare with estimated contract value | "Restricted above {currency} {amount}: {reason}" |
| Delivery country coverage | Check if supplier's service regions include the delivery country | "Does not cover delivery to {country}" |
| Data residency | If `data_residency_constraint` is true, check `data_residency_supported` | "Does not support data residency in {country}" |
| Capacity | If `quantity > capacity_per_month`, flag | "Quantity {qty} exceeds monthly capacity {cap}" |

**Output** (`ComplianceResult`):
```python
class ComplianceResult(BaseModel):
    compliant: list[EnrichedSupplier]
    excluded: list[ExcludedSupplier]  # supplier_id, supplier_name, reason
```

**Audit logs**: One entry per check (`category: "compliance"`). Exclusions at `level: "warn"`.

**Note**: The overview endpoint already filters out clearly restricted suppliers. This step catches edge cases: value-conditional restrictions, capacity constraints, and data residency mismatches that the overview endpoint's simpler filter may not catch.

---

### Step 5: RANK SUPPLIERS

**Purpose**: Rank compliant suppliers by true cost, incorporating quality, risk, and optionally ESG.

**Ranking Formula**:

When quantity is available and pricing exists:
```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100)
```

With ESG requirement (`esg_requirement: true`):
```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100) / (esg_score / 100)
```

Lower `true_cost` = better deal. The `overpayment` field = `true_cost - total_price` (the hidden cost of quality/risk gaps).

When quantity is null: rank by `quality_score` descending (no pricing comparison possible).

**Pricing details per supplier**:
- `unit_price` and `total_price` from the matched pricing tier
- `expedited_unit_price` and `expedited_total` (standard ~8% premium)
- `standard_lead_time_days` and `expedited_lead_time_days`
- `pricing_tier_applied` (e.g., "100-499 units")
- All prices are in the request's currency (the Org Layer returns pricing in the region's currency)

**Output** (`RankResult`):
```python
class RankResult(BaseModel):
    ranked_suppliers: list[RankedSupplier]  # Ordered by true_cost ascending
    ranking_method: str  # "true_cost" or "quality_score"
```

Each `RankedSupplier` includes:
- `rank` (1-based)
- All supplier metadata + pricing + scores
- `true_cost`, `overpayment`
- `preferred` (bool), `incumbent` (bool)
- `covers_delivery_country` (bool)
- `policy_compliant` (bool)

**Audit logs**:
- `category: "pricing"` -- "SUP-0001: tier 100-499, unit EUR 155.00, total EUR 37,200.00"
- `category: "ranking"` -- "SUP-0007 ranked #1: true_cost EUR 43,551.22 (lowest)"

---

### Step 6: EVALUATE POLICY

**Purpose**: Determine which procurement policies apply and how they constrain the decision.

**Sub-evaluations**:

#### 6a. Approval Threshold

From `FetchResult.approval_tier`:
- `rule_applied` (e.g., "AT-002")
- `quotes_required` (1, 2, or 3)
- `approvers` (list of role names)
- `deviation_approval` (who must approve a deviation)
- `basis` (prose explaining why this tier applies)
- `note` (edge case commentary, e.g., budget near a boundary)

If budget is null, determine the tier from the minimum total price across ranked suppliers. Log this as: "Budget is null; using minimum supplier total EUR {amount} for tier determination."

#### 6b. Preferred Supplier Analysis

Check the requester's `preferred_supplier_mentioned`:
- Is the named supplier in the compliant set?
- Is the named supplier actually preferred for this category+region?
- Is the named supplier restricted?
- Does the named supplier cover the delivery country?

Output: `{ supplier, status, is_preferred, covers_delivery_country, is_restricted, policy_note }`

Status values: `"eligible"`, `"not_preferred"`, `"restricted"`, `"wrong_category"`, `"no_coverage"`, `"not_found"`

#### 6c. Restricted Supplier Analysis

For each supplier in the original compliant set (before compliance filtering), document restriction status:
- Not restricted: `{ restricted: false, note: "..." }`
- Restricted: `{ restricted: true, scope: "...", note: "..." }`

#### 6d. Category Rules + Geography Rules

From `FetchResult.applicable_rules`:
- List all category rules that apply (e.g., CR-001: "Minimum 3 quotes required for IT Hardware above 5000 EUR")
- List all geography rules that apply (e.g., GR-001: "All IT procurement in CH must use CH-domiciled suppliers")

**Output** (`PolicyResult`):
```python
class PolicyResult(BaseModel):
    approval_threshold: ApprovalThresholdEval
    preferred_supplier: PreferredSupplierEval
    restricted_suppliers: dict[str, RestrictionEval]
    category_rules_applied: list[RuleRef]
    geography_rules_applied: list[RuleRef]
```

**Audit logs**: `category: "policy"` for each policy applied, with `details: { policy_id, ... }`.

---

### Step 7: COMPUTE ESCALATIONS

**Purpose**: Merge escalations from three sources into a single deduplicated list.

**Source 1: Org Layer computed escalations** (from Step 1)

The Org Layer's escalation engine (`services/escalations.py`) evaluates:

| Rule | Trigger | Escalate To | Blocking |
|------|---------|-------------|----------|
| ER-001 | Missing required info (budget, quantity, category) | Requester Clarification | Yes |
| ER-002 | Preferred supplier is restricted | Procurement Manager | Yes |
| ER-003 | Strategic sourcing approval tier (Head of Strategic Sourcing / CPO) | Head of Strategic Sourcing / CPO | No |
| ER-004 | No compliant supplier with valid pricing | Head of Category | Yes |
| ER-005 | Data residency requirement unsatisfiable | Data Protection Officer | Yes |
| ER-006 | Single supplier capacity risk | Head of Category | Yes |
| ER-007 | Influencer Campaign Management (brand safety) | Head of Marketing | Yes |
| ER-008 | Preferred supplier unregistered for USD delivery scope | Category Manager | Yes |
| AT-xxx | Single-supplier instruction conflicts with multi-quote threshold | Procurement Manager | Yes |

The AT conflict rule detects single-supplier language patterns in `request_text` across 6 languages and checks whether the approval threshold requires multiple quotes.

**Source 2: Pipeline-discovered issues** (from Steps 2-5)

| Condition | Maps To | Trigger Description |
|-----------|---------|-------------------|
| Budget insufficient for all suppliers | ER-001 / ER-004 | "Budget EUR {budget} cannot cover {quantity} units. Minimum total: EUR {min_total}" |
| Lead time infeasible at all suppliers (even expedited) | ER-004 | "Required by {date} ({days}d). All expedited lead times: {min}-{max} days" |
| Data residency not satisfiable by any supplier | ER-005 | "No compliant supplier supports data residency in {country}" |
| Preferred supplier is restricted | ER-002 | "Preferred supplier {name} is restricted: {reason}" |
| All compliant suppliers excluded after compliance | ER-004 | "No supplier remains after compliance checks" |

**Source 3: LLM-detected contradictions** (from Step 2)

| Condition | Maps To | Trigger Description |
|-----------|---------|-------------------|
| Requester instruction conflicts with policy | AT-xxx | "Requester instruction '{instruction}' conflicts with {policy}: {explanation}" |
| Quantity mismatch between text and fields | ER-001 | "Quantity in text ({text_qty}) differs from field ({field_qty})" |

**Merge Logic**:

1. Start with Org Layer escalations as the base set
2. For each pipeline-discovered issue, check if the same `rule_id` already exists:
   - If yes: keep the more specific trigger description (usually the pipeline's, since it has actual numbers)
   - If no: add as a new escalation
3. Assign sequential `escalation_id` values: ESC-001, ESC-002, ...
4. Each escalation carries a `source` field: `"org_layer"`, `"pipeline"`, or `"llm"`

**Output** (`EscalationResult`):
```python
class EscalationResult(BaseModel):
    escalations: list[Escalation]
    has_blocking: bool
    blocking_count: int
    non_blocking_count: int
```

Each `Escalation`:
```python
class Escalation(BaseModel):
    escalation_id: str      # ESC-001, ESC-002, ...
    rule: str               # ER-001, AT-002, etc.
    trigger: str            # Human-readable trigger description
    escalate_to: str        # Target role/person
    blocking: bool
    source: str             # org_layer, pipeline, llm
```

**Audit logs**: `category: "escalation"`, `level: "warn"` for non-blocking, `level: "error"` for blocking.

---

### Step 8: GENERATE RECOMMENDATION

**Purpose**: Determine the recommendation status (deterministic) and generate human-readable reasoning (LLM).

**Deterministic status logic**:

```python
if escalation_result.has_blocking:
    status = "cannot_proceed"
elif escalation_result.non_blocking_count > 0:
    status = "proceed_with_conditions"
else:
    status = "proceed"
```

**Deterministic fields**:
- `preferred_supplier_if_resolved`: the top-ranked supplier from Step 5. If the requester's preferred supplier is in the ranked list and not #1, mention both.
- `minimum_budget_required`: the lowest `total_price` from ranked suppliers (or `None` if quantity is null)
- `minimum_budget_currency`: from the request

**LLM-generated fields**:
- `reason`: 1-3 sentence summary of why the recommendation is what it is. Must reference exact supplier names, prices, and rule IDs.
- `preferred_supplier_rationale`: Why the recommended supplier is preferred. Must compare with alternatives using specific figures.

**LLM prompt context** (passed to Claude):
- Recommendation status and escalation list
- Top 3 ranked suppliers with pricing
- Validation issues
- Request interpretation
- Historical awards (if any) for pattern context

**Deterministic fallback**: If LLM fails, use template-based prose:
- `cannot_proceed`: "{N} blocking issues prevent autonomous award: {issue_list}. All require human resolution."
- `proceed_with_conditions`: "Recommendation to proceed with {supplier_name} (rank 1, {currency} {total}), subject to {condition_list}."
- `proceed`: "Recommend awarding to {supplier_name} at {currency} {total}. {quality/risk summary}."

**Output** (`RecommendationResult`):
```python
class RecommendationResult(BaseModel):
    status: str                      # proceed / proceed_with_conditions / cannot_proceed
    reason: str                      # LLM or template
    preferred_supplier_if_resolved: str | None
    preferred_supplier_rationale: str | None
    minimum_budget_required: float | None
    minimum_budget_currency: str | None
    confidence_score: int            # 0-100, see Section 7
```

**Audit logs**: `category: "recommendation"` -- "Status: cannot_proceed (3 blocking escalations). Confidence: 0%."

---

### Step 9: ASSEMBLE OUTPUT

**Purpose**: Combine all step outputs into the final response matching `example_output.json`.

**LLM enrichment** (two sub-calls):

1. **Enrich validation issues**: For each issue from Step 2, generate:
   - `severity`: critical / high / medium / low (may already be set by deterministic checks; LLM can adjust)
   - `description`: Detailed description with specific numbers from pricing/supplier data
   - `action_required`: What the requester or procurement team must do

2. **Generate supplier recommendation notes**: For each ranked supplier, generate a `recommendation_note`:
   - Must reference exact figures (price, lead time, quality score)
   - Must compare with other suppliers in the shortlist
   - Must note any concerns (lead time infeasible, budget exceeded, etc.)

**Dynamic currency keys**: Supplier shortlist entries use currency-suffixed keys:
```python
f"unit_price_{currency.lower()}": unit_price,    # e.g. unit_price_eur
f"total_price_{currency.lower()}": total_price,  # e.g. total_price_eur
```

**Audit trail assembly**: Built from the pipeline run's audit log data:
- `policies_checked`: all unique `policy_id` values from audit logs with `category: "policy"`
- `supplier_ids_evaluated`: all unique `supplier_id` values from audit logs
- `pricing_tiers_applied`: description of the pricing tier used
- `data_sources_used`: always `["requests.json", "suppliers.csv", "pricing.csv", "policies.json"]` (plus `"historical_awards.csv"` if awards exist)
- `historical_awards_consulted`: bool
- `historical_award_note`: summary of historical awards if present

**Output**: The complete pipeline response (see [Section 10](#10-output-format)).

---

## 6. Escalation Handling

### Philosophy

Escalation accuracy is the single most valuable capability for judging (25% weight). The system must:

1. **Never skip an escalation** that should fire. False negatives are the worst outcome.
2. **Prefer to over-escalate** rather than under-escalate. A false escalation is better than a false clearance.
3. **Provide specific, actionable trigger descriptions**. Generic triggers like "missing info" are insufficient. Say "Budget of EUR 25,199 cannot cover 240 units at minimum price EUR 148.80/unit (total EUR 35,712)".
4. **Name the correct escalation target**. Each rule has a specific target role. Routing to the wrong person is a correctness failure.
5. **Classify blocking vs. non-blocking correctly**. Blocking means the pipeline cannot make an autonomous recommendation. Non-blocking means the recommendation can proceed but requires additional approval.

### Escalation Rule Reference

| Rule | Trigger | Target | Blocking | Detection Method |
|------|---------|--------|----------|-----------------|
| ER-001 | Missing required info (budget, quantity, category) | Requester Clarification | Yes | Deterministic: null field checks in Step 2 |
| ER-002 | Preferred supplier is restricted | Procurement Manager | Yes | Org Layer engine + Step 4 compliance |
| ER-003 | Strategic sourcing approval tier (value > tier 3) | Head of Strategic Sourcing / CPO | No | Org Layer engine via approval tier |
| ER-004 | No compliant supplier with valid pricing | Head of Category | Yes | Org Layer engine + Step 4/5 (0 compliant or 0 priced) |
| ER-005 | Data residency constraint unsatisfiable | Data Protection Officer | Yes | Org Layer engine + Step 4 residency check |
| ER-006 | Single supplier capacity risk | Head of Category | Yes | Org Layer engine + Step 4 capacity check |
| ER-007 | Influencer Campaign Management (brand safety) | Head of Marketing | Yes | Org Layer engine (category-based) |
| ER-008 | Preferred supplier unregistered for USD delivery scope | Category Manager | Yes | Org Layer engine (USD + preferred supplier region mismatch) |
| AT-xxx | Single-supplier instruction vs. multi-quote threshold | Procurement Manager | Yes | Org Layer engine (multi-language pattern matching) + LLM instruction extraction |

### Merge Algorithm

```python
def merge_escalations(
    org_escalations: list[EscalationData],
    pipeline_issues: list[PipelineEscalation],
) -> list[Escalation]:
    merged = {}

    # Org Layer escalations as base
    for esc in org_escalations:
        merged[esc.rule_id] = Escalation(
            rule=esc.rule_id,
            trigger=esc.trigger,
            escalate_to=esc.escalate_to,
            blocking=esc.blocking,
            source="org_layer",
        )

    # Pipeline-discovered: merge or add
    for issue in pipeline_issues:
        if issue.rule_id in merged:
            # Keep more specific trigger
            if len(issue.trigger) > len(merged[issue.rule_id].trigger):
                merged[issue.rule_id].trigger = issue.trigger
                merged[issue.rule_id].source = "pipeline"
        else:
            merged[issue.rule_id] = Escalation(
                rule=issue.rule_id,
                trigger=issue.trigger,
                escalate_to=issue.escalate_to,
                blocking=issue.blocking,
                source=issue.source,
            )

    # Assign sequential IDs
    result = sorted(merged.values(), key=lambda e: e.rule)
    for i, esc in enumerate(result, 1):
        esc.escalation_id = f"ESC-{i:03d}"

    return result
```

---

## 7. Confidence Scoring

Each recommendation includes a `confidence_score` (0-100) that quantifies the system's certainty in the recommendation.

### Formula

```python
def compute_confidence(
    escalations: list[Escalation],
    validation_issues: list[ValidationIssue],
    ranked_suppliers: list[RankedSupplier],
) -> int:
    score = 100

    # Blocking escalations: hard cap at 0 for autonomous decisions
    blocking = [e for e in escalations if e.blocking]
    if blocking:
        return 0

    # Non-blocking escalations
    non_blocking = [e for e in escalations if not e.blocking]
    score -= len(non_blocking) * 10

    # Validation issues by severity
    severity_penalty = {"critical": 15, "high": 10, "medium": 5, "low": 2}
    for issue in validation_issues:
        score -= severity_penalty.get(issue.severity, 5)

    # Bonus: clear winner (top supplier has >20% gap over #2)
    if len(ranked_suppliers) >= 2:
        gap = (ranked_suppliers[1].true_cost - ranked_suppliers[0].true_cost) / ranked_suppliers[0].true_cost
        if gap > 0.20:
            score += 10

    # Bonus: preferred supplier is top-ranked
    if ranked_suppliers and ranked_suppliers[0].preferred:
        score += 5

    return max(0, min(100, score))
```

### Interpretation

| Range | Meaning |
|-------|---------|
| 0 | Cannot proceed autonomously (blocking escalations present) |
| 1-30 | Low confidence -- significant issues or many non-blocking escalations |
| 31-60 | Moderate confidence -- some concerns but recommendation is defensible |
| 61-80 | High confidence -- minor issues, clear recommendation |
| 81-100 | Very high confidence -- clean request, clear winner, no escalations |

---

## 8. Logging Strategy

The pipeline writes two types of logs to the Org Layer.

### 8a. Pipeline Run Logging (Step-Level Telemetry)

**Purpose**: Track pipeline execution progress, timing, and success/failure per step.

**Tables**: `pipeline_runs` + `pipeline_log_entries` (see `LOGGING_API.md`)

**Lifecycle**:

```
Pipeline start:
  POST /api/logs/runs  { run_id, request_id, started_at }

Each step:
  POST /api/logs/entries  { run_id, step_name, step_order, started_at, input_summary }
  ... step executes ...
  PATCH /api/logs/entries/{id}  { status, completed_at, duration_ms, output_summary, metadata_ }

Pipeline end:
  PATCH /api/logs/runs/{run_id}  { status, completed_at, total_duration_ms, steps_completed, steps_failed }
```

**Step names logged**:

| Order | Step Name | Description |
|-------|-----------|-------------|
| 1 | `fetch_overview` | Fetch request + overview + escalations |
| 2 | `validate_request` | Deterministic + LLM validation |
| 3 | `format_invalid_response` | (early exit only) |
| 3 | `filter_suppliers` | Filter & enrich suppliers |
| 4 | `check_compliance` | Per-supplier compliance checks |
| 5 | `rank_suppliers` | True-cost ranking |
| 6 | `evaluate_policy` | Policy evaluation |
| 7 | `compute_escalations` | Escalation merge |
| 8 | `generate_recommendation` | Recommendation + LLM prose |
| 9 | `assemble_output` | Final assembly + LLM enrichment |

**Metadata examples**:

| Step | `metadata_` contents |
|------|---------------------|
| `fetch_overview` | `{ "supplier_count": 4, "pricing_count": 4, "award_count": 3 }` |
| `validate_request` | `{ "completeness": true, "issue_count": 3, "llm_used": true }` |
| `filter_suppliers` | `{ "enriched_count": 4, "no_pricing_count": 0 }` |
| `check_compliance` | `{ "compliant_count": 3, "excluded_count": 1 }` |
| `rank_suppliers` | `{ "ranking_method": "true_cost", "top_supplier": "SUP-0007" }` |
| `evaluate_policy` | `{ "tier": "AT-002", "quotes_required": 2 }` |
| `compute_escalations` | `{ "total": 3, "blocking": 3, "non_blocking": 0 }` |
| `generate_recommendation` | `{ "status": "cannot_proceed", "confidence": 0 }` |
| `assemble_output` | `{ "sections": 8, "llm_enriched": true }` |

### 8b. Audit Logging (Human-Readable Decision Trail)

**Purpose**: Create a complete, auditable record of every decision the pipeline makes, readable by humans and queryable by the frontend.

**Table**: `audit_logs` (see `LOGGING_API.md`)

**Emission pattern**: Each pipeline step collects audit entries in a list, then flushes them all at once via `POST /api/logs/audit/batch` after the step completes. This minimizes HTTP calls.

**Categories and examples**:

| Category | Step | Level | Example Message |
|----------|------|-------|-----------------|
| `data_access` | fetch | info | "Fetched request overview for REQ-000004: 4 compliant suppliers, 4 pricing tiers" |
| `validation` | validate | error | "Budget EUR 25,199.55 insufficient: minimum total EUR 35,712.00 at cheapest supplier" |
| `validation` | validate | warn | "Contradiction: requester instruction 'no exception' conflicts with AT-002 multi-quote requirement" |
| `validation` | validate | info | "All required fields present. Completeness: pass" |
| `supplier_filter` | filter | info | "Included SUP-0007 (Bechtle Workplace Solutions): covers IT > Docking Stations in DE" |
| `supplier_filter` | filter | info | "Included SUP-0001 (Dell Enterprise Europe): preferred, covers IT > Docking Stations in DE" |
| `compliance` | comply | warn | "Excluded SUP-0008 (Computacenter): risk_score 34 exceeds acceptable threshold" |
| `compliance` | comply | info | "SUP-0007 (Bechtle): compliant. Not restricted, covers DE, no residency constraint" |
| `pricing` | rank | info | "SUP-0007: tier 100-499 units, unit EUR 148.80, total EUR 35,712.00, lead 26d standard / 18d expedited" |
| `ranking` | rank | info | "Ranked 3 suppliers by true_cost. #1: SUP-0007 (EUR 43,551.22), #2: SUP-0001 (EUR 43,764.71)" |
| `policy` | policy | info | "Applied AT-002: contract value EUR 35,712 exceeds EUR 25,000 threshold. 2 quotes required" |
| `policy` | policy | info | "Preferred supplier Dell Enterprise Europe: eligible, is_preferred=true, covers DE" |
| `escalation` | escalate | error | "ER-001 triggered: budget insufficient to cover 240 units. Escalate to Requester Clarification. BLOCKING" |
| `escalation` | escalate | error | "AT-002 triggered: 'no exception' instruction conflicts with 2-quote requirement. Escalate to Procurement Manager. BLOCKING" |
| `recommendation` | recommend | info | "Recommendation: cannot_proceed. 3 blocking escalations. Confidence: 0%" |
| `recommendation` | recommend | info | "Preferred supplier if resolved: Bechtle Workplace Solutions (rank #1, EUR 35,712)" |

**`details` JSON structure per category**:

```json
// validation
{ "issue_type": "budget_insufficient", "budget": 25199.55, "min_total": 35712.00, "currency": "EUR" }

// supplier_filter
{ "supplier_id": "SUP-0007", "action": "included", "reason": "covers category and country" }

// compliance
{ "supplier_id": "SUP-0008", "action": "excluded", "check": "risk_score", "value": 34 }

// pricing
{ "supplier_id": "SUP-0007", "tier": "100-499", "unit_price": 148.80, "total": 35712.00, "currency": "EUR" }

// policy
{ "policy_id": "AT-002", "threshold": 25000, "actual_value": 35712, "quotes_required": 2 }

// escalation
{ "rule_id": "ER-001", "blocking": true, "escalate_to": "Requester Clarification" }

// recommendation
{ "status": "cannot_proceed", "confidence": 0, "blocking_count": 3 }
```

### 8c. PipelineLogger Implementation

```python
class PipelineLogger:
    """Fire-and-forget logger that writes to Org Layer logging endpoints."""

    def __init__(self, org_client: OrganisationalClient, run_id: str, request_id: str):
        self.org = org_client
        self.run_id = run_id
        self.request_id = request_id
        self._step_order = 0
        self._audit_buffer: list[dict] = []
        self._steps_completed = 0
        self._steps_failed = 0

    async def start_run(self):
        """POST /api/logs/runs -- create the pipeline run record."""

    @asynccontextmanager
    async def step(self, step_name: str, input_summary: dict):
        """Context manager that logs step start/end with timing."""
        self._step_order += 1
        entry_id = await self._create_entry(step_name, input_summary)
        start = time.monotonic()
        try:
            yield StepContext(self)  # caller populates output_summary and metadata
            duration = int((time.monotonic() - start) * 1000)
            await self._update_entry(entry_id, "completed", duration, ...)
            self._steps_completed += 1
        except Exception as exc:
            duration = int((time.monotonic() - start) * 1000)
            await self._update_entry(entry_id, "failed", duration, error=str(exc))
            self._steps_failed += 1
            raise

    def audit(self, category: str, level: str, step_name: str, message: str, details: dict = None):
        """Buffer an audit log entry for batch flush."""
        self._audit_buffer.append({ ... })

    async def flush_audit(self):
        """POST /api/logs/audit/batch -- flush all buffered audit entries."""

    async def finalize_run(self, status: str):
        """PATCH /api/logs/runs/{run_id} -- mark run as completed/failed."""
```

All methods wrap their HTTP calls in `try/except` and never raise. If the Org Layer is unreachable, a warning is logged to stderr and the pipeline continues.

### 8d. Truncation Rules

Before storing in `input_summary` and `output_summary`:

- Strings: capped at 500 characters
- Dicts: capped at 30 keys
- Lists longer than 5 items: replaced with `{ "_type": "list", "_length": N, "_sample": [first 3 items] }`
- Recursion depth: capped at 3 levels
- Error messages: capped at 2000 characters

---

## 9. API Endpoints

### Pipeline Execution

#### `POST /api/pipeline/process`

Process a single purchase request through the full pipeline.

**Request body**:
```json
{ "request_id": "REQ-000004" }
```

**Response** (200):
Full output matching `example_output.json` plus:
```json
{
  "request_id": "REQ-000004",
  "processed_at": "2026-03-19T14:30:12Z",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processed",
  "request_interpretation": { ... },
  "validation": { ... },
  "policy_evaluation": { ... },
  "supplier_shortlist": [ ... ],
  "suppliers_excluded": [ ... ],
  "escalations": [ ... ],
  "recommendation": { ... },
  "audit_trail": { ... }
}
```

**Side effects**:
- Creates a pipeline run record in Org Layer
- Creates step-level log entries
- Creates audit log entries
- Updates request status in Org Layer: `"in_review"` -> `"evaluated"` (or `"escalated"` if blocking escalations)

**Error responses**:
- 404: Request not found
- 500: Pipeline failure (with `error_message` in response body and pipeline run marked as `"failed"`)

---

#### `POST /api/pipeline/process-batch`

Process multiple purchase requests concurrently.

**Request body**:
```json
{
  "request_ids": ["REQ-000001", "REQ-000002", "REQ-000003"],
  "concurrency": 5
}
```

**Response** (202):
```json
{
  "batch_id": "batch-uuid-here",
  "queued": 3,
  "concurrency": 5,
  "message": "Processing started"
}
```

**Implementation**: Uses `asyncio.Semaphore(concurrency)` to limit concurrent pipeline executions. Each request runs independently. Failures in one request do not affect others.

The frontend polls `GET /api/pipeline/status/{request_id}` for individual progress.

---

### Pipeline Status & Results

#### `GET /api/pipeline/status/{request_id}`

Get the latest processing status for a request.

**Response** (200):
```json
{
  "request_id": "REQ-000004",
  "latest_run": {
    "run_id": "550e8400-...",
    "status": "completed",
    "started_at": "2026-03-19T14:30:00",
    "completed_at": "2026-03-19T14:30:12",
    "total_duration_ms": 12340,
    "steps_completed": 9,
    "steps_failed": 0
  },
  "recommendation_status": "cannot_proceed",
  "escalation_count": 3,
  "confidence_score": 0
}
```

**Implementation**: Proxies to `GET /api/logs/by-request/{request_id}` on the Org Layer and extracts the latest run. Augments with recommendation summary from the stored pipeline result.

---

#### `GET /api/pipeline/result/{request_id}`

Get the full pipeline result from the latest successful run.

**Response** (200): Same as `POST /api/pipeline/process` response.

**Response** (404): No successful pipeline run found for this request.

**Implementation**: The pipeline result is stored as the `output_summary` of the `assemble_output` step's log entry. This endpoint retrieves it.

Alternatively, the logical layer can store results in an in-memory cache (dict or Redis) keyed by `request_id`, refreshed on each pipeline run. For 304 requests, an in-memory dict is sufficient.

---

#### `GET /api/pipeline/runs`

List all pipeline runs with filters.

**Query parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `request_id` | string | - | Filter by request ID |
| `status` | string | - | Filter by status |
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 50 | Page size (max 200) |

**Response**: Proxies to `GET /api/logs/runs` on the Org Layer.

---

#### `GET /api/pipeline/runs/{run_id}`

Get a specific run with all step details.

**Response**: Proxies to `GET /api/logs/runs/{run_id}` on the Org Layer.

---

### Audit & Logging

#### `GET /api/pipeline/audit/{request_id}`

Get full audit trail for a request.

**Query parameters**: Same as Org Layer's `GET /api/logs/audit/by-request/{request_id}` (level, category, run_id, step_name, skip, limit).

**Response**: Proxies to Org Layer audit log endpoint.

---

#### `GET /api/pipeline/audit/{request_id}/summary`

Get aggregated audit summary for a request.

**Response**: Proxies to `GET /api/logs/audit/summary/{request_id}` on the Org Layer.

---

### Health

#### `GET /health`

**Response** (200):
```json
{
  "status": "ok",
  "org_layer": "reachable",
  "llm": "configured",
  "version": "2.0.0"
}
```

Checks Org Layer connectivity by calling `GET /health` on the Org Layer. Reports LLM client configuration status.

---

## 10. Output Format

The pipeline output matches `examples/example_output.json`. Here is the complete schema with types and notes.

### Top Level

```json
{
  "request_id": "REQ-000004",
  "processed_at": "2026-03-19T14:30:12Z",
  "run_id": "550e8400-...",
  "status": "processed | invalid",

  "request_interpretation": { ... },
  "validation": { ... },
  "policy_evaluation": { ... },
  "supplier_shortlist": [ ... ],
  "suppliers_excluded": [ ... ],
  "escalations": [ ... ],
  "recommendation": { ... },
  "audit_trail": { ... }
}
```

### `request_interpretation`

```json
{
  "category_l1": "IT",
  "category_l2": "Docking Stations",
  "quantity": 240,
  "unit_of_measure": "device",
  "budget_amount": 25199.55,
  "currency": "EUR",
  "delivery_country": "DE",
  "required_by_date": "2026-03-20",
  "days_until_required": 6,
  "data_residency_required": false,
  "esg_requirement": false,
  "preferred_supplier_stated": "Dell Enterprise Europe",
  "incumbent_supplier": "Bechtle Workplace Solutions",
  "requester_instruction": "no exception -- single supplier only"
}
```

Fields are extracted from the request object and the LLM interpretation. `days_until_required` is computed as `(required_by_date - created_at).days`. `requester_instruction` is extracted by the LLM from `request_text`.

### `validation`

```json
{
  "completeness": "pass",
  "issues_detected": [
    {
      "issue_id": "V-001",
      "severity": "critical",
      "type": "budget_insufficient",
      "description": "Budget of EUR 25,199.55 cannot cover 240 units...",
      "action_required": "Requester must either increase budget..."
    }
  ]
}
```

`completeness` is `"pass"` or `"fail"` (string, not boolean). `"fail"` only when critical required fields are missing (category, currency). Budget or quantity being null is an issue but not a completeness failure.

Issue types: `missing_info`, `contradictory`, `budget_insufficient`, `lead_time_infeasible`, `policy_conflict`.

Severity levels: `critical`, `high`, `medium`, `low`.

### `policy_evaluation`

```json
{
  "approval_threshold": {
    "rule_applied": "AT-002",
    "basis": "All valid pricing options place total contract value between EUR 35,712 and EUR 37,200...",
    "quotes_required": 2,
    "approvers": ["business", "procurement"],
    "deviation_approval": "Procurement Manager",
    "note": "Stated budget falls just above AT-001 ceiling..."
  },
  "preferred_supplier": {
    "supplier": "Dell Enterprise Europe",
    "status": "eligible",
    "is_preferred": true,
    "covers_delivery_country": true,
    "is_restricted": false,
    "policy_note": "Dell is a preferred supplier for Docking Stations in DE..."
  },
  "restricted_suppliers": {
    "SUP-0008_Computacenter_Devices": {
      "restricted": false,
      "note": "Not restricted for Docking Stations. Excluded on risk grounds."
    }
  },
  "category_rules_applied": [],
  "geography_rules_applied": []
}
```

### `supplier_shortlist`

```json
[
  {
    "rank": 1,
    "supplier_id": "SUP-0007",
    "supplier_name": "Bechtle Workplace Solutions",
    "preferred": true,
    "incumbent": true,
    "pricing_tier_applied": "100-499 units",
    "unit_price_eur": 148.80,
    "total_price_eur": 35712.00,
    "standard_lead_time_days": 26,
    "expedited_lead_time_days": 18,
    "expedited_unit_price_eur": 160.70,
    "expedited_total_eur": 38568.00,
    "quality_score": 82,
    "risk_score": 19,
    "esg_score": 72,
    "policy_compliant": true,
    "covers_delivery_country": true,
    "recommendation_note": "Lowest total price at EUR 35,712..."
  }
]
```

Currency keys are dynamic: `unit_price_eur`, `total_price_eur` for EUR requests; `unit_price_usd`, `total_price_usd` for USD; `unit_price_chf`, `total_price_chf` for CHF.

### `suppliers_excluded`

```json
[
  {
    "supplier_id": "SUP-0008",
    "supplier_name": "Computacenter Devices",
    "reason": "preferred=False, risk_score=34 (highest of eligible set)..."
  }
]
```

### `escalations`

```json
[
  {
    "escalation_id": "ESC-001",
    "rule": "ER-001",
    "trigger": "Budget is insufficient to fulfil the stated quantity...",
    "escalate_to": "Requester Clarification",
    "blocking": true
  }
]
```

### `recommendation`

```json
{
  "status": "cannot_proceed",
  "reason": "Three blocking issues prevent autonomous award...",
  "preferred_supplier_if_resolved": "Bechtle Workplace Solutions",
  "preferred_supplier_rationale": "Bechtle is the incumbent and lowest-cost option...",
  "minimum_budget_required": 35712.00,
  "minimum_budget_currency": "EUR",
  "confidence_score": 0
}
```

Status values: `"proceed"`, `"proceed_with_conditions"`, `"cannot_proceed"`.

### `audit_trail`

```json
{
  "policies_checked": ["AT-001", "AT-002", "CR-001", "ER-001", "ER-004"],
  "supplier_ids_evaluated": ["SUP-0001", "SUP-0002", "SUP-0007", "SUP-0008"],
  "pricing_tiers_applied": "100-499 units (EU region, EUR currency)",
  "data_sources_used": ["requests.json", "suppliers.csv", "pricing.csv", "policies.json"],
  "historical_awards_consulted": true,
  "historical_award_note": "AWD-000009 through AWD-000011 show this request was previously awarded to Dell..."
}
```

---

## 11. Data Normalization

All normalization helpers live in `app/utils.py`. Every pipeline step imports from here.

### `normalize_delivery_countries(raw)`

The Org Layer returns delivery countries in two formats depending on the endpoint:

```python
def normalize_delivery_countries(raw: list) -> list[str]:
    """
    Handles both formats:
    - Simple: ["DE", "FR"]
    - Object: [{"country_code": "DE"}, {"country_code": "FR"}]
    """
    if not raw:
        return []
    if isinstance(raw[0], str):
        return raw
    return [item["country_code"] for item in raw if "country_code" in item]
```

### `normalize_scenario_tags(raw)`

```python
def normalize_scenario_tags(raw: list) -> list[str]:
    """
    Handles both formats:
    - Simple: ["standard", "urgent"]
    - Object: [{"tag": "standard"}, {"tag": "urgent"}]
    """
    if not raw:
        return []
    if isinstance(raw[0], str):
        return raw
    return [item["tag"] for item in raw if "tag" in item]
```

### `coerce_budget(val) -> float | None`

```python
def coerce_budget(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
```

### `coerce_quantity(val) -> int | None`

```python
def coerce_quantity(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))  # handles "240.0"
    except (ValueError, TypeError):
        return None
```

### `COUNTRY_TO_REGION`

```python
COUNTRY_TO_REGION: dict[str, str] = {
    "DE": "EU", "FR": "EU", "NL": "EU", "BE": "EU", "AT": "EU",
    "IT": "EU", "ES": "EU", "PL": "EU", "UK": "EU",
    "CH": "CH",
    "US": "Americas", "CA": "Americas", "BR": "Americas", "MX": "Americas",
    "SG": "APAC", "AU": "APAC", "IN": "APAC", "JP": "APAC",
    "UAE": "MEA", "ZA": "MEA",
}

def country_to_region(country_code: str) -> str:
    return COUNTRY_TO_REGION.get(country_code, "EU")
```

### `primary_delivery_country(request_data)`

```python
def primary_delivery_country(request_data: dict) -> str:
    countries = normalize_delivery_countries(request_data.get("delivery_countries", []))
    if countries:
        return countries[0]
    return request_data.get("country", "DE")
```

---

## 12. LLM Integration

### Client Setup

One `anthropic.AsyncAnthropic()` client created at app startup via lifespan:

```python
# main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm_client = LLMClient(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.ANTHROPIC_MODEL,  # default: "claude-sonnet-4-6"
    )
    async with httpx.AsyncClient(...) as http_client:
        app.state.org_client = OrganisationalClient(http_client)
        yield
```

### LLMClient Wrapper

```python
class LLMClient:
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        max_tokens: int = 2000,
    ) -> tuple[BaseModel | None, bool]:
        """
        Call Claude with tool_use for structured output.
        Returns (parsed_result, used_fallback).
        If LLM fails, returns (None, True).
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[{
                    "name": "structured_output",
                    "description": "Return structured data",
                    "input_schema": response_model.model_json_schema(),
                }],
                tool_choice={"type": "tool", "name": "structured_output"},
            )
            tool_block = next(b for b in response.content if b.type == "tool_use")
            result = response_model.model_validate(tool_block.input)
            return result, False
        except Exception as exc:
            logger.warning(f"LLM call failed: {exc}")
            return None, True
```

### LLM Calls in the Pipeline

| Step | Purpose | Response Model | Fallback |
|------|---------|---------------|----------|
| Step 2 (validate) | Detect contradictions + extract requester_instruction | `LLMValidationResult` | Return empty issues list + no instruction |
| Step 8 (recommend) | Generate `reason` and `preferred_supplier_rationale` | `LLMRecommendationText` | Template-based prose |
| Step 9 (assemble) | Enrich validation issues + generate supplier recommendation_notes | `LLMEnrichmentResult` | Pass-through issues unchanged; empty recommendation_notes |

### System Prompts to Preserve

**Validation prompt** (core rules):
- Only two issue types: `missing_info` and `contradictory`
- Explicit list of what IS vs IS NOT a contradiction
- Conservative: "when in doubt, do NOT flag"
- Handles multi-language `request_text`
- Extracts `requester_instruction` as a side output

**Recommendation prompt** (core rules):
- Receives status, escalations, ranked suppliers, validation issues, interpretation
- Must reference exact supplier names, prices, and rule IDs
- Professional, audit-ready language

**Enrichment prompt** (core rules):
- Severity levels: critical / high / medium / low
- Must use specific figures from pricing and supplier data
- Per-supplier recommendation notes must compare with alternatives

### LLM Failure Recording

When an LLM call fails, the pipeline:
1. Logs the failure as an audit entry: `category: "general"`, `level: "warn"`, message: "LLM call failed for {step}: {error}. Using deterministic fallback."
2. Records `llm_fallback: true` in the step's metadata
3. Continues with the deterministic fallback
4. The final output is still valid -- just with less polished prose

---

## 13. Org Layer Dependencies

### Endpoints Used by the Pipeline

| Endpoint | Used In | Purpose |
|----------|---------|---------|
| `GET /api/analytics/request-overview/{id}` | Step 1 | Primary data source: request, suppliers, pricing, rules, tier, awards |
| `GET /api/escalations/by-request/{id}` | Step 1 | Computed escalations from Org Layer engine |
| `GET /api/analytics/check-restricted` | Step 4 | Targeted restriction check for borderline suppliers |
| `PUT /api/requests/{id}` | Runner | Update request status (in_review, evaluated, escalated) |
| `POST /api/logs/runs` | Logger | Create pipeline run record |
| `PATCH /api/logs/runs/{run_id}` | Logger | Update run status/completion |
| `POST /api/logs/entries` | Logger | Create step log entry |
| `PATCH /api/logs/entries/{entry_id}` | Logger | Update step entry with timing/output |
| `POST /api/logs/audit/batch` | Logger | Flush audit log entries |
| `GET /api/logs/runs` | Status router | List pipeline runs (proxied) |
| `GET /api/logs/runs/{run_id}` | Status router | Get run details (proxied) |
| `GET /api/logs/by-request/{request_id}` | Status router | Get runs for request (proxied) |
| `GET /api/logs/audit/by-request/{request_id}` | Audit router | Get audit trail (proxied) |
| `GET /api/logs/audit/summary/{request_id}` | Audit router | Get audit summary (proxied) |
| `GET /health` | Health check | Verify Org Layer is reachable |

### OrganisationalClient Methods

```python
class OrganisationalClient:
    async def get_request_overview(self, request_id: str) -> dict
    async def get_escalations_by_request(self, request_id: str) -> list[dict]
    async def check_restricted(self, supplier_id, cat_l1, cat_l2, country) -> dict
    async def update_request_status(self, request_id: str, status: str) -> None

    # Logging
    async def create_run(self, run_id, request_id, started_at) -> dict
    async def update_run(self, run_id, **kwargs) -> None
    async def create_entry(self, run_id, step_name, step_order, started_at, input_summary) -> dict
    async def update_entry(self, entry_id, **kwargs) -> None
    async def batch_audit_logs(self, entries: list[dict]) -> None

    # Proxied reads
    async def get_runs(self, **filters) -> dict
    async def get_run(self, run_id: str) -> dict
    async def get_runs_by_request(self, request_id: str) -> list[dict]
    async def get_audit_by_request(self, request_id: str, **filters) -> dict
    async def get_audit_summary(self, request_id: str) -> dict
```

---

## 14. Frontend Contract

### What the Frontend Expects

The frontend (`frontend/src/lib/data/cases.ts`) currently fetches from the Org Layer. With the logical layer, the frontend needs additional data for the case detail page.

**Current frontend endpoints** (served by Org Layer):

| Endpoint | Frontend Usage |
|----------|---------------|
| `GET /api/requests/` | Inbox page: paginated request list |
| `GET /api/requests/{id}` | Case detail: request metadata |
| `GET /api/analytics/request-overview/{id}` | Case detail: suppliers, pricing, rules |
| `GET /api/escalations/by-request/{id}` | Case detail: escalation tab |
| `GET /api/escalations/queue` | Escalations page: queue view |
| `GET /api/awards/by-request/{id}` | Case detail: historical awards |

**New endpoints from Logical Layer** (the frontend will need to call these or they can be proxied through the Org Layer):

| Endpoint | Frontend Usage |
|----------|---------------|
| `POST /api/pipeline/process` | "Run Pipeline" button on case detail |
| `GET /api/pipeline/result/{request_id}` | Case detail: full pipeline result (all tabs) |
| `GET /api/pipeline/status/{request_id}` | Case detail: processing status indicator |
| `POST /api/pipeline/process-batch` | "Process All" button on inbox |
| `GET /api/pipeline/audit/{request_id}` | Case detail: Audit Trace tab |
| `GET /api/pipeline/audit/{request_id}/summary` | Case detail: Audit summary card |

### Frontend Type Mapping

The frontend defines types in `frontend/src/lib/types/case.ts`. The pipeline output maps to:

| Pipeline Section | Frontend Type | Notes |
|-----------------|---------------|-------|
| `request_interpretation` | `InterpretedRequirement` | Direct mapping |
| `validation.issues_detected` | `ValidationIssue[]` | Direct mapping |
| `policy_evaluation` | `PolicyCardData` | Needs mapping from nested structure |
| `supplier_shortlist` | `SupplierRow[]` | Dynamic currency keys need handling |
| `suppliers_excluded` | `ExcludedSupplier[]` | Direct mapping |
| `escalations` | `EscalationItem[]` | Direct mapping |
| `recommendation` | `RecommendationSummary` | Direct mapping + confidence_score |
| `audit_trail` | `AuditTrail` | Direct mapping |

### Request Status Flow

The frontend inbox uses these statuses to show badges:

```
new -> in_review -> evaluated -> resolved
                 -> escalated -> resolved
                 -> error
```

The pipeline sets:
- `in_review`: immediately when processing starts
- `evaluated`: when processing completes with `status: "proceed"` or `"proceed_with_conditions"`
- `escalated`: when processing completes with `status: "cannot_proceed"`
- `error`: when the pipeline fails with an unrecoverable error

---

## 15. Lessons from v1

These are the concrete bugs and design flaws from the first implementation that this rewrite addresses.

### Bugs Fixed

| Bug | v1 Behavior | v2 Fix |
|-----|------------|--------|
| `is_valid` vs `completeness` | `processing.py` read `is_valid` but `validateRequest.py` returned `completeness` -> logged `is_valid: None` | Pydantic model `ValidationResult.completeness` -- type-safe, no mismatch possible |
| `recommendation_status` vs `status` | `processing.py` read `recommendation_status` but `generateRecommendation.py` returned `status` -> logged `status: None` | Pydantic model `RecommendationResult.status` |
| `metadata_` field name | SQLAlchemy uses `metadata_` because `metadata` is reserved. PATCH payloads must use `metadata_` | OrganisationalClient handles this internally; pipeline code never sees it |

### Design Flaws Eliminated

| Flaw | v1 | v2 |
|------|----|----|
| Dual HTTP clients | Scripts used blocking `urllib` with hardcoded IP fallback; app used async `httpx` | Single async `httpx.AsyncClient` everywhere |
| Duplicated helpers | `_normalize_delivery_countries()` in 4 files, `api_get()` in 5 files, `COUNTRY_TO_REGION` in 2 files | Single `utils.py` module |
| N+2 HTTP calls in filter | Fetched ALL categories, then per-supplier category lookups | One call to `request-overview` returns everything |
| 10+ HTTP calls per request | Individual calls for request, suppliers, pricing, tier, rules, awards | `request-overview` mega-endpoint + one escalations call |
| Fragile LLM JSON parsing | Regex extraction of JSON from free text; fails on edge cases | Anthropic `tool_use` for structured output; Pydantic validation |
| Silently swallowed LLM errors | `try/except Exception: pass` with no logging | Logged to audit trail + `llm_fallback` flag in step metadata |
| New Anthropic client per call | `anthropic.Anthropic()` created in every script | Single `AsyncAnthropic` at startup |
| No parallelism | Steps ran sequentially even when independent | `asyncio.gather()` for fetch (overview + escalations) and for policy + escalation merge |
| Historical awards fetched too late | Fetched after recommendation, so recommendation couldn't use them | Fetched in Step 1 via `request-overview`; available to all steps |
| Supplier name enrichment as separate step | Step 7 was just to fetch `supplier_name` values | Names included in `request-overview` compliant suppliers |

### Patterns Preserved

These worked well in v1 and are kept:

| Pattern | Why It Worked |
|---------|--------------|
| Fire-and-forget logging | Pipeline never crashes due to logging failures |
| Deterministic escalation engine in Org Layer | Separates data-driven rule evaluation from pipeline logic |
| LLM for prose only | All policy decisions are deterministic; LLM adds human-readable explanations |
| Conservative validation prompt | "When in doubt, do NOT flag" -- avoids false positives |
| Early exit on invalid requests | Saves unnecessary supplier lookups for malformed requests |
| Step-level timing | Every step is timed and logged -- essential for debugging |
| Truncation of log payloads | Prevents log storage from growing unbounded |

### System Prompts Preserved (adapted)

The core rules from v1 system prompts are preserved:

**Validation**: only `missing_info` and `contradictory` issue types; explicit contradiction whitelist/blacklist; conservative flagging; multi-language support; `requester_instruction` extraction.

**Recommendation**: exact names, prices, rule IDs; professional audit-ready tone; structured status determination.

**Enrichment**: severity levels (critical/high/medium/low); specific figures from data; per-supplier comparison notes.

---

## 16. Deployment

### Dockerfile

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

No more `scripts/` directory -- everything is inside `app/`.

### requirements.txt

```
fastapi[standard]
uvicorn[standard]
httpx
pydantic-settings
python-dotenv
anthropic
```

### .env.example

```env
ORGANISATIONAL_LAYER_URL=http://organisational-layer:8000
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

### Docker Compose Integration

In `backend/docker-compose.yml`:

```yaml
services:
  organisational-layer:
    build: ./organisational_layer
    ports:
      - "8000:8000"
    env_file: ./organisational_layer/.env
    networks:
      - chainiq-network

  logical-layer:
    build: ./logical_layer
    ports:
      - "8080:8080"
    env_file: ./logical_layer/.env
    depends_on:
      - organisational-layer
    networks:
      - chainiq-network

networks:
  chainiq-network:
    external: true
```

### Local Development

```bash
cd backend/logical_layer
python -m venv .venv
source .venv/bin/activate
cp .env.example .env  # fill in ANTHROPIC_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Requires the Org Layer to be running on port 8000 (either Docker or local).

---

## Appendix A: Scenario Tag Handling

Each request has `scenario_tags` that indicate what kind of challenge it presents. The pipeline handles each:

| Tag | Count | Pipeline Handling |
|-----|-------|-------------------|
| `standard` | 141 | Happy path. All steps run normally. Expect `proceed` recommendation. |
| `threshold` | 29 | Budget near a tier boundary. Step 6 (policy) must determine correct tier carefully. May trigger ER-003 (strategic sourcing). |
| `lead_time` | 29 | Delivery deadline is critically short. Step 2 detects infeasible lead time. Step 7 may trigger ER-004. |
| `missing_info` | 28 | Budget or quantity is null. Step 2 flags issues. Pipeline continues with degraded capability (quality-only ranking). ER-001 triggers. |
| `contradictory` | 21 | Internal conflicts (quantity/budget/date mismatches, single-supplier vs multi-quote). Step 2 LLM detects. AT conflict may trigger. |
| `restricted` | 18 | Preferred supplier is restricted, wrong category, or out of scope. Step 4 catches. ER-002 triggers. |
| `multilingual` | 18 | Non-English `request_text`. LLM handles natively. AT conflict engine has multi-language patterns. |
| `capacity` | 18 | Quantity exceeds supplier capacity. Step 4 catches. ER-006 triggers. |
| `multi_country` | 3 | Multiple delivery countries with different compliance requirements. Step 4 checks each country. May trigger multiple geography rules. |

---

## Appendix B: REQ-000004 Walkthrough

This is the reference request from `examples/`. Here is how the pipeline processes it:

**Input**: REQ-000004 -- 240 docking stations, EUR 25,199.55 budget, deliver to DE by 2026-03-20, preferred Dell, incumbent Bechtle, "no exception -- single supplier only"

**Step 1**: Fetch overview returns 4 compliant suppliers (Dell, HP, Bechtle, Computacenter) with pricing at tier 100-499. Escalations from Org Layer: ER-001 (budget insufficient), AT-002 conflict (single-supplier instruction vs 2-quote requirement), ER-004 (lead time infeasible).

**Step 2**: Deterministic checks find: budget EUR 25,199 < minimum total EUR 35,712 (critical), lead time 6 days < all expedited lead times 17-19 days (high). LLM detects: requester instruction "no exception" conflicts with AT-002 (high). Completeness: pass (all required fields present).

**Step 3**: Enrich 4 suppliers with pricing and metadata.

**Step 4**: Exclude Computacenter (risk_score=34, not preferred). 3 compliant remain.

**Step 5**: Rank by true_cost: #1 Bechtle (EUR 35,712), #2 Dell (EUR 37,200), #3 HP (EUR 36,828).

**Step 6**: AT-002 applies (EUR 35,712 > EUR 25,000 threshold, 2 quotes required). Dell is eligible preferred supplier. Computacenter not restricted but excluded on risk.

**Step 7**: Merge 3 escalations from Org Layer. Pipeline adds more specific trigger descriptions (with exact figures).

**Step 8**: `cannot_proceed` (3 blocking escalations). Confidence: 0. LLM generates prose reasoning.

**Step 9**: Assemble output. LLM enriches validation issues with severity/action_required. LLM generates per-supplier recommendation notes.

**Output**: Matches `examples/example_output.json`.

---

## Appendix C: Request Status State Machine

```
            +-----------+
            |    new    |   <-- Initial state from data import
            +-----+-----+
                  |
          POST /api/pipeline/process
                  |
            +-----v-----+
            | in_review  |   <-- Pipeline sets this immediately
            +-----+-----+
                  |
         pipeline completes
                  |
          +-------+-------+
          |               |
    +-----v-----+   +----v------+
    | evaluated  |   | escalated |   <-- Based on recommendation status
    +-----+-----+   +-----+-----+
          |               |
     human reviews   human resolves
          |               |
    +-----v-----+   +-----v-----+
    | resolved   |   | resolved  |   <-- Set by frontend/human action
    +-----------+   +-----------+

    (on pipeline failure)
            +-----v-----+
            |   error    |
            +-----------+
```
