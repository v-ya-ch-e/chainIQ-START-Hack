# PLAN.md — Challenge Strategy & Implementation Plan

## Winning Philosophy

The judging weights tell us what matters:

| Criteria | Weight | What it really means |
|----------|--------|---------------------|
| Robustness & Escalation Logic | **25%** | Handle every edge case correctly. Never output a confident wrong answer. |
| Feasibility | **25%** | Build something that could actually ship. Clean architecture, real code. |
| Reachability | **20%** | Solve the actual procurement problem, not a toy version of it. |
| Creativity | **20%** | Surprise them with something they haven't seen from other teams. |
| Visual Design | **10%** | Clean and clear, but don't over-invest here. |

**Key insight from README**: *"A system that produces confident wrong answers will score lower than one that correctly identifies uncertainty and escalates."* This means escalation accuracy is more important than recommendation accuracy.

---

## Architecture Overview

### Recommended Stack

```
┌─────────────────────────────────────────────────┐
│                   Frontend (UI)                  │
│         Next.js / React + Tailwind CSS           │
│  Request viewer, comparison table, audit trail   │
└──────────────────────┬──────────────────────────┘
                       │ REST / WebSocket
┌──────────────────────▼──────────────────────────┐
│                Backend (API)                     │
│              Python (FastAPI)                    │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Parser   │  │ Policy   │  │ Supplier     │  │
│  │ (LLM)    │→ │ Engine   │→ │ Ranker       │  │
│  │          │  │ (Rules)  │  │              │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│       │              │              │            │
│       ▼              ▼              ▼            │
│  ┌──────────────────────────────────────────┐   │
│  │         Audit Trail Generator            │   │
│  └──────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Data Layer                          │
│   Preprocessed JSON/SQLite + Policy Index        │
│   (All 6 datasets loaded and cross-referenced)   │
└─────────────────────────────────────────────────┘
```

### Why This Stack

- **Python backend**: Best ecosystem for LLM integration, data manipulation, and rule engines
- **FastAPI**: Async, fast, auto-generates OpenAPI docs (shows feasibility)
- **React/Next.js frontend**: Modern, component-based, good for the comparison views judges want to see
- **SQLite or in-memory dicts**: No database server needed — keeps it deployable on Azure in minutes
- **LLM for parsing only**: Use the LLM to extract structure from free text, then use deterministic code for all policy logic (this is crucial for auditability)

---

## Data Transformation Plan

### Step 1: Normalize and Index All Data at Startup

#### 1a. Normalize `policies.json`

The policy file has inconsistent schemas. Normalize at load time:

```python
# Unified threshold structure
{
    "threshold_id": "AT-011",
    "currency": "USD",
    "min_amount": 0,        # normalized from min_value
    "max_amount": 27000,    # normalized from max_value
    "min_supplier_quotes": 1,  # normalized from quotes_required
    "managed_by": ["business"],  # normalized from approvers
    "deviation_approval_required_from": []  # extracted from policy_note or empty
}
```

Similarly normalize geography_rules (GR-001..GR-004 vs GR-005..GR-008) and escalation_rules (ER-008 uses different keys).

#### 1b. Build Supplier Lookup Indexes

Create fast-lookup dictionaries:

```python
# supplier by (category_l1, category_l2, country) → list of suppliers
suppliers_by_category_country = {}

# supplier by id → supplier details (merged across categories)
suppliers_by_id = {}

# supplier name → supplier_id (for resolving preferred_supplier_mentioned)
supplier_name_to_id = {}

# preferred suppliers: (supplier_id, category_l1, category_l2, region) → True
preferred_index = set()

# restricted suppliers: (supplier_id, category_l1, category_l2) → restriction details
restricted_index = {}
```

#### 1c. Build Pricing Lookup

```python
# pricing by (supplier_id, category_l1, category_l2, region) → sorted list of tiers
pricing_tiers = {}
```

