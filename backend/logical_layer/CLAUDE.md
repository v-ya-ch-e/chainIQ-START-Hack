# **USER INSTRUCTIONS**

> Always work in .venv
> Always update @CLAUDE.md file to keep it updated about the project
> You should keep this block with user instructions as it is. You can write below everything you want

# **SERVICE OVERVIEW**

Procurement decision engine (Logical Layer) for the ChainIQ platform. Provides HTTP API endpoints that n8n workflows call to filter suppliers by product category and rank them by true cost. The full end-to-end processing pipeline (`/api/processRequest`) is a stub — individual steps are exposed as separate endpoints so n8n can orchestrate them.

## How to run

```bash
cd backend/logical_layer
source .venv/bin/activate
cp .env.example .env   # set ORGANISATIONAL_LAYER_URL (default: http://localhost:8000 for local dev)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Swagger UI: http://localhost:8080/docs

**Requires the Organisational Layer to be running** (default: port 8000).

## Docker (both services together)

```bash
cd backend
cp organisational_layer/.env.example organisational_layer/.env   # fill in DB credentials
cp logical_layer/.env.example logical_layer/.env                 # default is fine for Docker
docker compose up --build
```

## Key files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app entry point, CORS, router registration, `/health` endpoint |
| `app/config.py` | Pydantic Settings — reads `ORGANISATIONAL_LAYER_URL` from env |
| `app/clients/organisational.py` | Async HTTP client wrapping Organisational Layer API calls (for future pipeline use) |
| `app/routers/processing.py` | `POST /api/processRequest` — stub endpoint (not yet implemented) |
| `app/routers/scripts.py` | `POST /api/filter-suppliers` and `POST /api/rank-suppliers` — script-backed endpoints |
| `app/schemas/processing.py` | Pydantic models for the processRequest stub |
| `app/schemas/scripts.py` | Pydantic models for the filter and rank endpoints |
| `scripts/filterCompaniesByProduct.py` | Standalone script: filters suppliers by product category via Organisational Layer API |
| `scripts/rankCompanies.py` | Standalone script: ranks suppliers by true cost (price adjusted for quality/risk/ESG) |
| `scripts/SCRIPTS_DOCUMENTATION.md` | Detailed documentation for both scripts |
| `Dockerfile` | Python 3.14-slim container, copies `app/` and `scripts/`, runs uvicorn on port 8080 |
| `requirements.txt` | fastapi, uvicorn, httpx, pydantic-settings, python-dotenv |
| `.env.example` | Template: `ORGANISATIONAL_LAYER_URL=http://organisational-layer:8000` |

## API endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| `GET` | `/health` | Active | Liveness check |
| `POST` | `/api/filter-suppliers` | Active | Filter suppliers by product category |
| `POST` | `/api/rank-suppliers` | Active | Rank suppliers by true cost |
| `POST` | `/api/processRequest` | Stub | Full pipeline (not yet implemented) |

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

n8n orchestrates the two-step flow: first filter, then rank. The Logical Layer delegates all data access to the Organisational Layer via HTTP.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORGANISATIONAL_LAYER_URL` | `http://organisational-layer:8000` (Docker) / `http://3.68.96.236:8000` (scripts standalone) | Base URL of the Organisational Layer API |

The FastAPI app reads this via `app/config.py` (Pydantic Settings). The standalone scripts in `scripts/` also read this env var (falling back to the hardcoded production URL if unset).

## Tech stack

- **Python 3.14** / FastAPI / httpx / Pydantic
- Scripts use only Python standard library (`urllib`, `json`, `os`, `sys`)
- Talks to Organisational Layer via HTTP (no direct DB connection)
- Docker / docker-compose for deployment (unified compose at `backend/docker-compose.yml`)

## Deployment

See root `DEPLOYMENT.md` for full deployment guide.
