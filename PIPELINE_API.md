# Pipeline API Reference

The ChainIQ Logical Layer exposes a 9-step procurement decision pipeline via REST endpoints. All endpoints are served at `http://localhost:8080` (or `http://logical-layer:8080` inside Docker).

---

## Architecture

```
┌─────────────┐     HTTP      ┌──────────────────┐     HTTP      ┌──────────────────────┐
│   Frontend   │ ──────────── │  Logical Layer    │ ──────────── │  Organisational Layer │
│  (Next.js)   │   :3000      │  (FastAPI :8080)  │   :8000      │  (FastAPI :8000)      │
└─────────────┘               │                   │               │                       │
                              │  9-Step Pipeline   │               │  MySQL (AWS RDS)      │
                              │  LLM (Anthropic)   │               │  37 tables            │
                              └──────────────────┘               └──────────────────────┘
```

The logical layer is **stateless** — it reads data from the organisational layer, processes it through the pipeline, writes logs/evaluations back, and returns the result. No local database.

---

## Pipeline Steps

| # | Step | Module | Purpose |
|---|------|--------|---------|
| 1 | Fetch | `steps/fetch.py` | Load request overview, suppliers, pricing, rules, approval tier, historical awards from Org Layer |
| 2 | Validate | `steps/validate.py` | Deterministic completeness checks + LLM contradiction detection |
| 3 | Filter | `steps/filter.py` | Enrich compliant suppliers with matched pricing tiers |
| 4 | Comply | `steps/comply.py` | Per-supplier compliance (residency, capacity, risk, restrictions via Org Layer) |
| 5 | Rank | `steps/rank.py` | Rank by true cost (price / quality×risk×ESG) or quality score fallback |
| 6 | Policy | `steps/policy.py` | Evaluate approval thresholds, preferred/restricted supplier status, category and geography rules |
| 7 | Escalate | `steps/escalate.py` | Merge escalations from Org Layer + pipeline-discovered issues (budget, lead time, residency, restrictions) |
| 8 | Recommend | `steps/recommend.py` | Determine recommendation status + LLM prose generation |
| 9 | Assemble | `steps/assemble.py` | Combine all outputs into final JSON with LLM enrichment and audit trail |

Steps 6 and 7 run **in parallel** via `asyncio.gather`.

---

## Endpoints

### `POST /api/pipeline/process`

Process a single purchase request through the full 9-step pipeline.

**Request:**
```json
{
  "request_id": "REQ-000004"
}
```

**Response:** Full `PipelineOutput` object (see Output Schema below).

**Status codes:**
- `200` — Success
- `404` — Request not found in Org Layer
- `500` — Pipeline failure

---

### `POST /api/pipeline/process-batch`

Process multiple requests concurrently in the background.

**Request:**
```json
{
  "request_ids": ["REQ-000001", "REQ-000002", "REQ-000003"],
  "concurrency": 5
}
```

**Response (202 Accepted):**
```json
{
  "batch_id": "uuid",
  "queued": 3,
  "concurrency": 5,
  "message": "Processing started"
}
```

---

### `GET /api/pipeline/status/{request_id}`

Get the latest pipeline run status for a request.

**Response:**
```json
{
  "request_id": "REQ-000004",
  "latest_run": { "run_id": "...", "status": "completed", ... },
  "recommendation_status": "cannot_proceed",
  "escalation_count": 3,
  "confidence_score": 0
}
```

---

### `GET /api/pipeline/result/{request_id}`

Get the full cached pipeline result from the latest successful run.

**Response:** Full `PipelineOutput` object. Returns `404` if the request hasn't been processed yet.

---

### `GET /api/pipeline/runs`

List all pipeline runs with optional filters.

**Query params:** `request_id`, `status`, `skip` (default 0), `limit` (default 50, max 200)

---

### `GET /api/pipeline/runs/{run_id}`

Get a specific run with all step details.

---

### `GET /api/pipeline/audit/{request_id}`

Get full audit trail for a request.

**Query params:** `level`, `category`, `run_id`, `step_name`, `skip`, `limit`

---

