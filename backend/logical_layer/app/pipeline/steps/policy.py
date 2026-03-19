"""Step 6: Evaluate procurement policy constraints."""

from __future__ import annotations

import logging

from app.models.pipeline_io import (
    ApprovalThresholdEval,
    ComplianceResult,
    FetchResult,
    PolicyResult,
    PreferredSupplierEval,
    RankResult,
    RestrictionEval,
    RuleRef,
)
from app.pipeline.logger import PipelineLogger
from app.utils import coerce_budget, primary_delivery_country, country_to_region

logger = logging.getLogger(__name__)

STEP_NAME = "evaluate_policy"


async def evaluate_policy(
    fetch_result: FetchResult,
    rank_result: RankResult,
    compliance_result: ComplianceResult,
    pipeline_logger: PipelineLogger,
) -> PolicyResult:
    """Determine which procurement policies apply and how they constrain the decision."""

    req = fetch_result.request
    budget = coerce_budget(req.budget_amount)
    currency = req.currency or "EUR"
    delivery_country = primary_delivery_country(req.model_dump())
    region = country_to_region(delivery_country)

    async with pipeline_logger.step(STEP_NAME, {"request_id": req.request_id}) as ctx:

        # ── 6a: Approval threshold ────────────────────────────

        approval_eval = _evaluate_approval_threshold(
            fetch_result, rank_result, budget, currency, pipeline_logger
        )

        # ── 6b: Preferred supplier analysis ───────────────────

        preferred_eval = _evaluate_preferred_supplier(
            fetch_result, rank_result, compliance_result,
            delivery_country, region, pipeline_logger
        )

        # ── 6c: Restricted supplier analysis ──────────────────

        restricted_evals = _evaluate_restricted_suppliers(
            fetch_result, compliance_result, pipeline_logger
        )

        # ── 6d: Category and geography rules ──────────────────

        category_rules = [
            RuleRef(
                rule_id=r.rule_id,
                rule_type=r.rule_type,
                rule_text=r.rule_text,
            )
            for r in fetch_result.applicable_rules.category_rules
        ]

        geography_rules = [
            RuleRef(
                rule_id=r.rule_id,
                rule_type=r.rule_type,
                rule_text=r.rule_text,
            )
            for r in fetch_result.applicable_rules.geography_rules
        ]

        for rule in category_rules:
            pipeline_logger.audit(
                "policy", "info", STEP_NAME,
                f"Category rule {rule.rule_id}: {rule.rule_text}",
                {"policy_id": rule.rule_id, "rule_type": rule.rule_type},
            )

        for rule in geography_rules:
            pipeline_logger.audit(
                "policy", "info", STEP_NAME,
                f"Geography rule {rule.rule_id}: {rule.rule_text}",
                {"policy_id": rule.rule_id, "rule_type": rule.rule_type},
            )

        result = PolicyResult(
            approval_threshold=approval_eval,
            preferred_supplier=preferred_eval,
            restricted_suppliers=restricted_evals,
            category_rules_applied=category_rules,
            geography_rules_applied=geography_rules,
        )

        ctx.output_summary = {
            "tier": approval_eval.rule_applied,
            "quotes_required": approval_eval.quotes_required,
        }
        ctx.metadata = {
            "tier": approval_eval.rule_applied,
            "quotes_required": approval_eval.quotes_required,
        }

        return result


