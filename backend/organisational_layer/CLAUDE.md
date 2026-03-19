# **USER INSTRUCTIONS**

> Always work in .venv
> Always update @CLAUDE.md file to keep it updated about the project
> You should keep this block with user instructions as it is. You can write below everything you want

# **SERVICE OVERVIEW**

FastAPI backend microservice for the ChainIQ procurement platform. Provides CRUD and analytics endpoints for 37 normalised MySQL tables hosted on AWS RDS.

## How to run

```bash
cd backend/organisational_layer
source .venv/bin/activate
cp .env.example .env   # then fill in your RDS credentials
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

## Docker (both services together)

```bash
cd backend
cp organisational_layer/.env.example organisational_layer/.env   # fill in DB credentials
cp logical_layer/.env.example logical_layer/.env                 # default is fine for Docker
docker compose up --build
```

> **Note:** `docker-compose.yml` has moved to `backend/` level to orchestrate both services. The old `organisational_layer/docker-compose.yml` has been removed.

## Testing

**Run tests every time changes are made to `backend/organisational_layer/`.**

```bash
cd backend/organisational_layer
source .venv/bin/activate
python -m pytest tests/ -v
```

Tests require a live MySQL database configured via `.env`. The test suite includes:

- **137 tests total** (128 integration + 9 unit)
- `tests/test_api.py` — 97 integration tests covering all API endpoints (health, categories, suppliers, requests, awards, policies, rules, escalations, analytics, pipeline logs, audit logs, rule versions, intake)
- `tests/test_evaluation_detail.py` — 6 integration tests for evaluation detail endpoint (supplier_shortlist, suppliers_excluded from output snapshot, null/empty/malformed handling)
- `tests/test_dynamic_rules.py` — 25 integration tests for dynamic rules CRUD, versioning, evaluation results, seeded rules
- `tests/test_escalation_service.py` — 6 unit tests for the escalation evaluation engine
- `tests/test_escalation_router.py` — 3 unit tests for escalation router endpoints (mocked DB)

Test dependencies: `pytest`, `httpx` (included in `requirements.txt`).

## Key files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app entry point, CORS, router registration, `/health` endpoint |
| `app/config.py` | Pydantic Settings — reads DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, LOGICAL_LAYER_URL from env |
| `app/database.py` | SQLAlchemy engine, session factory, `get_db` dependency |
| **Models** | |
| `app/models/reference.py` | `Category`, `Supplier`, `SupplierCategory`, `SupplierServiceRegion`, `PricingTier` |
| `app/models/requests.py` | `Request`, `RequestDeliveryCountry`, `RequestScenarioTag` |
| `app/models/historical.py` | `HistoricalAward` |
| `app/models/policies.py` | `ApprovalThreshold` (+ managers, deviation approvers), `PreferredSupplierPolicy` (+ region scopes), `RestrictedSupplierPolicy` (+ scopes), `CategoryRule`, `GeographyRule` (+ countries, applies_to_categories), `EscalationRule` (+ currencies) |
| `app/models/logs.py` | `PipelineRun`, `PipelineLogEntry`, `AuditLog` |
| `app/models/evaluations.py` | `RuleDefinition`, `RuleVersion`, `EvaluationRun`, `HardRuleCheck`, `PolicyCheck`, `SupplierEvaluation`, `RuleChangeLog`, `Escalation`, `EscalationLog`, `PolicyChangeLog`, `EvaluationRunLog`, `PolicyCheckLog` |
| `app/models/pipeline_results.py` | `PipelineResult` — stores full pipeline output JSON for frontend retrieval |
| **Schemas** | |
| `app/schemas/reference.py` | Category, Supplier, PricingTier Pydantic schemas |
| `app/schemas/requests.py` | Request CRUD schemas (create, update, list, detail) |
| `app/schemas/historical.py` | HistoricalAward schemas |
| `app/schemas/policies.py` | Approval threshold, preferred/restricted supplier, category/geography/escalation rule schemas |
| `app/schemas/analytics.py` | Analytics response schemas (compliant suppliers, pricing, approval tier, etc.) |
| `app/schemas/escalations.py` | Escalation queue item schema |
| `app/schemas/logs.py` | Pipeline logging and audit logging schemas |
| `app/schemas/pipeline_results.py` | Pipeline result CRUD schemas (create, list, detail, summary) |
| `app/schemas/rule_versions.py` | Rule definition, version, evaluation, checks, change log schemas |
| `app/schemas/parse.py` | Parse request/response schemas |
| `app/schemas/intake.py` | Intake extraction schemas |
| **Routers** | |
| `app/routers/categories.py` | CRUD for categories |
| `app/routers/suppliers.py` | CRUD for suppliers + sub-resources (categories, regions, pricing) |
| `app/routers/requests.py` | CRUD for purchase requests with delivery countries and scenario tags |
| `app/routers/awards.py` | Read endpoints for historical awards |
| `app/routers/policies.py` | Read endpoints for approval thresholds, preferred/restricted supplier policies |
| `app/routers/rules.py` | Read endpoints for category, geography, and escalation rules |
| `app/routers/escalations.py` | Deterministic escalation queue endpoints + stored escalation updates |
| `app/routers/rule_versions.py` | Rule definitions CRUD, rule versions CRUD, evaluations, hard-rule-checks, policy-checks, change logs |
| `app/routers/parse.py` | Parse text/file into structured purchase requests (uses Anthropic) |
| `app/routers/analytics.py` | Domain-specific analytics: compliant suppliers, pricing lookup, approval tiers, restriction/preferred checks, applicable rules, request overview, spend aggregations, supplier win rates |
| `app/routers/logs.py` | Pipeline logging + audit logging endpoints |
| `app/routers/pipeline_results.py` | Full pipeline output persistence and retrieval (CRUD for frontend) |
| `app/routers/intake.py` | Deterministic intake extraction (regex-based, no LLM) |
| **Services** | |
| `app/services/escalations.py` | Escalation evaluation engine (ER-001..008 + AT conflict detection) |
| `app/services/transaction_workflows.py` | ACID transaction workflows: escalation changes, evaluation triggers, rule updates, policy check overrides |
| `app/services/request_parser.py` | Anthropic-powered text/file → structured request parser |
| **Other** | |
| `LOGGING_API.md` | Full documentation for pipeline and audit logging APIs |
| `Dockerfile` | Python 3.14-slim container, multi-stage (dev + runtime) |
| `requirements.txt` | fastapi, uvicorn, sqlalchemy, pymysql, pydantic-settings, python-dotenv, cryptography, anthropic, pytest, httpx |
| `.env.example` | Template for DB connection env vars |
| `tests/conftest.py` | Shared pytest fixtures (TestClient, DB session) |

## API endpoints summary

### Health
- `GET /health` — returns `{"status": "ok"}`

### CRUD
- `GET/POST /api/categories/`, `GET/PUT/DELETE /api/categories/{id}`
- `GET/POST /api/suppliers/`, `GET/PUT/DELETE /api/suppliers/{id}`, `GET /api/suppliers/{id}/categories|regions|pricing`
- `GET/POST /api/requests/`, `GET/PUT/DELETE /api/requests/{id}` (PUT supports `delivery_countries` and `scenario_tags` replacement)
- `GET /api/awards/`, `GET /api/awards/{id}`, `GET /api/awards/by-request/{id}`
- `GET /api/policies/approval-thresholds[/{id}]`, `GET /api/policies/preferred-suppliers[/{id}]`, `GET /api/policies/restricted-suppliers[/{id}]`
- `GET /api/rules/category[/{id}]`, `GET /api/rules/geography[/{id}]`, `GET /api/rules/escalation[/{id}]`
- `GET /api/escalations/queue`, `GET /api/escalations/by-request/{id}`, `PATCH /api/escalations/{id}`

### Rule Definitions & Versions (`/api/rule-versions/`)
- `GET/POST /api/rule-versions/definitions`, `GET/PATCH/DELETE /api/rule-versions/definitions/{rule_id}`
- `GET/POST /api/rule-versions/versions`, `GET/PATCH /api/rule-versions/versions/{version_id}`, `GET /api/rule-versions/versions/active/{rule_id}`
- `GET /api/rule-versions/logs/rule-change[/{log_id}]`
- Evaluations: `GET /api/rule-versions/evaluations/{run_id}` (returns `supplier_shortlist` + `suppliers_excluded` from output snapshot), `POST /api/rule-versions/evaluations`, `POST /api/rule-versions/evaluations/full`, `POST /api/rule-versions/evaluations/from-pipeline`, `POST /api/rule-versions/evaluations/reeval/{request_id}`, `GET /api/rule-versions/evaluations/by-request/{request_id}`
- Hard rule checks: `GET /api/rule-versions/hard-rule-checks[/{check_id}]`, `POST /api/rule-versions/evaluations/{run_id}/hard-rule-checks`
- Policy checks: `GET/PATCH /api/rule-versions/policy-checks[/{check_id}]`, `POST /api/rule-versions/evaluations/{run_id}/policy-checks`
- Audit logs: `GET /api/rule-versions/logs/evaluation-run/{run_id}`, `GET /api/rule-versions/logs/escalation/{escalation_id}`, `GET /api/rule-versions/logs/policy-change/{escalation_id}`, `GET /api/rule-versions/logs/policy-check`

### Parse
- `POST /api/parse/text` — parse raw procurement text into structured request (Anthropic)
- `POST /api/parse/file` — parse uploaded file (PDF/image) into structured request (Anthropic)

### Pipeline Results
- `POST /api/pipeline-results/` — save full pipeline output (called by logical layer)
- `GET /api/pipeline-results/` — list results (paginated; filter by `request_id`, `status`, `recommendation_status`)
- `GET /api/pipeline-results/{run_id}` — get single result with full output
- `GET /api/pipeline-results/by-request/{request_id}` — all results for a request
- `GET /api/pipeline-results/latest/{request_id}` — most recent result for a request
- `DELETE /api/pipeline-results/{run_id}` — delete a result

### Pipeline Logging
- `POST /api/logs/runs`, `PATCH /api/logs/runs/{run_id}`, `GET /api/logs/runs[/{run_id}]`, `GET /api/logs/by-request/{request_id}`
- `POST /api/logs/entries`, `PATCH /api/logs/entries/{entry_id}`

### Audit Logging
- `POST /api/logs/audit`, `POST /api/logs/audit/batch`
- `GET /api/logs/audit/by-request/{request_id}`, `GET /api/logs/audit/summary/{request_id}`, `GET /api/logs/audit`

### Intake
- `POST /api/intake/extract` — deterministic extraction (regex-based, returns draft fields, per-field confidence/status, missing-required list, and warnings)

### Analytics
- `GET /api/analytics/compliant-suppliers` — non-restricted suppliers for category+country
- `GET /api/analytics/pricing-lookup` — pricing tier for supplier+category+region+quantity
- `GET /api/analytics/approval-tier` — approval threshold for currency+amount
- `GET /api/analytics/check-restricted` — restriction check for supplier+category+country
- `GET /api/analytics/check-preferred` — preferred status for supplier+category+region
- `GET /api/analytics/applicable-rules` — category and geography rules for a context
- `GET /api/analytics/request-overview/{id}?pipeline_mode=false` — comprehensive request evaluation (supplier/pricing data gated by pipeline status; use `pipeline_mode=true` for raw reference data)
- `GET /api/analytics/spend-by-category` — aggregated historical spend by category
- `GET /api/analytics/spend-by-supplier` — aggregated historical spend by supplier
- `GET /api/analytics/supplier-win-rates` — win rates from historical awards

## Database

38 MySQL tables on AWS RDS (`chainiq-data`), grouped into:

- **Reference data** (5): categories, suppliers, supplier_categories, supplier_service_regions, pricing_tiers
- **Requests** (3): requests, request_delivery_countries, request_scenario_tags
- **Historical** (1): historical_awards
- **Approval policies** (3): approval_thresholds, approval_threshold_managers, approval_threshold_deviation_approvers
- **Preferred/restricted** (4): preferred_suppliers_policy, preferred_supplier_region_scopes, restricted_suppliers_policy, restricted_supplier_scopes
- **Rules** (6): category_rules, geography_rules, geography_rule_countries, geography_rule_applies_to_categories, escalation_rules, escalation_rule_currencies
- **Rule versioning** (4): rule_definitions, rule_versions, rule_change_logs, evaluation_runs
- **Evaluation checks** (3): hard_rule_checks, policy_checks, supplier_evaluations
- **Escalations** (2): escalations, escalation_logs
- **Pipeline results** (1): pipeline_results
- **Pipeline logging** (2): pipeline_runs, pipeline_log_entries
- **Audit logging** (4): audit_logs, evaluation_run_logs, policy_change_logs, policy_check_logs

## Tech stack

- **Python 3.14** / FastAPI / SQLAlchemy 2.0 / PyMySQL
- **MySQL 8** on AWS RDS
- **Anthropic API** for request parsing (claude-sonnet-4-6)
- Docker / docker-compose for deployment (unified compose at `backend/docker-compose.yml`)

## Logical Layer Testing

**Run logical layer tests every time changes are made to `backend/logical_layer/`.**

```bash
cd backend/logical_layer
source .venv/bin/activate  # or: python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

