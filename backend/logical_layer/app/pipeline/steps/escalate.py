"""Step 7: Compute and merge escalations from three sources."""

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
from app.utils import coerce_budget, coerce_quantity

logger = logging.getLogger(__name__)

STEP_NAME = "compute_escalations"


async def compute_escalations(
    fetch_result: FetchResult,
    validation_result: ValidationResult,
    compliance_result: ComplianceResult,
    rank_result: RankResult,
    pipeline_logger: PipelineLogger,
) -> EscalationResult:
    """Merge escalations from Org Layer, pipeline, and LLM."""

    req = fetch_result.request
    budget = coerce_budget(req.budget_amount)
    quantity = coerce_quantity(req.quantity)
    currency = req.currency or "EUR"

    async with pipeline_logger.step(
        STEP_NAME,
        {"org_escalation_count": len(fetch_result.org_escalations)},
    ) as ctx:

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
    """Discover escalation-worthy issues from pipeline steps 2-5."""

    issues: list[PipelineEscalation] = []

    # Budget insufficient
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
                        f"Budget is insufficient to fulfil the stated quantity at any "
                        f"compliant supplier price. Budget {currency} {budget:,.2f}, "
                        f"minimum total {currency} {min_total:,.2f}. "
                        f"Requester must confirm revised budget or reduced quantity."
                    ),
                    escalate_to="Requester Clarification",
                    blocking=True,
                    source="pipeline",
                ))

    # Lead time infeasible
    for vi in validation_result.issues:
        if vi.type == "lead_time_infeasible":
            interp = validation_result.request_interpretation
            issues.append(PipelineEscalation(
                rule_id="ER-004",
                trigger=(
                    f"Lead time infeasible: required delivery "
                    f"{interp.required_by_date} "
                    f"({interp.days_until_required} days). "
                    f"All suppliers' expedited lead times exceed this window. "
                    f"No compliant supplier can meet the stated deadline."
                ),
                escalate_to="Head of Category",
                blocking=True,
                source="pipeline",
            ))
            break

    # Data residency not satisfiable
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

    # No suppliers remaining after compliance
    if not compliance_result.compliant and fetch_result.compliant_suppliers:
        issues.append(PipelineEscalation(
            rule_id="ER-004",
            trigger="No supplier remains after compliance checks.",
            escalate_to="Head of Category",
            blocking=True,
            source="pipeline",
        ))

    # Preferred supplier is restricted (check excluded list)
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

    # LLM-detected policy conflicts
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
