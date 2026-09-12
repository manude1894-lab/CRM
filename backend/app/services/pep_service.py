"""Service layer: PEPAssessment — standalone PEP / EDD assessment per party.

Follows aml_service: the sign-off (senior_management_approved / risk_conclusion) is
MLRO-only (Screening/Admin); the assessor is stamped on create.
"""
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import PEPAssessment, Case, User, UserRole
from app.schemas.pep_assessment import PEPAssessmentCreate, PEPAssessmentUpdate
from app.services import access_control


def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not access_control.user_can_access_case(case, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def list_for_case(db: Session, case_id: int) -> list[PEPAssessment]:
    return (
        db.query(PEPAssessment)
        .filter(PEPAssessment.case_id == case_id)
        .order_by(PEPAssessment.id.desc())
        .all()
    )


def get_assessment(db: Session, assessment_id: int) -> PEPAssessment:
    a = db.query(PEPAssessment).filter(PEPAssessment.id == assessment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="PEP assessment not found")
    return a


def _coerce(payload: dict) -> dict:
    """Enum values -> their string, so plain String columns store the label."""
    return {k: (v.value if hasattr(v, "value") else v) for k, v in payload.items()}


def create_assessment(db: Session, data: PEPAssessmentCreate, user: User) -> PEPAssessment:
    _get_case_for_write(db, data.case_id, user)
    payload = _coerce(data.model_dump())
    approving = payload.get("senior_management_approved") or payload.get("risk_conclusion")
    if approving and user.role not in (UserRole.ADMIN, UserRole.SCREENING):
        raise HTTPException(status_code=403, detail="Only the MLRO (Screening/Admin) can sign off a PEP assessment")
    a = PEPAssessment(**payload, assessed_by_id=user.id)
    if not a.assessment_date:
        a.assessment_date = date.today()
    if approving:
        a.approved_by_id = user.id
        a.approved_at = datetime.now(timezone.utc)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def update_assessment(db: Session, assessment_id: int, data: PEPAssessmentUpdate, user: User) -> PEPAssessment:
    a = get_assessment(db, assessment_id)
    _get_case_for_write(db, a.case_id, user)
    payload = _coerce(data.model_dump(exclude_unset=True))

    touches_signoff = (
        ("senior_management_approved" in payload and payload["senior_management_approved"] != a.senior_management_approved)
        or ("risk_conclusion" in payload and payload["risk_conclusion"] != a.risk_conclusion)
    )
    if touches_signoff and user.role not in (UserRole.ADMIN, UserRole.SCREENING):
        raise HTTPException(status_code=403, detail="Only the MLRO (Screening/Admin) can sign off a PEP assessment")

    for field, value in payload.items():
        setattr(a, field, value)

    if touches_signoff:
        a.approved_by_id = user.id
        a.approved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(a)
    return a


def delete_assessment(db: Session, assessment_id: int, user: User) -> None:
    a = get_assessment(db, assessment_id)
    if user.role != UserRole.ADMIN and a.assessed_by_id != user.id:
        raise HTTPException(status_code=403, detail="Only the assessor or an Admin can delete a PEP assessment")
    db.delete(a)
    db.commit()
