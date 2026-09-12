"""Service layer: FormationRecord — screening / MLRO sign-off / Vistra loop / §V milestones.

1:1 with Case, lazy get-or-create (same pattern as company_service / lifecycle_service).
MLRO sign-off and Vistra approval are tracked + notified only — they do not gate the
pipeline.
"""
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import (
    Case, FormationRecord, ScreeningStatus, MLROSignoffStatus, VistraStatus,
    User, UserRole,
)
from app.schemas.formation import FormationRecordUpdate
from app.services import notification_service, access_control

_SCREENING_FIELDS = {
    "screening_status", "screening_date", "screening_tool", "world_check_reference",
    "sanctions_hit", "pep_hit", "adverse_media_hit", "screening_findings",
}
_MLRO_LOCKED_STATUSES = {MLROSignoffStatus.SIGNED_OFF.value, MLROSignoffStatus.REJECTED.value}


def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not access_control.user_can_access_case(case, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def get_or_create(db: Session, case_id: int) -> FormationRecord:
    rec = db.query(FormationRecord).filter(FormationRecord.case_id == case_id).first()
    if rec:
        return rec
    if not db.query(Case).filter(Case.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    rec = FormationRecord(
        case_id=case_id,
        screening_status=ScreeningStatus.NOT_STARTED.value,
        mlro_signoff_status=MLROSignoffStatus.PENDING.value,
        vistra_status=VistraStatus.NOT_SUBMITTED.value,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _notify_rm_and_admin(db: Session, case: Case, message: str, ntype: str) -> None:
    link = f"/cases/{case.id}"
    if case.rm_id:
        notification_service.notify_user(db, case.rm_id, message, ntype, link=link, case_id=case.id)
    notification_service.notify_role(db, UserRole.ADMIN, message, ntype, link=link, case_id=case.id)


def update(db: Session, case_id: int, data: FormationRecordUpdate, user: User) -> FormationRecord:
    case = _get_case_for_write(db, case_id, user)
    rec = get_or_create(db, case_id)
    payload = data.model_dump(exclude_unset=True)

    old_vistra = rec.vistra_status
    old_mlro = rec.mlro_signoff_status

    new_mlro = payload.get("mlro_signoff_status")
    if new_mlro in _MLRO_LOCKED_STATUSES and new_mlro != old_mlro and user.role not in (UserRole.ADMIN, UserRole.SCREENING):
        raise HTTPException(status_code=403, detail="Only the MLRO (Screening/Admin) can sign off")

    for field, value in payload.items():
        setattr(rec, field, value)

    # Stamp the screener on first touch of any screening field.
    if _SCREENING_FIELDS & payload.keys():
        if rec.screened_by_id is None:
            rec.screened_by_id = user.id
        if rec.screening_status not in (ScreeningStatus.NOT_STARTED.value, None) and not rec.screening_date:
            rec.screening_date = date.today()

    if new_mlro in _MLRO_LOCKED_STATUSES and new_mlro != old_mlro:
        rec.mlro_signoff_by_id = user.id
        rec.mlro_signoff_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(rec)

    # Notifications on entry into a new state.
    if rec.vistra_status != old_vistra:
        if rec.vistra_status == VistraStatus.SUBMITTED.value:
            msg = f"{case.case_uid} ({case.company_name}) submitted to Vistra compliance."
            for role in (UserRole.SCREENING, UserRole.ADMIN):
                notification_service.notify_role(db, role, msg, "vistra_submitted", link=f"/cases/{case_id}", case_id=case_id)
        elif rec.vistra_status == VistraStatus.QUERY_RAISED.value:
            q = (rec.vistra_query_text or "").strip()
            msg = f"Vistra raised a query on {case.case_uid} ({case.company_name})." + (f" {q}" if q else "")
            if case.rm_id:
                notification_service.notify_user(db, case.rm_id, msg, "vistra_query", link=f"/cases/{case_id}", case_id=case_id)
            notification_service.notify_role(db, UserRole.OPS, msg, "vistra_query", link=f"/cases/{case_id}", case_id=case_id)
        elif rec.vistra_status == VistraStatus.APPROVED.value:
            _notify_rm_and_admin(db, case, f"Vistra compliance approved {case.case_uid} ({case.company_name}) — proceed to incorporation.", "vistra_approved")
        elif rec.vistra_status == VistraStatus.REJECTED.value:
            _notify_rm_and_admin(db, case, f"Vistra compliance rejected {case.case_uid} ({case.company_name}).", "vistra_rejected")

    if rec.mlro_signoff_status != old_mlro and rec.mlro_signoff_status in _MLRO_LOCKED_STATUSES:
        verb = "signed off" if rec.mlro_signoff_status == MLROSignoffStatus.SIGNED_OFF.value else "rejected"
        _notify_rm_and_admin(db, case, f"MLRO {verb} the CDD file for {case.case_uid} ({case.company_name}).", "mlro_signoff")

    return rec
