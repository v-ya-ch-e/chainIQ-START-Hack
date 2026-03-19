"""Evaluate procurement policies for a purchase request and its candidate suppliers.

Produces the policy_evaluation section of the pipeline output: approval threshold,
preferred supplier analysis, restriction checks, and applicable category/geography rules.

API-friendly: importable as a module, or callable via stdin/stdout for subprocess use.
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = os.environ.get("ORGANISATIONAL_LAYER_URL", "http://3.68.96.236:8000")

COUNTRY_TO_REGION = {
    "DE": "EU", "FR": "EU", "NL": "EU", "BE": "EU", "AT": "EU",
    "IT": "EU", "ES": "EU", "PL": "EU", "UK": "EU",
    "CH": "CH",
    "US": "Americas", "CA": "Americas", "BR": "Americas", "MX": "Americas",
    "SG": "APAC", "AU": "APAC", "IN": "APAC", "JP": "APAC",
    "UAE": "MEA", "ZA": "MEA",
}


def api_get(path, params=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _normalize_delivery_countries(raw):
    if not raw:
        return []
    if isinstance(raw[0], dict):
        return [c.get("country_code", "") for c in raw]
    return raw


def _resolve_region(request_data):
    delivery_countries = _normalize_delivery_countries(
        request_data.get("delivery_countries") or []
    )
    country = delivery_countries[0] if delivery_countries else request_data.get("country", "")
    return COUNTRY_TO_REGION.get(country, "EU")


def _evaluate_approval_threshold(currency, amount, ranked_suppliers):
    """Determine approval tier based on currency and amount."""
    effective_amount = amount
    if effective_amount is None and ranked_suppliers:
        prices = [s.get("total_price") for s in ranked_suppliers if s.get("total_price")]
        if prices:
            effective_amount = min(prices)

    if effective_amount is None or currency is None:
        return {
            "rule_applied": None,
            "basis": "Cannot determine approval tier: missing currency or amount.",
            "quotes_required": None,
            "approvers": [],
            "deviation_approval": None,
            "note": None,
        }

    try:
        tier = api_get("/api/analytics/approval-tier", {
            "currency": currency,
            "amount": float(effective_amount),
        })
    except (urllib.error.HTTPError, urllib.error.URLError):
        return {
            "rule_applied": None,
            "basis": f"Could not resolve approval tier for {currency} {effective_amount}.",
            "quotes_required": None,
            "approvers": [],
            "deviation_approval": None,
            "note": None,
        }

    if tier is None:
        return {
            "rule_applied": None,
            "basis": f"No matching threshold for {currency} {effective_amount}.",
            "quotes_required": None,
            "approvers": [],
            "deviation_approval": None,
            "note": None,
        }

    managers = tier.get("managers") or []
    deviation_approvers = tier.get("deviation_approvers") or []

    return {
        "rule_applied": tier.get("threshold_id"),
        "basis": f"Contract value of {currency} {effective_amount} falls in threshold {tier.get('threshold_id')} "
                 f"(range: {tier.get('min_amount')}–{tier.get('max_amount') or 'unlimited'}).",
        "quotes_required": tier.get("min_supplier_quotes"),
        "approvers": managers,
        "deviation_approval": deviation_approvers[0] if deviation_approvers else None,
        "note": tier.get("policy_note"),
    }


def _evaluate_preferred_supplier(request_data, ranked_suppliers):
    """Check preferred supplier status for the requester's stated preference."""
    preferred_name = request_data.get("preferred_supplier_mentioned")
    if not preferred_name:
        return {
            "supplier": None,
            "status": "none_stated",
            "is_preferred": False,
            "covers_delivery_country": None,
            "is_restricted": None,
            "policy_note": "No preferred supplier stated in request.",
        }

    category_l1 = request_data.get("category_l1", "")
    category_l2 = request_data.get("category_l2", "")
    region = _resolve_region(request_data)

    matched_supplier = None
    for s in ranked_suppliers:
        supplier_name = s.get("supplier_name", "")
        if preferred_name.lower() in supplier_name.lower() or supplier_name.lower() in preferred_name.lower():
            matched_supplier = s
            break

    supplier_id = matched_supplier.get("supplier_id") if matched_supplier else None

    if not supplier_id:
        return {
            "supplier": preferred_name,
            "status": "not_found",
            "is_preferred": False,
            "covers_delivery_country": False,
            "is_restricted": None,
            "policy_note": f"Stated preferred supplier '{preferred_name}' was not found among evaluated suppliers.",
        }

    try:
        pref_check = api_get("/api/analytics/check-preferred", {
            "supplier_id": supplier_id,
            "category_l1": category_l1,
            "category_l2": category_l2,
            "region": region,
        })
        is_preferred = pref_check.get("is_preferred", False)
        pref_note = pref_check.get("policy_note")
    except (urllib.error.HTTPError, urllib.error.URLError):
        is_preferred = matched_supplier.get("preferred_supplier", False) if matched_supplier else False
        pref_note = None

    covers_country = matched_supplier is not None
    is_restricted = matched_supplier.get("is_restricted", False) if matched_supplier else None

    return {
        "supplier": preferred_name,
        "status": "eligible" if not is_restricted else "restricted",
        "is_preferred": is_preferred,
        "covers_delivery_country": covers_country,
        "is_restricted": is_restricted,
        "policy_note": pref_note,
    }


