"""Compliance approval of cases (Triam's Compliance review desk, extending BRD §15 maker-checker).

    create case ──> Pending Approval ──Approve──> Approved (pipeline can move)
                        │ Reject / Withdraw
                        v
                     Returned ──(maker fixes, Resubmit)──> Pending Approval

Once approved, an edit to the case (PATCH /cases/{id}) is not applied straight away: it becomes a
"case_amendment" request with a before/after view. The live case changes when Compliance approves.
Stage moves and invoicing keep their own gates (CDD approved, invoice paid) and are not re-approved.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.permissions import has_permission
from app.models import ApprovalRequest, ApprovalStatus, Case, User
from app.schemas.case import CaseRead, CaseUpdate
from app.services import access_control, client_workflow_service as wf, master_service, notification_service

PENDING, APPROVED, RETURNED = "Pending Approval", "Approved", "Returned"
CREATION, AMENDMENT = "case_creation", "case_amendment"

_LABELS = {
    "company_name": "Company Name", "rm_id": "Relationship Manager", "ops_owner_id": "Ops Owner",
    "account_id": "Client", "invoice_amount": "Invoice Amount", "service_type": "Service",
    "onboarding_date": "Onboarding Date", "license_received_date": "Licence Received Date",
    "license_expiry_date": "Licence Expiry Date", "engagement_letter_sent_date": "Engagement Letter Sent",
    "engagement_letter_signed_date": "Engagement Letter Signed",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _label(case: Case) -> str:
    return f"{case.case_uid} ({case.company_name})"


def _show(db: Session, field: str, value):
    if value in (None, ""):
        return None
    if field in ("rm_id", "ops_owner_id"):
        u = db.get(User, value)
        return u.name if u else value
    if field == "account_id":
        from app.models import Account
        a = db.get(Account, value)
        return f"{a.company_name} ({a.client_id or a.account_uid})" if a else value
    return value


def _request(db: Session, case_id: int, types=(CREATION, AMENDMENT)) -> Optional[ApprovalRequest]:
    return (db.query(ApprovalRequest)
            .filter(ApprovalRequest.case_id == case_id, ApprovalRequest.request_type.in_(types),
                    ApprovalRequest.status == ApprovalStatus.PENDING.value)
            .order_by(ApprovalRequest.id.desc()).first())


def pending_request(db: Session, case_id: int) -> Optional[ApprovalRequest]:
    return _request(db, case_id)


def _snapshot(case: Case) -> dict:
    return CaseRead.model_validate(case).model_dump(mode="json")


def _notify_approvers(db: Session, user: User, msg: str, kind: str, case: Case) -> None:
    for u in wf._approvers(db):
        if u.id != user.id:
            notification_service.notify_user(db, u.id, msg, kind, link=f"/cases/{case.id}", case_id=case.id)


# ─── Hooks used by case_service ─────────────────────────────────────────────

def on_created(db: Session, case: Case, user: User) -> None:
    """A new case goes to Compliance before any work starts on it."""
    case.compliance_status = PENDING
    req = ApprovalRequest(case_id=case.id, account_id=case.account_id, request_type=CREATION,
                          status=ApprovalStatus.PENDING.value, maker_id=user.id, snapshot=_snapshot(case))
    db.add(req)
    db.flush()
    log_event(db, "submit", f"New case {_label(case)} sent to Compliance for approval", subject_type="Case",
              subject_id=case.id, account_id=case.account_id, changes={"request_id": req.id})


def notify_created(db: Session, case: Case, user: User) -> None:
    _notify_approvers(db, user, f"{user.name} created case {_label(case)} — awaiting Compliance approval.", "case_submitted", case)


def assert_can_progress(case: Case) -> None:
    """Pipeline moves and invoicing wait for Compliance approval of the case."""
    if case.compliance_status == PENDING:
        raise HTTPException(status_code=409, detail="This case is awaiting Compliance approval. It can move through the pipeline once approved.")
    if case.compliance_status == RETURNED:
        raise HTTPException(status_code=409, detail="This case was returned by Compliance. Update it and resubmit for approval first.")


def route_update(db: Session, case: Case, update_data: dict, user: User) -> Optional[ApprovalRequest]:
    """Called before an edit is applied. Returns a request when the edit must wait for Compliance
    (approved case), None when it may be applied directly (case returned to the maker)."""
    if case.compliance_status == PENDING:
        raise HTTPException(status_code=409, detail="This case is awaiting Compliance approval and is locked. Withdraw it to make changes.")
    if case.compliance_status == RETURNED:
        return None
    if _request(db, case.id, (AMENDMENT,)) is not None:
        raise HTTPException(status_code=409, detail="A change to this case is already awaiting Compliance approval. It is locked until that is decided.")
    changes = []
    for field, new in update_data.items():
        old = getattr(case, field, None)
        old_v = old.value if hasattr(old, "value") else old
        new_v = new.value if hasattr(new, "value") else new
        if str(old_v if old_v is not None else "") != str(new_v if new_v is not None else ""):
            changes.append({"field": field, "label": _LABELS.get(field) or field.replace("_", " ").capitalize(),
                            "old": _show(db, field, old_v), "new": _show(db, field, new_v)})
    if not changes:
        return None  # nothing actually changes; let the caller no-op
    payload = CaseUpdate(**update_data).model_dump(mode="json", exclude_unset=True)
    req = ApprovalRequest(case_id=case.id, account_id=case.account_id, request_type=AMENDMENT,
                          status=ApprovalStatus.PENDING.value, maker_id=user.id, payload=payload,
                          changes={"case": changes, "count": len(changes)}, snapshot=_snapshot(case))
    db.add(req)
    db.flush()
    log_event(db, "amend_submit", f"Change to case {_label(case)} sent to Compliance ({len(changes)} field(s))",
              subject_type="Case", subject_id=case.id, account_id=case.account_id, changes={"request_id": req.id})
    db.commit()
    _notify_approvers(db, user, f"{user.name} changed case {_label(case)} — awaiting Compliance approval.", "case_amendment_submitted", case)
    return req


# ─── Checker / maker actions ────────────────────────────────────────────────

def _get_pending(db: Session, case: Case) -> ApprovalRequest:
    req = pending_request(db, case.id)
    if req is None:
        raise HTTPException(status_code=409, detail="Nothing on this case is awaiting Compliance approval")
    return req


def _assert_checker(user: User, req: ApprovalRequest) -> None:
    if not has_permission(user, "client.approve"):
        raise HTTPException(status_code=403, detail="Needs an approver (CO / MLRO)")
    if req.maker_id == user.id:
        raise HTTPException(status_code=403, detail="You submitted this — another approver must review it")


def approve(db: Session, case: Case, user: User, comment: Optional[str] = None) -> ApprovalRequest:
    from app.services import case_service  # local: case_service imports this module
    req = _get_pending(db, case)
    _assert_checker(user, req)
    req.status, req.checker_id, req.decided_at = ApprovalStatus.APPROVED.value, user.id, _now()
    req.reason_text = (comment or "").strip() or None
    if req.request_type == CREATION:
        case.compliance_status = APPROVED
        log_event(db, "approve", f"Case {_label(case)} approved by Compliance", subject_type="Case", subject_id=case.id,
                  account_id=case.account_id, changes={"request_id": req.id, "comment": req.reason_text})
        db.commit()
    else:
        log_event(db, "amend_approve", f"Change to case {_label(case)} approved and applied", subject_type="Case",
                  subject_id=case.id, account_id=case.account_id, changes={"request_id": req.id, "diff": req.changes})
        case_service.apply_case_update(db, case, CaseUpdate(**(req.payload or {})), user)  # commits
    if req.maker_id:
        what = "new case" if req.request_type == CREATION else "change to case"
        notification_service.notify_user(db, req.maker_id, f"{user.name} approved your {what} {_label(case)}.", "case_approved",
                                         link=f"/cases/{case.id}", case_id=case.id)
    return req


def reject(db: Session, case: Case, user: User, reason_code: str, reason_text: str) -> ApprovalRequest:
    req = _get_pending(db, case)
    _assert_checker(user, req)
    reason_text = (reason_text or "").strip()
    if not reason_code:
        raise HTTPException(status_code=400, detail="Choose a rejection reason")
    master_service.assert_valid(db, "rejection_reason", reason_code, "Rejection reason")
    if len(reason_text) < wf.MIN_REJECT_TEXT:
        raise HTTPException(status_code=400, detail=f"Explain what needs fixing (at least {wf.MIN_REJECT_TEXT} characters) so the maker can act on it")
    req.status, req.checker_id, req.decided_at = ApprovalStatus.REJECTED.value, user.id, _now()
    req.reason_code, req.reason_text = reason_code, reason_text
    if req.request_type == CREATION:
        case.compliance_status = RETURNED
    log_event(db, "reject", f"{'Case' if req.request_type == CREATION else 'Change to case'} {_label(case)} rejected by Compliance: {reason_code} — {reason_text}",
              subject_type="Case", subject_id=case.id, account_id=case.account_id,
              changes={"request_id": req.id, "reason_code": reason_code, "reason_text": reason_text})
    db.commit()
    if req.maker_id:
        notification_service.notify_user(db, req.maker_id, f"{user.name} rejected {_label(case)}: {reason_code} — {reason_text}", "case_rejected",
                                         link=f"/cases/{case.id}", case_id=case.id)
    return req


def withdraw(db: Session, case: Case, user: User) -> ApprovalRequest:
    req = _get_pending(db, case)
    if req.maker_id != user.id and not has_permission(user, "client.approve"):
        raise HTTPException(status_code=403, detail="Only the submitter or an approver can withdraw")
    req.status, req.decided_at = ApprovalStatus.WITHDRAWN.value, _now()
    if req.request_type == CREATION:
        case.compliance_status = RETURNED
    log_event(db, "withdraw", f"Compliance request on case {_label(case)} withdrawn", subject_type="Case",
              subject_id=case.id, account_id=case.account_id, changes={"request_id": req.id})
    db.commit()
    return req


def resubmit(db: Session, case: Case, user: User, comment: Optional[str] = None) -> ApprovalRequest:
    if case.compliance_status != RETURNED:
        raise HTTPException(status_code=409, detail="Only a case returned by Compliance can be resubmitted")
    case.compliance_status = PENDING
    req = ApprovalRequest(case_id=case.id, account_id=case.account_id, request_type=CREATION,
                          status=ApprovalStatus.PENDING.value, maker_id=user.id, snapshot=_snapshot(case),
                          maker_comment=(comment or "").strip() or None)
    db.add(req)
    db.flush()
    log_event(db, "submit", f"Case {_label(case)} resubmitted to Compliance", subject_type="Case", subject_id=case.id,
              account_id=case.account_id, changes={"request_id": req.id})
    db.commit()
    _notify_approvers(db, user, f"{user.name} resubmitted case {_label(case)} for Compliance approval.", "case_submitted", case)
    return req


def state(db: Session, case: Case, user: User) -> dict:
    req = pending_request(db, case.id)
    approver = has_permission(user, "client.approve")
    actions = []
    if req is not None:
        if approver and req.maker_id != user.id:
            actions += ["approve", "reject"]
        if approver or req.maker_id == user.id:
            actions.append("withdraw")
    elif case.compliance_status == RETURNED:
        actions.append("resubmit")
    history = (db.query(ApprovalRequest).filter(ApprovalRequest.case_id == case.id)
               .order_by(ApprovalRequest.id.desc()).all())
    return {"compliance_status": case.compliance_status, "request": req, "actions": actions, "history": history}


def can_see(db: Session, req: ApprovalRequest, user: User) -> bool:
    if req.case is not None:
        return access_control.user_can_access_case(req.case, user)
    return req.account is not None and access_control.user_can_access_account(db, req.account, user)
