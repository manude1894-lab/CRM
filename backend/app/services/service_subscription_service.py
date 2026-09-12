"""Service layer: ServiceSubscription (recurring services per entity)."""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import ServiceSubscription, Case, User
from app.schemas.service_subscription import ServiceSubscriptionCreate, ServiceSubscriptionUpdate
from app.services import access_control


def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not access_control.user_can_access_case(case, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def list_for_case(db: Session, case_id: int, user: User) -> list[ServiceSubscription]:
    _get_case_for_write(db, case_id, user)
    return (
        db.query(ServiceSubscription)
        .filter(ServiceSubscription.case_id == case_id)
        .order_by(ServiceSubscription.id.desc())
        .all()
    )


def create(db: Session, case_id: int, data: ServiceSubscriptionCreate, user: User) -> ServiceSubscription:
    _get_case_for_write(db, case_id, user)
    sub = ServiceSubscription(case_id=case_id, **data.model_dump())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _get(db: Session, sub_id: int, user: User) -> ServiceSubscription:
    sub = db.query(ServiceSubscription).filter(ServiceSubscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Service subscription not found")
    _get_case_for_write(db, sub.case_id, user)
    return sub


def update(db: Session, sub_id: int, data: ServiceSubscriptionUpdate, user: User) -> ServiceSubscription:
    sub = _get(db, sub_id, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sub, field, value)
    db.commit()
    db.refresh(sub)
    return sub


def delete(db: Session, sub_id: int, user: User) -> None:
    sub = _get(db, sub_id, user)
    db.delete(sub)
    db.commit()
