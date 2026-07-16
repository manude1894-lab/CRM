"""Service layer: Dashboard and analytics aggregations."""
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models import (
    Case, CaseStage, CaseStatus, InvoiceStatus, User, UserRole,
    CDDRecord, DocumentStatus, ComplianceSchedule,
)
from app.services.compliance_service import list_upcoming
from app.utils.business_days import business_days_between, to_date


def _rbac_case_query(db: Session, user: User):
    q = db.query(Case)
    if user.role == UserRole.RM:
        q = q.filter(Case.rm_id == user.id)
    return q


def build_dashboard(db: Session, user: User) -> dict:
    cases = _rbac_case_query(db, user).all()
    today = date.today()

    open_cases = [c for c in cases if c.stage != CaseStage.ACTIVE]

    docs_pending_cases = [c for c in cases if c.status == CaseStatus.DOCS_PENDING]
    docs_pending = [{
        "case_id": c.id, "case_uid": c.case_uid, "company_name": c.company_name,
        "stage": c.stage.value,
        "business_days_pending": business_days_between(to_date(c.updated_at), today),
    } for c in docs_pending_cases]

    case_ids = [c.id for c in cases]
    cdd_records = db.query(CDDRecord).filter(CDDRecord.case_id.in_(case_ids)).all() if case_ids else []
    case_by_id = {c.id: c for c in cases}
    cdd_awaiting_screening = []
    for cdd in cdd_records:
        if cdd.cdd_form_status in (DocumentStatus.SUBMITTED, DocumentStatus.UNDER_REVIEW) or \
           cdd.kyc_verification_status in (DocumentStatus.SUBMITTED, DocumentStatus.UNDER_REVIEW):
            c = case_by_id.get(cdd.case_id)
            if not c:
                continue
            cdd_awaiting_screening.append({
                "case_id": c.id, "case_uid": c.case_uid, "company_name": c.company_name,
                "cdd_form_status": cdd.cdd_form_status.value,
                "kyc_verification_status": cdd.kyc_verification_status.value,
                "days_waiting": business_days_between(to_date(cdd.updated_at), today),
            })

    invoices_unpaid_cases = [c for c in cases if c.invoice_status == InvoiceStatus.RAISED]
    invoices_unpaid = [{
        "case_id": c.id, "case_uid": c.case_uid, "company_name": c.company_name,
        "invoice_amount": Decimal(c.invoice_amount),
        "invoice_raised_date": c.invoice_raised_date,
        "days_aging": (today - c.invoice_raised_date).days if c.invoice_raised_date else 0,
    } for c in invoices_unpaid_cases]

    upcoming_compliance = list_upcoming(db, days=60)

    kpis = {
        "open_cases": len(open_cases),
        "docs_pending": len(docs_pending),
        "cdd_awaiting_screening": len(cdd_awaiting_screening),
        "invoices_unpaid": len(invoices_unpaid),
        "upcoming_compliance_60d": len(upcoming_compliance),
    }

    stage_breakdown = [
        {"stage": stage.value, "count": len([c for c in cases if c.stage == stage])}
        for stage in CaseStage
    ]

    rm_ops_users = db.query(User).filter(User.role.in_([UserRole.RM, UserRole.OPS]), User.is_active == True).all()
    rm_ops_performance = []
    for u in rm_ops_users:
        if u.role == UserRole.RM:
            my_cases = [c for c in cases if c.rm_id == u.id]
        else:
            my_cases = [c for c in cases if c.ops_owner_id == u.id]
        rm_ops_performance.append({
            "user_id": u.id,
            "name": u.name,
            "role": u.role.value,
            "total_cases": len(my_cases),
            "active_cases": len([c for c in my_cases if c.stage != CaseStage.ACTIVE]),
        })

    return {
        "kpis": kpis,
        "stage_breakdown": stage_breakdown,
        "docs_pending": docs_pending,
        "cdd_awaiting_screening": cdd_awaiting_screening,
        "invoices_unpaid": invoices_unpaid,
        "upcoming_compliance": upcoming_compliance,
        "rm_ops_performance": rm_ops_performance,
    }