Given a quantity, binary search or linear scan to find the matching tier.

#### 1d. Country-to-Region Mapping

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

#### 1e. Historical Awards Index

```python
# request_id → list of award records (sorted by rank)
awards_by_request = {}

# (category_l1, category_l2, country) → aggregated win patterns
category_country_patterns = {}
```

### Step 2: Build the Processing Pipeline

For each request, run these stages in order:

---

## Processing Pipeline (Per Request)

### Stage 1: Parse & Interpret

**Use LLM here** to extract from `request_text`:
- Quantities mentioned in text (may differ from `quantity` field)
- Budget mentioned in text (may differ from `budget_amount` field)
- Dates mentioned in text
- Supplier preferences mentioned in text
- Special instructions or constraints
- Language detection + translation if needed

**Output**: `RequestInterpretation` object with all structured fields + any text-extracted overrides.

### Stage 2: Validate

Deterministic checks (no LLM needed):

| Check | Condition | Issue Type | Severity |
|-------|-----------|------------|----------|
| Budget present | `budget_amount is not None` | missing_info | critical |
| Quantity present | `quantity is not None` | missing_info | critical |
| Budget vs. text | LLM-extracted budget ≠ `budget_amount` | contradictory | high |
| Quantity vs. text | LLM-extracted quantity ≠ `quantity` | contradictory | high |
| Budget sufficient | `quantity × min_available_unit_price ≤ budget_amount` | budget_insufficient | critical |
| Lead time feasible | `required_by_date - created_at ≥ min_expedited_lead_time` | lead_time_infeasible | high |
| Category valid | `(category_l1, category_l2)` exists in `categories.csv` | invalid_category | critical |
| Delivery country covered | At least one supplier serves all delivery countries | no_coverage | critical |

### Stage 3: Apply Policy

Deterministic rule engine:

1. **Approval threshold**: Look up tier by `currency` + `total_value` (use actual calculated value, not budget). Determine required quotes and approvers.

2. **Preferred supplier check**: If `preferred_supplier_mentioned`:
   - Resolve name → `supplier_id`
   - Check if supplier serves the right `category_l1`/`category_l2`
   - Check if supplier's `service_regions` covers all `delivery_countries`
   - Check if supplier is restricted (see next step)
   - If any check fails, note the mismatch and discard the preference

3. **Restricted supplier check**: For every candidate supplier:
   - Check `policies.json` `restricted_suppliers` for `(supplier_id, category_l1, category_l2)`
   - If found, check `restriction_scope` against `delivery_countries`
   - Handle value-conditional restrictions (SUP-0045: OK below EUR 75K)

4. **Category rules**: Check if any `category_rules` apply to this `(category_l1, category_l2)`. Apply the rule (e.g., CR-001 requires ≥3 suppliers above 100K, CR-004 requires data residency filtering).

5. **Geography rules**: Check if any `geography_rules` apply to the `delivery_countries`. Note applicable compliance requirements.

### Stage 4: Find & Price Compliant Suppliers

1. Filter `suppliers.csv` to rows matching `category_l1`, `category_l2`
2. Filter to suppliers whose `service_regions` includes all `delivery_countries`
3. Filter out restricted suppliers (from Stage 3)
4. For each remaining supplier, look up pricing:
   - Map delivery country → region
   - Find the pricing tier matching `quantity`
   - Calculate `total_price = unit_price × quantity`
   - Also calculate `expedited_total = expedited_unit_price × quantity`
   - Check `standard_lead_time_days` and `expedited_lead_time_days` vs. available time
5. If `data_residency_constraint == true`, filter to suppliers with `data_residency_supported == true`

### Stage 5: Rank Suppliers

Score each compliant supplier using a weighted formula:

