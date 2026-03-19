"""Rule versioning and evaluation traceability endpoints."""

import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.requests import Request
from app.models.evaluations import (
    EscalationLog,
    EvaluationRun,
    EvaluationRunLog,
    HardRuleCheck,
    PolicyChangeLog,
    PolicyCheck,
    PolicyCheckLog,
    RuleChangeLog,
    RuleDefinition,
    RuleVersion,
    SupplierEvaluation,
)
from app.services.dynamic_rule_versions import (
    get_dynamic_snapshot_and_version,
    get_dynamic_snapshot_by_version,
)
from app.schemas.rule_versions import (
    DynamicRuleVersionActiveOut,
    DynamicRuleVersionPinnedOut,
    EscalationLogOut,
    EvaluationDetailOut,
    EvaluationRunCreate,
    EvaluationRunLogOut,
    FullEvaluationTriggerCreate,
    HardRuleCheckCreate,
    PipelineEvaluationInput,
    PolicyCheckCreate,
    PolicyCheckLogOut,
    PolicyCheckOut,
    PolicyCheckOverrideBody,
    PolicyChangeLogOut,
    RuleChangeLogOut,
    RuleCheckOut,
    RuleDefinitionCreate,
    RuleDefinitionOut,
    RuleDefinitionUpdate,
    RuleVersionCreate,
    RuleVersionOut,
    RuleVersionUpdate,
    RuleVersionWithDefinitionOut,
    SupplierRuleBreakdownOut,
)

router = APIRouter(prefix="/api/rule-versions", tags=["Rule Versions"])


def _rule_definition_name(db: Session, rule_id: str) -> str | None:
    rd = db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first()
    return rd.rule_name if rd else None


def _version_config_snapshot(db: Session, version_id: str) -> dict[str, Any] | None:
    rv = db.query(RuleVersion).filter(RuleVersion.version_id == version_id).first()
    if not rv:
        return None
    return rv.rule_config


def _hard_rule_check_out(db: Session, h: HardRuleCheck) -> RuleCheckOut:
    dyn_snap, dyn_ver = get_dynamic_snapshot_and_version(db, h.rule_id)
    return RuleCheckOut(
        check_id=h.check_id,
        rule_id=h.rule_id,
        version_id=h.version_id,
        supplier_id=h.supplier_id,
        result=h.result or "skipped",
        evidence=None,
        skipped=h.skipped,
        skip_reason=h.skip_reason,
        checked_at=h.checked_at,
        rule_name=_rule_definition_name(db, h.rule_id),
        version_snapshot=_version_config_snapshot(db, h.version_id),
        dynamic_snapshot=dyn_snap,
        dynamic_rule_version=dyn_ver,
    )


def _policy_rule_check_out(db: Session, p: PolicyCheck) -> PolicyCheckOut:
    dyn_snap, dyn_ver = get_dynamic_snapshot_and_version(db, p.rule_id)
    return PolicyCheckOut(
        check_id=p.check_id,
        rule_id=p.rule_id,
        version_id=p.version_id,
        supplier_id=p.supplier_id,
        result=p.result,
        evidence=p.evidence if isinstance(p.evidence, dict) else {},
        skipped=False,
        skip_reason=None,
        checked_at=p.checked_at,
        rule_name=_rule_definition_name(db, p.rule_id),
        version_snapshot=_version_config_snapshot(db, p.version_id),
        dynamic_snapshot=dyn_snap,
        dynamic_rule_version=dyn_ver,
        run_id=p.run_id,
        override_by=p.override_by,
        override_at=p.override_at,
        override_reason=p.override_reason,
    )


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


def _rule_exists(db: Session, rule_id: str) -> bool:
    """Check if rule definition exists (avoids FK violation when migrate_rules not run)."""
    return db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first() is not None


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


