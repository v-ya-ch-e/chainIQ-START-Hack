import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.policies import (
    CategoryRule,
    EscalationRule,
    GeographyRule,
    GeographyRuleCountry,
    RuleDefinition,
    RuleVersion,
)
from app.schemas.policies import (
    CategoryRuleOut,
    EscalationRuleOut,
    GeographyRuleOut,
    RuleDefinitionCreate,
    RuleDefinitionOut,
    RuleDefinitionUpdate,
    RuleVersionCreate,
    RuleVersionOut,
)
from app.services.rule_evaluator import _safe_context

router = APIRouter(prefix="/api/rules", tags=["Rules"])


# --- Category Rules ---


@router.get("/category", response_model=list[CategoryRuleOut])
def list_category_rules(
    category_id: int | None = None, db: Session = Depends(get_db)
):
    q = db.query(CategoryRule)
    if category_id:
        q = q.filter(CategoryRule.category_id == category_id)
    return q.order_by(CategoryRule.rule_id).all()


@router.get("/category/{rule_id}", response_model=CategoryRuleOut)
def get_category_rule(rule_id: str, db: Session = Depends(get_db)):
    r = db.query(CategoryRule).filter(CategoryRule.rule_id == rule_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Category rule not found")
    return r


# --- Geography Rules ---


@router.get("/geography", response_model=list[GeographyRuleOut])
def list_geography_rules(
    country: str | None = None, db: Session = Depends(get_db)
):
    q = db.query(GeographyRule).options(
        joinedload(GeographyRule.countries),
        joinedload(GeographyRule.applies_to_categories),
    )
    if country:
        region_rule_ids = (
            db.query(GeographyRuleCountry.rule_id)
            .filter(GeographyRuleCountry.country_code == country)
            .subquery()
        )
        q = q.filter(
            or_(
                GeographyRule.country == country,
                GeographyRule.rule_id.in_(db.query(region_rule_ids)),
            )
        )
    return q.order_by(GeographyRule.rule_id).all()


@router.get("/geography/{rule_id}", response_model=GeographyRuleOut)
def get_geography_rule(rule_id: str, db: Session = Depends(get_db)):
    r = (
        db.query(GeographyRule)
        .options(
            joinedload(GeographyRule.countries),
            joinedload(GeographyRule.applies_to_categories),
        )
        .filter(GeographyRule.rule_id == rule_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Geography rule not found")
    return r


# --- Escalation Rules ---


@router.get("/escalation", response_model=list[EscalationRuleOut])
def list_escalation_rules(db: Session = Depends(get_db)):
    return (
        db.query(EscalationRule)
        .options(joinedload(EscalationRule.currencies))
        .order_by(EscalationRule.rule_id)
        .all()
    )


@router.get("/escalation/{rule_id}", response_model=EscalationRuleOut)
def get_escalation_rule(rule_id: str, db: Session = Depends(get_db)):
    r = (
        db.query(EscalationRule)
        .options(joinedload(EscalationRule.currencies))
        .filter(EscalationRule.rule_id == rule_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Escalation rule not found")
    return r


# --- Rule Definitions + Versions (data-driven rule engine) ---

DUMMY_CONTEXT = {
    "missing_required_information": False, "preferred_supplier_restricted": False,
    "has_compliant_priceable_supplier": True, "has_residency_compatible_supplier": True,
    "single_supplier_capacity_risk": False, "preferred_supplier_unregistered_usd": False,
    "strategic_tier": False, "has_single_supplier_instruction": False,
    "category_label": "Test / Category", "threshold_id": "AT-001",
    "threshold_quotes_required": 1, "category_l1": "IT", "category_l2": "Hardware",
    "currency": "EUR", "budget_amount": 1000.0, "quantity": 10,
    "required_by_date": "2026-12-31", "days_until_required": 100,
    "delivery_countries_count": 1, "min_supplier_total": 500.0,
    "min_expedited_lead_time": 5, "req_data_residency_constraint": False,
    "req_quantity": 10, "delivery_country": "DE", "sup_supplier_id": "SUP-0001",
    "sup_preferred_supplier": True, "sup_data_residency_supported": True,
    "sup_capacity_per_month": 1000, "sup_risk_score": 20, "sup_is_restricted": False,
    "has_budget_insufficient_issue": False, "has_lead_time_issue": False,
    "compliant_count": 5, "initial_supplier_count": 10, "compliant_residency_count": 5,
    "preferred_supplier_excluded_restricted": False, "min_ranked_total": 500.0,
    "country": "DE", "requester_instruction": None,
}


def _current_version(db: Session, rule_id: str) -> RuleVersion | None:
    return (
        db.query(RuleVersion)
        .filter(RuleVersion.rule_id == rule_id, RuleVersion.valid_to == None)
        .order_by(RuleVersion.version_num.desc())
        .first()
    )


def _parse_rule_config(version: RuleVersion | None) -> dict:
    if not version or not version.rule_config:
        return {}
    raw = version.rule_config
    return json.loads(raw) if isinstance(raw, str) else raw


def _enrich_definition(rd: RuleDefinition, db: Session) -> dict:
    """Build a RuleDefinitionOut-compatible dict with current_version attached."""
    version = _current_version(db, rd.rule_id)
    result = {c.name: getattr(rd, c.name) for c in rd.__table__.columns}
    if version:
        config = _parse_rule_config(version)
        result["current_version"] = {
            "version_id": version.version_id,
            "rule_id": version.rule_id,
            "version_num": version.version_num,
            "rule_config": config,
            "valid_from": str(version.valid_from) if version.valid_from else None,
            "valid_to": str(version.valid_to) if version.valid_to else None,
            "changed_by": version.changed_by,
            "change_reason": version.change_reason,
        }
    else:
        result["current_version"] = None
    return result


@router.get("/definitions")
def list_rule_definitions(
    rule_type: str | None = Query(None),
    scope: str | None = Query(None),
    active: bool | None = Query(None),
    evaluation_mode: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(RuleDefinition)
    if rule_type:
        q = q.filter(RuleDefinition.rule_type == rule_type)
    if scope:
        q = q.filter(RuleDefinition.scope == scope)
    if active is not None:
        q = q.filter(RuleDefinition.active == active)
    if evaluation_mode:
        q = q.filter(RuleDefinition.evaluation_mode == evaluation_mode)
    defs = q.order_by(RuleDefinition.sort_order, RuleDefinition.rule_id).all()
    return [_enrich_definition(rd, db) for rd in defs]


@router.get("/definitions/context/{scope}")
def get_rule_context(scope: str):
    """Return available field names and types for a given scope (for UI expression builders)."""
    contexts = {
        "request": [
            ("category_l1", "str | None"), ("category_l2", "str | None"),
            ("currency", "str | None"), ("budget_amount", "float | None"),
            ("quantity", "int | None"), ("required_by_date", "str | None"),
            ("days_until_required", "int | None"), ("delivery_countries_count", "int"),
            ("missing_required_information", "bool"), ("preferred_supplier_restricted", "bool"),
            ("has_compliant_priceable_supplier", "bool"),
            ("has_residency_compatible_supplier", "bool | None"),
            ("single_supplier_capacity_risk", "bool"),
            ("preferred_supplier_unregistered_usd", "bool"),
            ("strategic_tier", "bool"), ("has_single_supplier_instruction", "bool"),
            ("threshold_id", "str | None"), ("threshold_quotes_required", "int"),
            ("category_label", "str"), ("min_supplier_total", "float | None"),
            ("min_expedited_lead_time", "int | None"),
        ],
        "supplier": [
            ("req_data_residency_constraint", "bool"), ("req_quantity", "int | None"),
            ("delivery_country", "str"), ("sup_supplier_id", "str"),
            ("sup_preferred_supplier", "bool"), ("sup_data_residency_supported", "bool"),
            ("sup_capacity_per_month", "int | None"), ("sup_risk_score", "int"),
            ("sup_is_restricted", "bool"), ("sup_restriction_reason", "str | None"),
        ],
        "pipeline": [
            ("has_budget_insufficient_issue", "bool"), ("has_lead_time_issue", "bool"),
            ("days_until_required", "int | None"), ("min_expedited_lead_time", "int | None"),
            ("compliant_count", "int"), ("initial_supplier_count", "int"),
            ("compliant_residency_count", "int"),
            ("preferred_supplier_excluded_restricted", "bool"),
            ("min_ranked_total", "float | None"), ("req_data_residency_constraint", "bool"),
            ("budget_amount", "float | None"), ("currency", "str"), ("country", "str"),
            ("requester_instruction", "str | None"), ("threshold_quotes_required", "int"),
        ],
    }
    if scope not in contexts:
        raise HTTPException(status_code=404, detail=f"Unknown scope: {scope}")
    return {"scope": scope, "fields": [{"name": n, "type": t} for n, t in contexts[scope]]}


@router.get("/definitions/{rule_id}")
def get_rule_definition(rule_id: str, db: Session = Depends(get_db)):
    rd = db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first()
    if not rd:
        raise HTTPException(status_code=404, detail="Rule definition not found")
    return _enrich_definition(rd, db)


def _validate_expression(condition_expr: str | None, evaluation_mode: str) -> None:
    if evaluation_mode != "expression":
        return
    if not condition_expr or not condition_expr.strip():
        return
    try:
        from simpleeval import SimpleEval
        names = _safe_context(DUMMY_CONTEXT)
        SimpleEval(names=names).eval(condition_expr.strip())
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid expression: {e!s}")


@router.post("/definitions")
def create_rule_definition(
    payload: RuleDefinitionCreate, db: Session = Depends(get_db)
):
    config = payload.rule_config or {}
    _validate_expression(config.get("condition_expr"), payload.evaluation_mode)
    if payload.evaluation_mode == "llm" and not config.get("llm_prompt"):
        raise HTTPException(status_code=422, detail="rule_config.llm_prompt required for llm mode")
    existing = db.query(RuleDefinition).filter(RuleDefinition.rule_id == payload.rule_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Rule ID already exists")

    rd = RuleDefinition(
        rule_id=payload.rule_id, rule_type=payload.rule_type, rule_name=payload.rule_name,
        scope=payload.scope, evaluation_mode=payload.evaluation_mode,
        is_skippable=payload.is_skippable, source=payload.source, severity=payload.severity,
        is_blocking=payload.is_blocking, breaks_completeness=payload.breaks_completeness,
        action_type=payload.action_type, action_target=payload.action_target,
        trigger_template=payload.trigger_template, action_required=payload.action_required,
        field_ref=payload.field_ref, description=payload.description,
        active=payload.active, sort_order=payload.sort_order,
    )
    db.add(rd)
    db.flush()

    rv = RuleVersion(
        version_id=str(uuid.uuid4()), rule_id=payload.rule_id, version_num=1,
        rule_config=json.dumps(config),
        valid_from=datetime.now(timezone.utc),
    )
    db.add(rv)
    db.commit()
    db.refresh(rd)
    return _enrich_definition(rd, db)


@router.put("/definitions/{rule_id}")
def update_rule_definition(
    rule_id: str, payload: RuleDefinitionUpdate, db: Session = Depends(get_db)
):
    rd = db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first()
    if not rd:
        raise HTTPException(status_code=404, detail="Rule definition not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rd, field, value)
    db.commit()
    db.refresh(rd)
    return _enrich_definition(rd, db)


@router.delete("/definitions/{rule_id}")
def delete_rule_definition(rule_id: str, db: Session = Depends(get_db)):
    rd = db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first()
    if not rd:
        raise HTTPException(status_code=404, detail="Rule definition not found")
    db.delete(rd)
    db.commit()
    return {"deleted": rule_id}


# --- Rule Versions ---


@router.get("/versions/{rule_id}", response_model=list[RuleVersionOut])
def list_rule_versions(rule_id: str, db: Session = Depends(get_db)):
    rd = db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first()
    if not rd:
        raise HTTPException(status_code=404, detail="Rule definition not found")
    versions = (
        db.query(RuleVersion)
        .filter(RuleVersion.rule_id == rule_id)
        .order_by(RuleVersion.version_num.desc())
        .all()
    )
    result = []
    for v in versions:
        result.append(RuleVersionOut(
            version_id=v.version_id, rule_id=v.rule_id, version_num=v.version_num,
            rule_config=_parse_rule_config(v),
            valid_from=str(v.valid_from) if v.valid_from else None,
            valid_to=str(v.valid_to) if v.valid_to else None,
            changed_by=v.changed_by, change_reason=v.change_reason,
        ))
    return result


@router.post("/versions/{rule_id}")
def create_rule_version(
    rule_id: str, payload: RuleVersionCreate, db: Session = Depends(get_db)
):
    """Create a new version for a rule. Closes the current version's valid_to."""
    rd = db.query(RuleDefinition).filter(RuleDefinition.rule_id == rule_id).first()
    if not rd:
        raise HTTPException(status_code=404, detail="Rule definition not found")

    config = payload.rule_config or {}
    _validate_expression(config.get("condition_expr"), rd.evaluation_mode)

    current = _current_version(db, rule_id)
    now = datetime.now(timezone.utc)
    next_num = (current.version_num + 1) if current else 1
    if current:
        current.valid_to = now

    rv = RuleVersion(
        version_id=str(uuid.uuid4()), rule_id=rule_id, version_num=next_num,
        rule_config=json.dumps(config), valid_from=now,
        changed_by=payload.changed_by, change_reason=payload.change_reason,
    )
    db.add(rv)
    db.commit()
    return _enrich_definition(rd, db)
