"""Processing router — stub endpoint for the full procurement pipeline (not yet implemented)."""

from fastapi import APIRouter

from app.schemas.processing import ProcessRequest, ProcessRequestResponse

router = APIRouter(prefix="/api", tags=["Processing"])


@router.post(
    "/processRequest",
    response_model=ProcessRequestResponse,
    summary="Process a purchase request (not yet implemented)",
    description=(
        "Placeholder endpoint for the full procurement decision pipeline. "
        "Returns a stub response. Use /api/filter-suppliers and "
        "/api/rank-suppliers for the individual processing steps."
    ),
)
async def process_request(body: ProcessRequest) -> ProcessRequestResponse:
    return ProcessRequestResponse(request_id=body.request_id)
