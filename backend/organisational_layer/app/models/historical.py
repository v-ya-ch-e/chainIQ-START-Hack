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


class HistoricalAward(Base):
    __tablename__ = "historical_awards"

    award_id = Column(String(20), primary_key=True)
    request_id = Column(String(20), ForeignKey("requests.request_id"), nullable=False)
    award_date = Column(Date, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    country = Column(String(5), nullable=False)
    business_unit = Column(String(80), nullable=False)
    supplier_id = Column(String(20), ForeignKey("suppliers.supplier_id"), nullable=False)
    supplier_name = Column(String(120), nullable=False)
    total_value = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(5), nullable=False)
    quantity = Column(Numeric(14, 2), nullable=False)
    required_by_date = Column(Date, nullable=False)
    awarded = Column(Boolean, nullable=False)
    award_rank = Column(Integer, nullable=False)
    decision_rationale = Column(Text, nullable=False)
    policy_compliant = Column(Boolean, nullable=False)
    preferred_supplier_used = Column(Boolean, nullable=False)
    escalation_required = Column(Boolean, nullable=False)
    escalated_to = Column(String(80), nullable=True)
    savings_pct = Column(Numeric(6, 2), nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    risk_score_at_award = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)

    request = relationship("Request", back_populates="historical_awards")
    category = relationship("Category", back_populates="historical_awards")
    supplier = relationship("Supplier", back_populates="historical_awards")
