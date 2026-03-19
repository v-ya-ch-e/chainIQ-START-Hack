# PAST_EXPERIENCE.md — Lessons from Logical Layer v1

This document captures everything learned while building the first version of the Logical Layer (procurement decision engine). It serves as the knowledge base for the rewrite.

---

## 1. Architecture Decisions and Why They Were Made

### Two-Layer Backend

The system uses two independent FastAPI services on a shared Docker network (`chainiq-network`):

- **Organisational Layer** (port 8000) — CRUD + analytics API over a normalised MySQL database (24 tables). Owns all data access, governance rule evaluation, and escalation computation.
- **Logical Layer** (port 8080) — Procurement decision engine. Never touches the database directly. Calls the Org Layer via HTTP for all data, then applies business logic and LLM-powered reasoning.

This separation was intentional: it means every data decision is auditable through the Org Layer, and the Logical Layer is stateless and horizontally scalable.

### Scripts as Importable Modules

Each pipeline step was implemented as a standalone Python script in `scripts/` that could be:
1. Imported as a module (`from scripts.validateRequest import validate_request`)
2. Called via stdin/stdout (`echo '{}' | python scripts/validateRequest.py`)
3. Called via CLI with file paths (`python scripts/validateRequest.py input.json output.json`)

This was designed for n8n integration flexibility. In practice, only the module import path was used by the FastAPI app. The CLI/stdin modes added complexity without value.

### n8n Orchestration

All pipeline steps were exposed as individual HTTP endpoints so n8n could orchestrate them with branching, retries, and human-in-the-loop logic. A convenience endpoint `POST /api/processRequest` also ran the full pipeline in a single call.

Individual endpoints supported `X-Pipeline-Run-Id` header for step-level logging when orchestrated externally.

### LLM Usage Philosophy

LLM (Anthropic Claude `claude-sonnet-4-6`) was used only for:
- **Validation** — Detecting contradictions between `request_text` and structured fields
- **Recommendation reasoning** — Generating human-readable explanations
- **Output enrichment** — Adding severity/action_required to validation issues, recommendation notes to suppliers
- **Invalid request formatting** — Summarizing validation failures for requesters

All policy logic (thresholds, restrictions, escalations, compliance) was deterministic Python code. This was the right call — judges valued auditability and the escalation engine in the Org Layer handles all 8 ER rules + AT conflict detection deterministically.

---

## 2. Pipeline Flow (What Worked)

The 11-step pipeline in `POST /api/processRequest`:

```
Step 1:  FETCH REQUEST         — org_client.get_request(request_id)
Step 2:  VALIDATE              — validate_request(request_data)  [LLM]
Step 3:  BRANCH ON VALIDITY    — if missing_required → format_invalid_response → early return
Step 4:  FILTER SUPPLIERS      — filter_suppliers({category_l1, category_l2})
Step 5:  CHECK COMPLIANCE      — check_compliance(request_data, suppliers)
Step 6:  RANK SUPPLIERS        — rank_suppliers(request_data, compliant_suppliers)
Step 7:  ENRICH SUPPLIER NAMES — org_client.get_compliant_suppliers() for name mapping
Step 8:  EVALUATE POLICY       — evaluate_policy(request_data, ranked, non_compliant)
Step 9:  CHECK ESCALATIONS     — check_escalations(request_id)
Step 10: GENERATE RECOMMENDATION — generate_recommendation(pipeline_data)  [LLM]
Step 11: FETCH HISTORICAL AWARDS — org_client.get_awards_by_request(request_id)
Step 12: ASSEMBLE OUTPUT       — assemble_output(all_step_outputs)  [LLM]
```

### What worked well

- **Early return on invalid requests**: Branching after validation to format_invalid_response saved unnecessary supplier lookups for malformed requests.
- **`asyncio.to_thread()` for blocking scripts**: Since scripts used blocking `urllib`, wrapping them in `asyncio.to_thread()` kept the FastAPI event loop responsive.
- **Fire-and-forget logging**: `PipelineLogger` never blocked the pipeline if the Org Layer logging endpoints were unreachable.
- **Step-level timing**: Every step was timed and logged with input/output summaries, making debugging straightforward.

### What was awkward

