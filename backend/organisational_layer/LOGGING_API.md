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
