"""Step 7: Compute and merge escalations from org layer, pipeline, and dynamic rules."""

from __future__ import annotations

import logging

from app.models.pipeline_io import (
    Escalation,
    EscalationResult,
    FetchResult,
    PipelineEscalation,
    ValidationResult,
    ComplianceResult,
    RankResult,
)
from app.pipeline.logger import PipelineLogger
from app.pipeline.rule_engine import RuleEngine
from app.utils import coerce_budget, coerce_quantity

logger = logging.getLogger(__name__)

STEP_NAME = "compute_escalations"


def _build_escalation_context(
    fetch_result: FetchResult,
    validation_result: ValidationResult,
    compliance_result: ComplianceResult,
    rank_result: RankResult,
    budget: float | None,
    quantity: int | None,
    currency: str,
) -> dict:
    """Build a flat context dict for escalation rule evaluation."""
    req = fetch_result.request

    min_ranked_total = None
    for s in rank_result.ranked_suppliers:
        if s.total_price is not None:
            if min_ranked_total is None or s.total_price < min_ranked_total:
                min_ranked_total = s.total_price

    max_supplier_capacity = None
    for s in compliance_result.compliant:
        cap = s.capacity_per_month
        if cap is not None:
            if max_supplier_capacity is None or cap > max_supplier_capacity:
                max_supplier_capacity = cap

    has_residency_supplier = any(
        s.data_residency_supported for s in compliance_result.compliant
    )

    preferred_is_restricted = False
    if req.preferred_supplier_mentioned:
        for exc in compliance_result.excluded:
            if (
                req.preferred_supplier_mentioned.lower() in exc.supplier_name.lower()
                and "restricted" in exc.reason.lower()
            ):
                preferred_is_restricted = True
                break

    has_contradictions = any(
        vi.type == "contradictory"
        for vi in validation_result.issues
    )

    has_lead_time_issue = any(
        vi.type == "lead_time_infeasible"
        for vi in validation_result.issues
    )

    has_budget_issue = any(
        vi.type == "budget_insufficient"
        for vi in validation_result.issues
    )

    approval_tier_requires_strategic = False
    if fetch_result.approval_tier:
        approvers = fetch_result.approval_tier.get_approvers()
        approval_tier_requires_strategic = any(
            a in ("head_of_strategic_sourcing", "cpo")
            for a in approvers
        )

    suppliers_meeting_qty = 0
    if quantity is not None:
        for s in compliance_result.compliant:
            if s.capacity_per_month is not None and s.capacity_per_month >= quantity:
                suppliers_meeting_qty += 1
    single_supplier_capacity_risk = (
        quantity is not None and suppliers_meeting_qty == 1
    )

    delivery_countries = set()
    if req.delivery_countries:
        if isinstance(req.delivery_countries, str):
            for part in req.delivery_countries.replace(";", ",").split(","):
                part = part.strip()
                if part:
                    delivery_countries.add(part)
        elif isinstance(req.delivery_countries, list):
            for c in req.delivery_countries:
                if c:
                    delivery_countries.add(c.strip())
    if not delivery_countries and req.country:
        delivery_countries.add(req.country)

    has_unregistered_supplier = False
    for s in compliance_result.compliant:
        if hasattr(s, "service_regions") and s.service_regions:
            regions = set()
            raw = s.service_regions
            if isinstance(raw, str):
                for part in raw.split(";"):
                    part = part.strip()
                    if part:
                        regions.add(part)
            elif isinstance(raw, list):
                regions = {r.strip() for r in raw if r}
            if delivery_countries and not delivery_countries.issubset(regions):
                has_unregistered_supplier = True
                break

    ctx = {
        "request_id": req.request_id,
        "category_l1": req.category_l1,
        "category_l2": req.category_l2,
        "budget_amount": budget,
        "quantity": quantity,
        "currency": currency,
        "country": req.country,
        "data_residency_constraint": req.data_residency_constraint,
        "preferred_supplier_mentioned": req.preferred_supplier_mentioned,
        "compliant_supplier_count": len(compliance_result.compliant),
        "min_ranked_total": min_ranked_total,
        "max_supplier_capacity": max_supplier_capacity,
        "has_residency_supplier": has_residency_supplier,
        "preferred_is_restricted": preferred_is_restricted,
        "has_contradictions": has_contradictions,
        "has_lead_time_issue": has_lead_time_issue,
        "has_budget_issue": has_budget_issue,
        "has_unregistered_supplier": has_unregistered_supplier,
        "single_supplier_capacity_risk": single_supplier_capacity_risk,
        "approval_tier_requires_strategic": approval_tier_requires_strategic,
    }
    return ctx


