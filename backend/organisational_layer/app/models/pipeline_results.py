"""ORM model for persisted pipeline evaluation results."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON

from app.database import Base


class PipelineResult(Base):
    __tablename__ = "pipeline_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False, index=True)
    request_id = Column(
        String(20), ForeignKey("requests.request_id"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="processed")
    recommendation_status = Column(String(30), nullable=True)
    processed_at = Column(DateTime, nullable=False)
    output = Column(JSON, nullable=False)
    summary = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
