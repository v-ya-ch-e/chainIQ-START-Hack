"""Filter suppliers from the database to those serving the same category as a purchase request.

API-friendly: importable as a module, or callable via stdin/stdout for subprocess use.
Still supports the original CLI file-based mode for backward compatibility.
"""

import json
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "http://3.68.96.236:8000"


def api_get(path, params=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def resolve_category_id(category_l1, category_l2):
    categories = api_get("/api/categories")
    for cat in categories:
        if cat["category_l1"] == category_l1 and cat["category_l2"] == category_l2:
            return cat["id"]
    raise ValueError(f"Category not found: {category_l1} / {category_l2}")


def filter_suppliers(request_data: dict) -> dict:
    """Core logic: takes a purchase request dict, returns a result dict.

    Input:  { "category_l1": "...", "category_l2": "...", ... }
    Output: { "suppliers": [...], "category_l1": "...", "category_l2": "...", "count": N }
    """
    category_l1 = request_data["category_l1"]
    category_l2 = request_data["category_l2"]

    category_id = resolve_category_id(category_l1, category_l2)

    suppliers = api_get("/api/suppliers", {"category_l1": category_l1})

    matching_rows = []
    for supplier in suppliers:
        sid = supplier["supplier_id"]
        cat_rows = api_get(f"/api/suppliers/{sid}/categories")
        for row in cat_rows:
            if row["category_id"] == category_id:
                matching_rows.append(row)

    return {
        "suppliers": matching_rows,
        "category_l1": category_l1,
        "category_l2": category_l2,
        "count": len(matching_rows),
    }


def main():
    if len(sys.argv) == 1:
        request_data = json.load(sys.stdin)
        result = filter_suppliers(request_data)
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        return

    if len(sys.argv) == 3:
        input_path = sys.argv[1]
        output_path = sys.argv[2]
        with open(input_path, "r", encoding="utf-8") as f:
            request_data = json.load(f)
        result = filter_suppliers(request_data)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Found {result['count']} supplier(s) for {result['category_l1']} / {result['category_l2']}")
        print(f"Output written to {output_path}")
        return

    print(
        f"Usage: {sys.argv[0]} [<input_request.json> <output_suppliers.json>]\n"
        f"  No args  — read request JSON from stdin, write result JSON to stdout\n"
        f"  2 args   — read/write from files (original mode)",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
