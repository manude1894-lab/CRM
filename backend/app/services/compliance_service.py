"""Service layer: ComplianceSchedule lookups + mark-done rollover."""
from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import ComplianceSchedule, Case
from app.schemas.compliance import ComplianceMarkDoneRequest

_ITEM_FIELDS = {
    "renewal": ("renewal_due_date", "renewal_last_completed_date", "renewal_cadence_months"),
    "compliance_filing": ("compliance_filing_due_date", "compliance_filing_last_completed_date", "compliance_filing_cadence_months"),
    "tax_filing": ("tax_filing_due_date", "tax_filing_last_completed_date", "tax_filing_cadence_months"),
}


def get_schedule(db: Session, case_id: int) -> ComplianceSchedule:
    schedule = db.query(ComplianceSchedule).filter(ComplianceSchedule.case_id == case_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Compliance schedule not found for this case")
    return schedule


def list_upcoming(db: Session, days: int = 60) -> list[dict]:
    horizon = date.today() + relativedelta(days=days)
    today = date.today()
    from sqlalchemy import or_
    schedules = (
        db.query(ComplianceSchedule, Case)
        .join(Case, Case.id == ComplianceSchedule.case_id)
        .filter(or_(
            ComplianceSchedule.renewal_due_date <= horizon,
            ComplianceSchedule.compliance_filing_due_date <= horizon,
            ComplianceSchedule.tax_filing_due_date <= horizon,
        ))
        .all()
    )
    rows: list[dict] = []
    for schedule, case in schedules:
        for item, (due_field, _, _) in _ITEM_FIELDS.items():
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


def mark_done(db: Session, case_id: int, data: ComplianceMarkDoneRequest) -> ComplianceSchedule:
    schedule = get_schedule(db, case_id)
    due_field, completed_field, cadence_field = _ITEM_FIELDS[data.item]

    cadence_months = getattr(schedule, cadence_field)
    today = date.today()
    setattr(schedule, completed_field, today)
    setattr(schedule, due_field, today + relativedelta(months=cadence_months))

    db.commit()
    db.refresh(schedule)
    return schedule