- The "enrich supplier names" step (Step 7) was a separate step just to fetch `supplier_name` values. This should have been part of the filter or compliance step.
- Historical awards (Step 11) were fetched after recommendation generation, meaning the recommendation couldn't reference historical patterns.
- The pipeline had no parallelism — steps that could run concurrently (e.g., escalation check + policy evaluation) ran sequentially.

---

## 3. Known Bugs and Field Name Mismatches

### `is_valid` vs `completeness`

In `processing.py` line 102:
```python
bag["metadata"] = {"is_valid": validation_result.get("is_valid")}
```

But `validateRequest.py` returns `completeness`, not `is_valid`:
```python
return {
    "completeness": completeness,
    "issues": all_issues,
    "request_interpretation": interpretation,
}
```

Result: logged metadata always had `is_valid: None`.

### `recommendation_status` vs `status`

In `processing.py` line 245:
```python
bag["output_summary"] = {
    "status": recommendation.get("recommendation_status"),
    ...
}
```

But `generateRecommendation.py` returns `status`, not `recommendation_status`:
```python
recommendation = {
    "status": status,
    "reason": llm_result.get("reason", ""),
    ...
}
```

Result: logged output summary always had `status: None`.

### Missing category branch

When `category_l1` or `category_l2` is missing after validation, the pipeline calls `format_invalid_response()`. But the interpretation from the LLM might have extracted a category — the pipeline checks `interpretation.get("category_l1")` as a fallback, which was correct. However, if both the structured field AND the interpretation are missing, the error message doesn't clearly tell the user which category fields are needed.

---

## 4. Data Normalization Gotchas

### `delivery_countries` format inconsistency

The Org Layer returns `delivery_countries` in two formats depending on the API endpoint:
- Simple: `["DE", "FR"]`
- Object: `[{"country_code": "DE"}, {"country_code": "FR"}]`

A helper `_normalize_delivery_countries()` was needed and was **duplicated across 4 files**:
- `app/routers/processing.py`
- `scripts/validateRequest.py`
- `scripts/checkCompliance.py`
- `scripts/evaluatePolicy.py`

Each copy was slightly different. The rewrite must centralize this.

### `scenario_tags` format inconsistency

Similar to delivery_countries:
- Simple: `["standard", "urgent"]`
- Object: `[{"tag": "standard"}, {"tag": "urgent"}]`

Handled in `processing.py` `_build_request_data_for_scripts()` but not consistently elsewhere.

### Numeric field type coercion

Fields from the Org Layer arrive as strings (MySQL decimal serialization):
- `budget_amount`: needs `float()` conversion
- `quantity`: needs `int(float())` conversion (float first because it may arrive as `"240.0"`)

This was handled in `_build_request_data_for_scripts()` in `processing.py` but scripts also needed to handle raw values when called independently.

### `preferred_supplier_mentioned` vs `incumbent_supplier`

These are intentionally different fields:
- `preferred_supplier_mentioned` = who the requester wants
- `incumbent_supplier` = who currently has the contract

The LLM validation prompt explicitly excludes this difference from contradiction detection. This is correct behavior.

---

## 5. Mixed HTTP Client Problem

### The dual-client architecture

The app layer used async `httpx` via `OrganisationalClient` (`app/clients/organisational.py`):
```python
class OrganisationalClient:
    def __init__(self):
        self._client = httpx.AsyncClient(base_url=..., timeout=30.0)
```

But scripts used blocking `urllib.request` with their own `api_get()` helper:
```python
BASE_URL = os.environ.get("ORGANISATIONAL_LAYER_URL", "http://3.68.96.236:8000")

def api_get(path, params=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())
```

This `api_get()` function was **duplicated across 5 script files**: `filterCompaniesByProduct.py`, `checkCompliance.py`, `rankCompanies.py`, `evaluatePolicy.py`, `checkEscalations.py`.

### Problems this caused

1. **Hardcoded IP fallback**: Scripts fell back to `http://3.68.96.236:8000` (the AWS EC2 IP) when `ORGANISATIONAL_LAYER_URL` wasn't set. This worked in development but was fragile.
2. **No connection pooling**: Each `urllib.request.urlopen()` created a new TCP connection. The `httpx.AsyncClient` in the app layer reused connections.
3. **No centralized error handling**: Each script had its own `try/except urllib.error.HTTPError` blocks.
4. **Timeout mismatch**: Scripts used 15s timeout, app client used 30s.

