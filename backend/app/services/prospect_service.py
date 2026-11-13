"""Service layer: Prospect (BRD §4A) — every new client starts as a prospect."""
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Prospect, ProspectStatus, User, UserRole, Account
from app.schemas.prospect import ProspectCreate, ProspectUpdate, DuplicateMatch
from app.utils.uid import next_uid
from app.utils.fuzzy_match import top_matches
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.audit import log_event
from app.auth.permissions import has_permission
from app.services import access_control, notification_service

MAX_ASSIGNOR_WORDS = 250


def account_norm(name: Optional[str]) -> str:
    return " ".join((name or "").split()).lower()


def _apply_rbac_filter(query, user: User):
    # An RM sees their team's prospects and the unassigned pool (so they can take one themselves);
    # a Prospecting Coordinator and the central desks see everything.
    if not access_control.sees_all_prospects(user):
        query = query.filter((Prospect.owner_id.in_(access_control.team_user_ids(query.session, user.id))) | (Prospect.owner_id.is_(None)))
    return query


def list_prospects(db: Session, user: User, status: Optional[str] = None) -> list[Prospect]:
    query = _apply_rbac_filter(db.query(Prospect), user)
    if status:
        query = query.filter(Prospect.status == status)
    return query.order_by(Prospect.id.desc()).all()


def get_prospect(db: Session, prospect_id: int, user: User) -> Prospect:
    p = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prospect not found")
    if not access_control.sees_all_prospects(user) and p.owner_id is not None \
            and p.owner_id not in access_control.team_user_ids(db, user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    return p


def find_similar(db: Session, name: str, exclude_id: Optional[int] = None) -> list[DuplicateMatch]:
    prospect_candidates = db.query(Prospect.id, Prospect.company_name)
    if exclude_id:
        prospect_candidates = prospect_candidates.filter(Prospect.id != exclude_id)
    matches = [
        DuplicateMatch(id=cid, company_name=cname, score=score, source="prospect")
        for cid, cname, score in top_matches(name, prospect_candidates.all())
    ]
    matches += [
        DuplicateMatch(id=cid, company_name=cname, score=score, source="client")
        for cid, cname, score in top_matches(name, db.query(Account.id, Account.company_name).all())
    ]
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:5]


def _same_name(db: Session, name: str, exclude_id: Optional[int] = None) -> Optional[str]:
    """BRD §3, §10 step 3 — the existing client or open prospect with exactly this name, described for
    the user. A Dropped prospect doesn't count, and a converted one is already found through its client."""
    from app.services import account_service  # local: account_service imports this module's models
    client = account_service._same_name_query(db, name).first()
    if client:
        return f"A client named '{client.company_name}' already exists ({client.client_id or client.account_uid})"
    q = db.query(Prospect).filter(func.lower(func.trim(Prospect.company_name)) == account_service._norm(name),
                                  Prospect.status != ProspectStatus.DROPPED.value, Prospect.converted_account_id.is_(None))
    if exclude_id:
        q = q.filter(Prospect.id != exclude_id)
    prospect = q.first()
    return f"A prospect named '{prospect.company_name}' already exists ({prospect.prospect_uid})" if prospect else None


def _check_duplicate(db: Session, name: str, allow: bool, reason: Optional[str], user: User,
                     exclude_id: Optional[int] = None) -> Optional[str]:
    """Blocks an ordinary duplicate. Same exception route as client creation: Compliance, with a reason.
    Returns the reason when the duplicate is allowed."""
    found = _same_name(db, name, exclude_id)
    if not found:
        return None
    if not allow:
        raise HTTPException(status_code=409, detail=f"{found}. Compliance can create it anyway with a reason.")
    if not has_permission(user, "client.approve"):
        raise HTTPException(status_code=403, detail="Only Compliance (CO / MLRO) or an Admin can create a duplicate prospect")
    reason = (reason or "").strip()
    if len(reason) < 10:
        raise HTTPException(status_code=400, detail="Give a meaningful reason (at least 10 characters) for creating a duplicate prospect")
    return reason


