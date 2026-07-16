"""Pydantic schemas: Dashboard & analytics responses."""
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import date


class KPISummary(BaseModel):
    open_cases: int
    docs_pending: int
    cdd_awaiting_screening: int
    invoices_unpaid: int
    upcoming_compliance_60d: int


class StageBreakdown(BaseModel):
    stage: str
    count: int


class DocsPendingItem(BaseModel):
    case_id: int
    case_uid: str
    company_name: str
    stage: str
    business_days_pending: int


class CDDAwaitingItem(BaseModel):
    case_id: int
    case_uid: str
    company_name: str
    cdd_form_status: str
    kyc_verification_status: str
    days_waiting: int


class InvoiceUnpaidItem(BaseModel):
    case_id: int
    case_uid: str
    company_name: str
    invoice_amount: Decimal
    invoice_raised_date: Optional[date] = None
    days_aging: int


class UpcomingComplianceRow(BaseModel):
    case_id: int
    case_uid: str
    company_name: str
    item: str
    due_date: date
    days_remaining: int


class RmOpsPerformance(BaseModel):
    user_id: int
    name: str
    role: str
    total_cases: int
    active_cases: int


class DashboardResponse(BaseModel):
    kpis: KPISummary
    stage_breakdown: List[StageBreakdown]
    docs_pending: List[DocsPendingItem]
    cdd_awaiting_screening: List[CDDAwaitingItem]
    invoices_unpaid: List[InvoiceUnpaidItem]
    upcoming_compliance: List[UpcomingComplianceRow]
    rm_ops_performance: List[RmOpsPerformance]
