"""Service layer: ServiceFeedback (staff-logged client feedback)."""
from datetime import date

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import ServiceFeedback, Case, User
from app.schemas.service_feedback import ServiceFeedbackCreate
from app.services import access_control


def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not access_control.user_can_access_case(case, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def list_for_case(db: Session, case_id: int, user: User) -> list[ServiceFeedback]:
    _get_case_for_write(db, case_id, user)
    return (
        db.query(ServiceFeedback)
        .filter(ServiceFeedback.case_id == case_id)
        .order_by(ServiceFeedback.id.desc())
        .all()
    )


def create(db: Session, case_id: int, data: ServiceFeedbackCreate, user: User) -> ServiceFeedback:
    _get_case_for_write(db, case_id, user)
    payload = data.model_dump()
    if not payload.get("feedback_date"):
        payload["feedback_date"] = date.today()
    fb = ServiceFeedback(case_id=case_id, recorded_by_id=user.id, **payload)
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def delete(db: Session, feedback_id: int, user: User) -> None:
    fb = db.query(ServiceFeedback).filter(ServiceFeedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback entry not found")
    _get_case_for_write(db, fb.case_id, user)
    db.delete(fb)
    db.commit()
