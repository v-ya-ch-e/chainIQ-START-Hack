from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.policies import (
    ApprovalThreshold,
    PreferredSupplierPolicy,
    RestrictedSupplierPolicy,
)
from app.schemas.policies import (
    ApprovalThresholdOut,
    PreferredSupplierPolicyOut,
    RestrictedSupplierPolicyOut,
)

router = APIRouter(prefix="/api/policies", tags=["Policies"])


# --- Approval Thresholds ---


@router.get("/approval-thresholds", response_model=list[ApprovalThresholdOut])
def list_approval_thresholds(
    currency: str | None = None, db: Session = Depends(get_db)
):
    q = db.query(ApprovalThreshold).options(
        joinedload(ApprovalThreshold.managers),
        joinedload(ApprovalThreshold.deviation_approvers),
    )
    if currency:
        q = q.filter(ApprovalThreshold.currency == currency)
    return q.order_by(ApprovalThreshold.currency, ApprovalThreshold.min_amount).all()


@router.get(
    "/approval-thresholds/{threshold_id}", response_model=ApprovalThresholdOut
)
def get_approval_threshold(threshold_id: str, db: Session = Depends(get_db)):
    t = (
        db.query(ApprovalThreshold)
        .options(
            joinedload(ApprovalThreshold.managers),
            joinedload(ApprovalThreshold.deviation_approvers),
        )
        .filter(ApprovalThreshold.threshold_id == threshold_id)
        .first()
    )
    if not t:
        raise HTTPException(status_code=404, detail="Threshold not found")
    return t


# --- Preferred Suppliers ---


@router.get("/preferred-suppliers", response_model=list[PreferredSupplierPolicyOut])
def list_preferred_suppliers(
    supplier_id: str | None = None,
    category_l1: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(PreferredSupplierPolicy).options(
        joinedload(PreferredSupplierPolicy.region_scopes)
    )
    if supplier_id:
        q = q.filter(PreferredSupplierPolicy.supplier_id == supplier_id)
    if category_l1:
        q = q.filter(PreferredSupplierPolicy.category_l1 == category_l1)
    return q.order_by(PreferredSupplierPolicy.supplier_id).all()


@router.get(
    "/preferred-suppliers/{policy_id}", response_model=PreferredSupplierPolicyOut
)
def get_preferred_supplier_policy(policy_id: int, db: Session = Depends(get_db)):
    p = (
        db.query(PreferredSupplierPolicy)
        .options(joinedload(PreferredSupplierPolicy.region_scopes))
        .filter(PreferredSupplierPolicy.id == policy_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Preferred supplier policy not found")
    return p


# --- Restricted Suppliers ---


@router.get("/restricted-suppliers", response_model=list[RestrictedSupplierPolicyOut])
def list_restricted_suppliers(
    supplier_id: str | None = None, db: Session = Depends(get_db)
):
    q = db.query(RestrictedSupplierPolicy).options(
        joinedload(RestrictedSupplierPolicy.scopes)
    )
    if supplier_id:
        q = q.filter(RestrictedSupplierPolicy.supplier_id == supplier_id)
    return q.order_by(RestrictedSupplierPolicy.supplier_id).all()


@router.get(
    "/restricted-suppliers/{policy_id}", response_model=RestrictedSupplierPolicyOut
)
def get_restricted_supplier_policy(policy_id: int, db: Session = Depends(get_db)):
    p = (
        db.query(RestrictedSupplierPolicy)
        .options(joinedload(RestrictedSupplierPolicy.scopes))
        .filter(RestrictedSupplierPolicy.id == policy_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Restricted supplier policy not found")
    return p
