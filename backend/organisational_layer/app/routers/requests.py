from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.requests import Request, RequestDeliveryCountry, RequestScenarioTag
from app.schemas.requests import (
    RequestCreate,
    RequestDetailOut,
    RequestListItemOut,
    RequestListOut,
    RequestOut,
    RequestUpdate,
)

router = APIRouter(prefix="/api/requests", tags=["Requests"])


@router.get("/", response_model=RequestListOut)
def list_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    country: str | None = None,
    category_id: int | None = None,
    status: str | None = None,
    currency: str | None = None,
    tag: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Request)
    if country:
        q = q.filter(Request.country == country)
    if category_id:
        q = q.filter(Request.category_id == category_id)
    if status:
        q = q.filter(Request.status == status)
    if currency:
        q = q.filter(Request.currency == currency)
    if tag:
        q = q.join(RequestScenarioTag).filter(RequestScenarioTag.tag == tag)

    total = q.count()
    items = (
        q.options(joinedload(Request.scenario_tags))
        .order_by(Request.request_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    items_out = [
        RequestListItemOut(
            **RequestOut.model_validate(item).model_dump(),
            scenario_tags=[entry.tag for entry in item.scenario_tags],
        )
        for item in items
    ]
    return RequestListOut(items=items_out, total=total, skip=skip, limit=limit)


@router.get("/{request_id}", response_model=RequestDetailOut)
def get_request(request_id: str, db: Session = Depends(get_db)):
    req = (
        db.query(Request)
        .options(
            joinedload(Request.delivery_countries),
            joinedload(Request.scenario_tags),
            joinedload(Request.category),
        )
        .filter(Request.request_id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    result = RequestDetailOut.model_validate(req)
    if req.category:
        result.category_l1 = req.category.category_l1
        result.category_l2 = req.category.category_l2
    return result


@router.post("/", response_model=RequestOut, status_code=201)
def create_request(payload: RequestCreate, db: Session = Depends(get_db)):
    existing = db.query(Request).filter(Request.request_id == payload.request_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Request ID already exists")

    data = payload.model_dump(exclude={"delivery_countries", "scenario_tags"})
    req = Request(**data)

    for cc in payload.delivery_countries:
        req.delivery_countries.append(RequestDeliveryCountry(country_code=cc))
    for t in payload.scenario_tags:
        req.scenario_tags.append(RequestScenarioTag(tag=t))

    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.put("/{request_id}", response_model=RequestOut)
def update_request(
    request_id: str, payload: RequestUpdate, db: Session = Depends(get_db)
):
    req = db.query(Request).filter(Request.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    update_data = payload.model_dump(exclude_unset=True)
    delivery_countries = update_data.pop("delivery_countries", None)
    scenario_tags = update_data.pop("scenario_tags", None)

    for field, value in update_data.items():
        setattr(req, field, value)

    if delivery_countries is not None:
        req.delivery_countries.clear()
        for country_code in delivery_countries:
            req.delivery_countries.append(RequestDeliveryCountry(country_code=country_code))

    if scenario_tags is not None:
        req.scenario_tags.clear()
        for tag in scenario_tags:
            req.scenario_tags.append(RequestScenarioTag(tag=tag))

    db.commit()
    db.refresh(req)
    return req


@router.delete("/{request_id}", status_code=204)
def delete_request(request_id: str, db: Session = Depends(get_db)):
    req = db.query(Request).filter(Request.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    db.delete(req)
    db.commit()
