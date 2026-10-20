"""Pydantic schemas: Service Request (BRD §15), stored as Instruction."""
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
    date_received: Optional[date] = None
    date_completed: Optional[date] = None
    charge_amount: Optional[Decimal] = Field(None, ge=0)
    invoice_id: Optional[int] = None
    comments: Optional[str] = None


class InstructionCreate(InstructionBase):
    account_id: Optional[int] = None  # required (the service checks it)


class InstructionUpdate(BaseModel):
    instruction_type: Optional[str] = Field(None, min_length=1, max_length=150)
    other_description: Optional[str] = Field(None, max_length=50)
    triam_entity: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, max_length=40)
    date_received: Optional[date] = None
    date_completed: Optional[date] = None
    charge_amount: Optional[Decimal] = Field(None, ge=0)
    invoice_id: Optional[int] = None
    comments: Optional[str] = None


class InstructionRead(InstructionBase):
    id: int
    status: str
    cancel_reason: Optional[str] = None
    account_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
