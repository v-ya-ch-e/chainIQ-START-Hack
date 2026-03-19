"""Step 2: Validate request completeness, consistency, and contradictions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.pipeline_io import (
    FetchResult,
    LLMValidationResult,
    RequestInterpretation,
    ValidationIssue,
    ValidationResult,
)
from app.pipeline.logger import PipelineLogger
from app.utils import (
    coerce_budget,
    coerce_quantity,
    compute_days_until_required,
    normalize_delivery_countries,
    primary_delivery_country,
)

if TYPE_CHECKING:
    from app.clients.llm import LLMClient

logger = logging.getLogger(__name__)

STEP_NAME = "validate_request"

VALIDATION_SYSTEM_PROMPT = """You are a procurement validation assistant. You receive a purchase request with both free-text and structured fields. Your job is to find CONTRADICTIONS between the text and the structured data, and to extract any explicit requester instructions.

RULES:
1. Only flag two issue types: "missing_info" and "contradictory"
2. A contradiction exists ONLY when:
   - Quantity in text differs from the quantity field
   - Budget in text differs from the budget_amount field
   - Date in text differs from the required_by_date field
   - Currency in text differs from the currency field
   - Category in text clearly doesn't match category_l1/category_l2
3. These are NOT contradictions:
   - preferred_supplier_mentioned vs incumbent_supplier (intentionally different)
   - Urgency language without a specific date
   - Policy concerns expressed in text