**136 tests** covering:
- `tests/test_utils.py` — 30 tests for utility functions (coerce, normalize, truncate, date parsing)
- `tests/test_models.py` — 22 tests for Pydantic model validation and edge cases
- `tests/test_llm_client.py` — 4 tests for LLM client (success, no tool_use block, API error, invalid schema)
- `tests/test_pipeline_steps.py` — 35 tests for all pipeline steps (fetch, validate, filter, comply, rank, escalate, recommend)
- `tests/test_pipeline_runner.py` — 11 tests for full pipeline runner (success, caching, early exit, error handling, audit trail)
- `tests/test_routers.py` — 18 tests for all API endpoints (health, process, batch, status, result, runs, audit, step endpoints)

Test dependencies: `pytest`, `pytest-asyncio`, `pytest-cov` (in `requirements.txt`).

## Logical Layer Integration Contract

The logical layer depends on these org layer endpoints:
- `GET /api/analytics/request-overview/{id}?pipeline_mode=true` — must return `request_text`, `created_at`, `request_language`, `unit_of_measure`, `capacity_per_month` in compliant suppliers; `pipeline_mode=true` is required for the pipeline to get raw reference data
- `GET /api/escalations/by-request/{id}` — returns deterministic escalation queue
- `GET /api/analytics/check-restricted` — per-supplier restriction check
- `PUT /api/requests/{id}` — status updates (`in_review`, `evaluated`, `escalated`, `error`)
- `POST /api/logs/runs`, `PATCH /api/logs/runs/{run_id}` — pipeline run lifecycle
- `POST /api/logs/entries`, `PATCH /api/logs/entries/{entry_id}` — step-level logging
- `POST /api/logs/audit/batch` — bulk audit log creation
- `POST /api/rule-versions/evaluations/from-pipeline` — evaluation persistence
- `POST /api/pipeline-results/` — persist full pipeline output for frontend retrieval

