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
from app.pipeline.rule_engine import RuleEngine
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

RULES — read ALL of them before responding:

1. Only flag issue type "contradictory". Do NOT flag "missing_info" — that is handled deterministically.

2. A contradiction exists ONLY when a SPECIFIC VALUE in the text DIRECTLY CONFLICTS with the corresponding structured field:
   - Quantity in text states a DIFFERENT number than the quantity field (e.g., text says "200 units" but field says 400)
   - Budget in text states a DIFFERENT amount than budget_amount (e.g., text says "EUR 50,000" but field says 100000)
   - Date in text states a DIFFERENT date than required_by_date
   - Currency in text states a DIFFERENT currency than the currency field
   - Category described in text is clearly incompatible with category_l1/category_l2

3. These are EXPLICITLY NOT contradictions — do NOT flag them:
   - "approximately X" or "around X" or "roughly X" matching the exact value X in the field (approximations are normal)
   - preferred_supplier_mentioned vs incumbent_supplier being different (these are intentionally separate fields)
   - Urgency language (e.g., "ASAP", "urgent") without stating a specific conflicting date
   - Policy concerns, preferences, or conditions expressed in text (e.g., "if commercially competitive")
   - Budget stated in text matching the budget_amount field (even if worded differently)
   - The text not mentioning every structured field (omission is not contradiction)
   - Rounding differences (e.g., text says "400,000" and field says 400000.00)
   - Unit of measure described differently but meaning the same thing

4. Be MAXIMALLY CONSERVATIVE. If there is ANY doubt, do NOT flag it. A false positive is far worse than a false negative.

5. The request_text may be in any language (en, fr, de, es, pt, ja). Analyze it in its original language.

6. Extract any explicit requester instruction (e.g., "no exception", "single supplier only", "must use X", "prefer X if competitive").

