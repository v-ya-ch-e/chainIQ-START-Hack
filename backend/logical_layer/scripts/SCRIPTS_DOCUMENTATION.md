# Scripts Documentation

All scripts expose their core logic as **importable Python functions** and support **stdin/stdout JSON** for easy API integration, while remaining backward-compatible with the original file-based CLI mode.

They are also exposed as **HTTP endpoints** through the Logical Layer FastAPI service.

## Configuration

The filter and rank scripts read the Organisational Layer base URL from the `ORGANISATIONAL_LAYER_URL` environment variable, falling back to `http://3.68.96.236:8000` if unset.

```bash
# Override for local development
export ORGANISATIONAL_LAYER_URL=http://localhost:8000

# In Docker (set via .env or docker-compose env_file)
ORGANISATIONAL_LAYER_URL=http://organisational-layer:8000
```

The validate script requires the `ANTHROPIC_API_KEY` environment variable for LLM-powered checks. It also loads variables from the `.env` file in the `backend/logical_layer/` directory via `python-dotenv`.

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

# Step 3: rank (pass the suppliers array from step 2)
curl -X POST http://localhost:8080/api/rank-suppliers \
  -H "Content-Type: application/json" \
  -d '{
    "request": {"category_l1": "IT", "category_l2": "Hardware", "quantity": 50},
    "suppliers": [ ... ]
  }'
```

Full Swagger documentation is available at `http://localhost:8080/docs`.

### 2. Import as a module (for in-process Python use)

```python
from scripts.validateRequest import validate_request
from scripts.filterCompaniesByProduct import filter_suppliers
from scripts.rankCompanies import rank_suppliers

# Step 1: validate
validation = validate_request(request_data)  # dict in -> dict out

# Step 2: filter
filter_result = filter_suppliers(request_data)   # dict in -> dict out

# Step 3: rank
rank_result = rank_suppliers(request_data, filter_result["suppliers"])  # dicts in -> dict out
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

# rankCompanies
proc = subprocess.run(
    ["python3", "scripts/rankCompanies.py"],
    input=json.dumps({"request": request_data, "suppliers": filter_result["suppliers"]}),
    capture_output=True, text=True,
)
rank_result = json.loads(proc.stdout)
```

### 4. Original file-based CLI (still works)

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

**Input** — a purchase request dict (same structure as `examples/example_request.json`). Required keys: `category_l1`, `category_l2`.

**Output:**

```json
{
  "suppliers": [ ...supplier_category rows... ],
  "category_l1": "IT",
  "category_l2": "Hardware",
  "count": 5
}
```

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"category_l1":"IT","category_l2":"Hardware"}' \| python3 scripts/filterCompaniesByProduct.py` |
| File-based | `python3 scripts/filterCompaniesByProduct.py <input_request.json> <output_suppliers.json>` |

### How It Works

1. Reads `category_l1` and `category_l2` from the input request.
2. Queries `GET /api/categories` to resolve the matching integer `category_id`.
3. Queries `GET /api/suppliers?category_l1={category_l1}` to get all suppliers serving that L1 category.
4. For each supplier, queries `GET /api/suppliers/{supplier_id}/categories` to retrieve their per-category rows.
5. Keeps only rows where `category_id` matches the exact L1+L2 combination from the request.

### Supplier Fields (inside `suppliers` array)

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `supplier_id` | string | Supplier ID (e.g. `SUP-0001`) |
| `category_id` | int | FK to `categories.id` |
| `pricing_model` | string | e.g. `tiered`, `per_unit` |
| `quality_score` | int | 0-100, higher is better |
| `risk_score` | int | 0-100, lower is better |
| `esg_score` | int | 0-100, higher is better |
| `preferred_supplier` | bool | Whether preferred for this category |
| `is_restricted` | bool | Hint only -- cross-reference `restricted_suppliers_policy` |
| `restriction_reason` | string/null | Reason if restricted |
| `data_residency_supported` | bool | Whether supplier supports in-country data residency |
| `notes` | string/null | Additional notes |

