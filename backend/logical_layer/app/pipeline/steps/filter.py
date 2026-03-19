"""Step 3: Filter and enrich compliant suppliers with pricing metadata."""

from __future__ import annotations

import logging

from app.models.pipeline_io import EnrichedSupplier, FetchResult, FilterResult
from app.pipeline.logger import PipelineLogger
from app.utils import coerce_quantity

logger = logging.getLogger(__name__)

STEP_NAME = "filter_suppliers"


async def filter_suppliers(
    fetch_result: FetchResult,
    pipeline_logger: PipelineLogger,
) -> FilterResult:
    """Take compliant suppliers from overview and enrich with pricing."""

    async with pipeline_logger.step(STEP_NAME, {"supplier_count": len(fetch_result.compliant_suppliers)}) as ctx:
        enriched: list[EnrichedSupplier] = []
        no_pricing: list[str] = []
        quantity = coerce_quantity(fetch_result.request.quantity)

        pricing_by_supplier: dict[str, list] = {}
        for p in fetch_result.pricing:
            pricing_by_supplier.setdefault(p.supplier_id, []).append(p)

        for supplier in fetch_result.compliant_suppliers:
            pricing_tiers = pricing_by_supplier.get(supplier.supplier_id, [])
            matched_tier = _match_pricing_tier(pricing_tiers, quantity)

            if matched_tier:
                unit_price = _safe_float(matched_tier.unit_price)
                total_price = _safe_float(matched_tier.total_price)
                expedited_unit = _safe_float(matched_tier.expedited_unit_price)
                expedited_total = _safe_float(matched_tier.expedited_total_price)
                tier_label = f"{int(matched_tier.min_quantity)}-{int(matched_tier.max_quantity)} units"

                es = EnrichedSupplier(
                    supplier_id=supplier.supplier_id,
                    supplier_name=supplier.supplier_name,
                    country_hq=supplier.country_hq,
                    currency=supplier.currency,
                    quality_score=supplier.quality_score,
                    risk_score=supplier.risk_score,
                    esg_score=supplier.esg_score,
                    preferred_supplier=supplier.preferred_supplier,
                    data_residency_supported=supplier.data_residency_supported,
                    capacity_per_month=supplier.capacity_per_month,
                    pricing_id=matched_tier.pricing_id,
                    unit_price=unit_price,
                    total_price=total_price,
                    expedited_unit_price=expedited_unit,
                    expedited_total_price=expedited_total,
                    standard_lead_time_days=matched_tier.standard_lead_time_days,
                    expedited_lead_time_days=matched_tier.expedited_lead_time_days,
                    pricing_tier_applied=tier_label,
                    has_pricing=True,
                )
                enriched.append(es)

                pipeline_logger.audit(
                    "supplier_filter", "info", STEP_NAME,
                    f"Included {supplier.supplier_id} ({supplier.supplier_name}): "
                    f"covers {fetch_result.request.category_l1} > "
                    f"{fetch_result.request.category_l2}, "
                    f"pricing tier {tier_label}",
                    {"supplier_id": supplier.supplier_id, "action": "included",
                     "reason": "covers category and country", "tier": tier_label},
                )
            else:
                es = EnrichedSupplier(
                    supplier_id=supplier.supplier_id,
                    supplier_name=supplier.supplier_name,
                    country_hq=supplier.country_hq,
                    currency=supplier.currency,
                    quality_score=supplier.quality_score,
                    risk_score=supplier.risk_score,
                    esg_score=supplier.esg_score,
                    preferred_supplier=supplier.preferred_supplier,
                    data_residency_supported=supplier.data_residency_supported,
                    capacity_per_month=supplier.capacity_per_month,
                    has_pricing=False,
                )
                enriched.append(es)
                no_pricing.append(supplier.supplier_id)

                pipeline_logger.audit(
                    "supplier_filter", "info", STEP_NAME,
                    f"{supplier.supplier_id} ({supplier.supplier_name}): "
                    f"no pricing tier covers quantity {quantity}",
                    {"supplier_id": supplier.supplier_id, "action": "included",
                     "reason": "no pricing tier", "quantity": quantity},
                )

        result = FilterResult(
            enriched_suppliers=enriched,
            suppliers_without_pricing=no_pricing,
        )

        ctx.output_summary = {
            "enriched_count": len(enriched),
            "no_pricing_count": len(no_pricing),
        }
        ctx.metadata = {
            "enriched_count": len(enriched),
            "no_pricing_count": len(no_pricing),
        }

        return result


def _match_pricing_tier(tiers: list, quantity: int | None) -> object | None:
    """Find the pricing tier that covers the given quantity."""
    if not tiers:
        return None

    if quantity is None:
        return None

    for tier in tiers:
        min_q = int(tier.min_quantity) if tier.min_quantity is not None else 0
        max_q = int(tier.max_quantity) if tier.max_quantity is not None else 999999
        if min_q <= quantity <= max_q:
            return tier

    return None


def _safe_float(val) -> float | None:
    """Safely convert a value to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