7. If you find ZERO contradictions, return an empty contradictions list. This is the expected outcome for most well-formed requests.
"""


def _build_request_context(fetch_result: FetchResult) -> dict:
    """Build a flat context dict from the fetch result for rule evaluation."""
    req = fetch_result.request
    budget = coerce_budget(req.budget_amount)
    quantity = coerce_quantity(req.quantity)
    countries = normalize_delivery_countries(req.delivery_countries)
    days_until = compute_days_until_required(req.required_by_date, req.created_at)

    min_total = _min_total_price(fetch_result.pricing)
    min_exp = _min_expedited_lead_time(fetch_result.pricing)

    return {
        "request_id": req.request_id,
        "category_l1": req.category_l1,
        "category_l2": req.category_l2,
        "budget_amount": budget,
        "quantity": quantity,
        "currency": req.currency,
        "required_by_date": req.required_by_date,
        "delivery_countries": countries if countries else None,
        "country": countries[0] if countries else req.country,
        "days_until_required": days_until,
        "data_residency_constraint": req.data_residency_constraint,
        "preferred_supplier_mentioned": req.preferred_supplier_mentioned,
        "request_text": req.request_text,
        "request_language": req.request_language,
        "min_total_price": min_total,
        "min_expedited_lead_time": min_exp,
    }


async def validate_request(
    fetch_result: FetchResult,
    llm_client: "LLMClient | None",
    pipeline_logger: PipelineLogger,
    *,
    rule_engine: RuleEngine | None = None,
    dynamic_rules: list[dict] | None = None,
) -> ValidationResult:
    """Run dynamic rules + LLM validation on the request."""

    req = fetch_result.request
    budget = coerce_budget(req.budget_amount)
    quantity = coerce_quantity(req.quantity)
    delivery_country = primary_delivery_country(req.model_dump())
    days_until = compute_days_until_required(req.required_by_date, req.created_at)

    async with pipeline_logger.step(STEP_NAME, {"request_id": req.request_id}) as ctx:
        issues: list[ValidationIssue] = []
        completeness = True

        # ── Phase A: Dynamic rule evaluation ──────────────────

        if rule_engine and dynamic_rules:
            context = _build_request_context(fetch_result)
            non_llm_rules = [r for r in dynamic_rules if r.get("eval_type") != "custom_llm"]
            rule_results = await rule_engine.evaluate_rules(non_llm_rules, context)

            for rr in rule_results:
                if rr.result == "failed":
                    sev = rr.severity

                    if rr.eval_type == "required":
                        for field_name in rr.actual_values.get("missing", []):
                            field_sev = sev
                            issues.append(ValidationIssue(
                                severity=field_sev,
                                type="missing_info",
                                field=field_name,
                                description=f"{field_name} is missing.",
                                action_required=f"Requester must provide {field_name}.",
                            ))
                            if field_sev == "critical":
                                completeness = False
                    else:
                        issue_type = _classify_issue_type(rr)
                        issues.append(ValidationIssue(
                            severity=sev,
                            type=issue_type,
                            description=rr.message,
                            action_required=rr.message,
                        ))
        else:
            # Fallback: deterministic checks (backward compatibility)
            issues, completeness = _deterministic_checks(fetch_result, budget, quantity, days_until)

        # ── Phase B: LLM contradiction detection ─────────────
        # Always use direct LLM call with the detailed VALIDATION_SYSTEM_PROMPT.
        # The rule engine's generic LLMRuleResponse + short prompt caused false
        # positives (VAL-006). Direct path uses the constrained LLMValidationResult
        # schema and temperature=0 for deterministic results.

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
                temperature=0,
            )

            if fallback or llm_result is None:
                llm_fallback = True
                pipeline_logger.audit(
                    "general", "warn", STEP_NAME,
                    "LLM call failed for validation. Using deterministic fallback.",
                )
            else:
                requester_instruction = llm_result.requester_instruction
                if llm_result.contradictions:
                    pipeline_logger.audit(
                        "validation", "info", STEP_NAME,
                        f"LLM contradiction check: {len(llm_result.contradictions)} issue(s) found.",
                        {"contradictions": [c.model_dump() for c in llm_result.contradictions]},
                    )
                else:
                    pipeline_logger.audit(
                        "validation", "info", STEP_NAME,
                        "LLM contradiction check: no contradictions found between text and structured fields.",
                    )
                for contradiction in llm_result.contradictions:
                    issues.append(ValidationIssue(
                        severity=contradiction.severity,
                        type=contradiction.type,
                        field=contradiction.field,
                        description=contradiction.description,
                        action_required="Review and resolve the contradiction before proceeding.",
                    ))

        # ── Policy conflict: requester single-supplier vs AT-002 ─────
        # When requester says "no exception" / "single supplier" but tier requires 2+ quotes
        instruction = requester_instruction or ""
        if not instruction and req.request_text:
            text_lower = req.request_text.lower()
            if "no exception" in text_lower or "single supplier" in text_lower or "single source" in text_lower:
                instruction = "no exception — single supplier only"
                requester_instruction = instruction
        if fetch_result.approval_tier and fetch_result.approval_tier.get_quotes_required() >= 2:
            if instruction and (
                "no exception" in instruction.lower()
                or "single supplier" in instruction.lower()
                or "single source" in instruction.lower()
            ):
                issues.append(ValidationIssue(
                    severity="high",
                    type="policy_conflict",
                    description=(
                        f"Requester instruction '{instruction}' conflicts with "
                        f"{fetch_result.approval_tier.threshold_id}: a contract value above "
                        f"{req.currency or 'EUR'} {fetch_result.approval_tier.get_min_amount():,.0f} "
                        f"requires at least {fetch_result.approval_tier.get_quotes_required()} supplier quotes. "
                        "All compliant pricing options for this quantity exceed that threshold. "
                        "The requester cannot waive this requirement unilaterally."
                    ),
                    action_required=(
                        f"Procurement policy {fetch_result.approval_tier.threshold_id} must be applied. "
                        f"{fetch_result.approval_tier.get_quotes_required()} quotes are required and a deviation "
                        "requires Procurement Manager approval."
                    ),
                ))

        # ── Build interpretation ──────────────────────────────

        countries = normalize_delivery_countries(req.delivery_countries)
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

        # Order: budget_insufficient, policy_conflict, lead_time_infeasible, then others
        _ORDER = {"budget_insufficient": 0, "policy_conflict": 1, "lead_time_infeasible": 2}
        issues.sort(key=lambda i: (_ORDER.get(i.type, 99), i.type))
        for idx, issue in enumerate(issues, 1):
            issue.issue_id = f"V-{idx:03d}"

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


def _classify_issue_type(rr) -> str:
    """Map a dynamic rule result to a specific issue type for downstream matching."""
    rule_id = getattr(rr, "rule_id", "")
    msg_lower = (getattr(rr, "message", "") or "").lower()
    if rule_id == "VAL-004" or "budget" in msg_lower:
        return "budget_insufficient"
    if rule_id == "VAL-005" or "lead time" in msg_lower:
        return "lead_time_infeasible"
    if rule_id == "VAL-003" or "past" in msg_lower:
        return "lead_time_infeasible"
    return "validation_rule_failed"


def _deterministic_checks(
    fetch_result: FetchResult,
    budget: float | None,
    quantity: int | None,
    days_until: int | None,
) -> tuple[list[ValidationIssue], bool]:
    """Fallback deterministic validation (used when no dynamic rules available)."""
    req = fetch_result.request
    issues: list[ValidationIssue] = []
    completeness = True

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

    if budget is not None and quantity is not None and fetch_result.pricing:
        min_total = _min_total_price(fetch_result.pricing)
        if min_total is not None and budget < min_total:
            currency = req.currency or "EUR"
            issues.append(ValidationIssue(
                severity="critical", type="budget_insufficient",
                description=f"Budget of {currency} {budget:,.2f} cannot cover {quantity} units at any supplier's pricing. Minimum total: {currency} {min_total:,.2f}.",
                action_required=f"Requester must either increase budget to at least {currency} {min_total:,.2f} or reduce quantity.",
            ))

    if days_until is not None and days_until >= 0 and fetch_result.pricing:
        min_expedited = _min_expedited_lead_time(fetch_result.pricing)
        if min_expedited is not None and days_until < min_expedited:
            max_expedited = _max_expedited_lead_time(fetch_result.pricing)
            issues.append(ValidationIssue(
                severity="high", type="lead_time_infeasible",
                description=f"Required delivery date {req.required_by_date} is {days_until} days from request creation. All suppliers' expedited lead times ({min_expedited}-{max_expedited or min_expedited} days) exceed this window.",
                action_required="Requester must confirm whether the delivery date is a hard constraint.",
            ))

    return issues, completeness


def _build_validation_prompt(req, budget: float | None, quantity: int | None) -> str:
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
    times = []
    for p in pricing:
        val = p.expedited_lead_time_days if hasattr(p, "expedited_lead_time_days") else p.get("expedited_lead_time_days")
        if val is not None:
            times.append(int(val))
    return min(times) if times else None


def _max_expedited_lead_time(pricing: list) -> int | None:
    times = []
    for p in pricing:
        val = p.expedited_lead_time_days if hasattr(p, "expedited_lead_time_days") else p.get("expedited_lead_time_days")
        if val is not None:
            times.append(int(val))
    return max(times) if times else None