@router.post("/definitions", response_model=RuleDefinitionOut, status_code=201)
def create_rule_definition(body: RuleDefinitionCreate, db: Session = Depends(get_db)):
    """Create a new rule definition."""
    existing = db.query(RuleDefinition).filter(RuleDefinition.rule_id == body.rule_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Rule definition {body.rule_id} already exists")
    rule = RuleDefinition(
        rule_id=body.rule_id,
        rule_type=body.rule_type,
        rule_name=body.rule_name,
        is_skippable=body.is_skippable,
        source=body.source,
        active=True,
        created_at=datetime.utcnow(),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/definitions/{rule_id}", response_model=RuleDefinitionOut)
def update_rule_definition(
    rule_id: str,
    body: RuleDefinitionUpdate,
    db: Session = Depends(get_db),
):
    """Update mutable fields on a rule definition (rule_name, is_skippable, active)."""
    rule = db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule definition not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/definitions/{rule_id}", status_code=204)
def delete_rule_definition(rule_id: str, db: Session = Depends(get_db)):
    """Soft-delete a rule definition by setting active=False."""
    rule = db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule definition not found")
    rule.active = False
    db.commit()


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
    Returns the new version. Uses ACID transaction workflow:
    1. INSERT new rule_version, 2. UPDATE previous valid_to, 3. INSERT rule_change_logs.
    """
    from app.services.transaction_workflows import apply_rule_update

    rule = db.query(RuleDefinition).filter(RuleDefinition.rule_id == body.rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule definition not found")

    try:
        new_version = apply_rule_update(
            db=db,
            rule_id=body.rule_id,
            rule_config=body.rule_config,
            changed_by=body.changed_by or "system",
            change_reason=body.change_reason,
        )
        return new_version
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


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


@router.get(
    "/dynamic-rule-versions/active/{rule_id}",
    response_model=DynamicRuleVersionActiveOut,
)
def get_active_dynamic_rule_version(rule_id: str, db: Session = Depends(get_db)):
    """
    Latest snapshot from `dynamic_rule_versions` (active row, else highest version),
    else live row from `dynamic_rules`. Used by clients when embedded check payloads
    omit `dynamic_snapshot` / `dynamic_rule_version`.
    """
    snap, ver = get_dynamic_snapshot_and_version(db, rule_id)
    if snap is None or ver is None:
        raise HTTPException(
            status_code=404,
            detail=f"No dynamic rule snapshot found for rule_id={rule_id}",
        )
    return DynamicRuleVersionActiveOut(rule_id=rule_id, version=ver, snapshot=snap)


@router.get(
    "/dynamic-rule-versions/{rule_id}/at-version/{version_num}",
    response_model=DynamicRuleVersionPinnedOut,
)
def get_dynamic_rule_version_at(
    rule_id: str,
    version_num: int,
    db: Session = Depends(get_db),
):
    """Exact row from `dynamic_rule_versions` by (rule_id, integer version)."""
    snap, row = get_dynamic_snapshot_by_version(db, rule_id, version_num)
    if row is None or snap is None:
        raise HTTPException(
            status_code=404,
            detail=f"No dynamic_rule_versions row for {rule_id} version {version_num}",
        )
    return DynamicRuleVersionPinnedOut(
        rule_id=rule_id,
        version=row.version,
        snapshot=snap,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
    )


@router.get("/versions/{version_id}", response_model=RuleVersionWithDefinitionOut)
def get_rule_version(version_id: str, db: Session = Depends(get_db)):
    """Get a single rule version by its UUID, including parent definition metadata."""
    row = (
        db.query(RuleVersion)
        .join(RuleDefinition, RuleVersion.rule_id == RuleDefinition.rule_id)
        .add_columns(RuleDefinition.rule_name, RuleDefinition.rule_type)
        .filter(RuleVersion.version_id == version_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Rule version not found")
    v, rule_name, rule_type = row
    return RuleVersionWithDefinitionOut(
        version_id=v.version_id,
        rule_id=v.rule_id,
        version_num=v.version_num,
        rule_config=v.rule_config,
        valid_from=v.valid_from,
        valid_to=v.valid_to,
        changed_by=v.changed_by,
        change_reason=v.change_reason,
        rule_name=rule_name,
        rule_type=rule_type,
    )


@router.patch("/versions/{version_id}", response_model=RuleVersionOut)
def update_rule_version_metadata(
    version_id: str,
    body: RuleVersionUpdate,
    db: Session = Depends(get_db),
):
    """Update metadata on a rule version (changed_by, change_reason). Config is immutable."""
    v = db.query(RuleVersion).filter(RuleVersion.version_id == version_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Rule version not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(v, field, value)
    db.commit()
    db.refresh(v)
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
            _hard_rule_check_out(db, h)
            for h in hard_checks
            if h.supplier_id == sid
        ]
        pc_list = [
            _policy_rule_check_out(db, p)
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
            d = sb.model_dump()
            d["supplier_name"] = sup.supplier_name
            supplier_breakdowns[i] = SupplierRuleBreakdownOut(**d)

    snapshot = run.output_snapshot or {}
    supplier_shortlist = snapshot.get("supplier_shortlist", [])
    suppliers_excluded = [
        e if isinstance(e, dict) else {"supplier_id": "", "supplier_name": "", "reason": ""}
        for e in snapshot.get("suppliers_excluded", [])
    ]

    return EvaluationDetailOut(
        run_id=run.run_id,
        request_id=run.request_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        supplier_breakdowns=supplier_breakdowns,
        supplier_shortlist=supplier_shortlist,
        suppliers_excluded=suppliers_excluded,
    )


@router.post("/evaluations/reeval/{request_id}", response_model=dict)
def trigger_reeval(
    request_id: str,
    db: Session = Depends(get_db),
):
    """
    Trigger full re-evaluation of a request. Calls the logical layer pipeline,
    which revalidates all suppliers and persists hard_rule_checks, policy_checks,
    supplier_evaluations, and escalations to the backend.
    Requires LOGICAL_LAYER_URL to be configured.
    """
    from app.config import settings

    if not settings.LOGICAL_LAYER_URL:
        raise HTTPException(
            status_code=503,
            detail="Re-evaluation requires LOGICAL_LAYER_URL to be configured",
        )
    req = db.query(Request).filter(Request.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    import httpx

    url = f"{settings.LOGICAL_LAYER_URL.rstrip('/')}/api/pipeline/process"
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json={"request_id": request_id})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Logical layer unreachable or error: {str(e)[:200]}",
        )


@router.post("/evaluations/from-pipeline", response_model=dict)
def create_evaluation_from_pipeline(
    body: PipelineEvaluationInput,
    db: Session = Depends(get_db),
):
    """
    Persist evaluation from pipeline output. Maps output_snapshot to hard_rule_checks,
    policy_checks, supplier_evaluations, escalations. Revalidates all suppliers.
    Uses ACID evaluation trigger workflow.
    """
    from app.services.transaction_workflows import run_evaluation_trigger

    req = db.query(Request).filter(Request.request_id == body.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    snapshot = body.output_snapshot or {}
    supplier_shortlist = snapshot.get("supplier_shortlist", [])
    suppliers_excluded = snapshot.get("suppliers_excluded", [])
    escalations_data = snapshot.get("escalations", [])
    policy_eval = snapshot.get("policy_evaluation", {})
    approval = policy_eval.get("approval_threshold", {}) or {}
    preferred = policy_eval.get("preferred_supplier", {}) or {}
    restricted = policy_eval.get("restricted_suppliers", {}) or {}

    # Build active version cache
    def _version(rule_id: str) -> str | None:
        v = _get_active_version(db, rule_id)
        return v.version_id if v else None

    pc001 = _version("PC-001")
    pc003 = _version("PC-003")
    pc004 = _version("PC-004")
    pc008 = _version("PC-008")
    hr001 = _version("HR-001")
    hr002 = _version("HR-002")
    hr003 = _version("HR-003")

    interp = snapshot.get("request_interpretation", {}) or {}
    budget = interp.get("budget_amount")
    days_required = interp.get("days_until_required")

    hard_rule_checks: list[dict] = []
    policy_checks: list[dict] = []
    supplier_evaluations: list[dict] = []
    escalations: list[dict] = []

    # Policy checks: PC-001 (approval tier) - request-level
    if pc001:
        policy_checks.append({
            "rule_id": "PC-001",
            "version_id": pc001,
            "supplier_id": None,
            "result": "passed",
            "evidence": {"tier": approval.get("rule_applied"), "quotes": approval.get("quotes_required")},
        })

    # Hard rule checks from excluded suppliers (HR-003 capacity, PC-004 restricted, PC-008 data residency)
    for e in suppliers_excluded:
        sid = e.get("supplier_id", "")
        reason = (e.get("reason", "") or "").lower()
        if "capacity" in reason or "exceeds monthly" in reason:
            if hr003:
                hard_rule_checks.append({
                    "rule_id": "HR-003",
                    "version_id": hr003,
                    "supplier_id": sid,
                    "skipped": False,
                    "result": "failed",
                    "actual_value": {"reason": reason},
                    "threshold": None,
                })
        if "restricted" in reason or "policy restriction" in reason:
            if pc004:
                policy_checks.append({
                    "rule_id": "PC-004",
                    "version_id": pc004,
                    "supplier_id": sid,
                    "result": "failed",
                    "evidence": {"restricted": True, "reason": reason},
                })
        if "data residency" in reason or "residency" in reason:
            if pc008:
                policy_checks.append({
                    "rule_id": "PC-008",
                    "version_id": pc008,
                    "supplier_id": sid,
                    "result": "failed",
                    "evidence": {"data_residency": False, "reason": reason},
                })
    # Per-supplier: shortlist — HR-001 (budget), HR-002 (delivery)
    for i, s in enumerate(supplier_shortlist):
        sid = s.get("supplier_id")
        sname = s.get("supplier_name", "")
        pref = s.get("preferred", False)
        policy_ok = s.get("policy_compliant", True)
        rank = i + 1
        currency_key = (interp.get("currency") or "EUR").lower()
        total_price = (
            s.get(f"total_price_{currency_key}") or s.get("total_price_eur") or s.get("total_price")
        )
        std_lead = s.get("standard_lead_time_days")
        exp_lead = s.get("expedited_lead_time_days")

        # HR-001: Budget ceiling — failed if total > budget
        if hr001 and sid and budget is not None and total_price is not None:
            over_budget = float(total_price) > float(budget)
            hard_rule_checks.append({
                "rule_id": "HR-001",
                "version_id": hr001,
                "supplier_id": sid,
                "skipped": False,
                "result": "failed" if over_budget else "passed",
                "actual_value": {"total_price": total_price, "currency": interp.get("currency", "EUR")},
                "threshold": {"budget_amount": budget},
            })
        # HR-002: Delivery deadline — failed if lead time > days_until_required
        if hr002 and sid and days_required is not None:
            min_lead = None
            if std_lead is not None:
                min_lead = int(std_lead)
            if exp_lead is not None:
                m = int(exp_lead)
                min_lead = m if min_lead is None else min(min_lead, m)
            if min_lead is not None:
                infeasible = min_lead > int(days_required)
                hard_rule_checks.append({
                    "rule_id": "HR-002",
                    "version_id": hr002,
                    "supplier_id": sid,
                    "skipped": False,
                    "result": "failed" if infeasible else "passed",
                    "actual_value": {"standard_lead_days": std_lead, "expedited_lead_days": exp_lead},
                    "threshold": {"days_until_required": days_required},
                })

        # PC-003 preferred
        if pc003:
            res = "passed" if pref else ("warned" if preferred.get("policy_note") else "passed")
            policy_checks.append({
                "rule_id": "PC-003",
                "version_id": pc003,
                "supplier_id": sid,
                "result": res,
                "evidence": {"preferred": pref, "supplier": sname},
            })

        # Restricted check
        if pc004 and sid:
            restr = restricted.get(sid, {})
            is_r = restr.get("restricted", False) if isinstance(restr, dict) else False
            policy_checks.append({
                "rule_id": "PC-004",
                "version_id": pc004,
                "supplier_id": sid,
                "result": "failed" if is_r else "passed",
                "evidence": {"restricted": is_r},
            })

        # Supplier evaluation (counts updated below from hard_rule_checks/policy_checks)
        supplier_evaluations.append({
            "supplier_id": sid,
            "rank": rank,
            "total_score": s.get("quality_score"),
            "quality_score": s.get("quality_score"),
            "risk_score": s.get("risk_score"),
            "esg_score": s.get("esg_score"),
            "hard_checks_total": 0,
            "hard_checks_passed": 0,
            "hard_checks_skipped": 0,
            "hard_checks_failed": 0,
            "policy_checks_total": 2,
            "policy_checks_passed": 2 if policy_ok else 1,
            "policy_checks_warned": 0,
            "policy_checks_failed": 0 if policy_ok else 1,
            "excluded": False,
        })

    # Aggregate hard_rule_checks and policy_checks counts per supplier and update supplier_evaluations
    def _hr_counts(supplier_id: str | None) -> tuple[int, int, int, int]:
        total = passed = skipped = failed = 0
        for h in hard_rule_checks:
            if h.get("supplier_id") != supplier_id:
                continue
            total += 1
            if h.get("skipped"):
                skipped += 1
            elif h.get("result") == "passed":
                passed += 1
            else:
                failed += 1
        return total, passed, skipped, failed

    def _pc_counts(supplier_id: str | None) -> tuple[int, int, int, int]:
        total = passed = warned = failed = 0
        for p in policy_checks:
            if p.get("supplier_id") != supplier_id:
                continue
            total += 1
            r = p.get("result", "passed")
            if r == "passed":
                passed += 1
            elif r == "warned":
                warned += 1
            else:
                failed += 1
        return total, passed, warned, failed

    for se in supplier_evaluations:
        sid = se.get("supplier_id")
        hr_t, hr_p, hr_s, hr_f = _hr_counts(sid)
        pc_t, pc_p, pc_w, pc_f = _pc_counts(sid)
        se["hard_checks_total"] = hr_t
        se["hard_checks_passed"] = hr_p
        se["hard_checks_skipped"] = hr_s
        se["hard_checks_failed"] = hr_f
        se["policy_checks_total"] = pc_t
        se["policy_checks_passed"] = pc_p
        se["policy_checks_warned"] = pc_w
        se["policy_checks_failed"] = pc_f

    # Excluded suppliers (before aggregation so they get counts from hard_rule_checks/policy_checks)
    for e in suppliers_excluded:
        sid = e.get("supplier_id", "")
        reason = (e.get("reason", "") or "").lower()
        excl_rule = "PC-004" if "restricted" in reason else "HR-003"
        exclusion_rule_id = excl_rule if _rule_exists(db, excl_rule) else None
        supplier_evaluations.append({
            "supplier_id": sid,
            "excluded": True,
            "exclusion_rule_id": exclusion_rule_id,
            "exclusion_reason": e.get("reason", ""),
            "hard_checks_total": 0,
            "hard_checks_passed": 0,
            "hard_checks_skipped": 0,
            "hard_checks_failed": 0,
            "policy_checks_total": 0,
            "policy_checks_passed": 0,
            "policy_checks_warned": 0,
            "policy_checks_failed": 0,
        })

    # Escalations (pipeline uses escalate_to, backend expects escalation_target)
    for j, esc in enumerate(escalations_data):
        rule = esc.get("rule", "ER-001")
        v = _get_active_version(db, rule)
        version_id = v.version_id if v else None
        if not version_id:
            logger.warning(
                "No active rule_version for %s — skipping escalation persistence", rule,
            )
            continue
        escalations.append({
            "escalation_id": esc.get("escalation_id", f"ESC-{j+1:03d}"),
            "rule_id": rule,
            "version_id": version_id,
            "escalation_target": esc.get("escalate_to", "Procurement Manager"),
            "escalation_reason": esc.get("trigger", ""),
            "trigger_table": "policy_checks",
            "trigger_check_id": "",
            "status": "open",
        })

    try:
        run_evaluation_trigger(
            db=db,
            run_id=body.run_id,
            request_id=body.request_id,
            triggered_by=body.triggered_by,
            agent_version=body.agent_version,
            hard_rule_checks=hard_rule_checks,
            policy_checks=policy_checks,
            supplier_evaluations=supplier_evaluations,
            escalations=escalations,
            output_snapshot=body.output_snapshot,
            trigger_reason=body.trigger_reason,
        )
        return {"run_id": body.run_id, "status": "created"}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/evaluations/full", response_model=dict)
def create_full_evaluation_trigger(
    body: FullEvaluationTriggerCreate,
    db: Session = Depends(get_db),
):
    """
    Full evaluation trigger with ACID workflow:
    1. INSERT evaluation_runs, 2. INSERT hard_rule_checks + policy_checks,
    3. INSERT escalations + supplier_evaluations, 4. INSERT escalation_logs + evaluation_run_logs,
    5. UPDATE evaluation_runs status.
    """
    from app.services.transaction_workflows import run_evaluation_trigger

    req = db.query(Request).filter(Request.request_id == body.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    try:
        run_evaluation_trigger(
            db=db,
            run_id=body.run_id,
            request_id=body.request_id,
            triggered_by=body.triggered_by,
            agent_version=body.agent_version,
            hard_rule_checks=[h.model_dump() for h in body.hard_rule_checks],
            policy_checks=[p.model_dump() for p in body.policy_checks],
            supplier_evaluations=[s.model_dump() for s in body.supplier_evaluations],
            escalations=[e.model_dump() for e in body.escalations],
            output_snapshot=body.output_snapshot,
            parent_run_id=body.parent_run_id,
            trigger_reason=body.trigger_reason,
        )
        return {"run_id": body.run_id, "status": "created"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


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


# ── Hard rule checks ───────────────────────────────────────────────────────


@router.get("/hard-rule-checks", response_model=list[RuleCheckOut])
def list_hard_rule_checks(
    run_id: str | None = None,
    request_id: str | None = None,
    supplier_id: str | None = None,
    db: Session = Depends(get_db),
):
    """List hard rule checks. Filter by run_id, request_id (via run), or supplier_id."""
    q = db.query(HardRuleCheck)
    if run_id:
        q = q.filter(HardRuleCheck.run_id == run_id)
    if request_id:
        q = q.join(EvaluationRun).filter(EvaluationRun.request_id == request_id)
    if supplier_id:
        q = q.filter(HardRuleCheck.supplier_id == supplier_id)
    rows = q.order_by(HardRuleCheck.checked_at.desc()).all()
    return [_hard_rule_check_out(db, h) for h in rows]


@router.get("/hard-rule-checks/{check_id}", response_model=RuleCheckOut)
def get_hard_rule_check(check_id: str, db: Session = Depends(get_db)):
    """Get a single hard rule check."""
    h = db.query(HardRuleCheck).filter(HardRuleCheck.check_id == check_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Hard rule check not found")
    return _hard_rule_check_out(db, h)


@router.post("/evaluations/{run_id}/hard-rule-checks", response_model=list[RuleCheckOut])
def add_hard_rule_checks(
    run_id: str,
    body: list[HardRuleCheckCreate],
    db: Session = Depends(get_db),
):
    """Append hard rule checks to an existing evaluation run."""
    run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    now = datetime.utcnow()
    created: list[HardRuleCheck] = []
    for h in body:
        hc = HardRuleCheck(
            check_id=str(uuid.uuid4()),
            run_id=run_id,
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
        created.append(hc)
    db.commit()
    return [_hard_rule_check_out(db, h) for h in created]


# ── Policy checks ───────────────────────────────────────────────────────────


@router.get("/policy-checks", response_model=list[PolicyCheckOut])
def list_policy_checks(
    run_id: str | None = None,
    request_id: str | None = None,
    supplier_id: str | None = None,
    db: Session = Depends(get_db),
):
    """List policy checks. Filter by run_id, request_id (via run), or supplier_id."""
    q = db.query(PolicyCheck)
    if run_id:
        q = q.filter(PolicyCheck.run_id == run_id)
    if request_id:
        q = q.join(EvaluationRun).filter(EvaluationRun.request_id == request_id)
    if supplier_id:
        q = q.filter(PolicyCheck.supplier_id == supplier_id)
    rows = q.order_by(PolicyCheck.checked_at.desc()).all()
    return [_policy_rule_check_out(db, p) for p in rows]


@router.get("/policy-checks/{check_id}", response_model=PolicyCheckOut)
def get_policy_check(check_id: str, db: Session = Depends(get_db)):
    """Get a single policy check."""
    p = db.query(PolicyCheck).filter(PolicyCheck.check_id == check_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Policy check not found")
    return _policy_rule_check_out(db, p)


@router.post("/evaluations/{run_id}/policy-checks", response_model=list[PolicyCheckOut])
def add_policy_checks(
    run_id: str,
    body: list[PolicyCheckCreate],
    db: Session = Depends(get_db),
):
    """Append policy checks to an existing evaluation run."""
    run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    now = datetime.utcnow()
    created: list[PolicyCheck] = []
    for p in body:
        pc = PolicyCheck(
            check_id=str(uuid.uuid4()),
            run_id=run_id,
            rule_id=p.rule_id,
            version_id=p.version_id,
            supplier_id=p.supplier_id,
            result=p.result,
            evidence=p.evidence,
            checked_at=now,
        )
        db.add(pc)
        created.append(pc)
    db.commit()
    return [_policy_rule_check_out(db, c) for c in created]


@router.patch("/policy-checks/{check_id}", response_model=PolicyCheckOut)
def override_policy_check(
    check_id: str,
    body: PolicyCheckOverrideBody,
    db: Session = Depends(get_db),
):
    """
    Override a policy check result. ACID workflow:
    1. INSERT policy_check_logs, 2. UPDATE policy_checks.
    """
    from app.services.transaction_workflows import apply_policy_check_override

    try:
        updated = apply_policy_check_override(
            db=db,
            check_id=check_id,
            changed_by=body.changed_by,
            new_result=body.new_result,
            override_reason=body.override_reason,
            new_evidence=body.new_evidence,
        )
        return _policy_rule_check_out(db, updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── Log endpoints (read-only) ───────────────────────────────────────────────


@router.get("/logs/evaluation-run/{run_id}", response_model=list[EvaluationRunLogOut])
def list_evaluation_run_logs(run_id: str, db: Session = Depends(get_db)):
    """List evaluation run logs for a run."""
    rows = (
        db.query(EvaluationRunLog)
        .filter(EvaluationRunLog.run_id == run_id)
        .order_by(EvaluationRunLog.changed_at.desc())
        .all()
    )
    return [EvaluationRunLogOut.model_validate(r) for r in rows]


@router.get("/logs/escalation/{escalation_id}", response_model=list[EscalationLogOut])
def list_escalation_logs(escalation_id: str, db: Session = Depends(get_db)):
    """List escalation logs for an escalation."""
    rows = (
        db.query(EscalationLog)
        .filter(EscalationLog.escalation_id == escalation_id)
        .order_by(EscalationLog.changed_at.desc())
        .all()
    )
    return [EscalationLogOut.model_validate(r) for r in rows]


@router.get("/logs/policy-change/{escalation_id}", response_model=list[PolicyChangeLogOut])
def list_policy_change_logs(escalation_id: str, db: Session = Depends(get_db)):
    """List policy change logs for an escalation."""
    rows = (
        db.query(PolicyChangeLog)
        .filter(PolicyChangeLog.escalation_id == escalation_id)
        .order_by(PolicyChangeLog.changed_at.desc())
        .all()
    )
    return [PolicyChangeLogOut.model_validate(r) for r in rows]


@router.get("/logs/policy-check", response_model=list[PolicyCheckLogOut])
def list_policy_check_logs(
    check_id: str | None = None,
    run_id: str | None = None,
    db: Session = Depends(get_db),
):
    """List policy check logs. Filter by check_id or run_id."""
    q = db.query(PolicyCheckLog)
    if check_id:
        q = q.filter(PolicyCheckLog.check_id == check_id)
    if run_id:
        q = q.filter(PolicyCheckLog.run_id == run_id)
    rows = q.order_by(PolicyCheckLog.changed_at.desc()).all()
    return [PolicyCheckLogOut.model_validate(r) for r in rows]


@router.get("/logs/rule-change", response_model=list[RuleChangeLogOut])
def list_rule_change_logs(
    rule_id: str | None = None,
    db: Session = Depends(get_db),
):
    """List rule change logs. Filter by rule_id."""
    q = db.query(RuleChangeLog)
    if rule_id:
        q = q.filter(RuleChangeLog.rule_id == rule_id)
    rows = q.order_by(RuleChangeLog.changed_at.desc()).all()
    return [RuleChangeLogOut.model_validate(r) for r in rows]


@router.get("/logs/rule-change/{log_id}", response_model=RuleChangeLogOut)
def get_rule_change_log(log_id: str, db: Session = Depends(get_db)):
    """Get a single rule change log entry by UUID."""
    row = db.query(RuleChangeLog).filter(RuleChangeLog.log_id == log_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Rule change log not found")
    return RuleChangeLogOut.model_validate(row)
