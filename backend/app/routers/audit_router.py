"""Audit log router (BRD §13, §15). Read-only by design — there are no write endpoints."""
import csv
import io
from datetime import date
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import User
from app.schemas.audit import AuditEntryRead
from app.services import audit_service, account_service

router = APIRouter(tags=["Audit"])


@router.get("/audit", response_model=list[AuditEntryRead], summary="Global audit log")
def list_audit(
    response: Response,
    account_id: Optional[int] = None,
    subject_type: Optional[str] = None,
    subject_id: Optional[int] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("audit.view")),
):
    rows, total = audit_service.list_entries(
        db, account_id=account_id, subject_type=subject_type, subject_id=subject_id, user_id=user_id,
        action=action, date_from=date_from, date_to=date_to, skip=skip, limit=limit,
    )
    response.headers["X-Total-Count"] = str(total)
    return [AuditEntryRead.from_row(r) for r in rows]


EXPORT_LIMIT = 50000
_TZ = ZoneInfo("Asia/Dubai")


def _changes_text(changes: Optional[dict]) -> str:
    if not changes:
        return ""
    out = []
    for field, value in changes.items():
        if isinstance(value, list) and len(value) == 2:
            out.append(f"{field}: {'' if value[0] is None else value[0]} -> {'' if value[1] is None else value[1]}")
        else:
            out.append(f"{field}: {value}")
    return "; ".join(out)


@router.get("/audit/export", summary="Activity report: the audit log as a CSV file (same filters as the log)")
def export_audit(
    account_id: Optional[int] = None,
    subject_type: Optional[str] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("audit.view")),
):
    """BRD §2 — activity reports for administration and user administration (users, roles, master
    data and every other recorded change), downloadable for review."""
    rows, _ = audit_service.list_entries(
        db, account_id=account_id, subject_type=subject_type, user_id=user_id, action=action,
        date_from=date_from, date_to=date_to, skip=0, limit=EXPORT_LIMIT,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date and time (UAE)", "User", "Action", "Record type", "Record ID", "Client record", "Summary", "Changes"])
    for r in rows:
        w.writerow([r.occurred_at.astimezone(_TZ).strftime("%d %m %Y %H:%M:%S") if r.occurred_at else "",
                    r.user.name if r.user else "System", r.action, r.subject_type, r.subject_id or "",
                    r.account_id or "", r.summary or "", _changes_text(r.changes)])
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="triam-crm-activity-{date.today():%Y-%m-%d}.csv"'})


@router.get("/accounts/{account_id}/audit", response_model=list[AuditEntryRead], summary="One client's history")
def account_history(
    account_id: int,
    response: Response,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Anyone who can see the client can see its history (same visibility rule as the client itself).
    account_service.get_account(db, account_id, user)
    rows, total = audit_service.list_entries(db, account_id=account_id, skip=skip, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    return [AuditEntryRead.from_row(r) for r in rows]
