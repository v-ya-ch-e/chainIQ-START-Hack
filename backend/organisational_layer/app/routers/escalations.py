from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evaluations import Escalation
from app.models.requests import Request
from app.schemas.escalations import EscalationQueueItemOut
from app.services.escalations import evaluate_escalation_queue
from app.services.transaction_workflows import apply_escalation_change

router = APIRouter(prefix="/api/escalations", tags=["Escalations"])


class EscalationChangeBody(BaseModel):
    """Payload for PATCH /api/escalations/{escalation_id}."""

    changed_by: str
    updates: dict[str, Any]  # e.g. {"status": "resolved", "resolved_by": "user@co", "resolved_at": "..."}
    policy_rule_id: str | None = None
    change_reason: str | None = None


@router.get("/queue", response_model=list[EscalationQueueItemOut])
def get_escalation_queue(db: Session = Depends(get_db)):
    return evaluate_escalation_queue(db)


@router.get("/by-request/{request_id}", response_model=list[EscalationQueueItemOut])
def get_request_escalations(request_id: str, db: Session = Depends(get_db)):
    exists = db.query(Request.request_id).filter(Request.request_id == request_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Request not found")
    return evaluate_escalation_queue(db, request_id=request_id)


@router.patch("/{escalation_id}")
@router.patch("/stored/{escalation_id}")
def update_stored_escalation(
    escalation_id: str,
    body: EscalationChangeBody,
    db: Session = Depends(get_db),
):
    """
    Update an escalation stored in the escalations table (from evaluation runs).
    ACID workflow: 1. INSERT policy_change_logs, 2. INSERT escalation_logs, 3. UPDATE escalations.
    """
    esc = db.query(Escalation).filter(Escalation.escalation_id == escalation_id).first()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    try:
        updated = apply_escalation_change(
            db=db,
            escalation_id=escalation_id,
            changed_by=body.changed_by,
            updates=body.updates,
            policy_rule_id=body.policy_rule_id,
            change_reason=body.change_reason,
        )
        return {"escalation_id": updated.escalation_id, "status": updated.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

