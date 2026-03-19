# n8n Integration Instructions

This document describes how to call the Logical Layer API from n8n workflows. The API base URL is `http://logical-layer:8080` (Docker internal) or `http://localhost:8080` (local dev).

Swagger UI with interactive docs is available at `http://localhost:8080/docs`.

## Pipeline Overview

The n8n workflow calls endpoints in sequence with **two branching points**:

```
1. Fetch request    ──→  GET  Org Layer /api/requests/{id}  (or POST /api/fetch-request)
2. Validate         ──→  POST /api/validate-request
3. Branch: valid / invalid
   ├─ Invalid       ──→  POST /api/format-invalid-response  ──→  Respond to Webhook
   └─ Valid          ──→  continue
4. Filter           ──→  POST /api/filter-suppliers
5. Check compliance ──→  POST /api/check-compliance
6. Branch: compliant / non-compliant
   ├─ Compliant     ──→  POST /api/rank-suppliers  ──→  Ranked companies
   └─ Non-compliant ──→  Excluded suppliers
7. Merge ranked + excluded
8. Evaluate policy  ──→  POST /api/evaluate-policy
9. Check escalations──→  POST /api/check-escalations
10. Recommend       ──→  POST /api/generate-recommendation
11. Assemble        ──→  POST /api/assemble-output
12. Respond / Save
```

There is also a convenience endpoint `POST /api/processRequest` that runs all steps internally and returns the final output in a single call.

---

## Endpoints

### 1. POST /api/fetch-request

Proxy endpoint that fetches the full purchase request from the Organisational Layer.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/fetch-request` |
| Body Content Type | JSON |
| Body | `{ "request_id": "REQ-000004" }` |

**Response:** The full purchase request object (same structure as `examples/example_request.json`).

Alternatively, n8n can call the Organisational Layer directly: `GET http://organisational-layer:8000/api/requests/REQ-000004`.

---

### 2. POST /api/validate-request

Validates a purchase request for completeness and internal consistency. Runs deterministic field checks and uses Claude (Anthropic LLM) to detect contradictions between the free-text `request_text` and the structured fields.

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

**Response:**

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

**n8n branching:** Check `{{ $json.completeness }}`. If `false` and any issue has `type == "missing_required"`, route to the invalid request path.

**Error responses:** `400` if invalid input. `502` if Anthropic API error.

---

### 3. POST /api/format-invalid-response (Invalid Request Branch)

Formats a structured response for requests that fail validation. Uses Claude LLM to generate human-readable summaries and enriched issue descriptions.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/format-invalid-response` |
| Body Content Type | JSON |
| Body | See below |

**Request body:**

```json
{
  "request_data": { ... full request object ... },
  "validation": {
    "completeness": false,
    "issues": [ ... from validate-request ... ]
  },
  "request_interpretation": { ... from validate-request ... }
}
```

**Response:**

```json
{
  "request_id": "REQ-000004",
  "processed_at": "2026-03-14T18:02:11Z",
  "status": "invalid",
  "validation": {
    "completeness": "fail",
    "issues_detected": [
      {
        "issue_id": "V-001",
        "severity": "critical",
        "type": "missing_required",
        "description": "Required field 'category_l1' is missing.",
        "action_required": "Provide the product category."
      }
    ]
  },
  "request_interpretation": { ... },
  "escalations": [
    {
      "escalation_id": "ESC-001",
      "rule": "ER-001",
      "trigger": "Missing required information prevents autonomous processing.",
      "escalate_to": "Requester Clarification",
      "blocking": true
    }
  ],
  "recommendation": {
    "status": "cannot_proceed",
    "reason": "Request has missing required fields that must be resolved."
  },
  "summary": "Human-readable summary of validation failures"
}
```

**n8n usage:** Send this response to the Respond to Webhook node.

---

### 4. POST /api/filter-suppliers

Filters all suppliers to only those serving the same product category as the purchase request.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/filter-suppliers` |
| Body Content Type | JSON |
| Body | `{ "category_l1": "...", "category_l2": "..." }` |

**Request body (use values from validate step):**

```json
{
  "category_l1": "IT",
  "category_l2": "Docking Stations"
}
```

**Response:**

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

**Error responses:** `400` if category not found. `502` if Org Layer unreachable.

---

