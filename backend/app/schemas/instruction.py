"""Pydantic schemas: Service Request (BRD §15), stored as Instruction."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class _Invoicing(BaseModel):
    """Triam's Invoice Box template (11-11-2026): the charge and payment, each with its currency, and any
    service provider. The invoice itself is linked by Submit, not chosen here (UAT row 58)."""
    charge_amount: Optional[Decimal] = Field(None, ge=0)
    charge_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    amount_paid: Optional[Decimal] = Field(None, ge=0)
    amount_paid_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    payment_received_date: Optional[date] = None
    govt_authority_amount: Optional[Decimal] = Field(None, ge=0)
    govt_authority_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    service_provider_involved: Optional[bool] = None
    service_provider_name: Optional[str] = Field(None, max_length=150)
    service_provider_amount: Optional[Decimal] = Field(None, ge=0)
    service_provider_currency: Optional[str] = Field(None, min_length=3, max_length=3)


class InstructionBase(_Invoicing):
    instruction_type: str = Field(..., min_length=1, max_length=150)
    other_description: Optional[str] = Field(None, max_length=50)
    triam_entity: Optional[str] = Field(None, max_length=60)
    # Checked against the entity's statuses (master list); empty = the entity's first status.
    status: Optional[str] = Field(None, max_length=60)
    date_received: Optional[date] = None
    date_completed: Optional[date] = None
    comments: Optional[str] = None


class InstructionCreate(InstructionBase):
    account_id: Optional[int] = None  # required (the service checks it)


class InstructionUpdate(_Invoicing):
    instruction_type: Optional[str] = Field(None, min_length=1, max_length=150)
    other_description: Optional[str] = Field(None, max_length=50)
    triam_entity: Optional[str] = Field(None, max_length=60)
    status: Optional[str] = Field(None, max_length=60)
    date_received: Optional[date] = None
    date_completed: Optional[date] = None
    comments: Optional[str] = None


class InstructionRead(InstructionBase):
    id: int
    status: str
    charge_currency: str = "AED"
    invoice_id: Optional[int] = None
    submitted_at: Optional[datetime] = None
    submitted_by_id: Optional[int] = None
    cancel_reason: Optional[str] = None
    account_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
