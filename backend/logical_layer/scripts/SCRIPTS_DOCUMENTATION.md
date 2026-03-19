# Scripts Documentation

All scripts expose their core logic as **importable Python functions** and support **stdin/stdout JSON** for easy API integration, while remaining backward-compatible with the original file-based CLI mode.

They are also exposed as **HTTP endpoints** through the Logical Layer FastAPI service.

## Configuration

The filter, rank, check-compliance, evaluate-policy, and check-escalations scripts read the Organisational Layer base URL from the `ORGANISATIONAL_LAYER_URL` environment variable, falling back to `http://3.68.96.236:8000` if unset.

```bash
# Override for local development
export ORGANISATIONAL_LAYER_URL=http://localhost:8000

# In Docker (set via .env or docker-compose env_file)
ORGANISATIONAL_LAYER_URL=http://organisational-layer:8000
```

The validate, generate-recommendation, assemble-output, and format-invalid-response scripts require the `ANTHROPIC_API_KEY` environment variable for LLM-powered checks. They also load variables from the `.env` file in the `backend/logical_layer/` directory via `python-dotenv`.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Integration Patterns

### 1. HTTP API via Logical Layer (recommended for n8n / external callers)

The Logical Layer exposes all scripts as POST endpoints at `http://localhost:8080`.

```bash
# Step 1: validate
curl -X POST http://localhost:8080/api/validate-request \
  -H "Content-Type: application/json" \
  -d '{ "request_id": "REQ-000004", "category_l1": "IT", ... }'

# Step 2: filter
curl -X POST http://localhost:8080/api/filter-suppliers \
  -H "Content-Type: application/json" \
  -d '{"category_l1": "IT", "category_l2": "Hardware"}'

# Step 3: check compliance
curl -X POST http://localhost:8080/api/check-compliance \
  -H "Content-Type: application/json" \
  -d '{"request_data": {...}, "suppliers": [...]}'

# Step 4: rank (pass compliant suppliers from step 3)
curl -X POST http://localhost:8080/api/rank-suppliers \
  -H "Content-Type: application/json" \
  -d '{"request": {...}, "suppliers": [...]}'

# Step 5: evaluate policy
curl -X POST http://localhost:8080/api/evaluate-policy \
  -H "Content-Type: application/json" \
  -d '{"request_data": {...}, "ranked_suppliers": [...], "non_compliant_suppliers": [...]}'

# Step 6: check escalations
curl -X POST http://localhost:8080/api/check-escalations \
  -H "Content-Type: application/json" \
  -d '{"request_id": "REQ-000004"}'

# Step 7: generate recommendation
curl -X POST http://localhost:8080/api/generate-recommendation \
  -H "Content-Type: application/json" \
  -d '{"escalations": [...], "ranked_suppliers": [...], "validation": {...}, "request_interpretation": {...}}'

# Step 8: assemble output
curl -X POST http://localhost:8080/api/assemble-output \
  -H "Content-Type: application/json" \
  -d '{"request_id": "...", "validation": {...}, ...}'

# Or run the full pipeline in one call:
curl -X POST http://localhost:8080/api/processRequest \
  -H "Content-Type: application/json" \
  -d '{"request_id": "REQ-000004"}'
```

Full Swagger documentation is available at `http://localhost:8080/docs`.

### 2. Import as a module (for in-process Python use)

```python
from scripts.validateRequest import validate_request
from scripts.filterCompaniesByProduct import filter_suppliers
from scripts.checkCompliance import check_compliance
from scripts.rankCompanies import rank_suppliers
from scripts.evaluatePolicy import evaluate_policy
from scripts.checkEscalations import check_escalations
from scripts.generateRecommendation import generate_recommendation
from scripts.assembleOutput import assemble_output

# Step 1: validate
validation = validate_request(request_data)

# Step 2: filter
filter_result = filter_suppliers(request_data)

# Step 3: check compliance
compliance = check_compliance(request_data, filter_result["suppliers"])

# Step 4: rank
rank_result = rank_suppliers(request_data, compliance["compliant"])

# Step 5: evaluate policy
policy = evaluate_policy(request_data, rank_result["ranked"], compliance["non_compliant"])

# Step 6: check escalations
escalations = check_escalations("REQ-000004")

# Step 7: generate recommendation
recommendation = generate_recommendation({
    "escalations": escalations["escalations"],
    "ranked_suppliers": rank_result["ranked"],
    "validation": validation,
    "request_interpretation": validation["request_interpretation"],
})

# Step 8: assemble output
output = assemble_output({
    "request_id": "REQ-000004",
    "validation": validation,
    "request_interpretation": validation["request_interpretation"],
    "ranked_suppliers": rank_result["ranked"],
    "non_compliant_suppliers": compliance["non_compliant"],
    "policy_evaluation": policy,
    "escalations": escalations["escalations"],
    "recommendation": recommendation,
})
```