### 5. POST /api/check-compliance

Checks each supplier against compliance rules (restrictions, delivery coverage, data residency). Returns suppliers split into compliant and non-compliant lists.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/check-compliance` |
| Body Content Type | JSON |
| Body | See below |

**Request body:**

```json
{
  "request_data": {
    "category_l1": "IT",
    "category_l2": "Docking Stations",
    "delivery_countries": ["DE"],
    "country": "DE",
    "currency": "EUR",
    "budget_amount": 25199.55,
    "data_residency_constraint": false
  },
  "suppliers": [ ... from filter-suppliers ... ]
}
```

For `request_data`, use the original request object or build it from the validate step's `request_interpretation`. For `suppliers`, pass the `suppliers` array from the filter step.

**Response:**

```json
{
  "compliant": [
    {
      "supplier_id": "SUP-0001",
      "quality_score": 88,
      "risk_score": 15,
      "compliance_notes": "Passes all compliance checks",
      ...
    }
  ],
  "non_compliant": [
    {
      "supplier_id": "SUP-0008",
      "quality_score": 70,
      "risk_score": 34,
      "exclusion_reason": "Restricted: Restricted above EUR 75,000",
      ...
    }
  ],
  "total_checked": 5,
  "compliant_count": 4,
  "non_compliant_count": 1
}
```

**n8n branching:** Split on the `compliant` and `non_compliant` arrays. Route `compliant` to the rank step and `non_compliant` to the excluded path.

**Error responses:** `400` if missing category fields. `502` if Org Layer unreachable.

---

### 6. POST /api/rank-suppliers

Ranks suppliers by computing a "true cost" -- the effective price adjusted for quality, risk, and optionally ESG. Lower true cost = better deal.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/rank-suppliers` |
| Body Content Type | JSON |
| Body | `{ "request": {...}, "suppliers": [...] }` |

**Request body:**

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
  "suppliers": [ ... compliant suppliers from check-compliance ... ]
}
```

**Response:**

```json
{
  "ranked": [
    {
      "rank": 1,
      "supplier_id": "SUP-0007",
      "true_cost": 43551.22,
      "overpayment": 7839.22,
      "quality_score": 82,
      "risk_score": 19,
      "esg_score": 72,
      "total_price": 35712.00,
      "unit_price": 148.80,
      "currency": "EUR",
      "standard_lead_time_days": 26,
      "expedited_lead_time_days": 18,
      "preferred_supplier": true,
      "is_restricted": false
    }
  ],
  "category_l1": "IT",
  "category_l2": "Docking Stations",
  "count": 3
}
```

**Scoring formula:**

```
true_cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100)
```

When `esg_requirement` is true: `/ (esg_score / 100)`.

**Error responses:** `400` if missing required fields. `502` if Org Layer unreachable.

---

### 7. POST /api/evaluate-policy

Evaluates procurement policies: approval threshold, preferred supplier analysis, restriction checks, and applicable rules.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/evaluate-policy` |
| Body Content Type | JSON |
| Body | See below |

**Request body:**

```json
{
  "request_data": { ... full request object ... },
  "ranked_suppliers": [ ... from rank-suppliers ... ],
  "non_compliant_suppliers": [ ... from check-compliance non_compliant ... ]
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
  "restricted_suppliers": {
    "SUP-0008_Computacenter_Devices": {
      "restricted": false,
      "note": "No restriction for IT/Docking Stations in DE."
    }
  },
  "category_rules_applied": [],
  "geography_rules_applied": []
}
```

**Error responses:** `400` if missing fields. `502` if Org Layer unreachable.

---

### 8. POST /api/check-escalations

Fetches computed escalations from the Organisational Layer's escalation engine (ER-001 through ER-008 + AT threshold conflict detection).

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/check-escalations` |
| Body Content Type | JSON |
| Body | `{ "request_id": "REQ-000004" }` |

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

**Error responses:** `502` if Org Layer unreachable.

---

### 9. POST /api/generate-recommendation

Generates a procurement recommendation based on escalations, ranked suppliers, and validation results. Uses Claude LLM for human-readable reasoning.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/generate-recommendation` |
| Body Content Type | JSON |
| Body | See below |

**Request body:**

