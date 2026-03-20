"""Step 4: Per-supplier compliance checks using dynamic rules."""

from __future__ import annotations

import logging

from app.clients.organisational import OrganisationalClient
from app.models.pipeline_io import (
    ComplianceResult,
    EnrichedSupplier,
    ExcludedSupplier,
    FetchResult,
    FilterResult,
)
from app.pipeline.logger import PipelineLogger
from app.pipeline.rule_engine import RuleEngine
from app.utils import coerce_budget, coerce_quantity, normalize_delivery_countries

logger = logging.getLogger(__name__)

STEP_NAME = "check_compliance"

RISK_SCORE_THRESHOLD = 70


def _build_supplier_context(
    supplier: EnrichedSupplier,
    req,
    budget: float | None,
    quantity: int | None,
    primary_country: str,
    is_restricted: bool = False,
    restriction_reason: str = "",
) -> dict:
    """Build a flat context dict for a single supplier."""
    return {
        "request_id": req.request_id,
        "category_l1": req.category_l1,
        "category_l2": req.category_l2,
        "budget_amount": budget,
        "quantity": quantity,
        "currency": req.currency,
        "country": primary_country,
        "data_residency_constraint": req.data_residency_constraint,
        "preferred_supplier_mentioned": req.preferred_supplier_mentioned,
        "supplier_id": supplier.supplier_id,
        "supplier_name": supplier.supplier_name,
        "quality_score": supplier.quality_score,
        "risk_score": supplier.risk_score,
        "esg_score": supplier.esg_score,
        "preferred_supplier": supplier.preferred_supplier,
        "data_residency_supported": supplier.data_residency_supported,
        "capacity_per_month": supplier.capacity_per_month,
        "unit_price": supplier.unit_price,
        "total_price": supplier.total_price,
        "moq": getattr(supplier, "moq", None),
        "standard_lead_time_days": supplier.standard_lead_time_days,
        "expedited_lead_time_days": supplier.expedited_lead_time_days,
        "is_restricted": is_restricted,
        "restriction_reason": restriction_reason,
    }


async def check_compliance(
    fetch_result: FetchResult,
    filter_result: FilterResult,
    org_client: OrganisationalClient,
    pipeline_logger: PipelineLogger,
    *,
    rule_engine: RuleEngine | None = None,
    dynamic_rules: list[dict] | None = None,
) -> ComplianceResult:
    """Apply compliance rules to each enriched supplier."""

    req = fetch_result.request
    budget = coerce_budget(req.budget_amount)
    quantity = coerce_quantity(req.quantity)
    delivery_countries = normalize_delivery_countries(req.delivery_countries)
    primary_country = delivery_countries[0] if delivery_countries else req.country or "DE"

    async with pipeline_logger.step(
        STEP_NAME,
        {"supplier_count": len(filter_result.enriched_suppliers)},
    ) as ctx:
        compliant: list[EnrichedSupplier] = []
        excluded: list[ExcludedSupplier] = []

        for supplier in filter_result.enriched_suppliers:
            exclusion_reason = await _check_supplier(
                supplier=supplier,
                req=req,
                budget=budget,
                quantity=quantity,
                primary_country=primary_country,
                org_client=org_client,
                rule_engine=rule_engine,
                dynamic_rules=dynamic_rules,
            )

            if exclusion_reason:
                excluded.append(ExcludedSupplier(
                    supplier_id=supplier.supplier_id,
                    supplier_name=supplier.supplier_name,
                    reason=exclusion_reason,
                ))
                pipeline_logger.audit(
                    "compliance", "warn", STEP_NAME,
                    f"Excluded {supplier.supplier_id} ({supplier.supplier_name}): {exclusion_reason}",
                    {"supplier_id": supplier.supplier_id, "action": "excluded",
                     "reason": exclusion_reason},
                )
            else:
                compliant.append(supplier)
                pipeline_logger.audit(
                    "compliance", "info", STEP_NAME,
                    f"{supplier.supplier_id} ({supplier.supplier_name}): compliant. "
                    f"Not restricted, covers {primary_country}, "
                    f"{'no' if not req.data_residency_constraint else ''} residency constraint",
                    {"supplier_id": supplier.supplier_id, "action": "compliant"},
                )

        result = ComplianceResult(compliant=compliant, excluded=excluded)

        ctx.output_summary = {
            "compliant_count": len(compliant),
            "excluded_count": len(excluded),
        }
        ctx.metadata = {
            "compliant_count": len(compliant),
            "excluded_count": len(excluded),
        }

        return result


async def _check_supplier(
    supplier: EnrichedSupplier,
    req,
    budget: float | None,
    quantity: int | None,
    primary_country: str,
    org_client: OrganisationalClient,
    rule_engine: RuleEngine | None = None,
    dynamic_rules: list[dict] | None = None,
) -> str | None:
    """Return an exclusion reason, or None if the supplier passes all checks."""

    # Resolve restriction status via org layer
    is_restricted = False
    restriction_reason = ""
    if req.category_l1 and req.category_l2:
        try:
            restriction = await org_client.check_restricted(
                supplier_id=supplier.supplier_id,
                category_l1=req.category_l1,
                category_l2=req.category_l2,
                delivery_country=primary_country,
            )
            if restriction.get("is_restricted"):
                is_restricted = True
                restriction_reason = restriction.get("restriction_reason", "Policy restriction")
        except Exception as exc:
            logger.warning(
                "Restriction check failed for %s — treating as non-restricted: %s",
                supplier.supplier_id, exc,
            )

    # ── Dynamic rule evaluation ──────────────────────────────
    if rule_engine and dynamic_rules:
        context = _build_supplier_context(
            supplier, req, budget, quantity, primary_country,
            is_restricted=is_restricted,
            restriction_reason=restriction_reason,
        )
        rule_results = await rule_engine.evaluate_rules(dynamic_rules, context)

        for rr in rule_results:
            if rr.result == "failed" and rr.action == "exclude":
                return rr.message
        return None

    # ── Fallback: hardcoded checks (backward compatibility) ──
    if req.data_residency_constraint and not supplier.data_residency_supported:
        return f"Does not support data residency in {primary_country}"

    if quantity is not None and supplier.capacity_per_month is not None:
        if quantity > supplier.capacity_per_month:
            return (
                f"Quantity {quantity} exceeds monthly capacity "
                f"{supplier.capacity_per_month}"
            )

    if not supplier.preferred_supplier and supplier.risk_score > RISK_SCORE_THRESHOLD:
        return (
            f"{supplier.supplier_name} is not restricted for {req.category_l2}. "
            f"However, preferred=False and risk_score={supplier.risk_score} "
            f"(exceeds threshold of {RISK_SCORE_THRESHOLD}). "
            f"Excluded from shortlist on risk grounds."
        )

    if is_restricted:
        return f"Restricted: {restriction_reason}"

    return None