### Recommendation for rewrite

Use a single async `httpx` client throughout. Pass it to pipeline steps as a dependency. No urllib, no hardcoded IPs.

---

## 6. LLM Integration Patterns

### Which scripts use LLM

| Script | LLM Purpose | Could be deterministic? |
|--------|------------|------------------------|
| `validateRequest.py` | Detect contradictions between `request_text` and structured fields; extract `requester_instruction` | Contradiction detection: no (requires language understanding). Instruction extraction: possibly with regex for common patterns. |
| `generateRecommendation.py` | Generate `reason` and `preferred_supplier_rationale` text | The status determination (`proceed`/`cannot_proceed`/`proceed_with_conditions`) is already deterministic. Only the prose explanation needs LLM. |
| `assembleOutput.py` | Enrich validation issues with severity/action_required; generate `recommendation_note` for each supplier | Severity could be rule-based. Recommendation notes with specific figures need LLM or templates. |
| `formatInvalidResponse.py` | Generate human-readable `summary` and enriched issue descriptions | Could use templates for common patterns. LLM adds polish. |

### JSON parsing from LLM output

All 4 LLM scripts used the same fragile pattern:
```python
raw = response.content[0].text.strip()
if raw.startswith("```"):
    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
start = raw.find("{")
end = raw.rfind("}") + 1
if start != -1 and end > 0:
    result = json.loads(raw[start:end])
```

This fails when:
- The LLM returns multiple JSON objects
- The JSON contains escaped braces in strings
- The LLM wraps output in extra text after the closing brace

**Recommendation**: Use Anthropic's structured output / tool_use feature, or at minimum validate the parsed JSON against a Pydantic model.

### Error handling pattern

All LLM calls were wrapped in broad `try/except Exception` that returned fallback values:
```python
try:
    # ... LLM call ...
    return json.loads(raw[start:end])
except Exception:
    pass
