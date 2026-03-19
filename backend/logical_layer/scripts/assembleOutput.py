"""Assemble all pipeline step outputs into the final output format.

Combines validation, policy evaluation, ranked suppliers, excluded suppliers,
escalations, and recommendation into the structure defined by example_output.json.
Uses Claude LLM to enrich supplier shortlist entries with recommendation notes
and validation issues with severity/action_required.

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

ENRICHMENT_PROMPT = """\
You are a procurement audit analyst. Given pipeline data for a purchase request, \
produce enriched output sections.

You will receive a JSON object with the full pipeline context. Produce ONLY a JSON \
object (no markdown fencing) with:

{
  "enriched_validation_issues": [
    {
      "issue_id": "V-001",
      "severity": "critical|high|medium|low",
      "type": "<original type or a more specific type like budget_insufficient, lead_time_infeasible, policy_conflict>",
      "description": "<detailed human-readable description with specific numbers>",
      "action_required": "<what the requester or procurement team must do>"
    }
  ],
  "enriched_supplier_shortlist": [
    {
      "supplier_id": "SUP-0001",
      "recommendation_note": "<1-2 sentence note with specific prices, lead times, and comparison to other suppliers>"
    }
  ]
}

Rules:
- For validation issues: convert each issue from the validation step into an enriched \
  form. Use data from ranked suppliers and policy evaluation to add specificity \
  (exact prices, lead times, threshold IDs). Assign severity: \
  critical = blocks procurement entirely, high = requires escalation, \
  medium = needs attention, low = informational.
- For supplier notes: reference specific numbers (price, lead time, quality score). \
  Compare to the top-ranked supplier. Note preferred/incumbent status.