```python
score = (
    w_price * normalize(1 / total_price) +     # lower price = better
    w_quality * normalize(quality_score) +       # higher = better
    w_risk * normalize(100 - risk_score) +       # lower risk = better
    w_esg * normalize(esg_score) +               # higher = better
    w_lead * lead_time_feasibility_score +        # 1 if standard works, 0.5 if only expedited, 0 if neither
    w_preferred * (1 if preferred else 0)         # bonus for preferred status
)
```

Default weights: price 30%, quality 25%, risk 20%, ESG 10%, lead time 10%, preferred 5%.
If `esg_requirement == true`, shift ESG weight to 25% (reduce price to 20%).

### Stage 6: Generate Escalations

Check each escalation rule:

| Rule | Check |
|------|-------|
| ER-001 | `budget_amount is None` or `quantity is None` or critical validation failures |
| ER-002 | `preferred_supplier_mentioned` resolves to a restricted supplier |
| ER-003 | Calculated total value crosses into a higher threshold tier than budget suggested |
| ER-004 | Zero compliant suppliers after all filtering |
| ER-005 | `data_residency_constraint == true` and no supplier supports it for this region |
| ER-006 | `quantity > preferred_supplier.capacity_per_month` (or only viable supplier) |
| ER-007 | `category_l2 == "Influencer Campaign Management"` (brand safety) |
| ER-008 | Delivery country is in Americas/APAC/MEA and supplier not registered there |

### Stage 7: Build Recommendation & Audit Trail

Assemble the final output matching the `example_output.json` format:
- `request_interpretation`
- `validation`
- `policy_evaluation`
- `supplier_shortlist` (top 3, ranked)
- `suppliers_excluded` (with reasons)
- `escalations` (with rule references, triggers, targets, blocking flag)
- `recommendation` (status: `proceed`, `proceed_with_conditions`, or `cannot_proceed`)
- `audit_trail` (policies checked, suppliers evaluated, data sources)

---

## Competitive Advantages — How to Win

### 1. Confidence Scoring (Stretch Goal, High Impact)

For each recommendation, output a confidence score (0–100%) based on:
- How many validation issues were found (fewer = higher confidence)
- Whether the top supplier is clearly ahead of #2 (larger gap = higher confidence)
- Whether any escalations are blocking (blocking = 0% confidence for autonomous decision)

This directly addresses the judging emphasis on "uncertainty handling."

### 2. Historical Pattern Context

Use `historical_awards.csv` to enhance recommendations:
- "This category in this country has historically been awarded to Supplier X 70% of the time"
- "Average savings in this category: 6.2%"
- "Escalation was required in 40% of similar past requests"

This adds credibility and shows the system learns from history.

### 3. Multi-Language Support (addresses 18 multilingual scenarios)

Use an LLM (GPT-4 / Claude) to:
- Detect language of `request_text`
- Translate to English for processing
- Keep original text in audit trail
- Flag if GR-003 (French language support) applies

### 4. Interactive Clarification Flow (addresses 28 missing_info scenarios)

Instead of just flagging "information missing," generate a **specific clarification request**:
- "Budget is missing. Based on similar requests (REQ-000045, REQ-000112), typical budget for 200 laptops in DE is EUR 180,000–190,000. Please confirm or provide your budget."

This shows sophistication and real-world usefulness.

### 5. Visual Supplier Comparison (10% of judging)

Build a clean comparison view:
- Side-by-side cards for top 3 suppliers
- Color-coded compliance indicators (green/amber/red)
- Price vs. quality scatter plot
- Timeline visualization (lead time vs. deadline)
- Collapsible audit trail per supplier

### 6. Approval Routing Simulation (Stretch Goal)

Show the approval flow:
- "This request requires Tier 3 approval (Head of Category) because the calculated value of EUR 185,000 exceeds the EUR 100,000 threshold"
- Visual workflow diagram: Requester → Business → Procurement → Head of Category

---

## What We Can Extract From the Data

