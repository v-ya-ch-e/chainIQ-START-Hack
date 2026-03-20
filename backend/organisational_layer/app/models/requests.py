import uuid as _uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Request(Base):
    __tablename__ = "requests"

    request_id = Column(String(20), primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(_uuid.uuid4()))
    created_at = Column(DateTime, nullable=False)
    request_channel = Column(String(20), nullable=False)
    request_language = Column(String(5), nullable=False)
    business_unit = Column(String(80), nullable=False)
    country = Column(String(5), nullable=False)
    site = Column(String(80), nullable=False)
    requester_id = Column(String(20), nullable=False)
    requester_role = Column(String(80), nullable=True)
    submitted_for_id = Column(String(20), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    title = Column(String(255), nullable=False)
    request_text = Column(Text, nullable=False)
    currency = Column(String(5), nullable=False)
    budget_amount = Column(Numeric(14, 2), nullable=True)
    quantity = Column(Numeric(14, 2), nullable=True)
    unit_of_measure = Column(String(30), nullable=False)
    required_by_date = Column(Date, nullable=False)
    preferred_supplier_mentioned = Column(String(120), nullable=True)
    incumbent_supplier = Column(String(120), nullable=True)
    contract_type_requested = Column(String(40), nullable=False)
    data_residency_constraint = Column(Boolean, nullable=False)
    esg_requirement = Column(Boolean, nullable=False)
    status = Column(String(20), nullable=False)

    category = relationship("Category", back_populates="requests")
    delivery_countries = relationship(
        "RequestDeliveryCountry", back_populates="request", cascade="all, delete-orphan"
    )
    scenario_tags = relationship(
        "RequestScenarioTag", back_populates="request", cascade="all, delete-orphan"
    )
    historical_awards = relationship("HistoricalAward", back_populates="request")


class RequestDeliveryCountry(Base):
    __tablename__ = "request_delivery_countries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(20), ForeignKey("requests.request_id"), nullable=False)
    country_code = Column(String(5), nullable=False)

    request = relationship("Request", back_populates="delivery_countries")


class RequestScenarioTag(Base):
    __tablename__ = "request_scenario_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(20), ForeignKey("requests.request_id"), nullable=False)
    tag = Column(String(30), nullable=False)

    request = relationship("Request", back_populates="scenario_tags")
