from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EscalationQueueItemOut(BaseModel):
    escalation_id: str
    request_id: str
    title: str
    category: str
    business_unit: str
    country: str
    rule_id: str
    rule_label: str
    trigger: str
    escalate_to: str
    blocking: bool
    status: Literal["open", "resolved"]
    created_at: datetime
    last_updated: datetime
    recommendation_status: Literal[
        "proceed",
        "proceed_with_conditions",
        "cannot_proceed",
    ]

