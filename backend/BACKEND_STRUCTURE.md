# BACKEND_STRUCTURE.md

Comprehensive overview of the ChainIQ backend — two FastAPI microservices on a shared Docker network, backed by MySQL 8 on AWS RDS.

---

## Table of Contents

1. [Topology](#1-topology)
2. [Organisational Layer (Port 8000)](#2-organisational-layer-port-8000)
3. [Logical Layer (Port 8080)](#3-logical-layer-port-8080)
4. [Pipeline Flow (9 Steps)](#4-pipeline-flow-9-steps)
5. [Inter-Service Contract](#5-inter-service-contract)
6. [Database Schema](#6-database-schema)
7. [Escalation Rules Reference](#7-escalation-rules-reference)
8. [Logging Architecture](#8-logging-architecture)
9. [LLM Integration](#9-llm-integration)
10. [Confidence Scoring](#10-confidence-scoring)
11. [Output Format](#11-output-format)
12. [Data Normalization Helpers](#12-data-normalization-helpers)
13. [Docker & Deployment](#13-docker--deployment)
14. [Testing](#14-testing)

---

## 1. Topology

```
Frontend (Next.js :3000)
  │
  │  Next.js rewrites /api/* ──►
  │
  ▼
Organisational Layer (FastAPI :8000)       ◄── Data + governance
  │   CRUD, analytics, escalation engine,
  │   pipeline logging, audit logging,
  │   rule versioning, evaluation tracking
  │   pymysql
  ▼
MySQL 8.4 (AWS RDS)                        ◄── 38 normalised tables

Logical Layer (FastAPI :8080)              ◄── Decision engine
  │   Pure Python 9-step pipeline
  │   No workflow engine — async Python only
  │   async httpx ──► Org Layer (all data)
  │   anthropic SDK
  ▼
Claude claude-sonnet-4-6                   ◄── LLM (prose + contradiction detection only)
```

**Design principles:**

| Principle | Detail |
|-----------|--------|
| Org Layer owns all data | Logical Layer never touches MySQL directly. Every read/write goes through Org Layer REST endpoints. |
| LLM for prose, deterministic for decisions | Policy evaluation, compliance, escalation, ranking — all deterministic Python. Claude is used only for contradiction detection, instruction extraction, and recommendation prose. |
| Single HTTP client | One shared `httpx.AsyncClient` at startup, injected via FastAPI dependency. |
| Type-safe pipeline | Pydantic models for every step's input/output. Field mismatches caught at development time. |
| Fire-and-forget logging | Logging never blocks or crashes the pipeline. Org Layer unreachable → logs are lost, pipeline continues. |
| Escalate over guess | A false escalation always scores better than a false clearance. |

---

## 2. Organisational Layer (Port 8000)

**Purpose:** Data backbone. Manages all reference data, procurement rules, request lifecycle, analytics, escalation evaluation, pipeline logging, audit logging, and rule versioning.

### File Structure

```
backend/organisational_layer/
  app/
    main.py                  # FastAPI entry point, CORS, router registration, /health
    config.py                # Pydantic Settings: DB_*, LOGICAL_LAYER_URL
    database.py              # SQLAlchemy engine, session factory, get_db dependency

    models/
      reference.py           # Category, Supplier, SupplierCategory, SupplierServiceRegion, PricingTier
      requests.py            # Request, RequestDeliveryCountry, RequestScenarioTag
      historical.py          # HistoricalAward
      policies.py            # ApprovalThreshold, PreferredSupplierPolicy, RestrictedSupplierPolicy,
                             #   CategoryRule, GeographyRule, EscalationRule (+ all junction tables)
      logs.py                # PipelineRun, PipelineLogEntry, AuditLog
      evaluations.py         # RuleDefinition, RuleVersion, EvaluationRun, HardRuleCheck,
                             #   PolicyCheck, SupplierEvaluation, Escalation, EscalationLog,
                             #   RuleChangeLog, PolicyChangeLog, EvaluationRunLog, PolicyCheckLog
      pipeline_results.py    # PipelineResult — full pipeline output JSON for frontend

    schemas/
      reference.py           # Category, Supplier, PricingTier Pydantic schemas
      requests.py            # Request CRUD schemas (create, update, list, detail)
      historical.py          # HistoricalAward schemas
      policies.py            # Approval threshold, preferred/restricted, category/geo/escalation rules
      analytics.py           # Analytics response schemas (compliant suppliers, pricing, tier, etc.)
      escalations.py         # Escalation queue item schema
      logs.py                # Pipeline logging and audit logging schemas
      pipeline_results.py    # Pipeline result CRUD schemas
      rule_versions.py       # Rule definition, version, evaluation, checks, change log schemas
      parse.py               # Parse request/response schemas
      intake.py              # Intake extraction schemas

    routers/
      categories.py          # CRUD for categories
      suppliers.py           # CRUD for suppliers + sub-resources (categories, regions, pricing)
      requests.py            # CRUD for purchase requests
      awards.py              # Read endpoints for historical awards
      policies.py            # Read endpoints for approval thresholds, preferred/restricted policies
      rules.py               # Read endpoints for category, geography, escalation rules
      escalations.py         # Deterministic escalation queue + stored escalation updates
      rule_versions.py       # Rule definitions/versions CRUD, evaluations, checks, change logs
      parse.py               # LLM-powered text/file → structured request parser
      analytics.py           # Compliant suppliers, pricing lookup, approval tier, restriction/preferred
                             #   checks, applicable rules, request-overview mega-endpoint, spend/win analytics
      logs.py                # Pipeline logging + audit logging endpoints
      pipeline_results.py    # Full pipeline output persistence and retrieval
      intake.py              # Deterministic regex-based intake extraction (no LLM)

    services/
      escalations.py         # Escalation evaluation engine: ER-001..008 + AT conflict detection
      transaction_workflows.py  # ACID transaction workflows: escalation changes, evaluation triggers,
                                #   rule updates, policy check overrides
      request_parser.py      # Anthropic-powered text/file → structured request parser

  LOGGING_API.md             # Full docs for pipeline + audit logging + rule management APIs
  Dockerfile                 # Python 3.14-slim, port 8000
  requirements.txt
  .env.example               # DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, LOGICAL_LAYER_URL
  tests/
    conftest.py              # TestClient + DB session fixtures
    test_api.py              # 97 integration tests (all endpoints)
    test_escalation_service.py  # 6 unit tests for escalation engine
    test_escalation_router.py   # 3 unit tests for escalation router (mocked DB)
```

### API Endpoints

#### Health
- `GET /health` → `{"status": "ok"}`

#### CRUD
| Endpoint | Description |
|----------|-------------|
| `GET/POST /api/categories/`, `GET/PUT/DELETE /api/categories/{id}` | Category management |
| `GET/POST /api/suppliers/`, `GET/PUT/DELETE /api/suppliers/{id}` | Supplier management |
| `GET /api/suppliers/{id}/categories\|regions\|pricing` | Supplier sub-resources |
| `GET/POST /api/requests/`, `GET/PUT/DELETE /api/requests/{id}` | Request lifecycle (PUT supports delivery_countries + scenario_tags replacement) |
| `GET /api/awards/`, `GET /api/awards/{id}`, `GET /api/awards/by-request/{id}` | Historical awards |
| `GET /api/policies/approval-thresholds[/{id}]` | Approval threshold read |
| `GET /api/policies/preferred-suppliers[/{id}]` | Preferred supplier policy read |
| `GET /api/policies/restricted-suppliers[/{id}]` | Restricted supplier policy read |
| `GET /api/rules/category[/{id}]` | Category rules read |
| `GET /api/rules/geography[/{id}]` | Geography rules read |
| `GET /api/rules/escalation[/{id}]` | Escalation rules read |
| `GET /api/escalations/queue` | Active escalation queue |
| `GET /api/escalations/by-request/{id}` | Escalations for a specific request |
| `PATCH /api/escalations/{id}` | Update escalation status |

#### Analytics
| Endpoint | Description |
|----------|-------------|
| `GET /api/analytics/compliant-suppliers` | Non-restricted suppliers for category+country |
| `GET /api/analytics/pricing-lookup` | Pricing tier for supplier+category+region+quantity |
| `GET /api/analytics/approval-tier` | Approval threshold for currency+amount |
| `GET /api/analytics/check-restricted` | Restriction check for supplier+category+country |
| `GET /api/analytics/check-preferred` | Preferred status for supplier+category+region |
| `GET /api/analytics/applicable-rules` | Category and geography rules for a context |
| `GET /api/analytics/request-overview/{id}?pipeline_mode=false` | **Mega-endpoint**: request + compliant suppliers + pricing + rules + approval tier + historical awards. Default (`pipeline_mode=false`) gates supplier/pricing behind pipeline result existence. Use `pipeline_mode=true` for raw reference data (Logical Layer). |
| `GET /api/analytics/spend-by-category` | Aggregated historical spend by category |
| `GET /api/analytics/spend-by-supplier` | Aggregated historical spend by supplier |
| `GET /api/analytics/supplier-win-rates` | Win rates from historical awards |

#### Parse & Intake
| Endpoint | Description |
|----------|-------------|
| `POST /api/parse/text` | LLM: raw procurement text → structured request |
| `POST /api/parse/file` | LLM: uploaded PDF/image → structured request |
| `POST /api/intake/extract` | Deterministic regex: draft fields + per-field confidence + missing-required list |

#### Pipeline Results
| Endpoint | Description |
|----------|-------------|
| `POST /api/pipeline-results/` | Save full pipeline output (called by Logical Layer) |
| `GET /api/pipeline-results/` | List results (paginated; filter by request_id, status, recommendation_status) |
| `GET /api/pipeline-results/{run_id}` | Single result with full output JSON |
| `GET /api/pipeline-results/by-request/{request_id}` | All results for a request |
| `GET /api/pipeline-results/latest/{request_id}` | Most recent result |
| `DELETE /api/pipeline-results/{run_id}` | Delete a result |

#### Pipeline Logging
| Endpoint | Description |
|----------|-------------|
| `POST /api/logs/runs` | Create pipeline run record |
| `PATCH /api/logs/runs/{run_id}` | Update run (completion, failure, timing) |
| `GET /api/logs/runs[/{run_id}]` | List runs or get single run with step entries |
| `GET /api/logs/by-request/{request_id}` | All runs for a request |
| `POST /api/logs/entries` | Create step log entry |
| `PATCH /api/logs/entries/{entry_id}` | Update step entry (timing, output) |

#### Audit Logging
| Endpoint | Description |
|----------|-------------|
| `POST /api/logs/audit` | Create single audit entry |
| `POST /api/logs/audit/batch` | Create multiple entries in one call |
| `GET /api/logs/audit/by-request/{request_id}` | All audit logs for a request (filterable) |
| `GET /api/logs/audit/summary/{request_id}` | Aggregated counts by level + category |
| `GET /api/logs/audit` | Global audit log list with filters |

#### Rule Versioning (`/api/rule-versions/`)
| Endpoint | Description |
|----------|-------------|
| `GET/POST /api/rule-versions/definitions` | Rule definitions CRUD |
| `GET/PATCH/DELETE /api/rule-versions/definitions/{rule_id}` | Single rule definition |
| `GET/POST /api/rule-versions/versions` | Rule versions list/create |
| `GET/PATCH /api/rule-versions/versions/{version_id}` | Single version |
| `GET /api/rule-versions/versions/active/{rule_id}` | Currently active version |
| `GET /api/rule-versions/logs/rule-change[/{log_id}]` | Rule change audit trail |
| `POST /api/rule-versions/evaluations` | Create evaluation run |
| `POST /api/rule-versions/evaluations/from-pipeline` | Persist hard-rule + policy + supplier evaluations from pipeline |
| `POST /api/rule-versions/evaluations/reeval/{request_id}` | Re-evaluate a request |
| `GET /api/rule-versions/evaluations/by-request/{request_id}` | All evaluations for a request |

---

## 3. Logical Layer (Port 8080)

**Purpose:** Procurement decision engine. Runs a 9-step async Python pipeline over every purchase request. Never touches MySQL directly — all data flows through the Org Layer.

### File Structure

```
backend/logical_layer/
  app/
    __init__.py
    main.py                  # FastAPI app, lifespan (creates httpx + anthropic clients)
    config.py                # Pydantic Settings: ORGANISATIONAL_LAYER_URL, ANTHROPIC_API_KEY, MODEL
    dependencies.py          # FastAPI dependency injection for clients

    clients/
      organisational.py      # OrganisationalClient — async httpx wrapper for all Org Layer calls
      llm.py                 # LLMClient — async Anthropic wrapper, structured output via tool_use

    models/
      common.py              # Shared types: RequestData, SupplierData, PricingData, etc.
      pipeline_io.py         # Pydantic models for every step's input/output
      output.py              # Final output model (matches examples/example_output.json)

    routers/
      pipeline.py            # POST /api/pipeline/process, POST /api/pipeline/process-batch
      steps.py               # Individual step endpoints (debug/testing)
      status.py              # GET /api/pipeline/status/{id}, /result/{id}, /runs, /audit/{id}

    pipeline/
      runner.py              # PipelineRunner — orchestrates steps 1–9, manages logging
      logger.py              # PipelineLogger — step telemetry + audit log via Org Layer

      steps/
        fetch.py             # Step 1: Fetch request + overview data (parallel calls)
        validate.py          # Step 2: Validate (deterministic + LLM contradiction detection)
        filter.py            # Step 3: Filter & enrich compliant suppliers
        comply.py            # Step 4: Per-supplier compliance checks
        rank.py              # Step 5: True-cost ranking
        policy.py            # Step 6: Evaluate procurement policy
        escalate.py          # Step 7: Merge escalations from 3 sources
        recommend.py         # Step 8: Recommendation status (deterministic) + prose (LLM)
        assemble.py          # Step 9: Assemble final output + LLM enrichment

    utils.py                 # normalize_delivery_countries, normalize_scenario_tags,
                             #   coerce_budget, coerce_quantity, COUNTRY_TO_REGION

  Dockerfile
  .dockerignore
  requirements.txt           # fastapi, uvicorn, httpx, pydantic-settings, python-dotenv, anthropic
  .env.example               # ORGANISATIONAL_LAYER_URL, ANTHROPIC_API_KEY, ANTHROPIC_MODEL
  tests/
    test_utils.py            # 30 tests for utility functions
    test_models.py           # 22 tests for Pydantic model validation
    test_llm_client.py       # 4 tests for LLM client
    test_pipeline_steps.py   # 35 tests for all pipeline steps
    test_pipeline_runner.py  # 11 tests for full pipeline runner
    test_routers.py          # 18 tests for API endpoints
```

### API Endpoints

#### Pipeline Execution
| Endpoint | Description |
|----------|-------------|
| `POST /api/pipeline/process` | Process a single request. Body: `{"request_id": "REQ-000004"}`. Returns full pipeline output. Side effects: creates run record, step entries, audit logs, updates request status. |
| `POST /api/pipeline/process-batch` | Process multiple requests concurrently. Body: `{"request_ids": [...], "concurrency": 5}`. Returns 202 with batch_id. Uses `asyncio.Semaphore`. |

#### Status & Results
| Endpoint | Description |
|----------|-------------|
| `GET /api/pipeline/status/{request_id}` | Latest run status: run_id, status, timing, recommendation_status, escalation_count, confidence_score |
| `GET /api/pipeline/result/{request_id}` | Full pipeline output from latest successful run (in-memory cache, falls back to Org Layer pipeline_results) |
| `GET /api/pipeline/runs` | List all pipeline runs (proxied to Org Layer) |
| `GET /api/pipeline/runs/{run_id}` | Single run with all step entries (proxied) |

#### Audit
| Endpoint | Description |
|----------|-------------|
| `GET /api/pipeline/audit/{request_id}` | Full audit trail for a request (proxied to Org Layer) |
| `GET /api/pipeline/audit/{request_id}/summary` | Aggregated audit summary (proxied) |

#### Health
| Endpoint | Description |
|----------|-------------|
| `GET /health` | `{"status": "ok", "org_layer": "reachable", "llm": "configured", "version": "2.0.0"}` |

### Request Status State Machine

```
new ──► in_review ──► evaluated   (proceed / proceed_with_conditions)
                  └──► escalated  (cannot_proceed)
                  └──► error      (pipeline failure)
         ▲
         └── set immediately when processing starts
```

---

## 4. Pipeline Flow (9 Steps)

```
Input: { "request_id": "REQ-000004" }
               │
   ┌───────────▼───────────┐
   │  Step 1: FETCH        │  GET /api/analytics/request-overview/{id}
   │                       │  GET /api/escalations/by-request/{id}   ← parallel
   └───────────┬───────────┘
               │
   ┌───────────▼───────────┐
   │  Step 2: VALIDATE     │  Deterministic checks + LLM contradiction detection
   └──────┬────────────────┘
          │
     [BRANCH: missing critical fields?]
          │ yes → format_invalid_response → return early
          │ no ↓
   ┌──────▼───────┐
   │ Step 3: FILTER│  Enrich compliant_suppliers from overview
   └──────┬───────┘
          │
   ┌──────▼───────┐
   │ Step 4: COMPLY│  Per-supplier restriction, delivery, residency, capacity checks
   └──────┬───────┘
          │
   ┌──────▼───────┐
   │ Step 5: RANK  │  True-cost ranking formula
   └──────┬───────┘
          │
   ┌──────┴──────┐
   │             │           ← parallel
   ▼             ▼
Step 6:       Step 7:
POLICY        ESCALATIONS
   │             │
   └──────┬──────┘
          │
   ┌──────▼───────┐
   │ Step 8:      │  Deterministic status + LLM prose
   │ RECOMMEND    │
   └──────┬───────┘
          │
   ┌──────▼───────┐
   │ Step 9:      │  Combine all + LLM enrichment
   │ ASSEMBLE     │
   └──────┬───────┘
          │
       Output
```

### Parallelism Strategy

| Phase | Steps | Mechanism |
|-------|-------|-----------|
| Fetch | 1a (overview) + 1b (escalations) | `asyncio.gather()` |
| Sequential | 2 → 3 → 4 → 5 | `await` (each depends on prior output) |
| Parallel | 6 (policy) + 7 (escalation merge) | `asyncio.gather()` |
| Sequential | 8 → 9 | `await` |

### Step Details

| Step | Module | LLM? | Description |
|------|--------|------|-------------|
| 1 FETCH | `steps/fetch.py` | No | Parallel: `request-overview` + `escalations/by-request`. Returns `FetchResult` with all pipeline data. |
| 2 VALIDATE | `steps/validate.py` | Yes | Phase A: deterministic rule checks (dynamic rules or fallback) for null checks + budget/lead-time feasibility. Phase B: Direct LLM contradiction detection (temperature=0, detailed prompt, `LLMValidationResult` schema) + `requester_instruction` extraction. Each contradiction preserves specific description for audit trail. |
| 3 FILTER | `steps/filter.py` | No | Enrich `compliant_suppliers` from overview with pricing tiers, scores, preferred flag. Flag suppliers with no pricing tier. |
| 4 COMPLY | `steps/comply.py` | Maybe | Per-supplier: global restriction, country-scoped restriction, value-conditional restriction, delivery coverage, data residency, capacity. Calls `check-restricted` for borderline cases. |
| 5 RANK | `steps/rank.py` | No | `true_cost = total_price / (quality/100) / ((100-risk)/100)`. ESG divisor added when `esg_requirement=true`. Falls back to quality-score ranking when quantity is null. |
| 6 POLICY | `steps/policy.py` | No | Approval threshold, preferred supplier analysis, restricted supplier analysis, category rules, geography rules — all from `FetchResult`. |
| 7 ESCALATE | `steps/escalate.py` | No | Merge Org Layer escalations (base) + pipeline-discovered issues + LLM-detected contradictions. Deduplicates by `rule_id`, keeps more specific trigger description. |
| 8 RECOMMEND | `steps/recommend.py` | Yes | Deterministic status (`proceed` / `proceed_with_conditions` / `cannot_proceed`). LLM generates `reason` + `preferred_supplier_rationale`. Template fallback if LLM fails. |
| 9 ASSEMBLE | `steps/assemble.py` | Yes | LLM enriches validation issues (severity, action_required) and generates per-supplier recommendation notes. Dynamic currency-suffixed keys (`unit_price_eur`, `total_price_usd`, etc.). |

---

## 5. Inter-Service Contract

### Org Layer Endpoints Called by the Pipeline

| Endpoint | Step | Purpose |
|----------|------|---------|
| `GET /api/analytics/request-overview/{id}?pipeline_mode=true` | Step 1 | Primary data: request, compliant suppliers, pricing, rules, tier, awards (pipeline_mode=true required for raw data) |
| `GET /api/escalations/by-request/{id}` | Step 1 | Deterministic escalations from Org Layer engine |
| `GET /api/analytics/check-restricted` | Step 4 | Targeted restriction check for borderline suppliers |
| `PUT /api/requests/{id}` | Runner | Status updates (in_review → evaluated / escalated / error) |
| `POST /api/logs/runs` | Logger | Create pipeline run record |
| `PATCH /api/logs/runs/{run_id}` | Logger | Finalize run |
| `POST /api/logs/entries` | Logger | Create step log entry |
| `PATCH /api/logs/entries/{entry_id}` | Logger | Update step entry with timing + output |
| `POST /api/logs/audit/batch` | Logger | Flush audit log entries |
| `POST /api/rule-versions/evaluations/from-pipeline` | Runner | Persist evaluation data |
| `POST /api/pipeline-results/` | Runner | Persist full pipeline output for frontend |
| `GET /api/pipeline-results/latest/{request_id}` | Status router | Retrieve persisted result on cache miss |
| `GET /api/logs/runs[/{run_id}]` | Status router | Proxied read |
| `GET /api/logs/by-request/{request_id}` | Status router | Proxied read |
| `GET /api/logs/audit/by-request/{request_id}` | Audit router | Proxied read |
| `GET /api/logs/audit/summary/{request_id}` | Audit router | Proxied read |
| `GET /health` | Health check | Verify Org Layer connectivity |

### `request-overview` Required Fields

The Logical Layer depends on these fields being present in the `request-overview` response:

- Request fields: `request_text`, `created_at`, `request_language`, `unit_of_measure`
- Compliant supplier fields: `capacity_per_month` (for capacity compliance checks)
- Multi-country: suppliers must be intersected across **all** delivery countries, pricing looked up for all regions, geography rules collected for every country

---

## 6. Database Schema

**38 MySQL tables on AWS RDS (`chainiq-data`)**

| Group | Tables | Count |
|-------|--------|-------|
| Reference data | categories, suppliers, supplier_categories, supplier_service_regions, pricing_tiers | 5 |
| Requests | requests, request_delivery_countries, request_scenario_tags | 3 |
| Historical | historical_awards | 1 |
| Approval policies | approval_thresholds, approval_threshold_managers, approval_threshold_deviation_approvers | 3 |
| Preferred/restricted | preferred_suppliers_policy, preferred_supplier_region_scopes, restricted_suppliers_policy, restricted_supplier_scopes | 4 |
| Rules | category_rules, geography_rules, geography_rule_countries, geography_rule_applies_to_categories, escalation_rules, escalation_rule_currencies | 6 |
| Rule versioning | rule_definitions, rule_versions, rule_change_logs, evaluation_runs | 4 |
| Evaluation checks | hard_rule_checks, policy_checks, supplier_evaluations | 3 |
| Escalations | escalations, escalation_logs | 2 |
| Pipeline results | pipeline_results | 1 |
| Pipeline logging | pipeline_runs, pipeline_log_entries | 2 |
| Audit logging | audit_logs, evaluation_run_logs, policy_change_logs, policy_check_logs | 4 |

### Critical Data Quirks

| Quirk | Detail |
|-------|--------|
| Inconsistent policy schema | EUR/CHF thresholds use `min_amount`/`max_amount`/`min_supplier_quotes`/`managed_by`/`deviation_approval_required_from`. USD uses `min_value`/`max_value`/`quotes_required`/`approvers`/`policy_note`. Org Layer normalizes at DB level. |
| Supplier rows are per-category | SUP-0001 (Dell) appears 5 times in `suppliers.csv`. Join on `(supplier_id, category_l1, category_l2)`. |
| `is_restricted` is unreliable | The boolean in suppliers is a hint. Always check `restricted_suppliers_policy` for actual scope (global, country-scoped, or value-conditional). |
| Quantity can be null or contradictory | Some requests have `quantity: null` or a field that conflicts with `request_text`. |
| Non-English requests | Languages: `en`, `fr`, `de`, `es`, `pt`, `ja`. LLM handles natively. |
| `service_regions` is semicolon-delimited | Split on `;`, not `,`. |
| `budget_amount` as string | MySQL decimal → JSON string. Must `float()`. |
| `quantity` as string | Arrives as `"240.0"`. Must `int(float())`. |

---

## 7. Escalation Rules Reference

| Rule | Trigger | Escalate To | Blocking | Detection |
|------|---------|-------------|----------|-----------|
| ER-001 | Missing required info (budget, quantity, category) | Requester Clarification | Yes | Deterministic: null field checks (Step 2) |
| ER-002 | Preferred supplier is restricted | Procurement Manager | Yes | Org Layer engine + Step 4 compliance |
| ER-003 | Strategic sourcing approval tier (value > tier 3) | Head of Strategic Sourcing / CPO | No | Org Layer engine via approval tier |
| ER-004 | No compliant supplier with valid pricing | Head of Category | Yes | Org Layer engine + Steps 4/5 |
| ER-005 | Data residency constraint unsatisfiable | Data Protection Officer | Yes | Org Layer engine + Step 4 residency check |
| ER-006 | Single supplier capacity risk | Head of Category | Yes | Org Layer engine + Step 4 capacity check |
| ER-007 | Influencer Campaign Management (brand safety) | Head of Marketing | Yes | Org Layer engine (category-based) |
| ER-008 | Preferred supplier unregistered for USD delivery scope | Category Manager | Yes | Org Layer engine |
| AT-xxx | Single-supplier instruction vs. multi-quote threshold | Procurement Manager | Yes | Multi-language pattern matching + LLM instruction extraction |

### Escalation Merge Algorithm

Three sources are merged into a single deduplicated list:

1. **Org Layer escalations** (base set, from Step 1 fetch)
2. **Pipeline-discovered issues** (Steps 2–5, with specific figures and numbers)
3. **LLM-detected contradictions** (Step 2, requester instruction conflicts)

Merge rule: same `rule_id` → keep the more specific trigger description (longer string). Pipeline triggers win because they have exact numbers. Assign sequential `ESC-001`, `ESC-002`, … IDs.

---

## 8. Logging Architecture

Two independent logging streams both written to the Org Layer.

### Stream A: Pipeline Run Telemetry (step-level timing)

**Tables:** `pipeline_runs` + `pipeline_log_entries`

**Lifecycle:**
```
POST /api/logs/runs          ← pipeline starts
POST /api/logs/entries       ← each step starts
PATCH /api/logs/entries/{id} ← each step ends (timing, output_summary, metadata_)
PATCH /api/logs/runs/{id}    ← pipeline ends (status, total_duration_ms, steps_completed)
```

**Steps logged in order:**

| # | Step Name | Description |
|---|-----------|-------------|
| 1 | `fetch_overview` | Fetch request + overview + escalations |
| 2 | `validate_request` | Deterministic + LLM validation |
| 3 | `format_invalid_response` | Early exit only |
| 3 | `filter_suppliers` | Filter & enrich suppliers |
| 4 | `check_compliance` | Per-supplier compliance checks |
| 5 | `rank_suppliers` | True-cost ranking |
| 6 | `evaluate_policy` | Policy evaluation |
| 7 | `compute_escalations` | Escalation merge |
| 8 | `generate_recommendation` | Recommendation + LLM prose |
| 9 | `assemble_output` | Final assembly + LLM enrichment |

### Stream B: Audit Logging (human-readable decision trail)

**Table:** `audit_logs`

**Emission pattern:** Steps buffer entries, flush via `POST /api/logs/audit/batch` after step completion (minimizes HTTP calls).

**Audit categories:**

| Category | Step | Example |
|----------|------|---------|
| `data_access` | fetch | "Fetched overview for REQ-000004: 4 compliant suppliers" |
| `validation` | validate | "Budget EUR 25,199.55 insufficient: minimum total EUR 35,712.00" |
| `supplier_filter` | filter | "Included SUP-0007 (Bechtle): covers IT > Docking Stations in DE" |
| `compliance` | comply | "Excluded SUP-0008 (Computacenter): risk_score 34 exceeds threshold" |
| `pricing` | rank | "SUP-0007: tier 100-499 units, unit EUR 148.80, total EUR 35,712.00" |
| `ranking` | rank | "Ranked 3 suppliers by true_cost. #1: SUP-0007 (EUR 43,551.22)" |
| `policy` | policy | "Applied AT-002: contract value EUR 35,712 > EUR 25,000. 2 quotes required" |
| `escalation` | escalate | "ER-001 triggered. Escalate to Requester Clarification. BLOCKING" |
| `recommendation` | recommend | "Status: cannot_proceed. 3 blocking escalations. Confidence: 0%" |

### Truncation Rules

Before storing `input_summary` / `output_summary`:
- Strings: capped at 500 characters
- Dicts: capped at 30 keys
- Lists > 5 items: `{"_type": "list", "_length": N, "_sample": [first 3]}`
- Recursion depth: capped at 3 levels
- Error messages: capped at 2000 characters

---

## 9. LLM Integration

**Model:** `claude-sonnet-4-6` (configurable via `ANTHROPIC_MODEL`)

**Client:** One `anthropic.AsyncAnthropic` instance created at app startup via FastAPI lifespan. Never re-created per request.

**Structured output pattern:** All LLM calls use Anthropic `tool_use` with `tool_choice: {type: "tool", name: "structured_output"}` and the response model's `model_json_schema()` as the tool input schema. Pydantic validates the tool block input. The `structured_call` method accepts an optional `temperature` parameter for deterministic calls.

### LLM Calls Per Pipeline Run

| Step | Purpose | Fallback if LLM fails |
|------|---------|----------------------|
| Step 2 VALIDATE | Detect contradictions between `request_text` and structured fields. Extract `requester_instruction`. Uses `temperature=0` for deterministic results. Direct LLM path with detailed `VALIDATION_SYSTEM_PROMPT` (VAL-006 dynamic rule is deprecated). | Empty issues list + no instruction |
| Step 8 RECOMMEND | Generate `reason` (1-3 sentences) + `preferred_supplier_rationale`. Must cite exact names, prices, rule IDs. | Template prose using deterministic values |
| Step 9 ASSEMBLE | Enrich validation issues with severity + `action_required`. Generate per-supplier `recommendation_note`. | Pass-through issues unchanged; empty notes |

**LLM failure handling:** Logged as audit entry (`category: "general"`, `level: "warn"`). Sets `llm_fallback: true` in step metadata. Pipeline output remains valid — just with less polished prose.

---

## 10. Confidence Scoring

Each recommendation includes a `confidence_score` (0–100):

```python
score = 100

# Blocking escalation → hard 0
if blocking_escalations:
    return 0

score -= len(non_blocking_escalations) * 10

# Validation issue penalties
severity_penalty = {"critical": 15, "high": 10, "medium": 5, "low": 2}
for issue in validation_issues:
    score -= severity_penalty[issue.severity]

# Bonus: clear winner (>20% gap over #2)
if len(ranked) >= 2:
    gap = (ranked[1].true_cost - ranked[0].true_cost) / ranked[0].true_cost
    if gap > 0.20:
        score += 10

# Bonus: preferred supplier is top-ranked
if ranked and ranked[0].preferred:
    score += 5

return max(0, min(100, score))
```

| Range | Meaning |
|-------|---------|
| 0 | Cannot proceed — blocking escalations present |
| 1–30 | Low confidence |
| 31–60 | Moderate confidence |
| 61–80 | High confidence |
| 81–100 | Very high confidence — clean request, clear winner |

---

## 11. Output Format

The pipeline output matches `examples/example_output.json`. Top-level structure:

```json
{
  "request_id": "REQ-000004",
  "processed_at": "2026-03-19T14:30:12Z",
  "run_id": "550e8400-...",
  "status": "processed | invalid",

  "request_interpretation": {
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
    "requester_instruction": "no exception -- single supplier only"
  },

  "validation": {
    "completeness": "pass | fail",
    "issues_detected": [
      { "issue_id": "V-001", "severity": "critical", "type": "budget_insufficient",
        "description": "...", "action_required": "..." }
    ]
  },

  "policy_evaluation": {
    "approval_threshold": { "rule_applied": "AT-002", "quotes_required": 2, "approvers": [...], ... },
    "preferred_supplier": { "supplier": "Dell", "status": "eligible", "is_preferred": true, ... },
    "restricted_suppliers": { "SUP-0008_Computacenter": { "restricted": false, "note": "..." } },
    "category_rules_applied": [],
    "geography_rules_applied": []
  },

  "supplier_shortlist": [
    {
      "rank": 1,
      "supplier_id": "SUP-0007",
      "supplier_name": "Bechtle Workplace Solutions",
      "preferred": true,
      "incumbent": true,
      "unit_price_eur": 148.80,
      "total_price_eur": 35712.00,
      "standard_lead_time_days": 26,
      "expedited_lead_time_days": 18,
      "quality_score": 82,
      "risk_score": 19,
      "esg_score": 72,
      "policy_compliant": true,
      "recommendation_note": "..."
    }
  ],

  "suppliers_excluded": [
    { "supplier_id": "SUP-0008", "supplier_name": "Computacenter", "reason": "..." }
  ],

  "escalations": [
    { "escalation_id": "ESC-001", "rule": "ER-001", "trigger": "...",
      "escalate_to": "Requester Clarification", "blocking": true }
  ],

  "recommendation": {
    "status": "cannot_proceed",
    "reason": "Three blocking issues prevent autonomous award...",
    "preferred_supplier_if_resolved": "Bechtle Workplace Solutions",
    "minimum_budget_required": 35712.00,
    "minimum_budget_currency": "EUR",
    "confidence_score": 0
  },

  "audit_trail": {
    "policies_checked": ["AT-002", "ER-001", "ER-004"],
    "supplier_ids_evaluated": ["SUP-0001", "SUP-0007", "SUP-0008"],
    "pricing_tiers_applied": "100-499 units (EU region, EUR)",
    "data_sources_used": ["requests.json", "suppliers.csv", "pricing.csv", "policies.json", "historical_awards.csv"],
    "historical_awards_consulted": true,
    "historical_award_note": "..."
  }
}
```

**Currency keys are dynamic:** `unit_price_eur` / `unit_price_usd` / `unit_price_chf` depending on the request's `currency` field.

---

## 12. Data Normalization Helpers

All helpers live in `app/utils.py`. All pipeline steps import from here.

| Function | Purpose |
|----------|---------|
| `normalize_delivery_countries(raw)` | Handles `["DE"]` and `[{"country_code": "DE"}]` formats |
| `normalize_scenario_tags(raw)` | Handles `["standard"]` and `[{"tag": "standard"}]` formats |
| `coerce_budget(val) → float \| None` | `float(val)`, returns None on failure |
| `coerce_quantity(val) → int \| None` | `int(float(val))`, handles `"240.0"` |
| `country_to_region(code) → str` | Maps country codes to regions via `COUNTRY_TO_REGION` dict |
| `primary_delivery_country(request_data) → str` | First delivery country, falls back to `request_data["country"]` |

**`COUNTRY_TO_REGION` mapping:**

| Region | Countries |
|--------|-----------|
| EU | DE, FR, NL, BE, AT, IT, ES, PL, UK |
| CH | CH |
| Americas | US, CA, BR, MX |
| APAC | SG, AU, IN, JP |
| MEA | UAE, ZA |

---

## 13. Docker & Deployment

### Docker Compose (`backend/docker-compose.yml`)

```yaml
services:
  organisational-layer:
    build: ./organisational_layer
    ports: ["8000:8000"]
    env_file: ./organisational_layer/.env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
    networks: [chainiq]

  logical-layer:
    build: ./logical_layer
    ports: ["8080:8080"]
    env_file: ./logical_layer/.env
    depends_on:
      organisational-layer:
        condition: service_healthy
    networks: [chainiq]

networks:
  chainiq:
    name: chainiq-network
    external: true
```

### Local Development

```bash
# 1. Create shared network (one-time)
docker network create chainiq-network

# 2. Configure env files
cp backend/organisational_layer/.env.example backend/organisational_layer/.env   # fill DB credentials
cp backend/logical_layer/.env.example backend/logical_layer/.env                 # fill ANTHROPIC_API_KEY

# 3. Start backend stack
cd backend && docker compose up --build -d && cd ..

# 4. Run without Docker (Org Layer)
cd backend/organisational_layer
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 5. Run without Docker (Logical Layer)
cd backend/logical_layer
source .venv/bin/activate
uvicorn app.main:app --reload --port 8080
```

### Dockerfiles

| Service | Base | Port | Notes |
|---------|------|------|-------|
| Organisational Layer | `python:3.14-slim` | 8000 | Multi-stage (dev + runtime) |
| Logical Layer | `python:3.14-slim` | 8080 | Single-stage, `.dockerignore` excludes `.venv`, `__pycache__`, `.env` |

### Environment Variables

| Service | Variable | Description |
|---------|----------|-------------|
| Org Layer | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | MySQL connection |
| Org Layer | `LOGICAL_LAYER_URL` | Internal URL of the Logical Layer |
| Logical Layer | `ORGANISATIONAL_LAYER_URL` | Internal URL of the Org Layer (default: `http://organisational-layer:8000`) |
| Logical Layer | `ANTHROPIC_API_KEY` | Claude API key |
| Logical Layer | `ANTHROPIC_MODEL` | Model name (default: `claude-sonnet-4-6`) |

---

## 14. Testing

### Organisational Layer (106 tests)

```bash
cd backend/organisational_layer
source .venv/bin/activate
python -m pytest tests/ -v
```

Requires a live MySQL database configured via `.env`.

| File | Tests | Coverage |
|------|-------|---------|
| `tests/test_api.py` | 97 | All API endpoints: health, categories, suppliers, requests, awards, policies, rules, escalations, analytics, pipeline logs, audit logs, rule versions, intake |
| `tests/test_escalation_service.py` | 6 | Escalation evaluation engine (ER-001..008 + AT conflict) |
| `tests/test_escalation_router.py` | 3 | Escalation router endpoints (mocked DB) |

### Logical Layer (136 tests)

```bash
cd backend/logical_layer
source .venv/bin/activate
python -m pytest tests/ -v
```

Does not require a live database — uses mocked Org Layer responses.

| File | Tests | Coverage |
|------|-------|---------|
| `tests/test_utils.py` | 30 | Utility functions: coerce, normalize, truncate, date parsing |
| `tests/test_models.py` | 22 | Pydantic model validation and edge cases |
| `tests/test_llm_client.py` | 4 | LLM client: success, no tool_use block, API error, invalid schema |
| `tests/test_pipeline_steps.py` | 35 | All pipeline steps: fetch, validate, filter, comply, rank, escalate, recommend |
| `tests/test_pipeline_runner.py` | 11 | Full pipeline runner: success, caching, early exit, error handling, audit trail |
| `tests/test_routers.py` | 18 | All API endpoints: health, process, batch, status, result, runs, audit, step endpoints |
