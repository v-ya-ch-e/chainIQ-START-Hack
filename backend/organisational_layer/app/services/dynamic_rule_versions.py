"""Resolve frozen / active snapshots from `dynamic_rule_versions` (and safe fallbacks)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.dynamic_rules import DynamicRule, DynamicRuleVersion


def coerce_snapshot_dict(raw: Any) -> dict[str, Any] | None:
    """MySQL JSON / drivers sometimes return str; normalize to dict."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def live_dynamic_rule_snapshot(rule: DynamicRule) -> dict[str, Any]:
    """Same shape as rows in `dynamic_rule_versions.snapshot` / pipeline contract."""
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


def get_dynamic_snapshot_and_version(
    db: Session,
    rule_id: str,
) -> tuple[dict[str, Any] | None, int | None]:
    """
    Return (snapshot dict, dynamic version int) for traceability UI.

    Order:
    1. Active row in `dynamic_rule_versions` (valid_to IS NULL)
    2. Else latest row by `version` DESC (historical / inconsistent valid_to)
    3. Else live `dynamic_rules` row (no version history yet)
    """
    active = (
        db.query(DynamicRuleVersion)
        .filter(
            DynamicRuleVersion.rule_id == rule_id,
            DynamicRuleVersion.valid_to.is_(None),
        )
        .first()
    )
    row = active
    if not row:
        row = (
            db.query(DynamicRuleVersion)
            .filter(DynamicRuleVersion.rule_id == rule_id)
            .order_by(DynamicRuleVersion.version.desc())
            .first()
        )
    if row:
        snap = coerce_snapshot_dict(row.snapshot)
        if snap is not None:
            return snap, row.version
        rule = db.query(DynamicRule).filter(DynamicRule.rule_id == rule_id).first()
        if rule:
            return live_dynamic_rule_snapshot(rule), row.version
        return None, row.version

    rule = db.query(DynamicRule).filter(DynamicRule.rule_id == rule_id).first()
    if rule:
        return live_dynamic_rule_snapshot(rule), int(rule.version)
    return None, None


def get_dynamic_snapshot_by_version(
    db: Session,
    rule_id: str,
    version: int,
) -> tuple[dict[str, Any] | None, DynamicRuleVersion | None]:
    row = (
        db.query(DynamicRuleVersion)
        .filter(
            DynamicRuleVersion.rule_id == rule_id,
            DynamicRuleVersion.version == version,
        )
        .first()
    )
    if not row:
        return None, None
    return coerce_snapshot_dict(row.snapshot), row