return fallback_dict
```

This was good for resilience (pipeline never crashed due to LLM failures) but bad for debugging (errors were silently swallowed with no logging).

**Recommendation**: Log the exception. Return the fallback but record that the LLM call failed in the step metadata.

### Anthropic client lifecycle

A new `anthropic.Anthropic()` client was created for every single LLM call. The SDK handles connection pooling internally, but creating a single client per service lifetime would be cleaner and allow configuration in one place.

### System prompts

The system prompts were well-crafted and should be preserved/adapted:
- **Validation prompt**: Explicitly lists what IS and ISN'T a contradiction. Handles multi-language input. Conservative by design ("when in doubt, do NOT flag").
- **Recommendation prompt**: Asks for specific supplier names, prices, and rule IDs. Professional, audit-ready tone.
- **Enrichment prompt**: Defines severity levels (critical/high/medium/low). Asks for specific figures.
- **Invalid response prompt**: Defines severity levels and asks for actionable descriptions.

---

## 7. Org Layer API Dependencies

### Endpoints used by the pipeline

| Endpoint | Used by | Purpose |
|----------|---------|---------|
| `GET /api/requests/{id}` | `org_client.get_request()` | Fetch full purchase request |
| `GET /api/categories` | `filterCompaniesByProduct.py` | Resolve category_l1+l2 to category_id |
| `GET /api/suppliers?category_l1=...` | `filterCompaniesByProduct.py` | List suppliers for a category |
| `GET /api/suppliers/{id}/categories` | `filterCompaniesByProduct.py` | Get category rows for a supplier |
| `GET /api/analytics/compliant-suppliers` | `checkCompliance.py`, `processing.py` | Non-restricted suppliers for category+country |
| `GET /api/analytics/pricing-lookup` | `rankCompanies.py` | Pricing tier for supplier+category+region+quantity |
| `GET /api/analytics/approval-tier` | `evaluatePolicy.py` | Approval threshold for currency+amount |
| `GET /api/analytics/check-restricted` | `checkCompliance.py`, `evaluatePolicy.py` | Restriction check with scope+conditional logic |
| `GET /api/analytics/check-preferred` | `evaluatePolicy.py` | Preferred status for supplier+category+region |
| `GET /api/analytics/applicable-rules` | `evaluatePolicy.py` | Category and geography rules for a context |
| `GET /api/escalations/by-request/{id}` | `checkEscalations.py` | Computed escalations for a request |
| `GET /api/awards/by-request/{id}` | `org_client.get_awards_by_request()` | Historical awards for audit trail |

### The unused mega-endpoint

`GET /api/analytics/request-overview/{id}` exists and returns a pre-assembled evaluation package containing:
- The full request object
- Compliant suppliers with pricing
- Approval tier
- Applicable rules
- Historical awards
- Computed escalations

The `OrganisationalClient` had a method for it (`get_request_overview()`) but the pipeline never used it. Instead, it made 10+ individual HTTP calls per request. **The rewrite should use this endpoint as the primary data source** and only make targeted follow-up calls when needed.

### Org Layer analytics endpoints — response shapes

Key response shapes to remember:

**`/api/analytics/compliant-suppliers`** returns:
```json
[{"supplier_id": "SUP-0001", "supplier_name": "Dell Enterprise Europe", ...}]
```

**`/api/analytics/pricing-lookup`** returns:
```json
[{"supplier_id": "...", "unit_price": "148.80", "total_price": "35712.00", "currency": "EUR", "standard_lead_time_days": 26, "expedited_lead_time_days": 18, ...}]
```
Note: prices are strings (MySQL decimal serialization).

**`/api/analytics/approval-tier`** returns:
```json
{"threshold_id": "AT-002", "min_amount": "25000.00", "max_amount": "99999.99", "min_supplier_quotes": 2, "managers": [...], "deviation_approvers": [...], "policy_note": "..."}
```

**`/api/analytics/check-restricted`** returns:
```json
{"supplier_id": "...", "is_restricted": false, "restriction_reason": null}
```

**`/api/escalations/by-request/{id}`** returns:
```json
[{"escalation_id": "ESC-001", "rule_id": "ER-001", "rule_label": "...", "trigger": "...", "escalate_to": "...", "blocking": true, "status": "open"}]
```

---

## 8. Policy Schema Inconsistencies

### Threshold key naming

The raw `policies.json` data has inconsistent key names:
- **EUR/CHF thresholds**: `min_amount`, `max_amount`, `min_supplier_quotes`, `managed_by`, `deviation_approval_required_from`
- **USD thresholds**: `min_value`, `max_value`, `quotes_required`, `approvers`, `policy_note`

The Org Layer's `database_init/migrate.py` normalizes this when loading into MySQL. The analytics API (`/api/analytics/approval-tier`) returns a consistent shape. But `evaluatePolicy.py` still used `tier.get("min_supplier_quotes")` which relies on the Org Layer having done the normalization correctly.

### Restricted supplier scoping

`is_restricted` in `suppliers.csv` is unreliable — it's a hint only. The actual restriction scope comes from `policies.json` `restricted_suppliers` and can be:
- **Global**: restricted everywhere
- **Country-scoped**: restricted only in specific countries
- **Value-conditional**: restricted only above a certain contract value (e.g., "restricted above EUR 75K")

The Org Layer's `check-restricted` endpoint handles all three cases. The Logical Layer scripts correctly deferred to this endpoint rather than trusting the CSV flag.

---

## 9. Ranking Formula

### True-cost computation

```python
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100)
```

With ESG requirement:
```python
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100) / (esg_score / 100)
```

Lower true_cost = better deal. The `overpayment` field (`true_cost - total_price`) shows the hidden cost of quality/risk gaps.

### Null quantity handling

When `quantity` is null, pricing lookup is skipped and suppliers are ranked by `quality_score` descending instead. This is a reasonable fallback but loses the ability to compare on price.

### `COUNTRY_TO_REGION` mapping

Maps 19 countries to 5 regions. Was duplicated between `rankCompanies.py` and `evaluatePolicy.py`:

```python
COUNTRY_TO_REGION = {
    "DE": "EU", "FR": "EU", "NL": "EU", "BE": "EU", "AT": "EU",
    "IT": "EU", "ES": "EU", "PL": "EU", "UK": "EU",
    "CH": "CH",
    "US": "Americas", "CA": "Americas", "BR": "Americas", "MX": "Americas",
    "SG": "APAC", "AU": "APAC", "IN": "APAC", "JP": "APAC",
    "UAE": "MEA", "ZA": "MEA",
}
```

The rewrite should have this in one place.

### Pricing tier selection

`rankCompanies.py` calls `/api/analytics/pricing-lookup` which returns the correct tier for the given quantity. It takes the first result (`pricing[0]`). The pricing tier includes both standard and expedited lead times and prices.

Expedited pricing fields: `expedited_unit_price` and `expedited_lead_time_days` are present in the pricing data but the ranking formula only uses standard `total_price`. Expedited prices are passed through to the output for display but don't affect ranking.

---

## 10. Pipeline Logging

### PipelineLogger design

`PipelineLogger` is an async context manager that:
1. Creates a pipeline run record via `POST /api/logs/runs`
2. For each step, creates a log entry via `POST /api/logs/entries`
3. Updates the entry with timing, output summary, and metadata via `PATCH /api/logs/entries/{id}`
4. Finalizes the run with total duration and step counts via `PATCH /api/logs/runs/{id}`

Two context managers:
- `step(name, input_summary)` — simple, just records timing and status
- `step_with_output(name, input_summary)` — yields a dict (`bag`) that the caller populates with `output_summary` and `metadata` keys

### Fire-and-forget safety

All logging calls are wrapped in `try/except Exception` that logs a warning and continues. If the Org Layer is down, the pipeline still runs — you just lose the audit log.

### `metadata_` field name

The Org Layer's SQLAlchemy model uses `metadata_ = Column("metadata", ...)` because `metadata` is a reserved SQLAlchemy attribute. The pipeline logger sends `metadata_` in PATCH payloads. This is a quirk that must be preserved if using the same Org Layer.

### Truncation

`truncate_summary()` recursively truncates values for safe JSON storage:
- Strings capped at 500 chars
- Dicts capped at 30 keys
- Lists longer than 5 items replaced with `{"_type": "list", "_length": N, "_sample": [first 3]}`
- Recursion depth capped at 3

---

## 11. Output Format Requirements

### Top-level structure

Must match `examples/example_output.json`:

```json
{
  "request_id": "REQ-000004",
  "processed_at": "2026-03-14T18:02:11Z",
  "request_interpretation": { ... },
  "validation": { ... },
  "policy_evaluation": { ... },
  "supplier_shortlist": [ ... ],
  "suppliers_excluded": [ ... ],
  "escalations": [ ... ],
  "recommendation": { ... },
  "audit_trail": { ... }
}
```

Plus a `status` field added by `processing.py`: `"processed"` for valid requests, `"invalid"` for failed validation.

### `request_interpretation` fields

```json
{
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
  "requester_instruction": "no exception — single supplier only"
}
```

### `validation` section

```json
{
  "completeness": "pass",
  "issues_detected": [
    {
      "issue_id": "V-001",
      "severity": "critical",
      "type": "budget_insufficient",
      "description": "Budget of EUR 25,199.55 cannot cover...",
      "action_required": "Requester must either increase budget..."
    }
  ]
}
```

Note: `completeness` is `"pass"` or `"fail"` (string), not a boolean. The validation script returns a boolean `completeness`, and `assembleOutput.py` converts it.

### `supplier_shortlist` entries

```json
{
  "rank": 1,
  "supplier_id": "SUP-0007",
  "supplier_name": "Bechtle Workplace Solutions",
  "preferred": true,
  "incumbent": true,
  "pricing_tier_applied": "100–499 units",
  "unit_price_eur": 148.80,
  "total_price_eur": 35712.00,
  "standard_lead_time_days": 26,
  "expedited_lead_time_days": 18,
  "expedited_unit_price_eur": 160.70,
  "expedited_total_eur": 38568.00,
  "quality_score": 82,
  "risk_score": 19,
  "esg_score": 72,
  "policy_compliant": true,
  "covers_delivery_country": true,
  "recommendation_note": "Lowest total price at EUR 35,712..."
}
```

Note the **dynamic currency keys**: `unit_price_eur`, `total_price_eur` — the suffix changes based on request currency (`eur`, `chf`, `usd`). The `assembleOutput.py` builds these dynamically:
```python
f"unit_price_{currency.lower()}": sup.get("unit_price"),
f"total_price_{currency.lower()}": sup.get("total_price"),
```

### `escalations` entries

```json
{
  "escalation_id": "ESC-001",
  "rule": "ER-001",
  "trigger": "Budget is insufficient...",
  "escalate_to": "Requester Clarification",
  "blocking": true
}
```

### `recommendation` section

```json
{
  "status": "cannot_proceed",
  "reason": "Three blocking issues prevent autonomous award...",
  "preferred_supplier_if_resolved": "Bechtle Workplace Solutions",
  "preferred_supplier_rationale": "Bechtle is the incumbent...",
  "minimum_budget_required": 35712.00,
  "minimum_budget_currency": "EUR"
}
```

Status values: `"proceed"`, `"proceed_with_conditions"`, `"cannot_proceed"`.

### `audit_trail` section

```json
{
  "policies_checked": ["AT-001", "AT-002", "CR-001", "ER-001", "ER-004"],
  "supplier_ids_evaluated": ["SUP-0001", "SUP-0002", "SUP-0007", "SUP-0008"],
  "pricing_tiers_applied": "100–499 units (EU region, EUR currency)",
  "data_sources_used": ["requests.json", "suppliers.csv", "pricing.csv", "policies.json"],
  "historical_awards_consulted": true,
  "historical_award_note": "AWD-000009 through AWD-000011..."
}
```

---

## 12. Escalation Rules Reference

The Org Layer's escalation engine evaluates these rules. The Logical Layer fetches the results via `GET /api/escalations/by-request/{id}`.

| Rule | Trigger | Blocking | Escalate To |
|------|---------|----------|-------------|
| ER-001 | Missing required info (budget, quantity, category) | Yes | Requester Clarification |
| ER-002 | Preferred supplier is restricted | Yes | Procurement Manager |
| ER-003 | Strategic sourcing approval tier (Head of Strategic Sourcing / CPO) | No | Head of Strategic Sourcing / CPO |
| ER-004 | No compliant supplier with valid pricing | Yes | Head of Category |
| ER-005 | Data residency requirement unsatisfiable | Yes | Data Protection Officer |
| ER-006 | Single supplier capacity risk | Yes | Head of Category |
| ER-007 | Influencer Campaign Management (brand safety) | Yes | Head of Marketing |
| ER-008 | Preferred supplier unregistered for USD delivery scope | Yes | Category Manager |
| AT-xxx | Single-supplier instruction conflicts with multi-quote threshold | Yes | Procurement Manager |

The AT conflict rule is sophisticated: it detects single-supplier language patterns in `request_text` across 6 languages (en, fr, de, es, pt, ja) and checks whether the approval threshold requires multiple quotes.

---

## 13. filterCompaniesByProduct — Inefficiency

The `filterCompaniesByProduct.py` script was the least efficient pipeline step. It:

1. Fetched ALL categories (`GET /api/categories`) to resolve `category_l1`+`category_l2` to a `category_id`
2. Fetched suppliers filtered by `category_l1` (`GET /api/suppliers?category_l1=...`)
3. For EACH supplier, made a separate HTTP call to get its category rows (`GET /api/suppliers/{id}/categories`)
4. Filtered to rows matching the resolved `category_id`

This was N+2 HTTP calls (where N = number of suppliers in the L1 category). The Org Layer's `compliant-suppliers` analytics endpoint does this in a single query. The rewrite should use that instead.

---

## 14. Environment Variables

| Variable | Default | Used By |
|----------|---------|---------|
| `ORGANISATIONAL_LAYER_URL` | `http://organisational-layer:8000` (Docker) / `http://3.68.96.236:8000` (scripts fallback) | App config + all scripts |
| `ANTHROPIC_API_KEY` | *(none — required)* | 4 LLM scripts via `anthropic.Anthropic()` |

