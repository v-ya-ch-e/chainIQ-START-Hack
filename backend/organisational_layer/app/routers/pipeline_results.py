"""Pipeline result persistence endpoints.

The logical layer POSTs the full pipeline output here after processing a
request. The frontend reads these endpoints to display evaluated requests.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.pipeline_results import PipelineResult
from app.schemas.pipeline_results import (
    PipelineResultCreate,
    PipelineResultListItem,
    PipelineResultListOut,
    PipelineResultOut,
    PipelineResultSummary,
)

router = APIRouter(prefix="/api/pipeline-results", tags=["Pipeline Results"])


def _extract_summary(output: dict) -> dict:
    """Derive lightweight summary from the full pipeline output."""
    shortlist = output.get("supplier_shortlist", [])
    excluded = output.get("suppliers_excluded", [])
    escalations = output.get("escalations", [])
    validation = output.get("validation", {})
    recommendation = output.get("recommendation", {})

    top = shortlist[0] if shortlist else {}
    blocking = [e for e in escalations if e.get("blocking")]

    return PipelineResultSummary(
        supplier_count=len(shortlist),
        excluded_count=len(excluded),
        escalation_count=len(escalations),
        blocking_escalation_count=len(blocking),
        top_supplier_id=top.get("supplier_id"),
        top_supplier_name=top.get("supplier_name"),
        total_issues=len(validation.get("issues_detected", [])),
        confidence_score=recommendation.get("confidence_score", 0),
    ).model_dump()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post("/", response_model=PipelineResultOut, status_code=201)
def save_pipeline_result(body: PipelineResultCreate, db: Session = Depends(get_db)):
    """Persist a full pipeline result. Called by the logical layer after processing."""
    existing = (
        db.query(PipelineResult)
        .filter(PipelineResult.run_id == body.run_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline result for run_id {body.run_id} already exists",
        )

    rec_status = body.recommendation_status
    if not rec_status:
        rec_status = body.output.get("recommendation", {}).get("status")

    result = PipelineResult(
        run_id=body.run_id,
        request_id=body.request_id,
        status=body.status,
        recommendation_status=rec_status,
        processed_at=body.processed_at,
        output=body.output,
        summary=_extract_summary(body.output),
        created_at=datetime.utcnow(),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


# ---------------------------------------------------------------------------
# List (paginated, filterable)
# ---------------------------------------------------------------------------


@router.get("/", response_model=PipelineResultListOut)
def list_pipeline_results(
    request_id: str | None = Query(None, description="Filter by request ID"),
    status: str | None = Query(None, description="Filter by pipeline status"),
    recommendation_status: str | None = Query(
        None, description="Filter by recommendation status"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Paginated list of pipeline results. Omits the full output blob for speed."""
    q = db.query(PipelineResult)
    if request_id:
        q = q.filter(PipelineResult.request_id == request_id)
    if status:
        q = q.filter(PipelineResult.status == status)
    if recommendation_status:
        q = q.filter(PipelineResult.recommendation_status == recommendation_status)

    total = q.count()
    rows = q.order_by(PipelineResult.processed_at.desc()).offset(skip).limit(limit).all()

    items = [
        PipelineResultListItem(
            id=r.id,
            run_id=r.run_id,
            request_id=r.request_id,
            status=r.status,
            recommendation_status=r.recommendation_status,
            processed_at=r.processed_at,
            summary=r.summary,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return PipelineResultListOut(items=items, total=total, skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# By request (must be above /{run_id} to avoid route conflicts)
# ---------------------------------------------------------------------------


@router.get(
    "/by-request/{request_id}",
    response_model=list[PipelineResultOut],
)
def get_results_by_request(request_id: str, db: Session = Depends(get_db)):
    """Get all pipeline results for a request, newest first. Includes full output."""
    rows = (
        db.query(PipelineResult)
        .filter(PipelineResult.request_id == request_id)
        .order_by(PipelineResult.processed_at.desc())
        .all()
    )
    return rows


# ---------------------------------------------------------------------------
# Latest for a request (must be above /{run_id} to avoid route conflicts)
# ---------------------------------------------------------------------------


@router.get(
    "/latest/{request_id}",
    response_model=PipelineResultOut,
)
def get_latest_result(request_id: str, db: Session = Depends(get_db)):
    """Get the most recent pipeline result for a request."""
    result = (
        db.query(PipelineResult)
        .filter(PipelineResult.request_id == request_id)
        .order_by(PipelineResult.processed_at.desc())
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No pipeline results found for request {request_id}",
        )
    return result


# ---------------------------------------------------------------------------
# Detail by run_id
# ---------------------------------------------------------------------------


@router.get("/{run_id}", response_model=PipelineResultOut)
def get_pipeline_result(run_id: str, db: Session = Depends(get_db)):
    """Get a single pipeline result by run_id, including the full output."""
    result = (
        db.query(PipelineResult)
        .filter(PipelineResult.run_id == run_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Pipeline result {run_id} not found")
    return result


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{run_id}", status_code=204)
def delete_pipeline_result(run_id: str, db: Session = Depends(get_db)):
    """Delete a pipeline result by run_id."""
    result = (
        db.query(PipelineResult)
        .filter(PipelineResult.run_id == run_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Pipeline result {run_id} not found")
    db.delete(result)
    db.commit()
