# DATABASE_BACKEND_API.md — ChainIQ Organisational Layer API

This document is the complete reference for the **Organisational Layer** — a FastAPI microservice that exposes the ChainIQ MySQL database (22 tables) over a REST API. Use it to understand every available endpoint, its parameters, and its response shape.

- **Source code:** `backend/organisational_layer/`
- **Deployment guide:** `backend/organisational_layer/DEPLOYMENT.md`
- **Database schema reference:** `DATABASE_STRUCTURE.md`
- **Live Swagger UI:** `http://3.68.96.236:8000/docs`
- **Live ReDoc:** `http://3.68.96.236:8000/redoc`

---

## Base URL

```
http://3.68.96.236:8000/
http://3.68.96.236:8000/docs#/
```

All data endpoints are prefixed with `/api`.

---

## Authentication

None. CORS is open (`*`) — all origins, methods, and headers are accepted. Suitable for hackathon use.

---

## Common Conventions

| Convention | Detail |
|---|---|
| Pagination | `?skip=0&limit=50` on list endpoints (max `limit` is 200) |
| Paginated response envelope | `{ items: [...], total: int, skip: int, limit: int }` |
| Not found | HTTP `404` with `{ "detail": "..." }` |
| Conflict on create | HTTP `409` with `{ "detail": "... already exists" }` |
| IDs | Categories use integer `id`; suppliers/requests use string IDs (`SUP-0001`, `REQ-000001`) |
| Decimal fields | Serialised as strings in JSON (e.g. `"total_price": "1250.00"`) |

---

## Endpoints Index

| Tag | Prefix | Endpoints |
|---|---|---|
| Health | `/health` | 1 |
| Categories | `/api/categories` | 5 |
| Suppliers | `/api/suppliers` | 8 |
| Requests | `/api/requests` | 5 |
| Historical Awards | `/api/awards` | 3 |
| Policies | `/api/policies` | 6 |
| Rules | `/api/rules` | 6 |
| Analytics | `/api/analytics` | 10 |

---

## Health

### `GET /health`

Service liveness check.

**Response `200`:**
```json
{ "status": "ok" }
```

---

## Categories

> 30 rows in the `categories` table — the full L1/L2 taxonomy (IT, Facilities, Professional Services, Logistics).

### `GET /api/categories`

Returns all 30 categories, ordered by `category_l1` then `category_l2`.

**Response `200`:** `CategoryOut[]`

```json
[
  {
    "id": 1,
    "category_l1": "IT",
    "category_l2": "Hardware",
    "category_description": "...",
    "typical_unit": "unit",
    "pricing_model": "per_unit"
  }
]
```

---

### `GET /api/categories/{category_id}`

Single category by integer `id`.

**Path params:**
- `category_id` — integer primary key

**Response `200`:** `CategoryOut`  
**Response `404`:** Category not found

---

### `POST /api/categories`

Create a new category.

**Request body (`CategoryCreate`):**
```json
{
  "category_l1": "IT",
  "category_l2": "NewSubcategory",
  "category_description": "...",
  "typical_unit": "unit",
  "pricing_model": "per_unit"
}
```

**Response `201`:** `CategoryOut`

---

### `PUT /api/categories/{category_id}`

Partial update — only send fields that need changing.

**Request body (`CategoryUpdate`):** all fields optional.

**Response `200`:** Updated `CategoryOut`  
**Response `404`:** Category not found

---

### `DELETE /api/categories/{category_id}`

**Response `204`:** No content  
**Response `404`:** Category not found

---

## Suppliers

> 40 unique suppliers in the `suppliers` table. Each supplier may serve multiple categories and regions (stored in `supplier_categories` and `supplier_service_regions`).

### `GET /api/suppliers`

List all suppliers with optional filters.

**Query params:**

| Param | Type | Example | Description |
|---|---|---|---|
| `country_hq` | string | `DE` | Filter by HQ country code |
| `currency` | string | `EUR` | Filter by billing currency (`EUR`, `USD`, `CHF`) |
| `category_l1` | string | `IT` | Filter to suppliers that serve this L1 category |

**Response `200`:** `SupplierOut[]`

