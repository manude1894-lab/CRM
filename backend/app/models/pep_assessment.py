"""SQLAlchemy model: PEPAssessment — a standalone PEP / EDD assessment for a party.

Many-per-case, optionally linked to a director / shareholder / UBO (same pattern as
AMLRiskAssessment). The EDD artifact the Process Manual calls for when a party is a
politically exposed person: PEP type, position, family & associates, the enhanced
due-diligence measures applied, and senior-management approval.
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class PEPType(str, enum.Enum):
    DOMESTIC = "Domestic PEP"
    FOREIGN = "Foreign PEP"
    INTERNATIONAL_ORG = "International Org PEP"
    FAMILY_MEMBER = "Family Member"
    CLOSE_ASSOCIATE = "Close Associate"


class PEPRiskConclusion(str, enum.Enum):
    PROCEED = "Proceed"
    PROCEED_WITH_EDD = "Proceed with EDD"
    DECLINE = "Decline"


class PEPAssessment(Base):
    __tablename__ = "pep_assessments"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    director_id = Column(Integer, ForeignKey("directors.id", ondelete="SET NULL"), nullable=True)
    shareholder_id = Column(Integer, ForeignKey("shareholders.id", ondelete="SET NULL"), nullable=True)
    ubo_id = Column(Integer, ForeignKey("ubos.id", ondelete="SET NULL"), nullable=True)

    subject_name = Column(String(255), nullable=False)

    pep_type = Column(String(40), nullable=True)
    position = Column(String(255), nullable=True)
    pep_jurisdiction = Column(String(120), nullable=True)
    since_date = Column(Date, nullable=True)
    still_in_office = Column(Boolean, default=False, nullable=False)

    family_and_associates = Column(Text, nullable=True)
    source_of_wealth_scrutiny = Column(Text, nullable=True)
    source_of_funds_scrutiny = Column(Text, nullable=True)
    edd_measures = Column(Text, nullable=True)
    adverse_media_findings = Column(Text, nullable=True)

    risk_conclusion = Column(String(30), nullable=True)  # Proceed / Proceed with EDD / Decline
    senior_management_approved = Column(Boolean, default=False, nullable=False)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    assessed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assessment_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case")
    director = relationship("Director")
    shareholder = relationship("Shareholder")
    ubo = relationship("UBO")
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    assessed_by = relationship("User", foreign_keys=[assessed_by_id])