def _evaluate_approval_threshold(
    fetch_result: FetchResult,
    rank_result: RankResult,
    budget: float | None,
    currency: str,
    pipeline_logger: PipelineLogger,
) -> ApprovalThresholdEval:
    """Determine approval tier from overview data or supplier pricing."""

    tier = fetch_result.approval_tier

    # If budget is null, use the minimum total from ranked suppliers
    reference_amount = budget
    basis_note = ""

    if reference_amount is None and rank_result.ranked_suppliers:
        totals = [
            s.total_price for s in rank_result.ranked_suppliers
            if s.total_price is not None
        ]
        if totals:
            reference_amount = min(totals)
            basis_note = (
                f"Budget is null; using minimum supplier total "
                f"{currency} {reference_amount:,.2f} for tier determination."
            )
            pipeline_logger.audit(
                "policy", "info", STEP_NAME, basis_note,
                {"inferred_amount": reference_amount, "currency": currency},
            )

    if tier is None:
        return ApprovalThresholdEval(
            note="No approval tier could be determined (budget and pricing unavailable)."
        )

    rule_applied = tier.threshold_id
    quotes_required = tier.get_quotes_required()
    approvers = tier.get_approvers()
    deviation_approvers = tier.get_deviation_approvers()
    deviation_approval = deviation_approvers[0] if deviation_approvers else None

    # Compute basis text
    if rank_result.ranked_suppliers:
        totals = [
            s.total_price for s in rank_result.ranked_suppliers
            if s.total_price is not None
        ]
        if totals:
            min_total = min(totals)
            max_total = max(totals)
            basis = (
                f"All valid pricing options place total contract value between "
                f"{currency} {min_total:,.2f} and {currency} {max_total:,.2f} — "
                f"above the {currency} {tier.get_min_amount():,.2f} threshold."
            )
        else:
            basis = f"Approval tier {rule_applied} applies."
    else:
        basis = f"Approval tier {rule_applied} applies based on budget {currency} {budget:,.2f}." if budget else ""

    # Note about budget near boundary
    note = tier.policy_note or ""
    if basis_note:
        note = f"{basis_note} {note}".strip()

    eval_result = ApprovalThresholdEval(
        rule_applied=rule_applied,
        basis=basis,
        quotes_required=quotes_required,
        approvers=approvers,
        deviation_approval=deviation_approval,
        note=note,
    )

    pipeline_logger.audit(
        "policy", "info", STEP_NAME,
        f"Applied {rule_applied}: {quotes_required} quotes required. Approvers: {approvers}",
        {
            "policy_id": rule_applied,
            "quotes_required": quotes_required,
            "threshold": tier.get_min_amount(),
            "actual_value": reference_amount,
        },
    )

    return eval_result


def _evaluate_preferred_supplier(
    fetch_result: FetchResult,
    rank_result: RankResult,
    compliance_result: ComplianceResult,
    delivery_country: str,
    region: str,
    pipeline_logger: PipelineLogger,
) -> PreferredSupplierEval:
    """Analyze the requester's preferred supplier."""

    preferred_name = fetch_result.request.preferred_supplier_mentioned
    if not preferred_name:
        return PreferredSupplierEval(status="not_stated")

    # Find supplier in compliant set by name match
    all_suppliers = fetch_result.compliant_suppliers
    matched = None
    for s in all_suppliers:
        if preferred_name.lower() in s.supplier_name.lower() or s.supplier_name.lower() in preferred_name.lower():
            matched = s
            break

    if matched is None:
        pipeline_logger.audit(
            "policy", "info", STEP_NAME,
            f"Preferred supplier '{preferred_name}': not found in compliant set",
            {"preferred_supplier": preferred_name, "status": "not_found"},
        )
        return PreferredSupplierEval(
            supplier=preferred_name,
            status="not_found",
            policy_note=f"'{preferred_name}' not found among compliant suppliers.",
        )

    is_preferred = matched.preferred_supplier
    is_restricted = False

    # Check if excluded
    excluded_ids = {e.supplier_id for e in compliance_result.excluded}
    in_ranked = any(r.supplier_id == matched.supplier_id for r in rank_result.ranked_suppliers)
    covers_country = True

    if matched.supplier_id in excluded_ids:
        for exc in compliance_result.excluded:
            if exc.supplier_id == matched.supplier_id and "restricted" in exc.reason.lower():
                is_restricted = True
                break

    status = "eligible"
    if is_restricted:
        status = "restricted"
    elif not is_preferred:
        status = "not_preferred"
    elif not in_ranked:
        status = "no_coverage"

    policy_note = (
        f"{matched.supplier_name} is "
        f"{'a preferred' if is_preferred else 'not a preferred'} supplier for "
        f"{fetch_result.request.category_l2} in {delivery_country}."
    )
    if is_preferred and status == "eligible":
        policy_note += (
            " Preferred status means this supplier should be included in the comparison."
        )

    eval_result = PreferredSupplierEval(
        supplier=matched.supplier_name,
        status=status,
        is_preferred=is_preferred,
        covers_delivery_country=covers_country,
        is_restricted=is_restricted,
        policy_note=policy_note,
    )

    pipeline_logger.audit(
        "policy", "info", STEP_NAME,
        f"Preferred supplier {matched.supplier_name}: {status}, "
        f"is_preferred={is_preferred}, covers {delivery_country}",
        {"preferred_supplier": matched.supplier_name, "status": status},
    )

    return eval_result


def _evaluate_restricted_suppliers(
    fetch_result: FetchResult,
    compliance_result: ComplianceResult,
    pipeline_logger: PipelineLogger,
) -> dict[str, RestrictionEval]:
    """Document restriction status for excluded suppliers."""

    result: dict[str, RestrictionEval] = {}

    for exc in compliance_result.excluded:
        key = f"{exc.supplier_id}_{exc.supplier_name.replace(' ', '_')}"
        is_restricted = "restricted" in exc.reason.lower()
        result[key] = RestrictionEval(
            restricted=is_restricted,
            note=exc.reason,
        )

    return result
