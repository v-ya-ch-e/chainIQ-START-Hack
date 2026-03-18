from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reference import Category
from app.schemas.reference import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/api/categories", tags=["Categories"])


@router.get("/", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.category_l1, Category.category_l2).all()


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: int, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@router.post("/", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    cat = Category(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)
):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()
