"""Service layer: ActionPoint — the shared WIP task board.

Every authenticated user sees the whole board (it mirrors the single "Action Points -
WIP" sheet in Triam's tracker). Anyone can create/edit; only the creator, the owner
or an Admin can delete.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import ActionPoint, ActionPointStatus, User, UserRole
from app.schemas.action_point import ActionPointCreate, ActionPointUpdate


def list_action_points(db: Session, user: User, status: Optional[str] = None) -> list[ActionPoint]:
    q = db.query(ActionPoint)
    if status:
        q = q.filter(ActionPoint.status == status)
    return q.order_by(ActionPoint.status, ActionPoint.id.desc()).all()


def get_action_point(db: Session, ap_id: int) -> ActionPoint:
    ap = db.query(ActionPoint).filter(ActionPoint.id == ap_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="Action point not found")
    return ap


def _apply_status_side_effects(ap: ActionPoint) -> None:
    if ap.status == ActionPointStatus.DONE.value:
        if not ap.completed_date:
            ap.completed_date = date.today()
    else:
        ap.completed_date = None


def create_action_point(db: Session, data: ActionPointCreate, user: User) -> ActionPoint:
    payload = data.model_dump()
    ap = ActionPoint(**payload, created_by_id=user.id)
    _apply_status_side_effects(ap)
    db.add(ap)
    db.commit()
    db.refresh(ap)
    return ap


def update_action_point(db: Session, ap_id: int, data: ActionPointUpdate, user: User) -> ActionPoint:
    ap = get_action_point(db, ap_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ap, field, value)
    _apply_status_side_effects(ap)
    db.commit()
    db.refresh(ap)
    return ap


def delete_action_point(db: Session, ap_id: int, user: User) -> None:
    ap = get_action_point(db, ap_id)
    if user.role != UserRole.ADMIN and user.id not in (ap.created_by_id, ap.owner_id):
        raise HTTPException(status_code=403, detail="Only the creator, owner or an Admin can delete this action point")
    db.delete(ap)
    db.commit()