```json
{
  "escalations": [ ... from check-escalations ... ],
  "ranked_suppliers": [ ... from rank-suppliers ... ],
  "validation": { ... from validate-request ... },
  "request_interpretation": { ... from validate-request ... }
}
```

**Response:**

```json
{
  "status": "cannot_proceed",
  "reason": "Three blocking issues prevent autonomous award: insufficient budget, policy conflict with requester's single-supplier instruction, and infeasible delivery timeline.",
  "preferred_supplier_if_resolved": "Bechtle Workplace Solutions",
  "preferred_supplier_rationale": "Bechtle is the incumbent and lowest-cost option at EUR 35,712.",
  "minimum_budget_required": 35712.00,
  "minimum_budget_currency": "EUR"
}
```

**Status values:**

| Status | Meaning |
|--------|---------|
| `proceed` | No escalations; autonomous award is possible |
| `proceed_with_conditions` | Non-blocking escalations exist; can proceed with oversight |
| `cannot_proceed` | Blocking escalations; human resolution required |

**Error responses:** `502` if LLM error.

---

### 10. POST /api/assemble-output

Assembles all pipeline step outputs into the final format matching `example_output.json`. Uses Claude LLM to enrich validation issues and supplier recommendation notes.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/assemble-output` |
| Body Content Type | JSON |
| Body | See below |

**Request body:**

```json
{
  "request_id": "REQ-000004",
  "request_data": { ... full request object ... },
  "validation": { ... from validate-request ... },
  "request_interpretation": { ... from validate-request ... },
  "ranked_suppliers": [ ... from rank-suppliers ... ],
  "non_compliant_suppliers": [ ... from check-compliance non_compliant ... ],
  "policy_evaluation": { ... from evaluate-policy ... },
  "escalations": [ ... from check-escalations ... ],
  "recommendation": { ... from generate-recommendation ... },
  "historical_awards": [ ... optional ... ]
}
```

**Response:** The complete pipeline output with all 8 sections:

```json
{
  "request_id": "REQ-000004",
  "processed_at": "2026-03-14T18:02:11Z",
  "request_interpretation": { ... },
  "validation": {
    "completeness": "pass|fail",
    "issues_detected": [ { "issue_id", "severity", "type", "description", "action_required" } ]
  },
  "policy_evaluation": { ... },
  "supplier_shortlist": [ { "rank", "supplier_id", "supplier_name", ... } ],
  "suppliers_excluded": [ { "supplier_id", "supplier_name", "reason" } ],
  "escalations": [ { "escalation_id", "rule", "trigger", "escalate_to", "blocking" } ],
  "recommendation": { ... },
  "audit_trail": {
    "policies_checked": [...],
    "supplier_ids_evaluated": [...],
    "pricing_tiers_applied": "...",
    "data_sources_used": [...],
    "historical_awards_consulted": true,
    "historical_award_note": "..."
  }
}
```

**Error responses:** `502` if LLM error.

---

### 11. POST /api/processRequest (Full Pipeline)

Convenience endpoint that runs all pipeline steps internally. Equivalent to calling steps 1-11 in sequence.

**n8n HTTP Request node configuration:**

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `http://logical-layer:8080/api/processRequest` |
| Body Content Type | JSON |
| Body | `{ "request_id": "REQ-000004" }` |

**Response:** Same structure as `/api/assemble-output` with an additional `status` field (`"processed"` or `"invalid"`).

---

### 12. GET /health

Liveness check. No input required.

**Response:** `{ "status": "ok" }`

---

## Chaining Steps in n8n

### Complete pipeline flow with branching