def create_prospect(db: Session, data: ProspectCreate, user: User) -> Prospect:
    """Entered by the Prospecting Team Coordinator (who may leave it unassigned or pick the RM) or by an
    RM directly (assigned to themselves)."""
    override = _check_duplicate(db, data.company_name, data.allow_duplicate, data.duplicate_reason, user)
    payload = data.model_dump(exclude={"allow_duplicate", "duplicate_reason"})
    if not access_control.is_prospect_coordinator(user):
        payload["owner_id"] = user.id if user.role == UserRole.RM else payload.get("owner_id")
    p = Prospect(prospect_uid=next_uid(db, Prospect, "prospect_uid", "PROS"), **payload)
    if p.owner_id:
        p.assigned_by_id, p.assigned_at = user.id, datetime.now(timezone.utc)
    db.add(p)
    db.flush()
    log_event(db, "create", f"Prospect {p.prospect_uid} ({p.company_name}) created", subject_type="Prospect", subject_id=p.id)
    if override:
        log_event(db, "duplicate_override", f"Duplicate prospect '{p.company_name}' created by exception: {override}",
                  subject_type="Prospect", subject_id=p.id, changes={"reason": override})
    db.commit()
    db.refresh(p)
    return p


def assign_prospect(db: Session, prospect_id: int, rm_id: int, comments: Optional[str], user: User) -> Prospect:
    """BRD §4A — the Prospecting Team Coordinator assigns an RM (after discussing with the Unit
    Managers), or an RM assigns the prospect to themselves. Assignor's comments are optional (≤ 250 words)."""
    p = get_prospect(db, prospect_id, user)
    if p.converted_account_id:
        raise HTTPException(status_code=400, detail="A client has already been created from this prospect")
    if not access_control.is_prospect_coordinator(user):
        if rm_id != user.id:
            raise HTTPException(status_code=403, detail="Only the Prospecting Coordinator can assign a prospect to someone else")
        if p.owner_id not in (None, user.id):
            raise HTTPException(status_code=403, detail="This prospect is already assigned to another RM")
    rm = db.get(User, rm_id)
    if rm is None or not rm.is_active:
        raise HTTPException(status_code=400, detail="RM not found")
    comments = (comments or "").strip() or None
    if comments and len(comments.split()) > MAX_ASSIGNOR_WORDS:
        raise HTTPException(status_code=400, detail=f"Assignor's comments can be at most {MAX_ASSIGNOR_WORDS} words")
    previous = p.owner_id
    p.owner_id, p.assigned_by_id, p.assigned_at, p.assignor_comments = rm.id, user.id, datetime.now(timezone.utc), comments
    # Triam UAT 26-10-2026: the Proposal Sent Date is stamped when the prospect is submitted (UAE date), not typed.
    if p.proposal_sent_date is None:
        p.proposal_sent_date = datetime.now(ZoneInfo("Asia/Dubai")).date()
    log_event(db, "assign", f"Prospect {p.prospect_uid} assigned to {rm.name}", subject_type="Prospect", subject_id=p.id,
              changes={"owner_id": {"old": previous, "new": rm.id}, "comments": comments})
    db.commit()
    db.refresh(p)
    if rm.id != user.id:
        notification_service.notify_user(db, rm.id, f"{user.name} assigned prospect {p.prospect_uid} ({p.company_name}) to you."
                                         + (f" Comments: {comments}" if comments else ""), "prospect_assigned")
    return p


def assert_ready_for_client(db: Session, prospect_id: int, user: User) -> Prospect:
    """A new client can only be created from an assigned prospect that has no client yet."""
    p = get_prospect(db, prospect_id, user)
    if p.converted_account_id:
        raise HTTPException(status_code=400, detail=f"A client has already been created from prospect {p.prospect_uid}")
    if not p.owner_id:
        raise HTTPException(status_code=400, detail=f"Assign prospect {p.prospect_uid} to an RM before creating the client")
    if p.status == ProspectStatus.DROPPED.value:
        raise HTTPException(status_code=400, detail=f"Prospect {p.prospect_uid} is marked Dropped")
    return p


def update_prospect(db: Session, prospect_id: int, data: ProspectUpdate, user: User) -> Prospect:
    p = get_prospect(db, prospect_id, user)
    update = data.model_dump(exclude_unset=True, exclude={"allow_duplicate", "duplicate_reason"})
    new_name = update.get("company_name")
    if new_name and account_norm(new_name) != account_norm(p.company_name):
        override = _check_duplicate(db, new_name, data.allow_duplicate, data.duplicate_reason, user, exclude_id=p.id)
        if override:
            log_event(db, "duplicate_override", f"Prospect {p.prospect_uid} renamed to the duplicate name '{new_name}' by exception: {override}",
                      subject_type="Prospect", subject_id=p.id, changes={"reason": override})
    new_owner = update.pop("owner_id", p.owner_id)
    if new_owner != p.owner_id:
        if not access_control.is_prospect_coordinator(user):
            raise HTTPException(status_code=403, detail="Use Assign to change the prospect's RM")
        p.owner_id, p.assigned_by_id, p.assigned_at = new_owner, user.id, datetime.now(timezone.utc) if new_owner else None
    for field, value in update.items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p
