# DATA_STRUCTURE.md — Complete Data Reference

This document is the definitive reference for all datasets in the ChainIQ hackathon. Use it when building data loaders, writing queries, or debugging pipeline issues.

---

## Overview

Six datasets, two formats. All data represents a simulated global enterprise procurement environment.

| File | Format | Records | Size | Primary Key |
|------|--------|---------|------|-------------|
| `requests.json` | JSON array | 304 | 345 KB | `request_id` |
| `suppliers.csv` | CSV | 151 rows (40 unique suppliers) | 23 KB | `(supplier_id, category_l1, category_l2)` |
| `pricing.csv` | CSV | 599 | 72 KB | `pricing_id` |
| `categories.csv` | CSV | 30 | 2.5 KB | `(category_l1, category_l2)` |
| `policies.json` | JSON object | 6 sections | 31 KB | Various rule IDs |
| `historical_awards.csv` | CSV | 590 | 148 KB | `award_id` |

---

## 1. requests.json — Purchase Requests

The inputs to the system. Each request is a messy, human-written purchase request from an internal stakeholder.

### Schema

| Field | Type | Nullable | Example | Notes |
|-------|------|----------|---------|-------|
| `request_id` | string | No | `"REQ-000001"` | Unique. Sequential format. |
| `created_at` | string (ISO 8601) | No | `"2026-04-14T10:33:00Z"` | UTC timestamp |
| `request_channel` | string | No | `"teams"` | One of: `portal`, `teams`, `email` |
| `request_language` | string | No | `"en"` | One of: `en`, `fr`, `de`, `es`, `pt`, `ja` |
| `business_unit` | string | No | `"Digital Workplace"` | Internal department |
| `country` | string | No | `"ES"` | ISO 2-letter country code of requester |
| `site` | string | No | `"Madrid"` | Office location |
| `requester_id` | string | No | `"USR-3001"` | |
| `requester_role` | string | No | `"Workplace Lead"` | |
| `submitted_for_id` | string | No | `"USR-8001"` | May differ from requester_id |
| `category_l1` | string | No | `"Professional Services"` | One of: `IT`, `Facilities`, `Professional Services`, `Marketing` |
| `category_l2` | string | No | `"IT Project Management Services"` | Subcategory (30 values) |
| `title` | string | No | `"IT project management request"` | Short title |
| `request_text` | string | No | (free text) | **The core input.** May be in non-English language. May contain quantities, dates, supplier names, constraints that contradict the structured fields. |
| `currency` | string | No | `"EUR"` | One of: `EUR`, `CHF`, `USD` |
| `budget_amount` | number | **Yes** | `400000` | Can be null (missing_info scenario) |
| `quantity` | number | **Yes** | `400` | Can be null. Can contradict `request_text`. |
| `unit_of_measure` | string | No | `"consulting_day"` | Matches `categories.csv` `typical_unit` |
| `required_by_date` | string | No | `"2026-05-17"` | ISO date. May be unrealistically tight. |
| `preferred_supplier_mentioned` | string | **Yes** | `"Accenture Advisory Europe"` | May name a restricted, wrong-category, or wrong-region supplier |
| `incumbent_supplier` | string | **Yes** | `"Accenture Advisory Europe"` | Currently contracted supplier |
| `contract_type_requested` | string | No | `"purchase"` | |
| `delivery_countries` | array[string] | No | `["ES"]` | ISO country codes. Can be multi-country. |
| `data_residency_constraint` | boolean | No | `false` | If true, data must stay in-country |
| `esg_requirement` | boolean | No | `false` | If true, ESG scores matter more |
| `status` | string | No | `"new"` | |
| `scenario_tags` | array[string] | No | `["standard"]` | See Scenario Tags section below |

### Scenario Tags Distribution

| Tag | Count | What to detect |
|-----|-------|----------------|
| `standard` | 141 | Well-formed, no issues — straightforward processing |
| `threshold` | 29 | Budget near/at approval tier boundary — careful tier determination needed |
| `lead_time` | 29 | Delivery deadline too tight for standard lead times |
| `missing_info` | 28 | `budget_amount` or `quantity` is null — must escalate (ER-001) |
| `contradictory` | 21 | Internal conflict: quantity in text vs. field, budget insufficient, requester refuses required policy steps |
| `restricted` | 18 | Preferred supplier is restricted, wrong category, or wrong region |
| `multilingual` | 18 | `request_text` in non-English language, or multi-country with different regulatory requirements |
| `capacity` | 18 | Quantity exceeds preferred supplier's monthly capacity |
| `multi_country` | 3 | Delivery across multiple countries with different compliance rules |

