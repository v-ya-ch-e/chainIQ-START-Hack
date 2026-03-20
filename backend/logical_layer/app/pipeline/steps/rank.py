"""Step 5: Rank compliant suppliers by true cost."""

from __future__ import annotations

import logging

from app.models.pipeline_io import (
    ComplianceResult,
    FetchResult,
    RankedSupplier,
    RankResult,
)
from app.pipeline.logger import PipelineLogger
from app.utils import coerce_budget, coerce_quantity

logger = logging.getLogger(__name__)

STEP_NAME = "rank_suppliers"


async def rank_suppliers(
    fetch_result: FetchResult,
    compliance_result: ComplianceResult,
    pipeline_logger: PipelineLogger,
    *,
    validation_result=None,
) -> RankResult:
    """Rank compliant suppliers by true cost or quality score."""

    req = fetch_result.request
    quantity = coerce_quantity(req.quantity)
    currency = req.currency or "EUR"
    esg_required = req.esg_requirement
    incumbent_name = req.incumbent_supplier

    async with pipeline_logger.step(
        STEP_NAME,
        {"compliant_count": len(compliance_result.compliant)},
    ) as ctx:

        ranked: list[RankedSupplier] = []
        use_quality_ranking = quantity is None

        for supplier in compliance_result.compliant:
            total_price = supplier.total_price
            unit_price = supplier.unit_price

            true_cost: float | None = None
            overpayment: float | None = None

            if total_price is not None and not use_quality_ranking:
                quality = max(supplier.quality_score, 1)
                risk = max(100 - supplier.risk_score, 1)
                denominator = (quality / 100) * (risk / 100)

                if esg_required and supplier.esg_score:
                    esg = max(supplier.esg_score, 1)
                    denominator *= esg / 100

                true_cost = total_price / denominator if denominator > 0 else total_price
                overpayment = true_cost - total_price

            is_incumbent = (
                incumbent_name is not None
                and incumbent_name.lower() in supplier.supplier_name.lower()
            )

            rs = RankedSupplier(
                supplier_id=supplier.supplier_id,
                supplier_name=supplier.supplier_name,
                preferred=supplier.preferred_supplier,
                incumbent=is_incumbent,
                pricing_tier_applied=supplier.pricing_tier_applied,
                unit_price=unit_price,
                total_price=total_price,
                expedited_unit_price=supplier.expedited_unit_price,
                expedited_total_price=supplier.expedited_total_price,
                standard_lead_time_days=supplier.standard_lead_time_days,
                expedited_lead_time_days=supplier.expedited_lead_time_days,
                quality_score=supplier.quality_score,
                risk_score=supplier.risk_score,
                esg_score=supplier.esg_score,
                true_cost=true_cost,
                overpayment=overpayment,
                policy_compliant=True,
                covers_delivery_country=True,
                currency=currency,
            )
            ranked.append(rs)

            # Log pricing details
            if total_price is not None:
                unit_str = f"{currency} {unit_price:,.2f}" if unit_price is not None else "N/A"
                pipeline_logger.audit(
                    "pricing", "info", STEP_NAME,
                    f"{supplier.supplier_id}: tier {supplier.pricing_tier_applied}, "
                    f"unit {unit_str}, "
                    f"total {currency} {total_price:,.2f}, "
                    f"lead {supplier.standard_lead_time_days}d standard / "
                    f"{supplier.expedited_lead_time_days}d expedited",
                    {
                        "supplier_id": supplier.supplier_id,
                        "tier": supplier.pricing_tier_applied,
                        "unit_price": unit_price,
                        "total": total_price,
                        "currency": currency,
                    },
                )

        # Sort: when budget insufficient, rank by price (lowest first) to surface best option
        has_budget_issue = False
        if validation_result:
            has_budget_issue = any(
                vi.type == "budget_insufficient" for vi in validation_result.issues
            )
        ranking_method = "true_cost"
        if use_quality_ranking:
            ranking_method = "quality_score"
            ranked.sort(key=lambda s: -s.quality_score)
        elif has_budget_issue:
            ranking_method = "total_price"
            ranked.sort(key=lambda s: s.total_price if s.total_price is not None else float("inf"))
        else:
            ranked.sort(key=lambda s: s.true_cost if s.true_cost is not None else float("inf"))

        for i, s in enumerate(ranked, 1):
            s.rank = i

        # Log ranking summary
        if ranked:
            top = ranked[0]
            cost_desc = (
                f"true_cost {currency} {top.true_cost:,.2f}"
                if top.true_cost is not None
                else f"quality_score {top.quality_score}"
            )
            pipeline_logger.audit(
                "ranking", "info", STEP_NAME,
                f"Ranked {len(ranked)} suppliers by {ranking_method}. "
                f"#1: {top.supplier_id} ({cost_desc})",
                {"ranking_method": ranking_method, "top_supplier": top.supplier_id},
            )

        result = RankResult(ranked_suppliers=ranked, ranking_method=ranking_method)

        ctx.output_summary = {
            "ranking_method": ranking_method,
            "ranked_count": len(ranked),
        }
        ctx.metadata = {
            "ranking_method": ranking_method,
            "top_supplier": ranked[0].supplier_id if ranked else None,
        }

        return result