async def compute_escalations(
    fetch_result: FetchResult,
    validation_result: ValidationResult,
    compliance_result: ComplianceResult,
    rank_result: RankResult,
    pipeline_logger: PipelineLogger,
    *,
    rule_engine: RuleEngine | None = None,
    dynamic_rules: list[dict] | None = None,
) -> EscalationResult:
    """Merge escalations from Org Layer, pipeline rules, and dynamic rules."""

    req = fetch_result.request
    budget = coerce_budget(req.budget_amount)
    quantity = coerce_quantity(req.quantity)
    currency = req.currency or "EUR"

    async with pipeline_logger.step(
        STEP_NAME,
        {"org_escalation_count": len(fetch_result.org_escalations)},
    ) as ctx:

        # ── Dynamic rule evaluation ──────────────────────────
        pipeline_issues: list[PipelineEscalation] = []

        if rule_engine and dynamic_rules:
            context = _build_escalation_context(
                fetch_result, validation_result, compliance_result,
                rank_result, budget, quantity, currency,
            )
            rule_results = await rule_engine.evaluate_rules(dynamic_rules, context)

            for rr in rule_results:
                if rr.result == "failed" and rr.action == "escalate":
                    pipeline_issues.append(PipelineEscalation(
                        rule_id=rr.rule_id,
                        trigger=rr.message,
                        escalate_to=rr.escalation_target or "Procurement Manager",
                        blocking=rr.is_blocking,
                        source="dynamic_rule",
                    ))
        else:
            pipeline_issues = _discover_pipeline_issues(
                fetch_result, validation_result, compliance_result,
                rank_result, budget, quantity, currency,
            )

        merged = _merge_escalations(
            fetch_result.org_escalations,
            pipeline_issues,
        )

        blocking = [e for e in merged if e.blocking]
        non_blocking = [e for e in merged if not e.blocking]

        for esc in merged:
            level = "error" if esc.blocking else "warn"
            pipeline_logger.audit(
                "escalation", level, STEP_NAME,
                f"{esc.rule} triggered: {esc.trigger}. "
                f"Escalate to {esc.escalate_to}. "
                f"{'BLOCKING' if esc.blocking else 'NON-BLOCKING'}",
                {
                    "rule_id": esc.rule,
                    "blocking": esc.blocking,
                    "escalate_to": esc.escalate_to,
                    "source": esc.source,
                },
            )

        result = EscalationResult(
            escalations=merged,
            has_blocking=len(blocking) > 0,
            blocking_count=len(blocking),
            non_blocking_count=len(non_blocking),
        )

        ctx.output_summary = {
            "total": len(merged),
            "blocking": len(blocking),
            "non_blocking": len(non_blocking),
        }
        ctx.metadata = {
            "total": len(merged),
            "blocking": len(blocking),
            "non_blocking": len(non_blocking),
        }

        return result