### `GET /api/pipeline/audit/{request_id}/summary`

Aggregated audit summary (counts by level/category, distinct policies, suppliers, escalation count).

---

### Step-Level Debug Endpoints

Each step endpoint runs the pipeline up to that step and returns intermediate results. Useful for debugging and testing.

| Endpoint | Steps Executed |
|----------|---------------|
| `POST /api/pipeline/steps/fetch` | 1 (Fetch) |
| `POST /api/pipeline/steps/validate` | 1-2 (Fetch + Validate) |
| `POST /api/pipeline/steps/filter` | 1-3 (Fetch + Validate + Filter) |
| `POST /api/pipeline/steps/comply` | 1-4 (Fetch + Validate + Filter + Comply) |
| `POST /api/pipeline/steps/rank` | 1-5 (Fetch through Rank) |
| `POST /api/pipeline/steps/escalate` | 1-7 (Fetch through Escalate) |

All accept `{"request_id": "REQ-000004"}` and return the step's result model.

---

### `GET /health`

Service health check.

**Response:**
```json
{
  "status": "ok",
  "org_layer": "reachable",
  "llm": "configured",
  "version": "2.0.0"
}
```

---

## Output Schema

The full pipeline output (`PipelineOutput`) matches the structure in `examples/example_output.json`:

```json
{
  "request_id": "REQ-000004",
  "processed_at": "2026-03-19T12:00:00Z",
  "run_id": "uuid",
  "status": "processed | invalid",

  "request_interpretation": {
    "category_l1": "IT",
    "category_l2": "Docking Stations",
    "quantity": 240,
    "unit_of_measure": "device",
    "budget_amount": 25199.55,
    "currency": "EUR",
    "delivery_country": "DE",
    "required_by_date": "2026-03-20",
    "days_until_required": 6,
    "data_residency_required": false,
    "esg_requirement": false,
    "preferred_supplier_stated": "Dell Enterprise Europe",
    "incumbent_supplier": "Bechtle Workplace Solutions",
    "requester_instruction": "no exception"
  },

  "validation": {
    "completeness": "pass | fail",
    "issues_detected": [
      {
        "issue_id": "V-001",
        "severity": "critical | high | medium | low",
        "type": "budget_insufficient | missing_info | contradictory | lead_time_infeasible",
        "description": "...",
        "action_required": "..."
      }
    ]
  },

  "policy_evaluation": {
    "approval_threshold": {
      "rule_applied": "AT-002",
      "basis": "...",
      "quotes_required": 2,
      "approvers": ["business", "procurement"],
      "deviation_approval": "Procurement Manager",
      "note": "..."
    },
    "preferred_supplier": {
      "supplier": "Dell Enterprise Europe",
      "status": "eligible | not_found | restricted | not_preferred | no_coverage",
      "is_preferred": true,
      "covers_delivery_country": true,
      "is_restricted": false,
      "policy_note": "..."
    },
    "restricted_suppliers": {
      "SUP-0008_Computacenter_Services": {
        "restricted": false,
        "note": "..."
      }
    },
    "category_rules_applied": [...],
    "geography_rules_applied": [...]
  },

  "supplier_shortlist": [
    {
      "rank": 1,
      "supplier_id": "SUP-0007",
      "supplier_name": "Bechtle Workplace Solutions",
      "preferred": true,
      "incumbent": true,
      "pricing_tier_applied": "100-499 units",
      "unit_price_eur": 148.80,
      "total_price_eur": 35712.00,
      "expedited_unit_price_eur": 163.68,
      "expedited_total_eur": 39283.20,
      "standard_lead_time_days": 16,
      "expedited_lead_time_days": 9,
      "quality_score": 82,
      "risk_score": 12,
      "esg_score": 78,
      "policy_compliant": true,
      "covers_delivery_country": true,
      "recommendation_note": "..."
    }
  ],

  "suppliers_excluded": [
    {
      "supplier_id": "SUP-0008",
      "supplier_name": "Computacenter Services",
      "reason": "..."
    }
  ],

  "escalations": [
    {
      "escalation_id": "ESC-001",
      "rule": "ER-001",
      "trigger": "...",
      "escalate_to": "Requester Clarification",
      "blocking": true
    }
  ],

  "recommendation": {
    "status": "proceed | proceed_with_conditions | cannot_proceed",
    "reason": "...",
    "preferred_supplier_if_resolved": "Bechtle Workplace Solutions",
    "preferred_supplier_rationale": "...",
    "minimum_budget_required": 35712.00,
    "minimum_budget_currency": "EUR",
    "confidence_score": 0
  },

  "audit_trail": {
    "policies_checked": ["AT-002", "CR-001"],
    "supplier_ids_evaluated": ["SUP-0001", "SUP-0002", "SUP-0007"],
    "pricing_tiers_applied": "100-499 units (EU region, EUR currency)",
    "data_sources_used": ["requests.json", "suppliers.csv", "pricing.csv", "policies.json", "historical_awards.csv"],
    "historical_awards_consulted": true,
    "historical_award_note": "..."
  }
}
```

