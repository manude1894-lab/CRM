"""Pydantic schemas: ComplianceSchedule."""
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import date, datetime

ComplianceItem = Literal["renewal", "esr_filing", "ar_filing", "bo_filing"]


class ComplianceScheduleUpdate(BaseModel):
    renewal_due_date: Optional[date] = None
    esr_filing_due_date: Optional[date] = None
    ar_filing_due_date: Optional[date] = None
    bo_filing_due_date: Optional[date] = None


class ComplianceMarkDoneRequest(BaseModel):
    item: ComplianceItem


class ARStatusRequest(BaseModel):
    status: Literal[
        "Not Started", "Data Prepared", "Submitted to Vistra", "Filed", "Confirmed",
    ]


class ComplianceScheduleRead(BaseModel):
    id: int
    case_id: int
    renewal_due_date: Optional[date] = None
    renewal_last_completed_date: Optional[date] = None
    renewal_cadence_months: int
    esr_filing_due_date: Optional[date] = None
    esr_filing_last_completed_date: Optional[date] = None
    esr_filing_cadence_months: int
    ar_filing_due_date: Optional[date] = None
    ar_filing_last_completed_date: Optional[date] = None
    ar_filing_cadence_months: int
    ar_filing_status: str = "Not Started"
    ar_reference_year: Optional[int] = None
    bo_filing_due_date: Optional[date] = None
    bo_filing_last_completed_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpcomingComplianceItem(BaseModel):
    case_id: int
    case_uid: str
    company_name: str
    item: ComplianceItem
    label: Optional[str] = None
    due_date: date
    days_remaining: int
    ar_filing_status: Optional[str] = None
