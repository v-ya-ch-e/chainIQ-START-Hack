# **USER INSTRUCTIONS**

> Always work in .venv
> Always update @CLAUDE.md file to keep it updated about the project
> You should keep this block with user instructions as it is. You can write below everything you want

# **SERVICE OVERVIEW**

Procurement decision engine (Logical Layer) for the ChainIQ platform. Provides HTTP API endpoints that n8n workflows call to validate purchase requests, filter suppliers by product category, and rank them by true cost. The full end-to-end processing pipeline (`/api/processRequest`) is a stub — individual steps are exposed as separate endpoints so n8n can orchestrate them.

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
**Requires `ANTHROPIC_API_KEY` to be set** for the `/api/validate-request` endpoint.

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
| `app/clients/organisational.py` | Async HTTP client wrapping Organisational Layer API calls (for future pipeline use) |
| `app/routers/processing.py` | `POST /api/processRequest` — stub endpoint (not yet implemented) |
| `app/routers/scripts.py` | `POST /api/filter-suppliers`, `/api/rank-suppliers`, `/api/validate-request` — script-backed endpoints |
| `app/schemas/processing.py` | Pydantic models for the processRequest stub |
| `app/schemas/scripts.py` | Pydantic models for the filter, rank, and validate endpoints |
| `scripts/filterCompaniesByProduct.py` | Standalone script: filters suppliers by product category via Organisational Layer API |
| `scripts/rankCompanies.py` | Standalone script: ranks suppliers by true cost (price adjusted for quality/risk/ESG) |
| `scripts/validateRequest.py` | Standalone script: validates purchase request completeness and consistency using deterministic checks + Anthropic LLM |
| `scripts/SCRIPTS_DOCUMENTATION.md` | Detailed documentation for all scripts |
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
| `POST` | `/api/processRequest` | Stub | Full pipeline (not yet implemented) |

### POST /api/validate-request

Accepts a full purchase request, runs deterministic checks for required/optional fields, then uses the Anthropic API to detect contradictions between the free-text `request_text` and structured fields. Returns validation issues and a structured interpretation.

**Request body:** A full purchase request JSON object (same structure as `examples/example_request.json`).

**Response:**
```json
{
  "completeness": false,
  "issues": [
    {
      "field": "quantity",
      "type": "missing_optional",
      "message": "Field 'quantity' is missing or null — request is incomplete."
    }
  ],
  "request_interpretation": {
    "category_l1": "IT",
    "category_l2": "Hardware",
    "quantity": null,
    "budget_amount": 50000,
    "currency": "EUR",
    "delivery_country": "DE",
    "requester_instruction": "must use Dell"
  }
}
```

### POST /api/filter-suppliers

Accepts a purchase request with `category_l1` and `category_l2`, queries the Organisational Layer to find all suppliers serving that exact category, and returns matching supplier-category rows.

**Request body:**
```json
{
  "category_l1": "IT",
  "category_l2": "Hardware"
}
```

**Response:** `{ "suppliers": [...], "category_l1": "...", "category_l2": "...", "count": N }`

### POST /api/rank-suppliers

Accepts a purchase request dict and a list of supplier rows (typically from `/api/filter-suppliers`), computes a true-cost score adjusted for quality, risk, and optionally ESG, and returns suppliers ranked best-to-worst.

**Request body:**
```json
{
  "request": {
    "category_l1": "IT",
    "category_l2": "Hardware",
    "quantity": 50,
    "esg_requirement": false,
    "delivery_countries": ["DE"]
  },
  "suppliers": [ ... ]
}
```

**Response:** `{ "ranked": [...], "category_l1": "...", "category_l2": "...", "count": N }`

### POST /api/processRequest

Stub endpoint. Accepts `{"request_id": "REQ-000004"}` and returns `{"request_id": "...", "status": "not_implemented", "message": "..."}`. Will be implemented later as the full procurement decision pipeline.

## Architecture

```
n8n workflow
  │
  ├─ POST /api/validate-request  ──→  Logical Layer (8080)
  │                                        │ Anthropic API
  │                                        ▼
  │                                  Claude (LLM)
  │
  ├─ POST /api/filter-suppliers  ──→  Logical Layer (8080)
  │                                        │ urllib
  │                                        ▼
  │                                  Organisational Layer (8000)
  │                                        │ SQL
  │                                        ▼
  │                                  AWS RDS MySQL
  │
  └─ POST /api/rank-suppliers    ──→  Logical Layer (8080)
                                           │ urllib
                                           ▼
                                     Organisational Layer (8000)
```

n8n orchestrates the multi-step flow: validate the request, then filter suppliers, then rank them. The Logical Layer delegates data access to the Organisational Layer via HTTP and uses the Anthropic API for LLM-powered validation.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORGANISATIONAL_LAYER_URL` | `http://organisational-layer:8000` (Docker) / `http://3.68.96.236:8000` (scripts standalone) | Base URL of the Organisational Layer API |
| `ANTHROPIC_API_KEY` | *(none — required)* | API key for the Anthropic API, used by `validateRequest.py` |

The FastAPI app reads `ORGANISATIONAL_LAYER_URL` via `app/config.py` (Pydantic Settings). The standalone scripts in `scripts/` also read this env var (falling back to the hardcoded production URL if unset). `ANTHROPIC_API_KEY` is read by the `anthropic` SDK directly from the environment.

## Tech stack

- **Python 3.14** / FastAPI / httpx / Pydantic
- **Anthropic SDK** for LLM-powered request validation (Claude claude-sonnet-4-6)
- Scripts use Python standard library (`urllib`, `json`, `os`, `sys`) + `anthropic` + `python-dotenv`
- Talks to Organisational Layer via HTTP (no direct DB connection)
- Docker / docker-compose for deployment (unified compose at `backend/docker-compose.yml`)

## Deployment

See root `DEPLOYMENT.md` for full deployment guide.
