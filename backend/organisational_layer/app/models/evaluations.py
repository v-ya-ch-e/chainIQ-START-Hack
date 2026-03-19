"""ORM models for rule versioning and evaluation traceability."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


class RuleDefinition(Base):
    """Evaluable rule (HR-*, PC-*, ER-*). Immutable definition."""

    __tablename__ = "rule_definitions"
    __table_args__ = {"extend_existing": True}

    rule_id = Column(String(10), primary_key=True)
    rule_type = Column(String(20), nullable=False)
    rule_name = Column(String(100), nullable=False)
    is_skippable = Column(Boolean, nullable=False, default=False)
    source = Column(String(10), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)

    versions = relationship(
        "RuleVersion",
        back_populates="rule",
        order_by="RuleVersion.version_num",
    )


class RuleVersion(Base):
    """Versioned rule config. valid_to=NULL = currently active."""

    __tablename__ = "rule_versions"

    version_id = Column(String(36), primary_key=True)
    rule_id = Column(String(10), ForeignKey("rule_definitions.rule_id"), nullable=False)
    version_num = Column(Integer, nullable=False)
    rule_config = Column(JSON, nullable=False)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=True)
    changed_by = Column(String(100), nullable=True)
    change_reason = Column(Text, nullable=True)

    rule = relationship("RuleDefinition", back_populates="versions")


class EvaluationRun(Base):
    """One evaluation run for a request."""

    __tablename__ = "evaluation_runs"

    run_id = Column(String(36), primary_key=True)
    request_id = Column(String(20), ForeignKey("requests.request_id"), nullable=False)
    triggered_by = Column(String(20), nullable=False)
    agent_version = Column(String(30), nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)
    final_outcome = Column(String(20), nullable=True)
    output_snapshot = Column(JSON, nullable=True)
    parent_run_id = Column(String(36), nullable=True)
    trigger_reason = Column(String(100), nullable=True)

    hard_rule_checks = relationship(
        "HardRuleCheck",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    policy_checks = relationship(
        "PolicyCheck",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    supplier_evaluations = relationship(
        "SupplierEvaluation",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class HardRuleCheck(Base):
    """Per-supplier hard rule check. Links to rule_version for traceability."""

    __tablename__ = "hard_rule_checks"

    check_id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("evaluation_runs.run_id"), nullable=False)
    rule_id = Column(String(10), ForeignKey("rule_definitions.rule_id"), nullable=False)
    version_id = Column(String(36), ForeignKey("rule_versions.version_id"), nullable=False)
    supplier_id = Column(String(10), ForeignKey("suppliers.supplier_id"), nullable=True)
    skipped = Column(Boolean, nullable=False, default=False)
    skip_reason = Column(String(200), nullable=True)
    result = Column(String(10), nullable=True)  # passed, failed
    actual_value = Column(JSON, nullable=True)
    threshold = Column(JSON, nullable=True)
    checked_at = Column(DateTime, nullable=False)

    run = relationship("EvaluationRun", back_populates="hard_rule_checks")


class PolicyCheck(Base):
    """Per-supplier policy check. Links to rule_version for traceability."""

    __tablename__ = "policy_checks"

    check_id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("evaluation_runs.run_id"), nullable=False)
    rule_id = Column(String(10), ForeignKey("rule_definitions.rule_id"), nullable=False)
    version_id = Column(String(36), ForeignKey("rule_versions.version_id"), nullable=False)
    supplier_id = Column(String(10), ForeignKey("suppliers.supplier_id"), nullable=True)
    result = Column(String(10), nullable=False)  # passed, warned, failed
    evidence = Column(JSON, nullable=False)
    override_by = Column(String(100), nullable=True)
    override_at = Column(DateTime, nullable=True)
    override_reason = Column(Text, nullable=True)
    checked_at = Column(DateTime, nullable=False)

    run = relationship("EvaluationRun", back_populates="policy_checks")


class SupplierEvaluation(Base):
    """Aggregated evaluation result per supplier per run."""

    __tablename__ = "supplier_evaluations"

    eval_id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("evaluation_runs.run_id"), nullable=False)
    supplier_id = Column(String(10), ForeignKey("suppliers.supplier_id"), nullable=False)
    rank = Column(Integer, nullable=True)
    total_score = Column(Numeric(5, 2), nullable=True)
    price_score = Column(Numeric(5, 2), nullable=True)
    quality_score = Column(Numeric(5, 2), nullable=True)
    esg_score = Column(Numeric(5, 2), nullable=True)
    risk_score = Column(Numeric(5, 2), nullable=True)
    hard_checks_total = Column(Integer, nullable=False, default=0)
    hard_checks_passed = Column(Integer, nullable=False, default=0)
    hard_checks_skipped = Column(Integer, nullable=False, default=0)
    hard_checks_failed = Column(Integer, nullable=False, default=0)
    policy_checks_total = Column(Integer, nullable=False, default=0)
    policy_checks_passed = Column(Integer, nullable=False, default=0)
    policy_checks_warned = Column(Integer, nullable=False, default=0)
    policy_checks_failed = Column(Integer, nullable=False, default=0)
    excluded = Column(Boolean, nullable=False, default=False)
    exclusion_rule_id = Column(String(10), ForeignKey("rule_definitions.rule_id"), nullable=True)
    exclusion_reason = Column(Text, nullable=True)
    pricing_snapshot = Column(JSON, nullable=True)
    evaluated_at = Column(DateTime, nullable=False)

    run = relationship("EvaluationRun", back_populates="supplier_evaluations")


class RuleChangeLog(Base):
    """Audit log for rule version changes."""

    __tablename__ = "rule_change_logs"

    log_id = Column(String(36), primary_key=True)
    rule_id = Column(String(10), ForeignKey("rule_definitions.rule_id"), nullable=False)
    old_version_id = Column(String(36), nullable=True)
    new_version_id = Column(String(36), ForeignKey("rule_versions.version_id"), nullable=False)
    changed_at = Column(DateTime, nullable=False)
    changed_by = Column(String(100), nullable=False)
    change_reason = Column(Text, nullable=True)
    affected_runs = Column(JSON, nullable=True)


class Escalation(Base):
    """Escalation entity from an evaluation run. Operational record."""

    __tablename__ = "escalations"

    escalation_id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("evaluation_runs.run_id"), nullable=False)
    rule_id = Column(String(10), ForeignKey("rule_definitions.rule_id"), nullable=False)
    version_id = Column(String(36), ForeignKey("rule_versions.version_id"), nullable=False)
    trigger_table = Column(String(30), nullable=False)
    trigger_check_id = Column(String(36), nullable=False)
    escalation_target = Column(String(100), nullable=False)
    escalation_reason = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=False)
    event_dispatched_at = Column(DateTime, nullable=True)
    event_payload = Column(JSON, nullable=True)
    event_status = Column(String(20), nullable=False, default="pending")
    status = Column(String(20), nullable=False, default="open")
    resolved_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class EscalationLog(Base):
    """Audit trail for changes to escalations."""

    __tablename__ = "escalation_logs"

    log_id = Column(String(36), primary_key=True)
    escalation_id = Column(String(36), ForeignKey("escalations.escalation_id"), nullable=False)
    changed_at = Column(DateTime, nullable=False)
    changed_by = Column(String(100), nullable=False)
    change_type = Column(String(30), nullable=False)
    field_changed = Column(String(50), nullable=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    note = Column(Text, nullable=True)


class PolicyChangeLog(Base):
    """Audit trail for policy-related changes (e.g. when user changes escalation)."""

    __tablename__ = "policy_change_logs"

    log_id = Column(String(36), primary_key=True)
    escalation_id = Column(String(36), ForeignKey("escalations.escalation_id"), nullable=False)
    changed_at = Column(DateTime, nullable=False)
    changed_by = Column(String(100), nullable=False)
    change_type = Column(String(30), nullable=False)
    policy_rule_id = Column(String(10), nullable=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    note = Column(Text, nullable=True)


class EvaluationRunLog(Base):
    """Audit trail for evaluation run status/outcome changes."""

    __tablename__ = "evaluation_run_logs"

    log_id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("evaluation_runs.run_id"), nullable=False)
    changed_at = Column(DateTime, nullable=False)
    changed_by = Column(String(100), nullable=False)
    change_type = Column(String(30), nullable=False)
    old_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=True)
    old_outcome = Column(String(20), nullable=True)
    new_outcome = Column(String(20), nullable=True)
    note = Column(Text, nullable=True)


class PolicyCheckLog(Base):
    """Audit trail for human overrides on policy checks."""

    __tablename__ = "policy_check_logs"

    log_id = Column(String(36), primary_key=True)
    check_id = Column(String(36), ForeignKey("policy_checks.check_id"), nullable=False)
    run_id = Column(String(36), ForeignKey("evaluation_runs.run_id"), nullable=False)
    changed_at = Column(DateTime, nullable=False)
    changed_by = Column(String(100), nullable=False)
    change_type = Column(String(30), nullable=False)
    old_result = Column(String(10), nullable=True)
    new_result = Column(String(10), nullable=True)
    old_evidence = Column(JSON, nullable=True)
    new_evidence = Column(JSON, nullable=True)
    override_reason = Column(Text, nullable=True)