The app reads `ORGANISATIONAL_LAYER_URL` via Pydantic Settings (`app/config.py`). Scripts read it via `os.environ.get()` with the hardcoded IP fallback.

---

## 15. Dockerfile and Dependencies

### Dockerfile

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY scripts/ ./scripts/
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Uses Python 3.14-slim. The rewrite may want to verify this image is stable.

### requirements.txt

```
fastapi[standard]
uvicorn[standard]
httpx
pydantic-settings
python-dotenv
anthropic
```

Minimal and correct. The `[standard]` extras for fastapi and uvicorn include useful defaults (e.g., uvloop, httptools).

---

## 16. What Should Change in the Rewrite

### Eliminate script/app duality
One clean Python package. No stdin/stdout modes, no CLI file-based modes. Just importable async functions.

### Single HTTP client
All Org Layer calls through one async `httpx.AsyncClient` instance. No `urllib`, no hardcoded IPs. Pass the client as a dependency.

### Use the mega-endpoint
`GET /api/analytics/request-overview/{id}` returns most of what the pipeline needs in one call. Use it as the primary data source, then make targeted follow-up calls only for what's missing (e.g., specific pricing lookups per supplier).

### Centralize data normalization
One module with helpers for:
- `normalize_delivery_countries(raw)` — handles both formats
- `normalize_scenario_tags(raw)` — handles both formats
- `coerce_budget(val)` → `float | None`
- `coerce_quantity(val)` → `int | None`
- `country_to_region(country_code)` — single COUNTRY_TO_REGION dict

