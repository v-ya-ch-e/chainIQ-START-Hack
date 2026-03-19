from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.logs import PipelineLogEntry, PipelineRun
from app.schemas.logs import (
    PipelineLogEntryCreate,
    PipelineLogEntryOut,
    PipelineLogEntryUpdate,
    PipelineRunCreate,
    PipelineRunDetailOut,
    PipelineRunListOut,
    PipelineRunOut,
    PipelineRunUpdate,
)

router = APIRouter(prefix="/api/logs", tags=["Pipeline Logs"])


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

@router.post("/runs", response_model=PipelineRunOut, status_code=201)
def create_run(body: PipelineRunCreate, db: Session = Depends(get_db)):
    run = PipelineRun(
        run_id=body.run_id,
        request_id=body.request_id,
        status="running",
        started_at=body.started_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.patch("/runs/{run_id}", response_model=PipelineRunOut)
def update_run(run_id: str, body: PipelineRunUpdate, db: Session = Depends(get_db)):
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(run, field, value)
    db.commit()
    db.refresh(run)
    return run


@router.get("/runs", response_model=PipelineRunListOut)
def list_runs(
    request_id: str | None = Query(None),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(PipelineRun)
    if request_id:
        q = q.filter(PipelineRun.request_id == request_id)
    if status:
        q = q.filter(PipelineRun.status == status)
    total = q.count()
    items = q.order_by(PipelineRun.started_at.desc()).offset(skip).limit(limit).all()
    return PipelineRunListOut(items=items, total=total)


@router.get("/runs/{run_id}", response_model=PipelineRunDetailOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = (
        db.query(PipelineRun)
        .options(joinedload(PipelineRun.entries))
        .filter(PipelineRun.run_id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@router.get("/by-request/{request_id}", response_model=list[PipelineRunDetailOut])
def get_runs_by_request(request_id: str, db: Session = Depends(get_db)):
    runs = (
        db.query(PipelineRun)
        .options(joinedload(PipelineRun.entries))
        .filter(PipelineRun.request_id == request_id)
        .order_by(PipelineRun.started_at.desc())
        .all()
    )
    return runs


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------

@router.post("/entries", response_model=PipelineLogEntryOut, status_code=201)
def create_entry(body: PipelineLogEntryCreate, db: Session = Depends(get_db)):
    entry = PipelineLogEntry(
        run_id=body.run_id,
        step_name=body.step_name,
        step_order=body.step_order,
        status="started",
        started_at=body.started_at,
        input_summary=body.input_summary,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/entries/{entry_id}", response_model=PipelineLogEntryOut)
def update_entry(entry_id: int, body: PipelineLogEntryUpdate, db: Session = Depends(get_db)):
    entry = db.query(PipelineLogEntry).filter(PipelineLogEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
    update_data = body.model_dump(exclude_unset=True)
    if "metadata_" in update_data:
        update_data["metadata_"] = update_data.pop("metadata_")
    for field, value in update_data.items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry
