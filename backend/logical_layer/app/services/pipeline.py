"""Procurement decision pipeline.

Orchestrates the full processing flow:
  1. Fetch data from the Organisational Layer
  2. Parse & interpret the request
  3. Validate completeness and consistency
  4. Apply procurement policies
  5. Find and price compliant suppliers
  6. Rank suppliers
  7. Determine escalations
  8. Build the final auditable output

Each stage is a separate function so it can be developed, tested, and
replaced independently.  Stages currently return placeholder data —
implement the real logic as needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.clients.organisational import org_client
from app.schemas.processing import (
    AuditTrail,
    Escalation,
    PolicyEvaluation,
    ProcessingResult,
    Recommendation,
    RequestInterpretation,
    SupplierExcluded,
    SupplierShortlistEntry,
    Validation,
    ValidationIssue,
)


async def fetch_overview(request_id: str) -> dict[str, Any]:
    """Stage 0: Pull the pre-assembled evaluation package from the org layer."""
    return await org_client.get_request_overview(request_id)


def interpret_request(overview: dict[str, Any]) -> RequestInterpretation:
    """Stage 1: Parse structured fields + free-text into a unified interpretation.

    TODO: integrate LLM here to extract quantities, dates, and instructions
    from request_text — especially for multilingual requests.
    """
    req = overview["request"]
    delivery_countries: list[str] = req.get("delivery_countries", [])
    primary_country = delivery_countries[0] if delivery_countries else req.get("country", "")

    days_until: int | None = None
    if req.get("required_by_date"):
        try:
            rbd = datetime.fromisoformat(req["required_by_date"]).date()
            days_until = (rbd - datetime.now(timezone.utc).date()).days
        except (ValueError, TypeError):
            pass

    quantity_raw = req.get("quantity")
    quantity = float(quantity_raw) if quantity_raw is not None else None

    budget_raw = req.get("budget_amount")
    budget = float(budget_raw) if budget_raw is not None else None

    return RequestInterpretation(
        category_l1=req.get("category_l1", ""),
        category_l2=req.get("category_l2", ""),
        quantity=quantity,
        unit_of_measure=req.get("unit_of_measure"),
        budget_amount=budget,
        currency=req.get("currency", ""),
        delivery_country=primary_country,
        required_by_date=req.get("required_by_date"),
        days_until_required=days_until,
        data_residency_required=req.get("data_residency_constraint", False),
        esg_requirement=req.get("esg_requirement", False),
        preferred_supplier_stated=req.get("preferred_supplier_mentioned"),
        incumbent_supplier=req.get("incumbent_supplier"),
        requester_instruction=None,  # TODO: extract from request_text via LLM
    )


def validate_request(
    interpretation: RequestInterpretation,
    overview: dict[str, Any],
) -> Validation:
    """Stage 2: Detect missing info, contradictions, budget/lead-time issues.

    TODO: implement full validation logic (budget sufficiency, lead-time
    feasibility, quantity vs text contradictions, etc.)
    """
    issues: list[ValidationIssue] = []

    if interpretation.budget_amount is None:
        issues.append(
            ValidationIssue(
                issue_id="V-001",
                severity="critical",
                type="missing_info",
                description="Budget amount is missing from the request.",
                action_required="Requester must provide a budget amount.",
            )
        )

    if interpretation.quantity is None:
        issues.append(
            ValidationIssue(
                issue_id="V-002",
                severity="critical",
                type="missing_info",
                description="Quantity is missing from the request.",
                action_required="Requester must provide a quantity.",
            )
        )

    completeness = "fail" if any(i.severity == "critical" for i in issues) else "pass"

    return Validation(completeness=completeness, issues_detected=issues)


def evaluate_policies(
    interpretation: RequestInterpretation,
    overview: dict[str, Any],
) -> PolicyEvaluation:
    """Stage 3: Determine approval tier, check preferred/restricted, apply rules.

    TODO: implement full policy evaluation logic.
    """
    return PolicyEvaluation(
        approval_threshold=None,
        preferred_supplier=None,
        restricted_suppliers={},
        category_rules_applied=overview.get("applicable_rules", {}).get("category_rules", []),
        geography_rules_applied=overview.get("applicable_rules", {}).get("geography_rules", []),
    )


def build_supplier_shortlist(
    interpretation: RequestInterpretation,
    overview: dict[str, Any],
) -> tuple[list[SupplierShortlistEntry], list[SupplierExcluded]]:
    """Stages 4 & 5: Filter, price, and rank compliant suppliers.

    TODO: implement scoring algorithm with weighted price/quality/risk/ESG/lead-time.
    """
    shortlist: list[SupplierShortlistEntry] = []
    excluded: list[SupplierExcluded] = []

    # Placeholder: return raw compliant suppliers from the overview as-is
    for rank, supplier in enumerate(overview.get("compliant_suppliers", []), start=1):
        shortlist.append(
            SupplierShortlistEntry(
                rank=rank,
                supplier_id=supplier.get("supplier_id", ""),
                supplier_name=supplier.get("supplier_name", ""),
                preferred=supplier.get("preferred_supplier", False),
                incumbent=False,
                quality_score=supplier.get("quality_score"),
                risk_score=supplier.get("risk_score"),
                esg_score=supplier.get("esg_score"),
            )
        )

    return shortlist, excluded


def determine_escalations(
    interpretation: RequestInterpretation,
    validation: Validation,
    policy: PolicyEvaluation,
    shortlist: list[SupplierShortlistEntry],
) -> list[Escalation]:
    """Stage 6: Check each escalation rule and fire where applicable.

    TODO: implement all 8 escalation rule checks (ER-001 through ER-008).
    """
    escalations: list[Escalation] = []

    if interpretation.budget_amount is None or interpretation.quantity is None:
        escalations.append(
            Escalation(
                escalation_id="ESC-001",
                rule="ER-001",
                trigger="Missing required information (budget or quantity).",
                escalate_to="Requester Clarification",
                blocking=True,
            )
        )

    if not shortlist:
        escalations.append(
            Escalation(
                escalation_id="ESC-002",
                rule="ER-004",
                trigger="No compliant supplier found for this request.",
                escalate_to="Head of Category",
                blocking=True,
            )
        )

    return escalations


def build_recommendation(
    shortlist: list[SupplierShortlistEntry],
    escalations: list[Escalation],
) -> Recommendation:
    """Stage 7: Produce the final recommendation status.

    TODO: implement full recommendation logic with confidence scoring.
    """
    blocking = [e for e in escalations if e.blocking]

    if blocking:
        return Recommendation(
            status="cannot_proceed",
            reason=f"{len(blocking)} blocking escalation(s) prevent autonomous award.",
        )

    if shortlist:
        top = shortlist[0]
        return Recommendation(
            status="proceed",
            reason=f"Recommended supplier: {top.supplier_name} (rank 1).",
            preferred_supplier_if_resolved=top.supplier_name,
        )

    return Recommendation(
        status="cannot_proceed",
        reason="No compliant suppliers available.",
    )


def build_audit_trail(
    overview: dict[str, Any],
    shortlist: list[SupplierShortlistEntry],
) -> AuditTrail:
    """Assemble the audit trail metadata."""
    return AuditTrail(
        policies_checked=[],  # TODO: collect from policy evaluation
        supplier_ids_evaluated=[s.supplier_id for s in shortlist],
        data_sources_used=["organisational_layer_api"],
        historical_awards_consulted=bool(overview.get("historical_awards")),
    )


# ------------------------------------------------------------------
# Public orchestrator
# ------------------------------------------------------------------


async def process_request(request_id: str) -> ProcessingResult:
    """Run the full procurement decision pipeline for a single request."""

    overview = await fetch_overview(request_id)

    interpretation = interpret_request(overview)
    validation = validate_request(interpretation, overview)
    policy = evaluate_policies(interpretation, overview)
    shortlist, excluded = build_supplier_shortlist(interpretation, overview)
    escalations = determine_escalations(interpretation, validation, policy, shortlist)
    recommendation = build_recommendation(shortlist, escalations)
    audit_trail = build_audit_trail(overview, shortlist)

    return ProcessingResult(
        request_id=request_id,
        processed_at=datetime.now(timezone.utc),
        request_interpretation=interpretation,
        validation=validation,
        policy_evaluation=policy,
        supplier_shortlist=shortlist,
        suppliers_excluded=excluded,
        escalations=escalations,
        recommendation=recommendation,
        audit_trail=audit_trail,
    )