```json
[
  {
    "supplier_id": "SUP-0001",
    "supplier_name": "Dell Technologies",
    "country_hq": "US",
    "currency": "USD",
    "contract_status": "active",
    "capacity_per_month": 5000
  }
]
```

---

### `GET /api/suppliers/{supplier_id}`

Full supplier detail including all categories served (with scores) and all service region country codes.

**Response `200`:** `SupplierDetailOut`

```json
{
  "supplier_id": "SUP-0001",
  "supplier_name": "Dell Technologies",
  "country_hq": "US",
  "currency": "USD",
  "contract_status": "active",
  "capacity_per_month": 5000,
  "categories": [
    {
      "id": 12,
      "supplier_id": "SUP-0001",
      "category_id": 3,
      "pricing_model": "per_unit",
      "quality_score": 85,
      "risk_score": 20,
      "esg_score": 70,
      "preferred_supplier": true,
      "is_restricted": false,
      "restriction_reason": null,
      "data_residency_supported": true,
      "notes": null
    }
  ],
  "service_regions": [
    { "supplier_id": "SUP-0001", "country_code": "DE" },
    { "supplier_id": "SUP-0001", "country_code": "FR" }
  ]
}
```

**Response `404`:** Supplier not found

---

### `POST /api/suppliers`

Create a new supplier record.

**Request body (`SupplierCreate`):**
```json
{
  "supplier_id": "SUP-0041",
  "supplier_name": "Acme Corp",
  "country_hq": "CH",
  "currency": "CHF",
  "contract_status": "active",
  "capacity_per_month": 1000
}
```

**Response `201`:** `SupplierOut`  
**Response `409`:** Supplier ID already exists

---

### `PUT /api/suppliers/{supplier_id}`

Partial update of supplier fields. Only provided fields are changed.

**Response `200`:** Updated `SupplierOut`  
**Response `404`:** Supplier not found

---

### `DELETE /api/suppliers/{supplier_id}`

**Response `204`:** No content  
**Response `404`:** Supplier not found

---

### `GET /api/suppliers/{supplier_id}/categories`

All category rows this supplier serves, with quality/risk/ESG scores.

**Response `200`:** `SupplierCategoryOut[]`

---

### `GET /api/suppliers/{supplier_id}/regions`

All country codes this supplier operates in.

**Response `200`:** `SupplierServiceRegionOut[]`

```json
[
  { "supplier_id": "SUP-0001", "country_code": "DE" },
  { "supplier_id": "SUP-0001", "country_code": "US" }
]
```

---

### `GET /api/suppliers/{supplier_id}/pricing`

All pricing tiers for this supplier with optional filters.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `category_id` | int | Filter by category integer ID |
| `region` | string | Filter by region (`EU`, `Americas`, `APAC`, `MEA`, `CH`) |

**Response `200`:** `PricingTierOut[]`

```json
[
  {
    "pricing_id": "PRICE-0001",
    "supplier_id": "SUP-0001",
    "category_id": 3,
    "region": "EU",
    "currency": "EUR",
    "pricing_model": "per_unit",
    "min_quantity": 1,
    "max_quantity": 100,
    "unit_price": "450.00",
    "expedited_unit_price": "540.00",
    "moq": 1,
    "standard_lead_time_days": 14,
    "expedited_lead_time_days": 5,
    "valid_from": "2024-01-01",
    "valid_to": "2024-12-31",
    "notes": null
  }
]
```

---

## Requests

> 304 purchase requests in the `requests` table. Each request has nested `delivery_countries` and `scenario_tags`.

### `GET /api/requests`

Paginated list of purchase requests with filters.

**Query params:**

| Param | Type | Example | Description |
|---|---|---|---|
| `skip` | int | `0` | Pagination offset |
| `limit` | int | `50` | Page size (max 200) |
| `country` | string | `DE` | Filter by requester country |
| `category_id` | int | `3` | Filter by category integer ID |
| `status` | string | `new` | Filter by status (`new`, `in_review`, `approved`, …) |
| `currency` | string | `EUR` | Filter by request currency |
| `tag` | string | `urgent` | Filter by scenario tag |

**Response `200`:** Paginated envelope

