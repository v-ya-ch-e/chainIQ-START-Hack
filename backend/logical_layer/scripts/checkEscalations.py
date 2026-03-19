"""Fetch computed escalations for a purchase request from the Organisational Layer.

The Org Layer's escalation engine evaluates ER-001 through ER-008 plus AT threshold
conflict detection. This script simply retrieves those computed results.

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


def check_escalations(request_id: str) -> dict:
    """Core logic: fetch escalations for a request from the Org Layer.

    Input:  request_id string (e.g. "REQ-000004")
    Output: {
      "request_id": "...",
      "escalations": [...],
      "has_blocking": bool,
      "count": N
    }
    """
    try:
        escalations = api_get(f"/api/escalations/by-request/{request_id}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {
                "request_id": request_id,
                "escalations": [],
                "has_blocking": False,
                "count": 0,
            }
        raise

    formatted = []
    for i, esc in enumerate(escalations, start=1):
        formatted.append({
            "escalation_id": esc.get("escalation_id", f"ESC-{i:03d}"),
            "rule": esc.get("rule_id", ""),
            "rule_label": esc.get("rule_label", ""),
            "trigger": esc.get("trigger", ""),
            "escalate_to": esc.get("escalate_to", ""),
            "blocking": esc.get("blocking", False),
            "status": esc.get("status", "open"),
        })

    has_blocking = any(e["blocking"] for e in formatted)

    return {
        "request_id": request_id,
        "escalations": formatted,
        "has_blocking": has_blocking,
        "count": len(formatted),
    }


def main():
    if len(sys.argv) == 1:
        input_data = json.load(sys.stdin)
        request_id = input_data["request_id"]
        result = check_escalations(request_id)
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        return

    if len(sys.argv) == 2:
        result = check_escalations(sys.argv[1])
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        return

    print(
        f"Usage: {sys.argv[0]} [<request_id>]\n"
        f"  No args  — read JSON from stdin ({{\"request_id\": \"...\"}})  , write result to stdout\n"
        f"  1 arg    — pass request_id directly, write result to stdout",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