def _discover_pipeline_issues(
    fetch_result: FetchResult,
    validation_result: ValidationResult,
    compliance_result: ComplianceResult,
    rank_result: RankResult,
    budget: float | None,
    quantity: int | None,
    currency: str,
) -> list[PipelineEscalation]:
    """Fallback: discover escalation-worthy issues from pipeline steps 2-5 (hardcoded)."""

    issues: list[PipelineEscalation] = []

    # ER-001: Missing required info (budget or quantity is null)
    missing_fields = []
    if budget is None:
        missing_fields.append("budget")
    if quantity is None:
        missing_fields.append("quantity")
    if missing_fields:
        issues.append(PipelineEscalation(
            rule_id="ER-001",
            trigger=f"Missing required information: {', '.join(missing_fields)}",
            escalate_to="Requester Clarification",
            blocking=True,
            source="pipeline",
        ))

    # ER-010: Lead time infeasible (non-blocking)
    for vi in validation_result.issues:
        if vi.type == "lead_time_infeasible":
            interp = validation_result.request_interpretation
            min_exp = max_exp = None
            for s in rank_result.ranked_suppliers:
                if s.expedited_lead_time_days is not None:
                    min_exp = min(min_exp, s.expedited_lead_time_days) if min_exp is not None else s.expedited_lead_time_days
                    max_exp = max(max_exp, s.expedited_lead_time_days) if max_exp is not None else s.expedited_lead_time_days
            range_str = f"{min_exp}–{max_exp}" if min_exp is not None and max_exp is not None and min_exp != max_exp else str(min_exp or max_exp or "?")
            issues.append(PipelineEscalation(
                rule_id="ER-010",
                trigger=(
                    f"Lead time infeasible: required delivery {interp.required_by_date} "
                    f"({interp.days_until_required} days). All suppliers' expedited lead times are "
                    f"{range_str} days."
                ),
                escalate_to="Head of Category",
                blocking=False,
                source="pipeline",
            ))
            break

    # ER-005: Data residency unsatisfiable (target: Security/Compliance)
    if fetch_result.request.data_residency_constraint:
        has_residency = any(
            s.data_residency_supported for s in compliance_result.compliant
        )
        if not has_residency and compliance_result.compliant:
            country = fetch_result.request.country or "unknown"
            issues.append(PipelineEscalation(
                rule_id="ER-005",
                trigger=f"No compliant supplier supports data residency in {country}",
                escalate_to="Security/Compliance",
                blocking=True,
                source="pipeline",
            ))

    # ER-004: No compliant supplier found
    if not compliance_result.compliant and fetch_result.compliant_suppliers:
        issues.append(PipelineEscalation(
            rule_id="ER-004",
            trigger="No supplier remains after compliance checks.",
            escalate_to="Head of Category",
            blocking=True,
            source="pipeline",
        ))

    # ER-002: Preferred supplier restricted
    preferred_name = fetch_result.request.preferred_supplier_mentioned
    if preferred_name:
        for exc in compliance_result.excluded:
            if (
                preferred_name.lower() in exc.supplier_name.lower()
                and "restricted" in exc.reason.lower()
            ):
                issues.append(PipelineEscalation(
                    rule_id="ER-002",
                    trigger=f"Preferred supplier {exc.supplier_name} is restricted: {exc.reason}",
                    escalate_to="Procurement Manager",
                    blocking=True,
                    source="pipeline",
                ))
                break

    # Policy conflict with requester instruction — use actual approval tier
    interp = validation_result.request_interpretation
    if interp.requester_instruction:
        for vi in validation_result.issues:
            if vi.type == "policy_conflict":
                instruction = interp.requester_instruction
                tier_info = ""
                if fetch_result.approval_tier:
                    tier = fetch_result.approval_tier
                    tier_id = getattr(tier, "tier_id", None) or getattr(tier, "tier", "")
                    quotes = getattr(tier, "min_supplier_quotes", None) or getattr(tier, "quotes_required", "")
                    approvers = tier.get_approvers() if hasattr(tier, "get_approvers") else []
                    tier_info = (
                        f"Approval tier {tier_id} requires {quotes} quotes"
                        f"{' and approval from ' + ', '.join(approvers) if approvers else ''}"
                    )
                issues.append(PipelineEscalation(
                    rule_id="ER-009",
                    trigger=(
                        f"Policy conflict: requester instruction '{instruction}' conflicts with "
                        f"procurement policy. {tier_info}. "
                        "Requires Procurement Manager review for any deviation."
                    ),
                    escalate_to="Procurement Manager",
                    blocking=False,
                    source="pipeline",
                ))
                break

    return issues


def _merge_escalations(
    org_escalations: list,
    pipeline_issues: list[PipelineEscalation],
) -> list[Escalation]:
    """Merge escalations from Org Layer and pipeline, deduplicating by rule_id."""

    merged: dict[str, Escalation] = {}

    for esc in org_escalations:
        rule_id = esc.rule_id
        merged[rule_id] = Escalation(
            rule=rule_id,
            trigger=esc.trigger,
            escalate_to=esc.escalate_to,
            blocking=esc.blocking,
            source="org_layer",
        )

    for issue in pipeline_issues:
        if issue.rule_id in merged:
            existing = merged[issue.rule_id]
            if len(issue.trigger) > len(existing.trigger):
                existing.trigger = issue.trigger
                existing.source = issue.source
        else:
            merged[issue.rule_id] = Escalation(
                rule=issue.rule_id,
                trigger=issue.trigger,
                escalate_to=issue.escalate_to,
                blocking=issue.blocking,
                source=issue.source,
            )

    # Order: ER-001 (budget) first, then AT-002 (policy), then others
    _PRIORITY = {"ER-001": 0, "AT-002": 1, "ER-004": 2}
    result = sorted(
        merged.values(),
        key=lambda e: (_PRIORITY.get(e.rule, 99), e.rule),
    )
    for i, esc in enumerate(result, 1):
        esc.escalation_id = f"ESC-{i:03d}"

    return result
