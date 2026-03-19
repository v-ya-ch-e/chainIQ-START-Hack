"""Step 8: Generate recommendation (deterministic status + LLM prose)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.pipeline_io import (
    EscalationResult,
    FetchResult,
    LLMRecommendationText,
    RankResult,
    RecommendationResult,
    ValidationResult,
)
from app.pipeline.logger import PipelineLogger
from app.utils import coerce_budget

if TYPE_CHECKING:
    from app.clients.llm import LLMClient

logger = logging.getLogger(__name__)

STEP_NAME = "generate_recommendation"

RECOMMENDATION_SYSTEM_PROMPT = """You are a procurement recommendation analyst. Generate concise, audit-ready text for a procurement recommendation.

RULES:
1. Reference exact supplier names, prices (with currency), and rule IDs (e.g., AT-002, ER-001).
2. Use professional, objective language suitable for audit documentation.
3. Keep the reason to 1-3 sentences.
4. Keep the preferred_supplier_rationale to 1-3 sentences, comparing the recommended supplier with alternatives using specific figures.
5. If the status is "cannot_proceed", explain why and what must be resolved.
6. If the status is "proceed_with_conditions", state the conditions.
7. If the status is "proceed", explain why the recommendation is clear.
"""


async def generate_recommendation(
    fetch_result: FetchResult,
    validation_result: ValidationResult,
    rank_result: RankResult,
    escalation_result: EscalationResult,
    llm_client: "LLMClient | None",
    pipeline_logger: PipelineLogger,
) -> RecommendationResult:
    """Determine recommendation status and generate reasoning."""

    req = fetch_result.request
    currency = req.currency or "EUR"
    budget = coerce_budget(req.budget_amount)

    async with pipeline_logger.step(
        STEP_NAME,
        {"escalation_count": len(escalation_result.escalations)},
    ) as ctx:

        # ── Deterministic status ──────────────────────────────

        if escalation_result.has_blocking:
            status = "cannot_proceed"
        elif escalation_result.non_blocking_count > 0:
            status = "proceed_with_conditions"
        else:
            status = "proceed"

        # ── Deterministic fields ──────────────────────────────

        top_supplier_name: str | None = None
        if rank_result.ranked_suppliers:
            top_supplier_name = rank_result.ranked_suppliers[0].supplier_name

        minimum_budget: float | None = None
        if rank_result.ranked_suppliers:
            totals = [
                s.total_price for s in rank_result.ranked_suppliers
                if s.total_price is not None
            ]
            if totals:
                minimum_budget = min(totals)

        # ── Confidence score ──────────────────────────────────

        confidence = _compute_confidence(
            escalation_result.escalations,
            validation_result.issues,
            rank_result.ranked_suppliers,
        )

        # ── LLM prose ─────────────────────────────────────────

        reason = ""
        rationale: str | None = None
        llm_used = False

        if llm_client:
            llm_used = True
            user_prompt = _build_recommendation_prompt(
                status, escalation_result, rank_result,
                validation_result, fetch_result, currency,
            )
            llm_result, fallback = await llm_client.structured_call(
                system_prompt=RECOMMENDATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=LLMRecommendationText,
                max_tokens=1500,
            )
            if llm_result and not fallback:
                reason = llm_result.reason
                rationale = llm_result.preferred_supplier_rationale
            else:
                pipeline_logger.audit(
                    "general", "warn", STEP_NAME,
                    "LLM call failed for recommendation. Using deterministic fallback.",
                )

        # Deterministic fallback
        if not reason:
            reason = _fallback_reason(
                status, escalation_result, rank_result, currency
            )
        if not rationale and top_supplier_name and rank_result.ranked_suppliers:
            top = rank_result.ranked_suppliers[0]
            price_str = (
                f"{currency} {top.total_price:,.2f}"
                if top.total_price
                else "unknown price"
            )
            rationale = (
                f"{top.supplier_name} is the top-ranked option at {price_str} "
                f"with quality score {top.quality_score} and risk score {top.risk_score}."
            )

        result = RecommendationResult(
            status=status,
            reason=reason,
            preferred_supplier_if_resolved=top_supplier_name,
            preferred_supplier_rationale=rationale,
            minimum_budget_required=minimum_budget,
            minimum_budget_currency=currency if minimum_budget else None,
            confidence_score=confidence,
        )

        pipeline_logger.audit(
            "recommendation", "info", STEP_NAME,
            f"Recommendation: {status}. "
            f"{escalation_result.blocking_count} blocking escalations. "
            f"Confidence: {confidence}%.",
            {"status": status, "confidence": confidence,
             "blocking_count": escalation_result.blocking_count},
        )

        if top_supplier_name:
            top = rank_result.ranked_suppliers[0]
            price_str = (
                f"{currency} {top.total_price:,.2f}"
                if top.total_price
                else "N/A"
            )
            pipeline_logger.audit(
                "recommendation", "info", STEP_NAME,
                f"Preferred supplier if resolved: {top_supplier_name} "
                f"(rank #{top.rank}, {price_str})",
                {"preferred_supplier": top_supplier_name, "rank": top.rank},
            )

        ctx.output_summary = {"status": status, "confidence": confidence}
        ctx.metadata = {"status": status, "confidence": confidence}

        return result


def _compute_confidence(
    escalations: list,
    validation_issues: list,
    ranked_suppliers: list,
) -> int:
    """Compute confidence score (0-100)."""

    score = 100

    blocking = [e for e in escalations if e.blocking]
    if blocking:
        return 0

    non_blocking = [e for e in escalations if not e.blocking]
    score -= len(non_blocking) * 10

    severity_penalty = {"critical": 15, "high": 10, "medium": 5, "low": 2}
    for issue in validation_issues:
        score -= severity_penalty.get(issue.severity, 5)

    if len(ranked_suppliers) >= 2:
        s1 = ranked_suppliers[0]
        s2 = ranked_suppliers[1]
        if s1.true_cost and s2.true_cost and s1.true_cost > 0:
            gap = (s2.true_cost - s1.true_cost) / s1.true_cost
            if gap > 0.20:
                score += 10

    if ranked_suppliers and ranked_suppliers[0].preferred:
        score += 5

    return max(0, min(100, score))


def _build_recommendation_prompt(
    status: str,
    escalation_result: EscalationResult,
    rank_result: RankResult,
    validation_result: ValidationResult,
    fetch_result: FetchResult,
    currency: str,
) -> str:
    """Build user prompt for LLM recommendation text."""

    parts = [f"## Recommendation Status: {status}\n"]

    if escalation_result.escalations:
        parts.append("## Escalations")
        for e in escalation_result.escalations:
            parts.append(
                f"- {e.rule}: {e.trigger} "
                f"(escalate to: {e.escalate_to}, "
                f"{'BLOCKING' if e.blocking else 'non-blocking'})"
            )

    if rank_result.ranked_suppliers:
        parts.append("\n## Top Ranked Suppliers")
        for s in rank_result.ranked_suppliers[:3]:
            price = f"{currency} {s.total_price:,.2f}" if s.total_price else "N/A"
            parts.append(
                f"- #{s.rank} {s.supplier_name}: {price}, "
                f"quality={s.quality_score}, risk={s.risk_score}, "
                f"preferred={s.preferred}, incumbent={s.incumbent}"
            )

    if validation_result.issues:
        parts.append("\n## Validation Issues")
        for issue in validation_result.issues:
            parts.append(f"- [{issue.severity}] {issue.type}: {issue.description}")

    interp = validation_result.request_interpretation
    parts.append(
        f"\n## Request: {fetch_result.request.request_id}, "
        f"category {interp.category_l1}/{interp.category_l2}, "
        f"quantity {interp.quantity}, budget {currency} {interp.budget_amount}"
    )

    if fetch_result.historical_awards:
        parts.append(f"\n## Historical Awards: {len(fetch_result.historical_awards)} found")
        for a in fetch_result.historical_awards[:3]:
            parts.append(f"- {a.award_id}: {a.supplier_name}, awarded={a.awarded}")

    return "\n".join(parts)


def _fallback_reason(
    status: str,
    escalation_result: EscalationResult,
    rank_result: RankResult,
    currency: str,
) -> str:
    """Template-based fallback when LLM is unavailable."""

    if status == "cannot_proceed":
        issue_list = ", ".join(
            e.trigger[:80] for e in escalation_result.escalations if e.blocking
        )
        return (
            f"{escalation_result.blocking_count} blocking issues prevent "
            f"autonomous award: {issue_list}. All require human resolution."
        )

    top = rank_result.ranked_suppliers[0] if rank_result.ranked_suppliers else None

    if status == "proceed_with_conditions":
        conditions = ", ".join(
            e.trigger[:60] for e in escalation_result.escalations if not e.blocking
        )
        if top and top.total_price:
            return (
                f"Recommendation to proceed with {top.supplier_name} "
                f"(rank 1, {currency} {top.total_price:,.2f}), "
                f"subject to: {conditions}."
            )
        return f"Recommendation to proceed, subject to: {conditions}."

    if top and top.total_price:
        return (
            f"Recommend awarding to {top.supplier_name} at "
            f"{currency} {top.total_price:,.2f}. "
            f"Quality score {top.quality_score}, risk score {top.risk_score}."
        )
    return "Recommend proceeding with the top-ranked supplier."
