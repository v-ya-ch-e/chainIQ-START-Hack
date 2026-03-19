from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.requests import Request
from app.schemas.escalations import EscalationQueueItemOut
from app.services.escalations import evaluate_escalation_queue

router = APIRouter(prefix="/api/escalations", tags=["Escalations"])


@router.get("/queue", response_model=list[EscalationQueueItemOut])
def get_escalation_queue(db: Session = Depends(get_db)):
    return evaluate_escalation_queue(db)


@router.get("/by-request/{request_id}", response_model=list[EscalationQueueItemOut])
def get_request_escalations(request_id: str, db: Session = Depends(get_db)):
    exists = db.query(Request.request_id).filter(Request.request_id == request_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Request not found")
    return evaluate_escalation_queue(db, request_id=request_id)