### 3. Subprocess with stdin/stdout (for process isolation)

```python
import subprocess, json

# validateRequest
proc = subprocess.run(
    ["python3", "scripts/validateRequest.py"],
    input=json.dumps(request_data),
    capture_output=True, text=True,
)
validation = json.loads(proc.stdout)

# filterCompaniesByProduct
proc = subprocess.run(
    ["python3", "scripts/filterCompaniesByProduct.py"],
    input=json.dumps(request_data),
    capture_output=True, text=True,
)
filter_result = json.loads(proc.stdout)

# checkCompliance
proc = subprocess.run(
    ["python3", "scripts/checkCompliance.py"],
    input=json.dumps({"request_data": request_data, "suppliers": filter_result["suppliers"]}),
    capture_output=True, text=True,
)
compliance = json.loads(proc.stdout)

# rankCompanies
proc = subprocess.run(
    ["python3", "scripts/rankCompanies.py"],
    input=json.dumps({"request": request_data, "suppliers": compliance["compliant"]}),
    capture_output=True, text=True,
)
rank_result = json.loads(proc.stdout)
```

### 4. Original file-based CLI (still works for validate, filter, rank)

```bash
python3 scripts/validateRequest.py request.json validation_output.json
python3 scripts/filterCompaniesByProduct.py request.json suppliers.json
python3 scripts/rankCompanies.py request.json suppliers.json ranked.json
```

---

## validateRequest.py

Validates a purchase request for completeness and internal consistency. Uses deterministic checks for required/optional fields and the Anthropic API (Claude) to detect discrepancies between the free-text `request_text` and the structured fields.

### HTTP Endpoint

`POST /api/validate-request`

**Request body:** A full purchase request JSON object (same structure as `examples/example_request.json`). All fields are accepted; the script checks which required/optional fields are present.

**Response:**
```json
{
  "completeness": false,
  "issues": [
    {
      "field": "quantity",
      "type": "missing_optional",
      "message": "Field 'quantity' is missing or null — request is incomplete."
    },
    {
      "field": "budget_amount",
      "type": "contradictory",
      "message": "Text says '50,000 EUR' but budget_amount is 30000."
    }
  ],
  "request_interpretation": {
    "category_l1": "IT",
    "category_l2": "Hardware",
    "quantity": null,
    "unit_of_measure": null,
    "budget_amount": 30000,
    "currency": "EUR",
    "delivery_country": "DE",
    "required_by_date": "2026-06-01",
    "days_until_required": 74,
    "data_residency_required": false,
    "esg_requirement": false,
    "preferred_supplier_stated": null,
    "incumbent_supplier": null,
    "requester_instruction": "must use Dell"
  }
}
```

**Error responses:** `400` if the input cannot be processed. `502` if the Anthropic API is unreachable or returns an error.

### Function API

```python
validate_request(request_data: dict) -> dict
```

**Input** — a purchase request dict (same structure as `examples/example_request.json`).

**Output:** `{ "completeness": bool, "issues": [...], "request_interpretation": {...} }`

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{ ... }' \| python3 scripts/validateRequest.py` |
| File (stdout) | `python3 scripts/validateRequest.py request.json` |
| File (output) | `python3 scripts/validateRequest.py request.json output.json` |

### How It Works

1. **Deterministic checks** — Verifies required fields (`request_id`, `created_at`, `request_channel`, `request_language`, `business_unit`, `country`, `category_l1`, `category_l2`, `title`, `request_text`, `currency`, `status`) are present and non-null. Checks completeness fields (`quantity`, `budget_amount`, `required_by_date`, `unit_of_measure`, `delivery_countries`) for presence.
2. **LLM checks** — Sends the full request JSON to Claude (claude-sonnet-4-6) with a system prompt that instructs it to find only major issues: `missing_info` (critical fields missing or text mentions info with no structured field) and `contradictory` (text clearly contradicts a structured field value). The LLM also extracts any explicit requester instruction from the free text.
3. **Interpretation** — Builds a structured interpretation of the request fields, including computed `days_until_required` and the LLM-extracted `requester_instruction`.
4. **Result** — Merges deterministic and LLM issues. `completeness` is `true` only if zero issues are found.

