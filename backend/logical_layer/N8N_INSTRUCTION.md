# n8n Integration Instructions

This document describes how to call the Logical Layer API from n8n workflows. The API base URL is `http://logical-layer:8080` (Docker internal) or `http://localhost:8080` (local dev).

Swagger UI with interactive docs is available at `http://localhost:8080/docs`.

## Pipeline Overview

The typical n8n workflow calls three endpoints in sequence:

```
1. Validate   ──→  POST /api/validate-request
2. Filter     ──→  POST /api/filter-suppliers
3. Rank       ──→  POST /api/rank-suppliers
```

Each step is independent -- you can use them individually or chain them together. The output of step 2 feeds into step 3.

There is also a stub endpoint `POST /api/processRequest` reserved for the future full pipeline.

---

## Endpoints

### 1. POST /api/validate-request

Validates a purchase request for completeness and internal consistency. Runs deterministic field checks and uses Claude (Anthropic LLM) to detect contradictions between the free-text `request_text` and the structured fields.

#### Input

Send the **full purchase request object** as the JSON body. All fields are accepted. The more fields you provide, the better the validation.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/validate-request` |
| Body Content Type | JSON |
| Body | The full purchase request object |

**Example request body:**

```json
{
  "request_id": "REQ-000004",
  "created_at": "2026-03-14T17:55:00Z",
  "request_channel": "teams",
  "request_language": "en",
  "business_unit": "Digital Workplace",
  "country": "DE",
  "site": "Berlin",
  "requester_id": "USR-3004",
  "requester_role": "Workplace Lead",
  "submitted_for_id": "USR-8004",
  "category_l1": "IT",
  "category_l2": "Docking Stations",
  "title": "Docking station purchase",
  "request_text": "Need 240 docking stations matching existing laptop fleet. Must be delivered by 2026-03-20 with premium specification. Budget capped at 25 199.55 EUR. Please use Dell Enterprise Europe with no exception.",
  "currency": "EUR",
  "budget_amount": 25199.55,
  "quantity": 240,
  "unit_of_measure": "device",
  "required_by_date": "2026-03-20",
  "preferred_supplier_mentioned": "Dell Enterprise Europe",
  "incumbent_supplier": "Bechtle Workplace Solutions",
  "contract_type_requested": "purchase",
  "delivery_countries": ["DE"],
  "data_residency_constraint": false,
  "esg_requirement": false,
  "status": "pending_review"
}
```

#### Output

```json
{
  "completeness": true,
  "issues": [],
  "request_interpretation": {
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
    "requester_instruction": "use Dell Enterprise Europe, no exception"
  }
}
```

**Output fields:**

| Field | Type | Description |
|-------|------|-------------|
| `completeness` | boolean | `true` if zero issues found, `false` otherwise |
| `issues` | array | List of validation issues (see below) |
| `request_interpretation` | object | Structured interpretation of all key request fields |

**Each issue object:**

| Field | Type | Description |
|-------|------|-------------|
| `field` | string or null | The structured field name this issue relates to |
| `type` | string | One of: `missing_required`, `missing_optional`, `missing_info`, `contradictory` |
| `message` | string | Human-readable explanation of the issue |

**Issue types explained:**

| Type | Source | Meaning |
|------|--------|---------|
| `missing_required` | Deterministic | A required field (request_id, created_at, category_l1, etc.) is missing or null |
| `missing_optional` | Deterministic | A completeness field (quantity, budget_amount, required_by_date, etc.) is missing or null |
| `missing_info` | LLM | The request_text mentions information that has no corresponding structured field |
| `contradictory` | LLM | The request_text clearly contradicts a structured field value |

**`request_interpretation` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `category_l1` | string or null | Level-1 category |
| `category_l2` | string or null | Level-2 category |
| `quantity` | number or null | Requested quantity |
| `unit_of_measure` | string or null | Unit of measure |
| `budget_amount` | number or null | Budget amount |
| `currency` | string or null | Currency code |
| `delivery_country` | string or null | Primary delivery country (first from delivery_countries, or fallback to country) |
| `required_by_date` | string or null | Deadline date (YYYY-MM-DD) |
| `days_until_required` | integer or null | Days from created_at to required_by_date |
| `data_residency_required` | boolean | Whether data residency is required |
| `esg_requirement` | boolean | Whether ESG compliance is required |
| `preferred_supplier_stated` | string or null | Supplier the requester prefers |
| `incumbent_supplier` | string or null | Current/existing supplier |
| `requester_instruction` | string or null | Explicit instruction extracted from request_text by LLM (e.g. "must use Dell, no exception") |

#### n8n usage notes

- Use the `request_interpretation` output to feed into subsequent steps (filter + rank).
- Check `completeness` to decide whether to proceed or route to a human review step.
- The `requester_instruction` field is useful for escalation logic downstream.

#### Error responses

| Status | Meaning |
|--------|---------|
| 400 | Invalid input (missing or malformed fields) |
| 502 | Anthropic API error (LLM unavailable or returned an error) |

---

### 2. POST /api/filter-suppliers

Filters all suppliers to only those serving the same product category as the purchase request.

#### Input

Send a JSON object with at least `category_l1` and `category_l2`. Extra fields are accepted and ignored.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/filter-suppliers` |
| Body Content Type | JSON |
| Body | `{ "category_l1": "...", "category_l2": "..." }` |

