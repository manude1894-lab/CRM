"""Service layer: reading the audit log (BRD §13, §15). Writing happens in app.audit."""
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models import AuditLog


def list_entries(
    db: Session,
    *,
    account_id: Optional[int] = None,
    subject_type: Optional[str] = None,
    subject_id: Optional[int] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[AuditLog], int]:
    q = db.query(AuditLog)
    if account_id is not None:
        q = q.filter(AuditLog.account_id == account_id)
    if subject_type:
        q = q.filter(AuditLog.subject_type == subject_type)
    if subject_id is not None:
        q = q.filter(AuditLog.subject_id == subject_id)
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if date_from:
        q = q.filter(AuditLog.occurred_at >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.filter(AuditLog.occurred_at < datetime.combine(date_to + timedelta(days=1), time.min))
    total = q.count()
    rows = (q.options(joinedload(AuditLog.user))
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .offset(skip).limit(min(limit, 500)).all())
    return rows, total
