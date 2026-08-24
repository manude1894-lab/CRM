"""SQLAlchemy model: Invoice (running ledger of charges per Case/entity).

Distinct from the Case's own invoice_status/invoice_amount fields, which gate
the one-time onboarding pipeline (CDD Approved -> Raise Invoice -> Invoice Paid
-> Ops Assigned) and are left untouched. This ledger covers ongoing servicing
invoices raised after the entity is Active — matching how Triam's accounting
team (Swathi) actually invoices: one invoice can consolidate charges across
several Instructions (e.g. COI + COGS + notarization billed together).
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class InvoiceLedgerStatus(str, enum.Enum):
    DRAFT = "Draft"
    RAISED = "Raised"
    PAID = "Paid"
    OVERDUE = "Overdue"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    invoice_number = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(12, 2), default=0, nullable=False)
    status = Column(String(20), default=InvoiceLedgerStatus.DRAFT.value, nullable=False)

    raised_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    paid_date = Column(Date, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="invoices")
    instructions = relationship("Instruction", back_populates="invoice")
