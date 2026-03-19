# **USER INSTRUCTIONS**

> Always work in .venv
> Always update @CLAUDE.md file to keep it updated about the project
> You should keep this block with user instructions as it is. You can write below everything you want

# **SERVICE OVERVIEW**

Procurement decision engine (Logical Layer) for the ChainIQ platform. Receives purchase requests from n8n via HTTP, fetches data from the Organisational Layer API, applies business logic (validation, policy checks, supplier ranking, escalation), and returns structured, auditable sourcing recommendations.

## How to run

```bash
cd backend/logical_layer
source .venv/bin/activate
cp .env.example .env   # set ORGANISATIONAL_LAYER_URL (default: http://localhost:8000 for local dev)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Swagger UI: http://localhost:8080/docs

**Requires the Organisational Layer to be running on port 8000.**

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
| `app/clients/organisational.py` | Async HTTP client wrapping all Organisational Layer API calls |
| `app/schemas/processing.py` | Pydantic request/response models (mirrors `example_output.json` structure) |
| `app/routers/processing.py` | `POST /api/process-request` — the endpoint n8n calls |
| `app/services/pipeline.py` | Processing pipeline orchestrator (parse, validate, policy, rank, escalate) |
| `Dockerfile` | Python 3.14-slim container, installs deps, runs uvicorn on port 8080 |
| `requirements.txt` | fastapi, uvicorn, httpx, pydantic-settings, python-dotenv |
| `.env.example` | Template: `ORGANISATIONAL_LAYER_URL=http://organisational-layer:8000` |

## API endpoints

- `GET /health` — liveness check
- `POST /api/process-request` — main processing endpoint; accepts `{"request_id": "REQ-000004"}`, returns full procurement decision

## Architecture

```
n8n → POST /api/process-request → Logical Layer (8080)
                                        ↓ HTTP
                                  Organisational Layer (8000)
                                        ↓ SQL
                                  AWS RDS MySQL
```

## Pipeline stages (in `app/services/pipeline.py`)

1. **Fetch** — calls `GET /api/analytics/request-overview/{id}` on org layer
2. **Interpret** — extracts structured fields from request data (TODO: add LLM for text parsing)
3. **Validate** — checks completeness, budget sufficiency, lead-time feasibility (TODO: full implementation)
4. **Policy** — evaluates approval thresholds, preferred/restricted suppliers, rules (TODO: full implementation)
5. **Rank** — scores and ranks compliant suppliers (TODO: weighted scoring algorithm)
6. **Escalate** — checks all 8 escalation rules (TODO: full ER-001..ER-008 implementation)
7. **Recommend** — produces final status: proceed / proceed_with_conditions / cannot_proceed

## Tech stack

- **Python 3.14** / FastAPI / httpx / Pydantic
- Talks to Organisational Layer via HTTP (no direct DB connection)
- Docker / docker-compose for deployment (unified compose at `backend/docker-compose.yml`)

## Deployment

See `backend/DEPLOYMENT.md` for full deployment guide.
