"""SQLAlchemy model: Instruction — a Service Request on an approved client (BRD §15).

Request types and statuses are per Triam entity, from Triam's "Service Requests - Triam Entities"
list (service_request_type / service_request_status master lists).
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class InstructionStatus(str, enum.Enum):
    """Statuses the code relies on. The full list is Triam's, per entity, in the
    service_request_status master list (Received, Applied for service ... / Not started ...)."""
    COMPLETED = "Completed"  # raises the invoice request to Accounts
    ON_HOLD = "On Hold"
    CANCELLED = "Dropped"    # set only by Cancel, with a reason


class Instruction(Base):
    __tablename__ = "instructions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # instruction_type/status stored as plain strings (not DB enums): Triam maintains the lists
    # as master data, so a new type or status needs no schema change.
    instruction_type = Column(String(150), nullable=False)
    other_description = Column(String(50), nullable=True)  # when the type is "Other"
    # The Triam entity handling the request; decides the request types and statuses offered.
    triam_entity = Column(String(20), nullable=True)
    status = Column(String(40), default="Received", nullable=False)

    date_received = Column(Date, nullable=True)
    date_completed = Column(Date, nullable=True)

    # What the client is charged; on completion it becomes an invoice instruction to Accounts (BRD §16).
    charge_amount = Column(Numeric(12, 2), nullable=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)

    comments = Column(Text, nullable=True)

    cancel_reason = Column(String(500), nullable=True)  # set when cancelled — records are never deleted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account = relationship("Account")
    invoice = relationship("Invoice", back_populates="instructions")
    attachments = relationship("Document", back_populates="instruction")
