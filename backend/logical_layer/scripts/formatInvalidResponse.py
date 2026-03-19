"""Format a structured response for invalid/incomplete purchase requests.

Used on the "Invalid request" branch of the n8n pipeline when validation fails.
Uses Claude LLM to generate a human-readable summary and enriched issue descriptions.

API-friendly: importable as a module, or callable via stdin/stdout for subprocess use.
Requires: ANTHROPIC_API_KEY environment variable.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ANTHROPIC_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a procurement system that explains validation failures to requesters. \
Given a purchase request and its validation issues, produce a clear, actionable summary.

You will receive a JSON object with the request data, validation issues, and \
request interpretation.

Produce ONLY a JSON object (no markdown fencing) with:
{
  "summary": "<2-4 sentence human-readable summary of all issues and what the requester must do>",
  "enriched_issues": [
    {
      "issue_id": "V-001",
      "severity": "critical|high|medium|low",
      "type": "<issue type>",
      "description": "<detailed description>",
      "action_required": "<specific action the requester must take>"
    }
  ]
}

Rules:
- severity: critical = blocks everything, high = must fix, medium = should fix, low = informational
- Be specific and reference exact field names and values
- Keep the summary concise but complete\
"""


def _llm_format(request_data, validation, interpretation):
    """Use Claude to generate enriched issue descriptions and summary."""
    try:
        client = anthropic.Anthropic()

        payload = {
            "request_data": {
                k: v for k, v in request_data.items()
                if k in ("request_id", "title", "request_text", "category_l1", "category_l2",
                         "currency", "budget_amount", "quantity", "required_by_date",
                         "preferred_supplier_mentioned", "delivery_countries")
            },
            "validation_issues": validation.get("issues", []),
            "request_interpretation": interpretation,
        }

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
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

    return None


def format_invalid_response(request_data: dict, validation: dict, interpretation: dict) -> dict:
    """Core logic: format a structured response for an invalid request.

    Input:
      request_data: full purchase request dict
      validation: { "completeness": bool, "issues": [...] }
      interpretation: request_interpretation from validate step

    Output: structured invalid-request response with escalation routing
    """
    request_id = request_data.get("request_id", "")
    issues = validation.get("issues", [])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    llm_result = _llm_format(request_data, validation, interpretation)

    if llm_result:
        enriched_issues = llm_result.get("enriched_issues", [])
        summary = llm_result.get("summary", "")
    else:
        enriched_issues = [
            {
                "issue_id": f"V-{i:03d}",
                "severity": "high" if issue.get("type") in ("missing_required", "contradictory") else "medium",
                "type": issue.get("type", "unknown"),
                "description": issue.get("message", ""),
                "action_required": "Review and provide the missing or corrected information.",
            }
            for i, issue in enumerate(issues, start=1)
        ]
        summary = f"Request {request_id} has {len(issues)} validation issue(s) that must be resolved before processing can continue."

    has_missing_required = any(i.get("type") == "missing_required" for i in issues)

    escalations = []
    if has_missing_required:
        escalations.append({
            "escalation_id": "ESC-001",
            "rule": "ER-001",
            "trigger": "Missing required information prevents autonomous processing.",
            "escalate_to": "Requester Clarification",
            "blocking": True,
        })

    return {
        "request_id": request_id,
        "processed_at": now,
        "status": "invalid",
        "validation": {
            "completeness": "fail",
            "issues_detected": enriched_issues,
        },
        "request_interpretation": interpretation,
        "escalations": escalations,
        "recommendation": {
            "status": "cannot_proceed",
            "reason": summary,
        },
        "summary": summary,
    }


def main():
    if len(sys.argv) == 1:
        input_data = json.load(sys.stdin)
        request_data = input_data.get("request_data", {})
        validation = input_data.get("validation", {})
        interpretation = input_data.get("request_interpretation", {})
        result = format_invalid_response(request_data, validation, interpretation)
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
