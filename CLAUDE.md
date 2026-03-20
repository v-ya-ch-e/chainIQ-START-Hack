# CLAUDE.md — Project Context

## What This Is

This is a hackathon project for **ChainIQ @ START Hack 2026**. The challenge is to build an **Audit-Ready Autonomous Sourcing Agent** — a prototype that converts unstructured purchase requests into structured, defensible supplier comparisons with transparent reasoning and escalation logic.

## The Domain

Enterprise procurement. A global company (19 countries, 3 currencies, 4 procurement categories) receives hundreds of purchase requests from internal stakeholders. These requests are messy, incomplete, sometimes contradictory, and written in multiple languages. Procurement teams must interpret them, apply internal governance rules, compare suppliers, and produce auditable decisions.

## What the System Must Do

Given a free-text purchase request, the agent must:

1. **Parse** — Extract structured fields (category, quantity, budget, delivery constraints) from unstructured text
2. **Validate** — Detect missing info, contradictions, budget/quantity mismatches between text and fields
3. **Apply Policy** — Determine approval tier, required quotes, check preferred/restricted suppliers, enforce category and geography rules
4. **Find Suppliers** — Filter to compliant suppliers covering the right category, region, and currency
5. **Price** — Look up correct pricing tier based on quantity, calculate total cost (standard and expedited)
6. **Rank** — Score suppliers on price, quality, risk, ESG, lead time feasibility
7. **Explain** — Produce human-readable rationale for every inclusion, exclusion, and ranking decision
8. **Escalate** — When the agent cannot make a compliant autonomous decision, trigger the correct escalation rule and name the target

## Key Files

| File | Purpose |
|------|---------|
| `data/requests.json` | 304 purchase requests (the inputs) |
| `data/suppliers.csv` | 40 suppliers × multiple categories = 151 rows |
| `data/pricing.csv` | 599 pricing tiers with lead times |
| `data/categories.csv` | 30 category definitions (L1/L2 taxonomy) |
| `data/policies.json` | 6 policy sections: thresholds, preferred, restricted, category rules, geography rules, escalation rules |
| `data/historical_awards.csv` | 590 historical decisions across 180 requests |
| `examples/example_output.json` | Reference output format for REQ-000004 |
| `examples/example_request.json` | Reference input for REQ-000004 |

## Critical Data Quirks

- **Inconsistent policy schema**: EUR/CHF thresholds use `min_amount`/`max_amount`/`min_supplier_quotes`/`managed_by`/`deviation_approval_required_from`. USD thresholds use `min_value`/`max_value`/`quotes_required`/`approvers`/`policy_note`. Your code must handle both.
- **Supplier rows are per-category**: SUP-0001 (Dell) appears 5 times in `suppliers.csv`, once for each category it serves. Join on `(supplier_id, category_l1, category_l2)`.
- **`is_restricted` is unreliable**: The boolean flag in `suppliers.csv` is a hint only. Always check `policies.json` `restricted_suppliers` for the actual restriction scope (global, country-scoped, or value-conditional).
- **Quantity can be null or contradictory**: Some requests have `quantity: null` or a `quantity` field that conflicts with the number stated in `request_text`.
- **Non-English requests**: Languages include `en`, `fr`, `de`, `es`, `pt`, `ja`. The `request_text` field will be in the stated language.
- **124 requests have no historical awards**: This is intentional, not a data error.
- **`service_regions` is semicolon-delimited**: Not comma-delimited. Split on `;`.

## Judging Criteria

| Criteria | Weight |
|----------|--------|
| Robustness & Escalation Logic | 25% |
| Feasibility | 25% |
| Reachability | 20% |
| Creativity | 20% |
| Visual Design | 10% |

The judges value **correct uncertainty handling** over confident wrong answers. A system that properly escalates when it cannot decide will outscore one that guesses.

## Presentation

- 5-minute live demo + 3-minute explanation
- Must show: one standard request, one edge case, supplier comparison view, rule application, escalation handling
- Must demonstrate: working prototype, clear reasoning logic, system design explanation, scalability statement

## Tech Stack

- Azure credits available
- Any language, framework, AI tooling, or rules engine is allowed

## Current Full-Stack Wiring (Implemented)

