# ChainIQ — Audit-Ready Autonomous Sourcing Agent

**START Hack 2026 — ChainIQ Challenge**

A full-stack prototype that converts unstructured, multilingual purchase requests into structured, defensible supplier comparisons with transparent reasoning, rule versioning, and escalation logic. The system processes 304 real-world procurement requests across 19 countries, 3 currencies, and 4 category families — producing auditable decisions end to end.

---

## Table of Contents

- [Architecture](#architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [The Pipeline](#the-pipeline)
- [Escalation Logic](#escalation-logic)
- [LLM Integration Strategy](#llm-integration-strategy)
- [Dynamic Rules Engine](#dynamic-rules-engine)
- [Confidence Scoring](#confidence-scoring)
- [Audit Trail](#audit-trail)
- [Data Model](#data-model)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Deployment](#deployment)
- [Design Principles](#design-principles)
- [License](#license)

---

## Architecture

```
                          ┌─────────────────────────┐
                          │        Frontend          │
                          │    Next.js 16 · React 19 │
                          │     Tailwind · shadcn     │
                          │        port 3000          │
                          └────────┬────────┬────────┘
                  /api/pipeline/*  │        │  /api/*
                                   │        │
              ┌────────────────────▼─┐  ┌───▼──────────────────┐
              │    Logical Layer     │  │ Organisational Layer  │
              │  (Decision Engine)   │  │   (Data Backbone)    │
              │  FastAPI · port 8080 │  │  FastAPI · port 8000  │
              │                      │  │                       │
              │  9-step async        │──│  CRUD · Analytics     │
              │  pipeline            │  │  Rule Versioning      │
              │  Claude claude-sonnet-4-6    │  │  Escalation Engine    │
              └──────────────────────┘  │  Audit Logging        │
                                        └───────────┬───────────┘
                                                    │ SQLAlchemy
                                              ┌─────▼─────┐
                                              │  MySQL 8.4 │
                                              │  38 tables │
                                              │  AWS RDS   │
                                              └────────────┘
```

The system is split into **three independently deployable services** connected via a shared Docker network:

| Service | Role | Port |
|---------|------|------|
| **Frontend** | Interactive case workspace, intake assistant, escalation management | 3000 |
| **Organisational Layer** | All data access, governance rules, analytics, audit logging, rule versioning | 8000 |
| **Logical Layer** | Stateless 9-step procurement decision pipeline with LLM-assisted validation | 8080 |

The Logical Layer **never touches the database directly** — every read and write flows through the Organisational Layer's REST API, enforcing a single source of truth and making the decision engine purely functional.

---

## Key Features

### Autonomous Decision Pipeline
A deterministic 9-step pipeline processes each purchase request: fetch reference data, validate for contradictions, filter compliant suppliers, check per-supplier compliance, rank by true cost, evaluate procurement policy, compute escalations, generate recommendations, and assemble the final auditable output.

### Escalate Over Guess
The system prioritises **correct uncertainty handling** over confident wrong answers. When it cannot make a compliant autonomous decision, it triggers the appropriate escalation rule, names the responsible party, and clearly marks the decision as blocked. A false escalation always scores better than a false clearance.

### Full Audit Traceability
Every pipeline run produces a complete audit trail: step-level telemetry with timing, human-readable decision logs explaining each inclusion/exclusion/ranking, frozen rule version snapshots, and per-supplier compliance breakdowns. Every decision can be traced back to the exact rule configuration that produced it.

### Multilingual Processing
Handles purchase requests in 6 languages (English, French, German, Spanish, Portuguese, Japanese) natively through LLM-powered validation and structured extraction.

### Dynamic Rules Engine
Procurement rules are stored in the database and evaluated at runtime — no code changes needed to adjust thresholds, add new compliance checks, or modify escalation triggers. Rules support versioning with full change audit trails.

### LLM-Powered Rule Management
Non-technical users can create or modify procurement rules by describing what they want in plain text. The LLM analyses existing rules, decides whether to create a new rule or update an existing one, and generates the structured configuration for human review before activation.

### PDF Audit Reports
On-demand downloadable PDF reports for any processed request, aggregating the pipeline result, full audit log, and summary statistics into a self-contained compliance document.

### AI-Assisted Intake
The frontend provides an intelligent chat-based intake assistant that helps requesters structure their procurement needs, with both LLM-powered parsing (text and file uploads including PDFs/images) and deterministic regex-based extraction with per-field confidence scoring.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui (Radix), Zustand |
| **AI Chat** | Vercel AI SDK, @assistant-ui/react, Anthropic Claude |
| **Backend — Org Layer** | Python 3.14, FastAPI, SQLAlchemy 2.0, PyMySQL, Pydantic Settings |
| **Backend — Logical Layer** | Python 3.14, FastAPI, httpx (async), Anthropic SDK, Pydantic |
| **Database** | MySQL 8.4 (AWS RDS, 38 normalised tables) |
| **LLM** | Anthropic Claude claude-sonnet-4-6 (structured output via tool_use) |
| **Infrastructure** | Docker, Docker Compose, AWS EC2 + RDS, nginx |
| **Testing** | pytest, pytest-asyncio, httpx TestClient |

---

## Project Structure

```
chainIQ-START-Hack/
├── frontend/                        # Next.js web application
│   ├── src/
│   │   ├── app/                     # App Router pages and API routes
│   │   ├── components/              # UI components (case-detail, intake, escalations, audit, etc.)
│   │   ├── hooks/                   # Custom React hooks
│   │   └── lib/                     # Data fetching, types, pipeline utilities
│   ├── Dockerfile
│   └── next.config.ts               # API proxy rewrites to backend services
│
├── backend/
│   ├── organisational_layer/        # Data backbone microservice (port 8000)
│   │   ├── app/
│   │   │   ├── models/              # SQLAlchemy ORM models (38 tables)
│   │   │   ├── schemas/             # Pydantic request/response schemas
│   │   │   ├── routers/             # FastAPI route handlers
│   │   │   └── services/            # Business logic (escalations, parsing, rule management)
│   │   ├── tests/                   # 137 tests (integration + unit)
│   │   └── Dockerfile
│   │
│   ├── logical_layer/               # Decision engine microservice (port 8080)
│   │   ├── app/
│   │   │   ├── clients/             # Async HTTP + LLM clients
│   │   │   ├── models/              # Pipeline I/O Pydantic models
│   │   │   ├── routers/             # Pipeline execution + status endpoints
│   │   │   ├── pipeline/
│   │   │   │   ├── runner.py        # Orchestrates 9-step pipeline
│   │   │   │   ├── logger.py        # Step telemetry + audit logging
│   │   │   │   ├── rule_engine.py   # Dynamic rules evaluator
│   │   │   │   └── steps/           # Individual pipeline steps (fetch → assemble)
│   │   │   └── reports/             # PDF audit report generation
│   │   ├── tests/                   # 167 tests (unit + integration)
│   │   └── Dockerfile
│   │
│   └── docker-compose.yml           # Backend stack orchestration
│
├── database_init/                   # Data migration and maintenance tools
│   ├── migrate.py                   # Main schema bootstrap (24 tables)
│   ├── migrate_rules.py             # Rule versioning tables + seed data
│   ├── migrate_dynamic_rules.py     # Dynamic rules tables + 30+ procurement rules
│   ├── clean_pipeline_data.py       # Reset pipeline results and evaluations
│   ├── clean_logs.py                # Reset pipeline/audit logs
│   └── process_all_requests.py      # Batch-process all requests through pipeline
│
├── data/                            # Challenge dataset
│   ├── requests.json                # 304 purchase requests
│   ├── suppliers.csv                # 40 suppliers × multiple categories (151 rows)
│   ├── pricing.csv                  # 599 pricing tiers with lead times
│   ├── categories.csv               # 30 category definitions (L1/L2 taxonomy)
│   ├── policies.json                # Thresholds, preferred/restricted, category/geo/escalation rules
│   └── historical_awards.csv        # 590 historical decisions across 180 requests
│
├── deploy/nginx/                    # Reference nginx reverse proxy config
├── docker-compose.yml               # Frontend stack (Next.js + MySQL + migrator)
├── docker-compose.dev.yml           # Development overrides (hot reload)
├── Makefile                         # Simplified run commands
└── DEPLOYMENT.md                    # Full deployment guide (local, AWS EC2 + RDS, nginx)
```

---

## Getting Started

### Prerequisites

- Docker Engine 20.10+ with Docker Compose plugin
- Git

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/chainIQ-START-Hack.git
cd chainIQ-START-Hack

# 2. Create the shared Docker network (one-time)
docker network create chainiq-network

# 3. Configure environment files
cp .env.example .env
cp backend/organisational_layer/.env.example backend/organisational_layer/.env
cp backend/logical_layer/.env.example backend/logical_layer/.env
# Edit .env files with your database credentials and API keys

# 4. Start backend services
cd backend && docker compose up --build -d && cd ..

# 5. Start frontend
docker compose up --build

# 6. Bootstrap the database (first run only)
docker compose --profile tools run --rm migrator
```

### Verify

```bash
curl http://localhost:8000/health   # Organisational Layer → {"status": "ok"}
curl http://localhost:8080/health   # Logical Layer → {"status": "ok", ...}
open http://localhost:3000          # Frontend
```

### Makefile Shortcuts

```bash
make help          # List all available commands
make local-up      # Full local stack (MySQL + migrator + backend + frontend)
make local-dev     # Same with frontend hot reload
make local-down    # Stop everything
```

### Environment Variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | Org Layer | MySQL connection |
| `ORGANISATIONAL_LAYER_URL` | Logical Layer | Internal URL to Org Layer |
| `ANTHROPIC_API_KEY` | Logical Layer + Frontend | Claude API key for LLM features |
| `ANTHROPIC_MODEL` | Logical Layer | Model selection (default: `claude-sonnet-4-6`) |
| `BACKEND_INTERNAL_URL` | Frontend | Org Layer URL for server-side rendering |
| `LOGICAL_BACKEND_INTERNAL_URL` | Frontend | Logical Layer URL for pipeline proxying |

---

## The Pipeline

Every purchase request goes through a **9-step asynchronous pipeline** that produces a fully auditable decision:

```
Request ID
    │
    ▼
┌─────────────────────┐
│ 1. FETCH            │  Parallel: request overview + existing escalations
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 2. VALIDATE         │  Deterministic checks + LLM contradiction detection (temperature=0)
└─────────┬───────────┘
          │
    [Missing critical fields?]
          │ yes → early exit with invalid response
          │ no ↓
┌─────────────────────┐
│ 3. FILTER           │  Enrich compliant suppliers with pricing, scores, preferred flags
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 4. COMPLY           │  Per-supplier: restriction, delivery, residency, capacity checks
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 5. RANK             │  True-cost ranking: price / (quality/100) / ((100-risk)/100)
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    ▼           ▼         (parallel)
┌────────┐ ┌────────────┐
│6. POLICY│ │7. ESCALATE │  Merge 3 sources: Org Layer + pipeline + LLM contradictions
└───┬────┘ └─────┬──────┘
    └─────┬──────┘
          ▼
┌─────────────────────┐
│ 8. RECOMMEND        │  Deterministic status + LLM-generated rationale (1-2 sentences)
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 9. ASSEMBLE         │  Final output + LLM-enriched supplier notes
└─────────┬───────────┘
          ▼
    Auditable Output
```

### Parallelism Strategy

| Phase | Steps | Mechanism |
|-------|-------|-----------|
| Fetch | Overview + escalations | `asyncio.gather()` |
| Sequential | Validate → Filter → Comply → Rank | `await` (each depends on prior output) |
| Parallel | Policy + Escalation merge | `asyncio.gather()` |
| Sequential | Recommend → Assemble | `await` |

### Pipeline Output

Each pipeline run produces a structured JSON output containing:
- **Request interpretation** — parsed and normalised fields with delivery constraints
- **Validation results** — completeness check, detected issues with severity
- **Policy evaluation** — approval threshold, preferred/restricted analysis, category and geography rules
- **Supplier shortlist** — ranked suppliers with pricing, lead times, quality/risk/ESG scores, compliance status
- **Excluded suppliers** — with specific exclusion reasons
- **Escalations** — triggered rules with targets and blocking status
- **Recommendation** — `proceed`, `proceed_with_conditions`, or `cannot_proceed` with confidence score and rationale
- **Audit trail** — policies checked, data sources used, historical context

---

## Escalation Logic

The system implements 8 specification-defined escalation rules plus 3 custom extensions:

| Rule | Trigger | Escalate To | Blocking |
|------|---------|-------------|----------|
| ER-001 | Missing required info (budget, quantity, category) | Requester Clarification | Yes |
| ER-002 | Preferred supplier is restricted | Procurement Manager | Yes |
| ER-003 | Contract value exceeds strategic sourcing tier | Head of Strategic Sourcing | No |
| ER-004 | No compliant supplier found | Head of Category | Yes |
| ER-005 | Data residency constraint unsatisfiable | Security/Compliance | Yes |
| ER-006 | Single supplier capacity risk | Sourcing Excellence Lead | No |
| ER-007 | Influencer campaign brand safety | Marketing Governance Lead | No |
| ER-008 | Supplier unregistered in delivery country | Regional Compliance Lead | No |
| ER-009* | LLM-detected contradictions | Procurement Manager | No |
| ER-010* | Lead time infeasible | Head of Category | No |
| ER-BUDGET* | Budget below minimum supplier price | Budget Owner / Requester | No |

*Custom extensions (ER-009, ER-010, ER-BUDGET) are intentionally non-blocking to avoid overriding the specification's escalation semantics.

### Three-Source Escalation Merge

Escalations are collected from three independent sources and deduplicated:

1. **Organisational Layer engine** — deterministic evaluation against stored rules
2. **Pipeline-discovered issues** — compliance checks with exact figures (steps 2–5)
3. **LLM-detected contradictions** — semantic analysis of request text vs structured fields

When the same rule is triggered by multiple sources, the more specific description (typically from the pipeline, with exact numbers) wins.

---

## LLM Integration Strategy

A core design principle: **LLM for prose, deterministic logic for decisions.** Policy evaluation, compliance checking, escalation triggering, and ranking are all implemented as deterministic Python code. The LLM (Claude claude-sonnet-4-6) is used in exactly three places:

| Step | Purpose | Fallback if LLM fails |
|------|---------|----------------------|
| **Validate** (Step 2) | Detect contradictions between `request_text` and structured fields; extract requester instructions. Uses `temperature=0` for deterministic results. | Empty issues list, no instruction |
| **Recommend** (Step 8) | Generate concise rationale (1-2 sentences) citing specific names, prices, and rule IDs | Template prose using deterministic values |
| **Assemble** (Step 9) | Enrich validation issues with severity; generate per-supplier recommendation notes (2-3 sentences) | Pass-through issues; empty notes |

All LLM calls use Anthropic's **structured output via tool_use** with Pydantic model schemas, ensuring type-safe responses. If the LLM fails, the pipeline degrades gracefully — decisions remain correct, only the explanatory prose is less polished.

### Contradiction Detection

The LLM validation uses a carefully engineered prompt (`VALIDATION_SYSTEM_PROMPT`) that explicitly defines what IS and IS NOT a contradiction. Approximations, omissions, rounding, and different wording for the same value are all excluded to minimise false positives. Each detected contradiction preserves its specific field and description for the audit trail.

---

## Dynamic Rules Engine

Procurement rules are stored in the database and evaluated at runtime by a Python-based rule engine (`rule_engine.py`). This enables:

- **No-code rule changes** — adjust thresholds, conditions, and actions without deploying code
- **Full version history** — every rule change creates a new version; the old version is timestamped and preserved
- **Frozen snapshots** — evaluation results record which exact rule version was applied
- **LLM-assisted authoring** — describe a rule in natural language and the system generates the structured configuration

Rules support 5 evaluation types: `required` (null checks), `range` (numeric bounds), `threshold` (value comparisons), `comparison` (field-to-field), and `custom_llm` (LLM-evaluated conditions).

---

## Confidence Scoring

Each recommendation includes a confidence score (0–100) computed deterministically:

| Factor | Impact |
|--------|--------|
| Blocking escalation | -25 per escalation |
| Non-blocking escalation | -10 per escalation |
| Critical validation issue | -20 |
| High validation issue | -10 |
| Medium validation issue | -5 |
| Low validation issue | -2 |
| Clear cost winner (>20% gap) | +10 |
| Preferred supplier is top-ranked | +5 |

| Range | Interpretation |
|-------|---------------|
| 0 | Cannot proceed — blocking escalations present |
| 1–30 | Low confidence |
| 31–60 | Moderate confidence |
| 61–80 | High confidence |
| 81–100 | Very high confidence — clean request, clear winner |

---

## Audit Trail

The system produces two independent audit streams:

### Pipeline Telemetry
Step-level timing for every pipeline run: when each step started/finished, duration in milliseconds, input/output summaries. Stored in `pipeline_runs` and `pipeline_log_entries` tables.

### Decision Audit Log
Human-readable entries explaining every decision point: which suppliers were included and why, which were excluded and why, which rules were applied, which escalations were triggered. Categorised by semantic type (`data_access`, `validation`, `supplier_filter`, `compliance`, `pricing`, `ranking`, `policy`, `escalation`, `recommendation`) with severity levels.

### Evaluation Traceability
Every evaluation run records:
- Per-supplier hard rule checks and policy checks with pass/fail results
- Frozen rule configuration snapshots at the time of evaluation
- Dynamic rule version numbers for reproducibility
- Supplier shortlist and exclusion reasons

---

## Data Model

38 MySQL tables organised into logical groups:

| Group | Tables | Description |
|-------|--------|-------------|
| **Reference data** (5) | categories, suppliers, supplier_categories, supplier_service_regions, pricing_tiers | Master data: 30 categories, 40 suppliers, 599 pricing tiers |
| **Requests** (3) | requests, request_delivery_countries, request_scenario_tags | 304 purchase requests with multi-country delivery support |
| **Historical** (1) | historical_awards | 590 past decisions across 180 requests |
| **Approval policies** (3) | approval_thresholds, managers, deviation_approvers | Multi-currency threshold tiers with approval chains |
| **Supplier policies** (4) | preferred_suppliers_policy, region_scopes, restricted_suppliers_policy, scopes | Preferred/restricted with geographic and value-conditional scoping |
| **Rules** (6) | category_rules, geography_rules (+ countries, categories), escalation_rules (+ currencies) | 10 category rules, 8 geography rules, 8 escalation rules |
| **Rule versioning** (4) | rule_definitions, rule_versions, rule_change_logs, evaluation_runs | Immutable version history with audit trail |
| **Evaluation checks** (3) | hard_rule_checks, policy_checks, supplier_evaluations | Per-supplier per-rule pass/fail results |
| **Escalations** (2) | escalations, escalation_logs | Active escalation queue with resolution workflow |
| **Pipeline results** (1) | pipeline_results | Full pipeline output JSON for frontend display |
| **Logging** (6) | pipeline_runs, pipeline_log_entries, audit_logs, evaluation_run_logs, policy_change_logs, policy_check_logs | Complete operational and decision audit trail |

### Data Normalisation

The raw challenge data contains several inconsistencies that are handled at ingestion:
- **Inconsistent policy schemas** — EUR/CHF and USD thresholds use different key names; normalised at migration
- **Supplier rows are per-category** — 151 CSV rows normalised into 40 suppliers + 151 category associations
- **Semicolon-delimited regions** — split into proper relational rows
- **Unreliable restriction flags** — the `is_restricted` boolean in supplier data is a hint only; actual restrictions evaluated against the policy table at runtime

---

## API Reference

### Organisational Layer (port 8000)

| Area | Endpoints | Purpose |
|------|-----------|---------|
| **CRUD** | Categories, Suppliers, Requests, Awards, Policies, Rules | Full lifecycle management for all reference data |
| **Analytics** | Compliant suppliers, pricing lookup, approval tier, restriction/preferred checks, applicable rules | Core procurement decision support queries |
| **Request Overview** | `GET /api/analytics/request-overview/{id}` | Single-call aggregation of all data needed for pipeline processing |
| **Pipeline Results** | CRUD for `pipeline_results` | Persist and retrieve full pipeline outputs |
| **Logging** | Pipeline runs, step entries, audit logs | Telemetry and decision audit trail |
| **Rule Versioning** | Definitions, versions, evaluations, checks | Full rule lifecycle with frozen snapshots |
| **Dynamic Rules** | CRUD + LLM-powered parse | Runtime rule management with version history |
| **Parse** | Text and file parsing | LLM-powered procurement text extraction |
| **Intake** | Deterministic extraction | Regex-based field extraction with confidence scores |

### Logical Layer (port 8080)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/pipeline/process` | Process a single purchase request through the 9-step pipeline |
| `POST /api/pipeline/process-batch` | Process multiple requests concurrently (configurable semaphore) |
| `GET /api/pipeline/status/{request_id}` | Latest pipeline run status with timing and scores |
| `GET /api/pipeline/result/{request_id}` | Full pipeline output (in-memory cache + persistent fallback) |
| `GET /api/pipeline/report/{request_id}` | Downloadable PDF audit report |
| `GET /api/pipeline/runs` | List all pipeline runs |
| `GET /api/pipeline/audit/{request_id}` | Full audit trail for a request |

Interactive API documentation is available at:
- Organisational Layer: `http://localhost:8000/docs`
- Logical Layer: `http://localhost:8080/docs`

---

## Testing

### Test Coverage

| Service | Tests | Coverage |
|---------|-------|----------|
| **Organisational Layer** | 137 tests | All API endpoints, escalation engine, evaluation detail, dynamic rules |
| **Logical Layer** | 167 tests | Utility functions, Pydantic models, LLM client, dynamic rule engine, all pipeline steps, full pipeline runner, API endpoints |
| **Database Init** | Unit tests | Clean scripts, migration logic |

### Running Tests

```bash
# Organisational Layer (requires live MySQL)
cd backend/organisational_layer
source .venv/bin/activate
python -m pytest tests/ -v

# Logical Layer (no database required — uses mocked responses)
cd backend/logical_layer
source .venv/bin/activate
python -m pytest tests/ -v

# Database Init
cd database_init
source .venv/bin/activate
python -m pytest tests/ -v
```

The Logical Layer test suite includes **13 regression tests** specifically targeting bugs discovered and fixed during development, ensuring they do not recur.

---

## Deployment

The system supports three deployment modes:

### Local Development
Both backend services run in Docker containers with a local MySQL instance. The frontend supports hot-reload via `docker-compose.dev.yml`.

### AWS (EC2 + RDS)
Backend and frontend Docker containers on EC2, connecting to a managed MySQL 8.0 instance on RDS. An nginx reverse proxy can unify all services behind port 80.

### Multi-Machine
Backend and frontend on separate EC2 instances, communicating via private IPs instead of Docker networking.

For detailed instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Escalate over guess** | A false escalation always scores better than a false clearance. The system triggers escalations proactively when data is ambiguous or constraints cannot be satisfied. |
| **LLM for prose, deterministic for decisions** | All policy evaluation, compliance checking, ranking, and escalation logic is deterministic Python. The LLM generates explanatory text only. |
| **Org Layer owns all data** | The Logical Layer never touches MySQL directly. Every read/write flows through the Org Layer REST API, creating a single auditable data gateway. |
| **Type-safe pipeline** | Pydantic models define every step's input and output. Schema mismatches are caught at development time, not in production. |
| **Fire-and-forget logging** | Logging calls never block or crash the pipeline. If the Org Layer is unreachable, logs are lost but pipeline execution continues. |
| **Graceful LLM degradation** | Every LLM call has a deterministic fallback. Pipeline output is always valid — the LLM only controls the quality of prose explanations. |
| **Frozen rule snapshots** | Evaluation results record the exact rule version applied, enabling full reproducibility and audit compliance. |
| **Conservative contradiction detection** | The LLM validation prompt explicitly lists what is NOT a contradiction (approximations, omissions, rounding) to minimise false positives. Uses `temperature=0` for deterministic results. |

---

## License

Hackathon project — START Hack 2026.