## Bugs fixed during code review

### Organisational Layer
1. **Missing `policy_change_logs` table** — SQLAlchemy model existed but the table was never created in the DB. Created it.
2. **Missing `pipeline_runs` / `pipeline_log_entries` tables** — Same issue. Created both tables.
3. **Request update delivery_countries unique constraint violation** — `PUT /api/requests/{id}` would fail when updating delivery_countries because SQLAlchemy didn't flush deletes before inserts. Fixed by adding `db.flush()` between clear and append operations.
4. **Missing `uuid` column in Request/Supplier models** — Both tables have a `NOT NULL UNIQUE` uuid column added by the migration. Added to ORM models with auto-generation default.
5. **`request-overview` missing critical fields** — The `request_dict` in `GET /api/analytics/request-overview/{id}` was missing `request_text`, `created_at`, `request_language`, `unit_of_measure`, and other fields needed by the logical layer. LLM validation was entirely non-functional. Fixed by adding all fields.
6. **`CompliantSupplierOut` missing `capacity_per_month`** — The supplier capacity compliance check in the logical layer never triggered because `capacity_per_month` was not included in the compliant supplier query/schema. Fixed by adding to both query and schema.

6. **`request-overview` multi-country delivery bug** — The endpoint only used the first delivery country for supplier filtering, restriction checks, pricing region lookup, and geography rules. For multi-country requests, this meant suppliers that don't serve all delivery countries were incorrectly included, pricing for other regions was missed, and geography rules for non-primary countries were omitted. Fixed by: intersecting supplier coverage across all delivery countries, checking restrictions against all countries, looking up pricing for all unique regions, and collecting geography rules for every delivery country.

