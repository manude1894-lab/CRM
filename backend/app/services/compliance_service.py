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
from app.models import ComplianceSchedule, Case, CaseStatus, UserRole
from app.schemas.compliance import ComplianceMarkDoneRequest
from app.services import notification_service
from app import jurisdictions

# Case statuses for which the compliance calendar no longer applies — the entity
# is struck off, dissolved or has left Triam's administration. Reminders and the
# "upcoming" list skip these.
DORMANT_CASE_STATUSES = {
    CaseStatus.STRUCK_OFF.value,
    CaseStatus.DISSOLVED.value,
    CaseStatus.TRANSFERRED_OUT.value,
}

# item -> (due_field, last_completed_field, cadence_field) — the ComplianceSchedule
# column names. The roll rule and label now come from the jurisdiction spec.
_ITEM_FIELDS = {
    "renewal": ("renewal_due_date", "renewal_last_completed_date", "renewal_cadence_months"),
    "esr_filing": ("esr_filing_due_date", "esr_filing_last_completed_date", "esr_filing_cadence_months"),
    "ar_filing": ("ar_filing_due_date", "ar_filing_last_completed_date", "ar_filing_cadence_months"),
    "bo_filing": ("bo_filing_due_date", "bo_filing_last_completed_date", None),
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


def next_fixed(mm: int, dd: int, after: date | None = None) -> date:
    """Next occurrence of a fixed month/day strictly after `after`."""
    after = after or date.today()
    candidate = date(after.year, mm, dd)
    if candidate <= after:
        candidate = date(after.year + 1, mm, dd)
    return candidate


def next_30_september(after: date | None = None) -> date:
    return next_fixed(9, 30, after)


def compute_due(item, *, incorporation_date: date | None, base: date | None,
                after: date | None = None):
    """The due date for one compliance item under its jurisdiction's anchor rule."""
    anchor = item.anchor
    if anchor == "anniversary":
        return next_anniversary(incorporation_date or base, after)
    if anchor.startswith("fixed:"):
        mm, dd = (int(x) for x in anchor.split(":", 1)[1].split("-"))
        return next_fixed(mm, dd, after)
    if anchor == "annual":
        return (after or base or date.today()) + relativedelta(months=item.cadence_months)
    return None  # "event" — set by flag_bo_filing_due only


def build_schedule_dates(spec, *, incorporation_date: date | None, base: date | None) -> dict:
    """The {<key>_due_date, <key>_cadence_months} values for a fresh schedule."""
    out = {}
    for item in spec.compliance_items:
        due = compute_due(item, incorporation_date=incorporation_date, base=base)
        if due is not None:
            out[f"{item.key}_due_date"] = due
        if item.key != "bo_filing":
            out[f"{item.key}_cadence_months"] = item.cadence_months
    return out


def recompute_schedule(db: Session, case: Case) -> ComplianceSchedule | None:
    """Rebuild the due dates on an existing schedule from the case's current
    jurisdiction. Preserves *_last_completed_date and the AR sub-workflow fields."""
    schedule = db.query(ComplianceSchedule).filter(ComplianceSchedule.case_id == case.id).first()
    if not schedule:
        return None
    spec = jurisdictions.get(case.jurisdiction)
    profile = getattr(case, "company_profile", None)
    incorp = profile.incorporation_date if profile else None
    base = incorp or case.license_received_date or date.today()
    active = {i.key for i in spec.compliance_items}
    for key in ("renewal", "esr_filing", "ar_filing", "bo_filing"):
        if key not in active or key == "bo_filing":
            continue
        item = spec.item(key)
        setattr(schedule, f"{key}_due_date", compute_due(item, incorporation_date=incorp, base=base))
        setattr(schedule, f"{key}_cadence_months", item.cadence_months)
    db.commit()
    db.refresh(schedule)
    return schedule


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
        .filter(Case.status.notin_(DORMANT_CASE_STATUSES))
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
        spec = jurisdictions.get(case.jurisdiction)
        for item_key, (due_field, *_rest) in _ITEM_FIELDS.items():
            due_date = getattr(schedule, due_field)
            if due_date and due_date <= horizon:
                spec_item = spec.item(item_key)
                rows.append({
                    "case_id": case.id,
                    "case_uid": case.case_uid,
                    "company_name": case.company_name,
                    "item": item_key,
                    "label": spec_item.label if spec_item else item_key,
                    "due_date": due_date,
                    "days_remaining": (due_date - today).days,
                    "ar_filing_status": schedule.ar_filing_status if item_key == "ar_filing" else None,
                })
    rows.sort(key=lambda r: r["due_date"])
    return rows


# ─── Mutations ───────────────────────────────────────────────────────────
def _roll_item(db: Session, schedule: ComplianceSchedule, item_key: str) -> None:
    """Advance one item's due date per its jurisdiction's anchor rule."""
    case = db.query(Case).filter(Case.id == schedule.case_id).first()
    spec = jurisdictions.get(case.jurisdiction if case else None)
    item = spec.item(item_key)
    due_field = _ITEM_FIELDS[item_key][0]
    today = date.today()
    if item is None or item.anchor == "event":
        setattr(schedule, due_field, None)
    elif item.anchor == "annual":
        setattr(schedule, due_field, today + relativedelta(months=item.cadence_months))
    else:  # anniversary | fixed
        profile = getattr(case, "company_profile", None) if case else None
        incorp = profile.incorporation_date if profile else None
        setattr(schedule, due_field, compute_due(item, incorporation_date=incorp, base=today, after=today))


def mark_done(db: Session, case_id: int, data: ComplianceMarkDoneRequest) -> ComplianceSchedule:
    schedule = get_schedule(db, case_id)
    completed_field = _ITEM_FIELDS[data.item][1]
    setattr(schedule, completed_field, date.today())
    _roll_item(db, schedule, data.item)

    if data.item == "ar_filing":
        _reset_ar_subworkflow(schedule)

    db.commit()
    db.refresh(schedule)
    return schedule


# ─── Annual Return sub-workflow (light) ──────────────────────────────────
_AR_STATUSES = ("Not Started", "Data Prepared", "Submitted to Vistra", "Filed", "Confirmed")


def _reset_ar_subworkflow(schedule: ComplianceSchedule) -> None:
    """Roll the AR sub-workflow after a filing is confirmed: bump the reference year,
    reset the status. The due-date roll itself is handled by the caller."""
    schedule.ar_reference_year = (schedule.ar_reference_year or date.today().year) + 1
    schedule.ar_filing_status = "Not Started"


def set_ar_status(db: Session, case_id: int, status: str) -> ComplianceSchedule:
    from app.models import Instruction  # local import — avoids a services import cycle

    schedule = get_schedule(db, case_id)
    schedule.ar_filing_status = status
    year = schedule.ar_reference_year or date.today().year

    if status == "Data Prepared":
        has_open = (
            db.query(Instruction)
            .filter(
                Instruction.case_id == case_id,
                Instruction.instruction_type == "AR Filing",
                Instruction.status != "Completed",
            )
            .first()
        )
        if not has_open:
            db.add(Instruction(
                case_id=case_id,
                instruction_type="AR Filing",
                status="Pending",
                comments=f"Annual Return {year} — auto-created from the compliance calendar.",
            ))
    elif status == "Confirmed":
        schedule.ar_filing_last_completed_date = date.today()
        _roll_item(db, schedule, "ar_filing")
        _reset_ar_subworkflow(schedule)

    db.commit()
    db.refresh(schedule)
    return schedule


def flag_bo_filing_due(db: Session, case_id: int) -> None:
    """Called after any ownership change (UBO/shareholder create or edit): a ROM/RBO
    filing is due within BO_FILING_DEADLINE_DAYS. No-op if the case has no schedule yet."""
    schedule = db.query(ComplianceSchedule).filter(ComplianceSchedule.case_id == case_id).first()
    if not schedule:
        return
    case = db.query(Case).filter(Case.id == case_id).first()
    days = jurisdictions.get(case.jurisdiction if case else None).bo_filing_days
    new_due = date.today() + timedelta(days=days)
    # Don't push an already-closer deadline further out.
    if schedule.bo_filing_due_date and schedule.bo_filing_due_date <= new_due:
        return
    schedule.bo_filing_due_date = new_due
    db.commit()

    if case:
        msg = (f"Ownership change on {case.case_uid} ({case.company_name}) — "
               f"ROM/RBO filing due by {new_due} (to the registered agent).")
        notification_service.notify_role(db, UserRole.OPS, msg, "bo_filing_flagged",
                                         link=f"/compliance/{case_id}", case_id=case_id)
        notification_service.notify_role(db, UserRole.ADMIN, msg, "bo_filing_flagged",
                                         link=f"/compliance/{case_id}", case_id=case_id)
