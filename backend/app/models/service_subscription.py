"""SQLAlchemy model: ServiceSubscription — recurring services an entity is subscribed to
(Monthly Accounting, VAT, Corporate Tax, ...), distinct from the one-off Instruction log.
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ServiceBillingFrequency(str, enum.Enum):
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    ANNUALLY = "Annually"
    ONE_OFF = "One-off"


class ServiceSubscriptionStatus(str, enum.Enum):
    ACTIVE = "Active"
    PAUSED = "Paused"
    CANCELLED = "Cancelled"


class ServiceSubscription(Base):
    __tablename__ = "service_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    service_name = Column(String(150), nullable=False)  # e.g. "Monthly Accounting", "VAT Return Filing"
    billing_frequency = Column(String(20), default=ServiceBillingFrequency.MONTHLY.value, nullable=False)
    fee_amount = Column(Numeric(12, 2), nullable=True)
    status = Column(String(20), default=ServiceSubscriptionStatus.ACTIVE.value, nullable=False)

    start_date = Column(Date, nullable=True)
    next_billing_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case")
