"""
ACID-compliant database transaction workflows for audit-ready procurement.

All workflows use SQLAlchemy sessions with explicit transaction boundaries.
MySQL InnoDB provides ACID guarantees; we wrap each workflow in a single
transaction (commit on success, rollback on failure).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session


def _json_safe(val: Any) -> Any:
    """Convert value for JSON column storage."""
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _json_safe(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_json_safe(v) for v in val]
    return val

from app.models.evaluations import (
    Escalation,
    EscalationLog,
    EvaluationRun,
    EvaluationRunLog,
    HardRuleCheck,
    PolicyChangeLog,
    PolicyCheck,
    RuleChangeLog,
    RuleVersion,
    SupplierEvaluation,
)


# ---------------------------------------------------------------------------
# 1. Escalation Change Workflow
# ---------------------------------------------------------------------------
# When a user changes an escalation:
#   1. INSERT policy_change_logs
#   2. INSERT escalation_logs
#   3. UPDATE escalations
# ---------------------------------------------------------------------------


def apply_escalation_change(
    db: Session,
    escalation_id: str,
    changed_by: str,
    updates: dict[str, Any],
    policy_rule_id: str | None = None,
    change_reason: str | None = None,
) -> Escalation:
    """
    Apply a user-initiated escalation change with full audit trail.
    Wrapped in ACID transaction.
    """
    escalation = db.query(Escalation).filter(Escalation.escalation_id == escalation_id).first()
    if not escalation:
        raise ValueError(f"Escalation {escalation_id} not found")

    now = datetime.utcnow()

    # Step 1: INSERT policy_change_logs
    old_vals = {
        k: _json_safe(getattr(escalation, k))
        for k in updates
        if hasattr(escalation, k)
    }
    policy_log = PolicyChangeLog(
        log_id=str(uuid.uuid4()),
        escalation_id=escalation_id,
        changed_at=now,
        changed_by=changed_by,
        change_type="escalation_change",
        policy_rule_id=policy_rule_id,
        old_value=old_vals,
        new_value=_json_safe(updates),
        note=change_reason,
    )
    db.add(policy_log)

    # Step 2: INSERT escalation_logs (audit trail for escalation changes)
    for field, new_val in updates.items():
        if hasattr(escalation, field):
            old_val = getattr(escalation, field)
            if old_val != new_val:
                esc_log = EscalationLog(
                    log_id=str(uuid.uuid4()),
                    escalation_id=escalation_id,
                    changed_at=now,
                    changed_by=changed_by,
                    change_type="field_update",
                    field_changed=field,
                    old_value=_json_safe(old_val) if old_val is not None and not callable(old_val) else None,
                    new_value=_json_safe(new_val) if new_val is not None and not callable(new_val) else new_val,
                    note=change_reason,
                )
                db.add(esc_log)

    # Step 3: UPDATE escalations
    for field, value in updates.items():
        if hasattr(escalation, field):
            setattr(escalation, field, value)

    db.commit()
    db.refresh(escalation)
    return escalation


# ---------------------------------------------------------------------------
# 2. Evaluation Trigger Workflow
# ---------------------------------------------------------------------------
# On evaluation trigger:
#   1. INSERT evaluation_runs (status=started)
#   2. INSERT hard_rule_checks, policy_checks (linked to run)
#   3. INSERT escalations, supplier_evaluations (from check results)
#   4. INSERT escalation_logs, evaluation_run_logs
#   5. UPDATE evaluation_runs (status=completed)
# ---------------------------------------------------------------------------


def run_evaluation_trigger(
    db: Session,
    run_id: str,
    request_id: str,
    triggered_by: str,
    agent_version: str,
    hard_rule_checks: list[dict[str, Any]],
    policy_checks: list[dict[str, Any]],
    supplier_evaluations: list[dict[str, Any]],
    escalations: list[dict[str, Any]],
    output_snapshot: dict[str, Any] | None = None,
    parent_run_id: str | None = None,
    trigger_reason: str | None = None,
) -> EvaluationRun:
    """
    Execute full evaluation trigger with audit trail.
    Wrapped in ACID transaction.
    """
    now = datetime.utcnow()

    # Step 1: INSERT evaluation_runs (status=started)
    run = EvaluationRun(
        run_id=run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        agent_version=agent_version,
        started_at=now,
        finished_at=None,
        status="started",
        final_outcome=None,
        output_snapshot=output_snapshot,
        parent_run_id=parent_run_id,
        trigger_reason=trigger_reason,
    )
    db.add(run)
    db.flush()

    # Step 2: INSERT hard_rule_checks, policy_checks
    for h in hard_rule_checks:
        hc = HardRuleCheck(
            check_id=h.get("check_id") or str(uuid.uuid4()),
            run_id=run_id,
            rule_id=h["rule_id"],
            version_id=h["version_id"],
            supplier_id=h.get("supplier_id"),
            skipped=h.get("skipped", False),
            skip_reason=h.get("skip_reason"),
            result=h.get("result"),
            actual_value=h.get("actual_value"),
            threshold=h.get("threshold"),
            checked_at=now,
        )
        db.add(hc)

    for p in policy_checks:
        pc = PolicyCheck(
            check_id=p.get("check_id") or str(uuid.uuid4()),
            run_id=run_id,
            rule_id=p["rule_id"],
            version_id=p["version_id"],
            supplier_id=p.get("supplier_id"),
            result=p["result"],
            evidence=p.get("evidence", {}),
            checked_at=now,
        )
        db.add(pc)

    db.flush()

    # Step 3: INSERT escalations, supplier_evaluations
    created_escalation_ids: list[str] = []
    for e in escalations:
        esc_id = e.get("escalation_id") or str(uuid.uuid4())
        created_escalation_ids.append(esc_id)
        esc = Escalation(
            escalation_id=esc_id,
            run_id=run_id,
            rule_id=e["rule_id"],
            version_id=e["version_id"],
            trigger_table=e.get("trigger_table", "policy_checks"),
            trigger_check_id=e.get("trigger_check_id", ""),
            escalation_target=e["escalation_target"],
            escalation_reason=e["escalation_reason"],
            event_type=e.get("event_type", "escalation"),
            event_status=e.get("event_status", "pending"),
            status=e.get("status", "open"),
            created_at=now,
        )
        db.add(esc)

    for s in supplier_evaluations:
        se = SupplierEvaluation(
            eval_id=s.get("eval_id") or str(uuid.uuid4()),
            run_id=run_id,
            supplier_id=s["supplier_id"],
            rank=s.get("rank"),
            total_score=s.get("total_score"),
            price_score=s.get("price_score"),
            quality_score=s.get("quality_score"),
            esg_score=s.get("esg_score"),
            risk_score=s.get("risk_score"),
            hard_checks_total=s.get("hard_checks_total", 0),
            hard_checks_passed=s.get("hard_checks_passed", 0),
            hard_checks_skipped=s.get("hard_checks_skipped", 0),
            hard_checks_failed=s.get("hard_checks_failed", 0),
            policy_checks_total=s.get("policy_checks_total", 0),
            policy_checks_passed=s.get("policy_checks_passed", 0),
            policy_checks_warned=s.get("policy_checks_warned", 0),
            policy_checks_failed=s.get("policy_checks_failed", 0),
            excluded=s.get("excluded", False),
            exclusion_rule_id=s.get("exclusion_rule_id"),
            exclusion_reason=s.get("exclusion_reason"),
            pricing_snapshot=s.get("pricing_snapshot"),
            evaluated_at=now,
        )
        db.add(se)

    db.flush()

    # Step 4: INSERT escalation_logs, evaluation_run_logs
    for i, esc_id in enumerate(created_escalation_ids):
        e = escalations[i] if i < len(escalations) else {}
        erl = EscalationLog(
            log_id=str(uuid.uuid4()),
            escalation_id=esc_id,
            changed_at=now,
            changed_by=triggered_by,
            change_type="created",
            field_changed=None,
            old_value=None,
            new_value={"status": "open", "rule_id": e.get("rule_id", "")},
            note="Evaluation run created escalation",
        )
        db.add(erl)

    run_log = EvaluationRunLog(
        log_id=str(uuid.uuid4()),
        run_id=run_id,
        changed_at=now,
        changed_by=triggered_by,
        change_type="status_change",
        old_status="started",
        new_status="completed",
        old_outcome=None,
        new_outcome="completed",
        note="Evaluation completed",
    )
    db.add(run_log)

    # Step 5: UPDATE evaluation_runs (status=completed)
    run.status = "completed"
    run.finished_at = now
    run.final_outcome = "completed"

    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# 3. Rule Updates Workflow
# ---------------------------------------------------------------------------
# On rule update:
#   1. INSERT new rule_version
#   2. UPDATE previous rule_version (valid_to=NOW())
#   3. INSERT rule_change_logs
# ---------------------------------------------------------------------------


def apply_rule_update(
    db: Session,
    rule_id: str,
    rule_config: dict[str, Any],
    changed_by: str,
    change_reason: str | None = None,
    affected_runs: list[str] | None = None,
) -> RuleVersion:
    """
    Create new rule version, invalidate previous, log change.
    Wrapped in ACID transaction.
    """
    now = datetime.utcnow()

    from sqlalchemy import func

    # Get current active version
    old_version = (
        db.query(RuleVersion)
        .filter(RuleVersion.rule_id == rule_id, RuleVersion.valid_to.is_(None))
        .first()
    )

    # Next version number
    max_ver = (
        db.query(func.max(RuleVersion.version_num))
        .filter(RuleVersion.rule_id == rule_id)
        .scalar()
    )
    version_num = (max_ver or 0) + 1

    # Step 1 & 2: INSERT new rule_version, UPDATE previous valid_to
    new_version_id = str(uuid.uuid4())
    new_version = RuleVersion(
        version_id=new_version_id,
        rule_id=rule_id,
        version_num=version_num,
        rule_config=rule_config,
        valid_from=now,
        valid_to=None,
        changed_by=changed_by,
        change_reason=change_reason,
    )
    db.add(new_version)

    if old_version:
        old_version.valid_to = now
        old_version.changed_by = changed_by
        old_version.change_reason = change_reason

    db.flush()

    # Step 3: INSERT rule_change_logs
    rule_change_log = RuleChangeLog(
        log_id=str(uuid.uuid4()),
        rule_id=rule_id,
        old_version_id=old_version.version_id if old_version else None,
        new_version_id=new_version_id,
        changed_at=now,
        changed_by=changed_by or "system",
        change_reason=change_reason,
        affected_runs=affected_runs,
    )
    db.add(rule_change_log)

    db.commit()
    db.refresh(new_version)
    return new_version
