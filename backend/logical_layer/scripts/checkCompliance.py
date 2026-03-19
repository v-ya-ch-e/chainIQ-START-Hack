"""Check compliance rules for each supplier against a purchase request context.

Splits suppliers into compliant and non-compliant lists with reasons.
Checks: restriction status (with conditional logic), delivery country coverage,
and data residency support.

API-friendly: importable as a module, or callable via stdin/stdout for subprocess use.
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = os.environ.get("ORGANISATIONAL_LAYER_URL", "http://3.68.96.236:8000")


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


def _check_single_supplier(supplier, request_data, compliant_supplier_ids):
    """Check a single supplier against compliance rules.

    Returns (is_compliant, reason_if_excluded, detail).
    """
    supplier_id = supplier["supplier_id"]
    category_l1 = request_data["category_l1"]
    category_l2 = request_data["category_l2"]

    delivery_countries = _normalize_delivery_countries(
        request_data.get("delivery_countries") or []
    )
    primary_country = delivery_countries[0] if delivery_countries else request_data.get("country", "")

    reasons = []

    if compliant_supplier_ids is not None and supplier_id not in compliant_supplier_ids:
        reasons.append(f"Does not cover delivery country {primary_country} for {category_l1}/{category_l2}")

    try:
        restriction = api_get("/api/analytics/check-restricted", {
            "supplier_id": supplier_id,
            "category_l1": category_l1,
            "category_l2": category_l2,
            "delivery_country": primary_country,
        })
        if restriction.get("is_restricted"):
            detail = restriction.get("restriction_reason") or "Policy restriction"
            reasons.append(f"Restricted: {detail}")
    except urllib.error.HTTPError:
        pass

    data_residency_required = request_data.get("data_residency_constraint", False)
    if data_residency_required and not supplier.get("data_residency_supported", False):
        reasons.append("Does not support required data residency")

    if reasons:
        return False, "; ".join(reasons), reasons
    return True, None, []


def check_compliance(request_data: dict, suppliers: list) -> dict:
    """Core logic: check each supplier for compliance with request context.

    Input:
      request_data: { "category_l1", "category_l2", "delivery_countries", ... }
      suppliers:    [ { "supplier_id", "quality_score", ... }, ... ]

    Output: {
      "compliant": [...suppliers with compliance_notes...],
      "non_compliant": [...suppliers with exclusion_reason...],
      "total_checked": N,
      "compliant_count": N,
      "non_compliant_count": N
    }
    """
    category_l1 = request_data["category_l1"]
    category_l2 = request_data["category_l2"]
    delivery_countries = _normalize_delivery_countries(
        request_data.get("delivery_countries") or []
    )
    primary_country = delivery_countries[0] if delivery_countries else request_data.get("country", "")

    compliant_supplier_ids = None
    if primary_country:
        try:
            compliant_list = api_get("/api/analytics/compliant-suppliers", {
                "category_l1": category_l1,
                "category_l2": category_l2,
                "delivery_country": primary_country,
            })
            compliant_supplier_ids = {s["supplier_id"] for s in compliant_list}
        except urllib.error.HTTPError:
            pass

    compliant = []
    non_compliant = []

    for supplier in suppliers:
        is_ok, reason, _details = _check_single_supplier(
            supplier, request_data, compliant_supplier_ids
        )
        row = dict(supplier)
        if is_ok:
            row["compliance_notes"] = "Passes all compliance checks"
            compliant.append(row)
        else:
            row["exclusion_reason"] = reason
            non_compliant.append(row)

    return {
        "compliant": compliant,
        "non_compliant": non_compliant,
        "total_checked": len(suppliers),
        "compliant_count": len(compliant),
        "non_compliant_count": len(non_compliant),
    }


def main():
    if len(sys.argv) == 1:
        input_data = json.load(sys.stdin)
        request_data = input_data["request_data"]
        suppliers = input_data["suppliers"]
        result = check_compliance(request_data, suppliers)
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        return

    print(
        f"Usage: {sys.argv[0]}\n"
        f"  No args — read JSON from stdin ({{\"request_data\": ..., \"suppliers\": [...]}}), write result to stdout",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
