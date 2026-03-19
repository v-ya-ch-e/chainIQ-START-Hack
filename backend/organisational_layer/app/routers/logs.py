from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.logs import AuditLog, PipelineLogEntry, PipelineRun
from app.schemas.logs import (
    AuditLogBatchCreate,
    AuditLogCreate,
    AuditLogListOut,
    AuditLogOut,
    AuditLogSummaryOut,
    CategoryCount,
    LevelCount,
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


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------

@router.post("/audit", response_model=AuditLogOut, status_code=201)
def create_audit_log(body: AuditLogCreate, db: Session = Depends(get_db)):
    entry = AuditLog(
        request_id=body.request_id,
        run_id=body.run_id,
        timestamp=body.timestamp,
        level=body.level,
        category=body.category,
        step_name=body.step_name,
        message=body.message,
        details=body.details,
        source=body.source,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/audit/batch", response_model=list[AuditLogOut], status_code=201)
def create_audit_logs_batch(body: AuditLogBatchCreate, db: Session = Depends(get_db)):
    rows = [
        AuditLog(
            request_id=e.request_id,
            run_id=e.run_id,
            timestamp=e.timestamp,
            level=e.level,
            category=e.category,
            step_name=e.step_name,
            message=e.message,
            details=e.details,
            source=e.source,
        )
        for e in body.entries
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


@router.get("/audit/by-request/{request_id}", response_model=AuditLogListOut)
def get_audit_logs_by_request(
    request_id: str,
    level: str | None = Query(None),
    category: str | None = Query(None),
    run_id: str | None = Query(None),
    step_name: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog).filter(AuditLog.request_id == request_id)
    if level:
        q = q.filter(AuditLog.level == level)
    if category:
        q = q.filter(AuditLog.category == category)
    if run_id:
        q = q.filter(AuditLog.run_id == run_id)
    if step_name:
        q = q.filter(AuditLog.step_name == step_name)
    total = q.count()
    items = q.order_by(AuditLog.timestamp.asc()).offset(skip).limit(limit).all()
    return AuditLogListOut(items=items, total=total)


@router.get("/audit/summary/{request_id}", response_model=AuditLogSummaryOut)
def get_audit_log_summary(request_id: str, db: Session = Depends(get_db)):
    base = db.query(AuditLog).filter(AuditLog.request_id == request_id)

    total = base.count()
    if total == 0:
        return AuditLogSummaryOut(
            request_id=request_id,
            total_entries=0,
            by_level=[],
            by_category=[],
            distinct_policies=[],
            distinct_suppliers=[],
            escalation_count=0,
        )

    by_level = [
        LevelCount(level=row[0], count=row[1])
        for row in (
            base.with_entities(AuditLog.level, func.count())
            .group_by(AuditLog.level)
            .all()
        )
    ]

    by_category = [
        CategoryCount(category=row[0], count=row[1])
        for row in (
            base.with_entities(AuditLog.category, func.count())
            .group_by(AuditLog.category)
            .all()
        )
    ]

    escalation_count = base.filter(AuditLog.category == "escalation").count()

    time_range = base.with_entities(
        func.min(AuditLog.timestamp), func.max(AuditLog.timestamp)
    ).one()

    policy_rows = (
        base.filter(AuditLog.category == "policy")
        .with_entities(AuditLog.details)
        .all()
    )
    policies: set[str] = set()
    for (det,) in policy_rows:
        if isinstance(det, dict) and "policy_id" in det:
            policies.add(det["policy_id"])

    supplier_rows = (
        base.filter(AuditLog.category.in_(["supplier_filter", "compliance", "ranking", "pricing"]))
        .with_entities(AuditLog.details)
        .all()
    )
    suppliers: set[str] = set()
    for (det,) in supplier_rows:
        if isinstance(det, dict) and "supplier_id" in det:
            suppliers.add(det["supplier_id"])

    return AuditLogSummaryOut(
        request_id=request_id,
        total_entries=total,
        by_level=by_level,
        by_category=by_category,
        distinct_policies=sorted(policies),
        distinct_suppliers=sorted(suppliers),
        escalation_count=escalation_count,
        first_event=time_range[0],
        last_event=time_range[1],
    )


@router.get("/audit", response_model=AuditLogListOut)
def list_audit_logs(
    request_id: str | None = Query(None),
    level: str | None = Query(None),
    category: str | None = Query(None),
    run_id: str | None = Query(None),
    step_name: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if request_id:
        q = q.filter(AuditLog.request_id == request_id)
    if level:
        q = q.filter(AuditLog.level == level)
    if category:
        q = q.filter(AuditLog.category == category)
    if run_id:
        q = q.filter(AuditLog.run_id == run_id)
    if step_name:
        q = q.filter(AuditLog.step_name == step_name)
    total = q.count()
    items = q.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    return AuditLogListOut(items=items, total=total)
