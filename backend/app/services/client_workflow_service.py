"""Client profile lifecycle + maker-checker (BRD §11, §12 steps 10–14, §14, §15). See p2-design.md.

All status changes go through here; `profile_status` can no longer be edited directly.

New clients are approved in two steps (Triam BRD mark-up §7–§10). While Awaiting Approval the
pending request's `stage` says where it is:
  Compliance — the MLRO completes the CDD section and approves with comments (Client ID issued)
  Approver   — the Approver gives the final approval with comments → Approved
A rejection at either step returns the client to the RM (WIP) with the reason.

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
MAX_COMMENT_WORDS = 250
STAGE_COMPLIANCE, STAGE_APPROVER = "Compliance", "Approver"


def _comment(text: Optional[str], label: str) -> str:
    """The mandatory comment boxes (RM/Sales, Compliance, Approver): required, up to 250 words."""
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail=f"{label} are required")
    if len(text.split()) > MAX_COMMENT_WORDS:
        raise HTTPException(status_code=400, detail=f"{label} can be at most {MAX_COMMENT_WORDS} words")
    return text


def stage_of(req: Optional[ApprovalRequest]) -> Optional[str]:
    if req is None:
        return None
    return req.stage or STAGE_COMPLIANCE


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


def _is_final_approver_for(user: User, req: Optional[ApprovalRequest]) -> bool:
    return has_permission(user, "client.final_approve") and (req is None or req.maker_id != user.id)


def _missing(acc: Account) -> list[dict]:
    from app.services.account_service import missing_mandatory  # local: account_service imports this module
    return missing_mandatory(acc)


def _missing_cdd(acc: Account) -> list[dict]:
    from app.services.account_service import missing_cdd
    return missing_cdd(acc)


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
        own = "You submitted this profile — someone else must review it"
        if stage_of(req) == STAGE_APPROVER:
            final = has_permission(user, "client.final_approve")
            why = own if is_maker and final else "Needs the Approver"
            add("approve", "Final approval", _is_final_approver_for(user, req), why)
            add("reject", "Reject", _is_final_approver_for(user, req), why)
        else:
            why = own if is_maker and approver else "Needs Compliance (MLRO)"
            checker = _is_checker_for(user, req)
            missing_cdd = _missing_cdd(acc) if checker else []
            if checker and missing_cdd:
                add("approve", "Approve (Compliance)", False,
                    "Complete the CDD section first: " + ", ".join(m["label"] for m in missing_cdd), code=400)
            else:
                add("approve", "Approve (Compliance)", checker, why)
            add("reject", "Reject", checker, why)
            add("withdraw", "Withdraw submission", is_maker or approver, "Only the submitter or Compliance can withdraw")
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

def submit(db: Session, acc: Account, user: User, comment: Optional[str] = None, kyc_declared: bool = False) -> ApprovalRequest:
    """BRD §12 step 11 — the maker submits; every mandatory field must be complete. Triam mark-up §7:
    with mandatory RM/Sales comments and the declaration that KYC verification is done."""
    _require(db, acc, user, "submit")
    comment = _comment(comment, "RM/Sales comments")
    if not kyc_declared:
        raise HTTPException(status_code=400, detail="Confirm that the client's KYC verification is done as per the verification procedures")
    req = ApprovalRequest(account_id=acc.id, request_type="client_profile", status=ApprovalStatus.PENDING.value,
                          maker_id=user.id, maker_comment=comment, snapshot=_snapshot(acc),
                          stage=STAGE_COMPLIANCE, kyc_declared=True)
    db.add(req)
    _set_status(acc, AWAITING, user)
    db.flush()
    log_event(db, "submit", f"Client {_label(acc)} submitted for approval", subject_type="Account",
              subject_id=acc.id, account_id=acc.id, changes={"request_id": req.id})
    db.commit()
    for u in _approvers(db):
        if u.id != user.id:
            notification_service.notify_user(db, u.id, f"{user.name} submitted client {_label(acc)} for Compliance review.", "client_submitted")
    return req


def approve(db: Session, acc: Account, user: User, comment: Optional[str] = None) -> ApprovalRequest:
    """Compliance step: the MLRO approves with comments; the Client ID is issued and the client goes to
    the Approver. Approver step: final approval with comments → Approved (Triam mark-up §10)."""
    _require(db, acc, user, "approve")
    req = pending_request(db, acc.id)
    if stage_of(req) == STAGE_COMPLIANCE:
        comment = _comment(comment, "Compliance comments")
        req.compliance_checker_id, req.compliance_comment, req.compliance_decided_at = user.id, comment, _now()
        req.stage = STAGE_APPROVER
        _issue_client_id(db, acc)
        req.snapshot = _snapshot(acc)  # now includes the CDD section Compliance completed
        log_event(db, "compliance_approve", f"Client {_label(acc)} approved by Compliance — now with the Approver",
                  subject_type="Account", subject_id=acc.id, account_id=acc.id, changes={"request_id": req.id, "comment": comment})
        db.commit()
        for u in _final_approvers(db):
            if u.id != user.id:
                notification_service.notify_user(db, u.id, f"Client {_label(acc)} passed Compliance and needs your final approval.", "client_submitted")
        if req.maker_id:
            notification_service.notify_user(db, req.maker_id, f"Compliance ({user.name}) approved client {_label(acc)}; it is now with the Approver.", "client_approved")
        return req

    comment = _comment(comment, "Approver's comments")
    req.status, req.checker_id, req.decided_at = ApprovalStatus.APPROVED.value, user.id, _now()
    req.reason_text = comment
    _issue_client_id(db, acc)
    _set_status(acc, APPROVED, user)
    log_event(db, "approve", f"Client {_label(acc)} approved", subject_type="Account", subject_id=acc.id,
              account_id=acc.id, changes={"request_id": req.id, "comment": comment})
    db.commit()
    if req.maker_id:
        notification_service.notify_user(db, req.maker_id, f"{user.name} gave the final approval for client {_label(acc)}.", "client_approved")
    return req


def _issue_client_id(db: Session, acc: Account) -> None:
    """Triam mark-up §18: the Unique Client ID is issued once Compliance approves the new client."""
    if not acc.client_id and acc.anchor_entity:
        from app.services.account_service import next_client_id
        acc.client_id = next_client_id(db, acc.anchor_entity)


def _final_approvers(db: Session) -> list[User]:
    return [u for u in db.query(User).filter(User.is_active == True).all() if has_permission(u, "client.final_approve")]  # noqa: E712


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
    step = stage_of(req)
    req.status, req.checker_id, req.decided_at = ApprovalStatus.REJECTED.value, user.id, _now()
    req.reason_code, req.reason_text = reason_code, reason_text
    _set_status(acc, WIP, user)
    log_event(db, "reject", f"Client {_label(acc)} rejected by {step}: {reason_code} — {reason_text}", subject_type="Account",
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
    """Client review history: onboarding submissions and amendments (drafts never reached Compliance)."""
    return (db.query(ApprovalRequest)
            .filter(ApprovalRequest.account_id == account_id,
                    ApprovalRequest.request_type.in_(("client_profile", "client_amendment")),
                    ~ApprovalRequest.status.in_((ApprovalStatus.DRAFT.value, ApprovalStatus.DISCARDED.value)))
            .order_by(ApprovalRequest.id.desc()).all())


def inbox(db: Session, user: User, status: str = ApprovalStatus.PENDING.value,
          request_type: Optional[str] = None) -> list[ApprovalRequest]:
    """The Compliance inbox — every kind of request (new client, client amendment, new case, case
    amendment) on records this user may see."""
    from app.services import case_approval_service
    q = db.query(ApprovalRequest).filter(ApprovalRequest.status == status)
    if request_type:
        q = q.filter(ApprovalRequest.request_type == request_type)
    reqs = q.order_by(ApprovalRequest.submitted_at).all()
    return [r for r in reqs if case_approval_service.can_see(db, r, user) and _in_my_queue(r, user, status)]


def _in_my_queue(r: ApprovalRequest, user: User, status: str) -> bool:
    """Compliance sees everything; an Approver sees new clients at (or past) the Approver step."""
    if has_permission(user, "client.approve"):
        return True
    if not has_permission(user, "client.final_approve") or r.request_type != "client_profile":
        return False
    return status != ApprovalStatus.PENDING.value or stage_of(r) == STAGE_APPROVER
