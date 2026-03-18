from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.policies import CategoryRule, EscalationRule, GeographyRule
from app.schemas.policies import (
    CategoryRuleOut,
    EscalationRuleOut,
    GeographyRuleOut,
)

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
        q = q.filter(GeographyRule.country == country)
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
