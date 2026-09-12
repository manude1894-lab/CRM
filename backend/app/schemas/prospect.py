"""Pydantic schemas: Prospect (pre-Case proposal tracking)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.prospect import ProspectStatus


class ProspectBase(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    source: Optional[str] = None
    owner_id: Optional[int] = None
    status: ProspectStatus = ProspectStatus.NEW
    proposal_sent_date: Optional[date] = None
    proposal_amount: Optional[Decimal] = Field(None, ge=0)
    expected_close_date: Optional[date] = None
    next_follow_up_date: Optional[date] = None
    lost_reason: Optional[str] = None
    notes: Optional[str] = None


class ProspectCreate(ProspectBase):
    pass


class ProspectUpdate(BaseModel):
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    source: Optional[str] = None
    owner_id: Optional[int] = None
    status: Optional[ProspectStatus] = None
    proposal_sent_date: Optional[date] = None
    proposal_amount: Optional[Decimal] = Field(None, ge=0)
    expected_close_date: Optional[date] = None
    next_follow_up_date: Optional[date] = None
    lost_reason: Optional[str] = None
    notes: Optional[str] = None


class ProspectConvertRequest(BaseModel):
    jurisdiction: Optional[str] = None
    service_type: Optional[str] = None
    rm_id: Optional[int] = None


class ProspectRead(ProspectBase):
    id: int
    prospect_uid: str
    converted_case_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
