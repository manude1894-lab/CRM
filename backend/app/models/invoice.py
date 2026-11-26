"""SQLAlchemy model: Invoice (BRD §16) — for a new client's onboarding or for service requests.

RM / Sales request the invoice (instruction to Accounts, pricing approvals attached); Accounts record
the Invoice No, Date, Currency and Amount and attach the invoice file. One invoice can cover several
service requests.
"""
from sqlalchemy import Boolean, Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


ONBOARDING, SERVICE_REQUEST = "Onboarding", "Service Request"  # Invoice.kind


class InvoiceLedgerStatus(str, enum.Enum):
    # Triam UAT 25-11-2026 row 182: an onboarding invoice for a client not yet approved waits for the CO first.
    WITH_COMPLIANCE = "With Compliance"
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

    # Triam UAT 19-11-2026: what the invoice is for, "Onboarding" (the client form's Invoice for Onboarding Services)
    # or "Service Request"; and, for an onboarding invoice, what Triam pays out of it.
    kind = Column(String(20), nullable=True, index=True)
    govt_authority_amount = Column(Numeric(12, 2), nullable=True)
    govt_authority_currency = Column(String(3), nullable=True)
    introducer_involved = Column(Boolean, nullable=True)
    introducer_amount = Column(Numeric(12, 2), nullable=True)
    introducer_currency = Column(String(3), nullable=True)

    cancel_reason = Column(String(500), nullable=True)  # set when cancelled — records are never deleted
    # Triam UAT 25-11-2026 row 182: the CO's decision on an onboarding invoice request before approval.
    co_decided_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    co_decided_at = Column(DateTime(timezone=True), nullable=True)
    co_decision = Column(String(20), nullable=True)  # Approved / Returned
    co_comment = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account = relationship("Account")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    raised_by = relationship("User", foreign_keys=[raised_by_id])
    co_decided_by = relationship("User", foreign_keys=[co_decided_by_id])
    instructions = relationship("Instruction", back_populates="invoice")
