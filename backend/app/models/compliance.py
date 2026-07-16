"""SQLAlchemy model: ComplianceSchedule (1:1 with Case, created on License Received)."""
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ComplianceSchedule(Base):
    __tablename__ = "compliance_schedules"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), unique=True, nullable=False)

    renewal_due_date = Column(Date, nullable=True)
    renewal_last_completed_date = Column(Date, nullable=True)
    renewal_cadence_months = Column(Integer, default=12, nullable=False)

    compliance_filing_due_date = Column(Date, nullable=True)
    compliance_filing_last_completed_date = Column(Date, nullable=True)
    compliance_filing_cadence_months = Column(Integer, default=12, nullable=False)

    tax_filing_due_date = Column(Date, nullable=True)
    tax_filing_last_completed_date = Column(Date, nullable=True)
    tax_filing_cadence_months = Column(Integer, default=12, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="compliance_schedule")