### Currency-to-Region Mapping

| Currency | Regions/Countries |
|----------|-------------------|
| `EUR` | DE, FR, NL, BE, AT, IT, ES, PL, UK |
| `CHF` | CH |
| `USD` | US, CA, BR, MX, SG, AU, IN, JP, UAE, ZA |

---

## 2. suppliers.csv — Supplier Master Data

Each row represents one supplier-category combination. A single supplier (e.g., SUP-0001 Dell) appears on **multiple rows**, one per category it serves.

### Schema

| Column | Type | Nullable | Example | Notes |
|--------|------|----------|---------|-------|
| `supplier_id` | string | No | `"SUP-0001"` | Not unique per row — unique per (supplier_id, category_l1, category_l2) |
| `supplier_name` | string | No | `"Dell Enterprise Europe"` | |
| `category_l1` | string | No | `"IT"` | Matches `categories.csv` |
| `category_l2` | string | No | `"Laptops"` | Matches `categories.csv` |
| `country_hq` | string | No | `"DE"` | ISO country code of HQ |
| `service_regions` | string | No | `"DE;FR;NL;BE;AT;CH;IT;ES;PL"` | **Semicolon-delimited** list of countries served |
| `currency` | string | No | `"EUR"` | Currency the supplier prices in |
| `pricing_model` | string | No | `"tiered"` | One of: `tiered`, `fixed`, `usage`, `subscription`, `day_rate`, `blended_rate`, `performance` |
| `quality_score` | int | No | `87` | 0–100 scale, higher is better |
| `risk_score` | int | No | `16` | 0–100 scale, **lower is better** |
| `esg_score` | int | No | `73` | 0–100 scale, higher is better |
| `preferred_supplier` | boolean | No | `True` | Whether this supplier is preferred for this category |
| `is_restricted` | boolean | No | `False` | **Unreliable flag.** Always cross-reference with `policies.json` `restricted_suppliers` |
| `restriction_reason` | string | **Yes** | `"Restricted for selected categories..."` | Empty if not restricted |
| `contract_status` | string | No | `"active"` | All are `active` in this dataset |
| `data_residency_supported` | boolean | No | `True` | Whether supplier supports in-country data residency |
| `capacity_per_month` | int | No | `18000` | Max units per month across all categories |
| `notes` | string | **Yes** | | Mostly empty |

### Unique Suppliers (40 total)

| ID Range | Category L1 | Notable Suppliers |
|----------|-------------|-------------------|
| SUP-0001 to SUP-0009 | IT (Hardware) | Dell, HP, Lenovo, Apple, Samsung, Panasonic, Bechtle, Computacenter, Insight |
| SUP-0010 to SUP-0017 | IT (Cloud) | Azure, AWS, Google Cloud, OVHcloud, Swiss Sovereign Cloud, Oracle, CDW, Alibaba |
| SUP-0020 to SUP-0026 | Facilities | Kinnarps, Steelcase (EU & Americas), Herman Miller, IKEA, Bene, Haworth |
| SUP-0030 to SUP-0039 | Professional Services | Accenture, Capgemini, Thoughtworks, Deloitte, EPAM, Visium, Wipro, Infosys |
| SUP-0040 to SUP-0047 | Marketing | WPP, Publicis, DEPT, Monks, Artefact, Boutique Creator, Dentsu, Havas |

### Key Gotcha: `service_regions` Matching

To check if a supplier covers a delivery country, split `service_regions` on `;` and check membership. Example:

```
"DE;FR;NL;BE;AT;CH;IT;ES;PL".split(";") → ["DE","FR","NL","BE","AT","CH","IT","ES","PL"]
```

Then check: `delivery_country in service_regions_list`.

---

## 3. pricing.csv — Pricing Tiers & Lead Times

Each row is a pricing tier for a specific supplier-category-region combination.

