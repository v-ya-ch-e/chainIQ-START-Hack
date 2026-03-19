# Pipeline Logging API

The Organisational Layer exposes a set of logging endpoints under `/api/logs/` that store detailed, step-level telemetry for every pipeline execution. The Logical Layer calls these endpoints automatically during request processing.

## Database Tables

### `pipeline_runs`

One row per pipeline execution.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment |
| `run_id` | VARCHAR(36) | UUID, unique external reference |
| `request_id` | VARCHAR(20) | FK to `requests.request_id` |
| `status` | VARCHAR(20) | `running`, `completed`, or `failed` |
| `started_at` | DATETIME | When the pipeline run started |
| `completed_at` | DATETIME | When the run finished (nullable) |
| `total_duration_ms` | INT | Total elapsed time in milliseconds |
| `steps_completed` | INT | Number of steps that succeeded |
| `steps_failed` | INT | Number of steps that failed |
| `error_message` | TEXT | Top-level error if the run failed |

### `pipeline_log_entries`

One row per step within a run.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment |
| `run_id` | VARCHAR(36) | FK to `pipeline_runs.run_id` |
| `step_name` | VARCHAR(60) | Step identifier (e.g. `validate_request`) |
| `step_order` | INT | 1-based execution order |
| `status` | VARCHAR(20) | `started`, `completed`, `failed`, or `skipped` |
| `started_at` | DATETIME | When the step started |
| `completed_at` | DATETIME | When the step finished |
| `duration_ms` | INT | Step duration in milliseconds |
| `input_summary` | JSON | Truncated input data for audit |
| `output_summary` | JSON | Truncated output data for audit |
| `error_message` | TEXT | Error details if the step failed |
| `metadata` | JSON | Step-specific counters and identifiers |

## Endpoints

### `POST /api/logs/runs`

Create a new pipeline run record.

