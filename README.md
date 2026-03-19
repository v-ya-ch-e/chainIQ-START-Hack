# ChainIQ START Hack 2026

Full-stack prototype for an audit-ready autonomous sourcing agent.

## Services

The project runs as **two independent Docker Compose stacks** on a shared network:

**Backend stack** (`backend/docker-compose.yml`):

- `organisational-layer` (FastAPI): `http://localhost:8000` — CRUD + analytics API
- `logical-layer` (FastAPI): `http://localhost:8080` — Procurement decision engine

**Frontend stack** (`docker-compose.yml` at repo root):

- `frontend` (Next.js): `http://localhost:3000` — Web UI
- `mysql` (MySQL 8.4): `localhost:3306` — Optional local database (`localdb` profile)
- `migrator` (one-shot): loads `data/` into MySQL via `database_init/migrate.py` (`tools` profile)

## Prerequisites

- Docker Engine 20.10+ with Docker Compose plugin

## Quick Start

```bash
# 1. Create the shared Docker network (one-time)
docker network create chainiq-network

# 2. Configure environment
cp .env.example .env
cp backend/organisational_layer/.env.example backend/organisational_layer/.env
cp backend/logical_layer/.env.example backend/logical_layer/.env

# Set BACKEND_INTERNAL_URL in .env to your deployed organisational-layer URL

# 3. Start backend services
cd backend
docker compose up --build -d
cd ..

# 4. Start frontend only (dev mode with hot reload)
docker compose up --build

# 5. Optional: run local DB + migration instead of deployed backend
docker compose --profile localdb up -d mysql
docker compose --profile tools run --rm migrator
```

## Production-like mode (no hot reload)

```bash
docker compose -f docker-compose.yml up --build
```

## Common commands

```bash
# Stop frontend stack
docker compose down

# Stop backend stack
cd backend && docker compose down

# Stop and wipe database volume
docker compose down -v

# View logs
docker compose logs -f frontend
cd backend && docker compose logs -f organisational-layer
```

## API wiring

- Frontend routes under `/api/*` are proxied to the backend via Next.js rewrites.
- Server-side data loaders use `BACKEND_INTERNAL_URL` for container-internal requests.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment instructions covering local development, AWS (EC2 + RDS), and nginx reverse proxy setup.
