"""Service layer: in-app Notification rows + best-effort email delivery."""
import asyncio
import logging

from sqlalchemy.orm import Session

from app.models import Notification, User, UserRole
from app.config import settings
from app.services.email_service import send_notification_email
from app.services.sms_service import send_sms

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
    account_id: int | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        account_id=account_id,
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
        # BRD §17 — SMS for the notification types Triam chooses (Compliance decisions by default).
        if user.mobile and notification_type in {t.strip() for t in settings.SMS_NOTIFICATION_TYPES.split(",")}:
            send_sms(user.mobile, f"TRIAM: {message}")
    return notification


def notify_role(
    db: Session,
    role: UserRole,
    message: str,
    notification_type: str,
    link: str | None = None,
    account_id: int | None = None,
) -> list[Notification]:
    users = db.query(User).filter(User.role == role, User.is_active == True).all()  # noqa: E712
    return [
        notify_user(db, u.id, message, notification_type, link=link, account_id=account_id)
        for u in users
    ]


def notify_permission(
    db: Session,
    flag: str,
    message: str,
    notification_type: str,
    link: str | None = None,
    account_id: int | None = None,
) -> list[Notification]:
    """Notify every active user holding a permission flag (e.g. client.approve = Compliance)."""
    from app.auth.permissions import has_permission  # local import: auth imports models
    users = [u for u in db.query(User).filter(User.is_active == True).all() if has_permission(u, flag)]  # noqa: E712
    return [notify_user(db, u.id, message, notification_type, link=link, account_id=account_id) for u in users]


def resolve(db: Session, account_id: int, *notification_types: str) -> None:
    """The work an alert asked for is done (e.g. the client was approved): mark everyone's unread alerts
    of that type for the client as read, so the bell only shows what still needs doing."""
    from datetime import datetime, timezone
    db.query(Notification).filter(Notification.account_id == account_id, Notification.notification_type.in_(notification_types),
                                  Notification.read_at.is_(None)).update({Notification.read_at: datetime.now(timezone.utc)},
                                                                          synchronize_session=False)
    db.commit()


def has_unresolved_notification(db: Session, account_id: int, notification_type: str) -> bool:
    """Dedup helper for scheduled jobs: skip if an unread notification of this type already exists for the client."""
    return db.query(Notification).filter(
        Notification.account_id == account_id,
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