```json
{
  "items": [ { ...RequestOut } ],
  "total": 304,
  "skip": 0,
  "limit": 50
}
```

---

### `GET /api/requests/{request_id}`

Full request detail including nested delivery countries, scenario tags, and resolved `category_l1` / `category_l2` strings.

**Example:** `GET /api/requests/REQ-000004`

**Response `200`:** `RequestDetailOut`

```json
{
  "request_id": "REQ-000004",
  "created_at": "2024-03-15T10:30:00",
  "request_channel": "email",
  "request_language": "en",
  "business_unit": "Finance",
  "country": "DE",
  "site": "Berlin HQ",
  "requester_id": "EMP-1234",
  "requester_role": "Finance Manager",
  "submitted_for_id": "EMP-5678",
  "category_id": 3,
  "category_l1": "IT",
  "category_l2": "Hardware",
  "title": "Laptop refresh Q1",
  "request_text": "We need 50 laptops...",
  "currency": "EUR",
  "budget_amount": "75000.00",
  "quantity": "50",
  "unit_of_measure": "unit",
  "required_by_date": "2024-04-30",
  "preferred_supplier_mentioned": "Dell",
  "incumbent_supplier": null,
  "contract_type_requested": "one_off",
  "data_residency_constraint": false,
  "esg_requirement": true,
  "status": "new",
  "delivery_countries": [
    { "id": 1, "country_code": "DE" }
  ],
  "scenario_tags": [
    { "id": 1, "tag": "urgent" }
  ]
}
```

**Response `404`:** Request not found

---

### `POST /api/requests`

Create a new request with nested delivery countries and scenario tags.

**Request body (`RequestCreate`):**
```json
{
  "request_id": "REQ-000305",
  "created_at": "2026-03-18T09:00:00",
  "request_channel": "portal",
  "request_language": "en",
  "business_unit": "IT",
  "country": "CH",
  "site": "Zurich HQ",
  "requester_id": "EMP-0099",
  "requester_role": "IT Manager",
  "submitted_for_id": "EMP-0099",
  "category_id": 3,
  "title": "Server upgrade",
  "request_text": "Need 2 rack servers for data centre...",
  "currency": "CHF",
  "budget_amount": "30000.00",
  "quantity": "2",
  "unit_of_measure": "unit",
  "required_by_date": "2026-04-30",
  "contract_type_requested": "one_off",
  "data_residency_constraint": true,
  "esg_requirement": false,
  "delivery_countries": ["CH"],
  "scenario_tags": ["data_residency"]
}
```

**Response `201`:** `RequestOut`  
**Response `409`:** Request ID already exists

---

### `PUT /api/requests/{request_id}`

Partial update — only scalar fields (delivery countries and tags not updated via this endpoint).

**Response `200`:** Updated `RequestOut`  
**Response `404`:** Request not found

---

### `DELETE /api/requests/{request_id}`

**Response `204`:** No content  
**Response `404`:** Request not found

---

## Historical Awards

> 590 rows — supplier evaluations for 180 unique requests. 124 requests have no historical awards (intentional).

### `GET /api/awards`

Paginated list with filters.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `skip` | int | Pagination offset |
| `limit` | int | Page size (max 200) |
| `request_id` | string | Filter by request ID |
| `supplier_id` | string | Filter by supplier ID |
| `awarded` | bool | Filter to winners (`true`) or losers (`false`) |
| `policy_compliant` | bool | Filter to compliant/non-compliant decisions |

**Response `200`:** Paginated envelope with `HistoricalAwardOut` items

---

### `GET /api/awards/by-request/{request_id}`

All award evaluations for a specific request, ordered by `award_rank` ascending (rank 1 = winner).

**Response `200`:** `HistoricalAwardOut[]`

```json
[
  {
    "award_id": "AWARD-000001",
    "request_id": "REQ-000001",
    "award_date": "2024-01-15",
    "category_id": 3,
    "country": "DE",
    "business_unit": "IT",
    "supplier_id": "SUP-0001",
    "supplier_name": "Dell Technologies",
    "total_value": "45000.00",
    "currency": "EUR",
    "quantity": "100",
    "required_by_date": "2024-02-28",
    "awarded": true,
    "award_rank": 1,
    "decision_rationale": "Lowest price, preferred supplier, policy compliant",
    "policy_compliant": true,
    "preferred_supplier_used": true,
    "escalation_required": false,
    "escalated_to": null,
    "savings_pct": "8.50",
    "lead_time_days": 14,
    "risk_score_at_award": 20,
    "notes": null
  }
]
```

