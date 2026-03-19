"""Individual step endpoints for debugging and testing."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.clients.llm import LLMClient
from app.clients.organisational import OrganisationalClient
from app.dependencies import get_llm_client, get_org_client
from app.pipeline.logger import PipelineLogger
from app.pipeline.steps.comply import check_compliance
from app.pipeline.steps.escalate import compute_escalations
from app.pipeline.steps.fetch import fetch_overview
from app.pipeline.steps.filter import filter_suppliers
from app.pipeline.steps.policy import evaluate_policy
from app.pipeline.steps.rank import rank_suppliers
from app.pipeline.steps.validate import validate_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline/steps", tags=["Pipeline Steps"])


class StepRequest(BaseModel):
    request_id: str


@router.post("/fetch")
async def run_fetch(
    body: StepRequest,
    org: OrganisationalClient = Depends(get_org_client),
):
    """Run Step 1 (fetch) in isolation."""
    run_id = str(uuid.uuid4())
    pl = PipelineLogger(org, run_id, body.request_id)
    await pl.start_run()
    try:
        result = await fetch_overview(body.request_id, org, pl)
        await pl.flush_audit()
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/validate")
async def run_validate(
    body: StepRequest,
    org: OrganisationalClient = Depends(get_org_client),
    llm: LLMClient | None = Depends(get_llm_client),
):
    """Run Steps 1-2 (fetch + validate) in isolation."""
    run_id = str(uuid.uuid4())
    pl = PipelineLogger(org, run_id, body.request_id)
    await pl.start_run()
    try:
        fetch_result = await fetch_overview(body.request_id, org, pl)
        await pl.flush_audit()
        result = await validate_request(fetch_result, llm, pl, org)
        await pl.flush_audit()
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/filter")
async def run_filter(
    body: StepRequest,
    org: OrganisationalClient = Depends(get_org_client),
    llm: LLMClient | None = Depends(get_llm_client),
):
    """Run Steps 1-3 (fetch + validate + filter) in isolation."""
    run_id = str(uuid.uuid4())
    pl = PipelineLogger(org, run_id, body.request_id)
    await pl.start_run()
    try:
        fetch_result = await fetch_overview(body.request_id, org, pl)
        await pl.flush_audit()
        await validate_request(fetch_result, llm, pl, org)
        await pl.flush_audit()
        result = await filter_suppliers(fetch_result, pl)
        await pl.flush_audit()
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/comply")
async def run_comply(
    body: StepRequest,
    org: OrganisationalClient = Depends(get_org_client),
    llm: LLMClient | None = Depends(get_llm_client),
):
    """Run Steps 1-4 (fetch + validate + filter + comply) in isolation."""
    run_id = str(uuid.uuid4())
    pl = PipelineLogger(org, run_id, body.request_id)
    await pl.start_run()
    try:
        fetch_result = await fetch_overview(body.request_id, org, pl)
        await pl.flush_audit()
        await validate_request(fetch_result, llm, pl, org)
        await pl.flush_audit()
        filter_result = await filter_suppliers(fetch_result, pl)
        await pl.flush_audit()
        result = await check_compliance(fetch_result, filter_result, org, pl)
        await pl.flush_audit()
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/rank")
async def run_rank(
    body: StepRequest,
    org: OrganisationalClient = Depends(get_org_client),
    llm: LLMClient | None = Depends(get_llm_client),
):
    """Run Steps 1-5 (through ranking) in isolation."""
    run_id = str(uuid.uuid4())
    pl = PipelineLogger(org, run_id, body.request_id)
    await pl.start_run()
    try:
        fetch_result = await fetch_overview(body.request_id, org, pl)
        await pl.flush_audit()
        await validate_request(fetch_result, llm, pl, org)
        await pl.flush_audit()
        filter_result = await filter_suppliers(fetch_result, pl)
        await pl.flush_audit()
        compliance_result = await check_compliance(fetch_result, filter_result, org, pl)
        await pl.flush_audit()
        result = await rank_suppliers(fetch_result, compliance_result, pl)
        await pl.flush_audit()
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/escalate")
async def run_escalate(
    body: StepRequest,
    org: OrganisationalClient = Depends(get_org_client),
    llm: LLMClient | None = Depends(get_llm_client),
):
    """Run Steps 1-7 (through escalation) in isolation."""
    run_id = str(uuid.uuid4())
    pl = PipelineLogger(org, run_id, body.request_id)
    await pl.start_run()
    try:
        fetch_result = await fetch_overview(body.request_id, org, pl)
        await pl.flush_audit()
        validation_result = await validate_request(fetch_result, llm, pl, org)
        await pl.flush_audit()
        filter_result = await filter_suppliers(fetch_result, pl)
        await pl.flush_audit()
        compliance_result = await check_compliance(fetch_result, filter_result, org, pl)
        await pl.flush_audit()
        rank_result = await rank_suppliers(fetch_result, compliance_result, pl)
        await pl.flush_audit()
        result = await compute_escalations(
            fetch_result, validation_result, compliance_result, rank_result, pl, org,
        )
        await pl.flush_audit()
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