**Request body:**

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "request_id": "REQ-000042",
  "started_at": "2026-03-19T14:30:00"
}
```

**Response** (201):

```json
{
  "id": 1,
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "request_id": "REQ-000042",
  "status": "running",
  "started_at": "2026-03-19T14:30:00",
  "completed_at": null,
  "total_duration_ms": null,
  "steps_completed": 0,
  "steps_failed": 0,
  "error_message": null
}
```

### `PATCH /api/logs/runs/{run_id}`

Update an existing run (typically to mark it as completed or failed).

**Request body** (all fields optional):

```json
{
  "status": "completed",
  "completed_at": "2026-03-19T14:30:12",
  "total_duration_ms": 12340,
  "steps_completed": 11,
  "steps_failed": 0
}
```

### `GET /api/logs/runs`

List pipeline runs with optional filters.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `request_id` | string | - | Filter by request ID |
| `status` | string | - | Filter by status (`running`, `completed`, `failed`) |
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 50 | Page size (max 200) |

**Response:**

```json
{
  "items": [ ... ],
  "total": 42
}
```

### `GET /api/logs/runs/{run_id}`

Get a single run with all its log entries.

**Response:**

```json
{
  "id": 1,
  "run_id": "550e8400-...",
  "request_id": "REQ-000042",
  "status": "completed",
  "started_at": "2026-03-19T14:30:00",
  "completed_at": "2026-03-19T14:30:12",
  "total_duration_ms": 12340,
  "steps_completed": 11,
  "steps_failed": 0,
  "error_message": null,
  "entries": [
    {
      "id": 1,
      "run_id": "550e8400-...",
      "step_name": "fetch_request",
      "step_order": 1,
      "status": "completed",
      "started_at": "2026-03-19T14:30:00",
      "completed_at": "2026-03-19T14:30:01",
      "duration_ms": 230,
      "input_summary": {"request_id": "REQ-000042"},
      "output_summary": {"title": "Office supplies", "country": "DE"},
      "error_message": null,
      "metadata_": null
    }
  ]
}
```

### `GET /api/logs/by-request/{request_id}`

Get all pipeline runs for a given request, ordered newest first. Each run includes its full list of log entries.

### `POST /api/logs/entries`

Create a new log entry (step started).

**Request body:**

```json
{
  "run_id": "550e8400-...",
  "step_name": "validate_request",
  "step_order": 2,
  "started_at": "2026-03-19T14:30:01",
  "input_summary": {"request_id": "REQ-000042", "title": "Office supplies"}
}
```

**Response** (201): returns the created entry with `id` and `status: "started"`.

### `PATCH /api/logs/entries/{entry_id}`

Update a log entry (step completed or failed).

**Request body** (all fields optional):

```json
{
  "status": "completed",
  "completed_at": "2026-03-19T14:30:03",
  "duration_ms": 1820,
  "output_summary": {"issue_count": 2, "is_valid": true},
  "metadata_": {"issue_types": ["missing_optional", "budget_mismatch"]}
}
```

## Pipeline Steps Logged

When the full pipeline runs via `POST /api/processRequest`, these steps are logged in order:

| Order | Step Name | Description |
|-------|-----------|-------------|
| 1 | `fetch_request` | Fetch purchase request from Org Layer |
| 2 | `validate_request` | Deterministic + LLM validation |
| 3 | `format_invalid_response` | (early exit only) Format invalid response |
| 4 | `filter_suppliers` | Filter suppliers by category |
| 5 | `check_compliance` | Check restrictions, delivery, residency |
| 6 | `rank_suppliers` | Rank by true cost |
| 7 | `enrich_supplier_names` | Fetch supplier display names |
| 8 | `evaluate_policy` | Approval tier, preferred, rules |
| 9 | `check_escalations` | Fetch escalation triggers |
| 10 | `generate_recommendation` | Determine recommendation + LLM reasoning |
| 11 | `fetch_historical_awards` | Fetch audit trail |
| 12 | `assemble_output` | Assemble final output with LLM enrichment |

## n8n Integration

When using the individual pipeline endpoints (e.g. `POST /api/check-compliance`), pass the header `X-Pipeline-Run-Id` with a valid run UUID to log the step execution to an existing run. If the header is omitted, no logging occurs.

## Design Notes

- **Fire-and-forget**: Logging never blocks or fails the pipeline. If the Org Layer is unreachable, the pipeline continues without logging.
- **Truncation**: Input/output summaries are truncated to prevent storing large payloads. Lists longer than 5 items are replaced with `{_type: "list", _length: N, _sample: [...]}`.
- **String limits**: String values in summaries are capped at 500 characters; error messages at 2000 characters.

---

# Audit Logging API

Separate from step-level telemetry, the **audit log** captures human-readable, categorized messages that explain what the system decided and why. Every log entry is tied to a `request_id` and optionally to a `run_id`, enabling full audit trails per request.

## Database Table: `audit_logs`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment |
| `request_id` | VARCHAR(20) | FK to `requests.request_id` |
| `run_id` | VARCHAR(36) | Optional link to a pipeline run UUID |
| `timestamp` | DATETIME(3) | Millisecond-precision event time |
| `level` | VARCHAR(10) | `debug`, `info`, `warn`, `error`, `critical` |
| `category` | VARCHAR(40) | Semantic grouping (see below) |
| `step_name` | VARCHAR(60) | Pipeline step that produced this log |
| `message` | TEXT | Human-readable audit message |
| `details` | JSON | Structured data for programmatic consumption |
| `source` | VARCHAR(30) | Producing service (`logical_layer`, `organisational_layer`, `n8n`) |

### Categories

| Category | Use |
|----------|-----|
| `validation` | Missing fields, contradictions, budget mismatches |
| `policy` | Threshold checks, approval tier determinations |
| `supplier_filter` | Supplier inclusions/exclusions with reasons |
| `compliance` | Restriction checks, geography/residency checks |
| `pricing` | Tier lookups, cost calculations |
| `ranking` | Scoring decisions, weight applications |
| `escalation` | Triggered rules, escalation targets |
| `recommendation` | Final decision reasoning |
| `data_access` | Which data sources were consulted |
| `general` | Catch-all |

## Endpoints

### `POST /api/logs/audit`

Create a single audit log entry.

**Request body:**

```json
{
  "request_id": "REQ-000042",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-03-19T14:30:01.234",
  "level": "info",
  "category": "policy",
  "step_name": "evaluate_policy",
  "message": "Applied approval threshold AT-002: contract value EUR 37,200 exceeds EUR 25,000 — 2 quotes required.",
  "details": {"policy_id": "AT-002", "threshold": 25000, "actual_value": 37200, "quotes_required": 2},
  "source": "logical_layer"
}
```

**Response** (201): returns the created entry with `id`.

### `POST /api/logs/audit/batch`

Create multiple audit log entries in one call.

**Request body:**

```json
{
  "entries": [
    {
      "request_id": "REQ-000042",
      "timestamp": "2026-03-19T14:30:01.100",
      "level": "info",
      "category": "supplier_filter",
      "step_name": "filter_suppliers",
      "message": "Included SUP-0001 (Dell): covers IT > Docking Stations in DE.",
      "details": {"supplier_id": "SUP-0001", "action": "included"}
    },
    {
      "request_id": "REQ-000042",
      "timestamp": "2026-03-19T14:30:01.120",
      "level": "warn",
      "category": "compliance",
      "step_name": "check_compliance",
      "message": "Excluded SUP-0008 (Computacenter): risk_score 34 exceeds threshold.",
      "details": {"supplier_id": "SUP-0008", "action": "excluded", "risk_score": 34}
    }
  ]
}
```

**Response** (201): returns a list of created entries.

### `GET /api/logs/audit/by-request/{request_id}`

Get all audit logs for a specific request.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `level` | string | - | Filter by severity level |
| `category` | string | - | Filter by semantic category |
| `run_id` | string | - | Filter to a specific pipeline run |
| `step_name` | string | - | Filter to a specific pipeline step |
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 100 | Page size (max 500) |

**Response:**

```json
{
  "items": [ ... ],
  "total": 47
}
```

### `GET /api/logs/audit/summary/{request_id}`

Returns an aggregated audit summary for a request.

**Response:**

```json
{
  "request_id": "REQ-000042",
  "total_entries": 47,
  "by_level": [
    {"level": "info", "count": 38},
    {"level": "warn", "count": 6},
    {"level": "error", "count": 3}
  ],
  "by_category": [
    {"category": "validation", "count": 5},
    {"category": "supplier_filter", "count": 12},
    {"category": "policy", "count": 8},
    {"category": "escalation", "count": 3}
  ],
  "distinct_policies": ["AT-001", "AT-002", "CR-001", "ER-001", "ER-004"],
  "distinct_suppliers": ["SUP-0001", "SUP-0002", "SUP-0007", "SUP-0008"],
  "escalation_count": 3,
  "first_event": "2026-03-19T14:30:00.100",
  "last_event": "2026-03-19T14:30:12.450"
}
```

The `distinct_policies` field is extracted from entries where `category = "policy"` and `details.policy_id` is present. The `distinct_suppliers` field is extracted from entries where `category` is one of `supplier_filter`, `compliance`, `ranking`, or `pricing` and `details.supplier_id` is present.

### `GET /api/logs/audit`

List all audit logs with the same filter set as `by-request` plus an additional `request_id` filter. Ordered newest first.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `request_id` | string | - | Filter by request ID |
| `level` | string | - | Filter by severity level |
| `category` | string | - | Filter by semantic category |
| `run_id` | string | - | Filter to a specific pipeline run |
| `step_name` | string | - | Filter to a specific pipeline step |
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 100 | Page size (max 500) |

## Usage from the Logical Layer

The pipeline should emit audit logs at key decision points:

1. **Validation step** — Log each issue found (missing field, contradiction, budget mismatch) with `category: "validation"` and relevant severity
2. **Supplier filtering** — Log each inclusion/exclusion with `category: "supplier_filter"` and `details: {"supplier_id": "...", "action": "included/excluded", "reason": "..."}`
3. **Compliance checks** — Log restriction checks, geography checks with `category: "compliance"`
4. **Pricing** — Log tier lookups and cost calculations with `category: "pricing"` and `details: {"supplier_id": "...", "tier": "...", "unit_price": ..., "total": ...}`
5. **Policy evaluation** — Log each policy applied with `category: "policy"` and `details: {"policy_id": "...", ...}`
6. **Escalation** — Log each triggered rule with `category: "escalation"` and `level: "warn"` or `"error"`
7. **Recommendation** — Log the final decision with `category: "recommendation"`

Use `POST /api/logs/audit/batch` to flush all logs for a step in a single HTTP call.
