# AGENTS.md — Project Context

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
