"""Pydantic schemas: Instruction (per-entity service-request tracker)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

class InstructionBase(BaseModel):
    instruction_type: str = Field(..., min_length=1, max_length=150)
    other_description: Optional[str] = Field(None, max_length=50)
    triam_entity: Optional[str] = Field(None, max_length=20)
    # Checked against the entity's statuses (master list); empty = the entity's first status.
    status: Optional[str] = Field(None, max_length=40)
    document_shared: Optional[str] = None
    date_received: Optional[date] = None
    date_sent_to_vistra: Optional[date] = None
    date_received_from_vistra: Optional[date] = None
    date_completed: Optional[date] = None
    cost_amount: Optional[Decimal] = Field(None, ge=0)
    charge_amount: Optional[Decimal] = Field(None, ge=0)
    invoice_reference: Optional[str] = None
    invoice_id: Optional[int] = None
    comments: Optional[str] = None


class InstructionCreate(InstructionBase):
    # BRD §17 — a service request belongs to a client; the BVI case is optional.
    account_id: Optional[int] = None
    case_id: Optional[int] = None


class InstructionUpdate(BaseModel):
    instruction_type: Optional[str] = Field(None, min_length=1, max_length=150)
    other_description: Optional[str] = Field(None, max_length=50)
    triam_entity: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, max_length=40)
    document_shared: Optional[str] = None
    date_received: Optional[date] = None
    date_sent_to_vistra: Optional[date] = None
    date_received_from_vistra: Optional[date] = None
    date_completed: Optional[date] = None
    cost_amount: Optional[Decimal] = Field(None, ge=0)
    charge_amount: Optional[Decimal] = Field(None, ge=0)
    invoice_reference: Optional[str] = None
    invoice_id: Optional[int] = None
    comments: Optional[str] = None


class InstructionRead(InstructionBase):
    id: int
    status: str
    cancel_reason: Optional[str] = None
    case_id: Optional[int] = None
    account_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
