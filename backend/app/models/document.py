"""SQLAlchemy model: Document — a file (or link) in the client's folder (BRD §14).

The actual bytes live in the deferred `content` column (Postgres bytea). List
queries never load it; only document_service.stream_content() touches it — that
is the single swap point if storage later moves to a volume or S3.

A document can also belong to a service request (instruction_id) or an invoice (invoice_id).
Categories come from the document_category master list.
"""
from sqlalchemy import Column, Integer, String, DateTime, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship, deferred
from sqlalchemy.sql import func
import enum

from app.database import Base


class DocumentCategory(str, enum.Enum):
    OTHER = "Other"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    instruction_id = Column(Integer, ForeignKey("instructions.id", ondelete="SET NULL"), nullable=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True, index=True)  # pricing approval / invoice file
    party_id = Column(Integer, ForeignKey("account_parties.id", ondelete="SET NULL"), nullable=True, index=True)  # the UBO / director / signatory

    category = Column(String(40), default=DocumentCategory.OTHER.value, nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=False)

    content = deferred(Column(LargeBinary, nullable=True))  # empty for link documents
    link_url = Column(String(1000), nullable=True)  # BRD §14: a link (e.g. SharePoint) instead of a file

    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(String(500), nullable=True)

    # Never deleted (Triam: no delete in the CRM) — a removal is recorded here and the record is kept.
    removed_at = Column(DateTime(timezone=True), nullable=True)
    removed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    removed_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account", back_populates="documents")
    instruction = relationship("Instruction", back_populates="attachments")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])
