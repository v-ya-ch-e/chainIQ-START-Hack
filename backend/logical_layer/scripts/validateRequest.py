"""Validate a purchase request for completeness and internal consistency.

Uses deterministic checks for required fields and the Anthropic API to detect
discrepancies between the free-text request_text and the structured fields.

API-friendly: importable as a module, or callable via stdin/stdout for subprocess use.
Still supports the original CLI file-based mode for backward compatibility.

Requires: ANTHROPIC_API_KEY environment variable.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REQUIRED_FIELDS = [
    "request_id", "created_at", "request_channel", "request_language",
    "business_unit", "country", "category_l1", "category_l2",
    "title", "request_text", "currency", "status",
]

COMPLETENESS_FIELDS = [
    "quantity", "budget_amount", "required_by_date",
    "unit_of_measure", "delivery_countries",
]

ANTHROPIC_MODEL = "claude-sonnet-4-6"


def _deterministic_checks(data: dict) -> list[dict]:
    issues = []
    for field in REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            issues.append({
                "field": field,
                "type": "missing_required",
                "message": f"Required field '{field}' is missing or null.",
            })
    for field in COMPLETENESS_FIELDS:
        if field not in data or data[field] is None:
            issues.append({
                "field": field,
                "type": "missing_optional",
                "message": f"Field '{field}' is missing or null — request is incomplete.",
            })
        elif field == "delivery_countries" and isinstance(data[field], list) and len(data[field]) == 0:
            issues.append({
                "field": field,
                "type": "missing_optional",
                "message": "delivery_countries is an empty list — request is incomplete.",
            })
    return issues


def _compute_days_until_required(created_at: str | None, required_by_date: str | None) -> int | None:
    if not created_at or not required_by_date:
        return None
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        required = datetime.strptime(required_by_date, "%Y-%m-%d")
        created_date = created.date()
        return (required.date() - created_date).days
    except (ValueError, TypeError):
        return None


def _normalize_delivery_countries(raw: list) -> list[str]:
    """Accept both ["DE"] and [{"country_code": "DE"}] formats."""
    if not raw:
        return []
    if isinstance(raw[0], dict):
        return [c.get("country_code", "") for c in raw]
    return raw


def _build_interpretation(data: dict) -> dict:
    delivery_countries = _normalize_delivery_countries(data.get("delivery_countries") or [])
    delivery_country = delivery_countries[0] if delivery_countries else data.get("country")

    return {
        "category_l1": data.get("category_l1"),
        "category_l2": data.get("category_l2"),
        "quantity": data.get("quantity"),
        "unit_of_measure": data.get("unit_of_measure"),
        "budget_amount": data.get("budget_amount"),
        "currency": data.get("currency"),
        "delivery_country": delivery_country,
        "required_by_date": data.get("required_by_date"),
        "days_until_required": _compute_days_until_required(
            data.get("created_at"), data.get("required_by_date")
        ),
        "data_residency_required": data.get("data_residency_constraint", False),
        "esg_requirement": data.get("esg_requirement", False),
        "preferred_supplier_stated": data.get("preferred_supplier_mentioned"),
        "incumbent_supplier": data.get("incumbent_supplier"),
        "requester_instruction": None,
    }


SYSTEM_PROMPT = """\
You are a procurement data-quality auditor. You receive a JSON purchase request \
containing structured fields and a free-text `request_text` (which may be in any \
language: en, fr, de, es, pt, ja).

Your job is to find ONLY major issues. There are exactly two types:

1. "missing_info" — A critical field (quantity, budget_amount, currency, \
   required_by_date, category_l1, category_l2, delivery_countries) is null or \
   missing, OR the request_text mentions information that has no corresponding \
   structured field filled in.

2. "contradictory" — The request_text CLEARLY states a value that DIRECTLY \
   CONTRADICTS the corresponding structured field. Specifically:
   - Quantity in text differs from `quantity` field
   - Budget/price in text differs from `budget_amount` field
   - Date in text differs from `required_by_date` field
   - Currency in text differs from `currency` field
   - Category described in text doesn't match `category_l1`/`category_l2`

THINGS THAT ARE NOT CONTRADICTIONS — do NOT flag these:
- preferred_supplier_mentioned differing from incumbent_supplier (these are \
  intentionally different fields — preferred is who the requester wants, \
  incumbent is the current supplier)
- Requester requesting a specific supplier (this is normal, not a contradiction)
- Urgency, tight deadlines, or policy concerns (not your job here)
- Threshold proximity, lead time, capacity, or supplier restriction issues

Also extract any explicit requester instruction or constraint from the free text \
(e.g. "no exception", "must use X", "expedite"). Summarise as a short phrase. \
If none, return null.

CRITICAL RULES:
- Do NOT invent or infer issues. Only flag what is clearly wrong.
- Be conservative: when in doubt, do NOT flag.
- If request_text is in a non-English language, translate relevant parts in your \
  descriptions.

Respond with ONLY a JSON object (no markdown fencing):
{
  "issues": [
    {
      "field": "<structured field name>",
      "type": "<missing_info or contradictory>",
      "message": "<human-readable explanation>"
    }
  ],
  "requester_instruction": "<short phrase or null>"
}

If no issues, return an empty array for "issues".\
"""


def _llm_checks(data: dict) -> tuple[list[dict], str | None]:
    """Call the Anthropic API to detect discrepancies and extract instructions.

    Returns (issues_list, requester_instruction).
    """
    client = anthropic.Anthropic()

    user_content = json.dumps(data, indent=2, ensure_ascii=False)

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    if not raw:
        return [], None

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return [], None
    raw = raw[start:end]

    result = json.loads(raw)

    issues = []
    for d in result.get("issues", []):
        issues.append({
            "field": d.get("field"),
            "type": d.get("type", "unknown"),
            "message": d.get("message", ""),
        })

    requester_instruction = result.get("requester_instruction")
    return issues, requester_instruction


def validate_request(request_data: dict) -> dict:
    """Core logic: takes a purchase request dict, returns a validation result dict.

    Input:  a purchase request dict (same structure as examples/example_request.json)
    Output: { "completeness": bool, "issues": [...], "request_interpretation": {...} }
    """
    deterministic_issues = _deterministic_checks(request_data)

    llm_issues, requester_instruction = _llm_checks(request_data)

    all_issues = deterministic_issues + llm_issues
    completeness = len(all_issues) == 0

    interpretation = _build_interpretation(request_data)
    interpretation["requester_instruction"] = requester_instruction

    return {
        "completeness": completeness,
        "issues": all_issues,
        "request_interpretation": interpretation,
    }


def main():
    if len(sys.argv) == 1:
        request_data = json.load(sys.stdin)
        result = validate_request(request_data)
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        return

    if len(sys.argv) in (2, 3):
        input_path = sys.argv[1]
        with open(input_path, "r", encoding="utf-8") as f:
            request_data = json.load(f)

        result = validate_request(request_data)

        if len(sys.argv) == 3:
            output_path = sys.argv[2]
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            status = "COMPLETE" if result["completeness"] else "INCOMPLETE"
            print(f"[{status}] {len(result['issues'])} issue(s) found for {request_data.get('request_id', '?')}")
            print(f"Output written to {output_path}")
        else:
            json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        return

    print(
        f"Usage: {sys.argv[0]} [<input_request.json> [output.json]]\n"
        f"  No args  — read request JSON from stdin, write result JSON to stdout\n"
        f"  1 arg    — read from file, write result JSON to stdout\n"
        f"  2 args   — read from file, write result to output file",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
