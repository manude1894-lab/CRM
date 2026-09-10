"""SQLAlchemy model: ComplianceSchedule (1:1 with Case, created on License Received).

Slots, anchored to the BVI calendar (see case_service._create_compliance_schedule):
  - renewal      : Annual Licence Fee — the incorporation anniversary
  - esr_filing   : Economic Substance Regulation filing — annual (per Vistra portal)
  - ar_filing    : Annual Return — fixed 30 September each year
  - bo_filing    : ROM/RBO beneficial-ownership filing — event-driven, 30 days after
                   any ownership change (set by compliance_service.flag_bo_filing_due,
                   cleared rather than rolled)
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
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

    esr_filing_due_date = Column(Date, nullable=True)
    esr_filing_last_completed_date = Column(Date, nullable=True)
    esr_filing_cadence_months = Column(Integer, default=12, nullable=False)

    ar_filing_due_date = Column(Date, nullable=True)
    ar_filing_last_completed_date = Column(Date, nullable=True)
    ar_filing_cadence_months = Column(Integer, default=12, nullable=False)
    # Light AR sub-workflow: Not Started / Data Prepared / Submitted to Vistra / Filed / Confirmed
    ar_filing_status = Column(String(30), default="Not Started", nullable=False)
    ar_reference_year = Column(Integer, nullable=True)

    bo_filing_due_date = Column(Date, nullable=True)
    bo_filing_last_completed_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="compliance_schedule")
