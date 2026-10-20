"""Pydantic schemas: Dashboard snapshot MI (BRD §2)."""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class KPISummary(BaseModel):
    prospects_open: int
    prospects_unassigned: int
    clients_in_progress: int
    clients_awaiting_approval: int
    clients_active: int
    service_requests_open: int
    invoices_unpaid: int
    aml_reviews_due: int


class StatusCount(BaseModel):
    status: str
    count: int


class ApprovalsPending(BaseModel):
    compliance: int
    approver: int


class AmlReviewDue(BaseModel):
    account_id: int
    client_id: Optional[str] = None
    company_name: str
    risk_rating: Optional[str] = None
    next_aml_review_date: date
    days_remaining: int


class PortfolioRow(BaseModel):
    user_id: int
    name: str
    total: int
    in_progress: int
    active: int


class DashboardResponse(BaseModel):
    kpis: KPISummary
    client_status_breakdown: List[StatusCount]
    approvals_pending: ApprovalsPending
    aml_reviews_due: List[AmlReviewDue]
    portfolio_by_rm: List[PortfolioRow]