7. **`request-overview` leaked pre-processing supplier data** — The endpoint returned compliant suppliers and pricing tiers for ALL requests, even unprocessed ones. The frontend displayed these as if the request had been evaluated, showing misleading supplier comparisons with pricing/rankings before the pipeline had run. Fixed by adding a `pipeline_mode` query parameter: `pipeline_mode=false` (default, used by frontend) gates supplier/pricing data behind pipeline result existence and filters to the pipeline's evaluated shortlist; `pipeline_mode=true` (used by Logical Layer) returns the full raw reference data needed for pipeline processing.

### Logical Layer
7. **`llm.py` StopIteration crash** — `next()` without default would raise `StopIteration` if the LLM returned no `tool_use` block. Fixed with `next(..., None)` + explicit None check.
8. **`comply.py` silent error swallowing** — The restriction check HTTP call silently ignored all errors with bare `except: pass`, potentially allowing restricted suppliers through. Fixed to log errors.
9. **`rank.py` None formatting crash** — `f"{unit_price:,.2f}"` would crash when `unit_price` is `None` while `total_price` is not. Fixed with None check.
10. **`status.py` redundant assignment** — `latest` was set twice with identical logic. Removed duplicate.
11. **`pipeline.py` batch fire-and-forget** — `asyncio.ensure_future()` (deprecated) was called with `asyncio.gather()` result, which is a Future, not a coroutine — crashes on Python 3.14. Fixed by wrapping in async function and using `asyncio.create_task()`.
12. **`filter.py` arbitrary tier selection** — `_match_pricing_tier` returned the first tier when quantity was None. Fixed to return None consistently.
13. **`logger.py` missing timezone** — `_now_iso()` produced timestamps without timezone suffix. Fixed to append "Z".
14. **Missing `.dockerignore`** — No `.dockerignore` for logical_layer meant `.venv`, `__pycache__`, `.env` etc. could be copied into Docker builds. Added.
