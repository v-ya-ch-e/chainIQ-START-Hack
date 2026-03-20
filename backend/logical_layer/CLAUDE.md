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
- `GET /api/dynamic-rules/active` — fetch all active dynamic rules for rule engine evaluation
- `PUT /api/requests/{id}` — status updates
- `POST /api/logs/runs`, `PATCH /api/logs/runs/{run_id}` — pipeline run lifecycle
- `POST /api/logs/entries`, `PATCH /api/logs/entries/{entry_id}` — step-level logging
- `POST /api/logs/audit/batch` — bulk audit log creation
- `POST /api/rule-versions/evaluations/from-pipeline` — evaluation persistence
- `POST /api/pipeline-results/` — full pipeline output persistence
- `GET /api/pipeline-results/latest/{request_id}` — retrieve latest persisted result

## Bugs Fixed (2026-03-19)

The following critical bugs were identified and fixed via code review + runtime verification:

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| 100% `cannot_proceed` rate | ER-009 (`is_blocking=True`) fired on every LLM contradiction | Made ER-009 non-blocking (severity: medium) |
| ER-001 misidentifying budget insufficiency | Dynamic rule checked `budget_amount >= min_ranked_total` | Changed to `required` eval_type: fires only when budget/quantity is NULL |
| ER-005 wrong escalation target | Hardcoded "Data Protection Officer" | Changed to "Security/Compliance" per spec |
| ER-006 not detecting single-supplier risk | Checked `max_supplier_capacity >= quantity` | Added `single_supplier_capacity_risk` context field (true when only 1 supplier meets qty) |
| ER-008 never firing | `has_unregistered_supplier` hardcoded to `False` | Computed by comparing supplier `service_regions` against delivery countries |
| ER-010 blocking incorrectly | `is_blocking=True` for non-spec rule | Made non-blocking |
| Hardcoded AT-002/EUR 25k in fallback | `_discover_pipeline_issues` used fixed tier values | Uses actual `approval_tier` from fetch_result |
| Risk threshold excludes valid suppliers | `RISK_SCORE_THRESHOLD = 30` | Raised to 70 |
| ER-004 misused for lead time | Lead time infeasible mapped to ER-004 | Lead time now maps to ER-010; ER-004 only for "no compliant supplier" |
| Escalation persistence uses wrong version_id | Fallback to `pc001` (PC-001's version) for unknown rules | Logs warning and skips instead of inserting with wrong FK |
| Confidence always 0 for blocking | `_compute_confidence` returned 0 immediately | Now applies -25 per blocking escalation (graded, not binary) |
| `has_contradictions` too broad | Included `policy_conflict` type | Only checks `contradictory` type now |

## Bugs Fixed (2026-03-20)

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| False positive contradictions (e.g. REQ-000001) | VAL-006 (custom_llm rule) had a vague 1-line prompt that hijacked contradiction detection, bypassing the detailed `VALIDATION_SYSTEM_PROMPT`. Generic `LLMRuleResponse` model let the LLM hallucinate issues. | Always use direct LLM path with detailed prompt + constrained `LLMValidationResult` schema. VAL-006 deactivated. |
| Non-deterministic LLM responses across calls | No `temperature` parameter set on LLM calls — used API default which includes randomness. | Added `temperature=0` to the validation LLM call for deterministic results. |
| Generic "LLM detected contradictions" with no details | VAL-006's `fail_message_template` was static — actual contradiction descriptions from the LLM were lost. | Direct LLM path preserves each contradiction's specific `description` and `field`, logged individually to audit trail. |
| Missing audit trail for contradiction check outcome | No audit entry when LLM found zero contradictions (the expected case). | Added explicit audit log for both zero-contradiction and N-contradiction outcomes. |

## Bugs Fixed (2026-03-20 — batch 2)

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Budget insufficient → "proceed" with 90% confidence (REQ-000005) | Recommendation status determined ONLY from escalation count. No escalation existed for budget < prices. Dynamic rule VAL-004 produced `type="validation_rule_failed"` instead of `"budget_insufficient"`, so escalation context `has_budget_issue` was always False. | Three-part fix: (1) recommend.py considers critical/high validation issues in status determination, (2) escalate.py adds `ER-BUDGET` non-blocking escalation when budget < min supplier price, (3) validate.py uses `_classify_issue_type()` to tag budget issues as `"budget_insufficient"`. |
| LLM recommendation/notes too verbose | Prompts allowed 1-3 sentences for recommendation, no length constraints for enrichment. `max_tokens` was 1500/3000. | Tightened prompts to 1-2 sentences max for recommendation, 2-3 sentences for supplier notes. Reduced `max_tokens` to 600/1500. |
| Stale debug instrumentation in validate.py | Previous debug session left a log write in Phase B. | Removed. |

## Key Design Decisions

- **ER-009, ER-010, and ER-BUDGET are not in the challenge spec** (ER-001–008 only). They are custom rules added for additional coverage but must remain non-blocking to avoid overriding the spec's escalation semantics.
- **Recommendation status considers validation issues** — critical validation issues (like budget insufficiency) force `proceed_with_conditions` even when no escalation rules fire. This prevents the pipeline from recommending "proceed" when the budget cannot cover any supplier. Status hierarchy: blocking escalation → `cannot_proceed`, budget insufficient → `proceed_with_conditions`, non-blocking escalations or critical/high validation issues → `proceed_with_conditions`, else → `proceed`.
- **Risk score threshold of 70** allows more suppliers into the compliant set while still excluding genuinely high-risk non-preferred suppliers.
- **Confidence scoring** uses graded penalties: -25 per blocking escalation, -10 per non-blocking, -20/10/5/2 per validation issue severity (critical/high/medium/low). This provides meaningful differentiation even when blocking issues exist.
- **LLM contradiction detection uses direct path only** — the `VALIDATION_SYSTEM_PROMPT` in `validate.py` is the single source of truth for contradiction detection prompt engineering. The dynamic rule `VAL-006` is deprecated/inactive. This avoids the prompt quality split between the rule engine's generic model and the purpose-built `LLMValidationResult` schema.
- **temperature=0 for validation LLM calls** ensures deterministic contradiction detection across repeated pipeline runs on the same request. The `LLMClient.structured_call` accepts an optional `temperature` parameter.
- **LLM response length control** — recommendation prompts capped at 1-2 sentences, enrichment supplier notes at 2-3 sentences. `max_tokens` reduced to 600 (recommendation) and 1500 (enrichment) to enforce brevity.