### Schema

| Column | Type | Nullable | Example | Notes |
|--------|------|----------|---------|-------|
| `pricing_id` | string | No | `"PR-00001"` | Unique |
| `supplier_id` | string | No | `"SUP-0001"` | FK → suppliers.csv |
| `category_l1` | string | No | `"IT"` | |
| `category_l2` | string | No | `"Laptops"` | |
| `region` | string | No | `"EU"` | One of: `EU`, `CH`, `Americas`, `APAC`, `MEA` |
| `currency` | string | No | `"EUR"` | |
| `pricing_model` | string | No | `"tiered"` | Must match suppliers.csv |
| `min_quantity` | int | No | `1` | Lower bound of tier (inclusive) |
| `max_quantity` | int | No | `99` | Upper bound of tier (inclusive) |
| `unit_price` | float | No | `980.0` | Price per unit in this tier |
| `moq` | int | No | `1` | Minimum order quantity |
| `standard_lead_time_days` | int | No | `27` | Working days for standard delivery |
| `expedited_lead_time_days` | int | No | `22` | Working days for fast delivery |
| `expedited_unit_price` | float | No | `1058.4` | ~8% premium over standard |
| `valid_from` | string (date) | No | `"2026-01-01"` | All rows: 2026-01-01 |
| `valid_to` | string (date) | No | `"2026-12-31"` | All rows: 2026-12-31 |
| `notes` | string | **Yes** | | Mostly empty |

### Tier Structure (Hardware Categories)

Hardware suppliers (tiered pricing) typically have 4 tiers:

| Tier | min_quantity | max_quantity |
|------|-------------|-------------|
| 1 | 1 | 99 |
| 2 | 100 | 499 |
| 3 | 500 | 1,999 |
| 4 | 2,000 | 99,999 |

### Region Mapping

| Region | Countries | Currency |
|--------|-----------|----------|
| `EU` | DE, FR, NL, BE, AT, IT, ES, PL, UK | EUR |
| `CH` | CH | CHF |
| `Americas` | US, CA, BR, MX | USD |
| `APAC` | SG, AU, IN, JP | USD |
| `MEA` | UAE, ZA | USD |

### How to Look Up a Price

Given a request with `supplier_id`, `category_l1`, `category_l2`, `quantity`, and a delivery country:

1. Map delivery country → region (using table above)
2. Filter `pricing.csv` where `supplier_id`, `category_l1`, `category_l2`, and `region` all match
3. Find the row where `min_quantity <= quantity <= max_quantity`
4. Read `unit_price` (or `expedited_unit_price` if lead time requires it)
5. Calculate `total_price = unit_price × quantity`
6. Check `quantity >= moq`

---

## 4. categories.csv — Category Taxonomy

Defines all valid L1/L2 category combinations. 30 rows total.

### Schema

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| `category_l1` | string | `"IT"` | 4 values: IT, Facilities, Professional Services, Marketing |
| `category_l2` | string | `"Laptops"` | 30 unique subcategories |
| `category_description` | string | `"Standard employee laptops"` | Human-readable |
| `typical_unit` | string | `"device"` | Expected UoM for this category |
| `pricing_model` | string | `"tiered"` | Expected pricing model |

### Full Category Tree

```
IT (16 subcategories)
├── Laptops                            device          tiered
├── Mobile Workstations                device          tiered
├── Desktop Workstations               device          tiered
├── Monitors                           device          tiered
├── Docking Stations                   device          tiered
├── Smartphones                        device          tiered
├── Tablets                            device          tiered
├── Rugged Devices                     device          tiered
├── Accessories Bundles                set             tiered
├── Replacement / Break-Fix Pool       device          tiered
├── Cloud Compute                      instance_hour   usage
├── Cloud Storage                      TB_month        usage
├── Cloud Networking                   GB_transfer     usage
├── Managed Cloud Platform Services    monthly_sub     subscription
└── Cloud Security Services            seat_license    subscription

Facilities (5 subcategories)
├── Workstations and Desks             unit            tiered
├── Office Chairs                      unit            tiered
├── Meeting Room Furniture             set             fixed
├── Storage Cabinets                   unit            tiered
└── Reception and Lounge Furniture     project         fixed

Professional Services (5 subcategories)
├── Cloud Architecture Consulting      consulting_day  day_rate
├── Cybersecurity Advisory             consulting_day  day_rate
├── Data Engineering Services          consulting_day  day_rate
├── Software Development Services      consulting_day  blended_rate
└── IT Project Management Services     consulting_day  day_rate

Marketing (5 subcategories)
├── Search Engine Marketing (SEM)      campaign        performance
├── Social Media Advertising           campaign        performance
├── Content Production Services        project         fixed
├── Marketing Analytics Services       monthly_sub     subscription
└── Influencer Campaign Management     campaign        fixed
```

