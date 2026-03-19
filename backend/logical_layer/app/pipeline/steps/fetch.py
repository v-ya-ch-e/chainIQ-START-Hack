"""Step 1: Fetch request overview and escalations from the Org Layer."""

from __future__ import annotations

import asyncio
import logging

from app.clients.organisational import OrganisationalClient
from app.models.common import (
    ApprovalTierData,
    AwardData,
    EscalationData,
    PricingData,
    RequestData,
    RulesData,
    SupplierData,
)
from app.models.pipeline_io import FetchResult
from app.pipeline.logger import PipelineLogger

logger = logging.getLogger(__name__)

STEP_NAME = "fetch_overview"


async def fetch_overview(
    request_id: str,
    org_client: OrganisationalClient,
    pipeline_logger: PipelineLogger,
) -> FetchResult:
    """Fetch all data the pipeline needs in minimal HTTP calls."""

    async with pipeline_logger.step(STEP_NAME, {"request_id": request_id}) as ctx:
        overview_task = org_client.get_request_overview(request_id)
        escalations_task = org_client.get_escalations_by_request(request_id)

        overview_raw, escalations_raw = await asyncio.gather(
            overview_task, escalations_task
        )

        request_data = RequestData.model_validate(overview_raw.get("request", {}))

        compliant_suppliers = [
            SupplierData.model_validate(s)
            for s in overview_raw.get("compliant_suppliers", [])
        ]

        pricing = [
            PricingData.model_validate(p)
            for p in overview_raw.get("pricing", [])
        ]

        rules_raw = overview_raw.get("applicable_rules", {})
        applicable_rules = RulesData.model_validate(rules_raw) if rules_raw else RulesData()

        tier_raw = overview_raw.get("approval_tier")
        approval_tier = ApprovalTierData.model_validate(tier_raw) if tier_raw else None

        historical_awards = [
            AwardData.model_validate(a)
            for a in overview_raw.get("historical_awards", [])
        ]

        org_escalations = [
            EscalationData.model_validate(e) for e in escalations_raw
        ]

        result = FetchResult(
            request=request_data,
            compliant_suppliers=compliant_suppliers,
            pricing=pricing,
            applicable_rules=applicable_rules,
            approval_tier=approval_tier,
            historical_awards=historical_awards,
            org_escalations=org_escalations,
        )

        pipeline_logger.audit(
            "data_access", "info", STEP_NAME,
            f"Fetched request overview for {request_id}: "
            f"{len(compliant_suppliers)} compliant suppliers, "
            f"{len(pricing)} pricing tiers, "
            f"{len(historical_awards)} historical awards",
            {
                "request_id": request_id,
                "supplier_count": len(compliant_suppliers),
                "pricing_count": len(pricing),
                "award_count": len(historical_awards),
                "escalation_count": len(org_escalations),
            },
        )

        ctx.output_summary = {
            "supplier_count": len(compliant_suppliers),
            "pricing_count": len(pricing),
            "award_count": len(historical_awards),
        }
        ctx.metadata = {
            "supplier_count": len(compliant_suppliers),
            "pricing_count": len(pricing),
            "award_count": len(historical_awards),
        }

        return result
