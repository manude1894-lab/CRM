"""Service layer: Activity business logic.

BRD §15 — Visit Reports and Call Reports belong to the client. A user sees an activity they (or their
team) own, or one on a client they can see.

Triam 23-11-2026 (S T Krishna): the report has three buttons, Cancel, Save Draft and Save the Report. A draft can be
changed by its writer (or their supervisor); the saved report is final and stays as written, so past reports can be
reviewed at any time. A correction to a final report is a note added beside it, with who and when.
"""
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, select
from fastapi import HTTPException
from typing import Optional

from app.audit import log_event
from app.models import Account, Activity, ActivityCorrection, ActivityStatus, ActivityType, User, UserRole
from app.schemas.activity import ActivityCreate, ActivityUpdate

EDITABLE = (ActivityStatus.DRAFT, ActivityStatus.PLANNED, ActivityStatus.OVERDUE)  # not yet the final report
# The list's status filter: Draft (still being written), Final, Cancelled.
STATUS_FILTER = {"Draft": EDITABLE, "Final": (ActivityStatus.COMPLETED,), "Cancelled": (ActivityStatus.CANCELLED,)}
from app.utils.uid import next_uid
from app.services import access_control

# Visit / Call Report fields that must be filled.
REPORT_REQUIRED = {
    ActivityType.VISIT_REPORT.value: [("client_contact", "Client contact met"), ("location", "Location")],
    ActivityType.CALL_REPORT.value: [("client_contact", "Client contact spoken to")],
}


def _restricted(user: User) -> bool:
    return user.role == UserRole.RM


def _visibility(db: Session, user: User):
    team = access_control.team_user_ids(db, user.id)
    clauses = [Activity.owner_id.in_(team)]
    acc_clause = access_control.account_visibility_clause(db, user)
    if acc_clause is None:
        clauses.append(Activity.account_id.isnot(None))
    else:
        clauses.append(Activity.account_id.in_(select(Account.id).where(acc_clause)))
    return or_(*clauses)


def list_activities(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    activity_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    search: Optional[str] = None,
    account_id: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> tuple[list[Activity], int]:
    query = db.query(Activity).options(selectinload(Activity.owner), selectinload(Activity.finalised_by),
                                       selectinload(Activity.corrections).selectinload(ActivityCorrection.author))
    if _restricted(user):
        query = query.filter(_visibility(db, user))

    if account_id:
        query = query.filter(Activity.account_id == account_id)
    if activity_type:
        query = query.filter(Activity.activity_type == activity_type)
    if owner_id:
        query = query.filter(Activity.owner_id == owner_id)
    if status in STATUS_FILTER:
        query = query.filter(Activity.status.in_(STATUS_FILTER[status]))
    if date_from:
        query = query.filter(Activity.activity_date >= date_from)
    if date_to:
        query = query.filter(Activity.activity_date <= date_to)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Activity.summary.ilike(pattern),
            Activity.outcome.ilike(pattern),
            Activity.company_name.ilike(pattern),
            Activity.client_contact.ilike(pattern),
        ))

    total = query.count()
    items = query.order_by(Activity.activity_date.desc(), Activity.id.desc()).offset(skip).limit(limit).all()
    return items, total


def _can_see(db: Session, act: Activity, user: User) -> bool:
    if not _restricted(user) or act.owner_id in access_control.team_user_ids(db, user.id):
        return True
    acc = db.get(Account, act.account_id) if act.account_id else None
    return bool(acc and access_control.user_can_access_account(db, acc, user))


