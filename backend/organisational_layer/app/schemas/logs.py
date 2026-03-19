from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pipeline Runs
# ---------------------------------------------------------------------------

class PipelineRunCreate(BaseModel):
    run_id: str
    request_id: str
    started_at: datetime


class PipelineRunUpdate(BaseModel):
    status: str | None = None
    completed_at: datetime | None = None
    total_duration_ms: int | None = None
    steps_completed: int | None = None
    steps_failed: int | None = None
    error_message: str | None = None


class PipelineRunOut(BaseModel):
    id: int
    run_id: str
    request_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_ms: int | None = None
    steps_completed: int
    steps_failed: int
    error_message: str | None = None

    model_config = {"from_attributes": True}


class PipelineLogEntryOut(BaseModel):
    id: int
    run_id: str
    step_name: str
    step_order: int
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    input_summary: Any | None = None
    output_summary: Any | None = None
    error_message: str | None = None
    metadata_: Any | None = None

    model_config = {"from_attributes": True}


class PipelineRunDetailOut(PipelineRunOut):
    entries: list[PipelineLogEntryOut] = []

    model_config = {"from_attributes": True}


class PipelineRunListOut(BaseModel):
    items: list[PipelineRunOut]
    total: int


# ---------------------------------------------------------------------------
# Pipeline Log Entries
# ---------------------------------------------------------------------------

class PipelineLogEntryCreate(BaseModel):
    run_id: str
    step_name: str
    step_order: int
    started_at: datetime
    input_summary: Any | None = None


class PipelineLogEntryUpdate(BaseModel):
    status: str | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    output_summary: Any | None = None
    error_message: str | None = None
    metadata_: Any | None = None
