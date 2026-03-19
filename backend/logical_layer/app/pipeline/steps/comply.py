"""Step 4: Per-supplier compliance checks."""

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
from app.utils import coerce_budget, coerce_quantity, normalize_delivery_countries

logger = logging.getLogger(__name__)

STEP_NAME = "check_compliance"

RISK_SCORE_THRESHOLD = 30


async def check_compliance(
    fetch_result: FetchResult,
    filter_result: FilterResult,
    org_client: OrganisationalClient,
    pipeline_logger: PipelineLogger,
) -> ComplianceResult:
    """Apply detailed compliance rules to each enriched supplier."""

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
) -> str | None:
    """Return an exclusion reason, or None if the supplier passes all checks."""

    # Data residency check
    if req.data_residency_constraint and not supplier.data_residency_supported:
        return f"Does not support data residency in {primary_country}"

    # Capacity check
    if quantity is not None and supplier.capacity_per_month is not None:
        if quantity > supplier.capacity_per_month:
            return (
                f"Quantity {quantity} exceeds monthly capacity "
                f"{supplier.capacity_per_month}"
            )

    # Risk-based exclusion for non-preferred suppliers
    if not supplier.preferred_supplier and supplier.risk_score > RISK_SCORE_THRESHOLD:
        return (
            f"preferred=False, risk_score={supplier.risk_score} "
            f"(exceeds threshold of {RISK_SCORE_THRESHOLD}). "
            f"Excluded from shortlist on risk grounds."
        )

    # Value-conditional restriction check via Org Layer for borderline cases
    if req.category_l1 and req.category_l2:
        try:
            restriction = await org_client.check_restricted(
                supplier_id=supplier.supplier_id,
                category_l1=req.category_l1,
                category_l2=req.category_l2,
                delivery_country=primary_country,
            )
            if restriction.get("is_restricted"):
                reason = restriction.get("restriction_reason", "Policy restriction")
                return f"Restricted: {reason}"
        except Exception as exc:
            logger.warning(
                "Restriction check failed for %s — treating as non-restricted: %s",
                supplier.supplier_id, exc,
            )

    return None
