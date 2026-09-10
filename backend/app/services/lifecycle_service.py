"""Service layer: EntityLifecycle — closure / strike-off / restoration / RA transfer.

1:1 with Case, lazy get-or-create (same pattern as company_service). The single
place Case.status is moved to a lifecycle value: update() derives the status from
the lifecycle fields after every patch, so status and the underlying dates can
never drift apart.
"""
from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import (
    Case, CaseStatus, EntityLifecycle, RestorationStatus, User, UserRole,
    new_restoration_checklist,
)
from app.schemas.entity_lifecycle import EntityLifecycleUpdate
from app.services import notification_service
from app import jurisdictions

_NOTIFY_ON_ENTRY = {
    CaseStatus.IN_CLOSURE.value,
    CaseStatus.STRUCK_OFF.value,
    CaseStatus.DISSOLVED.value,
    CaseStatus.TRANSFERRED_OUT.value,
}


def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if user.role == UserRole.RM and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def get_or_create(db: Session, case_id: int) -> EntityLifecycle:
    lc = db.query(EntityLifecycle).filter(EntityLifecycle.case_id == case_id).first()
    if lc:
        return lc
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    lc = EntityLifecycle(
        case_id=case_id,
        restoration_status=RestorationStatus.NOT_APPLICABLE.value,
        restoration_checklist=new_restoration_checklist(case.jurisdiction),
    )
    db.add(lc)
    db.commit()
    db.refresh(lc)
    return lc


def _derive_status(lc: EntityLifecycle) -> str | None:
    """The Case.status implied by the lifecycle fields, or None to leave it alone."""
    if lc.restoration_status == RestorationStatus.COMPLETED.value:
        return CaseStatus.ACTIVE.value
    if lc.restoration_status == RestorationStatus.IN_PROGRESS.value:
        return CaseStatus.STRUCK_OFF.value
    if lc.dissolution_confirmed:
        return CaseStatus.DISSOLVED.value
    if lc.strike_off_date:
        return CaseStatus.STRUCK_OFF.value
    if lc.transfer_completed_date and lc.transfer_ends_administration:
        return CaseStatus.TRANSFERRED_OUT.value
    if lc.closure_initiated_date:
        return CaseStatus.IN_CLOSURE.value
    return None


def update(db: Session, case_id: int, data: EntityLifecycleUpdate, user: User) -> EntityLifecycle:
    case = _get_case_for_write(db, case_id, user)
    lc = get_or_create(db, case_id)

    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(lc, field, value)

    today = date.today()

    # Fill in the obvious companion dates when a state is entered without one.
    if lc.strike_off_date and not lc.expected_dissolution_date:
        years = jurisdictions.get(case.jurisdiction).strike_off_years
        lc.expected_dissolution_date = lc.strike_off_date + relativedelta(years=years)
    if lc.restoration_status == RestorationStatus.IN_PROGRESS.value and not lc.restoration_initiated_date:
        lc.restoration_initiated_date = today
    if lc.restoration_status == RestorationStatus.COMPLETED.value and not lc.restoration_completed_date:
        lc.restoration_completed_date = today
    if lc.dissolution_confirmed and not lc.dissolution_date:
        lc.dissolution_date = today

    new_status = _derive_status(lc)
    status_changed_to = None
    if new_status and new_status != case.status:
        case.status = new_status
        status_changed_to = new_status

    db.commit()
    db.refresh(lc)

    if status_changed_to in _NOTIFY_ON_ENTRY:
        msg = f"{case.case_uid} ({case.company_name}) is now '{status_changed_to}'."
        for role in (UserRole.OPS, UserRole.ADMIN):
            notification_service.notify_role(
                db, role, msg, "lifecycle_status_changed",
                link=f"/cases/{case_id}", case_id=case_id,
            )

    return lc
