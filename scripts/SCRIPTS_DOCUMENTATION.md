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
