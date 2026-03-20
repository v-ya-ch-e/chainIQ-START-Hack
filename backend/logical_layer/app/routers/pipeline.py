"""Pipeline execution endpoints: process single and batch requests."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_pipeline_runner
from app.pipeline.runner import PipelineRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])


class ProcessRequest(BaseModel):
    request_id: str


class BatchProcessRequest(BaseModel):
    request_ids: list[str]
    concurrency: int = Field(default=5, ge=1, le=20)


class BatchResponse(BaseModel):
    batch_id: str
    queued: int
    concurrency: int
    message: str = "Processing started"


@router.post("/process")
async def process_request(
    body: ProcessRequest,
    runner: PipelineRunner = Depends(get_pipeline_runner),
):
    """Process a single purchase request through the full pipeline."""
    try:
        result = await runner.process(body.request_id)
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Pipeline failed for %s", body.request_id)
        if "404" in str(exc) or "Not Found" in str(exc):
            raise HTTPException(status_code=404, detail=f"Request {body.request_id} not found")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(exc)[:500]}")


@router.post("/process-batch", response_model=BatchResponse, status_code=202)
async def process_batch(
    body: BatchProcessRequest,
    runner: PipelineRunner = Depends(get_pipeline_runner),
):
    """Process multiple purchase requests concurrently."""

    batch_id = str(uuid.uuid4())
    semaphore = asyncio.Semaphore(body.concurrency)

    async def _run_one(request_id: str) -> None:
        async with semaphore:
            try:
                await runner.process(request_id)
            except Exception:
                logger.exception("Batch item %s failed", request_id)

    async def _run_batch() -> None:
        await asyncio.gather(*[_run_one(rid) for rid in body.request_ids])

    asyncio.create_task(_run_batch())

    return BatchResponse(
        batch_id=batch_id,
        queued=len(body.request_ids),
        concurrency=body.concurrency,
    )