---

## 5. policies.json — Procurement Rules

Six top-level sections. This is the governance brain of the system.

### 5.1 `approval_thresholds` (15 entries)

Determines approval level and required supplier quotes based on contract value.

**CRITICAL: Schema is inconsistent between currencies.**

#### EUR thresholds (AT-001 to AT-005) and CHF thresholds (AT-006 to AT-010)

```json
{
  "threshold_id": "AT-001",
  "currency": "EUR",
  "min_amount": 0,
  "max_amount": 24999.99,
  "min_supplier_quotes": 1,
  "managed_by": ["business"],
  "deviation_approval_required_from": []
}
```

#### USD thresholds (AT-011 to AT-015) — DIFFERENT FIELD NAMES

```json
{
  "threshold_id": "AT-011",
  "currency": "USD",
  "min_value": 0,           // ← not min_amount
  "max_value": 27000,       // ← not max_amount
  "quotes_required": 1,     // ← not min_supplier_quotes
  "approvers": ["business"],// ← not managed_by
  "policy_note": "..."      // ← not deviation_approval_required_from
}
```

**Your code must normalize these into a common structure.**

#### Threshold Tiers Summary

| Tier | EUR Range | CHF Range | USD Range | Quotes | Approver |
|------|-----------|-----------|-----------|--------|----------|
| 1 | 0 – 24,999 | 0 – 24,999 | 0 – 27,000 | 1 | Business |
| 2 | 25,000 – 99,999 | 25,000 – 99,999 | 27,000 – 108,000 | 2 | Business + Procurement |
| 3 | 100,000 – 499,999 | 100,000 – 499,999 | 108,000 – 540,000 | 3 | Head of Category |
| 4 | 500,000 – 4,999,999 | 500,000 – 4,999,999 | 540,000 – 5,400,000 | 3 | Head of Strategic Sourcing |
| 5 | 5,000,000+ | 5,000,000+ | 5,400,000+ | 3 | CPO |

Note: AT-015 (USD tier 5) has `"max_value": null` instead of a large number like the EUR/CHF tiers use.

### 5.2 `preferred_suppliers` (56 entries)

Each entry maps a supplier to a category and regional scope.

```json
{
  "supplier_id": "SUP-0001",
  "supplier_name": "Dell Enterprise Europe",
  "category_l1": "IT",
  "category_l2": "Laptops",
  "region_scope": ["EU", "CH"],
  "policy_note": "Preferred where commercially competitive and policy-compliant"
}
```

Some entries (SUP-0009, SUP-0015, SUP-0025, etc.) **lack `region_scope`** — these are global/Americas preferred suppliers. Handle missing `region_scope` as "all regions" or infer from the supplier's `service_regions`.

### 5.3 `restricted_suppliers` (5 entries)

```json
{
  "supplier_id": "SUP-0008",
  "supplier_name": "Computacenter Devices",
  "category_l1": "IT",
  "category_l2": "Laptops",
  "restriction_scope": ["CH", "DE"],
  "restriction_reason": "Policy restriction for selected device sourcing events"
}
```

Three restriction types:
- **Country-scoped**: `restriction_scope` lists specific country codes (SUP-0008, SUP-0011, SUP-0017)
- **Global**: `restriction_scope: ["all"]` (SUP-0045 Boutique Creator Network)
- **Value-conditional**: SUP-0045 can be used below EUR 75,000 without exception approval

### 5.4 `category_rules` (10 entries)

