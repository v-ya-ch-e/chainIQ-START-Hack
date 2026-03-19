"""Script-backed endpoints for supplier filtering, ranking, and validation.

These endpoints wrap the standalone scripts in ``scripts/`` as HTTP APIs.
The scripts use synchronous I/O internally, so they are run in a thread
via ``asyncio.to_thread`` to avoid blocking the event loop.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from app.schemas.scripts import (
    FilterSuppliersRequest,
    FilterSuppliersResponse,
    RankSuppliersRequest,
    RankSuppliersResponse,
    ValidateRequestRequest,
    ValidateRequestResponse,
)
from scripts.filterCompaniesByProduct import filter_suppliers
from scripts.rankCompanies import rank_suppliers
from scripts.validateRequest import validate_request

router = APIRouter(prefix="/api", tags=["Scripts"])


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
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Organisational layer error: {exc}")
    return FilterSuppliersResponse(**result)


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
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Organisational layer error: {exc}")
    return RankSuppliersResponse(**result)


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
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Validation error: {exc}")
    return ValidateRequestResponse(**result)