- The project uses **two independent Docker Compose stacks** on a shared network (`chainiq-network`).
- Backend stack (`backend/docker-compose.yml`):
  - `organisational-layer` (FastAPI, port 8000) — CRUD + analytics API
  - `logical-layer` (FastAPI, port 8080) — Procurement decision engine
- Frontend stack (`docker-compose.yml` at repo root):
  - `frontend` (Next.js, port 3000)
  - `mysql` (MySQL 8.4, port 3306) — local dev only
  - `migrator` (one-shot data bootstrap using `database_init/migrate.py` + `migrate_rules.py` + `migrate_dynamic_rules.py`)
- Root orchestration files:
  - `docker-compose.yml` (frontend + MySQL + migrator)
  - `docker-compose.override.yml` (development hot-reload for frontend)
  - `.env.example` (frontend stack env contract)
- Container files:
  - `frontend/Dockerfile`, `frontend/.dockerignore`
  - `backend/organisational_layer/Dockerfile`, `backend/organisational_layer/.dockerignore`
  - `backend/logical_layer/Dockerfile`

## Local Runbook

1. Create shared network (one-time):
   - `docker network create chainiq-network`
2. Copy env files:
   - `cp .env.example .env`
   - `cp backend/organisational_layer/.env.example backend/organisational_layer/.env`
   - `cp backend/logical_layer/.env.example backend/logical_layer/.env`
3. Start backend stack:
   - `cd backend && docker compose up --build -d && cd ..`
4. Start frontend stack (dev mode):
   - `docker compose up --build`
5. Bootstrap database (first run / after reset):
   - `docker compose --profile tools run --rm migrator`

Default local URLs:

- Frontend: `http://localhost:3000`
- Organisational Layer: `http://localhost:8000`
- Logical Layer: `http://localhost:8080`
- MySQL: `localhost:3306`

## Integration Notes

- Frontend API calls are same-origin (`/api/*`) and proxied to backend through Next rewrites.
- Frontend server-side data loaders use `BACKEND_INTERNAL_URL` for container-internal networking.
- Mock fixture pass-through in `frontend/src/lib/data/cases.ts` has been replaced with backend-backed async mapping logic.
- **`request-overview` pipeline gating:** The `GET /api/analytics/request-overview/{id}` endpoint accepts `?pipeline_mode=true|false`. The default (`false`) hides supplier and pricing data for requests that have not been processed through the pipeline, and filters the supplier list to the pipeline's evaluated shortlist for processed requests. The Logical Layer always calls with `pipeline_mode=true` to get the full raw reference data needed for processing.

## Deployment

- Full deployment guide: `DEPLOYMENT.md` (covers local dev, AWS EC2 + RDS, nginx reverse proxy)
- Reference nginx config: `deploy/nginx/aws.conf`
- AWS env template: `.env.aws.example`

## Dynamic Rules Engine

The pipeline uses a dynamic rules engine (`backend/logical_layer/app/pipeline/rule_engine.py`) that evaluates rules fetched from the Org Layer at runtime. Rules are stored in `dynamic_rules` / `dynamic_rule_versions` tables and seeded by `database_init/migrate_dynamic_rules.py`.

### Escalation Rules (ER-001–010 + ER-BUDGET)

| Rule | Condition | Blocking | Target |
|------|-----------|----------|--------|
| ER-001 | Budget or quantity is NULL (missing required info) | Yes | Requester Clarification |
| ER-002 | Preferred supplier is restricted | Yes | Procurement Manager |
| ER-003 | Contract value exceeds strategic tier | No | Head of Strategic Sourcing |
| ER-004 | No compliant supplier found after checks | Yes | Head of Category |
| ER-005 | Data residency unsatisfiable | Yes | Security/Compliance |
| ER-006 | Single supplier capacity risk (only 1 meets qty) | No | Sourcing Excellence Lead |
| ER-007 | Influencer campaign brand safety | No | Marketing Governance Lead |
| ER-008 | Supplier not registered in delivery country | No | Regional Compliance Lead |
| ER-009 | LLM-detected contradictions (non-spec, custom) | **No** | Procurement Manager |
| ER-010 | Lead time infeasible (non-spec, custom) | **No** | Head of Category |
| ER-BUDGET | Budget < minimum supplier price (pipeline-generated) | **No** | Budget Owner / Requester |

### Key Design Constraints

