"""Client profile lifecycle + maker-checker (BRD §11, §12 steps 10–14, §14, §15). See p2-design.md.

All status changes go through here; `profile_status` can no longer be edited directly.

    New ──save──> WIP ──Submit──> Awaiting Approval ──Approve──> Approved ──Activate──> Active
                   ^                 │  │                                     │   ^
                   └──Reject/Withdraw┘  │                       Deactivate/Reactivate (Inactive)
                                                               Mark for Exit ─> Marked for Exit ─> Exited
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.permissions import has_permission
from app.models import Account, ApprovalRequest, ApprovalStatus, User
from app.schemas.account import AccountRead
from app.schemas.account_party import AccountPartyRead
from app.services import access_control, master_service, notification_service

NEW, WIP, AWAITING, APPROVED, ACTIVE = "New", "WIP", "Awaiting Approval", "Approved", "Active"
INACTIVE, MARKED_EXIT, EXITED = "Inactive", "Marked for Exit", "Exited"

MIN_REJECT_TEXT = 15


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_status(acc: Account, status: str, user: User) -> None:
    acc.profile_status = status
    acc.status_updated_at = _now()
    acc.status_updated_by_id = user.id


def pending_request(db: Session, account_id: int) -> Optional[ApprovalRequest]:
    return (db.query(ApprovalRequest)
            .filter(ApprovalRequest.account_id == account_id, ApprovalRequest.status == ApprovalStatus.PENDING.value)
            .order_by(ApprovalRequest.id.desc()).first())


# ─── Hooks used by other services ───────────────────────────────────────────

def assert_editable(acc: Account) -> None:
    """While a profile is with the checker it's frozen, so they approve exactly what was submitted."""
    if acc.profile_status == AWAITING:
        raise HTTPException(status_code=409, detail="This client is awaiting approval and is locked. Withdraw the submission to make changes.")
    if acc.profile_status == EXITED:
        raise HTTPException(status_code=409, detail="This client has exited and can no longer be changed.")


def note_edit(acc: Account, user: User) -> None:
    """BRD §11 — the first save after creation moves a New profile to WIP (work in progress)."""
    if acc.profile_status == NEW:
        _set_status(acc, WIP, user)


# ─── Checks ─────────────────────────────────────────────────────────────────

def _can_see(db, acc, user) -> bool:
    return access_control.user_can_access_account(db, acc, user)


def _is_checker_for(user: User, req: Optional[ApprovalRequest]) -> bool:
    return has_permission(user, "client.approve") and (req is None or req.maker_id != user.id)


def _missing(acc: Account) -> list[dict]:
    from app.services.account_service import missing_mandatory  # local: account_service imports this module
    return missing_mandatory(acc)


def allowed_actions(db: Session, acc: Account, user: User) -> list[dict]:
    """Every action valid from the current status, with whether *this* user may do it and why not.
    Drives the workflow buttons, so the UI never offers something the server would refuse."""
    status = acc.profile_status
    req = pending_request(db, acc.id) if status == AWAITING else None
    approver = has_permission(user, "client.approve")
    out = []

    def add(action, label, ok, why=None, code=403):
        # code: HTTP status the server returns if this action is attempted while not allowed.
        out.append({"action": action, "label": label, "allowed": bool(ok), "reason": None if ok else why,
                    "_code": None if ok else code})

    if status in (NEW, WIP):
        missing = _missing(acc)
        add("submit", "Submit for approval", not missing,
            f"{len(missing)} mandatory field{'s' if len(missing) != 1 else ''} still missing", code=400)
    elif status == AWAITING:
        is_maker = req is not None and req.maker_id == user.id
        add("approve", "Approve", _is_checker_for(user, req),
            "You submitted this profile — another approver must review it" if is_maker and approver else "Needs an approver (CO / MLRO)")
        add("reject", "Reject", _is_checker_for(user, req),
            "You submitted this profile — another approver must review it" if is_maker and approver else "Needs an approver (CO / MLRO)")
        add("withdraw", "Withdraw submission", is_maker or approver, "Only the submitter or an approver can withdraw")
    elif status == APPROVED:
        add("activate", "Activate", True)
    elif status == ACTIVE:
        add("deactivate", "Mark Inactive", approver, "Needs an approver (CO / MLRO)")
        add("mark_exit", "Mark for Exit", True)
    elif status == INACTIVE:
        add("reactivate", "Reactivate", approver, "Needs an approver (CO / MLRO)")
        add("mark_exit", "Mark for Exit", True)
    elif status == MARKED_EXIT:
        last = _last_status_actor(db, acc)
        add("confirm_exit", "Confirm Exit", approver and last != user.id,
            "Another approver must confirm the exit you marked" if approver else "Needs an approver (CO / MLRO)")
        add("cancel_exit", "Cancel Exit", True)
    return out


def _last_status_actor(db: Session, acc: Account) -> Optional[int]:
    return acc.status_updated_by_id


def _require(db: Session, acc: Account, user: User, action: str) -> None:
    if not _can_see(db, acc, user):
        raise HTTPException(status_code=403, detail="Access denied")
    match = next((a for a in allowed_actions(db, acc, user) if a["action"] == action), None)
    if match is None:
        raise HTTPException(status_code=409, detail=f"'{action}' isn't possible while the client is {acc.profile_status}")
    if not match["allowed"]:
        raise HTTPException(status_code=match["_code"], detail=match["reason"])


def _snapshot(acc: Account) -> dict:
    return {
        "account": AccountRead.model_validate(acc).model_dump(mode="json"),
        "parties": [AccountPartyRead.model_validate(p).model_dump(mode="json") for p in acc.parties],
    }


