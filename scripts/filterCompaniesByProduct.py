"""Filter suppliers from the database to those serving the same category as a purchase request."""

import json
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "http://18.197.20.103:8000"


def api_get(path, params=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        print(f"Error reaching API at {url}: {e}", file=sys.stderr)
        sys.exit(1)


def resolve_category_id(category_l1, category_l2):
    categories = api_get("/api/categories")
    for cat in categories:
        if cat["category_l1"] == category_l1 and cat["category_l2"] == category_l2:
            return cat["id"]
    print(
        f"Category not found: {category_l1} / {category_l2}",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <input_request.json> <output_suppliers.json>",
            file=sys.stderr,
        )
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, "r", encoding="utf-8") as f:
        request_data = json.load(f)

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

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(matching_rows, f, indent=2, ensure_ascii=False)

    print(f"Found {len(matching_rows)} supplier(s) for {category_l1} / {category_l2}")
    print(f"Output written to {output_path}")


if __name__ == "__main__":
    main()
