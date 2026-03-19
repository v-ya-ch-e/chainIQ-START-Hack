"""Script-backed endpoints for supplier filtering and ranking.

These endpoints wrap the standalone scripts in ``scripts/`` as HTTP APIs.
The scripts use synchronous urllib internally, so they are run in a thread
via ``asyncio.to_thread`` to avoid blocking the event loop.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from app.schemas.scripts import (
    FilterSuppliersRequest,
    FilterSuppliersResponse,
    RankSuppliersRequest,
    RankSuppliersResponse,
)
from scripts.filterCompaniesByProduct import filter_suppliers
from scripts.rankCompanies import rank_suppliers

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
