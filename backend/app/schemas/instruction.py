"""Pydantic schemas: Instruction (per-entity service-request tracker)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.instruction import InstructionStatus


class InstructionBase(BaseModel):
    instruction_type: str = Field(..., min_length=1, max_length=150)
    status: InstructionStatus = InstructionStatus.PENDING
    document_shared: Optional[str] = None
    date_received: Optional[date] = None
    date_sent_to_vistra: Optional[date] = None
    date_received_from_vistra: Optional[date] = None
    date_completed: Optional[date] = None
    charge_amount: Optional[Decimal] = Field(None, ge=0)
    invoice_reference: Optional[str] = None
    invoice_id: Optional[int] = None
    comments: Optional[str] = None


class InstructionCreate(InstructionBase):
    case_id: int


class InstructionUpdate(BaseModel):
    instruction_type: Optional[str] = Field(None, min_length=1, max_length=150)
    status: Optional[InstructionStatus] = None
    document_shared: Optional[str] = None
    date_received: Optional[date] = None
    date_sent_to_vistra: Optional[date] = None
    date_received_from_vistra: Optional[date] = None
    date_completed: Optional[date] = None
    charge_amount: Optional[Decimal] = Field(None, ge=0)
    invoice_reference: Optional[str] = None
    invoice_id: Optional[int] = None
    comments: Optional[str] = None


class InstructionRead(InstructionBase):
    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