---

## Recommendation Status Logic

| Status | Condition |
|--------|-----------|
| `cannot_proceed` | Any blocking escalation exists |
| `proceed_with_conditions` | Non-blocking escalations exist, no blocking |
| `proceed` | No escalations |

---

## Confidence Score

Starts at 100, modified by:
- **Blocking escalation**: immediately 0
- **Non-blocking escalation**: -10 each
- **Validation issues**: -15 (critical), -10 (high), -5 (medium), -2 (low)
- **Price gap > 20% between #1 and #2**: +10
- **Top supplier is preferred**: +5
- Clamped to [0, 100]

---

## Escalation Rules

| Rule | Trigger | Escalate To | Blocking |
|------|---------|-------------|----------|
| ER-001 | Budget insufficient | Requester Clarification | Yes |
| ER-002 | Preferred supplier is restricted | Procurement Manager | Yes |
| ER-004 | Lead time infeasible / No compliant suppliers | Head of Category | Yes |
| ER-005 | Data residency not satisfiable | Data Protection Officer | Yes |
| AT-002 | Policy conflict with requester instruction | Procurement Manager | Yes |

---

## True Cost Ranking Formula

```
quality_factor = max(quality_score, 1) / 100
risk_factor = max(100 - risk_score, 1) / 100
denominator = quality_factor × risk_factor

If ESG required:
  esg_factor = max(esg_score, 1) / 100
  denominator = denominator × esg_factor

true_cost = total_price / denominator
```

Suppliers are ranked ascending by true cost. When quantity is null, ranking falls back to quality score descending.

---

## Compliance Checks

| Check | Condition | Result |
|-------|-----------|--------|
| Data residency | `data_residency_constraint=true` and `data_residency_supported=false` | Excluded |
| Capacity | `quantity > capacity_per_month` | Excluded |
| Risk (non-preferred) | `preferred=false` and `risk_score > 30` | Excluded |
| Restriction | `check-restricted` API returns `is_restricted=true` | Excluded |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORGANISATIONAL_LAYER_URL` | `http://organisational-layer:8000` | Org Layer base URL |
| `ANTHROPIC_API_KEY` | (none) | Anthropic API key (optional — pipeline works without it) |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Anthropic model name |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## LLM Integration

The pipeline uses Anthropic Claude at three points:
1. **Validation** (Step 2): Contradiction detection between `request_text` and structured fields
2. **Recommendation** (Step 8): Audit-ready prose generation for the recommendation
3. **Enrichment** (Step 9): Detailed issue descriptions and supplier recommendation notes

All LLM calls use `tool_use` for structured output. If the API key is missing or calls fail, the pipeline gracefully degrades to deterministic-only mode.

---

## Testing

```bash
cd backend/logical_layer
source .venv/bin/activate
python3 -m pytest tests/ -v
```

136 tests covering all pipeline steps, models, utilities, and API endpoints. Tests use mocked Org Layer and LLM clients — no external dependencies required.

---

## Docker

```bash
cd backend
docker compose up --build
```

Both services run on the shared `chainiq-network`. The logical layer waits for the organisational layer health check before starting.
