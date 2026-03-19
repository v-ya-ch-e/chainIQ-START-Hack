"""Generate a procurement recommendation based on escalations, ranked suppliers, and validation.

Determines status (cannot_proceed / proceed_with_conditions / proceed),
calculates minimum budget, identifies preferred supplier, and uses Claude LLM
to produce human-readable reasoning.

API-friendly: importable as a module, or callable via stdin/stdout for subprocess use.
Requires: ANTHROPIC_API_KEY environment variable.
"""

import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ANTHROPIC_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a procurement decision analyst. Given the escalation status, ranked supplier \
data, and validation results for a purchase request, produce a concise recommendation.

You will receive a JSON object with:
- "status": one of "cannot_proceed", "proceed_with_conditions", or "proceed"
- "escalations": list of triggered escalation rules
- "ranked_suppliers": ranked supplier shortlist
- "validation_issues": list of validation issues found
- "request_interpretation": structured interpretation of the request

Produce ONLY a JSON object (no markdown fencing) with these fields:
{
  "reason": "<1-3 sentence explanation of why this status was determined>",
  "preferred_supplier_rationale": "<1-2 sentence rationale for why the recommended supplier is best, or null if cannot_proceed>"
}

Be specific: reference exact supplier names, prices, rule IDs, and figures. \
Keep language professional and audit-ready.\
"""


def _determine_status(escalations):
    """Determine recommendation status from escalations."""
    if not escalations:
        return "proceed"
    has_blocking = any(e.get("blocking", False) for e in escalations)
    if has_blocking:
        return "cannot_proceed"
    return "proceed_with_conditions"


def _find_minimum_budget(ranked_suppliers):
    """Find the minimum total price across ranked suppliers."""
    prices = [s["total_price"] for s in ranked_suppliers
              if s.get("total_price") is not None]
    if not prices:
        return None
    return min(prices)


def _find_preferred_supplier(ranked_suppliers, interpretation):
    """Identify the best supplier to recommend if issues are resolved."""
    if not ranked_suppliers:
        return None

    preferred_name = interpretation.get("preferred_supplier_stated")
    incumbent_name = interpretation.get("incumbent_supplier")

    for s in ranked_suppliers:
        name = s.get("supplier_name", "")
        if preferred_name and preferred_name.lower() in name.lower():
            return name
        if incumbent_name and incumbent_name.lower() in name.lower():
            return name

    return ranked_suppliers[0].get("supplier_name", ranked_suppliers[0].get("supplier_id"))


def _llm_reasoning(status, escalations, ranked_suppliers, validation_issues, interpretation):
    """Use Claude to generate human-readable reason and rationale."""
    try:
        client = anthropic.Anthropic()

        payload = {
            "status": status,
            "escalations": escalations,
            "ranked_suppliers": ranked_suppliers[:5],
            "validation_issues": validation_issues[:10],
            "request_interpretation": interpretation,
        }

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload, indent=2, ensure_ascii=False)}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > 0:
            return json.loads(raw[start:end])
    except Exception:
        pass

    return {
        "reason": f"Status: {status}. {len(escalations)} escalation(s) detected.",
        "preferred_supplier_rationale": None,
    }


def generate_recommendation(data: dict) -> dict:
    """Core logic: generate a recommendation from pipeline data.

    Input: {
      "escalations": [...],
      "ranked_suppliers": [...],
      "validation": { "completeness": bool, "issues": [...] },
      "request_interpretation": { ... }
    }

    Output: recommendation object matching example_output.json
    """
    escalations = data.get("escalations", [])
    ranked_suppliers = data.get("ranked_suppliers", [])
    validation = data.get("validation", {})
    interpretation = data.get("request_interpretation", {})

    validation_issues = validation.get("issues", [])

    status = _determine_status(escalations)
    min_budget = _find_minimum_budget(ranked_suppliers)
    preferred = _find_preferred_supplier(ranked_suppliers, interpretation)
    currency = interpretation.get("currency")

    llm_result = _llm_reasoning(
        status, escalations, ranked_suppliers, validation_issues, interpretation
    )

    recommendation = {
        "status": status,
        "reason": llm_result.get("reason", ""),
        "preferred_supplier_if_resolved": preferred,
        "preferred_supplier_rationale": llm_result.get("preferred_supplier_rationale"),
    }

    if min_budget is not None:
        recommendation["minimum_budget_required"] = min_budget
    if currency:
        recommendation["minimum_budget_currency"] = currency

    return recommendation


def main():
    if len(sys.argv) == 1:
        input_data = json.load(sys.stdin)
        result = generate_recommendation(input_data)
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
