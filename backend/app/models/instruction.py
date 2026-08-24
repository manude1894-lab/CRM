"""SQLAlchemy model: Instruction (per-entity service-request tracker).

Mirrors Triam's real Instruction Tracker (Annexure 7) — the day-to-day log of
service requests against an already-formed entity (COI/COGS issuance, LEI
renewal, AR/ESR/ROM-RBO filings, restoration, closure, notarization, etc.),
as distinct from the Case's one-time onboarding pipeline.
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class InstructionStatus(str, enum.Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    ON_HOLD = "On Hold"


class Instruction(Base):
    __tablename__ = "instructions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    # instruction_type/status stored as plain strings (not DB enums) — same precedent
    # as jurisdiction/service_type on Case (migration 0003): free text is far cheaper
    # to extend than altering a Postgres enum every time Triam adds a new request type.
    instruction_type = Column(String(150), nullable=False)
    status = Column(String(20), default=InstructionStatus.PENDING.value, nullable=False)

    document_shared = Column(Text, nullable=True)

    date_received = Column(Date, nullable=True)
    date_sent_to_vistra = Column(Date, nullable=True)
    date_received_from_vistra = Column(Date, nullable=True)
    date_completed = Column(Date, nullable=True)

    charge_amount = Column(Numeric(12, 2), nullable=True)
    # Free-text invoice reference for quick entry before a formal ledger entry exists.
    # invoice_id (below) is the structured link once the charge is actually invoiced.
    invoice_reference = Column(String(50), nullable=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)

    comments = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="instructions")
    invoice = relationship("Invoice", back_populates="instructions")
