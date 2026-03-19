# Scripts Documentation

Both scripts expose their core logic as **importable Python functions** and support **stdin/stdout JSON** for easy API integration, while remaining backward-compatible with the original file-based CLI mode.

## Integration Patterns

### 1. Import as a module (recommended for FastAPI / in-process)

```python
from scripts.filterCompaniesByProduct import filter_suppliers
from scripts.rankCompanies import rank_suppliers

# Step 1: filter
filter_result = filter_suppliers(request_data)   # dict in → dict out

# Step 2: rank
rank_result = rank_suppliers(request_data, filter_result["suppliers"])  # dicts in → dict out
```

### 2. Subprocess with stdin/stdout (for process isolation)

```python
import subprocess, json

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

### 3. Original file-based CLI (still works)

```bash
python3 scripts/filterCompaniesByProduct.py request.json suppliers.json
python3 scripts/rankCompanies.py request.json suppliers.json ranked.json
```

---

## filterCompaniesByProduct.py

Filters suppliers from the ChainIQ database to only those serving the same product category as a given purchase request.

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

None -- uses only Python standard library (`json`, `sys`, `urllib`).

### API

Queries the ChainIQ Organisational Layer API at `http://3.68.96.236:8000`. See `DATABASE_BACKEND_API.md` for full endpoint documentation.

---

## rankCompanies.py

Ranks filtered suppliers by computing a "true cost" -- the effective price inflated by quality gaps and risk exposure. The score answers: "how much am I really paying once I account for imperfect quality and risk?"

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

None -- uses only Python standard library (`json`, `sys`, `urllib`).

### API

Queries the ChainIQ Organisational Layer API at `http://3.68.96.236:8000`. See `DATABASE_BACKEND_API.md` for full endpoint documentation.