def _evaluate_restricted_suppliers(request_data, all_suppliers):
    """Check restriction status for each evaluated supplier."""
    category_l1 = request_data.get("category_l1", "")
    category_l2 = request_data.get("category_l2", "")
    delivery_countries = _normalize_delivery_countries(
        request_data.get("delivery_countries") or []
    )
    primary_country = delivery_countries[0] if delivery_countries else request_data.get("country", "")

    result = {}
    for sup in all_suppliers:
        supplier_id = sup.get("supplier_id", "")
        supplier_name = sup.get("supplier_name", supplier_id)
        key = f"{supplier_id}_{supplier_name}".replace(" ", "_")

        try:
            check = api_get("/api/analytics/check-restricted", {
                "supplier_id": supplier_id,
                "category_l1": category_l1,
                "category_l2": category_l2,
                "delivery_country": primary_country,
            })
            result[key] = {
                "restricted": check.get("is_restricted", False),
                "note": check.get("restriction_reason") or f"No restriction for {category_l1}/{category_l2} in {primary_country}.",
            }
        except (urllib.error.HTTPError, urllib.error.URLError):
            result[key] = {
                "restricted": sup.get("is_restricted", False),
                "note": sup.get("restriction_reason") or "Could not verify restriction status.",
            }

    return result


def _evaluate_applicable_rules(request_data):
    """Fetch applicable category and geography rules."""
    category_l1 = request_data.get("category_l1", "")
    category_l2 = request_data.get("category_l2", "")
    delivery_countries = _normalize_delivery_countries(
        request_data.get("delivery_countries") or []
    )
    primary_country = delivery_countries[0] if delivery_countries else request_data.get("country", "")

    try:
        rules = api_get("/api/analytics/applicable-rules", {
            "category_l1": category_l1,
            "category_l2": category_l2,
            "delivery_country": primary_country,
        })
        return {
            "category_rules_applied": rules.get("category_rules", []),
            "geography_rules_applied": rules.get("geography_rules", []),
        }
    except (urllib.error.HTTPError, urllib.error.URLError):
        return {
            "category_rules_applied": [],
            "geography_rules_applied": [],
        }


def evaluate_policy(request_data: dict, ranked_suppliers: list, non_compliant_suppliers: list) -> dict:
    """Core logic: evaluate procurement policies for the request.

    Input:
      request_data: full purchase request dict
      ranked_suppliers: ranked compliant suppliers (from rank step)
      non_compliant_suppliers: excluded suppliers (from compliance check)

    Output: policy_evaluation object matching example_output.json
    """
    currency = request_data.get("currency")
    budget_amount = request_data.get("budget_amount")

    all_suppliers = ranked_suppliers + non_compliant_suppliers

    approval = _evaluate_approval_threshold(currency, budget_amount, ranked_suppliers)
    preferred = _evaluate_preferred_supplier(request_data, ranked_suppliers)
    restricted = _evaluate_restricted_suppliers(request_data, all_suppliers)
    rules = _evaluate_applicable_rules(request_data)

    return {
        "approval_threshold": approval,
        "preferred_supplier": preferred,
        "restricted_suppliers": restricted,
        **rules,
    }


def main():
    if len(sys.argv) == 1:
        input_data = json.load(sys.stdin)
        request_data = input_data["request_data"]
        ranked_suppliers = input_data.get("ranked_suppliers", [])
        non_compliant_suppliers = input_data.get("non_compliant_suppliers", [])
        result = evaluate_policy(request_data, ranked_suppliers, non_compliant_suppliers)
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        return

    print(
        f"Usage: {sys.argv[0]}\n"
        f"  No args — read JSON from stdin, write result to stdout",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