**Example request body (minimal):**

```json
{
  "category_l1": "IT",
  "category_l2": "Docking Stations"
}
```

You can also pass the full request object -- only `category_l1` and `category_l2` are used:

```json
{
  "category_l1": "IT",
  "category_l2": "Docking Stations",
  "quantity": 240,
  "currency": "EUR"
}
```

#### Output

```json
{
  "suppliers": [
    {
      "id": 5,
      "supplier_id": "SUP-0001",
      "category_id": 5,
      "pricing_model": "tiered",
      "quality_score": 88,
      "risk_score": 15,
      "esg_score": 82,
      "preferred_supplier": true,
      "is_restricted": false,
      "restriction_reason": null,
      "data_residency_supported": true,
      "notes": null
    }
  ],
  "category_l1": "IT",
  "category_l2": "Docking Stations",
  "count": 5
}
```

**Output fields:**

| Field | Type | Description |
|-------|------|-------------|
| `suppliers` | array | Matching supplier-category rows |
| `category_l1` | string | The L1 category that was searched |
| `category_l2` | string | The L2 category that was searched |
| `count` | integer | Number of matching suppliers |

**Each supplier object:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Primary key in the database |
| `supplier_id` | string | Supplier ID (e.g. `SUP-0001`) |
| `category_id` | integer | FK to the categories table |
| `pricing_model` | string or null | e.g. `tiered`, `per_unit` |
| `quality_score` | integer | 0-100, higher is better |
| `risk_score` | integer | 0-100, lower is better |
| `esg_score` | integer | 0-100, higher is better |
| `preferred_supplier` | boolean | Whether this supplier is preferred for this category |
| `is_restricted` | boolean | Restriction hint (cross-reference with policy for actual restrictions) |
| `restriction_reason` | string or null | Reason if restricted |
| `data_residency_supported` | boolean | Whether supplier supports in-country data residency |
| `notes` | string or null | Additional notes |

#### n8n usage notes

- The `suppliers` array from this response is passed directly into the rank-suppliers endpoint.
- You need `category_l1` and `category_l2` from either the original request or from the validate-request `request_interpretation` output.

#### Error responses

| Status | Meaning |
|--------|---------|
| 400 | Category not found, or category_l1/category_l2 missing |
| 502 | Organisational Layer API unreachable |

---

### 3. POST /api/rank-suppliers

Ranks suppliers by computing a "true cost" -- the effective price adjusted for quality, risk, and optionally ESG. Lower true cost = better deal.

#### Input

