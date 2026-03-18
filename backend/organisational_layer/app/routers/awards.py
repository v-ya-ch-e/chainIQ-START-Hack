from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.historical import HistoricalAward
from app.schemas.historical import HistoricalAwardListOut, HistoricalAwardOut

router = APIRouter(prefix="/api/awards", tags=["Historical Awards"])


@router.get("/", response_model=HistoricalAwardListOut)
def list_awards(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    request_id: str | None = None,
    supplier_id: str | None = None,
    awarded: bool | None = None,
    policy_compliant: bool | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(HistoricalAward)
    if request_id:
        q = q.filter(HistoricalAward.request_id == request_id)
    if supplier_id:
        q = q.filter(HistoricalAward.supplier_id == supplier_id)
    if awarded is not None:
        q = q.filter(HistoricalAward.awarded == awarded)
    if policy_compliant is not None:
        q = q.filter(HistoricalAward.policy_compliant == policy_compliant)

    total = q.count()
    items = q.order_by(HistoricalAward.award_id).offset(skip).limit(limit).all()
    return HistoricalAwardListOut(items=items, total=total, skip=skip, limit=limit)


@router.get("/by-request/{request_id}", response_model=list[HistoricalAwardOut])
def get_awards_by_request(request_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(HistoricalAward)
        .filter(HistoricalAward.request_id == request_id)
        .order_by(HistoricalAward.award_rank)
        .all()
    )
    return rows


@router.get("/{award_id}", response_model=HistoricalAwardOut)
def get_award(award_id: str, db: Session = Depends(get_db)):
    award = (
        db.query(HistoricalAward)
        .filter(HistoricalAward.award_id == award_id)
        .first()
    )
    if not award:
        raise HTTPException(status_code=404, detail="Award not found")
    return award