### From requests.json (304 records)
- **Scenario distribution analysis**: Know exactly how many of each edge case type to handle
- **Business unit patterns**: Which units request what categories
- **Country/currency clustering**: Which countries use which currencies
- **Supplier preference patterns**: How often are preferred suppliers mentioned, and how often are they actually viable

### From suppliers.csv (40 suppliers)
- **Coverage map**: Which suppliers cover which countries × categories
- **Score distributions**: Quality/risk/ESG score ranges per category — useful for normalization
- **Capacity constraints**: Which suppliers are capacity-limited (small capacity_per_month)
- **Restriction flags**: Cross-reference with policies.json for the full picture

### From pricing.csv (599 tiers)
- **Price benchmarks per category**: Min/max/avg unit prices by category and region
- **Volume discount curves**: How much prices drop across tiers (for budget feasibility checks)
- **Lead time ranges**: Min/max lead times per category (for feasibility checks)
- **Expedited premium**: Consistently ~8%, can be used to estimate expedited costs

### From historical_awards.csv (590 records)
- **Win rate by supplier**: Which suppliers win most often in each category
- **Average savings**: Typical savings percentage by category
- **Escalation frequency**: How often escalations are triggered by category/country
- **Decision patterns**: Rationale text can be used for LLM few-shot examples

### From policies.json
- **Complete governance rulebook**: Every rule the system must enforce
- **Threshold boundaries**: Exact values for approval tier determination
- **Escalation routing table**: Who to escalate to for each trigger

---

## Implementation Priority Order

### Phase 1: Core Pipeline (Must Have — 60% of value)

1. Data loader with normalization (handle all schema inconsistencies)
2. Request parser (LLM-powered text extraction)
3. Validation engine (completeness, consistency, budget sufficiency, lead time)
4. Policy engine (thresholds, preferred, restricted, category rules, geography rules)
5. Supplier filtering and pricing lookup
6. Escalation logic
7. Output formatter (matching example_output.json structure)

### Phase 2: Ranking & Intelligence (Should Have — 25% of value)

8. Supplier scoring and ranking algorithm
9. Historical context integration
10. Confidence scoring
11. Multi-language support

### Phase 3: Frontend & Polish (Nice to Have — 15% of value)

12. Request list view with scenario tags
13. Single request detail view with supplier comparison
14. Audit trail viewer
15. Approval flow visualization

---

## Demo Script (8 minutes total)

### Live Demo (5 min)

1. **Standard request** (1 min): Show REQ-000001 (400 consulting days, Accenture, EUR 400K). Walk through parsing → policy → suppliers → ranking → recommendation. Clean, happy path.

2. **Edge case — contradictory** (2 min): Show REQ-000004 (240 docking stations, insufficient budget, impossible lead time, "no exception" instruction). Highlight: budget detection, policy conflict, lead time analysis, three escalations triggered.

3. **Supplier comparison view** (1 min): Show the side-by-side comparison for the contradictory case. Price/quality/risk/lead time breakdown. Color-coded compliance.

4. **Escalation handling** (1 min): Show the escalation panel. Which rules fired, why, who gets notified, what's blocking.

### Explanation (3 min)

1. **Architecture** (1 min): LLM for parsing only, deterministic code for all governance logic. Why this matters for auditability.
2. **Rule enforcement** (1 min): How policy rules are indexed and applied. Show the inconsistent schema handling.
3. **Scale statement** (1 min): How this would work at 10,000 requests/year: batch processing, caching, human-in-the-loop queue.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM hallucination on policy | Use LLM only for text parsing. All policy logic is deterministic code. |
| Schema inconsistencies missed | Write comprehensive data normalization tests at load time. |
| Not enough time for frontend | Prioritize backend correctness. A terminal demo with JSON output is better than a pretty UI with wrong answers. |
| Azure deployment issues | Have a local demo ready. Docker container as backup. |
| Edge cases we haven't seen | Build the escalation path as the default — when in doubt, escalate. |
