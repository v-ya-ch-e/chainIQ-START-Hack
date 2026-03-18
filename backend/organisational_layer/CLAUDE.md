# **USER INSTRUCTIONS**

> Always work in .venv
> Always update @CLAUDE.md file to keep it updated about the project
> You should keep this block with user instructions as it is. You can write below everything you want

# **SERVICE OVERVIEW**

FastAPI backend microservice for the ChainIQ procurement platform. Provides CRUD and analytics endpoints for all 22 normalised MySQL tables hosted on AWS RDS.

## How to run

```bash
cd backend/organisational_layer
source .venv/bin/activate
cp .env.example .env   # then fill in your RDS credentials
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

## Docker

```bash
cd backend/organisational_layer
cp .env.example .env   # fill in credentials
docker compose up --build
```

## Key files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app entry point, CORS, router registration, `/health` endpoint |
| `app/config.py` | Pydantic Settings — reads DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME from env |
| `app/database.py` | SQLAlchemy engine, session factory, `get_db` dependency |
| `app/models/` | SQLAlchemy ORM models for all 22 tables (reference, requests, historical, policies) |
| `app/schemas/` | Pydantic request/response schemas |
| `app/routers/categories.py` | CRUD for categories |
| `app/routers/suppliers.py` | CRUD for suppliers + sub-resources (categories, regions, pricing) |
| `app/routers/requests.py` | CRUD for purchase requests with delivery countries and scenario tags |
| `app/routers/awards.py` | Read endpoints for historical awards |
| `app/routers/policies.py` | Read endpoints for approval thresholds, preferred/restricted supplier policies |
| `app/routers/rules.py` | Read endpoints for category, geography, and escalation rules |
| `app/routers/analytics.py` | Domain-specific analytics: compliant suppliers, pricing lookup, approval tiers, restriction/preferred checks, applicable rules, request overview, spend aggregations, supplier win rates |
| `Dockerfile` | Python 3.14-slim container, installs deps, runs uvicorn |
| `docker-compose.yml` | Single service with health check, connects to external RDS |
| `requirements.txt` | fastapi, uvicorn, sqlalchemy, pymysql, pydantic-settings, python-dotenv, cryptography |
| `.env.example` | Template for DB connection env vars |

## API endpoints summary

### CRUD
- `GET/POST /api/categories/`, `GET/PUT/DELETE /api/categories/{id}`
- `GET/POST /api/suppliers/`, `GET/PUT/DELETE /api/suppliers/{id}`, `GET /api/suppliers/{id}/categories|regions|pricing`
- `GET/POST /api/requests/`, `GET/PUT/DELETE /api/requests/{id}`
- `GET /api/awards/`, `GET /api/awards/{id}`, `GET /api/awards/by-request/{id}`
- `GET /api/policies/approval-thresholds`, `GET /api/policies/preferred-suppliers`, `GET /api/policies/restricted-suppliers`
- `GET /api/rules/category`, `GET /api/rules/geography`, `GET /api/rules/escalation`

### Analytics
- `GET /api/analytics/compliant-suppliers` — non-restricted suppliers for category+country
- `GET /api/analytics/pricing-lookup` — pricing tier for supplier+category+region+quantity
- `GET /api/analytics/approval-tier` — approval threshold for currency+amount
- `GET /api/analytics/check-restricted` — restriction check for supplier+category+country
- `GET /api/analytics/check-preferred` — preferred status for supplier+category+region
- `GET /api/analytics/applicable-rules` — category and geography rules for a context
- `GET /api/analytics/request-overview/{id}` — comprehensive request evaluation
- `GET /api/analytics/spend-by-category` — aggregated historical spend by category
- `GET /api/analytics/spend-by-supplier` — aggregated historical spend by supplier
- `GET /api/analytics/supplier-win-rates` — win rates from historical awards

## Tech stack

- **Python 3.14** / FastAPI / SQLAlchemy 2.0 / PyMySQL
- **MySQL 8** on AWS RDS (database created by `database_init/migrate.py`)
- Docker / docker-compose for deployment