- **ER-009, ER-010, and ER-BUDGET are NOT in the challenge spec** (ER-001–008 only). They must remain non-blocking.
- **Recommendation status considers validation issues**: Critical validation issues (like budget insufficiency) force `proceed_with_conditions` even when no escalation rules fire. Status hierarchy: blocking escalation → `cannot_proceed`, budget insufficient → `proceed_with_conditions`, non-blocking escalations or critical/high issues → `proceed_with_conditions`, else → `proceed`.
- **Risk score threshold**: 70 for non-preferred suppliers (was 30, which excluded too aggressively).
- **Confidence scoring**: Graded (-25/blocking, -10/non-blocking, -20/-10/-5/-2 per validation issue severity) — never immediately zero.
- **`has_contradictions`**: Only checks `contradictory` validation issues, NOT `policy_conflict`.
- **Validation issue type classification**: Dynamic rule results are classified into specific types (`budget_insufficient`, `lead_time_infeasible`) via `_classify_issue_type()` for proper downstream matching, instead of using the generic `validation_rule_failed`.
- **LLM response brevity**: Recommendation prompts capped at 1-2 sentences, enrichment supplier notes at 2-3 sentences. `max_tokens` reduced to 600/1500.
- **Migration idempotency**: `migrate_dynamic_rules.py` uses `ON DUPLICATE KEY UPDATE` to update existing rules.

## LLM-Powered Rule Management

The Escalations page has a "New Rule" button that opens a dialog with a single textarea. The user describes what they want in plain text (new rule or change to existing). The backend (`POST /api/dynamic-rules/parse`) fetches all active rules from the DB, passes them to the LLM alongside the user text, and the LLM decides whether to create a new rule or update an existing one. The user reviews the generated rule and approves it. Backend service: `backend/organisational_layer/app/services/rule_parser.py`.
### LLM Contradiction Detection

- **Direct LLM path only**: Contradiction detection always uses the `VALIDATION_SYSTEM_PROMPT` in `validate.py` with the `LLMValidationResult` Pydantic model. The dynamic rule `VAL-006` (custom_llm) is deprecated and inactive — its vague prompt caused false positives.
- **temperature=0**: Validation LLM calls use `temperature=0` for deterministic results across identical pipeline runs.
- **Each contradiction preserves its description**: Individual contradictions from the LLM are logged as separate audit entries with specific field/description, visible in the frontend decision timeline.
- **Conservative prompt**: The system prompt explicitly lists what IS NOT a contradiction (approximations, omissions, rounding, different wording for same value) to minimize false positives.

## Evaluation Traceability (added via dev merge)

The Org Layer now enriches rule check responses with full traceability metadata:

- **`RuleCheckOut` enrichment**: Hard rule checks and policy checks include `rule_name` (from `rule_definitions`), `version_snapshot` (frozen `rule_config` from `rule_versions`), `dynamic_snapshot` (active row from `dynamic_rule_versions`), and `dynamic_rule_version` (integer version).
- **Dynamic rule version resolution service**: `backend/organisational_layer/app/services/dynamic_rule_versions.py` resolves snapshots with a 3-tier fallback: active version row → latest version row → live `dynamic_rules` row.
- **New endpoints**: `GET /api/rule-versions/dynamic-rule-versions/active/{rule_id}` and `GET /api/rule-versions/dynamic-rule-versions/{rule_id}/at-version/{version_num}` for on-demand snapshot resolution.
- **Evaluation results persistence**: `POST /api/dynamic-rules/evaluation-results` stores bulk evaluation results; `GET /api/dynamic-rules/evaluation-results/by-run/{run_id}` retrieves them.

## Frontend Case Workspace Redesign (added via dev merge)

- **Header actions context**: `frontend/src/components/app-shell/header-actions-context.tsx` provides `setActions`, `setTitleExtra`, and `setBreadcrumbOverride` to let child pages inject actions into the shell header.
- **Dual provider pattern**: The shell wraps pages in both `WorkspaceHeaderActionsProvider` (for list pages with topbar filters) and `HeaderActionsProvider` (for case detail with contextual actions).
- **Enriched rule checks table**: The case workspace displays rule checks with tooltips showing frozen `eval_config.condition` snapshots, rule names from definitions, and dynamic rule versions.
- **Evaluation run history**: The case detail view shows all evaluation runs with per-supplier hard rule and policy check breakdowns, supplier shortlist, and excluded suppliers from each run.