4. Be CONSERVATIVE. When in doubt, do NOT flag.
5. The request_text may be in any language (en, fr, de, es, pt, ja). Analyze it in its original language.
6. Extract any explicit requester instruction (e.g., "no exception", "single supplier only", "must use X").
"""


async def validate_request(
    fetch_result: FetchResult,
    llm_client: "LLMClient | None",
    pipeline_logger: PipelineLogger,
) -> ValidationResult:
    """Run deterministic + LLM validation on the request."""

    req = fetch_result.request
    budget = coerce_budget(req.budget_amount)
    quantity = coerce_quantity(req.quantity)
    delivery_country = primary_delivery_country(req.model_dump())
    days_until = compute_days_until_required(req.required_by_date, req.created_at)

    async with pipeline_logger.step(STEP_NAME, {"request_id": req.request_id}) as ctx:
        issues: list[ValidationIssue] = []
        completeness = True

        # ── Phase A: Deterministic checks ─────────────────────

        if not req.category_l1:
            issues.append(ValidationIssue(
                severity="critical", type="missing_info", field="category_l1",
                description="category_l1 is missing.",
                action_required="Requester must specify L1 category.",
            ))
            completeness = False

        if not req.category_l2:
            issues.append(ValidationIssue(
                severity="critical", type="missing_info", field="category_l2",
                description="category_l2 is missing.",
                action_required="Requester must specify L2 category.",
            ))
            completeness = False

        if not req.currency:
            issues.append(ValidationIssue(
                severity="critical", type="missing_info", field="currency",
                description="currency is missing.",
                action_required="Requester must specify currency.",
            ))
            completeness = False

        if budget is None:
            issues.append(ValidationIssue(
                severity="high", type="missing_info", field="budget_amount",
                description="budget_amount is null. Pipeline will continue with degraded capability.",
                action_required="Requester should provide a budget for accurate pricing comparison.",
            ))

        if quantity is None:
            issues.append(ValidationIssue(
                severity="high", type="missing_info", field="quantity",
                description="quantity is null. Pricing comparison will be limited to quality-only ranking.",
                action_required="Requester should provide a quantity for pricing lookup.",
            ))

        if not req.required_by_date:
            issues.append(ValidationIssue(
                severity="medium", type="missing_info", field="required_by_date",
                description="required_by_date is not specified.",
                action_required="Requester should specify a delivery date for lead time feasibility checks.",
            ))

        countries = normalize_delivery_countries(req.delivery_countries)
        if not countries:
            issues.append(ValidationIssue(
                severity="high", type="missing_info", field="delivery_countries",
                description="No delivery countries specified.",
                action_required="Requester must specify at least one delivery country.",
            ))

        if days_until is not None and days_until < 0:
            issues.append(ValidationIssue(
                severity="critical", type="lead_time_infeasible", field="required_by_date",
                description=f"Required by date {req.required_by_date} is in the past ({days_until} days ago).",
                action_required="Requester must provide a future delivery date.",
            ))

        # Budget sufficiency check
        if budget is not None and quantity is not None and fetch_result.pricing:
            min_total = _min_total_price(fetch_result.pricing)
            if min_total is not None and budget < min_total:
                currency = req.currency or "EUR"
                issues.append(ValidationIssue(
                    severity="critical", type="budget_insufficient",
                    description=(
                        f"Budget of {currency} {budget:,.2f} cannot cover {quantity} units "
                        f"at any compliant supplier's standard pricing. Minimum total: "
                        f"{currency} {min_total:,.2f}."
                    ),
                    action_required=(
                        f"Requester must either increase budget to at least "
                        f"{currency} {min_total:,.2f} or reduce quantity."
                    ),
                ))

        # Lead time feasibility check
        if days_until is not None and days_until >= 0 and fetch_result.pricing:
            min_expedited = _min_expedited_lead_time(fetch_result.pricing)
            if min_expedited is not None and days_until < min_expedited:
                max_expedited = _max_expedited_lead_time(fetch_result.pricing)
                issues.append(ValidationIssue(
                    severity="high", type="lead_time_infeasible",
                    description=(
                        f"Required delivery date {req.required_by_date} is {days_until} days "
                        f"from request creation. All suppliers' expedited lead times "
                        f"({min_expedited}-{max_expedited or min_expedited} days) exceed this window."
                    ),
                    action_required=(
                        "Requester must confirm whether the delivery date is a hard constraint. "
                        "If so, an escalation is required."
                    ),
                ))

        # ── Phase B: LLM contradiction detection ─────────────

        llm_used = False
        llm_fallback = False
        requester_instruction: str | None = None

        if llm_client and req.request_text:
            llm_used = True
            user_prompt = _build_validation_prompt(req, budget, quantity)
            llm_result, fallback = await llm_client.structured_call(
                system_prompt=VALIDATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=LLMValidationResult,
                max_tokens=1500,
            )

            if fallback or llm_result is None:
                llm_fallback = True
                pipeline_logger.audit(
                    "general", "warn", STEP_NAME,
                    "LLM call failed for validation. Using deterministic fallback.",
                )
            else:
                requester_instruction = llm_result.requester_instruction
                for contradiction in llm_result.contradictions:
                    issues.append(ValidationIssue(
                        severity=contradiction.severity,
                        type=contradiction.type,
                        field=contradiction.field,
                        description=contradiction.description,
                        action_required="Review and resolve the contradiction before proceeding.",
                    ))

        # ── Build interpretation ──────────────────────────────

        interpretation = RequestInterpretation(
            category_l1=req.category_l1,
            category_l2=req.category_l2,
            quantity=quantity,
            unit_of_measure=req.unit_of_measure,
            budget_amount=budget,
            currency=req.currency,
            delivery_country=delivery_country,
            required_by_date=req.required_by_date,
            days_until_required=days_until,
            data_residency_required=req.data_residency_constraint,
            esg_requirement=req.esg_requirement,
            preferred_supplier_stated=req.preferred_supplier_mentioned,
            incumbent_supplier=req.incumbent_supplier,
            requester_instruction=requester_instruction,
        )

        # Assign issue IDs
        for idx, issue in enumerate(issues, 1):
            issue.issue_id = f"V-{idx:03d}"

        # Log each issue
        for issue in issues:
            log_level = "error" if issue.severity == "critical" else (
                "warn" if issue.severity == "high" else "info"
            )
            pipeline_logger.audit(
                "validation", log_level, STEP_NAME,
                issue.description,
                {"issue_type": issue.type, "severity": issue.severity, "field": issue.field},
            )

        if completeness:
            pipeline_logger.audit(
                "validation", "info", STEP_NAME,
                "All required fields present. Completeness: pass",
            )

        result = ValidationResult(
            completeness=completeness,
            issues=issues,
            request_interpretation=interpretation,
            llm_used=llm_used,
            llm_fallback=llm_fallback,
        )

        ctx.output_summary = {
            "completeness": completeness,
            "issue_count": len(issues),
        }
        ctx.metadata = {
            "completeness": completeness,
            "issue_count": len(issues),
            "llm_used": llm_used,
        }

        return result


def _build_validation_prompt(req: "RequestData", budget: float | None, quantity: int | None) -> str:
    """Build the user prompt for LLM validation."""
    fields = [
        f"request_id: {req.request_id}",
        f"category_l1: {req.category_l1}",
        f"category_l2: {req.category_l2}",
        f"quantity (field): {quantity}",
        f"budget_amount (field): {budget}",
        f"currency: {req.currency}",
        f"required_by_date: {req.required_by_date}",
        f"preferred_supplier_mentioned: {req.preferred_supplier_mentioned}",
        f"incumbent_supplier: {req.incumbent_supplier}",
        f"language: {req.request_language}",
    ]
    return (
        f"## Structured Fields\n{chr(10).join(fields)}\n\n"
        f"## Request Text\n{req.request_text}\n\n"
        "Find contradictions between the text and the structured fields. "
        "Also extract any explicit requester instruction from the text."
    )


def _min_total_price(pricing: list) -> float | None:
    """Find the minimum total price across all pricing tiers."""
    totals = []
    for p in pricing:
        val = p.total_price if hasattr(p, "total_price") else p.get("total_price")
        if val is not None:
            try:
                totals.append(float(val))
            except (ValueError, TypeError):
                pass
    return min(totals) if totals else None


def _min_expedited_lead_time(pricing: list) -> int | None:
    """Find the minimum expedited lead time across all pricing tiers."""
    times = []
    for p in pricing:
        val = p.expedited_lead_time_days if hasattr(p, "expedited_lead_time_days") else p.get("expedited_lead_time_days")
        if val is not None:
            times.append(int(val))
    return min(times) if times else None


def _max_expedited_lead_time(pricing: list) -> int | None:
    """Find the maximum expedited lead time across all pricing tiers."""
    times = []
    for p in pricing:
        val = p.expedited_lead_time_days if hasattr(p, "expedited_lead_time_days") else p.get("expedited_lead_time_days")
        if val is not None:
            times.append(int(val))
    return max(times) if times else None