- Be concise but specific. Reference exact figures.\
"""


def _enrich_via_llm(pipeline_data):
    """Use Claude to enrich validation issues and supplier notes."""
    try:
        client = anthropic.Anthropic()

        context = {
            "request_interpretation": pipeline_data.get("request_interpretation", {}),
            "validation_issues": pipeline_data.get("validation", {}).get("issues", []),
            "ranked_suppliers": pipeline_data.get("ranked_suppliers", [])[:5],
            "non_compliant_suppliers": pipeline_data.get("non_compliant_suppliers", [])[:5],
            "policy_evaluation": pipeline_data.get("policy_evaluation", {}),
            "escalations": pipeline_data.get("escalations", []),
        }

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2048,
            system=ENRICHMENT_PROMPT,
            messages=[{"role": "user", "content": json.dumps(context, indent=2, ensure_ascii=False)}],
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


def _build_validation_section(pipeline_data, enrichment):
    """Build the enriched validation section."""
    validation = pipeline_data.get("validation", {})
    issues = validation.get("issues", [])

    if enrichment and enrichment.get("enriched_validation_issues"):
        return {
            "completeness": "pass" if not issues else "fail",
            "issues_detected": enrichment["enriched_validation_issues"],
        }

    enriched = []
    for i, issue in enumerate(issues, start=1):
        enriched.append({
            "issue_id": f"V-{i:03d}",
            "severity": "high" if issue.get("type") in ("missing_required", "contradictory") else "medium",
            "type": issue.get("type", "unknown"),
            "description": issue.get("message", ""),
            "action_required": "Review and resolve before proceeding.",
        })

    return {
        "completeness": "pass" if not issues else "fail",
        "issues_detected": enriched,
    }


def _build_supplier_shortlist(pipeline_data, enrichment):
    """Build the enriched supplier shortlist."""
    ranked = pipeline_data.get("ranked_suppliers", [])
    interpretation = pipeline_data.get("request_interpretation", {})

    note_map = {}
    if enrichment and enrichment.get("enriched_supplier_shortlist"):
        for entry in enrichment["enriched_supplier_shortlist"]:
            note_map[entry["supplier_id"]] = entry.get("recommendation_note", "")

    shortlist = []
    for sup in ranked:
        supplier_id = sup.get("supplier_id", "")
        supplier_name = sup.get("supplier_name", supplier_id)

        preferred_stated = interpretation.get("preferred_supplier_stated", "")
        incumbent = interpretation.get("incumbent_supplier", "")
        is_preferred = sup.get("preferred_supplier", False)
        is_incumbent = bool(incumbent and incumbent.lower() in supplier_name.lower())

        currency = sup.get("currency", interpretation.get("currency", "EUR"))

        entry = {
            "rank": sup.get("rank"),
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "preferred": is_preferred,
            "incumbent": is_incumbent,
            "pricing_tier_applied": sup.get("pricing_tier_applied"),
            f"unit_price_{currency.lower()}": sup.get("unit_price"),
            f"total_price_{currency.lower()}": sup.get("total_price"),
            "standard_lead_time_days": sup.get("standard_lead_time_days"),
            "expedited_lead_time_days": sup.get("expedited_lead_time_days"),
            "expedited_unit_price": sup.get("expedited_unit_price"),
            "expedited_total": sup.get("expedited_total"),
            "quality_score": sup.get("quality_score"),
            "risk_score": sup.get("risk_score"),
            "esg_score": sup.get("esg_score"),
            "policy_compliant": True,
            "covers_delivery_country": True,
            "recommendation_note": note_map.get(supplier_id, ""),
        }
        shortlist.append(entry)

    return shortlist


def _build_suppliers_excluded(pipeline_data):
    """Build the excluded suppliers list."""
    non_compliant = pipeline_data.get("non_compliant_suppliers", [])
    excluded = []
    for sup in non_compliant:
        excluded.append({
            "supplier_id": sup.get("supplier_id", ""),
            "supplier_name": sup.get("supplier_name", sup.get("supplier_id", "")),
            "reason": sup.get("exclusion_reason", "Excluded during compliance check"),
        })
    return excluded


def _build_escalations_section(pipeline_data):
    """Build the escalations section."""
    escalations = pipeline_data.get("escalations", [])
    return [
        {
            "escalation_id": e.get("escalation_id", f"ESC-{i:03d}"),
            "rule": e.get("rule", e.get("rule_id", "")),
            "trigger": e.get("trigger", ""),
            "escalate_to": e.get("escalate_to", ""),
            "blocking": e.get("blocking", False),
        }
        for i, e in enumerate(escalations, start=1)
    ]


def _build_audit_trail(pipeline_data):
    """Build the audit trail from collected metadata."""
    policy_eval = pipeline_data.get("policy_evaluation", {})
    ranked = pipeline_data.get("ranked_suppliers", [])
    escalations = pipeline_data.get("escalations", [])
    historical = pipeline_data.get("historical_awards", [])

    policies_checked = set()

    approval = policy_eval.get("approval_threshold", {})
    if approval.get("rule_applied"):
        policies_checked.add(approval["rule_applied"])

    for esc in escalations:
        rule = esc.get("rule", esc.get("rule_id", ""))
        if rule:
            policies_checked.add(rule)

    for rule in policy_eval.get("category_rules_applied", []):
        rid = rule.get("rule_id", "")
        if rid:
            policies_checked.add(rid)
    for rule in policy_eval.get("geography_rules_applied", []):
        rid = rule.get("rule_id", "")
        if rid:
            policies_checked.add(rid)

    supplier_ids = [s.get("supplier_id") for s in ranked if s.get("supplier_id")]
    non_compliant = pipeline_data.get("non_compliant_suppliers", [])
    supplier_ids += [s.get("supplier_id") for s in non_compliant if s.get("supplier_id")]

    interpretation = pipeline_data.get("request_interpretation", {})
    currency = interpretation.get("currency", "EUR")
    quantity = interpretation.get("quantity")
    pricing_desc = "N/A"
    if quantity and ranked:
        pricing_desc = f"Quantity {quantity} ({interpretation.get('delivery_country', 'unknown')} region, {currency} currency)"

    has_historical = bool(historical)
    historical_note = None
    if historical:
        award_ids = [a.get("award_id", "") for a in historical[:5]]
        historical_note = f"Historical awards consulted: {', '.join(award_ids)}."

    return {
        "policies_checked": sorted(policies_checked),
        "supplier_ids_evaluated": sorted(set(supplier_ids)),
        "pricing_tiers_applied": pricing_desc,
        "data_sources_used": ["requests", "suppliers", "pricing", "policies", "categories"],
        "historical_awards_consulted": has_historical,
        "historical_award_note": historical_note,
    }


def assemble_output(pipeline_data: dict) -> dict:
    """Core logic: assemble all step outputs into the final pipeline output.

    Input: {
      "request_id": "...",
      "request_data": { ... },
      "validation": { "completeness": bool, "issues": [...] },
      "request_interpretation": { ... },
      "ranked_suppliers": [...],
      "non_compliant_suppliers": [...],
      "policy_evaluation": { ... },
      "escalations": [...],
      "recommendation": { ... },
      "historical_awards": [...]  (optional)
    }

    Output: Complete pipeline output matching example_output.json
    """
    enrichment = _enrich_via_llm(pipeline_data)

    request_id = pipeline_data.get("request_id", "")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "request_id": request_id,
        "processed_at": now,
        "request_interpretation": pipeline_data.get("request_interpretation", {}),
        "validation": _build_validation_section(pipeline_data, enrichment),
        "policy_evaluation": pipeline_data.get("policy_evaluation", {}),
        "supplier_shortlist": _build_supplier_shortlist(pipeline_data, enrichment),
        "suppliers_excluded": _build_suppliers_excluded(pipeline_data),
        "escalations": _build_escalations_section(pipeline_data),
        "recommendation": pipeline_data.get("recommendation", {}),
        "audit_trail": _build_audit_trail(pipeline_data),
    }


def main():
    if len(sys.argv) == 1:
        input_data = json.load(sys.stdin)
        result = assemble_output(input_data)
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
