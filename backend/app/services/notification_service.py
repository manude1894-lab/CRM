"""Service layer: in-app Notification rows + best-effort email delivery."""
import asyncio
import logging

from sqlalchemy.orm import Session

from app.models import Notification, User, UserRole
from app.services.email_service import send_notification_email

logger = logging.getLogger("ezeetech.notifications")


def _send_email_best_effort(to_email: str, subject: str, message: str) -> None:
    try:
        asyncio.run(send_notification_email(to_email, subject, message))
    except Exception:
        logger.exception("Notification email dispatch failed for %s", to_email)


def notify_user(
    db: Session,
    user_id: int,
    message: str,
    notification_type: str,
    link: str | None = None,
    case_id: int | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        case_id=case_id,
        notification_type=notification_type,
        message=message,
        link=link,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        _send_email_best_effort(user.email, f"TRIAM: {notification_type.replace('_', ' ').title()}", message)
    return notification


def notify_role(
    db: Session,
    role: UserRole,
    message: str,
    notification_type: str,
    link: str | None = None,
    case_id: int | None = None,
) -> list[Notification]:
    users = db.query(User).filter(User.role == role, User.is_active == True).all()
    return [
        notify_user(db, u.id, message, notification_type, link=link, case_id=case_id)
        for u in users
    ]


def has_unresolved_notification(db: Session, case_id: int, notification_type: str) -> bool:
    """Dedup helper for scheduled jobs: skip if an unread notification of this type already exists for the case."""
    return db.query(Notification).filter(
        Notification.case_id == case_id,
        Notification.notification_type == notification_type,
        Notification.read_at.is_(None),
    ).first() is not None


def list_notifications(db: Session, user_id: int, unread_only: bool = False, skip: int = 0, limit: int = 50) -> list[Notification]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()


def unread_count(db: Session, user_id: int) -> int:
    return db.query(Notification).filter(Notification.user_id == user_id, Notification.read_at.is_(None)).count()


def mark_read(db: Session, user_id: int, notification_id: int) -> Notification:
    from datetime import datetime, timezone
    from fastapi import HTTPException

    notification = db.query(Notification).filter(
        Notification.id == notification_id, Notification.user_id == user_id
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_read(db: Session, user_id: int) -> int:
    from datetime import datetime, timezone

    count = db.query(Notification).filter(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    ).update({"read_at": datetime.now(timezone.utc)})
    db.commit()
    return count
