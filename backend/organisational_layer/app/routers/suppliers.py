from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.reference import (
    Category,
    PricingTier,
    Supplier,
    SupplierCategory,
    SupplierServiceRegion,
)
from app.schemas.reference import (
    PricingTierOut,
    SupplierCategoryOut,
    SupplierCreate,
    SupplierDetailOut,
    SupplierOut,
    SupplierServiceRegionOut,
    SupplierUpdate,
)

router = APIRouter(prefix="/api/suppliers", tags=["Suppliers"])


@router.get("/", response_model=list[SupplierOut])
def list_suppliers(
    country_hq: str | None = None,
    currency: str | None = None,
    category_l1: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Supplier)
    if country_hq:
        q = q.filter(Supplier.country_hq == country_hq)
    if currency:
        q = q.filter(Supplier.currency == currency)
    if category_l1:
        q = q.join(SupplierCategory).join(Category).filter(
            Category.category_l1 == category_l1
        )
    return q.order_by(Supplier.supplier_id).all()


@router.get("/{supplier_id}", response_model=SupplierDetailOut)
def get_supplier(supplier_id: str, db: Session = Depends(get_db)):
    sup = (
        db.query(Supplier)
        .options(joinedload(Supplier.categories), joinedload(Supplier.service_regions))
        .filter(Supplier.supplier_id == supplier_id)
        .first()
    )
    if not sup:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return sup


@router.post("/", response_model=SupplierOut, status_code=201)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    existing = db.query(Supplier).filter(Supplier.supplier_id == payload.supplier_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Supplier ID already exists")
    sup = Supplier(**payload.model_dump())
    db.add(sup)
    db.commit()
    db.refresh(sup)
    return sup


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: str, payload: SupplierUpdate, db: Session = Depends(get_db)
):
    sup = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    if not sup:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sup, field, value)
    db.commit()
    db.refresh(sup)
    return sup


@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: str, db: Session = Depends(get_db)):
    sup = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    if not sup:
        raise HTTPException(status_code=404, detail="Supplier not found")
    db.delete(sup)
    db.commit()


@router.get("/{supplier_id}/categories", response_model=list[SupplierCategoryOut])
def get_supplier_categories(supplier_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(SupplierCategory)
        .filter(SupplierCategory.supplier_id == supplier_id)
        .all()
    )
    if not rows:
        sup = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
        if not sup:
            raise HTTPException(status_code=404, detail="Supplier not found")
    return rows


@router.get("/{supplier_id}/regions", response_model=list[SupplierServiceRegionOut])
def get_supplier_regions(supplier_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(SupplierServiceRegion)
        .filter(SupplierServiceRegion.supplier_id == supplier_id)
        .all()
    )
    if not rows:
        sup = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
        if not sup:
            raise HTTPException(status_code=404, detail="Supplier not found")
    return rows


@router.get("/{supplier_id}/pricing", response_model=list[PricingTierOut])
def get_supplier_pricing(
    supplier_id: str,
    category_id: int | None = None,
    region: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(PricingTier).filter(PricingTier.supplier_id == supplier_id)
    if category_id:
        q = q.filter(PricingTier.category_id == category_id)
    if region:
        q = q.filter(PricingTier.region == region)
    rows = q.order_by(PricingTier.category_id, PricingTier.min_quantity).all()
    if not rows:
        sup = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
        if not sup:
            raise HTTPException(status_code=404, detail="Supplier not found")
    return rows
