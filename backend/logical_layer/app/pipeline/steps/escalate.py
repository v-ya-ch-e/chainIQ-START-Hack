"""Step 7: Compute and merge escalations from three sources."""

from __future__ import annotations

import logging

from app.clients.organisational import OrganisationalClient
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
from app.services.rule_evaluator import evaluate_rules_async
from app.utils import coerce_budget, coerce_quantity

logger = logging.getLogger(__name__)

STEP_NAME = "compute_escalations"


async def compute_escalations(
    fetch_result: FetchResult,
    validation_result: ValidationResult,
    compliance_result: ComplianceResult,
    rank_result: RankResult,
    pipeline_logger: PipelineLogger,
    org_client: OrganisationalClient | None = None,
) -> EscalationResult:
    """Merge escalations from Org Layer, pipeline rules, and LLM."""

    req = fetch_result.request
    budget = coerce_budget(req.budget_amount)
    currency = req.currency or "EUR"
    interp = validation_result.request_interpretation

    async with pipeline_logger.step(
        STEP_NAME,
        {"org_escalation_count": len(fetch_result.org_escalations)},
    ) as ctx:

        pipeline_issues = await _discover_pipeline_issues(
            fetch_result, validation_result, compliance_result,
            rank_result, budget, currency, org_client,
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


async def _discover_pipeline_issues(
    fetch_result: FetchResult,
    validation_result: ValidationResult,
    compliance_result: ComplianceResult,
    rank_result: RankResult,
    budget: float | None,
    currency: str,
    org_client: OrganisationalClient | None,
) -> list[PipelineEscalation]:
    """Discover escalation-worthy issues from pipeline rules (PE-001..PE-005, PE-LLM)."""

    issues: list[PipelineEscalation] = []
    req = fetch_result.request
    interp = validation_result.request_interpretation

    has_budget_insufficient = any(vi.type == "budget_insufficient" for vi in validation_result.issues)
    has_lead_time_issue = any(vi.type == "lead_time_infeasible" for vi in validation_result.issues)

    min_ranked_total = None
    for s in rank_result.ranked_suppliers:
        if s.total_price is not None:
            if min_ranked_total is None or s.total_price < min_ranked_total:
                min_ranked_total = s.total_price

    compliant_residency_count = sum(
        1 for s in compliance_result.compliant if s.data_residency_supported
    )
    preferred_excluded_restricted = False
    if req.preferred_supplier_mentioned:
        for exc in compliance_result.excluded:
            if (
                req.preferred_supplier_mentioned.lower() in exc.supplier_name.lower()
                and "restricted" in exc.reason.lower()
            ):
                preferred_excluded_restricted = True
                break

    pipeline_context = {
        "has_budget_insufficient_issue": has_budget_insufficient,
        "has_lead_time_issue": has_lead_time_issue,
        "days_until_required": interp.days_until_required,
        "min_expedited_lead_time": None,  # Could add from rank/filter if needed
        "compliant_count": len(compliance_result.compliant),
        "initial_supplier_count": len(compliance_result.compliant) + len(compliance_result.excluded),
        "compliant_residency_count": compliant_residency_count,
        "preferred_supplier_excluded_restricted": preferred_excluded_restricted,
        "min_ranked_total": min_ranked_total,
        "req_data_residency_constraint": req.data_residency_constraint,
        "budget_amount": budget,
        "currency": currency,
        "country": req.country or "unknown",
        "requester_instruction": interp.requester_instruction or "",
        "threshold_quotes_required": fetch_result.approval_tier.get_quotes_required() if fetch_result.approval_tier else 2,
    }

    rules: list[dict] = []
    if org_client:
        try:
            rules = await org_client.get_procurement_rules(
                rule_type="pipeline_escalation",
                scope="pipeline",
                enabled=True,
            )
        except Exception as exc:
            logger.warning("Failed to fetch pipeline escalation rules: %s", exc)

    if rules:
        triggered = await evaluate_rules_async(
            rules, pipeline_context,
            llm_client=None,  # PE-LLM would need llm_client; pass from caller if needed
        )
        for t in triggered:
            issues.append(PipelineEscalation(
                rule_id=t.get("rule_id", "PE-001"),
                trigger=t.get("trigger", ""),
                escalate_to=t.get("action_target") or "Procurement Manager",
                blocking=t.get("is_blocking", True),
                source="pipeline",
            ))
    else:
        # Fallback: original hardcoded logic
        if has_budget_insufficient and budget is not None and min_ranked_total is not None:
            issues.append(PipelineEscalation(
                rule_id="PE-001",
                trigger=(
                    f"Budget is insufficient. Budget {currency} {budget:,.2f}, "
                    f"minimum total {currency} {min_ranked_total:,.2f}. "
                    f"Requester must confirm revised budget or reduced quantity."
                ),
                escalate_to="Requester Clarification",
                blocking=True,
                source="pipeline",
            ))
        if has_lead_time_issue:
            issues.append(PipelineEscalation(
                rule_id="PE-002",
                trigger=(
                    f"Lead time infeasible: required delivery {interp.required_by_date} "
                    f"({interp.days_until_required} days). "
                    f"All suppliers' expedited lead times exceed this window."
                ),
                escalate_to="Head of Category",
                blocking=True,
                source="pipeline",
            ))
        if req.data_residency_constraint and compliant_residency_count == 0 and compliance_result.compliant:
            issues.append(PipelineEscalation(
                rule_id="PE-003",
                trigger=f"No compliant supplier supports data residency in {req.country or 'unknown'}",
                escalate_to="Data Protection Officer",
                blocking=True,
                source="pipeline",
            ))
        if not compliance_result.compliant and fetch_result.compliant_suppliers:
            issues.append(PipelineEscalation(
                rule_id="PE-004",
                trigger="No supplier remains after compliance checks.",
                escalate_to="Head of Category",
                blocking=True,
                source="pipeline",
            ))
        if preferred_excluded_restricted:
            for exc in compliance_result.excluded:
                if req.preferred_supplier_mentioned and req.preferred_supplier_mentioned.lower() in exc.supplier_name.lower():
                    issues.append(PipelineEscalation(
                        rule_id="PE-005",
                        trigger=f"Preferred supplier {exc.supplier_name} is restricted: {exc.reason}",
                        escalate_to="Procurement Manager",
                        blocking=True,
                        source="pipeline",
                    ))
                    break
        if interp.requester_instruction:
            for vi in validation_result.issues:
                if vi.type in ("contradictory", "policy_conflict"):
                    issues.append(PipelineEscalation(
                        rule_id="PE-LLM",
                        trigger=(
                            f"Policy conflict: requester instruction "
                            f"'{interp.requester_instruction}' conflicts with policy. {vi.description}"
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