---

### `GET /api/awards/{award_id}`

Single award by ID.

**Response `200`:** `HistoricalAwardOut`  
**Response `404`:** Award not found

---

## Policies

> Approval thresholds, preferred supplier policies, and restricted supplier policies.

### `GET /api/policies/approval-thresholds`

All approval thresholds with their managers and deviation approvers.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `currency` | string | Filter by currency (`EUR`, `USD`, `CHF`) |

**Response `200`:** `ApprovalThresholdOut[]`

```json
[
  {
    "threshold_id": "THR-EUR-001",
    "currency": "EUR",
    "tier_name": "Standard",
    "min_amount": "0",
    "max_amount": "10000.00",
    "min_supplier_quotes": 1,
    "policy_note": "Single quote allowed under 10k EUR",
    "deviation_approval_required": false,
    "managers": ["Category Manager"],
    "deviation_approvers": []
  }
]
```

---

### `GET /api/policies/approval-thresholds/{threshold_id}`

Single threshold by ID (e.g. `THR-EUR-001`).

**Response `200`:** `ApprovalThresholdOut`  
**Response `404`:** Threshold not found

---

### `GET /api/policies/preferred-suppliers`

All preferred supplier policies with region scopes.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `supplier_id` | string | Filter by supplier |
| `category_l1` | string | Filter by L1 category |

**Response `200`:** `PreferredSupplierPolicyOut[]`

```json
[
  {
    "id": 1,
    "supplier_id": "SUP-0001",
    "category_l1": "IT",
    "category_l2": "Hardware",
    "policy_note": "Preferred for EMEA laptop procurement",
    "region_scopes": [
      { "id": 1, "policy_id": 1, "region": "EU" },
      { "id": 2, "policy_id": 1, "region": "CH" }
    ]
  }
]
```

---

### `GET /api/policies/preferred-suppliers/{policy_id}`

Single preferred supplier policy by integer `id`.

**Response `200`:** `PreferredSupplierPolicyOut`  
**Response `404`:** Policy not found

---

### `GET /api/policies/restricted-suppliers`

All restricted supplier policies with scope details.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `supplier_id` | string | Filter by supplier |

**Response `200`:** `RestrictedSupplierPolicyOut[]`

```json
[
  {
    "id": 1,
    "supplier_id": "SUP-0015",
    "category_l1": "IT",
    "category_l2": "Software",
    "restriction_reason": "Data residency violation in CH",
    "scopes": [
      { "id": 1, "policy_id": 1, "scope_type": "country", "scope_value": "CH" }
    ]
  }
]
```

---

### `GET /api/policies/restricted-suppliers/{policy_id}`

Single restricted supplier policy by integer `id`.

**Response `200`:** `RestrictedSupplierPolicyOut`  
**Response `404`:** Policy not found

---

## Rules

> Category rules (10), geography rules (8), and escalation rules (8).

### `GET /api/rules/category`

All category-specific procurement rules.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `category_id` | int | Filter to rules for a specific category |

**Response `200`:** `CategoryRuleOut[]`

```json
[
  {
    "rule_id": "CR-001",
    "category_id": 3,
    "rule_type": "minimum_quotes",
    "rule_text": "Minimum 3 quotes required for IT Hardware above 5000 EUR"
  }
]
```

---

### `GET /api/rules/category/{rule_id}`

Single category rule by `rule_id` (e.g. `CR-001`).

**Response `200`:** `CategoryRuleOut`  
**Response `404`:** Rule not found

---

### `GET /api/rules/geography`

All geography rules with their applicable country codes and category scopes.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `country` | string | Filter to rules that apply in a country |

**Response `200`:** `GeographyRuleOut[]`

```json
[
  {
    "rule_id": "GR-001",
    "country": "CH",
    "region": null,
    "rule_type": "data_residency",
    "rule_text": "All IT procurement in CH must use CH-domiciled suppliers",
    "countries": [],
    "applies_to_categories": []
  }
]
```

