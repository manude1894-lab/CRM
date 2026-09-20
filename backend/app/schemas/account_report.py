"""Pydantic schemas: Client Track Record (in-app summary + PDF export)."""
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class TrackRecordCase(BaseModel):
    case_uid: str
    company_name: str
    jurisdiction: Optional[str] = None
    service_type: Optional[str] = None
    stage: str
    status: str
    onboarding_date: Optional[date] = None
    invoice_status: str
    invoice_amount: Decimal
    next_renewal_due: Optional[date] = None
    next_esr_due: Optional[date] = None
    next_ar_due: Optional[date] = None
    next_bo_due: Optional[date] = None


class TrackRecordParty(BaseModel):
    full_name: str
    party_role: str
    constitution: str
    effective_ownership_percent: Optional[Decimal] = None


class TrackRecordRead(BaseModel):
    account_uid: str
    company_name: str
    account_type: str
    industry: Optional[str] = None
    country: Optional[str] = None
    risk_rating: Optional[str] = None
    kyc_status: str
    client_since: datetime

    total_cases: int
    active_cases: int
    total_onboarding_invoiced: Decimal
    ledger_invoices_paid: Decimal
    ledger_invoices_outstanding: Decimal

    cases: list[TrackRecordCase]
    parties: list[TrackRecordParty]