def _approvers(db: Session) -> list[User]:
    return [u for u in db.query(User).filter(User.is_active == True).all() if has_permission(u, "client.approve")]  # noqa: E712


def _label(acc: Account) -> str:
    return f"{acc.company_name} ({acc.client_id or acc.account_uid})"


# ─── Actions ────────────────────────────────────────────────────────────────

def submit(db: Session, acc: Account, user: User, comment: Optional[str] = None) -> ApprovalRequest:
    """BRD §12 step 11 — the maker submits; every mandatory field must be complete."""
    _require(db, acc, user, "submit")
    req = ApprovalRequest(account_id=acc.id, request_type="client_profile", status=ApprovalStatus.PENDING.value,
                          maker_id=user.id, maker_comment=(comment or "").strip() or None, snapshot=_snapshot(acc))
    db.add(req)
    _set_status(acc, AWAITING, user)
    db.flush()
    log_event(db, "submit", f"Client {_label(acc)} submitted for approval", subject_type="Account",
              subject_id=acc.id, account_id=acc.id, changes={"request_id": req.id})
    db.commit()
    for u in _approvers(db):
        if u.id != user.id:
            notification_service.notify_user(db, u.id, f"{user.name} submitted client {_label(acc)} for approval.", "client_submitted")
    return req


def approve(db: Session, acc: Account, user: User, comment: Optional[str] = None) -> ApprovalRequest:
    """BRD §12 steps 12–13 — an authorised checker (not the maker) approves."""
    _require(db, acc, user, "approve")
    req = pending_request(db, acc.id)
    req.status, req.checker_id, req.decided_at = ApprovalStatus.APPROVED.value, user.id, _now()
    req.reason_text = (comment or "").strip() or None
    _set_status(acc, APPROVED, user)
    log_event(db, "approve", f"Client {_label(acc)} approved", subject_type="Account", subject_id=acc.id,
              account_id=acc.id, changes={"request_id": req.id, "comment": req.reason_text})
    db.commit()
    if req.maker_id:
        notification_service.notify_user(db, req.maker_id, f"{user.name} approved client {_label(acc)}.", "client_approved")
    return req


def reject(db: Session, acc: Account, user: User, reason_code: str, reason_text: str) -> ApprovalRequest:
    """BRD §12 step 13 / §14 — rejection needs a reason from the list and a meaningful explanation."""
    _require(db, acc, user, "reject")
    reason_text = (reason_text or "").strip()
    if not reason_code:
        raise HTTPException(status_code=400, detail="Choose a rejection reason")
    master_service.assert_valid(db, "rejection_reason", reason_code, "Rejection reason")
    if len(reason_text) < MIN_REJECT_TEXT:
        raise HTTPException(status_code=400, detail=f"Explain what needs fixing (at least {MIN_REJECT_TEXT} characters) so the maker can act on it")
    req = pending_request(db, acc.id)
    req.status, req.checker_id, req.decided_at = ApprovalStatus.REJECTED.value, user.id, _now()
    req.reason_code, req.reason_text = reason_code, reason_text
    _set_status(acc, WIP, user)
    log_event(db, "reject", f"Client {_label(acc)} rejected: {reason_code} — {reason_text}", subject_type="Account",
              subject_id=acc.id, account_id=acc.id, changes={"request_id": req.id, "reason_code": reason_code, "reason_text": reason_text})
    db.commit()
    if req.maker_id:
        notification_service.notify_user(db, req.maker_id, f"{user.name} rejected client {_label(acc)}: {reason_code} — {reason_text}", "client_rejected")
    return req


def withdraw(db: Session, acc: Account, user: User) -> ApprovalRequest:
    _require(db, acc, user, "withdraw")
    req = pending_request(db, acc.id)
    req.status, req.decided_at = ApprovalStatus.WITHDRAWN.value, _now()
    _set_status(acc, WIP, user)
    log_event(db, "withdraw", f"Submission of {_label(acc)} withdrawn", subject_type="Account", subject_id=acc.id,
              account_id=acc.id, changes={"request_id": req.id})
    db.commit()
    return req


_STATUS_ACTIONS = {
    "activate": ACTIVE, "deactivate": INACTIVE, "reactivate": ACTIVE,
    "mark_exit": MARKED_EXIT, "cancel_exit": ACTIVE, "confirm_exit": EXITED,
}


def change_status(db: Session, acc: Account, user: User, action: str, reason: Optional[str] = None) -> Account:
    if action not in _STATUS_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown action '{action}'")
    _require(db, acc, user, action)
    reason = (reason or "").strip() or None
    if action in ("mark_exit", "deactivate") and not reason:
        raise HTTPException(status_code=400, detail="Give a reason")
    old = acc.profile_status
    _set_status(acc, _STATUS_ACTIONS[action], user)
    log_event(db, action, f"Client {_label(acc)}: {old} → {acc.profile_status}" + (f" ({reason})" if reason else ""),
              subject_type="Account", subject_id=acc.id, account_id=acc.id, changes={"reason": reason} if reason else None)
    db.commit()
    db.refresh(acc)
    return acc


# ─── Reads ──────────────────────────────────────────────────────────────────

def history(db: Session, account_id: int) -> list[ApprovalRequest]:
    return (db.query(ApprovalRequest).filter(ApprovalRequest.account_id == account_id)
            .order_by(ApprovalRequest.id.desc()).all())


def inbox(db: Session, user: User, status: str = ApprovalStatus.PENDING.value) -> list[ApprovalRequest]:
    """Checker inbox — requests on clients this user may see."""
    reqs = db.query(ApprovalRequest).filter(ApprovalRequest.status == status).order_by(ApprovalRequest.submitted_at).all()
    return [r for r in reqs if _can_see(db, r.account, user)]
