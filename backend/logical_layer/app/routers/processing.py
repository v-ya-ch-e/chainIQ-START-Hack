"""Processing router — full procurement pipeline endpoint.

Chains all pipeline steps: fetch -> validate -> filter -> check compliance ->
rank -> evaluate policy -> check escalations -> generate recommendation ->
assemble output.  Every step is logged to the Organisational Layer's pipeline
logging API via :class:`PipelineLogger`.
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from app.clients.organisational import org_client
from app.schemas.processing import ProcessRequest, ProcessRequestResponse
from app.services.pipeline_logger import PipelineLogger
from scripts.assembleOutput import assemble_output
from scripts.checkCompliance import check_compliance
from scripts.checkEscalations import check_escalations
from scripts.evaluatePolicy import evaluate_policy
from scripts.filterCompaniesByProduct import filter_suppliers
from scripts.formatInvalidResponse import format_invalid_response
from scripts.generateRecommendation import generate_recommendation
from scripts.rankCompanies import rank_suppliers
from scripts.validateRequest import validate_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Processing"])


def _normalize_delivery_countries(raw):
    if not raw:
        return []
    if isinstance(raw[0], dict):
        return [c.get("country_code", "") for c in raw]
    return raw


def _build_request_data_for_scripts(request_obj: dict) -> dict:
    """Normalise the Org Layer request object into the shape scripts expect."""
    data = dict(request_obj)
    raw_dc = data.get("delivery_countries") or []
    data["delivery_countries"] = _normalize_delivery_countries(raw_dc)
    cats = data.get("scenario_tags", [])
    if cats and isinstance(cats[0], dict):
        data["scenario_tags"] = [t.get("tag", "") for t in cats]

    for field in ("budget_amount",):
        if field in data and data[field] is not None:
            try:
                data[field] = float(data[field])
            except (ValueError, TypeError):
                pass
    for field in ("quantity",):
        if field in data and data[field] is not None:
            try:
                data[field] = int(float(data[field]))
            except (ValueError, TypeError):
                pass
    return data


async def _run_pipeline(request_id: str) -> dict:
    """Execute the full procurement pipeline for a single request."""

    pl = await PipelineLogger.start(request_id)

    try:
        # Step 1: Fetch request from Organisational Layer
        async with pl.step_with_output("fetch_request", {"request_id": request_id}) as bag:
            try:
                request_obj = await org_client.get_request(request_id)
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to fetch request {request_id} from Organisational Layer: {exc}",
                )
            bag["output_summary"] = {
                "title": request_obj.get("title"),
                "country": request_obj.get("country"),
                "currency": request_obj.get("currency"),
                "status": request_obj.get("status"),
            }

        request_data = _build_request_data_for_scripts(request_obj)

        # Step 2: Validate
        async with pl.step_with_output("validate_request", {
            "request_id": request_id,
            "title": request_data.get("title"),
            "currency": request_data.get("currency"),
        }) as bag:
            validation_result = await asyncio.to_thread(validate_request, request_data)
            interpretation = validation_result.get("request_interpretation", {})
            issues = validation_result.get("issues", [])
            bag["output_summary"] = {
                "issue_count": len(issues),
                "issue_types": list({i.get("type") for i in issues}),
                "interpretation_keys": list(interpretation.keys()),
            }
            bag["metadata"] = {"is_valid": validation_result.get("is_valid")}

        # Step 3: Check if invalid -> early return
        has_missing_required = any(
            i.get("type") == "missing_required" for i in issues
        )
        if has_missing_required:
            async with pl.step_with_output("format_invalid_response", {
                "reason": "missing_required_fields",
                "issue_count": len(issues),
            }) as bag:
                invalid_resp = await asyncio.to_thread(
                    format_invalid_response, request_data, validation_result, interpretation
                )
                bag["output_summary"] = {"status": "invalid"}
            await pl.finish(status="completed")
            return invalid_resp

        # Step 4: Filter suppliers by category
        category_l1 = request_data.get("category_l1") or interpretation.get("category_l1")
        category_l2 = request_data.get("category_l2") or interpretation.get("category_l2")

        if not category_l1 or not category_l2:
            async with pl.step_with_output("format_invalid_response", {
                "reason": "missing_category",
            }) as bag:
                invalid_resp = await asyncio.to_thread(
                    format_invalid_response, request_data, validation_result, interpretation
                )
                bag["output_summary"] = {"status": "invalid"}
            await pl.finish(status="completed")
            return invalid_resp

        async with pl.step_with_output("filter_suppliers", {
            "category_l1": category_l1,
            "category_l2": category_l2,
        }) as bag:
            filter_input = {"category_l1": category_l1, "category_l2": category_l2}
            filter_result = await asyncio.to_thread(filter_suppliers, filter_input)
            filtered_suppliers = filter_result.get("suppliers", [])
            bag["output_summary"] = {"supplier_count": len(filtered_suppliers)}
            bag["metadata"] = {
                "supplier_ids": [s.get("supplier_id") for s in filtered_suppliers[:10]],
            }

        # Step 5: Check compliance for each supplier
        async with pl.step_with_output("check_compliance", {
            "supplier_count": len(filtered_suppliers),
        }) as bag:
            compliance_result = await asyncio.to_thread(
                check_compliance, request_data, filtered_suppliers
            )
            compliant_suppliers = compliance_result.get("compliant", [])
            non_compliant_suppliers = compliance_result.get("non_compliant", [])
            bag["output_summary"] = {
                "compliant_count": len(compliant_suppliers),
                "non_compliant_count": len(non_compliant_suppliers),
            }
            bag["metadata"] = {
                "compliant_ids": [s.get("supplier_id") for s in compliant_suppliers],
                "non_compliant_ids": [s.get("supplier_id") for s in non_compliant_suppliers],
            }

        # Step 6: Rank compliant suppliers
        async with pl.step_with_output("rank_suppliers", {
            "compliant_count": len(compliant_suppliers),
            "category_l1": category_l1,
            "category_l2": category_l2,
        }) as bag:
            rank_request_data = {
                "category_l1": category_l1,
                "category_l2": category_l2,
                "quantity": request_data.get("quantity") or interpretation.get("quantity"),
                "esg_requirement": request_data.get("esg_requirement", False),
                "delivery_countries": request_data.get("delivery_countries", []),
                "country": request_data.get("country", ""),
            }
            rank_result = await asyncio.to_thread(
                rank_suppliers, rank_request_data, compliant_suppliers
            )
            ranked_suppliers = rank_result.get("ranked", [])
            bag["output_summary"] = {
                "ranked_count": len(ranked_suppliers),
                "top_supplier": ranked_suppliers[0].get("supplier_id") if ranked_suppliers else None,
            }

        # Enrich ranked suppliers with names
        async with pl.step("enrich_supplier_names"):
            supplier_name_map = {}
            try:
                compliant_list = await org_client.get_compliant_suppliers(
                    category_l1, category_l2,
                    (request_data.get("delivery_countries") or [request_data.get("country", "")])[0],
                )
                for s in compliant_list:
                    supplier_name_map[s["supplier_id"]] = s.get("supplier_name", s["supplier_id"])
            except Exception:
                pass

            for sup in ranked_suppliers:
                if "supplier_name" not in sup:
                    sup["supplier_name"] = supplier_name_map.get(sup.get("supplier_id"), sup.get("supplier_id"))
            for sup in non_compliant_suppliers:
                if "supplier_name" not in sup:
                    sup["supplier_name"] = supplier_name_map.get(sup.get("supplier_id"), sup.get("supplier_id"))

        # Step 7: Evaluate policy
        async with pl.step_with_output("evaluate_policy", {
            "ranked_count": len(ranked_suppliers),
            "non_compliant_count": len(non_compliant_suppliers),
        }) as bag:
            policy_result = await asyncio.to_thread(
                evaluate_policy, request_data, ranked_suppliers, non_compliant_suppliers
            )
            bag["output_summary"] = {
                "approval_tier": policy_result.get("approval_threshold", {}).get("threshold_id"),
                "preferred_count": len(policy_result.get("preferred_suppliers", [])),
                "rules_count": len(policy_result.get("applicable_rules", {}).get("category_rules", []))
                    + len(policy_result.get("applicable_rules", {}).get("geography_rules", [])),
            }

        # Step 8: Check escalations
        async with pl.step_with_output("check_escalations", {"request_id": request_id}) as bag:
            escalation_result = await asyncio.to_thread(check_escalations, request_id)
            escalations = escalation_result.get("escalations", [])
            bag["output_summary"] = {"escalation_count": len(escalations)}
            bag["metadata"] = {
                "escalation_rules": [e.get("rule_id") for e in escalations],
            }

        # Step 9: Generate recommendation
        async with pl.step_with_output("generate_recommendation", {
            "escalation_count": len(escalations),
            "ranked_count": len(ranked_suppliers),
        }) as bag:
            rec_input = {
                "escalations": escalations,
                "ranked_suppliers": ranked_suppliers,
                "validation": validation_result,
                "request_interpretation": interpretation,
            }
            recommendation = await asyncio.to_thread(generate_recommendation, rec_input)
            bag["output_summary"] = {
                "status": recommendation.get("recommendation_status"),
                "has_reasoning": bool(recommendation.get("reasoning")),
            }

        # Step 10: Fetch historical awards for audit trail
        async with pl.step_with_output("fetch_historical_awards", {"request_id": request_id}) as bag:
            historical_awards = []
            try:
                historical_awards = await org_client.get_awards_by_request(request_id)
            except Exception:
                pass
            bag["output_summary"] = {"award_count": len(historical_awards)}

        # Step 11: Assemble final output
        async with pl.step_with_output("assemble_output", {
            "request_id": request_id,
            "ranked_count": len(ranked_suppliers),
            "escalation_count": len(escalations),
        }) as bag:
            assembly_input = {
                "request_id": request_id,
                "request_data": request_data,
                "validation": validation_result,
                "request_interpretation": interpretation,
                "ranked_suppliers": ranked_suppliers,
                "non_compliant_suppliers": non_compliant_suppliers,
                "policy_evaluation": policy_result,
                "escalations": escalations,
                "recommendation": recommendation,
                "historical_awards": historical_awards,
            }
            output = await asyncio.to_thread(assemble_output, assembly_input)
            output["status"] = "processed"
            bag["output_summary"] = {"status": "processed"}

        await pl.finish(status="completed")
        return output

    except HTTPException:
        await pl.finish(status="failed", error_message="HTTP error during pipeline")
        raise
    except Exception as exc:
        await pl.finish(status="failed", error_message=str(exc)[:2000])
        raise


@router.post(
    "/processRequest",
    response_model=ProcessRequestResponse,
    summary="Process a purchase request through the full pipeline",
    description=(
        "Runs the complete procurement decision pipeline: fetch request, validate, "
        "filter suppliers by category, check compliance, rank by true cost, evaluate "
        "policy, check escalations, generate recommendation, and assemble output. "
        "Returns a structured, auditable sourcing recommendation."
    ),
)
async def process_request(body: ProcessRequest) -> ProcessRequestResponse:
    result = await _run_pipeline(body.request_id)
    return ProcessRequestResponse(**result)
