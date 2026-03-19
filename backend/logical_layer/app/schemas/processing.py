"""Pydantic models for the processRequest endpoint (full pipeline)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    """Incoming payload — the minimum needed to kick off processing."""

    request_id: str = Field(
        ..., description="Purchase request ID, e.g. REQ-000004", examples=["REQ-000004"]
    )


class ProcessRequestResponse(BaseModel):
    """Full pipeline output matching example_output.json structure.

    When the request is invalid, only a subset of fields is populated
    and ``status`` is ``"invalid"`` instead of ``"processed"``.
    """

    model_config = {"extra": "allow"}

    request_id: str
    processed_at: str
    status: str = Field(
        default="processed",
        description="'processed' for valid requests, 'invalid' for requests that fail validation",
    )
    request_interpretation: dict[str, Any] = Field(default={})
    validation: dict[str, Any] = Field(default={})
    policy_evaluation: dict[str, Any] = Field(default={})
    supplier_shortlist: list[dict[str, Any]] = Field(default=[])
    suppliers_excluded: list[dict[str, Any]] = Field(default=[])
    escalations: list[dict[str, Any]] = Field(default=[])
    recommendation: dict[str, Any] = Field(default={})
    audit_trail: dict[str, Any] = Field(default={})
    summary: str | None = Field(default=None, description="Only present for invalid requests")
