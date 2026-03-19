"""Pydantic models for the process-request endpoint (stub)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    """Incoming payload — the minimum needed to kick off processing."""

    request_id: str = Field(
        ..., description="Purchase request ID, e.g. REQ-000004", examples=["REQ-000004"]
    )


class ProcessRequestResponse(BaseModel):
    """Stub response returned until the full pipeline is implemented."""

    request_id: str
    status: str = "not_implemented"
    message: str = "Full processing pipeline is not yet implemented. Use /api/filter-suppliers and /api/rank-suppliers for individual steps."
