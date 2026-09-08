"""Service layer: ComplianceSchedule — BVI-calendar due dates + mark-done rollover.

Slots: renewal (Annual Licence Fee, incorporation anniversary), esr_filing (annual),
ar_filing (fixed 30 September), bo_filing (event-driven, 30 days, cleared not rolled).
"""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.config import settings
from app.models import ComplianceSchedule, Case, UserRole
from app.schemas.compliance import ComplianceMarkDoneRequest
from app.services import notification_service

# item -> (due_field, last_completed_field, roll)
#   roll("cadence") — add N months;  roll("sept30") — next 30 September;  roll("clear") — set due None
_ITEM_FIELDS = {
    "renewal": ("renewal_due_date", "renewal_last_completed_date", "cadence", "renewal_cadence_months"),
    "esr_filing": ("esr_filing_due_date", "esr_filing_last_completed_date", "cadence", "esr_filing_cadence_months"),
    "ar_filing": ("ar_filing_due_date", "ar_filing_last_completed_date", "sept30", None),
    "bo_filing": ("bo_filing_due_date", "bo_filing_last_completed_date", "clear", None),
}

_ITEM_LABEL = {
    "renewal": "Annual Licence Fee renewal",
    "esr_filing": "Economic Substance (ESR) filing",
    "ar_filing": "Annual Return filing",
    "bo_filing": "BO / ROM-RBO filing",
}


# ─── Date helpers ────────────────────────────────────────────────────────
def next_anniversary(anchor: date | None, after: date | None = None) -> date:
    """Next occurrence of anchor's month/day strictly after `after` (default today)."""
    after = after or date.today()
    if not anchor:
        return after + relativedelta(months=12)
    candidate = anchor.replace(year=after.year)
    if candidate <= after:
        candidate = anchor.replace(year=after.year + 1)
    return candidate


def next_30_september(after: date | None = None) -> date:
    after = after or date.today()
    candidate = date(after.year, 9, 30)
    if candidate <= after:
        candidate = date(after.year + 1, 9, 30)
    return candidate


# ─── Lookups ─────────────────────────────────────────────────────────────
def get_schedule(db: Session, case_id: int) -> ComplianceSchedule:
    schedule = db.query(ComplianceSchedule).filter(ComplianceSchedule.case_id == case_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Compliance schedule not found for this case")
    return schedule


def list_upcoming(db: Session, days: int = 60) -> list[dict]:
    horizon = date.today() + timedelta(days=days)
    today = date.today()
    schedules = (
        db.query(ComplianceSchedule, Case)
        .join(Case, Case.id == ComplianceSchedule.case_id)
        .filter(or_(
            ComplianceSchedule.renewal_due_date <= horizon,
            ComplianceSchedule.esr_filing_due_date <= horizon,
            ComplianceSchedule.ar_filing_due_date <= horizon,
            ComplianceSchedule.bo_filing_due_date <= horizon,
        ))
        .all()
    )
    rows: list[dict] = []
    for schedule, case in schedules:
        for item, (due_field, *_rest) in _ITEM_FIELDS.items():
            due_date = getattr(schedule, due_field)
            if due_date and due_date <= horizon:
                rows.append({
                    "case_id": case.id,
                    "case_uid": case.case_uid,
                    "company_name": case.company_name,
                    "item": item,
                    "due_date": due_date,
                    "days_remaining": (due_date - today).days,
                })
    rows.sort(key=lambda r: r["due_date"])
    return rows


# ─── Mutations ───────────────────────────────────────────────────────────
def mark_done(db: Session, case_id: int, data: ComplianceMarkDoneRequest) -> ComplianceSchedule:
    schedule = get_schedule(db, case_id)
    due_field, completed_field, roll, cadence_field = _ITEM_FIELDS[data.item]
    today = date.today()
    setattr(schedule, completed_field, today)

    if roll == "cadence":
        setattr(schedule, due_field, today + relativedelta(months=getattr(schedule, cadence_field)))
    elif roll == "sept30":
        setattr(schedule, due_field, next_30_september(after=today))
    elif roll == "clear":
        setattr(schedule, due_field, None)

    db.commit()
    db.refresh(schedule)
    return schedule


def flag_bo_filing_due(db: Session, case_id: int) -> None:
    """Called after any ownership change (UBO/shareholder create or edit): a ROM/RBO
    filing is due within BO_FILING_DEADLINE_DAYS. No-op if the case has no schedule yet."""
    schedule = db.query(ComplianceSchedule).filter(ComplianceSchedule.case_id == case_id).first()
    if not schedule:
        return
    new_due = date.today() + timedelta(days=settings.BO_FILING_DEADLINE_DAYS)
    # Don't push an already-closer deadline further out.
    if schedule.bo_filing_due_date and schedule.bo_filing_due_date <= new_due:
        return
    schedule.bo_filing_due_date = new_due
    db.commit()

    case = db.query(Case).filter(Case.id == case_id).first()
    if case:
        msg = (f"Ownership change on {case.case_uid} ({case.company_name}) — "
               f"ROM/RBO filing due by {new_due}.")
        notification_service.notify_role(db, UserRole.OPS, msg, "bo_filing_flagged",
                                         link=f"/compliance/{case_id}", case_id=case_id)
        notification_service.notify_role(db, UserRole.ADMIN, msg, "bo_filing_flagged",
                                         link=f"/compliance/{case_id}", case_id=case_id)
