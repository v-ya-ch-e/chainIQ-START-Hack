# Scripts Documentation

## filterCompaniesByProduct.py

Filters suppliers from the ChainIQ database to only those serving the same product category as a given purchase request.

### Usage

```bash
python3 scripts/filterCompaniesByProduct.py <input_request.json> <output_suppliers.json>
```

| Argument | Description |
|----------|-------------|
| `input_request.json` | Path to a purchase request JSON file (same structure as `examples/example_request.json`) |
| `output_suppliers.json` | Path where the filtered supplier list will be written |

### How It Works

1. Reads `category_l1` and `category_l2` from the input request.
2. Queries `GET /api/categories` to resolve the matching integer `category_id`.
3. Queries `GET /api/suppliers?category_l1={category_l1}` to get all suppliers serving that L1 category.
4. For each supplier, queries `GET /api/suppliers/{supplier_id}/categories` to retrieve their per-category rows.
5. Keeps only rows where `category_id` matches the exact L1+L2 combination from the request.
6. Writes the filtered rows to the output file.

### Output Format

A JSON array of `supplier_categories` rows (database schema 1.3). Each element has the following fields:

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

### Example

```bash
python3 scripts/filterCompaniesByProduct.py examples/example_request.json output.json
```

This reads the example request (IT / Docking Stations) and writes the matching suppliers to `output.json`.

### Dependencies

None -- uses only Python standard library (`json`, `sys`, `urllib`).

### API

Queries the ChainIQ Organisational Layer API at `http://18.197.20.103:8000`. See `DATABASE_BACKEND_API.md` for full endpoint documentation.

---

## rankCompanies.py

Ranks filtered suppliers by computing a "true cost" -- the effective price inflated by quality gaps and risk exposure. The score answers: "how much am I really paying once I account for imperfect quality and risk?"

### Usage

```bash
python3 scripts/rankCompanies.py <request.json> <suppliers.json> <output.json>
```

| Argument | Description |
|----------|-------------|
| `request.json` | Path to a purchase request JSON file (same structure as `examples/example_request.json`) |
| `suppliers.json` | Path to the filtered supplier list (output of `filterCompaniesByProduct.py`) |
| `output.json` | Path where the ranked results will be written |

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

### Output Format

A JSON array sorted by `true_cost` ascending, each element containing:

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

### Example

```bash
python3 scripts/filterCompaniesByProduct.py examples/example_request.json /tmp/suppliers.json
python3 scripts/rankCompanies.py examples/example_request.json /tmp/suppliers.json /tmp/ranked.json
```

### Dependencies

None -- uses only Python standard library (`json`, `sys`, `urllib`).

### API

Queries the ChainIQ Organisational Layer API at `http://18.197.20.103:8000`. See `DATABASE_BACKEND_API.md` for full endpoint documentation.
