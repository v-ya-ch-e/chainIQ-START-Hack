"""ORM models for the dynamic rule engine."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class DynamicRule(Base):
    __tablename__ = "dynamic_rules"

    rule_id = Column(String(20), primary_key=True)
    rule_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    rule_category = Column(String(20), nullable=False)
    eval_type = Column(String(20), nullable=False)
    scope = Column(String(10), nullable=False, default="request")
    pipeline_stage = Column(String(20), nullable=False)
    eval_config = Column(JSON, nullable=False)
    action_on_fail = Column(String(20), nullable=False, default="warn")
    severity = Column(String(10), nullable=False, default="medium")
    is_blocking = Column(Boolean, nullable=False, default=False)
    escalation_target = Column(String(200), nullable=True)
    fail_message_template = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_skippable = Column(Boolean, nullable=False, default=False)
    priority = Column(Integer, nullable=False, default=100)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100), nullable=True)

    versions = relationship(
        "DynamicRuleVersion",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="DynamicRuleVersion.version",
    )


class DynamicRuleVersion(Base):
    __tablename__ = "dynamic_rule_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(20), ForeignKey("dynamic_rules.rule_id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    valid_from = Column(DateTime, nullable=False, server_default=func.now())
    valid_to = Column(DateTime, nullable=True)
    changed_by = Column(String(100), nullable=True)
    change_reason = Column(Text, nullable=True)

    rule = relationship("DynamicRule", back_populates="versions")


class RuleEvaluationResult(Base):
    __tablename__ = "rule_evaluation_results"

    result_id = Column(String(36), primary_key=True)
    run_id = Column(String(36), nullable=False)
    rule_id = Column(String(20), ForeignKey("dynamic_rules.rule_id"), nullable=False)
    rule_version = Column(Integer, nullable=False)
    supplier_id = Column(String(10), nullable=True)
    scope = Column(String(10), nullable=False)
    result = Column(String(10), nullable=False)
    actual_values = Column(JSON, nullable=True)
    expected_values = Column(JSON, nullable=True)
    message = Column(Text, nullable=True)
    action_taken = Column(String(20), nullable=True)
    evaluated_at = Column(DateTime, nullable=False, server_default=func.now())

    rule = relationship("DynamicRule")
