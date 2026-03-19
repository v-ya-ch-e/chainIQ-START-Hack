# **USER INSTRUCTIONS**

> Always work in .venv
> Always update @CLAUDE.md file to keep it updated about the project
> You should keep this block with user instructions as it is. You can write below everything you want

# **SERVICE OVERVIEW**

FastAPI microservice implementing the procurement decision pipeline. Processes purchase requests through a 9-step pipeline (fetch → validate → filter → comply → rank → policy → escalate → recommend → assemble) and persists results to the Organisational Layer.

## Pipeline Result Persistence

After processing, the pipeline persists results in two ways:

1. **Evaluation data** — `POST /api/rule-versions/evaluations/from-pipeline` (hard rule checks, policy checks, supplier evaluations, escalations)
2. **Full pipeline output** — `POST /api/pipeline-results/` (entire output JSON for frontend display)

Both the normal completion path and the early-exit path (invalid requests) persist results.

## Status/Result Retrieval

The `GET /api/pipeline/result/{request_id}` endpoint checks in-memory cache first, then falls back to the org layer's persisted `pipeline_results` table. This means results survive server restarts and are available across instances.

## PDF Audit Report

`GET /api/pipeline/report/{request_id}` generates a downloadable PDF audit report. It aggregates:

1. **Pipeline result** — from in-memory cache or persisted `pipeline_results` table
2. **Audit logs** — from `GET /api/logs/audit/by-request/{id}` (best-effort)
3. **Audit summary** — from `GET /api/logs/audit/summary/{id}` (best-effort)

The PDF is rendered via `reportlab` in `app/reports/audit_report.py` and returned as a `StreamingResponse` with `Content-Type: application/pdf`. Report generation is self-contained — if audit logs or summary are unavailable the report still renders with pipeline result data only.

## Org Layer Endpoints Used

- `GET /api/analytics/request-overview/{id}?pipeline_mode=true` — fetch raw reference data (pipeline_mode=true bypasses the frontend gate that hides supplier data for unprocessed requests)
- `GET /api/escalations/by-request/{id}` — deterministic escalation queue
- `GET /api/analytics/check-restricted` — per-supplier restriction check
- `PUT /api/requests/{id}` — status updates
- `POST /api/logs/runs`, `PATCH /api/logs/runs/{run_id}` — pipeline run lifecycle
- `POST /api/logs/entries`, `PATCH /api/logs/entries/{entry_id}` — step-level logging
- `POST /api/logs/audit/batch` — bulk audit log creation
- `POST /api/rule-versions/evaluations/from-pipeline` — evaluation persistence
- `POST /api/pipeline-results/` — full pipeline output persistence
- `GET /api/pipeline-results/latest/{request_id}` — retrieve latest persisted result
