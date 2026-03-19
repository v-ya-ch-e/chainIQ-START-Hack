"""Processing router — the endpoint that n8n calls."""

from fastapi import APIRouter, HTTPException
from httpx import HTTPStatusError

from app.schemas.processing import ProcessingResult, ProcessRequest
from app.services.pipeline import process_request

router = APIRouter(prefix="/api", tags=["Processing"])


@router.post(
    "/process-request",
    response_model=ProcessingResult,
    summary="Process a purchase request through the procurement decision pipeline",
    description=(
        "Accepts a request_id, fetches all relevant data from the "
        "Organisational Layer, runs validation / policy / supplier ranking / "
        "escalation logic, and returns a structured, auditable result."
    ),
)
async def process_purchase_request(body: ProcessRequest) -> ProcessingResult:
    try:
        return await process_request(body.request_id)
    except HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Request {body.request_id} not found in organisational layer.",
            )
        raise HTTPException(
            status_code=502,
            detail=f"Organisational layer error: {exc.response.status_code}",
        )