---

### `GET /api/rules/geography/{rule_id}`

Single geography rule by `rule_id` (e.g. `GR-001`).

**Response `200`:** `GeographyRuleOut`  
**Response `404`:** Rule not found

---

### `GET /api/rules/escalation`

All escalation rules with their applicable currencies.

**Response `200`:** `EscalationRuleOut[]`

```json
[
  {
    "rule_id": "ER-001",
    "escalation_trigger": "budget_exceeded",
    "threshold_amount": "500000.00",
    "escalate_to": "CPO",
    "rule_text": "Escalate to CPO when total value exceeds 500k in any currency",
    "currencies": [
      { "id": 1, "rule_id": "ER-001", "currency": "EUR" }
    ]
  }
]
```

---

### `GET /api/rules/escalation/{rule_id}`

Single escalation rule by `rule_id` (e.g. `ER-001`).

**Response `200`:** `EscalationRuleOut`  
**Response `404`:** Rule not found

---

## Analytics

> Domain-specific endpoints that implement the core procurement decision logic. These are the **primary endpoints for the sourcing agent**.

### `GET /api/analytics/compliant-suppliers`

Find all non-restricted suppliers for a specific category and delivery country, with quality/risk/ESG scores. This is the correct starting point for supplier selection — it filters out restricted suppliers automatically.

**Query params (all required):**

| Param | Type | Example | Description |
|---|---|---|---|
| `category_l1` | string | `IT` | L1 category name |
| `category_l2` | string | `Hardware` | L2 category name |
| `delivery_country` | string | `DE` | ISO country code for delivery |

**Response `200`:** `CompliantSupplierOut[]`

```json
[
  {
    "supplier_id": "SUP-0001",
    "supplier_name": "Dell Technologies",
    "country_hq": "US",
    "currency": "USD",
    "quality_score": 85,
    "risk_score": 20,
    "esg_score": 70,
    "preferred_supplier": true,
    "data_residency_supported": true
  }
]
```

> **Note:** A supplier is excluded if they appear in `restricted_suppliers_policy` with `scope_value = "all"` OR `scope_value = <delivery_country>` for the given category.

---

### `GET /api/analytics/pricing-lookup`

Look up the exact pricing tier for a supplier+category+region+quantity combination. Returns unit price, expedited price, and pre-calculated totals.

**Query params (all required):**

| Param | Type | Example | Description |
|---|---|---|---|
| `supplier_id` | string | `SUP-0001` | Supplier ID |
| `category_l1` | string | `IT` | L1 category |
| `category_l2` | string | `Hardware` | L2 category |
| `region` | string | `EU` | Region (`EU`, `Americas`, `APAC`, `MEA`, `CH`) |
| `quantity` | int | `50` | Requested quantity |

**Response `200`:** `PricingLookupOut[]`

```json
[
  {
    "pricing_id": "PRICE-0042",
    "supplier_id": "SUP-0001",
    "supplier_name": "Dell Technologies",
    "region": "EU",
    "currency": "EUR",
    "min_quantity": 1,
    "max_quantity": 100,
    "unit_price": "450.00",
    "expedited_unit_price": "540.00",
    "total_price": "22500.00",
    "expedited_total_price": "27000.00",
    "standard_lead_time_days": 14,
    "expedited_lead_time_days": 5,
    "moq": 1
  }
]
```

> Returns an empty array if no pricing tier covers the requested quantity.

---

### `GET /api/analytics/approval-tier`

Determine which approval threshold applies for a given currency and total amount, and who must approve it.

**Query params (all required):**

| Param | Type | Example | Description |
|---|---|---|---|
| `currency` | string | `EUR` | Currency (`EUR`, `USD`, `CHF`) |
| `amount` | decimal | `75000` | Transaction amount |

**Response `200`:** `ApprovalTierOut`

```json
{
  "threshold_id": "THR-EUR-003",
  "currency": "EUR",
  "min_amount": "50000.00",
  "max_amount": "200000.00",
  "min_supplier_quotes": 3,
  "policy_note": "Category Manager + Finance Director sign-off required",
  "managers": ["Category Manager", "Finance Director"],
  "deviation_approvers": ["CPO"]
}
```

