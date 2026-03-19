"""Pipeline endpoints for the n8n procurement workflow.

These endpoints correspond to the individual steps in the n8n pipeline:
fetch-request, check-compliance, evaluate-policy, check-escalations,
generate-recommendation, assemble-output, and format-invalid-response.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from app.clients.organisational import org_client
from app.schemas.pipeline import (
    AssembleOutputRequest,
    AssembleOutputResponse,
    CheckComplianceRequest,
    CheckComplianceResponse,
    CheckEscalationsRequest,
    CheckEscalationsResponse,
    EvaluatePolicyRequest,
    EvaluatePolicyResponse,
    FetchRequestRequest,
    FetchRequestResponse,
    FormatInvalidResponseRequest,
    FormatInvalidResponseResponse,
    GenerateRecommendationRequest,
    GenerateRecommendationResponse,
)
from scripts.assembleOutput import assemble_output
from scripts.checkCompliance import check_compliance
from scripts.checkEscalations import check_escalations
from scripts.evaluatePolicy import evaluate_policy
from scripts.formatInvalidResponse import format_invalid_response
from scripts.generateRecommendation import generate_recommendation

router = APIRouter(prefix="/api", tags=["Pipeline"])


@router.post(
    "/fetch-request",
    response_model=FetchRequestResponse,
    summary="Fetch a purchase request from the Organisational Layer",
    description=(
        "Proxy endpoint that fetches the full purchase request object from the "
        "Organisational Layer. Returns the request data as-is."
    ),
)
async def fetch_request_endpoint(body: FetchRequestRequest) -> dict:
    try:
        data = await org_client.get_request(body.request_id)
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Organisational layer error: {exc}")


@router.post(
    "/check-compliance",
    response_model=CheckComplianceResponse,
    summary="Check compliance rules for each supplier",
    description=(
        "For each supplier from the filter step, checks restriction status, "
        "delivery country coverage, and data residency support. Returns suppliers "
        "split into compliant and non-compliant lists with reasons."
    ),
)
async def check_compliance_endpoint(body: CheckComplianceRequest) -> CheckComplianceResponse:
    try:
        result = await asyncio.to_thread(check_compliance, body.request_data, body.suppliers)
        return CheckComplianceResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Compliance check error: {exc}")


@router.post(
    "/evaluate-policy",
    response_model=EvaluatePolicyResponse,
    summary="Evaluate procurement policies for a request",
    description=(
        "Evaluates approval threshold, preferred supplier status, restriction "
        "checks, and applicable category/geography rules. Produces the "
        "policy_evaluation section of the pipeline output."
    ),
)
async def evaluate_policy_endpoint(body: EvaluatePolicyRequest) -> EvaluatePolicyResponse:
    try:
        result = await asyncio.to_thread(
            evaluate_policy, body.request_data, body.ranked_suppliers, body.non_compliant_suppliers
        )
        return EvaluatePolicyResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Policy evaluation error: {exc}")


@router.post(
    "/check-escalations",
    response_model=CheckEscalationsResponse,
    summary="Fetch computed escalations for a request",
    description=(
        "Retrieves escalations computed by the Organisational Layer's escalation "
        "engine (ER-001 through ER-008 + AT threshold conflict detection)."
    ),
)
async def check_escalations_endpoint(body: CheckEscalationsRequest) -> CheckEscalationsResponse:
    try:
        result = await asyncio.to_thread(check_escalations, body.request_id)
        return CheckEscalationsResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Escalation check error: {exc}")


@router.post(
    "/generate-recommendation",
    response_model=GenerateRecommendationResponse,
    summary="Generate a procurement recommendation",
    description=(
        "Determines recommendation status (cannot_proceed / proceed_with_conditions / proceed) "
        "based on escalations, ranked suppliers, and validation results. Uses Claude LLM "
        "to generate human-readable reasoning."
    ),
)
async def generate_recommendation_endpoint(
    body: GenerateRecommendationRequest,
) -> GenerateRecommendationResponse:
    try:
        result = await asyncio.to_thread(generate_recommendation, body.model_dump())
        return GenerateRecommendationResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Recommendation generation error: {exc}")


@router.post(
    "/assemble-output",
    response_model=AssembleOutputResponse,
    summary="Assemble the final pipeline output",
    description=(
        "Combines all pipeline step outputs into the complete output format "
        "matching example_output.json. Uses Claude LLM to enrich validation "
        "issues and supplier recommendation notes."
    ),
)
async def assemble_output_endpoint(body: AssembleOutputRequest) -> AssembleOutputResponse:
    try:
        result = await asyncio.to_thread(assemble_output, body.model_dump())
        return AssembleOutputResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Output assembly error: {exc}")


@router.post(
    "/format-invalid-response",
    response_model=FormatInvalidResponseResponse,
    summary="Format response for invalid/incomplete requests",
    description=(
        "Formats a structured response for requests that fail validation. "
        "Used on the 'Invalid request' branch of the n8n pipeline. "
        "Uses Claude LLM to generate human-readable summaries."
    ),
)
async def format_invalid_response_endpoint(
    body: FormatInvalidResponseRequest,
) -> FormatInvalidResponseResponse:
    try:
        result = await asyncio.to_thread(
            format_invalid_response, body.request_data, body.validation, body.request_interpretation
        )
        return FormatInvalidResponseResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Invalid response formatting error: {exc}")
