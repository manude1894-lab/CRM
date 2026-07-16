"""Service layer: Activity business logic."""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException
from typing import Optional

from app.models import Activity, Case, User, UserRole
from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.utils.uid import next_uid


def list_activities(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    case_id: Optional[int] = None,
    activity_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    search: Optional[str] = None,
) -> tuple[list[Activity], int]:
    query = db.query(Activity)
    if user.role == UserRole.RM:
        query = query.filter(Activity.owner_id == user.id)

    if case_id:
        query = query.filter(Activity.case_id == case_id)
    if activity_type:
        query = query.filter(Activity.activity_type == activity_type)
    if owner_id:
        query = query.filter(Activity.owner_id == owner_id)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Activity.summary.ilike(pattern),
            Activity.outcome.ilike(pattern),
            Activity.company_name.ilike(pattern),
        ))

    total = query.count()
    items = query.order_by(Activity.activity_date.desc(), Activity.id.desc()).offset(skip).limit(limit).all()
    return items, total


def get_activity(db: Session, activity_id: int, user: User) -> Activity:
    act = db.query(Activity).filter(Activity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    if user.role == UserRole.RM and act.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return act


def create_activity(db: Session, data: ActivityCreate, user: User) -> Activity:
    case = db.query(Case).filter(Case.id == data.case_id).first()
    if not case:
        raise HTTPException(status_code=400, detail="Case does not exist")
    if user.role == UserRole.RM and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="You don't own this case")

    owner_id = data.owner_id or user.id
    if user.role == UserRole.RM:
        owner_id = user.id

    payload = data.model_dump(exclude={"owner_id"})
    act = Activity(
        activity_uid=next_uid(db, Activity, "activity_uid", "ACT"),
        **payload,
        owner_id=owner_id,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


def update_activity(db: Session, activity_id: int, data: ActivityUpdate, user: User) -> Activity:
    act = get_activity(db, activity_id, user)
    update_data = data.model_dump(exclude_unset=True)
    if user.role == UserRole.RM:
        update_data.pop("owner_id", None)
    for field, value in update_data.items():
        setattr(act, field, value)
    db.commit()
    db.refresh(act)
    return act


def delete_activity(db: Session, activity_id: int, user: User) -> None:
    act = get_activity(db, activity_id, user)
    if user.role == UserRole.RM and act.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    db.delete(act)
    db.commit()