### Dependencies

None -- uses only Python standard library (`json`, `os`, `sys`, `urllib`).

### API

Queries the ChainIQ Organisational Layer API. URL is configurable via the `ORGANISATIONAL_LAYER_URL` environment variable (default: `http://3.68.96.236:8000`). See `DATABASE_BACKEND_API.md` for full endpoint documentation.

---

## rankCompanies.py

Ranks filtered suppliers by computing a "true cost" -- the effective price inflated by quality gaps and risk exposure. The score answers: "how much am I really paying once I account for imperfect quality and risk?"

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
  "suppliers": [ ...supplier rows from filter-suppliers... ]
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

**Input:**
- `request_data` — purchase request dict. Required keys: `category_l1`, `category_l2`. Optional: `quantity`, `esg_requirement`, `delivery_countries`, `country`.
- `suppliers` — list of supplier dicts (the `suppliers` array from `filter_suppliers()` output).

**Output:**

```json
{
  "ranked": [ ...ranked supplier rows... ],
  "category_l1": "IT",
  "category_l2": "Hardware",
  "count": 5
}
```

### CLI Usage

| Mode | Command |
|------|---------|
| stdin/stdout | `echo '{"request": {...}, "suppliers": [...]}' \| python3 scripts/rankCompanies.py` |
| File-based | `python3 scripts/rankCompanies.py <request.json> <suppliers.json> <output.json>` |

When using stdin/stdout, the input JSON must have two top-level keys: `"request"` and `"suppliers"`.

### How It Works

1. Reads category, quantity, delivery countries, and `esg_requirement` from the request.
2. Maps the delivery country to a pricing region (EU, CH, Americas, APAC, MEA).
3. For each supplier, calls `GET /api/analytics/pricing-lookup` to get `total_price`, `unit_price`, and lead times. Suppliers with no matching pricing tier are excluded.
4. Computes the true cost and overpayment for each supplier.
5. Sorts by `true_cost` ascending (lowest effective cost first) and assigns ranks.

### Scoring Function

**When `esg_requirement` is false:**

```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100)
```

**When `esg_requirement` is true:**

```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100) / (esg_score / 100)
```

Lower `true_cost` = better deal. The score is in currency units and represents the effective price once you factor in the hidden costs of imperfect quality and risk exposure. The `overpayment` field (`true_cost - total_price`) shows how much extra you're effectively paying. ESG is only factored in when the request requires it.

### Ranked Supplier Fields (inside `ranked` array)

| Field | Type | Description |
|-------|------|-------------|
| `rank` | int | Position in ranking (1 = best) |
| `supplier_id` | string | Supplier ID |
| `true_cost` | float/null | Effective price adjusted for quality/risk/ESG |
| `overpayment` | float/null | Hidden cost: `true_cost - total_price` |
| `quality_score` | int | Raw quality score (0-100) |
| `risk_score` | int | Raw risk score (0-100, lower is better) |
| `esg_score` | int | Raw ESG score (0-100) |
| `total_price` | float/null | Total order cost from pricing API |
| `unit_price` | float/null | Per-unit price |
| `currency` | string/null | Pricing currency |
| `standard_lead_time_days` | int/null | Standard delivery lead time |
| `expedited_lead_time_days` | int/null | Expedited delivery lead time |
| `preferred_supplier` | bool | Whether preferred for this category |
| `is_restricted` | bool | Restriction hint flag |

When `quantity` is null in the request, pricing is skipped and suppliers are sorted by `quality_score` descending instead.

### Dependencies

None -- uses only Python standard library (`json`, `os`, `sys`, `urllib`).

### API

Queries the ChainIQ Organisational Layer API. URL is configurable via the `ORGANISATIONAL_LAYER_URL` environment variable (default: `http://3.68.96.236:8000`). See `DATABASE_BACKEND_API.md` for full endpoint documentation.