**Response `404`:** No threshold found for the given currency/amount

---

### `GET /api/analytics/check-restricted`

Check whether a specific supplier is restricted for a given category and delivery country.

**Query params (all required):**

| Param | Type | Example |
|---|---|---|
| `supplier_id` | string | `SUP-0015` |
| `category_l1` | string | `IT` |
| `category_l2` | string | `Software` |
| `delivery_country` | string | `CH` |

**Response `200`:** `RestrictionCheckOut`

```json
{
  "supplier_id": "SUP-0015",
  "is_restricted": true,
  "restriction_reason": "Data residency violation in CH",
  "scope_values": ["CH"]
}
```

If not restricted:
```json
{
  "supplier_id": "SUP-0015",
  "is_restricted": false,
  "restriction_reason": null,
  "scope_values": []
}
```

---

### `GET /api/analytics/check-preferred`

Check whether a supplier is designated as preferred for a given category and optional region.

**Query params:**

| Param | Type | Required | Description |
|---|---|---|---|
| `supplier_id` | string | yes | |
| `category_l1` | string | yes | |
| `category_l2` | string | yes | |
| `region` | string | no | If omitted, checks for any global preferred status |

**Response `200`:** `PreferredCheckOut`

```json
{
  "supplier_id": "SUP-0001",
  "is_preferred": true,
  "policy_note": "Preferred for EMEA laptop procurement",
  "region_scopes": ["EU", "CH"]
}
```

---

### `GET /api/analytics/applicable-rules`

Return all category rules and geography rules that apply to a given category + delivery country combination.

**Query params (all required):**

| Param | Type | Example |
|---|---|---|
| `category_l1` | string | `IT` |
| `category_l2` | string | `Hardware` |
| `delivery_country` | string | `CH` |

**Response `200`:** `ApplicableRulesOut`

```json
{
  "category_rules": [
    {
      "rule_id": "CR-001",
      "category_id": 3,
      "rule_type": "minimum_quotes",
      "rule_text": "Minimum 3 quotes required for IT Hardware above 5000 EUR"
    }
  ],
  "geography_rules": [
    {
      "rule_id": "GR-001",
      "country": "CH",
      "region": null,
      "rule_type": "data_residency",
      "rule_text": "All IT procurement in CH must use CH-domiciled suppliers"
    }
  ]
}
```

---

### `GET /api/analytics/request-overview/{request_id}`

**The single most useful endpoint for the sourcing agent.** Returns a comprehensive, pre-assembled evaluation package for a request: request details, compliant suppliers with pricing, applicable rules, approval tier, and historical awards — all in one call.

**Path params:**
- `request_id` — e.g. `REQ-000004`

**Response `200`:** `RequestOverviewOut`

```json
{
  "request": {
    "request_id": "REQ-000004",
    "title": "Laptop refresh Q1",
    "category_l1": "IT",
    "category_l2": "Hardware",
    "currency": "EUR",
    "budget_amount": "75000.00",
    "quantity": "50",
    "country": "DE",
    "delivery_countries": ["DE"],
    "scenario_tags": ["urgent"],
    "required_by_date": "2024-04-30",
    "data_residency_constraint": false,
    "esg_requirement": true,
    "preferred_supplier_mentioned": "Dell",
    "incumbent_supplier": null,
    "status": "new"
  },
  "compliant_suppliers": [ { ...CompliantSupplierOut } ],
  "pricing": [ { ...PricingLookupOut } ],
  "applicable_rules": {
    "category_rules": [ { ...} ],
    "geography_rules": [ { ... } ]
  },
  "approval_tier": { ...ApprovalTierOut },
  "historical_awards": [
    {
      "award_id": "AWARD-000001",
      "supplier_id": "SUP-0001",
      "supplier_name": "Dell Technologies",
      "total_value": "45000.00",
      "currency": "EUR",
      "awarded": true,
      "award_rank": 1,
      "decision_rationale": "Lowest price, preferred supplier, policy compliant",
      "savings_pct": "8.50",
      "lead_time_days": 14
    }
  ]
}
```