def get_activity(db: Session, activity_id: int, user: User) -> Activity:
    act = db.query(Activity).filter(Activity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    if not _can_see(db, act, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return act


def _check_report(activity_type, values: dict) -> None:
    """What the final report must have. A draft may be unfinished."""
    t = activity_type.value if hasattr(activity_type, "value") else activity_type
    missing = [label for field, label in REPORT_REQUIRED.get(t, []) if not (values.get(field) or "").strip()]
    if not (values.get("summary") or "").strip():
        missing.insert(0, "Summary")
    if missing:
        raise HTTPException(status_code=400, detail=f"{t}: {', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required")


def create_activity(db: Session, data: ActivityCreate, user: User) -> Activity:
    if not data.account_id:
        raise HTTPException(status_code=400, detail="Choose the client this activity is for")
    account = db.get(Account, data.account_id)
    if not account:
        raise HTTPException(status_code=400, detail="Client does not exist")
    if not access_control.user_can_access_account(db, account, user):
        raise HTTPException(status_code=403, detail="You don't have access to this client")
    if data.final:
        _check_report(data.activity_type, data.model_dump())

    owner_id = data.owner_id or user.id
    if _restricted(user):
        owner_id = user.id
    payload = data.model_dump(exclude={"owner_id", "account_id", "company_name", "final"})
    payload["summary"] = (payload.get("summary") or "").strip()
    act = Activity(
        activity_uid=next_uid(db, Activity, "activity_uid", "ACT"),
        **payload,
        account_id=account.id,
        company_name=data.company_name or account.company_name,
        owner_id=owner_id,
        status=ActivityStatus.DRAFT,
    )
    db.add(act)
    db.flush()
    if data.final:
        _finalise(db, act, user)
    db.commit()
    db.refresh(act)
    return act


def _finalise(db: Session, act: Activity, user: User) -> None:
    act.status, act.finalised_at, act.finalised_by_id = ActivityStatus.COMPLETED, datetime.now(timezone.utc), user.id
    log_event(db, "activity_final", f"{act.activity_type.value} {act.activity_uid} saved as the final report for {act.company_name}",
              user_id=user.id, subject_type="Activity", subject_id=act.id, account_id=act.account_id)


def _assert_writer(db: Session, act: Activity, user: User, what: str) -> None:
    """Only the writer of a report, their supervisor or an administrator changes it."""
    if user.role == UserRole.ADMIN:
        return
    if act.owner_id not in access_control.team_user_ids(db, user.id):
        raise HTTPException(status_code=403, detail=f"Only the writer of this report (or their supervisor) can {what}")


def update_activity(db: Session, activity_id: int, data: ActivityUpdate, user: User) -> Activity:
    act = get_activity(db, activity_id, user)
    _assert_writer(db, act, user, "change it")
    if act.status == ActivityStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="This report is final and kept as written. Add a correction note instead")
    if act.status == ActivityStatus.CANCELLED:
        raise HTTPException(status_code=409, detail="This report was cancelled")
    update_data = data.model_dump(exclude_unset=True, exclude={"final"})
    if _restricted(user):
        update_data.pop("owner_id", None)
    for field, value in update_data.items():
        setattr(act, field, (value or "").strip() if field == "summary" else value)
    if data.final:
        _check_report(act.activity_type, {c: getattr(act, c) for c in ("client_contact", "location", "summary")})
        _finalise(db, act, user)
    db.commit()
    db.refresh(act)
    return act


def add_correction(db: Session, activity_id: int, text: str, user: User) -> Activity:
    """A note beside a final report; the report itself stays as written."""
    act = get_activity(db, activity_id, user)
    _assert_writer(db, act, user, "add a correction")
    if act.status != ActivityStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Only a final report takes correction notes; edit the draft instead")
    db.add(ActivityCorrection(activity_id=act.id, author_id=user.id, text=text.strip()))
    log_event(db, "activity_correction", f"Correction note added to {act.activity_uid} ({act.company_name})",
              user_id=user.id, subject_type="Activity", subject_id=act.id, account_id=act.account_id)
    db.commit()
    db.refresh(act)
    return act


def cancel_activity(db: Session, activity_id: int, reason: str, user: User) -> None:
    act = get_activity(db, activity_id, user)
    if _restricted(user) and act.owner_id not in access_control.team_user_ids(db, user.id):
        raise HTTPException(status_code=403, detail="Only the owner (or their supervisor) can cancel this activity")
    if act.status == ActivityStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="This activity is already cancelled")
    act.status, act.cancel_reason = ActivityStatus.CANCELLED, reason.strip()
    db.commit()