### Issue Types

| Type | Source | Description |
|------|--------|-------------|
| `missing_required` | Deterministic | A required field is missing or null |
| `missing_optional` | Deterministic | A completeness field is missing or null |
| `missing_info` | LLM | Text mentions info with no corresponding structured field |
| `contradictory` | LLM | Text clearly contradicts a structured field value |

### Dependencies

- `anthropic` — Anthropic Python SDK
- `python-dotenv` — Loads `.env` file for API key
- Requires `ANTHROPIC_API_KEY` environment variable

---

## filterCompaniesByProduct.py

Filters suppliers from the ChainIQ database to only those serving the same product category as a given purchase request.

### HTTP Endpoint

`POST /api/filter-suppliers`

**Request body:** JSON object with at least `category_l1` and `category_l2`. Extra fields are allowed and ignored.

**Response:**
```json
{
  "suppliers": [ ...supplier_category rows... ],
  "category_l1": "IT",
  "category_l2": "Hardware",
  "count": 5
}
```

**Error responses:** `400` if category_l1/category_l2 are missing or the category is not found. `502` if the Organisational Layer is unreachable.

### Function API

```python
filter_suppliers(request_data: dict) -> dict
```

**Input** — a purchase request dict. Required keys: `category_l1`, `category_l2`.

**Output:** `{ "suppliers": [...], "category_l1": "...", "category_l2": "...", "count": N }`

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"category_l1":"IT","category_l2":"Hardware"}' \| python3 scripts/filterCompaniesByProduct.py` |
| File-based | `python3 scripts/filterCompaniesByProduct.py <input_request.json> <output_suppliers.json>` |

### Dependencies

None -- uses only Python standard library (`json`, `os`, `sys`, `urllib`).

---

## checkCompliance.py

Checks each supplier from the filter step against compliance rules. Splits suppliers into compliant and non-compliant lists with reasons.

### HTTP Endpoint

`POST /api/check-compliance`

**Request body:**
```json
{
  "request_data": {
    "category_l1": "IT",
    "category_l2": "Docking Stations",
    "delivery_countries": ["DE"],
    "currency": "EUR",
    "budget_amount": 25199.55,
    "data_residency_constraint": false
  },
  "suppliers": [ ...from filter step... ]
}
```

**Response:**
```json
{
  "compliant": [
    { "supplier_id": "SUP-0001", "compliance_notes": "Passes all compliance checks", ... }
  ],
  "non_compliant": [
    { "supplier_id": "SUP-0008", "exclusion_reason": "Restricted: ...", ... }
  ],
  "total_checked": 5,
  "compliant_count": 4,
  "non_compliant_count": 1
}
```

**Error responses:** `400` if missing category fields. `502` if Org Layer unreachable.

### Function API

```python
check_compliance(request_data: dict, suppliers: list) -> dict
```

**Input:**
- `request_data` — purchase request dict with at least `category_l1`, `category_l2`, `delivery_countries`
- `suppliers` — list of supplier dicts from the filter step

**Output:** `{ "compliant": [...], "non_compliant": [...], "total_checked": N, "compliant_count": N, "non_compliant_count": N }`

### How It Works

1. Fetches the list of compliant suppliers for the category + delivery country from the Org Layer.
2. For each supplier, checks:
   - Is the supplier in the compliant list (covers delivery country)?
   - Is the supplier restricted for this category/country (via check-restricted endpoint)?
   - Does the supplier support data residency if required?
3. Suppliers passing all checks go to `compliant`; others go to `non_compliant` with a reason.

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"request_data": {...}, "suppliers": [...]}' \| python3 scripts/checkCompliance.py` |

### Dependencies

None -- uses only Python standard library (`json`, `os`, `sys`, `urllib`).

---

## rankCompanies.py

Ranks filtered suppliers by computing a "true cost" -- the effective price inflated by quality gaps and risk exposure.

### HTTP Endpoint

`POST /api/rank-suppliers`

**Request body:**
```json
{
  "request": {
    "category_l1": "IT",
    "category_l2": "Hardware",
    "quantity": 50,
    "esg_requirement": false,
    "delivery_countries": ["DE"]
  },
  "suppliers": [ ...supplier rows from filter or check-compliance compliant list... ]
}
```

