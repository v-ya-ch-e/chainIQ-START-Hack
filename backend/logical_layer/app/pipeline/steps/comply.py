"""Step 4: Per-supplier compliance checks."""

from __future__ import annotations

import asyncio
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
from app.services.rule_evaluator import evaluate_rules_async
from app.utils import coerce_budget, coerce_quantity, normalize_delivery_countries

logger = logging.getLogger(__name__)

STEP_NAME = "check_compliance"


async def _prefetch_restrictions(
    suppliers: list[EnrichedSupplier],
    category_l1: str,
    category_l2: str,
    primary_country: str,
    org_client: OrganisationalClient,
) -> dict[str, tuple[bool, str | None]]:
    """Pre-fetch restriction status for all suppliers. Returns {supplier_id: (is_restricted, reason)}."""
    if not category_l1 or not category_l2:
        return {s.supplier_id: (False, None) for s in suppliers}

    async def check_one(supplier: EnrichedSupplier) -> tuple[str, bool, str | None]:
        try:
            r = await org_client.check_restricted(
                supplier_id=supplier.supplier_id,
                category_l1=category_l1,
                category_l2=category_l2,
                delivery_country=primary_country,
            )
            return (supplier.supplier_id, r.get("is_restricted", False), r.get("restriction_reason"))
        except Exception:
            return (supplier.supplier_id, False, None)

    results = await asyncio.gather(*[check_one(s) for s in suppliers])
    return {sid: (restricted, reason) for sid, restricted, reason in results}


async def check_compliance(
    fetch_result: FetchResult,
    filter_result: FilterResult,
    org_client: OrganisationalClient,
    pipeline_logger: PipelineLogger,
) -> ComplianceResult:
    """Apply rule-based compliance checks to each enriched supplier."""

    req = fetch_result.request
    quantity = coerce_quantity(req.quantity)
    delivery_countries = normalize_delivery_countries(req.delivery_countries)
    primary_country = delivery_countries[0] if delivery_countries else req.country or "DE"

    async with pipeline_logger.step(
        STEP_NAME,
        {"supplier_count": len(filter_result.enriched_suppliers)},
    ) as ctx:
        compliant: list[EnrichedSupplier] = []
        excluded: list[ExcludedSupplier] = []

        # Pre-fetch restriction status for all suppliers
        restriction_map = await _prefetch_restrictions(
            filter_result.enriched_suppliers,
            req.category_l1 or "",
            req.category_l2 or "",
            primary_country,
            org_client,
        )

        # Fetch compliance rules
        rules: list[dict] = []
        try:
            rules = await org_client.get_procurement_rules(
                rule_type="supplier_compliance",
                scope="supplier",
                enabled=True,
            )
        except Exception as exc:
            logger.warning("Failed to fetch compliance rules, using fallback: %s", exc)

        if rules:
            pipeline_logger.audit(
                "compliance", "info", STEP_NAME,
                f"Loaded {len(rules)} compliance rules from rule_definitions",
                {"rules_loaded": len(rules),
                 "rule_ids": [r.get("rule_id") for r in rules]},
            )

        for supplier in filter_result.enriched_suppliers:
            is_restricted, restriction_reason = restriction_map.get(
                supplier.supplier_id, (False, None)
            )

            supplier_context = {
                "req_data_residency_constraint": req.data_residency_constraint,
                "req_quantity": quantity,
                "req_category_l1": req.category_l1,
                "req_category_l2": req.category_l2,
                "delivery_country": primary_country,
                "sup_supplier_id": supplier.supplier_id,
                "sup_supplier_name": supplier.supplier_name,
                "sup_preferred_supplier": supplier.preferred_supplier,
                "sup_data_residency_supported": supplier.data_residency_supported,
                "sup_capacity_per_month": supplier.capacity_per_month,
                "sup_risk_score": int(supplier.risk_score) if supplier.risk_score is not None else 0,
                "sup_esg_score": int(supplier.esg_score) if supplier.esg_score is not None else 0,
                "sup_quality_score": int(supplier.quality_score) if supplier.quality_score is not None else 0,
                "sup_is_restricted": is_restricted,
                "sup_restriction_reason": restriction_reason or "",
            }

            exclusion_reason: str | None = None
            exclusion_rule_id: str | None = None

            if rules:
                triggered = await evaluate_rules_async(rules, supplier_context)
                if triggered:
                    exclusion_reason = triggered[0].get("trigger", "Excluded by compliance rule")
                    exclusion_rule_id = triggered[0].get("rule_id")
            else:
                # Fallback: original hardcoded checks
                if req.data_residency_constraint and not supplier.data_residency_supported:
                    exclusion_reason = f"Does not support data residency in {primary_country}"
                elif quantity is not None and supplier.capacity_per_month is not None and quantity > supplier.capacity_per_month:
                    exclusion_reason = f"Quantity {quantity} exceeds monthly capacity {supplier.capacity_per_month}"
                elif not supplier.preferred_supplier and (supplier.risk_score or 0) > 30:
                    exclusion_reason = (f"preferred=False, risk_score={supplier.risk_score} "
                        f"(exceeds threshold of 30). Excluded from shortlist on risk grounds.")
                elif is_restricted:
                    exclusion_reason = f"Restricted: {restriction_reason or 'Policy restriction'}"

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
                     "rule_id": exclusion_rule_id, "reason": exclusion_reason},
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
