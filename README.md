# ChainIQ START Hack 2026

Full-stack prototype for an audit-ready sourcing agent.

## Services

- `frontend` (Next.js): `http://localhost:3000`
- `backend` (FastAPI): `http://localhost:8000`
- `mysql` (MySQL 8): `localhost:3306`
- `migrator` (one-shot): loads `data/` into MySQL via `database_init/migrate.py`

## Prerequisites

- Docker + Docker Compose plugin

## Environment

```bash
cp .env.example .env
```

You can keep defaults for local development.

## Development mode (hot reload)

This uses `docker-compose.yml` + `docker-compose.override.yml`.

```bash
docker compose up --build
```

In development mode:

- backend runs with `uvicorn --reload`
- frontend runs with `next dev`
- source files are mounted into containers

## Production-like mode

Run only the base compose file (no dev override):

```bash
docker compose -f docker-compose.yml up --build
```

This uses production commands/images:

- backend runs `uvicorn` without reload
- frontend runs `next start`

## Database bootstrap (required on first start)

After MySQL is up, run:

```bash
docker compose --profile tools run --rm migrator
```

This creates tables and imports dataset files from `data/`.

## Common commands

- Stop services:

```bash
docker compose down
```

- Stop and remove DB volume (full reset):

```bash
docker compose down -v
```

- Validate compose configuration:

```bash
docker compose config
```

## API wiring notes

- Frontend routes under `/api/*` are proxied to backend using Next rewrites.
- Server-side data loaders also use `BACKEND_INTERNAL_URL` for container-internal requests.