"""Pydantic schemas: Case."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.case import CaseStage, CaseStatus, CaseSource, InvoiceStatus


class CaseBase(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    source: CaseSource = CaseSource.OTHER
    stage: CaseStage = CaseStage.NEW_INQUIRY
    status: CaseStatus = CaseStatus.ACTIVE
    invoice_amount: float = Field(0, ge=0)
    license_received_date: Optional[date] = None
    license_expiry_date: Optional[date] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    account_id: Optional[int] = None
    rm_id: Optional[int] = None
    ops_owner_id: Optional[int] = None


class CaseCreate(CaseBase):
    pass


class CaseUpdate(BaseModel):
    company_name: Optional[str] = None
    source: Optional[CaseSource] = None
    status: Optional[CaseStatus] = None
    invoice_amount: Optional[float] = Field(None, ge=0)
    license_received_date: Optional[date] = None
    license_expiry_date: Optional[date] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    account_id: Optional[int] = None
    rm_id: Optional[int] = None
    ops_owner_id: Optional[int] = None


class CaseStageChangeRequest(BaseModel):
    stage: CaseStage


class InvoiceRaiseRequest(BaseModel):
    amount: float = Field(0, ge=0)


class CaseRead(CaseBase):
    id: int
    case_uid: str
    invoice_status: InvoiceStatus
    invoice_raised_date: Optional[date] = None
    invoice_paid_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
