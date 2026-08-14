"""SQLAlchemy models: CDDRecord (1:1 with Case) and CaseDocument checklist."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class DocumentStatus(str, enum.Enum):
    NOT_STARTED = "Not Started"
    SUBMITTED = "Submitted"
    UNDER_REVIEW = "Under Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class AMLRiskRating(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class CDDRecord(Base):
    __tablename__ = "cdd_records"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), unique=True, nullable=False)

    cdd_form_status = Column(SAEnum(DocumentStatus, name="document_status", values_callable=lambda obj: [e.value for e in obj]), default=DocumentStatus.NOT_STARTED, nullable=False)
    kyc_verification_status = Column(SAEnum(DocumentStatus, name="document_status", values_callable=lambda obj: [e.value for e in obj]), default=DocumentStatus.NOT_STARTED, nullable=False)

    aml_risk_rating = Column(String(20), nullable=True)
    screening_reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="cdd_record")
    screening_reviewer = relationship("User", foreign_keys=[screening_reviewer_id])
    documents = relationship("CaseDocument", back_populates="cdd_record", cascade="all, delete-orphan")


class CaseDocument(Base):
    __tablename__ = "case_documents"

    id = Column(Integer, primary_key=True, index=True)
    cdd_record_id = Column(Integer, ForeignKey("cdd_records.id", ondelete="CASCADE"), nullable=False)

    doc_type = Column(String(150), nullable=False)
    received = Column(Boolean, default=False, nullable=False)
    received_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cdd_record = relationship("CDDRecord", back_populates="documents")
