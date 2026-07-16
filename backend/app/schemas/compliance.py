"""Pydantic schemas: ComplianceSchedule."""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date, datetime


class ComplianceScheduleUpdate(BaseModel):
    renewal_due_date: Optional[date] = None
    compliance_filing_due_date: Optional[date] = None
    tax_filing_due_date: Optional[date] = None


class ComplianceMarkDoneRequest(BaseModel):
    item: Literal["renewal", "compliance_filing", "tax_filing"]


class ComplianceScheduleRead(BaseModel):
    id: int
    case_id: int
    renewal_due_date: Optional[date] = None
    renewal_last_completed_date: Optional[date] = None
    renewal_cadence_months: int
    compliance_filing_due_date: Optional[date] = None
    compliance_filing_last_completed_date: Optional[date] = None
    compliance_filing_cadence_months: int
    tax_filing_due_date: Optional[date] = None
    tax_filing_last_completed_date: Optional[date] = None
    tax_filing_cadence_months: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpcomingComplianceItem(BaseModel):
    case_id: int
    case_uid: str
    company_name: str
    item: Literal["renewal", "compliance_filing", "tax_filing"]
    due_date: date
    days_remaining: int