| Rule ID | Category | Type | Key Condition |
|---------|----------|------|---------------|
| CR-001 | IT / Laptops | mandatory_comparison | ≥3 suppliers above EUR/CHF 100K |
| CR-002 | IT / Mobile Workstations | engineering_spec_review | >50 units requires engineering review |
| CR-003 | IT / Break-Fix Pool | fast_track | Below EUR/CHF 75K: fast-track with 1 quote |
| CR-004 | IT / Cloud Compute | residency_check | Data residency constraint → filter suppliers |
| CR-005 | IT / Managed Cloud | security_review | Above EUR/CHF 250K → security architecture review |
| CR-006 | Facilities / Reception | design_signoff | Requires business design sign-off |
| CR-007 | Prof Services / Software Dev | cv_review | >60 consulting days → named CVs required |
| CR-008 | Prof Services / Cybersecurity | certification_check | Supplier must show certifications |
| CR-009 | Marketing / SEM | performance_baseline | Proposals need performance benchmarks |
| CR-010 | Marketing / Influencer | brand_safety | Brand-safety review before award |

### 5.5 `geography_rules` (8 entries)

| Rule ID | Scope | Type | Summary |
|---------|-------|------|---------|
| GR-001 | CH | sovereign_preference | Swiss data residency → sovereign/approved providers |
| GR-002 | DE | lead_time_constraint | Urgent device requests in DE need delivery within deadline |
| GR-003 | FR | language_support | French-language delivery support for business-facing services |
| GR-004 | ES | regional_rollout | Large rollouts in Spain need installation support evidence |
| GR-005 | Americas | US data sovereignty | Financial/healthcare data must stay in-country |
| GR-006 | APAC | Data localisation | India RBI, SG MAS, JP FISC guidelines |
| GR-007 | MEA | Compliance | UAE PDPL, South Africa POPIA |
| GR-008 | LATAM | DPA requirement | Brazil LGPD, Mexico LFPDPPP |

**Schema inconsistency**: GR-001 to GR-004 use `country` + `rule_type` + `rule_text`. GR-005 to GR-008 use `region` + `countries` + `rule` + `applies_to`. Normalize both.

### 5.6 `escalation_rules` (8 entries)

| Rule ID | Trigger | Escalate To |
|---------|---------|-------------|
| ER-001 | Missing required info (budget, quantity, spec) | Requester Clarification |
| ER-002 | Preferred supplier is restricted | Procurement Manager |
| ER-003 | Value exceeds threshold | Head of Strategic Sourcing |
| ER-004 | No compliant supplier found | Head of Category |
| ER-005 | Data residency constraint conflict | Security and Compliance Review |
| ER-006 | Single supplier capacity risk | Sourcing Excellence Lead |
| ER-007 | Brand safety review needed | Marketing Governance Lead |
| ER-008 | Supplier not registered/sanctioned in delivery country | Regional Compliance Lead |

**Schema inconsistency**: ER-001 to ER-007 use `trigger`/`action`/`escalate_to`. ER-008 uses `trigger`/`action`/`escalation_target` (different key name) and adds `applies_to_currencies`. Normalize.

---

## 6. historical_awards.csv — Past Decisions

590 rows covering 180 of the 304 requests. Multiple rows per request (one per evaluated supplier).

### Schema

| Column | Type | Nullable | Example | Notes |
|--------|------|----------|---------|-------|
| `award_id` | string | No | `"AWD-000001"` | Unique |
| `request_id` | string | No | `"REQ-000001"` | FK → requests.json |
| `award_date` | string (date) | No | `"2026-04-21"` | Decision date (not delivery date) |
| `category_l1` | string | No | `"Professional Services"` | |
| `category_l2` | string | No | `"IT Project Management Services"` | |
| `country` | string | No | `"ES"` | |
| `business_unit` | string | No | `"Digital Workplace"` | |
| `supplier_id` | string | No | `"SUP-0030"` | FK → suppliers.csv |
| `supplier_name` | string | No | `"Accenture Advisory Europe"` | |
| `total_value` | float | No | `448000.0` | Total contract value |
| `currency` | string | No | `"EUR"` | |
| `quantity` | float | No | `400.0` | |
| `required_by_date` | string (date) | No | `"2026-05-17"` | |
| `awarded` | boolean | No | `True` | `True` = winner, `False` = evaluated alternative |
| `award_rank` | int | No | `1` | 1 = recommended |
| `decision_rationale` | string | No | `"Strong incumbent performance..."` | |
| `policy_compliant` | boolean | No | `True` | |
| `preferred_supplier_used` | boolean | No | `True` | |
| `escalation_required` | boolean | No | `False` | |
| `escalated_to` | string | **Yes** | `"Head of Strategic Sourcing"` | Empty if no escalation |
| `savings_pct` | float | No | `7.5` | % savings vs. budget (0.0 for non-winners) |
| `lead_time_days` | int | No | `13` | |
| `risk_score_at_award` | int | No | `25` | Snapshot at decision time |
| `notes` | string | **Yes** | | Mostly empty |

