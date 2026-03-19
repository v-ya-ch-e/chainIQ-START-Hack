# **USER INSTRUCTIONS**

> Always work in .venv
> Always update @CLAUDE.md file to keep it updated about the project
> You should keep this block with user instructions as it is. You can write below everything you want

# **SERVICE OVERVIEW**

Procurement decision engine (Logical Layer) for the ChainIQ platform. Provides HTTP API endpoints that n8n workflows call to validate purchase requests, filter suppliers by product category, check compliance rules, rank suppliers by true cost, evaluate procurement policies, check escalations, generate recommendations, and assemble auditable pipeline output. The full end-to-end processing pipeline is available both as individual endpoints (for n8n orchestration) and as a single convenience endpoint (`/api/processRequest`).

## How to run

```bash
cd backend/logical_layer
source .venv/bin/activate
cp .env.example .env   # set ORGANISATIONAL_LAYER_URL and ANTHROPIC_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Swagger UI: http://localhost:8080/docs

**Requires the Organisational Layer to be running** (default: port 8000).
**Requires `ANTHROPIC_API_KEY` to be set** for endpoints that use Claude LLM (validate-request, format-invalid-response, generate-recommendation, assemble-output).

## Docker (both services together)

```bash
cd backend
cp organisational_layer/.env.example organisational_layer/.env   # fill in DB credentials
cp logical_layer/.env.example logical_layer/.env                 # set ANTHROPIC_API_KEY
docker compose up --build
```

## Key files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app entry point, CORS, router registration, `/health` endpoint |
| `app/config.py` | Pydantic Settings — reads `ORGANISATIONAL_LAYER_URL` from env |
| `app/clients/organisational.py` | Async HTTP client wrapping all Org Layer API calls (requests, analytics, escalations, awards, pipeline logging) |
| `app/routers/processing.py` | `POST /api/processRequest` — full pipeline endpoint (instrumented with step-level logging) |
| `app/services/pipeline_logger.py` | `PipelineLogger` — async context-manager that records step-level timing, inputs, outputs, and errors to the Org Layer's logging API |
| `app/routers/scripts.py` | `POST /api/filter-suppliers`, `/api/rank-suppliers`, `/api/validate-request` — script-backed endpoints |
| `app/routers/pipeline.py` | `POST /api/fetch-request`, `/api/check-compliance`, `/api/evaluate-policy`, `/api/check-escalations`, `/api/generate-recommendation`, `/api/assemble-output`, `/api/format-invalid-response` — pipeline step endpoints (supports `X-Pipeline-Run-Id` header for logging) |
| `app/schemas/processing.py` | Pydantic models for the processRequest endpoint |
| `app/schemas/scripts.py` | Pydantic models for the filter, rank, and validate endpoints |
| `app/schemas/pipeline.py` | Pydantic models for all pipeline step endpoints |
| `scripts/validateRequest.py` | Validates purchase request completeness and consistency using deterministic checks + Anthropic LLM |
| `scripts/filterCompaniesByProduct.py` | Filters suppliers by product category via Organisational Layer API |
| `scripts/rankCompanies.py` | Ranks suppliers by true cost (price adjusted for quality/risk/ESG) |
| `scripts/checkCompliance.py` | Checks each supplier against compliance rules (restrictions, delivery coverage, data residency) |
| `scripts/evaluatePolicy.py` | Evaluates procurement policies (approval tier, preferred supplier, applicable rules) |
| `scripts/checkEscalations.py` | Fetches computed escalations from the Org Layer |
| `scripts/generateRecommendation.py` | Generates recommendation status and reasoning using deterministic logic + Claude LLM |
| `scripts/assembleOutput.py` | Assembles all step outputs into final pipeline output with LLM-enriched descriptions |
| `scripts/formatInvalidResponse.py` | Formats structured response for invalid requests with LLM-generated summaries |
| `scripts/SCRIPTS_DOCUMENTATION.md` | Detailed documentation for all scripts |
| `N8N_INSTRUCTION.md` | Complete n8n integration guide with endpoint docs and pipeline flow |
| `Dockerfile` | Python 3.14-slim container, copies `app/` and `scripts/`, runs uvicorn on port 8080 |
| `requirements.txt` | fastapi, uvicorn, httpx, pydantic-settings, python-dotenv, anthropic |
| `.env.example` | Template: `ORGANISATIONAL_LAYER_URL`, `ANTHROPIC_API_KEY` |

## API endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| `GET` | `/health` | Active | Liveness check |
| `POST` | `/api/validate-request` | Active | Validate request completeness and consistency (uses Anthropic LLM) |
| `POST` | `/api/filter-suppliers` | Active | Filter suppliers by product category |
| `POST` | `/api/rank-suppliers` | Active | Rank suppliers by true cost |
| `POST` | `/api/fetch-request` | Active | Fetch request from Org Layer (proxy) |
| `POST` | `/api/check-compliance` | Active | Check supplier compliance (restrictions, delivery, residency) |
| `POST` | `/api/evaluate-policy` | Active | Evaluate procurement policies (approval tier, preferred, rules) |
| `POST` | `/api/check-escalations` | Active | Fetch computed escalations for a request |
| `POST` | `/api/generate-recommendation` | Active | Generate recommendation with LLM reasoning |
| `POST` | `/api/assemble-output` | Active | Assemble final pipeline output with LLM enrichment |
| `POST` | `/api/format-invalid-response` | Active | Format response for invalid requests |
| `POST` | `/api/processRequest` | Active | Full pipeline — runs all steps and returns complete output |

## Architecture

```
n8n workflow
  │
  ├─ POST /api/fetch-request        ──→  Logical Layer (8080)
  │                                           │ httpx (async)
  │                                           ▼
  │                                     Organisational Layer (8000)
  │
  ├─ POST /api/validate-request     ──→  Logical Layer (8080)
  │                                           │ Anthropic SDK
  │                                           ▼
  │                                     Claude (LLM)
  │
  ├─ POST /api/filter-suppliers     ──→  Logical Layer (8080)
  │                                           │ urllib
  │                                           ▼
  │                                     Organisational Layer (8000)
  │
  ├─ POST /api/check-compliance     ──→  Logical Layer (8080)
  │                                           │ urllib
  │                                           ▼
  │                                     Organisational Layer (8000)
  │
  ├─ POST /api/rank-suppliers       ──→  Logical Layer (8080)
  │                                           │ urllib
  │                                           ▼
  │                                     Organisational Layer (8000)
  │
  ├─ POST /api/evaluate-policy      ──→  Logical Layer (8080)
  │                                           │ urllib
  │                                           ▼
  │                                     Organisational Layer (8000)
  │
  ├─ POST /api/check-escalations    ──→  Logical Layer (8080)
  │                                           │ urllib
  │                                           ▼
  │                                     Organisational Layer (8000)
  │
  ├─ POST /api/generate-recommendation ──→ Logical Layer (8080)
  │                                           │ Anthropic SDK
  │                                           ▼
  │                                     Claude (LLM)
  │
  ├─ POST /api/assemble-output      ──→  Logical Layer (8080)
  │                                           │ Anthropic SDK
  │                                           ▼
  │                                     Claude (LLM)
  │
  └─ POST /api/format-invalid-response ──→ Logical Layer (8080)
                                              │ Anthropic SDK
                                              ▼
                                        Claude (LLM)
