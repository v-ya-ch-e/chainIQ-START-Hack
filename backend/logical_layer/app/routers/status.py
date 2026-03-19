"""Pipeline status, result, and audit read endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.clients.organisational import OrganisationalClient
from app.dependencies import get_org_client, get_pipeline_runner
from app.pipeline.runner import PipelineRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline Status"])


@router.get("/status/{request_id}")
async def get_pipeline_status(
    request_id: str,
    org: OrganisationalClient = Depends(get_org_client),
    runner: PipelineRunner = Depends(get_pipeline_runner),
):
    """Get the latest processing status for a request."""
    try:
        runs = await org.get_runs_by_request(request_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")

    if not runs:
        raise HTTPException(status_code=404, detail="No pipeline runs found")

    latest = runs[0] if isinstance(runs, list) else runs

    response: dict = {
        "request_id": request_id,
        "latest_run": latest,
    }

    cached = runner.get_cached_result(request_id)
    if cached:
        response["recommendation_status"] = cached.recommendation.status
        response["escalation_count"] = len(cached.escalations)
        response["confidence_score"] = cached.recommendation.confidence_score
    else:
        persisted = await org.get_latest_pipeline_result(request_id)
        if persisted:
            summary = persisted.get("summary") or {}
            response["recommendation_status"] = persisted.get("recommendation_status")
            response["escalation_count"] = summary.get("escalation_count", 0)
            response["confidence_score"] = summary.get("confidence_score", 0)

    return response


@router.get("/result/{request_id}")
async def get_pipeline_result(
    request_id: str,
    org: OrganisationalClient = Depends(get_org_client),
    runner: PipelineRunner = Depends(get_pipeline_runner),
):
    """Get the full pipeline result from the latest successful run.

    Checks in-memory cache first, then falls back to the org layer's
    persisted pipeline results.
    """
    cached = runner.get_cached_result(request_id)
    if cached:
        return cached.model_dump()

    persisted = await org.get_latest_pipeline_result(request_id)
    if persisted and persisted.get("output"):
        return persisted["output"]

    raise HTTPException(
        status_code=404,
        detail="No pipeline result found. Process the request first.",
    )


@router.get("/runs")
async def list_runs(
    request_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    org: OrganisationalClient = Depends(get_org_client),
):
    """List all pipeline runs with filters."""
    try:
        return await org.get_runs(
            request_id=request_id, status=status, skip=skip, limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    org: OrganisationalClient = Depends(get_org_client),
):
    """Get a specific run with all step details."""
    try:
        return await org.get_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")


@router.get("/audit/{request_id}")
async def get_audit_trail(
    request_id: str,
    level: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    step_name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    org: OrganisationalClient = Depends(get_org_client),
):
    """Get full audit trail for a request."""
    try:
        return await org.get_audit_by_request(
            request_id,
            level=level,
            category=category,
            run_id=run_id,
            step_name=step_name,
            skip=skip,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")


@router.get("/audit/{request_id}/summary")
async def get_audit_summary(
    request_id: str,
    org: OrganisationalClient = Depends(get_org_client),
):
    """Get aggregated audit summary for a request."""
    try:
        return await org.get_audit_summary(request_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")
