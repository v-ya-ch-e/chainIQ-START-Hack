"""Rank suppliers by true cost -- the effective price adjusted for quality, risk, and ESG.

API-friendly: importable as a module, or callable via stdin/stdout for subprocess use.
Still supports the original CLI file-based mode for backward compatibility.
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


def resolve_region(request_data):
    delivery_countries = request_data.get("delivery_countries", [])
    if delivery_countries and isinstance(delivery_countries[0], dict):
        delivery_countries = [c.get("country_code", "") for c in delivery_countries]
    country = delivery_countries[0] if delivery_countries else request_data.get("country", "")
    return COUNTRY_TO_REGION.get(country, "EU")


def compute_true_cost(total_price, quality_score, risk_score, esg_score, esg_requirement):
    """Effective price inflated by quality gaps and risk exposure.

    Formula: total_price / (quality_score/100) / ((100 - risk_score)/100)
    With ESG:              / (esg_score/100)

    Lower = better. Units are currency (EUR, CHF, USD).
    Difference (true_cost - total_price) is the hidden cost of quality/risk.
    """
    if total_price is None or total_price == 0:
        return None
    cost = total_price / (quality_score / 100) / ((100 - risk_score) / 100)
    if esg_requirement:
        cost /= esg_score / 100
    return round(cost, 2)


def rank_suppliers(request_data: dict, suppliers: list) -> dict:
    """Core logic: takes a purchase request dict and supplier list, returns ranked results.

    Input:
      request_data: { "category_l1": "...", "category_l2": "...", "quantity": N, ... }
      suppliers:    [ { "supplier_id": "...", "quality_score": N, ... }, ... ]

    Output: { "ranked": [...], "category_l1": "...", "category_l2": "...", "count": N }
    """
    category_l1 = request_data["category_l1"]
    category_l2 = request_data["category_l2"]
    quantity = request_data.get("quantity")
    esg_requirement = request_data.get("esg_requirement", False)
    region = resolve_region(request_data)

    results = []

    for sup in suppliers:
        quality_score = sup["quality_score"]
        risk_score = sup["risk_score"]
        esg_score = sup["esg_score"]
        supplier_id = sup["supplier_id"]

        if quantity is None:
            results.append({
                "supplier_id": supplier_id,
                "true_cost": None,
                "overpayment": None,
                "quality_score": quality_score,
                "risk_score": risk_score,
                "esg_score": esg_score,
                "total_price": None,
                "unit_price": None,
                "currency": None,
                "standard_lead_time_days": None,
                "expedited_lead_time_days": None,
                "preferred_supplier": sup.get("preferred_supplier", False),
                "is_restricted": sup.get("is_restricted", False),
            })
            continue

        pricing = api_get("/api/analytics/pricing-lookup", {
            "supplier_id": supplier_id,
            "category_l1": category_l1,
            "category_l2": category_l2,
            "region": region,
            "quantity": int(quantity),
        })

        if not pricing:
            continue

        tier = pricing[0]
        total_price = float(tier["total_price"])
        unit_price = float(tier["unit_price"])
        true_cost = compute_true_cost(total_price, quality_score, risk_score, esg_score, esg_requirement)
        overpayment = round(true_cost - total_price, 2) if true_cost is not None else None

        results.append({
            "supplier_id": supplier_id,
            "true_cost": true_cost,
            "overpayment": overpayment,
            "quality_score": quality_score,
            "risk_score": risk_score,
            "esg_score": esg_score,
            "total_price": total_price,
            "unit_price": unit_price,
            "currency": tier.get("currency"),
            "standard_lead_time_days": tier.get("standard_lead_time_days"),
            "expedited_lead_time_days": tier.get("expedited_lead_time_days"),
            "preferred_supplier": sup.get("preferred_supplier", False),
            "is_restricted": sup.get("is_restricted", False),
        })

    if quantity is None:
        results.sort(key=lambda r: r["quality_score"], reverse=True)
    else:
        results.sort(key=lambda r: r["true_cost"] or float("inf"))

    for i, row in enumerate(results, start=1):
        row["rank"] = i

    return {
        "ranked": results,
        "category_l1": category_l1,
        "category_l2": category_l2,
        "count": len(results),
    }


def main():
    if len(sys.argv) == 1:
        input_data = json.load(sys.stdin)
        request_data = input_data["request"]
        suppliers = input_data["suppliers"]
        result = rank_suppliers(request_data, suppliers)
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        return

    if len(sys.argv) == 4:
        request_path = sys.argv[1]
        suppliers_path = sys.argv[2]
        output_path = sys.argv[3]
        with open(request_path, "r", encoding="utf-8") as f:
            request_data = json.load(f)
        with open(suppliers_path, "r", encoding="utf-8") as f:
            suppliers = json.load(f)
        result = rank_suppliers(request_data, suppliers)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Ranked {result['count']} supplier(s) for {result['category_l1']} / {result['category_l2']}")
        print(f"Output written to {output_path}")
        return

    print(
        f"Usage: {sys.argv[0]} [<request.json> <suppliers.json> <output.json>]\n"
        f"  No args  — read JSON from stdin ({{\"request\": ..., \"suppliers\": [...]}}), write result to stdout\n"
        f"  3 args   — read/write from files (original mode)",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
