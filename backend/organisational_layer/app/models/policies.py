from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# --- Approval Thresholds ---


class ApprovalThreshold(Base):
    __tablename__ = "approval_thresholds"

    threshold_id = Column(String(20), primary_key=True)
    currency = Column(String(5), nullable=False)
    min_amount = Column(Numeric(14, 2), nullable=False)
    max_amount = Column(Numeric(14, 2), nullable=True)
    min_supplier_quotes = Column(Integer, nullable=False)
    policy_note = Column(Text, nullable=True)

    managers = relationship(
        "ApprovalThresholdManager", back_populates="threshold", cascade="all, delete-orphan"
    )
    deviation_approvers = relationship(
        "ApprovalThresholdDeviationApprover",
        back_populates="threshold",
        cascade="all, delete-orphan",
    )


class ApprovalThresholdManager(Base):
    __tablename__ = "approval_threshold_managers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    threshold_id = Column(
        String(20), ForeignKey("approval_thresholds.threshold_id"), nullable=False
    )
    manager_role = Column(String(80), nullable=False)

    threshold = relationship("ApprovalThreshold", back_populates="managers")


class ApprovalThresholdDeviationApprover(Base):
    __tablename__ = "approval_threshold_deviation_approvers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    threshold_id = Column(
        String(20), ForeignKey("approval_thresholds.threshold_id"), nullable=False
    )
    approver_role = Column(String(80), nullable=False)

    threshold = relationship("ApprovalThreshold", back_populates="deviation_approvers")


# --- Preferred Suppliers ---


class PreferredSupplierPolicy(Base):
    __tablename__ = "preferred_suppliers_policy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(
        String(20), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    category_l1 = Column(String(50), nullable=False)
    category_l2 = Column(String(80), nullable=False)
    policy_note = Column(Text, nullable=True)

    supplier = relationship("Supplier", back_populates="preferred_policies")
    region_scopes = relationship(
        "PreferredSupplierRegionScope",
        back_populates="policy",
        cascade="all, delete-orphan",
    )


class PreferredSupplierRegionScope(Base):
    __tablename__ = "preferred_supplier_region_scopes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    preferred_suppliers_policy_id = Column(
        Integer, ForeignKey("preferred_suppliers_policy.id"), nullable=False
    )
    region = Column(String(20), nullable=False)

    policy = relationship("PreferredSupplierPolicy", back_populates="region_scopes")


# --- Restricted Suppliers ---


class RestrictedSupplierPolicy(Base):
    __tablename__ = "restricted_suppliers_policy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(
        String(20), ForeignKey("suppliers.supplier_id"), nullable=False
    )
    category_l1 = Column(String(50), nullable=False)
    category_l2 = Column(String(80), nullable=False)
    restriction_reason = Column(Text, nullable=False)

    supplier = relationship("Supplier", back_populates="restricted_policies")
    scopes = relationship(
        "RestrictedSupplierScope", back_populates="policy", cascade="all, delete-orphan"
    )


class RestrictedSupplierScope(Base):
    __tablename__ = "restricted_supplier_scopes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    restricted_suppliers_policy_id = Column(
        Integer, ForeignKey("restricted_suppliers_policy.id"), nullable=False
    )
    scope_value = Column(String(10), nullable=False)

    policy = relationship("RestrictedSupplierPolicy", back_populates="scopes")


# --- Category Rules ---


class CategoryRule(Base):
    __tablename__ = "category_rules"

    rule_id = Column(String(20), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    rule_type = Column(String(40), nullable=False)
    rule_text = Column(Text, nullable=False)

    category = relationship("Category", back_populates="category_rules")


# --- Geography Rules ---


class GeographyRule(Base):
    __tablename__ = "geography_rules"

    rule_id = Column(String(20), primary_key=True)
    country = Column(String(5), nullable=True)
    region = Column(String(20), nullable=True)
    rule_type = Column(String(40), nullable=True)
    rule_text = Column(Text, nullable=False)

    countries = relationship(
        "GeographyRuleCountry", back_populates="rule", cascade="all, delete-orphan"
    )
    applies_to_categories = relationship(
        "GeographyRuleAppliesToCategory",
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class GeographyRuleCountry(Base):
    __tablename__ = "geography_rule_countries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(20), ForeignKey("geography_rules.rule_id"), nullable=False)
    country_code = Column(String(5), nullable=False)

    rule = relationship("GeographyRule", back_populates="countries")


class GeographyRuleAppliesToCategory(Base):
    __tablename__ = "geography_rule_applies_to_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(20), ForeignKey("geography_rules.rule_id"), nullable=False)
    category_l1 = Column(String(50), nullable=False)

    rule = relationship("GeographyRule", back_populates="applies_to_categories")


# --- Escalation Rules ---


class EscalationRule(Base):
    __tablename__ = "escalation_rules"

    rule_id = Column(String(20), primary_key=True)
    trigger_condition = Column(String(120), nullable=False)
    action = Column(String(120), nullable=False)
    escalate_to = Column(String(80), nullable=False)

    currencies = relationship(
        "EscalationRuleCurrency", back_populates="rule", cascade="all, delete-orphan"
    )


class EscalationRuleCurrency(Base):
    __tablename__ = "escalation_rule_currencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(
        String(20), ForeignKey("escalation_rules.rule_id"), nullable=False
    )
    currency = Column(String(5), nullable=False)

    rule = relationship("EscalationRule", back_populates="currencies")


# --- Rule Definitions + Versions (data-driven rule engine) ---


class RuleDefinition(Base):
    __tablename__ = "rule_definitions"
    __table_args__ = {"extend_existing": True}

    rule_id = Column(String(10), primary_key=True)
    rule_type = Column(String(30), nullable=False)
    rule_name = Column(String(100), nullable=False)
    scope = Column(String(20), nullable=False, default="request")
    evaluation_mode = Column(String(20), nullable=False, default="expression")
    is_skippable = Column(Boolean, nullable=False, default=False)
    source = Column(String(10), nullable=False, default="custom")
    severity = Column(String(10), nullable=False, default="high")
    is_blocking = Column(Boolean, nullable=False, default=True)
    breaks_completeness = Column(Boolean, nullable=False, default=False)
    action_type = Column(String(30), nullable=False, default="escalate")
    action_target = Column(String(120), nullable=True)
    trigger_template = Column(Text, nullable=True)
    action_required = Column(Text, nullable=True)
    field_ref = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=100)
    created_at = Column(DateTime, server_default=func.now(), nullable=True)

    versions = relationship("RuleVersion", back_populates="definition", cascade="all, delete-orphan")


class RuleVersion(Base):
    __tablename__ = "rule_versions"
    __table_args__ = {"extend_existing": True}

    version_id = Column(String(36), primary_key=True)
    rule_id = Column(String(10), ForeignKey("rule_definitions.rule_id"), nullable=False)
    version_num = Column(Integer, nullable=False)
    rule_config = Column(Text, nullable=False)  # JSON stored as TEXT for compatibility
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=True)
    changed_by = Column(String(100), nullable=True)
    change_reason = Column(Text, nullable=True)

    definition = relationship("RuleDefinition", back_populates="versions")
