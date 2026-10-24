"""Pydantic schemas: Prospect (BRD §4A)."""
import re

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.prospect import ProspectStatus


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _ProspectRules(BaseModel):
    @field_validator("contact_email", mode="before", check_fields=False)
    @classmethod
    def _email(cls, v):
        """Contact email in the standard name@domain.tld form (Triam input 19-10-2026)."""
        if v in (None, ""):
            return None
        v = str(v).strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("is not a valid email address (name@domain.com)")
        return v


class ProspectBase(_ProspectRules):
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


class ProspectUpdate(_ProspectRules):
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


class DuplicateMatch(BaseModel):
    id: int
    company_name: str
    score: int
    source: Optional[str] = None  # "prospect" | "client"


class ProspectAssignRequest(BaseModel):
    rm_id: int
    comments: Optional[str] = Field(None, max_length=4000)  # "Assignor's comments", up to 250 words, optional


class ProspectRead(ProspectBase):
    id: int
    prospect_uid: str
    converted_account_id: Optional[int] = None
    assigned_by_id: Optional[int] = None
    assigned_by_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    assignor_comments: Optional[str] = None
    owner_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
