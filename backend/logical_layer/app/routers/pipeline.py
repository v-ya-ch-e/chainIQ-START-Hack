"""Pipeline endpoints for the n8n procurement workflow.

These endpoints correspond to the individual steps in the n8n pipeline:
fetch-request, check-compliance, evaluate-policy, check-escalations,
generate-recommendation, assemble-output, and format-invalid-response.

When an ``X-Pipeline-Run-Id`` header is present, each endpoint also logs
its execution to the Organisational Layer's logging API.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException

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
from app.services.pipeline_logger import truncate_summary
from scripts.assembleOutput import assemble_output
from scripts.checkCompliance import check_compliance
from scripts.checkEscalations import check_escalations
from scripts.evaluatePolicy import evaluate_policy
from scripts.formatInvalidResponse import format_invalid_response
from scripts.generateRecommendation import generate_recommendation

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Pipeline"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


async def _log_step(
    run_id: str | None,
    step_name: str,
    step_order: int,
    started_at: str,
    duration_ms: int,
    status: str,
    input_summary: Any = None,
    output_summary: Any = None,
    error_message: str | None = None,
) -> None:
    """Best-effort single-call log for standalone pipeline endpoints."""
    if not run_id:
        return
    try:
        resp = await org_client.create_log_entry(
            run_id=run_id,
            step_name=step_name,
            step_order=step_order,
            started_at=started_at,
            input_summary=truncate_summary(input_summary),
        )
        entry_id = resp.get("id")
        if entry_id:
            fields: dict[str, Any] = {
                "status": status,
                "completed_at": _now_iso(),
                "duration_ms": duration_ms,
            }
            if output_summary is not None:
                fields["output_summary"] = truncate_summary(output_summary)
            if error_message:
                fields["error_message"] = error_message[:2000]
            await org_client.update_log_entry(entry_id, **fields)
    except Exception:
        _log.warning("Failed to log step %s for run %s", step_name, run_id)


@router.post(
    "/fetch-request",
    response_model=FetchRequestResponse,
    summary="Fetch a purchase request from the Organisational Layer",
    description=(
        "Proxy endpoint that fetches the full purchase request object from the "
        "Organisational Layer. Returns the request data as-is."
    ),
)
async def fetch_request_endpoint(
    body: FetchRequestRequest,
    x_pipeline_run_id: str | None = Header(None),
) -> dict:
    started = _now_iso()
    t0 = time.monotonic()
    try:
        data = await org_client.get_request(body.request_id)
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "fetch_request", 1, started, ms, "completed",
                        {"request_id": body.request_id},
                        {"title": data.get("title"), "country": data.get("country")})
        return data
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "fetch_request", 1, started, ms, "failed",
                        {"request_id": body.request_id}, error_message=str(exc))
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
async def check_compliance_endpoint(
    body: CheckComplianceRequest,
    x_pipeline_run_id: str | None = Header(None),
) -> CheckComplianceResponse:
    started = _now_iso()
    t0 = time.monotonic()
    try:
        result = await asyncio.to_thread(check_compliance, body.request_data, body.suppliers)
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "check_compliance", 5, started, ms, "completed",
                        {"supplier_count": len(body.suppliers)},
                        {"compliant": len(result.get("compliant", [])),
                         "non_compliant": len(result.get("non_compliant", []))})
        return CheckComplianceResponse(**result)
    except (ValueError, KeyError) as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "check_compliance", 5, started, ms, "failed",
                        error_message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "check_compliance", 5, started, ms, "failed",
                        error_message=str(exc))
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
async def evaluate_policy_endpoint(
    body: EvaluatePolicyRequest,
    x_pipeline_run_id: str | None = Header(None),
) -> EvaluatePolicyResponse:
    started = _now_iso()
    t0 = time.monotonic()
    try:
        result = await asyncio.to_thread(
            evaluate_policy, body.request_data, body.ranked_suppliers, body.non_compliant_suppliers
        )
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "evaluate_policy", 7, started, ms, "completed",
                        {"ranked_count": len(body.ranked_suppliers)},
                        {"has_threshold": bool(result.get("approval_threshold"))})
        return EvaluatePolicyResponse(**result)
    except (ValueError, KeyError) as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "evaluate_policy", 7, started, ms, "failed",
                        error_message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "evaluate_policy", 7, started, ms, "failed",
                        error_message=str(exc))
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
async def check_escalations_endpoint(
    body: CheckEscalationsRequest,
    x_pipeline_run_id: str | None = Header(None),
) -> CheckEscalationsResponse:
    started = _now_iso()
    t0 = time.monotonic()
    try:
        result = await asyncio.to_thread(check_escalations, body.request_id)
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "check_escalations", 8, started, ms, "completed",
                        {"request_id": body.request_id},
                        {"escalation_count": len(result.get("escalations", []))})
        return CheckEscalationsResponse(**result)
    except (ValueError, KeyError) as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "check_escalations", 8, started, ms, "failed",
                        error_message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "check_escalations", 8, started, ms, "failed",
                        error_message=str(exc))
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
    x_pipeline_run_id: str | None = Header(None),
) -> GenerateRecommendationResponse:
    started = _now_iso()
    t0 = time.monotonic()
    try:
        result = await asyncio.to_thread(generate_recommendation, body.model_dump())
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "generate_recommendation", 9, started, ms, "completed",
                        {"escalation_count": len(body.escalations)},
                        {"status": result.get("recommendation_status")})
        return GenerateRecommendationResponse(**result)
    except (ValueError, KeyError) as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "generate_recommendation", 9, started, ms, "failed",
                        error_message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "generate_recommendation", 9, started, ms, "failed",
                        error_message=str(exc))
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
async def assemble_output_endpoint(
    body: AssembleOutputRequest,
    x_pipeline_run_id: str | None = Header(None),
) -> AssembleOutputResponse:
    started = _now_iso()
    t0 = time.monotonic()
    try:
        result = await asyncio.to_thread(assemble_output, body.model_dump())
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "assemble_output", 11, started, ms, "completed",
                        {"request_id": body.request_id},
                        {"status": result.get("status")})
        return AssembleOutputResponse(**result)
    except (ValueError, KeyError) as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "assemble_output", 11, started, ms, "failed",
                        error_message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "assemble_output", 11, started, ms, "failed",
                        error_message=str(exc))
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
    x_pipeline_run_id: str | None = Header(None),
) -> FormatInvalidResponseResponse:
    started = _now_iso()
    t0 = time.monotonic()
    try:
        result = await asyncio.to_thread(
            format_invalid_response, body.request_data, body.validation, body.request_interpretation
        )
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "format_invalid_response", 3, started, ms, "completed",
                        {"has_validation": bool(body.validation)},
                        {"status": "invalid"})
        return FormatInvalidResponseResponse(**result)
    except (ValueError, KeyError) as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "format_invalid_response", 3, started, ms, "failed",
                        error_message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        await _log_step(x_pipeline_run_id, "format_invalid_response", 3, started, ms, "failed",
                        error_message=str(exc))
        raise HTTPException(status_code=502, detail=f"Invalid response formatting error: {exc}")