### Structured LLM output
Use Anthropic's tool_use or JSON mode for structured output instead of free-text parsing. Define Pydantic models for expected LLM output and validate against them.

### Proper error handling
- Log LLM failures with the raw response text
- Add retry logic for transient Org Layer errors (with exponential backoff)
- Return structured errors, not just fallback values

### Type-safe pipeline
Define Pydantic models for the input/output of every pipeline step. This catches field name mismatches at development time instead of runtime.

### Parallelism
Steps that don't depend on each other can run concurrently:
- After compliance check: ranking + policy evaluation could overlap
- Escalation check could run in parallel with other post-validation steps

### Reuse Anthropic client
Create one `anthropic.Anthropic()` (or `anthropic.AsyncAnthropic()`) at service startup and share it across all LLM calls.

### Better audit trail
Include the `request-overview` endpoint data in the audit trail. Reference specific pricing tier IDs, not just descriptions. Record which LLM model was used and whether any LLM calls fell back to deterministic mode.

---

## 17. Key System Prompts to Preserve

### Validation prompt (from validateRequest.py)

Core rules that worked well:
- Only two issue types: `missing_info` and `contradictory`
- Explicit list of what IS a contradiction (quantity, budget, date, currency, category)
- Explicit list of what is NOT a contradiction (preferred vs incumbent supplier, urgency, policy concerns)
- Conservative: "when in doubt, do NOT flag"
- Handles multi-language `request_text`
- Extracts `requester_instruction` as a side output

