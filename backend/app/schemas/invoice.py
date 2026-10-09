"""Pydantic schemas: Invoice (running ledger of charges per Case)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.invoice import InvoiceLedgerStatus


class InvoiceBase(BaseModel):
    invoice_number: Optional[str] = None
    description: Optional[str] = None
    amount: Decimal = Field(0, ge=0)
    status: InvoiceLedgerStatus = InvoiceLedgerStatus.DRAFT
    raised_date: Optional[date] = None
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    notes: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    account_id: Optional[int] = None
    case_id: Optional[int] = None
    currency: str = "AED"


class InvoiceRequest(BaseModel):
    """Triam mark-up §16 — the RM / Sales instruction to the Accounts Department."""
    account_id: int
    case_id: Optional[int] = None
    instruction_id: Optional[int] = None  # the service request being invoiced
    description: str = Field(..., min_length=2, max_length=500)
    amount: Decimal = Field(..., ge=0)
    currency: str = "AED"
    notes: Optional[str] = Field(None, max_length=2000)


class InvoiceRaise(BaseModel):
    """Accounts records the invoice it has issued."""
    invoice_number: str = Field(..., min_length=1, max_length=50)
    invoice_date: date
    currency: str = "AED"
    amount: Decimal = Field(..., ge=0)
    due_date: Optional[date] = None


class InvoicePaid(BaseModel):
    paid_date: Optional[date] = None


class InvoiceUpdate(BaseModel):
    invoice_number: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    status: Optional[InvoiceLedgerStatus] = None
    raised_date: Optional[date] = None
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    notes: Optional[str] = None
    currency: Optional[str] = None


class InvoiceRead(InvoiceBase):
    id: int
    account_id: Optional[int] = None
    case_id: Optional[int] = None
    currency: str = "AED"
    requested_by_id: Optional[int] = None
    requested_by_name: Optional[str] = None
    requested_at: Optional[datetime] = None
    raised_by_id: Optional[int] = None
    raised_by_name: Optional[str] = None
    company_name: Optional[str] = None
    client_id: Optional[str] = None
    attachment_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


def invoice_read(inv, db=None) -> "InvoiceRead":
    out = InvoiceRead.model_validate(inv)
    out.requested_by_name = inv.requested_by.name if inv.requested_by else None
    out.raised_by_name = inv.raised_by.name if inv.raised_by else None
    acc = inv.account
    if acc is not None:
        out.company_name, out.client_id = acc.company_name, acc.client_id or acc.temp_id
    elif inv.case is not None:
        out.company_name = inv.case.company_name
    if db is not None:
        from app.models import Document
        out.attachment_count = db.query(Document).filter(Document.invoice_id == inv.id).count()
    return out
