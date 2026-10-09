"""Service layer: Prospect (pre-Case proposal tracking)."""
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Prospect, ProspectStatus, User, UserRole, Account
from app.schemas.prospect import ProspectCreate, ProspectUpdate, ProspectConvertRequest, DuplicateMatch
from app.schemas.case import CaseCreate
from app.utils.uid import next_uid
from app.utils.fuzzy_match import top_matches
from datetime import datetime, timezone

from app.audit import log_event
from app.auth.permissions import has_permission
from app.services import case_service, access_control, notification_service

MAX_ASSIGNOR_WORDS = 250


def _apply_rbac_filter(query, user: User):
    # An RM sees their team's prospects and the unassigned pool (so they can take one themselves);
    # a Prospecting Coordinator sees everything.
    if user.role == UserRole.RM and not has_permission(user, "prospect.assign"):
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
    if user.role == UserRole.RM and not has_permission(user, "prospect.assign") and p.owner_id is not None \
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


def create_prospect(db: Session, data: ProspectCreate, user: User) -> Prospect:
    """Entered by the Prospecting Team Coordinator (who may leave it unassigned or pick the RM) or by an
    RM directly (assigned to themselves)."""
    payload = data.model_dump()
    coordinator = has_permission(user, "prospect.assign")
    if not coordinator:
        payload["owner_id"] = user.id if user.role == UserRole.RM else payload.get("owner_id")
    p = Prospect(prospect_uid=next_uid(db, Prospect, "prospect_uid", "PROS"), **payload)
    if p.owner_id:
        p.assigned_by_id, p.assigned_at = user.id, datetime.now(timezone.utc)
    db.add(p)
    db.flush()
    log_event(db, "create", f"Prospect {p.prospect_uid} ({p.company_name}) created", subject_type="Prospect", subject_id=p.id)
    db.commit()
    db.refresh(p)
    return p


def assign_prospect(db: Session, prospect_id: int, rm_id: int, comments: Optional[str], user: User) -> Prospect:
    """Triam mark-up §4A — the Prospecting Team Coordinator assigns an RM (after discussing with the Unit
    Managers), or an RM assigns the prospect to themselves. Assignor's comments are optional (≤ 250 words)."""
    p = get_prospect(db, prospect_id, user)
    if p.converted_account_id:
        raise HTTPException(status_code=400, detail="A client has already been created from this prospect")
    coordinator = has_permission(user, "prospect.assign")
    if not coordinator:
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
    if p.status == ProspectStatus.LOST.value:
        raise HTTPException(status_code=400, detail=f"Prospect {p.prospect_uid} is marked Lost")
    return p


def update_prospect(db: Session, prospect_id: int, data: ProspectUpdate, user: User) -> Prospect:
    p = get_prospect(db, prospect_id, user)
    update = data.model_dump(exclude_unset=True)
    new_owner = update.pop("owner_id", p.owner_id)
    if new_owner != p.owner_id:
        if not has_permission(user, "prospect.assign"):
            raise HTTPException(status_code=403, detail="Use Assign to change the prospect's RM")
        p.owner_id, p.assigned_by_id, p.assigned_at = new_owner, user.id, datetime.now(timezone.utc) if new_owner else None
    for field, value in update.items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


def delete_prospect(db: Session, prospect_id: int, user: User) -> None:
    p = get_prospect(db, prospect_id, user)
    db.delete(p)
    db.commit()


def convert_to_case(db: Session, prospect_id: int, data: ProspectConvertRequest, user: User):
    p = get_prospect(db, prospect_id, user)
    if p.converted_case_id:
        raise HTTPException(status_code=400, detail="This prospect has already been converted")
    case = case_service.create_case(db, CaseCreate(
        company_name=p.company_name,
        source="Referral",
        introducer=p.source,
        jurisdiction=data.jurisdiction,
        service_type=data.service_type or "Company Formation",
        rm_id=data.rm_id or p.owner_id,
        notes=f"Converted from prospect {p.prospect_uid}.",
    ), user)
    p.converted_case_id = case.id
    p.status = ProspectStatus.WON.value
    db.commit()
    db.refresh(p)
    return case