```
┌──────────────────────────┐
│  GET Org Layer           │  Fetch request data
│  /api/requests/{id}      │  (or POST /api/fetch-request)
└────────────┬─────────────┘
             │ request_data
             ▼
┌──────────────────────────┐
│  POST /api/              │  Input:  full request object
│  validate-request        │  Output: completeness, issues, request_interpretation
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  Branch: completeness?   │
│  Has missing_required?   │
└──┬───────────────────┬───┘
   │ Invalid           │ Valid
   ▼                   ▼
┌──────────────────┐  ┌──────────────────────────┐
│ POST /api/       │  │  POST /api/              │
│ format-invalid-  │  │  filter-suppliers        │
│ response         │  │  Input: category_l1, l2  │
└────────┬─────────┘  └────────────┬─────────────┘
         │                         │ suppliers[]
         ▼                         ▼
┌──────────────────┐  ┌──────────────────────────┐
│ Respond to       │  │  POST /api/              │
│ Webhook          │  │  check-compliance        │
└──────────────────┘  │  Input: request_data,    │
                      │         suppliers         │
                      └────────────┬─────────────┘
                                   │
                                   ▼
                      ┌──────────────────────────┐
                      │  Branch: compliant?      │
                      └──┬───────────────────┬───┘
                         │ Non-compliant     │ Compliant
                         ▼                   ▼
                      ┌──────────────┐  ┌──────────────────────────┐
                      │ Collect      │  │  POST /api/              │
                      │ excluded     │  │  rank-suppliers          │
                      │ suppliers    │  │  Input: request,         │
                      └──────┬───────┘  │         compliant suppl. │
                             │          └────────────┬─────────────┘
                             │                       │ ranked[]
                             ▼                       ▼
                      ┌──────────────────────────────────┐
                      │           Merge                   │
                      └────────────────┬─────────────────┘
                                       │
                                       ▼
                      ┌──────────────────────────┐
                      │  POST /api/              │
                      │  evaluate-policy         │
                      │  Input: request_data,    │
                      │    ranked, non_compliant │
                      └────────────┬─────────────┘
                                   │
                                   ▼
                      ┌──────────────────────────┐
                      │  POST /api/              │
                      │  check-escalations       │
                      │  Input: request_id       │
                      └────────────┬─────────────┘
                                   │
                                   ▼
                      ┌──────────────────────────┐
                      │  POST /api/              │
                      │  generate-recommendation │
                      │  Input: escalations,     │
                      │    ranked, validation    │
                      └────────────┬─────────────┘
                                   │
                                   ▼
                      ┌──────────────────────────┐
                      │  POST /api/              │
                      │  assemble-output         │
                      │  Input: all step outputs │
                      └────────────┬─────────────┘
                                   │
                                   ▼
                      ┌──────────────────────────┐
                      │  Respond / Save          │
                      └──────────────────────────┘
```

### Mapping data between steps

**Fetch → Validate:**
- Pass the full request object from the Org Layer as the body to validate-request.

**Validate → Branch:**
- Check `{{ $json.completeness }}` and whether any issue has `type == "missing_required"`.
- If invalid: route to `format-invalid-response` with the request data, validation result, and interpretation.

**Validate → Filter:**
- Use `{{ $json.request_interpretation.category_l1 }}` and `{{ $json.request_interpretation.category_l2 }}` from the validate output as input to filter.

**Filter → Check Compliance:**
- Pass the original request object (or build from interpretation) as `request_data`.
- Pass `{{ $json.suppliers }}` from filter output as `suppliers`.

**Check Compliance → Branch:**
- Split on `compliant` and `non_compliant` arrays.

**Compliant → Rank:**
- Pass the `compliant` array as `suppliers` in the rank input.
- For `request`, use the original request object or build from interpretation (need category_l1, category_l2, quantity, esg_requirement, delivery_countries).

**Merge → Evaluate Policy:**
- Pass original request as `request_data`.
- Pass ranked suppliers as `ranked_suppliers`.
- Pass non-compliant suppliers as `non_compliant_suppliers`.

**Evaluate Policy → Check Escalations:**
- Pass `{ "request_id": "REQ-000004" }`.

**Check Escalations → Generate Recommendation:**
- Pass `escalations` from check-escalations.
- Pass `ranked` array from rank-suppliers as `ranked_suppliers`.
- Pass `validation` and `request_interpretation` from validate step.

**Generate Recommendation → Assemble Output:**
- Combine all outputs: request_id, request_data, validation, interpretation, ranked_suppliers, non_compliant_suppliers, policy_evaluation, escalations, recommendation.

### Key fields to carry forward from validate

- `request_interpretation.quantity` -- needed for pricing in rank
- `request_interpretation.esg_requirement` -- determines whether ESG factors into ranking
- `request_interpretation.delivery_country` -- determines pricing region
- `request_interpretation.requester_instruction` -- useful for downstream escalation logic
- `request_interpretation.currency` -- needed for approval tier lookup
- `request_interpretation.budget_amount` -- needed for budget sufficiency checks
