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
        vi.type in ("contradictory", "policy_conflict")
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

    return {
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
        "has_unregistered_supplier": False,
        "approval_tier_requires_strategic": approval_tier_requires_strategic,
    }


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

    for vi in validation_result.issues:
        if vi.type == "budget_insufficient" and budget is not None:
            min_total = None
            for s in rank_result.ranked_suppliers:
                if s.total_price is not None:
                    if min_total is None or s.total_price < min_total:
                        min_total = s.total_price

            if min_total is not None:
                issues.append(PipelineEscalation(
                    rule_id="ER-001",
                    trigger=(
                        f"Budget is insufficient. Budget {currency} {budget:,.2f}, "
                        f"minimum total {currency} {min_total:,.2f}."
                    ),
                    escalate_to="Requester Clarification",
                    blocking=True,
                    source="pipeline",
                ))

    for vi in validation_result.issues:
        if vi.type == "lead_time_infeasible":
            interp = validation_result.request_interpretation
            issues.append(PipelineEscalation(
                rule_id="ER-004",
                trigger=(
                    f"Lead time infeasible: required delivery "
                    f"{interp.required_by_date} "
                    f"({interp.days_until_required} days)."
                ),
                escalate_to="Head of Category",
                blocking=True,
                source="pipeline",
            ))
            break

    if fetch_result.request.data_residency_constraint:
        has_residency = any(
            s.data_residency_supported for s in compliance_result.compliant
        )
        if not has_residency and compliance_result.compliant:
            country = fetch_result.request.country or "unknown"
            issues.append(PipelineEscalation(
                rule_id="ER-005",
                trigger=f"No compliant supplier supports data residency in {country}",
                escalate_to="Data Protection Officer",
                blocking=True,
                source="pipeline",
            ))

    if not compliance_result.compliant and fetch_result.compliant_suppliers:
        issues.append(PipelineEscalation(
            rule_id="ER-004",
            trigger="No supplier remains after compliance checks.",
            escalate_to="Head of Category",
            blocking=True,
            source="pipeline",
        ))

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

    interp = validation_result.request_interpretation
    if interp.requester_instruction:
        for vi in validation_result.issues:
            if vi.type in ("contradictory", "policy_conflict"):
                issues.append(PipelineEscalation(
                    rule_id="AT-002",
                    trigger=(
                        f"Policy conflict: requester instruction "
                        f"'{interp.requester_instruction}' conflicts with policy. "
                        f"{vi.description}"
                    ),
                    escalate_to="Procurement Manager",
                    blocking=True,
                    source="llm",
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

    result = sorted(merged.values(), key=lambda e: e.rule)
    for i, esc in enumerate(result, 1):
        esc.escalation_id = f"ESC-{i:03d}"

    return result