### Usage Patterns

- Typically 2–3 rows per request (winner + alternatives)
- `awarded=True` rows always have `award_rank=1`
- `savings_pct > 0` only for the winning supplier
- Can be used to learn decision patterns: which suppliers win in which categories, typical savings, escalation frequency

---

## Entity Relationship Diagram

```
requests.json ─────────────────────── historical_awards.csv
   │  request_id                          │  request_id
   │                                      │  supplier_id
   │  category_l1, category_l2            │
   │       │                              │
   │       ▼                              │
   │  categories.csv                      │
   │  (category_l1, category_l2)          │
   │                                      │
   │  delivery_countries ──→ region       │
   │       │                              │
   │       ▼                              ▼
   │  suppliers.csv ◄──────────────── pricing.csv
   │  (supplier_id,                   (supplier_id,
   │   category_l1,                    category_l1,
   │   category_l2)                    category_l2,
   │   service_regions ──→ coverage    region)
   │
   │  currency, budget_amount
   │       │
   │       ▼
   │  policies.json
   │  ├── approval_thresholds (by currency + value)
   │  ├── preferred_suppliers (by supplier_id + category + region)
   │  ├── restricted_suppliers (by supplier_id + category + scope)
   │  ├── category_rules (by category_l1 + category_l2)
   │  ├── geography_rules (by country/region)
   │  └── escalation_rules (by trigger condition)
```

### Join Keys Summary

| From → To | Join On |
|-----------|---------|
| request → suppliers | `category_l1`, `category_l2`, then filter by `delivery_countries ∩ service_regions` |
| request → pricing | Via supplier, then `category_l1`, `category_l2`, `region` (mapped from country), `quantity` range |
| request → categories | `category_l1`, `category_l2` |
| request → approval_thresholds | `currency`, then `budget_amount` or calculated `total_value` within `[min_amount, max_amount]` |
| request → preferred_suppliers | `preferred_supplier_mentioned` name match → `supplier_id` → check `category_l1`, `category_l2`, `region_scope` |
| request → restricted_suppliers | All matched suppliers → check if `supplier_id` + `category` appears in restricted list, then check `restriction_scope` vs. delivery country |
| request → category_rules | `category_l1`, `category_l2` |
| request → geography_rules | `delivery_countries` → match against `country` or `countries` array |
| request → historical_awards | `request_id` |
| historical_awards → suppliers | `supplier_id` |

---

## Data Quality Notes

1. **Null values in requests**: `budget_amount` and `quantity` can be null. These are `missing_info` scenarios requiring ER-001 escalation.

2. **Text vs. field contradictions**: Some requests have a `quantity` field that differs from the quantity mentioned in `request_text`. Both should be surfaced as a contradiction.

3. **Preferred supplier mismatches**: `preferred_supplier_mentioned` may name a supplier that:
   - Is restricted (check `policies.json`)
   - Serves a different category than requested
   - Doesn't cover the delivery country
   - Requires exception approval above a value threshold

4. **Budget vs. actual cost**: The `budget_amount` may be insufficient to cover `quantity × unit_price` at any compliant supplier. This is a `contradictory` scenario.

5. **Lead time feasibility**: `required_by_date - created_at` gives available days. Compare against `standard_lead_time_days` and `expedited_lead_time_days`. Some requests are impossible.

6. **Capacity constraints**: `capacity_per_month` in suppliers.csv is shared across all categories for that supplier. Compare against `quantity` in the request.

7. **Historical awards as context only**: 124 of 304 requests have no awards. Award data shows precedent but is not ground truth for evaluation.
