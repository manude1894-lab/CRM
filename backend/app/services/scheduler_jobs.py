"""Daily scheduled SLA checks, run in-process via APScheduler (no Redis/Celery).

Each job opens its own DB session since it runs outside the FastAPI request
lifecycle. Notifications are deduped per (case, notification_type) so the
daily sweep doesn't re-notify on every run while the breach is still open.
"""
import logging
from datetime import date, datetime, timezone

from app.database import SessionLocal
from app.models import Case, CaseStatus, CDDRecord, DocumentStatus, ComplianceSchedule, UserRole
from app.services import notification_service, compliance_service
from app.services.compliance_service import DORMANT_CASE_STATUSES
from app.services.compliance_service import _ITEM_FIELDS
from app.utils.business_days import business_days_between, to_date
from app import jurisdictions

logger = logging.getLogger("ezeetech.scheduler")

DOCS_PENDING_BUSINESS_DAYS = 3
CDD_REVIEW_SLA_DAYS = 2
INVOICE_UNPAID_SLA_DAYS = 7


def _notify_once(db, case_id: int, notification_type: str, role: UserRole, message: str, link: str):
    if notification_service.has_unresolved_notification(db, case_id, notification_type):
        return
    notification_service.notify_role(db, role, message, notification_type, link=link, case_id=case_id)


def check_docs_pending():
    db = SessionLocal()
    try:
        today = date.today()
        cases = db.query(Case).filter(Case.status == CaseStatus.DOCS_PENDING.value).all()
        for case in cases:
            days = business_days_between(to_date(case.updated_at), today)
            if days > DOCS_PENDING_BUSINESS_DAYS and case.rm_id:
                _notify_once(
                    db, case.id, "docs_pending_overdue", UserRole.RM,
                    f"Case {case.case_uid} ({case.company_name}) has been awaiting client documents for {days} business days.",
                    f"/cases/{case.id}",
                )
    finally:
        db.close()


def check_cdd_awaiting_screening():
    db = SessionLocal()
    try:
        today = date.today()
        records = db.query(CDDRecord).filter(
            CDDRecord.cdd_form_status.in_([DocumentStatus.SUBMITTED, DocumentStatus.UNDER_REVIEW])
        ).all()
        for cdd in records:
            days = business_days_between(to_date(cdd.updated_at), today)
            if days > CDD_REVIEW_SLA_DAYS:
                case = db.query(Case).filter(Case.id == cdd.case_id).first()
                if case:
                    _notify_once(
                        db, case.id, "cdd_awaiting_screening", UserRole.SCREENING,
                        f"CDD/KYC for case {case.case_uid} ({case.company_name}) has awaited screening for {days} days.",
                        f"/cdd/{case.id}",
                    )
    finally:
        db.close()


def check_invoice_unpaid():
    db = SessionLocal()
    try:
        from app.models import InvoiceStatus
        today = date.today()
        cases = db.query(Case).filter(Case.invoice_status == InvoiceStatus.RAISED).all()
        for case in cases:
            if not case.invoice_raised_date:
                continue
            days = (today - case.invoice_raised_date).days
            if days > INVOICE_UNPAID_SLA_DAYS:
                if notification_service.has_unresolved_notification(db, case.id, "invoice_unpaid"):
                    continue
                msg = f"Invoice for case {case.case_uid} ({case.company_name}) has been unpaid for {days} days."
                if case.rm_id:
                    notification_service.notify_user(db, case.rm_id, msg, "invoice_unpaid", link=f"/cases/{case.id}", case_id=case.id)
                notification_service.notify_role(db, UserRole.ADMIN, msg, "invoice_unpaid", link=f"/cases/{case.id}", case_id=case.id)
    finally:
        db.close()


def _check_compliance_reminders(db, item_key: str, notification_type: str, role: UserRole):
    """Fire reminders for one compliance item across all schedules. The reminder-day
    windows and the label come from each case's jurisdiction spec."""
    today = date.today()
    due_field = _ITEM_FIELDS[item_key][0]
    for schedule in db.query(ComplianceSchedule).all():
        due_date = getattr(schedule, due_field)
        if not due_date:
            continue
        days_remaining = (due_date - today).days
        case = db.query(Case).filter(Case.id == schedule.case_id).first()
        if not case or case.status in DORMANT_CASE_STATUSES:
            continue
        spec_item = jurisdictions.get(case.jurisdiction).item(item_key)
        if not spec_item or days_remaining not in spec_item.reminder_days:
            continue
        key = f"{notification_type}_{days_remaining}d"
        if notification_service.has_unresolved_notification(db, case.id, key):
            continue
        msg = f"{spec_item.label} for case {case.case_uid} ({case.company_name}) is due in {days_remaining} days ({due_date})."
        notification_service.notify_role(db, role, msg, key, link=f"/compliance/{case.id}", case_id=case.id)
        notification_service.notify_role(db, UserRole.ADMIN, msg, key, link=f"/compliance/{case.id}", case_id=case.id)


def check_renewals_due():
    db = SessionLocal()
    try:
        _check_compliance_reminders(db, "renewal", "renewal_due", UserRole.RM)
    finally:
        db.close()


def check_esr_filings_due():
    db = SessionLocal()
    try:
        _check_compliance_reminders(db, "esr_filing", "esr_filing_due", UserRole.OPS)
    finally:
        db.close()


def check_ar_filings_due():
    db = SessionLocal()
    try:
        _check_compliance_reminders(db, "ar_filing", "ar_filing_due", UserRole.OPS)
    finally:
        db.close()


def check_bo_filings_due():
    db = SessionLocal()
    try:
        _check_compliance_reminders(db, "bo_filing", "bo_filing_due", UserRole.OPS)
    finally:
        db.close()


def run_daily_sweep():
    """Entry point registered with APScheduler — runs all checks in sequence."""
    for job in (
        check_docs_pending,
        check_cdd_awaiting_screening,
        check_invoice_unpaid,
        check_renewals_due,
        check_esr_filings_due,
        check_ar_filings_due,
        check_bo_filings_due,
    ):
        try:
            job()
        except Exception:
            logger.exception("Scheduled job %s failed", job.__name__)
