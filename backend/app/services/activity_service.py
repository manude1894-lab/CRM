"""Service layer: Activity business logic.

BRD §17 — activities (including Visit Reports and Call Reports) belong to the client; linking a case
is optional. A user sees an activity they (or their team) own, or one on a client they can see.
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from fastapi import HTTPException
from typing import Optional

from app.models import Account, Activity, ActivityType, Case, User, UserRole
from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.utils.uid import next_uid
from app.services import access_control

# Visit / Call Report fields that must be filled (BRD §17 report templates).
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
    case_id: Optional[int] = None,
    activity_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    search: Optional[str] = None,
    account_id: Optional[int] = None,
) -> tuple[list[Activity], int]:
    query = db.query(Activity)
    if _restricted(user):
        query = query.filter(_visibility(db, user))

    if account_id:
        query = query.filter(Activity.account_id == account_id)
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
    t = activity_type.value if hasattr(activity_type, "value") else activity_type
    missing = [label for field, label in REPORT_REQUIRED.get(t, []) if not (values.get(field) or "").strip()]
    if missing:
        raise HTTPException(status_code=400, detail=f"{t}: {', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required")


def create_activity(db: Session, data: ActivityCreate, user: User) -> Activity:
    case = account = None
    if data.case_id:
        case = db.query(Case).filter(Case.id == data.case_id).first()
        if not case:
            raise HTTPException(status_code=400, detail="Case does not exist")
        if not access_control.user_can_access_case(case, user):
            raise HTTPException(status_code=403, detail="You don't have access to this case")
    account_id = data.account_id or (case.account_id if case else None)
    if account_id:
        account = db.get(Account, account_id)
        if not account:
            raise HTTPException(status_code=400, detail="Client does not exist")
        if not access_control.user_can_access_account(db, account, user):
            raise HTTPException(status_code=403, detail="You don't have access to this client")
        if case and case.account_id and case.account_id != account.id:
            raise HTTPException(status_code=400, detail="The case belongs to a different client")
    if not case and not account:
        raise HTTPException(status_code=400, detail="Choose the client (and optionally the case) this activity is for")
    _check_report(data.activity_type, data.model_dump())

    owner_id = data.owner_id or user.id
    if _restricted(user):
        owner_id = user.id
    payload = data.model_dump(exclude={"owner_id", "account_id", "company_name"})
    act = Activity(
        activity_uid=next_uid(db, Activity, "activity_uid", "ACT"),
        **payload,
        account_id=account_id,
        company_name=data.company_name or (account.company_name if account else case.company_name),
        owner_id=owner_id,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


def update_activity(db: Session, activity_id: int, data: ActivityUpdate, user: User) -> Activity:
    act = get_activity(db, activity_id, user)
    update_data = data.model_dump(exclude_unset=True)
    if _restricted(user):
        update_data.pop("owner_id", None)
    for field, value in update_data.items():
        setattr(act, field, value)
    _check_report(act.activity_type, {c: getattr(act, c) for c in ("client_contact", "location")})
    db.commit()
    db.refresh(act)
    return act


def delete_activity(db: Session, activity_id: int, user: User) -> None:
    act = get_activity(db, activity_id, user)
    if _restricted(user) and act.owner_id not in access_control.team_user_ids(db, user.id):
        raise HTTPException(status_code=403, detail="Only the owner (or their supervisor) can delete this activity")
    db.delete(act)
    db.commit()
