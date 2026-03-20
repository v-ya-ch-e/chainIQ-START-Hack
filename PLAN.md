# PLAN.md — Challenge Strategy & Implementation Plan

## Winning Philosophy

The judging weights tell us what matters:

| Criteria | Weight | What it really means |
|----------|--------|---------------------|
| Robustness & Escalation Logic | **25%** | Handle every edge case correctly. Never output a confident wrong answer. |
| Feasibility | **25%** | Build something that could actually ship. Clean architecture, real code. |
| Reachability | **20%** | Solve the actual procurement problem, not a toy version of it. |
| Creativity | **20%** | Surprise them with something they haven't seen from other teams. |
| Visual Design | **10%** | Clean and clear, but don't over-invest here. |

**Key insight from README**: *"A system that produces confident wrong answers will score lower than one that correctly identifies uncertainty and escalates."* This means escalation accuracy is more important than recommendation accuracy.

---

## Architecture Overview

### Implemented Topology

The system runs as three independent services on a shared Docker network (`chainiq-network`), with an external orchestrator (n8n) driving the procurement pipeline.

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js :3000)                 │
│  5 pages: Overview, Inbox, Case Detail, Escalations, Audit  │
│  shadcn v4 + Tailwind CSS, server components                │
└──────────────────────────┬──────────────────────────────────┘
                           │ Next.js rewrites /api/* →
┌──────────────────────────▼──────────────────────────────────┐
│           Organisational Layer (FastAPI :8000)                │
│  CRUD + Analytics API — 8 routers, 40+ endpoints             │
│  Escalation engine (ER-001..ER-008 + AT conflict detection)  │
│  SQLAlchemy ORM — 22 normalised tables                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ pymysql
┌──────────────────────────▼──────────────────────────────────┐
│                    MySQL 8.4 (AWS RDS)                       │
│  All 6 source datasets normalised into relational tables     │
│  Bootstrap: database_init/migrate.py                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│             Logical Layer (FastAPI :8080)                     │
│  Procurement decision engine — 11 active endpoints           │
│  Calls Organisational Layer via HTTP (never touches DB)       │
│  Uses Anthropic Claude for LLM-powered validation/reasoning  │
└──────────┬──────────────────────┬───────────────────────────┘
           │ HTTP                  │ Anthropic SDK
           ▼                      ▼
  Organisational Layer       Claude (claude-sonnet-4-6)

┌─────────────────────────────────────────────────────────────┐
│                    n8n (external)                             │
│  Orchestrates: validate → filter → compliance → rank →       │
│  policy → escalations → recommendation → assemble            │
│  Calls Logical Layer endpoints with branching logic           │
└─────────────────────────────────────────────────────────────┘
```

### Why This Stack

- **Two-layer backend**: Organisational Layer owns data + governance rules. Logical Layer owns decision logic + LLM integration. Clean separation means policy enforcement is deterministic and auditable.
- **MySQL on RDS**: All 6 source datasets (requests, suppliers, pricing, categories, policies, historical awards) normalised into 22 relational tables at bootstrap. No flat-file loading at runtime.
- **LLM for parsing and reasoning**: Claude is used in `validateRequest.py` (contradiction detection), `generateRecommendation.py` (human-readable reasoning), `assembleOutput.py` (enriching validation issues and supplier notes), and `formatInvalidResponse.py` (summarizing validation failures). All policy and compliance logic is deterministic Python code.
- **n8n orchestration**: All 11 pipeline steps are exposed as independent HTTP endpoints so n8n can chain them with branching logic (validation branch + compliance branch), retries, and human-in-the-loop steps. A convenience endpoint (`processRequest`) also runs the full pipeline in a single call.
- **Next.js frontend**: Server components fetch data from the Organisational Layer via `BACKEND_INTERNAL_URL` (container-internal). No client-side API calls for data loading.

### Docker Compose Topology

Two independent compose files on the shared `chainiq-network`:

**Backend stack** (`backend/docker-compose.yml`):
- `organisational-layer` — FastAPI on port 8000, reads `.env` for DB creds
- `logical-layer` — FastAPI on port 8080, depends on organisational-layer, reads `.env` for `ORGANISATIONAL_LAYER_URL` + `ANTHROPIC_API_KEY`

**Frontend stack** (`docker-compose.yml` at repo root):
- `frontend` — Next.js on port 3000, `BACKEND_INTERNAL_URL` points to organisational-layer
- `mysql` — MySQL 8.4 on port 3306 (local dev only, profile `localdb`)
- `migrator` — one-shot Python script to bootstrap DB (profile `tools`)

---

## Current State — What's Built

### Frontend (status: fully functional)

| Component | Path | Purpose |
|-----------|------|---------|
| Root layout | `frontend/src/app/layout.tsx` | Fonts, TooltipProvider |
| Workspace shell | `frontend/src/components/app-shell/workspace-shell.tsx` | Sidebar, header, breadcrumbs |
| Overview page | `frontend/src/app/(workspace)/page.tsx` | Metrics, blocked cases, recent escalations |
| Inbox page | `frontend/src/app/(workspace)/inbox/page.tsx` | Case list with search, filter, status badges |
| Case detail | `frontend/src/app/(workspace)/cases/[caseId]/page.tsx` | Tabbed workspace: Overview, Suppliers, Escalations, Audit Trace |
| Escalations page | `frontend/src/app/(workspace)/escalations/page.tsx` | Escalation queue with drill-down sheet |
| Audit page | `frontend/src/app/(workspace)/audit/page.tsx` | Audit summary + activity feed |
| Data layer | `frontend/src/lib/data/cases.ts` | All backend calls + response mapping |
| Type system | `frontend/src/lib/types/case.ts` | `CaseDetail`, `CaseListItem`, `SupplierRow`, `EscalationItem`, etc. |
| UI primitives | `frontend/src/components/ui/` | shadcn v4 components (Button, Card, Table, Tabs, Badge, Sheet, etc.) |

Data flow: Pages are async server components -> call loaders in `cases.ts` -> fetch from `BACKEND_INTERNAL_URL/api/*` -> map response to frontend types.

### Organisational Layer (status: fully functional)

| Component | Path | Purpose |
|-----------|------|---------|
| App entry | `backend/organisational_layer/app/main.py` | FastAPI app, CORS, router registration |
| DB config | `backend/organisational_layer/app/config.py` | Pydantic Settings for MySQL connection |
| ORM models | `backend/organisational_layer/app/models/` | 22 tables across 4 modules (reference, requests, historical, policies) |
| CRUD routers | `backend/organisational_layer/app/routers/` | categories, suppliers, requests, awards, policies, rules |
| Analytics router | `backend/organisational_layer/app/routers/analytics.py` | Compliant suppliers, pricing lookup, approval tier, restriction/preferred checks, request overview, spend aggregations, supplier win rates |
| Escalation router | `backend/organisational_layer/app/routers/escalations.py` | Queue endpoint + per-request escalations |
| Escalation engine | `backend/organisational_layer/app/services/escalations.py` | ER-001 through ER-008, AT conflict detection, conditional restriction parsing, multi-language single-supplier pattern matching |

Key analytics endpoints the pipeline depends on:
- `GET /api/analytics/request-overview/{id}` — comprehensive pre-assembled evaluation (compliant suppliers, pricing, rules, awards)
- `GET /api/analytics/compliant-suppliers` — non-restricted suppliers for category+country
- `GET /api/analytics/pricing-lookup` — pricing tier for supplier+category+region+quantity
- `GET /api/analytics/approval-tier` — approval threshold for currency+amount
- `GET /api/analytics/check-restricted` — restriction check with scope+conditional logic
- `GET /api/analytics/check-preferred` — preferred status for supplier+category+region
- `GET /api/analytics/applicable-rules` — category and geography rules for a context
- `GET /api/escalations/by-request/{id}` — computed escalations for a request

### Logical Layer (status: fully implemented)

| Component | Path | Status | Purpose |
|-----------|------|--------|---------|
| App entry | `backend/logical_layer/app/main.py` | Done | FastAPI app, CORS, lifespan, router registration |
| Config | `backend/logical_layer/app/config.py` | Done | `ORGANISATIONAL_LAYER_URL` setting |
| Org client | `backend/logical_layer/app/clients/organisational.py` | Done | Async httpx client wrapping all Org Layer API calls + escalations |
| Validate endpoint | `POST /api/validate-request` | Done | Deterministic checks + Claude LLM for contradictions |
| Filter endpoint | `POST /api/filter-suppliers` | Done | Filter suppliers by category via Org Layer |
| Rank endpoint | `POST /api/rank-suppliers` | Done | True-cost ranking (price / quality / risk / ESG) |
| Process endpoint | `POST /api/processRequest` | Done | Full pipeline — chains all steps, returns complete output |
| Fetch request | `POST /api/fetch-request` | Done | Proxy to fetch request from Org Layer |
| Check compliance | `POST /api/check-compliance` | Done | Per-supplier compliance checks (restrictions, delivery, residency) |
| Evaluate policy | `POST /api/evaluate-policy` | Done | Approval tier, preferred supplier, restriction checks, applicable rules |
| Check escalations | `POST /api/check-escalations` | Done | Fetch computed escalations from Org Layer |
| Gen recommendation | `POST /api/generate-recommendation` | Done | Recommendation status + LLM reasoning |
| Assemble output | `POST /api/assemble-output` | Done | Final output assembly with LLM enrichment |
| Format invalid | `POST /api/format-invalid-response` | Done | Structured response for invalid requests |
| Validate script | `backend/logical_layer/scripts/validateRequest.py` | Done | Required/optional field checks + LLM contradiction detection |
| Filter script | `backend/logical_layer/scripts/filterCompaniesByProduct.py` | Done | Category-based supplier filtering |
| Rank script | `backend/logical_layer/scripts/rankCompanies.py` | Done | True-cost computation + ranking |
| Compliance script | `backend/logical_layer/scripts/checkCompliance.py` | Done | Per-supplier compliance rule checks |
| Policy script | `backend/logical_layer/scripts/evaluatePolicy.py` | Done | Procurement policy evaluation |
| Escalation script | `backend/logical_layer/scripts/checkEscalations.py` | Done | Escalation fetching from Org Layer |
| Recommend script | `backend/logical_layer/scripts/generateRecommendation.py` | Done | Recommendation generation with LLM |
| Assembly script | `backend/logical_layer/scripts/assembleOutput.py` | Done | Output assembly with LLM enrichment |
| Invalid script | `backend/logical_layer/scripts/formatInvalidResponse.py` | Done | Invalid request response formatting |
| Pipeline schemas | `backend/logical_layer/app/schemas/pipeline.py` | Done | Pydantic models for all pipeline endpoints |
| Pipeline router | `backend/logical_layer/app/routers/pipeline.py` | Done | Router for pipeline step endpoints |

The `OrganisationalClient` (async httpx) has methods for every Org Layer endpoint: `get_request_overview`, `get_request`, `get_compliant_suppliers`, `get_pricing_lookup`, `get_approval_tier`, `check_restricted`, `check_preferred`, `get_applicable_rules`, `get_awards_by_request`, `get_escalation_rules`, `get_escalations_by_request`, `get_supplier_win_rates`.

### Database (status: fully functional)

Bootstrap via `database_init/migrate.py`. Reads all 6 source CSV/JSON files from `data/` and loads them into 22 normalised MySQL tables. Handles the inconsistent policy schemas (EUR/CHF vs USD thresholds), semicolon-delimited service regions, per-category supplier rows, etc.

---

## Gaps — Status

All critical gaps have been addressed by the pipeline implementation.

| Gap | Status | Implementation |
|-----|--------|---------------|
| Gap 1: Full Pipeline Orchestration | **Resolved** | `POST /api/processRequest` in `app/routers/processing.py` chains all steps. Individual endpoints available for n8n orchestration. |
| Gap 2: Policy Evaluation Assembly | **Resolved** | `scripts/evaluatePolicy.py` + `POST /api/evaluate-policy` produces the full `policy_evaluation` section (approval tier, preferred supplier, restrictions, rules). |
| Gap 3: Output Format Matching | **Resolved** | `scripts/assembleOutput.py` + `POST /api/assemble-output` produces all 8 sections of `example_output.json`. LLM enriches validation issues and supplier notes. |
| Gap 4: Supplier Exclusion Reasoning | **Resolved** | `scripts/checkCompliance.py` + `POST /api/check-compliance` splits suppliers into compliant/non-compliant with detailed exclusion reasons. |
| Gap 5: Recommendation Generation | **Resolved** | `scripts/generateRecommendation.py` + `POST /api/generate-recommendation` produces status, reason, preferred supplier, minimum budget with LLM reasoning. |
| Gap 6: Budget & Lead Time Checks | **Partially resolved** | LLM enrichment in `assembleOutput.py` adds severity and action_required to validation issues including budget/lead-time analysis. Cross-referencing with pricing data happens in the enrichment prompt. |
| Gap 7: Historical Context | **Resolved** | `processRequest` fetches historical awards via `org_client.get_awards_by_request()` and passes them to `assembleOutput` for audit trail. |
| Gap 8: Audit Trail Assembly | **Resolved** | `assembleOutput.py` builds the complete `audit_trail` section from all pipeline stage metadata. |

---

## Target Processing Pipeline (Implemented)

### `POST /api/processRequest` — Full Implementation

```
Input: { "request_id": "REQ-000004" }

Step 1: FETCH REQUEST
  Call: org_client.get_request(request_id)
  Output: full request object with delivery countries, scenario tags, category

Step 2: VALIDATE
  Call: validate_request(request_data) via asyncio.to_thread
  Output: completeness, issues[], request_interpretation

Step 3: BRANCH ON VALIDITY
  If missing_required issues → format_invalid_response() → return early
  Otherwise → continue

Step 4: FILTER SUPPLIERS
  Call: filter_suppliers({category_l1, category_l2}) via asyncio.to_thread
  Output: matching supplier rows

Step 5: CHECK COMPLIANCE
  Call: check_compliance(request_data, suppliers) via asyncio.to_thread
  Output: compliant[], non_compliant[] with exclusion reasons

Step 6: RANK SUPPLIERS
  Call: rank_suppliers(request_data, compliant) via asyncio.to_thread
  Output: ranked suppliers[] with pricing and true-cost scores

Step 7: ENRICH SUPPLIER NAMES
  Call: org_client.get_compliant_suppliers() for name mapping
  Output: supplier_name added to ranked and non-compliant suppliers

Step 8: EVALUATE POLICY
  Call: evaluate_policy(request_data, ranked, non_compliant) via asyncio.to_thread
  Output: policy_evaluation (approval_threshold, preferred_supplier, restricted, rules)

Step 9: CHECK ESCALATIONS
  Call: check_escalations(request_id) via asyncio.to_thread
  Output: escalations[] with rule_id, trigger, escalate_to, blocking

Step 10: GENERATE RECOMMENDATION
  Call: generate_recommendation({escalations, ranked, validation, interpretation}) via asyncio.to_thread
  Uses Claude LLM for human-readable reason and rationale
  Output: recommendation with status, reason, preferred supplier, minimum budget

Step 11: FETCH HISTORICAL AWARDS
  Call: org_client.get_awards_by_request(request_id)
  Output: historical awards for audit trail

Step 12: ASSEMBLE OUTPUT
  Call: assemble_output(all_step_outputs) via asyncio.to_thread
  Uses Claude LLM to enrich validation issues and supplier notes
  Output: complete pipeline response matching example_output.json
```

### Individual n8n Pipeline Endpoints

Each step is also available as an independent endpoint for n8n orchestration:

| Step | Endpoint | n8n Node |
|------|----------|----------|
| 1 | `POST /api/fetch-request` | HTTP Request |
| 2 | `POST /api/validate-request` | validate-request |
| 3 | `POST /api/format-invalid-response` | outputInvalidRequest |
| 4 | `POST /api/filter-suppliers` | filter-suppliers |
| 5 | `POST /api/check-compliance` | checkRules |
| 6 | `POST /api/rank-suppliers` | rank-suppliers |
| 8 | `POST /api/evaluate-policy` | (after Merge) |
| 9 | `POST /api/check-escalations` | (after Merge) |
| 10 | `POST /api/generate-recommendation` | (after Merge) |
| 12 | `POST /api/assemble-output` | (final step) |

### Ranking Formula (implemented)

Current true-cost formula in `rankCompanies.py`:

```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100)
```

With ESG requirement:

```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100) / (esg_score / 100)
```

Lower true_cost = better deal. The `overpayment` field shows the hidden cost of quality/risk gaps.

When quantity is null, suppliers are ranked by `quality_score` descending instead.

### Escalation Rules (implemented in Org Layer)

| Rule | Trigger | Blocking |
|------|---------|----------|
| ER-001 | Missing required info (budget, quantity, category) | Yes |
| ER-002 | Preferred supplier is restricted | Yes |
| ER-003 | Strategic sourcing approval tier (Head of Strategic Sourcing / CPO) | No |
| ER-004 | No compliant supplier with valid pricing | Yes |
| ER-005 | Data residency requirement unsatisfiable | Yes |
| ER-006 | Single supplier capacity risk | Yes |
| ER-007 | Influencer Campaign Management (brand safety) | Yes |
| ER-008 | Preferred supplier unregistered for USD delivery scope | Yes |
| AT-xxx | Single-supplier instruction conflicts with multi-quote threshold | Yes |

The AT conflict rule detects when `request_text` contains single-supplier language (in 6 languages) but the approval threshold requires multiple quotes.

---

## Competitive Advantages

### 1. Deterministic Policy Engine (already built)

The escalation engine in `backend/organisational_layer/app/services/escalations.py` handles:
- All 8 ER rules + AT threshold conflicts
- Value-conditional restrictions (e.g., "restricted above EUR 75K")
- Multi-language single-supplier instruction detection (en, fr, de, es, pt, ja)
- Country-to-region mapping for 19 countries across 5 regions

This is the core of the 25% Robustness & Escalation Logic criterion.

### 2. Three-Layer Separation (already built)

Data layer (MySQL + Org Layer) is fully separated from decision logic (Logical Layer) which is separated from presentation (Frontend). This directly demonstrates Feasibility (25%) — it's a production-grade architecture, not a hackathon script.

### 3. Pre-Built Frontend (already built)

Five functional pages with a modern UI. The case detail page has 4 tabs (Overview, Suppliers, Escalations, Audit Trace) that map directly to what judges want to see. Visual Design (10%) is covered.

### 4. Historical Pattern Context (data available, integration pending)

The `historical_awards` table has 590 records across 180 requests. Win rates and spend aggregations are available via analytics endpoints. Integration into recommendations would add credibility: "This category in DE has historically been awarded to Bechtle 60% of the time."

### 5. Confidence Scoring (stretch goal, high impact)

For each recommendation, output a confidence score (0-100%) based on:
- Validation issue count and severity (fewer/lower = higher confidence)
- Gap between top supplier and #2 (larger gap = higher confidence)
- Blocking escalation presence (blocking = 0% confidence for autonomous decision)

### 6. Multi-Language Support (partially built)

The LLM validation step already processes `request_text` in any language (Claude handles multilingual input natively). The escalation engine already detects single-supplier instructions in 6 languages. Geography rule GR-003 (French language support) is enforced by the Org Layer.

### 7. Interactive Clarification Flow (stretch goal)

Instead of flagging "information missing," generate a specific clarification request: "Budget is missing. Based on similar requests, typical budget for 200 laptops in DE is EUR 180,000-190,000." Requires historical context integration (Gap 7).

---

## Implementation Priority

### Done

- [x] Data normalisation into MySQL (22 tables, `database_init/migrate.py`)
- [x] CRUD + analytics API (40+ endpoints, Organisational Layer)
- [x] Request validation with LLM contradiction detection (`validateRequest.py`)
- [x] Supplier filtering by product category (`filterCompaniesByProduct.py`)
- [x] Supplier ranking by true cost (`rankCompanies.py`)
- [x] Escalation engine (ER-001 through ER-008 + AT conflict, `escalations.py`)
- [x] Async Org Layer client with all needed methods (`organisational.py`)
- [x] Frontend shell (5 pages, server components, shadcn v4)
- [x] Docker deployment (two compose stacks on shared network)
- [x] Database migration tooling (one-shot bootstrap)
- [x] n8n integration documentation (`N8N_INSTRUCTION.md`)
- [x] Compliance checking per supplier (`checkCompliance.py` + `POST /api/check-compliance`)
- [x] Policy evaluation assembly (`evaluatePolicy.py` + `POST /api/evaluate-policy`)
- [x] Escalation fetching (`checkEscalations.py` + `POST /api/check-escalations`)
- [x] Recommendation generation with LLM (`generateRecommendation.py` + `POST /api/generate-recommendation`)
- [x] Output assembly with LLM enrichment (`assembleOutput.py` + `POST /api/assemble-output`)
- [x] Invalid request formatting (`formatInvalidResponse.py` + `POST /api/format-invalid-response`)
- [x] Request fetching proxy (`POST /api/fetch-request`)
- [x] Full pipeline endpoint (`POST /api/processRequest` — chains all 11 steps)
- [x] Complete n8n pipeline documentation with all endpoint examples and data mapping

### Remaining — Phase 3: Polish & Demo Prep

1. **Wire frontend to display full pipeline output**
   - Case detail page already has tabs; ensure data mapping handles new fields
   - Add "Run Pipeline" action if not triggered automatically

2. **Demo script rehearsal**
   - Verify REQ-000001 (happy path) and REQ-000004 (edge case) produce correct output
   - Prepare talking points for architecture explanation

3. **Confidence scoring** (stretch goal)
   - Score based on validation issue count, supplier gap, escalation blocking status
   - Include in recommendation output

---

## Demo Script (8 minutes total)

### Live Demo (5 min)

1. **Inbox overview** (30s): Open `/inbox`. Show the list of 304 purchase requests with status badges, filters, and search. Point out scenario tags.

2. **Standard request** (1.5 min): Click into a clean happy-path request (e.g., REQ-000001). Walk through:
   - Overview tab: original request text, interpreted requirements, validation (all pass)
   - Suppliers tab: ranked comparison table with true-cost scores
   - Audit Trace tab: policies checked, data sources used

3. **Edge case — REQ-000004** (2 min): Click into the contradictory request. Highlight:
   - Validation issues: budget insufficient (EUR 25K vs EUR 35K+ minimum), lead time infeasible (6 days vs 17+ days)
   - Policy conflict: "no exception" instruction vs AT-002 requiring 2 quotes
   - Escalations tab: three blocking escalations (ER-001, AT-002, ER-004)
   - Recommendation: `cannot_proceed` with minimum budget calculation

4. **Escalation queue** (1 min): Navigate to `/escalations`. Show the global queue. Filter by blocking status. Drill into an escalation to see rule details and routing target.

### Explanation (3 min)

1. **Architecture** (1 min): Three-service design. LLM for parsing only, deterministic code for all governance logic. MySQL for auditable data. Why this matters: every decision is traceable, reproducible, and explainable.

2. **Rule enforcement** (1 min): Show the escalation engine code. Highlight: 8 ER rules + AT conflict detection, conditional restriction parsing, multi-language instruction detection. All deterministic — no LLM involvement in policy decisions.

3. **Scale statement** (1 min): Current architecture handles 304 requests. At 10,000 requests/year: the pipeline is stateless and horizontally scalable. n8n orchestration supports batch processing, retry logic, and human-in-the-loop queues. MySQL on RDS scales vertically. Frontend is server-rendered with 15-second cache TTL.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM hallucination on policy | LLM is used only for text parsing in `validateRequest.py`. All policy logic (thresholds, restrictions, escalations) is deterministic Python code in the Org Layer. |
| Pipeline orchestration complexity | The `OrganisationalClient` already wraps all needed API calls. The pipeline is a linear chain of async calls — no complex state management needed. |
| Output format mismatch | Use `examples/example_output.json` as the schema contract. Validate pipeline output against it during development. |
| Frontend data mapping breaks | The frontend's `cases.ts` data layer already maps backend responses to typed interfaces. New pipeline fields need to be added to both the backend response and frontend types. |
| Anthropic API unavailable | The validate step has deterministic checks as a fallback. If Claude is down, deterministic validation still runs — only LLM-detected contradictions and `requester_instruction` extraction are lost. |
| AWS/Docker deployment issues | Local Docker Compose setup is fully functional. Demo can run locally if cloud deployment fails. |
| Edge cases producing wrong escalations | The escalation engine defaults to escalating when uncertain. A false escalation is always better than a false clearance for audit purposes. |
