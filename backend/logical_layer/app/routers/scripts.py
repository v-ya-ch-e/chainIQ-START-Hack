"""Script-backed endpoints for supplier filtering, ranking, and validation.

These endpoints wrap the standalone scripts in ``scripts/`` as HTTP APIs.
The scripts use synchronous I/O internally, so they are run in a thread
via ``asyncio.to_thread`` to avoid blocking the event loop.
"""

import asyncio
import mimetypes

from fastapi import APIRouter, HTTPException, UploadFile

from app.schemas.scripts import (
    CreateRequestResponse,
    FilterSuppliersRequest,
    FilterSuppliersResponse,
    RankSuppliersRequest,
    RankSuppliersResponse,
    ValidateRequestRequest,
    ValidateRequestResponse,
)
from scripts.createRequest import create_request
from scripts.filterCompaniesByProduct import filter_suppliers
from scripts.rankCompanies import rank_suppliers
from scripts.validateRequest import validate_request

router = APIRouter(prefix="/api", tags=["Scripts"])


@router.post(
    "/create-request",
    response_model=CreateRequestResponse,
    summary="Convert any file into a structured purchase request",
    description=(
        "Accepts a file upload (JSON, plain text, PDF, image) and converts it "
        "into a structured purchase request matching the canonical schema. "
        "For JSON inputs, missing fields are filled from request_text. "
        "For other formats, the Anthropic API extracts the structured data. "
        "Returns the request and a completeness flag."
    ),
)
async def create_request_endpoint(file: UploadFile) -> CreateRequestResponse:
    try:
        raw = await file.read()

        try:
            file_content = raw.decode("utf-8")
            result = await asyncio.to_thread(create_request, file_content)
        except UnicodeDecodeError:
            media_type = (
                file.content_type
                or mimetypes.guess_type(file.filename or "")[0]
                or "application/octet-stream"
            )
            result = await asyncio.to_thread(
                create_request, file_bytes=raw, media_type=media_type,
            )

        return CreateRequestResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Request creation error: {exc}")


@router.post(
    "/filter-suppliers",
    response_model=FilterSuppliersResponse,
    summary="Filter suppliers by product category",
    description=(
        "Accepts purchase request data (at minimum category_l1 and category_l2), "
        "queries the Organisational Layer to find all suppliers serving that "
        "category, and returns the matching supplier-category rows."
    ),
)
async def filter_suppliers_endpoint(body: FilterSuppliersRequest) -> FilterSuppliersResponse:
    try:
        result = await asyncio.to_thread(filter_suppliers, body.model_dump())
        return FilterSuppliersResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Organisational layer error: {exc}")


@router.post(
    "/rank-suppliers",
    response_model=RankSuppliersResponse,
    summary="Rank suppliers by true cost",
    description=(
        "Accepts purchase request data and a list of supplier rows "
        "(typically from /api/filter-suppliers), computes a true-cost score "
        "adjusted for quality, risk, and ESG, and returns suppliers ranked "
        "from best to worst."
    ),
)
async def rank_suppliers_endpoint(body: RankSuppliersRequest) -> RankSuppliersResponse:
    try:
        result = await asyncio.to_thread(rank_suppliers, body.request, body.suppliers)
        return RankSuppliersResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Organisational layer error: {exc}")


@router.post(
    "/validate-request",
    response_model=ValidateRequestResponse,
    summary="Validate a purchase request for completeness and consistency",
    description=(
        "Accepts a full purchase request, runs deterministic checks for "
        "required/optional fields, then uses the Anthropic API to detect "
        "contradictions between the free-text request_text and structured "
        "fields. Returns validation issues and a structured interpretation."
    ),
)
async def validate_request_endpoint(body: ValidateRequestRequest) -> ValidateRequestResponse:
    try:
        result = await asyncio.to_thread(validate_request, body.model_dump())
        return ValidateRequestResponse(**result)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Validation error: {exc}")