### Recommendation prompt (from generateRecommendation.py)

Core rules:
- Receives status, escalations, ranked suppliers, validation issues, interpretation
- Must reference exact supplier names, prices, rule IDs
- Professional, audit-ready language
- Outputs `reason` and `preferred_supplier_rationale`

### Enrichment prompt (from assembleOutput.py)

Core rules:
- Converts validation issues to enriched form with severity levels (critical/high/medium/low)
- Adds specific numbers from ranked suppliers and policy evaluation
- Generates per-supplier recommendation notes with comparisons
- References exact figures (prices, lead times, quality scores)

---

## 18. Challenge Data Quirks (from CLAUDE.md)

These are critical to remember:

1. **Inconsistent policy schema**: EUR/CHF vs USD key names — the Org Layer normalizes this
2. **Supplier rows are per-category**: SUP-0001 appears 5 times. Join on `(supplier_id, category_l1, category_l2)`
3. **`is_restricted` is unreliable**: Always check the Org Layer's `check-restricted` endpoint
4. **Quantity can be null or contradictory**: Handle gracefully
5. **Non-English requests**: Languages include en, fr, de, es, pt, ja
6. **124 requests have no historical awards**: This is intentional
7. **`service_regions` is semicolon-delimited**: Not comma-delimited. Split on `;`

---

## 19. Judging Criteria Priorities

| Criteria | Weight | Implication for rewrite |
|----------|--------|------------------------|
| Robustness & Escalation Logic | 25% | Correct escalation handling is paramount. Better to escalate than guess. |
| Feasibility | 25% | Clean architecture, production-grade code. The rewrite should be cleaner than v1. |
| Reachability | 20% | Must solve the actual procurement problem end-to-end. |
| Creativity | 20% | Confidence scoring, historical pattern context, interactive clarification. |
| Visual Design | 10% | Frontend is already built. Focus on data quality feeding the UI. |

Key insight: "A system that produces confident wrong answers will score lower than one that correctly identifies uncertainty and escalates."
