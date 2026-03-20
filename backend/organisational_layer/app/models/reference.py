import uuid as _uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_l1 = Column(String(50), nullable=False)
    category_l2 = Column(String(80), nullable=False)
    category_description = Column(String(255), nullable=False)
    typical_unit = Column(String(30), nullable=False)
    pricing_model = Column(String(30), nullable=False)

    supplier_categories = relationship("SupplierCategory", back_populates="category")
    pricing_tiers = relationship("PricingTier", back_populates="category")
    requests = relationship("Request", back_populates="category")
    historical_awards = relationship("HistoricalAward", back_populates="category")
    category_rules = relationship("CategoryRule", back_populates="category")


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(String(20), primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(_uuid.uuid4()))
    supplier_name = Column(String(120), nullable=False)
    country_hq = Column(String(5), nullable=False)
    currency = Column(String(5), nullable=False)
    contract_status = Column(String(20), nullable=False)
    capacity_per_month = Column(Integer, nullable=False)

    categories = relationship("SupplierCategory", back_populates="supplier")
    service_regions = relationship("SupplierServiceRegion", back_populates="supplier")
    pricing_tiers = relationship("PricingTier", back_populates="supplier")
    historical_awards = relationship("HistoricalAward", back_populates="supplier")
    preferred_policies = relationship("PreferredSupplierPolicy", back_populates="supplier")
    restricted_policies = relationship("RestrictedSupplierPolicy", back_populates="supplier")


class SupplierCategory(Base):
    __tablename__ = "supplier_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(String(20), ForeignKey("suppliers.supplier_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    pricing_model = Column(String(30), nullable=False)
    quality_score = Column(Integer, nullable=False)
    risk_score = Column(Integer, nullable=False)
    esg_score = Column(Integer, nullable=False)
    preferred_supplier = Column(Boolean, nullable=False)
    is_restricted = Column(Boolean, nullable=False)
    restriction_reason = Column(Text, nullable=True)
    data_residency_supported = Column(Boolean, nullable=False)
    notes = Column(Text, nullable=True)

    supplier = relationship("Supplier", back_populates="categories")
    category = relationship("Category", back_populates="supplier_categories")


class SupplierServiceRegion(Base):
    __tablename__ = "supplier_service_regions"

    supplier_id = Column(
        String(20), ForeignKey("suppliers.supplier_id"), primary_key=True
    )
    country_code = Column(String(5), primary_key=True)

    supplier = relationship("Supplier", back_populates="service_regions")


class PricingTier(Base):
    __tablename__ = "pricing_tiers"

    pricing_id = Column(String(20), primary_key=True)
    supplier_id = Column(String(20), ForeignKey("suppliers.supplier_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    region = Column(String(20), nullable=False)
    currency = Column(String(5), nullable=False)
    pricing_model = Column(String(30), nullable=False)
    min_quantity = Column(Integer, nullable=False)
    max_quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 4), nullable=False)
    moq = Column(Integer, nullable=False)
    standard_lead_time_days = Column(Integer, nullable=False)
    expedited_lead_time_days = Column(Integer, nullable=False)
    expedited_unit_price = Column(Numeric(12, 4), nullable=False)
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)

    supplier = relationship("Supplier", back_populates="pricing_tiers")
    category = relationship("Category", back_populates="pricing_tiers")