**Response:**
```json
{
  "ranked": [ ...ranked supplier rows... ],
  "category_l1": "IT",
  "category_l2": "Hardware",
  "count": 5
}
```

**Error responses:** `400` if required fields are missing. `502` if the Organisational Layer is unreachable.

### Function API

```python
rank_suppliers(request_data: dict, suppliers: list) -> dict
```

### Scoring Function

```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100)
```

When `esg_requirement` is true: `/ (esg_score / 100)`.

Lower `true_cost` = better deal. When `quantity` is null, suppliers are sorted by `quality_score` descending.

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"request": {...}, "suppliers": [...]}' \| python3 scripts/rankCompanies.py` |
| File-based | `python3 scripts/rankCompanies.py <request.json> <suppliers.json> <output.json>` |

### Dependencies

None -- uses only Python standard library (`json`, `os`, `sys`, `urllib`).

---

## evaluatePolicy.py

Evaluates procurement policies for the overall request: approval threshold, preferred supplier analysis, restriction checks, and applicable category/geography rules.

### HTTP Endpoint

`POST /api/evaluate-policy`

**Request body:**
```json
{
  "request_data": { ... full request object ... },
  "ranked_suppliers": [ ... from rank step ... ],
  "non_compliant_suppliers": [ ... from compliance check ... ]
}
```

**Response:**
```json
{
  "approval_threshold": {
    "rule_applied": "AT-002",
    "basis": "Contract value of EUR 25199.55 falls in threshold AT-002...",
    "quotes_required": 2,
    "approvers": ["business", "procurement"],
    "deviation_approval": "Procurement Manager",
    "note": null
  },
  "preferred_supplier": {
    "supplier": "Dell Enterprise Europe",
    "status": "eligible",
    "is_preferred": true,
    "covers_delivery_country": true,
    "is_restricted": false,
    "policy_note": "..."
  },
  "restricted_suppliers": { ... },
  "category_rules_applied": [],
  "geography_rules_applied": []
}
```

### Function API

```python
evaluate_policy(request_data: dict, ranked_suppliers: list, non_compliant_suppliers: list) -> dict
```

### How It Works

1. Determines the approval threshold by calling `GET /api/analytics/approval-tier` with the request's currency and budget amount.
2. Checks preferred supplier status via `GET /api/analytics/check-preferred`.
3. Checks restriction status for each evaluated supplier via `GET /api/analytics/check-restricted`.
4. Fetches applicable rules via `GET /api/analytics/applicable-rules`.

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"request_data": {...}, "ranked_suppliers": [...], "non_compliant_suppliers": [...]}' \| python3 scripts/evaluatePolicy.py` |

### Dependencies

None -- uses only Python standard library (`json`, `os`, `sys`, `urllib`).

---

## checkEscalations.py

Fetches computed escalations from the Organisational Layer's escalation engine (ER-001 through ER-008 + AT threshold conflict detection).

### HTTP Endpoint

`POST /api/check-escalations`

**Request body:** `{ "request_id": "REQ-000004" }`

**Response:**
```json
{
  "request_id": "REQ-000004",
  "escalations": [
    {
      "escalation_id": "ESC-001",
      "rule": "ER-001",
      "rule_label": "Missing Required Information",
      "trigger": "Budget is insufficient...",
      "escalate_to": "Requester Clarification",
      "blocking": true,
      "status": "open"
    }
  ],
  "has_blocking": true,
  "count": 3
}
```

### Function API

```python
check_escalations(request_id: str) -> dict
```

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"request_id": "REQ-000004"}' \| python3 scripts/checkEscalations.py` |
| Direct arg | `python3 scripts/checkEscalations.py REQ-000004` |

### Dependencies

None -- uses only Python standard library (`json`, `os`, `sys`, `urllib`).

---

## generateRecommendation.py

Generates a procurement recommendation based on escalations, ranked suppliers, and validation results. Uses deterministic logic for status determination and Claude LLM for human-readable reasoning.

### HTTP Endpoint

`POST /api/generate-recommendation`

**Request body:**
```json
{
  "escalations": [ ... from check-escalations ... ],
  "ranked_suppliers": [ ... from rank step ... ],
  "validation": { ... from validate step ... },
  "request_interpretation": { ... from validate step ... }
}
```

