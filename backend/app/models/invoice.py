"""SQLAlchemy model: Invoice (BRD §16) — for a new client's onboarding or for service requests.

RM / Sales request the invoice (instruction to Accounts, pricing approvals attached); Accounts record
the Invoice No, Date, Currency and Amount and attach the invoice file. One invoice can cover several
service requests.
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class InvoiceLedgerStatus(str, enum.Enum):
    REQUESTED = "Requested"  # BRD §16: RM / Sales instruction to Accounts
    DRAFT = "Draft"
    RAISED = "Raised"
    PAID = "Paid"
    OVERDUE = "Overdue"
    CANCELLED = "Cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    currency = Column(String(3), default="AED", server_default="AED", nullable=False)
    requested_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=True)
    raised_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    invoice_number = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(12, 2), default=0, nullable=False)
    status = Column(String(20), default=InvoiceLedgerStatus.DRAFT.value, nullable=False)

    raised_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    paid_date = Column(Date, nullable=True)

    notes = Column(Text, nullable=True)

    cancel_reason = Column(String(500), nullable=True)  # set when cancelled — records are never deleted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account = relationship("Account")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    raised_by = relationship("User", foreign_keys=[raised_by_id])
    instructions = relationship("Instruction", back_populates="invoice")
