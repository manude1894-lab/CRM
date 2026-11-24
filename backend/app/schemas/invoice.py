"""Pydantic schemas: Invoice module (BRD §16)."""
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
    account_id: int
    currency: str = "AED"


class InvoiceRequest(BaseModel):
    """The RM / Sales instruction to the Accounts Department."""
    account_id: int
    instruction_id: Optional[int] = None  # the service request being invoiced
    # Triam 23-11-2026: an invoice for onboarding services is the client's one onboarding invoice (as on the client
    # form); it may be requested before the client is approved. Ignored when a service request is given.
    onboarding: bool = False
    description: str = Field(..., min_length=2, max_length=500)
    amount: Decimal = Field(..., ge=0)
    currency: str = "AED"
    notes: Optional[str] = Field(None, max_length=2000)
    submit: bool = True  # False keeps it as the requester's draft; Accounts is not told yet


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
    account_id: int
    currency: str = "AED"
    requested_by_id: Optional[int] = None
    requested_by_name: Optional[str] = None
    requested_at: Optional[datetime] = None
    raised_by_id: Optional[int] = None
    raised_by_name: Optional[str] = None
    company_name: Optional[str] = None
    client_id: Optional[str] = None
    attachment_count: int = 0
    # Triam UAT 19-11-2026: Onboarding / Service Request, and an onboarding invoice's payouts.
    kind: Optional[str] = None
    govt_authority_amount: Optional[Decimal] = None
    govt_authority_currency: Optional[str] = None
    introducer_involved: Optional[bool] = None
    introducer_amount: Optional[Decimal] = None
    introducer_currency: Optional[str] = None
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
    if db is not None:
        from app.models import Document
        out.attachment_count = db.query(Document).filter(Document.invoice_id == inv.id, Document.removed_at.is_(None)).count()
    return out


class OnboardingInvoiceSave(BaseModel):
    """The client form's Invoice for Onboarding Services (Triam UAT 19-11-2026). submit=True sends it to Accounts."""
    wanted: Optional[bool] = None  # "Do you want an invoice raised for onboarding services?"
    client_amount: Optional[Decimal] = Field(None, ge=0)  # amount payable by the client
    client_currency: str = "AED"
    govt_authority_amount: Optional[Decimal] = Field(None, ge=0)  # amount payable to the Regn / Govt Authority
    govt_authority_currency: str = "AED"
    introducer_involved: Optional[bool] = None  # is an introducer / referrer involved?
    introducer_amount: Optional[Decimal] = Field(None, ge=0)
    introducer_currency: str = "AED"
    comments: Optional[str] = Field(None, max_length=2000)
    submit: bool = False


class OnboardingInvoiceState(BaseModel):
    wanted: Optional[bool] = None
    invoice: Optional[InvoiceRead] = None  # the current onboarding invoice (not cancelled), if any
    editable: bool = False  # the RM may still change it (not yet with Accounts)
    can_submit: bool = False
    why_not: Optional[str] = None  # why it can't be submitted yet
    currencies: list[str] = []