Send a JSON object with two top-level keys: `request` (the purchase request data) and `suppliers` (the supplier array from the filter step).

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/rank-suppliers` |
| Body Content Type | JSON |
| Body | `{ "request": {...}, "suppliers": [...] }` |

**Example request body:**

```json
{
  "request": {
    "category_l1": "IT",
    "category_l2": "Docking Stations",
    "quantity": 240,
    "esg_requirement": false,
    "delivery_countries": ["DE"],
    "country": "DE"
  },
  "suppliers": [
    {
      "supplier_id": "SUP-0001",
      "quality_score": 88,
      "risk_score": 15,
      "esg_score": 82,
      "preferred_supplier": true,
      "is_restricted": false
    }
  ]
}
```

**Required fields in `request`:**

| Field | Required | Description |
|-------|----------|-------------|
| `category_l1` | Yes | Level-1 category |
| `category_l2` | Yes | Level-2 category |
| `quantity` | No | If null, pricing is skipped and suppliers are sorted by quality_score descending |
| `esg_requirement` | No | Default false. If true, ESG score is factored into ranking |
| `delivery_countries` | No | Used to determine pricing region. Falls back to `country` |
| `country` | No | Fallback if delivery_countries is empty |

**Required fields in each `suppliers` entry:**

| Field | Required | Description |
|-------|----------|-------------|
| `supplier_id` | Yes | Supplier ID |
| `quality_score` | Yes | 0-100 |
| `risk_score` | Yes | 0-100 |
| `esg_score` | Yes | 0-100 |

#### Output

```json
{
  "ranked": [
    {
      "rank": 1,
      "supplier_id": "SUP-0001",
      "true_cost": 28750.42,
      "overpayment": 3550.87,
      "quality_score": 88,
      "risk_score": 15,
      "esg_score": 82,
      "total_price": 25199.55,
      "unit_price": 104.998,
      "currency": "EUR",
      "standard_lead_time_days": 14,
      "expedited_lead_time_days": 7,
      "preferred_supplier": true,
      "is_restricted": false
    }
  ],
  "category_l1": "IT",
  "category_l2": "Docking Stations",
  "count": 1
}
```

**Output fields:**

| Field | Type | Description |
|-------|------|-------------|
| `ranked` | array | Suppliers sorted by true_cost ascending (best first) |
| `category_l1` | string | The L1 category |
| `category_l2` | string | The L2 category |
| `count` | integer | Number of ranked suppliers |

**Each ranked supplier object:**

| Field | Type | Description |
|-------|------|-------------|
| `rank` | integer | Position (1 = best deal) |
| `supplier_id` | string | Supplier ID |
| `true_cost` | number or null | Effective price adjusted for quality/risk/ESG. Null if quantity is null |
| `overpayment` | number or null | Hidden cost: `true_cost - total_price`. Null if quantity is null |
| `quality_score` | integer | Raw quality score (0-100) |
| `risk_score` | integer | Raw risk score (0-100, lower is better) |
| `esg_score` | integer | Raw ESG score (0-100) |
| `total_price` | number or null | Total order cost from pricing lookup. Null if quantity is null |
| `unit_price` | number or null | Per-unit price. Null if quantity is null |
| `currency` | string or null | Pricing currency (EUR, CHF, USD) |
| `standard_lead_time_days` | integer or null | Standard delivery lead time in days |
| `expedited_lead_time_days` | integer or null | Expedited delivery lead time in days |
| `preferred_supplier` | boolean | Whether preferred for this category |
| `is_restricted` | boolean | Restriction hint flag |

#### Scoring formula

```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100)
```

When `esg_requirement` is true:

```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100) / (esg_score / 100)
```

The `overpayment` field shows how much extra you effectively pay due to quality and risk gaps.

#### n8n usage notes

- Pass the entire `suppliers` array from the filter-suppliers response as-is into the `suppliers` field.
- For `request`, you can use the `request_interpretation` from validate-request, or the original request object. Just make sure `category_l1` and `category_l2` are present.
- If `quantity` is null, no pricing lookup is performed. Suppliers are ranked by `quality_score` descending instead.
- Suppliers with no matching pricing tier are excluded from results.

#### Error responses

| Status | Meaning |
|--------|---------|
| 400 | Required fields missing (category_l1, category_l2, or supplier fields) |
| 502 | Organisational Layer API unreachable |

---

### 4. POST /api/processRequest (stub)

Placeholder for the future full pipeline. Currently returns a stub response.

#### Input

```json
{
  "request_id": "REQ-000004"
}
```

#### Output

```json
{
  "request_id": "REQ-000004",
  "status": "not_implemented",
  "message": "Full processing pipeline is not yet implemented. Use /api/filter-suppliers and /api/rank-suppliers for individual steps."
}
```

---

### 5. GET /health

Liveness check. No input required.

#### Output

```json
{
  "status": "ok"
}
```

---

## Chaining Steps in n8n

### Recommended flow

```
┌─────────────────────┐
│  Fetch request data  │  (from Organisational Layer or your data source)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  POST /api/         │  Input:  full request object
│  validate-request   │  Output: completeness, issues, request_interpretation
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Check completeness │  Branch: if completeness == false → route to human review
└──────────┬──────────┘
           │ (completeness == true)
           ▼
┌─────────────────────┐
│  POST /api/         │  Input:  { "category_l1": ..., "category_l2": ... }
│  filter-suppliers   │         (from request_interpretation or original request)
└──────────┬──────────┘  Output: { suppliers: [...], count: N }
           │
           ▼
┌─────────────────────┐
│  POST /api/         │  Input:  { "request": ..., "suppliers": <from previous step> }
│  rank-suppliers     │  Output: { ranked: [...], count: N }
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Process results    │  Use ranked suppliers for decision-making,
│  (your logic)       │  escalation, or award recommendation
└─────────────────────┘
```

### Mapping data between steps

**Validate -> Filter:**
- Use `{{ $json.request_interpretation.category_l1 }}` and `{{ $json.request_interpretation.category_l2 }}` from the validate output as input to filter.

**Filter -> Rank:**
- Pass the `suppliers` array from the filter output directly into the rank input's `suppliers` field: `{{ $json.suppliers }}`
- For the `request` field, use either the original request object or build it from the validate output's `request_interpretation`.

**Key fields to carry forward from validate:**
- `request_interpretation.quantity` -- needed for pricing in rank
- `request_interpretation.esg_requirement` -- determines whether ESG factors into ranking
- `request_interpretation.delivery_country` -- determines pricing region
- `request_interpretation.requester_instruction` -- useful for downstream escalation logic
