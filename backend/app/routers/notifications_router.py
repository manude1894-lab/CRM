"""In-app notifications router (bell icon, polling)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import NotificationRead
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    unread_only: bool = False, skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return notification_service.list_notifications(db, user.id, unread_only, skip, limit)


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"unread_count": notification_service.unread_count(db, user.id)}


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return notification_service.mark_read(db, user.id, notification_id)


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = notification_service.mark_all_read(db, user.id)
    return {"marked_read": count}
