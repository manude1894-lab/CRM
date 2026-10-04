"""Audit log router (BRD §13, §15). Read-only by design — there are no write endpoints."""
from datetime import date
from typing import Optional

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
