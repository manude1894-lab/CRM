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
    case_id: int


class InvoiceUpdate(BaseModel):
    invoice_number: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    status: Optional[InvoiceLedgerStatus] = None
    raised_date: Optional[date] = None
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    notes: Optional[str] = None


class InvoiceRead(InvoiceBase):
    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
