"""Pydantic schemas for pipeline result persistence and retrieval."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PipelineResultSummary(BaseModel):
    """Pre-extracted summary fields for fast list rendering."""

    supplier_count: int = 0
    excluded_count: int = 0
    escalation_count: int = 0
    blocking_escalation_count: int = 0
    top_supplier_id: str | None = None
    top_supplier_name: str | None = None
    total_issues: int = 0
    confidence_score: int = 0


class PipelineResultCreate(BaseModel):
    """Body for POST — save a pipeline result."""

    run_id: str
    request_id: str
    status: str = "processed"
    recommendation_status: str | None = None
    processed_at: datetime
    output: dict[str, Any]


class PipelineResultOut(BaseModel):
    """Full pipeline result returned by detail endpoints."""

    id: int
    run_id: str
    request_id: str
    status: str
    recommendation_status: str | None = None
    processed_at: datetime
    output: dict[str, Any]
    summary: PipelineResultSummary | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineResultListItem(BaseModel):
    """Lightweight item for list endpoints (no full output)."""

    id: int
    run_id: str
    request_id: str
    status: str
    recommendation_status: str | None = None
    processed_at: datetime
    summary: PipelineResultSummary | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineResultListOut(BaseModel):
    """Paginated envelope for list endpoints."""

    items: list[PipelineResultListItem]
    total: int
    skip: int
    limit: int