```

n8n orchestrates the multi-step pipeline with branching on validation and compliance. The Logical Layer delegates data access to the Organisational Layer via HTTP and uses the Anthropic API for LLM-powered validation, recommendation, and enrichment.

## Pipeline Logging

Every invocation of `/api/processRequest` is instrumented with `PipelineLogger` (`app/services/pipeline_logger.py`). The logger creates a pipeline run record and logs each step (timing, truncated input/output, errors) to the Org Layer's `/api/logs/*` endpoints. Logging is fire-and-forget: if the Org Layer is unreachable, the pipeline continues unaffected.

Individual pipeline endpoints (`/api/fetch-request`, `/api/check-compliance`, etc.) also support logging when the `X-Pipeline-Run-Id` header is provided. See `LOGGING_API.md` in the organisational layer for full API documentation.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORGANISATIONAL_LAYER_URL` | `http://organisational-layer:8000` (Docker) / `http://3.68.96.236:8000` (scripts standalone) | Base URL of the Organisational Layer API |
| `ANTHROPIC_API_KEY` | *(none — required)* | API key for the Anthropic API, used by validate, recommend, assemble, and format-invalid scripts |

The FastAPI app reads `ORGANISATIONAL_LAYER_URL` via `app/config.py` (Pydantic Settings). The standalone scripts in `scripts/` also read this env var (falling back to the hardcoded production URL if unset). `ANTHROPIC_API_KEY` is read by the `anthropic` SDK directly from the environment.

## Tech stack

- **Python 3.14** / FastAPI / httpx / Pydantic
- **Anthropic SDK** for LLM-powered validation, recommendation, and enrichment (Claude claude-sonnet-4-6)
- Scripts use Python standard library (`urllib`, `json`, `os`, `sys`) + `anthropic` + `python-dotenv`
- Talks to Organisational Layer via HTTP (no direct DB connection)
- Docker / docker-compose for deployment (unified compose at `backend/docker-compose.yml`)

## Deployment

See root `DEPLOYMENT.md` for full deployment guide.