**Response:**
```json
{
  "status": "cannot_proceed",
  "reason": "Three blocking issues prevent autonomous award...",
  "preferred_supplier_if_resolved": "Bechtle Workplace Solutions",
  "preferred_supplier_rationale": "Bechtle is the incumbent and lowest-cost option at EUR 35,712.",
  "minimum_budget_required": 35712.00,
  "minimum_budget_currency": "EUR"
}
```

### Function API

```python
generate_recommendation(data: dict) -> dict
```

### How It Works

1. **Status determination** (deterministic):
   - Any blocking escalation → `cannot_proceed`
   - Non-blocking escalations exist → `proceed_with_conditions`
   - No escalations → `proceed`
2. **Budget calculation:** Finds minimum total price across ranked suppliers.
3. **Preferred supplier:** Matches the requester's stated preference or incumbent against ranked suppliers.
4. **LLM reasoning:** Uses Claude to generate human-readable `reason` and `preferred_supplier_rationale`.

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"escalations": [...], "ranked_suppliers": [...], ...}' \| python3 scripts/generateRecommendation.py` |

### Dependencies

- `anthropic` — Anthropic Python SDK
- `python-dotenv` — Loads `.env` file for API key
- Requires `ANTHROPIC_API_KEY` environment variable

---

## assembleOutput.py

Combines all pipeline step outputs into the final output format matching `example_output.json`. Uses Claude LLM to enrich validation issues with severity/action_required and supplier shortlist entries with recommendation notes.

### HTTP Endpoint

`POST /api/assemble-output`

**Request body:** All pipeline step outputs combined into a single object (see `AssembleOutputRequest` schema).

**Response:** Complete pipeline output with all 8 sections: `request_interpretation`, `validation`, `policy_evaluation`, `supplier_shortlist`, `suppliers_excluded`, `escalations`, `recommendation`, `audit_trail`.

### Function API

```python
assemble_output(pipeline_data: dict) -> dict
```

### How It Works

1. **LLM enrichment:** Sends pipeline context to Claude to get enriched validation issues (with severity, action_required) and supplier recommendation notes.
2. **Validation section:** Converts raw issues to enriched format with issue_id, severity, type, description, action_required.
3. **Supplier shortlist:** Builds from ranked suppliers with recommendation notes, preferred/incumbent flags, pricing details.
4. **Suppliers excluded:** Builds from non-compliant suppliers with exclusion reasons.
5. **Escalations:** Formats escalation data with escalation_id, rule, trigger, escalate_to, blocking.
6. **Audit trail:** Collects all policy IDs checked, supplier IDs evaluated, pricing tiers, data sources, historical context.

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"request_id": "...", ...}' \| python3 scripts/assembleOutput.py` |

### Dependencies

- `anthropic` — Anthropic Python SDK
- `python-dotenv` — Loads `.env` file for API key
- Requires `ANTHROPIC_API_KEY` environment variable

---

## formatInvalidResponse.py

Formats a structured response for invalid/incomplete purchase requests. Used on the "Invalid request" branch of the n8n pipeline.

### HTTP Endpoint

`POST /api/format-invalid-response`

**Request body:**
```json
{
  "request_data": { ... full request object ... },
  "validation": { "completeness": false, "issues": [...] },
  "request_interpretation": { ... from validate step ... }
}
```

**Response:**
```json
{
  "request_id": "REQ-000004",
  "processed_at": "2026-03-14T18:02:11Z",
  "status": "invalid",
  "validation": { "completeness": "fail", "issues_detected": [...] },
  "request_interpretation": { ... },
  "escalations": [ ... ],
  "recommendation": { "status": "cannot_proceed", "reason": "..." },
  "summary": "Human-readable summary of validation failures"
}
```

### Function API

```python
format_invalid_response(request_data: dict, validation: dict, interpretation: dict) -> dict
```

### How It Works

1. Uses Claude LLM to generate enriched issue descriptions and a human-readable summary.
2. Adds ER-001 escalation if required fields are missing.
3. Sets recommendation status to `cannot_proceed`.

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"request_data": {...}, "validation": {...}, "request_interpretation": {...}}' \| python3 scripts/formatInvalidResponse.py` |

### Dependencies

- `anthropic` — Anthropic Python SDK
- `python-dotenv` — Loads `.env` file for API key
- Requires `ANTHROPIC_API_KEY` environment variable
