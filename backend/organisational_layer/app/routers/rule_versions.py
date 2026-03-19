"""Rule versioning and evaluation traceability endpoints."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.evaluations import (
    EvaluationRun,
    HardRuleCheck,
    PolicyCheck,
    RuleChangeLog,
    RuleDefinition,
    RuleVersion,
    SupplierEvaluation,
)
from app.schemas.rule_versions import (
    EvaluationDetailOut,
    EvaluationRunCreate,
    RuleCheckOut,
    RuleDefinitionOut,
    RuleVersionCreate,
    RuleVersionOut,
    RuleVersionWithDefinitionOut,
    SupplierRuleBreakdownOut,
)

router = APIRouter(prefix="/api/rule-versions", tags=["Rule Versions"])


def _get_active_version(db: Session, rule_id: str) -> RuleVersion | None:
    """Return the currently active rule version (valid_to IS NULL)."""
    return (
        db.query(RuleVersion)
        .filter(
            RuleVersion.rule_id == rule_id,
            RuleVersion.valid_to.is_(None),
        )
        .first()
    )


@router.get("/definitions", response_model=list[RuleDefinitionOut])
def list_rule_definitions(db: Session = Depends(get_db)):
    """List all rule definitions (HR-*, PC-*, ER-*)."""
    return db.query(RuleDefinition).order_by(RuleDefinition.rule_id).all()


@router.get("/definitions/{rule_id}", response_model=RuleDefinitionOut)
def get_rule_definition(rule_id: str, db: Session = Depends(get_db)):
    """Get a single rule definition."""
    r = db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rule definition not found")
    return r


@router.get("/versions", response_model=list[RuleVersionWithDefinitionOut])
def list_rule_versions(
    rule_id: str | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    """List rule versions. Filter by rule_id and/or active_only (valid_to IS NULL)."""
    q = (
        db.query(RuleVersion)
        .join(RuleDefinition, RuleVersion.rule_id == RuleDefinition.rule_id)
        .add_columns(RuleDefinition.rule_name, RuleDefinition.rule_type)
    )
    if rule_id:
        q = q.filter(RuleVersion.rule_id == rule_id)
    if active_only:
        q = q.filter(RuleVersion.valid_to.is_(None))
    rows = q.order_by(RuleVersion.rule_id, RuleVersion.version_num.desc()).all()
    return [
        RuleVersionWithDefinitionOut(
            version_id=r.version_id,
            rule_id=r.rule_id,
            version_num=r.version_num,
            rule_config=r.rule_config,
            valid_from=r.valid_from,
            valid_to=r.valid_to,
            changed_by=r.changed_by,
            change_reason=r.change_reason,
            rule_name=rule_name,
            rule_type=rule_type,
        )
        for r, rule_name, rule_type in rows
    ]


@router.post("/versions", response_model=RuleVersionOut)
def create_rule_version(
    body: RuleVersionCreate,
    db: Session = Depends(get_db),
):
    """
    Add a new rule version. Sets valid_to=NOW() on the previously active version.
    Returns the new version.
    """
    # Ensure rule exists
    rule = db.query(RuleDefinition).filter(RuleDefinition.rule_id == body.rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule definition not found")

    now = datetime.utcnow()
    old_version = _get_active_version(db, body.rule_id)

    # Get next version number
    max_ver = (
        db.query(func.max(RuleVersion.version_num))
        .filter(RuleVersion.rule_id == body.rule_id)
        .scalar()
    )
    version_num = (max_ver or 0) + 1

    # Set valid_to on previous active version
    if old_version:
        old_version.valid_to = now
        old_version.changed_by = body.changed_by
        old_version.change_reason = body.change_reason

    # Create new version
    new_version_id = str(uuid.uuid4())
    new_version = RuleVersion(
        version_id=new_version_id,
        rule_id=body.rule_id,
        version_num=version_num,
        rule_config=body.rule_config,
        valid_from=now,
        valid_to=None,
        changed_by=body.changed_by,
        change_reason=body.change_reason,
    )
    db.add(new_version)
    db.flush()  # Ensure new_version is inserted before rule_change_log (FK dependency)

    # Audit log
    rule_change_log = RuleChangeLog(
        log_id=str(uuid.uuid4()),
        rule_id=body.rule_id,
        old_version_id=old_version.version_id if old_version else None,
        new_version_id=new_version_id,
        changed_at=now,
        changed_by=body.changed_by or "system",
        change_reason=body.change_reason,
    )
    db.add(rule_change_log)

    db.commit()
    db.refresh(new_version)
    return new_version


@router.get("/versions/active/{rule_id}", response_model=RuleVersionOut)
def get_active_version(rule_id: str, db: Session = Depends(get_db)):
    """Get the currently active version for a rule (valid_to IS NULL)."""
    v = _get_active_version(db, rule_id)
    if not v:
        raise HTTPException(
            status_code=404,
            detail=f"No active version found for rule {rule_id}",
        )
    return v


@router.get("/evaluations/{run_id}", response_model=EvaluationDetailOut)
def get_evaluation_detail(
    run_id: str,
    db: Session = Depends(get_db),
):
    """
    Get full evaluation detail with per-supplier rule pass/fail breakdown.
    Shows which rule versions passed/failed for each supplier.
    """
    run = (
        db.query(EvaluationRun)
        .filter(EvaluationRun.run_id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")

    # Build supplier breakdowns from hard_rule_checks and policy_checks
    hard_checks = (
        db.query(HardRuleCheck)
        .filter(HardRuleCheck.run_id == run_id)
        .all()
    )
    policy_checks = (
        db.query(PolicyCheck)
        .filter(PolicyCheck.run_id == run_id)
        .all()
    )
    supplier_evals = (
        db.query(SupplierEvaluation)
        .filter(SupplierEvaluation.run_id == run_id)
        .all()
    )

    # Group by supplier
    supplier_ids: set[str | None] = set()
    for h in hard_checks:
        supplier_ids.add(h.supplier_id)
    for p in policy_checks:
        supplier_ids.add(p.supplier_id)
    for s in supplier_evals:
        supplier_ids.add(s.supplier_id)
    supplier_ids.discard(None)

    supplier_breakdowns: list[SupplierRuleBreakdownOut] = []
    for sid in sorted(supplier_ids):
        se = next((s for s in supplier_evals if s.supplier_id == sid), None)
        hc_list = [
            RuleCheckOut(
                check_id=h.check_id,
                rule_id=h.rule_id,
                version_id=h.version_id,
                supplier_id=h.supplier_id,
                result=h.result or "skipped",
                evidence=None,
                skipped=h.skipped,
                skip_reason=h.skip_reason,
                checked_at=h.checked_at,
            )
            for h in hard_checks
            if h.supplier_id == sid
        ]
        pc_list = [
            RuleCheckOut(
                check_id=p.check_id,
                rule_id=p.rule_id,
                version_id=p.version_id,
                supplier_id=p.supplier_id,
                result=p.result,
                evidence=p.evidence if isinstance(p.evidence, dict) else {},
                skipped=False,
                skip_reason=None,
                checked_at=p.checked_at,
            )
            for p in policy_checks
            if p.supplier_id == sid
        ]
        supplier_breakdowns.append(
            SupplierRuleBreakdownOut(
                supplier_id=sid,
                supplier_name=None,
                hard_rule_checks=hc_list,
                policy_checks=pc_list,
                excluded=se.excluded if se else False,
                exclusion_rule_id=se.exclusion_rule_id if se else None,
                exclusion_reason=se.exclusion_reason if se else None,
            )
        )

    # Add supplier names from supplier table
    from app.models.reference import Supplier
    for i, sb in enumerate(supplier_breakdowns):
        sup = db.query(Supplier).filter(Supplier.supplier_id == sb.supplier_id).first()
        if sup:
            supplier_breakdowns[i] = SupplierRuleBreakdownOut(
                **sb.model_dump(),
                supplier_name=sup.supplier_name,
            )

    return EvaluationDetailOut(
        run_id=run.run_id,
        request_id=run.request_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        supplier_breakdowns=supplier_breakdowns,
    )


@router.post("/evaluations", response_model=dict)
def create_evaluation_run(
    body: EvaluationRunCreate,
    db: Session = Depends(get_db),
):
    """
    Create an evaluation run with hard_rule_checks, policy_checks, supplier_evaluations.
    Each check must include rule_id and version_id for traceability.
    Called by logical layer after processing a request.
    """
    from app.models.requests import Request

    req = db.query(Request).filter(Request.request_id == body.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    now = datetime.utcnow()
    run = EvaluationRun(
        run_id=body.run_id,
        request_id=body.request_id,
        triggered_by=body.triggered_by,
        agent_version=body.agent_version,
        started_at=now,
        finished_at=now,
        status=body.status,
        final_outcome=body.final_outcome,
        output_snapshot=body.output_snapshot,
        parent_run_id=body.parent_run_id,
        trigger_reason=body.trigger_reason,
    )
    db.add(run)

    for h in body.hard_rule_checks:
        hc = HardRuleCheck(
            check_id=str(uuid.uuid4()),
            run_id=body.run_id,
            rule_id=h.rule_id,
            version_id=h.version_id,
            supplier_id=h.supplier_id,
            skipped=h.skipped,
            skip_reason=h.skip_reason,
            result=h.result,
            actual_value=h.actual_value,
            threshold=h.threshold,
            checked_at=now,
        )
        db.add(hc)

    for p in body.policy_checks:
        pc = PolicyCheck(
            check_id=str(uuid.uuid4()),
            run_id=body.run_id,
            rule_id=p.rule_id,
            version_id=p.version_id,
            supplier_id=p.supplier_id,
            result=p.result,
            evidence=p.evidence,
            checked_at=now,
        )
        db.add(pc)

    for s in body.supplier_evaluations:
        se = SupplierEvaluation(
            eval_id=str(uuid.uuid4()),
            run_id=body.run_id,
            supplier_id=s.supplier_id,
            rank=s.rank,
            total_score=s.total_score,
            price_score=s.price_score,
            quality_score=s.quality_score,
            esg_score=s.esg_score,
            risk_score=s.risk_score,
            hard_checks_total=s.hard_checks_total,
            hard_checks_passed=s.hard_checks_passed,
            hard_checks_skipped=s.hard_checks_skipped,
            hard_checks_failed=s.hard_checks_failed,
            policy_checks_total=s.policy_checks_total,
            policy_checks_passed=s.policy_checks_passed,
            policy_checks_warned=s.policy_checks_warned,
            policy_checks_failed=s.policy_checks_failed,
            excluded=s.excluded,
            exclusion_rule_id=s.exclusion_rule_id,
            exclusion_reason=s.exclusion_reason,
            pricing_snapshot=s.pricing_snapshot,
            evaluated_at=now,
        )
        db.add(se)

    db.commit()
    return {"run_id": body.run_id, "status": "created"}


@router.get("/evaluations/by-request/{request_id}", response_model=list[EvaluationDetailOut])
def list_evaluations_by_request(
    request_id: str,
    db: Session = Depends(get_db),
):
    """List all evaluation runs for a request."""
    runs = (
        db.query(EvaluationRun)
        .filter(EvaluationRun.request_id == request_id)
        .order_by(EvaluationRun.started_at.desc())
        .all()
    )
    result = []
    for run in runs:
        detail = get_evaluation_detail(run.run_id, db)
        result.append(detail)
    return result
