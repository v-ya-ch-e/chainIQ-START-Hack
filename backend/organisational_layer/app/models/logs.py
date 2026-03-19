from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False, index=True)
    request_id = Column(String(20), ForeignKey("requests.request_id"), nullable=False)
    status = Column(String(20), nullable=False, default="running")
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    total_duration_ms = Column(Integer, nullable=True)
    steps_completed = Column(Integer, nullable=False, default=0)
    steps_failed = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

    entries = relationship(
        "PipelineLogEntry", back_populates="run", cascade="all, delete-orphan",
        order_by="PipelineLogEntry.step_order",
    )


class PipelineLogEntry(Base):
    __tablename__ = "pipeline_log_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("pipeline_runs.run_id"), nullable=False)
    step_name = Column(String(60), nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="started")
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    input_summary = Column(JSON, nullable=True)
    output_summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)

    run = relationship("PipelineRun", back_populates="entries")