**Internal logic:**
1. Resolves primary delivery country (first in `delivery_countries`, falls back to `request.country`)
2. Maps country to region using: `DE/FR/NL/BE/AT/IT/ES/PL/UK → EU`, `CH → CH`, `US/CA/BR/MX → Americas`, `SG/AU/IN/JP → APAC`, `UAE/ZA → MEA`
3. Filters suppliers: must serve the category + primary country, must not be restricted
4. Looks up pricing tiers for each compliant supplier at the resolved region + request quantity
5. Fetches approval tier for `(currency, budget_amount)`
6. Returns `approval_tier: null` if `budget_amount` is null or no threshold matches
7. Returns `pricing: []` if `quantity` is null

**Response `404`:** Request not found

---

### `GET /api/analytics/spend-by-category`

Aggregated historical spend from awarded decisions, grouped by category, sorted by total spend descending. Useful for dashboards.

**No query params.**

**Response `200`:** `SpendByCategoryOut[]`

```json
[
  {
    "category_l1": "IT",
    "category_l2": "Hardware",
    "total_spend": "4250000.00",
    "award_count": 42,
    "avg_savings_pct": "7.30"
  }
]
```

---

### `GET /api/analytics/spend-by-supplier`

Aggregated historical spend from awarded decisions, grouped by supplier, sorted by total spend descending.

**Response `200`:** `SpendBySupplierOut[]`

```json
[
  {
    "supplier_id": "SUP-0001",
    "supplier_name": "Dell Technologies",
    "total_spend": "1200000.00",
    "award_count": 18,
    "avg_savings_pct": "9.10"
  }
]
```

---

### `GET /api/analytics/supplier-win-rates`

Win rate statistics for every supplier that has appeared in historical awards, sorted by total wins descending.

**Response `200`:** `SupplierWinRateOut[]`

```json
[
  {
    "supplier_id": "SUP-0001",
    "supplier_name": "Dell Technologies",
    "total_evaluations": 25,
    "wins": 18,
    "win_rate": "72.00"
  }
]
```

---

## Country → Region Mapping

The `request-overview` and `pricing-lookup` endpoints require a `region` value. The internal mapping used is:

| Countries | Region |
|---|---|
| DE, FR, NL, BE, AT, IT, ES, PL, UK | `EU` |
| CH | `CH` |
| US, CA, BR, MX | `Americas` |
| SG, AU, IN, JP | `APAC` |
| UAE, ZA | `MEA` |

Countries not in this map default to `EU`.

---

## Typical Agent Workflow

For a new purchase request, the recommended sequence of API calls is:

```
1. GET /api/requests/{request_id}
   → Extract category_l1, category_l2, delivery_country, currency, budget_amount, quantity

2. GET /api/analytics/applicable-rules?category_l1=&category_l2=&delivery_country=
   → Understand mandatory rules and constraints

3. GET /api/analytics/approval-tier?currency=&amount=
   → Determine who must approve and how many quotes are required

4. GET /api/analytics/compliant-suppliers?category_l1=&category_l2=&delivery_country=
   → Get the shortlist of eligible (non-restricted) suppliers

5. GET /api/analytics/pricing-lookup?supplier_id=&category_l1=&category_l2=&region=&quantity=
   → (Repeat for each compliant supplier) — get pricing and lead times

6. GET /api/analytics/check-preferred?supplier_id=&category_l1=&category_l2=&region=
   → (For each supplier) — flag preferred suppliers in ranking

7. GET /api/awards/by-request/{request_id}
   → Check historical decisions for this exact request (if any)
```

Or use the single-call shortcut:

```
GET /api/analytics/request-overview/{request_id}
```

This executes steps 1–7 server-side and returns everything in one response.

---

## Related Documents

| Document | Purpose |
|---|---|
| `DATABASE_STRUCTURE.md` | Full MySQL schema — all 22 tables, column types, FK relationships, row counts |
| `backend/organisational_layer/DEPLOYMENT.md` | How to deploy this service to AWS EC2 with Docker |
| `backend/organisational_layer/CLAUDE.md` | Service development notes |
| `database_init/CLAUDE.md` | How the database was populated |
| `examples/example_output.json` | Reference output for REQ-000004 |
