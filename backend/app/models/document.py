"""SQLAlchemy model: Document — an uploaded file attached to a Case.

The actual bytes live in the deferred `content` column (Postgres bytea). List
queries never load it; only document_service.stream_content() touches it — that
is the single swap point if storage later moves to a volume or S3.

A document can also be linked to a CDD checklist item (case_document_id) or an
Instruction (instruction_id); uploading against a checklist item marks it received.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship, deferred
from sqlalchemy.sql import func
import enum

from app.database import Base


class DocumentCategory(str, enum.Enum):
    CDD = "CDD"
    ACTIVATION = "Activation Document"
    REFERENCE_LETTER = "Reference Letter"
    STRUCTURE_CHART = "Structure Chart"
    CORPORATE_DOCUMENT = "Corporate Document"
    KYC_FORM = "KYC Form"
    FILED_RETURN = "Filed Return / Confirmation"
    RESTORATION = "Restoration"
    CLOSURE = "Closure / Strike Off"
    OTHER = "Other"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    case_document_id = Column(Integer, ForeignKey("case_documents.id", ondelete="SET NULL"), nullable=True)
    instruction_id = Column(Integer, ForeignKey("instructions.id", ondelete="SET NULL"), nullable=True)

    category = Column(String(40), default=DocumentCategory.OTHER.value, nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=False)

    content = deferred(Column(LargeBinary, nullable=False))

    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="documents")
    case_document = relationship("CaseDocument", back_populates="attachments")
    instruction = relationship("Instruction", back_populates="attachments")
    uploaded_by = relationship("User")
