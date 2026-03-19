"""CRUD router for dynamic rules: list, create, read, update, soft-delete, versions, evaluation results."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dynamic_rules import DynamicRule, DynamicRuleVersion, RuleEvaluationResult
from app.schemas.dynamic_rules import (
    VALID_ACTIONS,
    VALID_EVAL_TYPES,
    VALID_PIPELINE_STAGES,
    VALID_RULE_CATEGORIES,
    VALID_SCOPES,
    VALID_SEVERITIES,
    BulkEvaluationResultCreate,
    DynamicRuleCreate,
    DynamicRuleOut,
    DynamicRuleUpdate,
    DynamicRuleVersionOut,
    RuleEvaluationResultCreate,
    RuleEvaluationResultOut,
)

router = APIRouter(prefix="/api/dynamic-rules", tags=["Dynamic Rules"])


def _validate_enums(data: dict):
    if "eval_type" in data and data["eval_type"] is not None:
        if data["eval_type"] not in VALID_EVAL_TYPES:
            raise HTTPException(400, f"eval_type must be one of {VALID_EVAL_TYPES}")
    if "rule_category" in data and data["rule_category"] is not None:
        if data["rule_category"] not in VALID_RULE_CATEGORIES:
            raise HTTPException(400, f"rule_category must be one of {VALID_RULE_CATEGORIES}")
    if "scope" in data and data["scope"] is not None:
        if data["scope"] not in VALID_SCOPES:
            raise HTTPException(400, f"scope must be one of {VALID_SCOPES}")
    if "pipeline_stage" in data and data["pipeline_stage"] is not None:
        if data["pipeline_stage"] not in VALID_PIPELINE_STAGES:
            raise HTTPException(400, f"pipeline_stage must be one of {VALID_PIPELINE_STAGES}")
    if "action_on_fail" in data and data["action_on_fail"] is not None:
        if data["action_on_fail"] not in VALID_ACTIONS:
            raise HTTPException(400, f"action_on_fail must be one of {VALID_ACTIONS}")
    if "severity" in data and data["severity"] is not None:
        if data["severity"] not in VALID_SEVERITIES:
            raise HTTPException(400, f"severity must be one of {VALID_SEVERITIES}")


def _rule_snapshot(rule: DynamicRule) -> dict:
    return {
        "rule_id": rule.rule_id,
        "rule_name": rule.rule_name,
        "description": rule.description,
        "rule_category": rule.rule_category,
        "eval_type": rule.eval_type,
        "scope": rule.scope,
        "pipeline_stage": rule.pipeline_stage,
        "eval_config": rule.eval_config,
        "action_on_fail": rule.action_on_fail,
        "severity": rule.severity,
        "is_blocking": rule.is_blocking,
        "escalation_target": rule.escalation_target,
        "fail_message_template": rule.fail_message_template,
        "is_active": rule.is_active,
        "is_skippable": rule.is_skippable,
        "priority": rule.priority,
    }


# ── List / Active ──────────────────────────────────────────────────


@router.get("/", response_model=list[DynamicRuleOut])
def list_rules(
    stage: str | None = None,
    category: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(DynamicRule)
    if stage:
        q = q.filter(DynamicRule.pipeline_stage == stage)
    if category:
        q = q.filter(DynamicRule.rule_category == category)
    if is_active is not None:
        q = q.filter(DynamicRule.is_active == is_active)
    return q.order_by(DynamicRule.priority, DynamicRule.rule_id).all()


@router.get("/active", response_model=list[DynamicRuleOut])
def list_active_rules(
    stage: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(DynamicRule).filter(DynamicRule.is_active == True)  # noqa: E712
    if stage:
        q = q.filter(DynamicRule.pipeline_stage == stage)
    return q.order_by(DynamicRule.priority, DynamicRule.rule_id).all()


# ── CRUD ───────────────────────────────────────────────────────────


@router.post("/", response_model=DynamicRuleOut, status_code=201)
def create_rule(payload: DynamicRuleCreate, db: Session = Depends(get_db)):
    _validate_enums(payload.model_dump())

    existing = db.query(DynamicRule).filter(DynamicRule.rule_id == payload.rule_id).first()
    if existing:
        raise HTTPException(409, f"Rule {payload.rule_id} already exists")

    rule = DynamicRule(**payload.model_dump())
    db.add(rule)
    db.flush()

    version = DynamicRuleVersion(
        rule_id=rule.rule_id,
        version=1,
        snapshot=_rule_snapshot(rule),
        changed_by=payload.created_by,
        change_reason="Initial creation",
    )
    db.add(version)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{rule_id}", response_model=DynamicRuleOut)
def get_rule(rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(DynamicRule).filter(DynamicRule.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    return rule


@router.put("/{rule_id}", response_model=DynamicRuleOut)
def update_rule(rule_id: str, payload: DynamicRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(DynamicRule).filter(DynamicRule.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")

    update_data = payload.model_dump(exclude_unset=True)
    changed_by = update_data.pop("changed_by", None)
    change_reason = update_data.pop("change_reason", None)

    _validate_enums(update_data)

    if not update_data:
        raise HTTPException(400, "No fields to update")

    old_version = (
        db.query(DynamicRuleVersion)
        .filter(DynamicRuleVersion.rule_id == rule_id, DynamicRuleVersion.valid_to.is_(None))
        .first()
    )
    if old_version:
        old_version.valid_to = datetime.now(timezone.utc)

    for key, value in update_data.items():
        setattr(rule, key, value)
    rule.version += 1

    db.flush()

    new_version = DynamicRuleVersion(
        rule_id=rule.rule_id,
        version=rule.version,
        snapshot=_rule_snapshot(rule),
        changed_by=changed_by,
        change_reason=change_reason,
    )
    db.add(new_version)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    """Soft-delete: sets is_active=False."""
    rule = db.query(DynamicRule).filter(DynamicRule.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")

    rule.is_active = False
    rule.version += 1

    old_version = (
        db.query(DynamicRuleVersion)
        .filter(DynamicRuleVersion.rule_id == rule_id, DynamicRuleVersion.valid_to.is_(None))
        .first()
    )
    if old_version:
        old_version.valid_to = datetime.now(timezone.utc)

    db.flush()

    new_version = DynamicRuleVersion(
        rule_id=rule.rule_id,
        version=rule.version,
        snapshot=_rule_snapshot(rule),
        changed_by="system",
        change_reason="Soft-deleted",
    )
    db.add(new_version)
    db.commit()


# ── Versions ───────────────────────────────────────────────────────


@router.get("/{rule_id}/versions", response_model=list[DynamicRuleVersionOut])
def list_versions(rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(DynamicRule).filter(DynamicRule.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    return (
        db.query(DynamicRuleVersion)
        .filter(DynamicRuleVersion.rule_id == rule_id)
        .order_by(DynamicRuleVersion.version)
        .all()
    )


# ── Evaluation Results ─────────────────────────────────────────────


@router.post("/evaluation-results", status_code=201)
def store_evaluation_results(payload: BulkEvaluationResultCreate, db: Session = Depends(get_db)):
    for r in payload.results:
        obj = RuleEvaluationResult(**r.model_dump())
        db.add(obj)
    db.commit()
    return {"stored": len(payload.results)}


@router.get("/evaluation-results/by-run/{run_id}", response_model=list[RuleEvaluationResultOut])
def get_results_by_run(run_id: str, db: Session = Depends(get_db)):
    return (
        db.query(RuleEvaluationResult)
        .filter(RuleEvaluationResult.run_id == run_id)
        .order_by(RuleEvaluationResult.evaluated_at)
        .all()
    )
