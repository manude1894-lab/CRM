"""Compliance router — client onboarding workflow (BRD §11, §12 steps 11–14, §15), client amendments
(§13), Compliance approval of cases, and the single Compliance inbox. Rules live in
client_workflow_service, amendment_service and case_approval_service."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import User
from app.schemas.account import AccountRead
from app.schemas.approval import (
    AmendmentState, ApprovalRead, ApproveRequest, CaseComplianceState, RejectOrComment, RejectRequest,
    StatusActionRequest, SubmitRequest, WorkflowAction, WorkflowState,
)
from app.services import account_service, amendment_service as amend, case_approval_service as case_ok
from app.services import case_service, client_workflow_service as wf

router = APIRouter(tags=["Client Workflow"])


def _state(db: Session, acc, user: User) -> WorkflowState:
    updater = db.get(User, acc.status_updated_by_id) if acc.status_updated_by_id else None
    return WorkflowState(
        status=acc.profile_status,
        status_updated_at=acc.status_updated_at,
        status_updated_by=updater.name if updater else None,
        locked=acc.profile_status in (wf.AWAITING, wf.EXITED),
        actions=[WorkflowAction(**{k: v for k, v in a.items() if not k.startswith("_")}) for a in wf.allowed_actions(db, acc, user)],
        history=[ApprovalRead.from_row(r) for r in wf.history(db, acc.id)],
    )


@router.get("/accounts/{account_id}/workflow", response_model=WorkflowState, summary="Status, allowed actions and review history")
def get_workflow(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _state(db, account_service.get_account(db, account_id, user), user)


@router.post("/accounts/{account_id}/submit", response_model=WorkflowState)
def submit(account_id: int, data: SubmitRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    acc = account_service.get_account(db, account_id, user)
    wf.submit(db, acc, user, data.comment)
    return _state(db, acc, user)


@router.post("/accounts/{account_id}/approve", response_model=WorkflowState)
def approve(account_id: int, data: ApproveRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    acc = account_service.get_account(db, account_id, user)
    wf.approve(db, acc, user, data.comment)
    return _state(db, acc, user)


@router.post("/accounts/{account_id}/reject", response_model=WorkflowState)
def reject(account_id: int, data: RejectRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    acc = account_service.get_account(db, account_id, user)
    wf.reject(db, acc, user, data.reason_code, data.reason_text)
    return _state(db, acc, user)


@router.post("/accounts/{account_id}/withdraw", response_model=WorkflowState)
def withdraw(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    acc = account_service.get_account(db, account_id, user)
    wf.withdraw(db, acc, user)
    return _state(db, acc, user)


@router.post("/accounts/{account_id}/status", response_model=WorkflowState, summary="Activate / Deactivate / Reactivate / Mark for Exit / Cancel / Confirm Exit")
def status_action(account_id: int, data: StatusActionRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    acc = account_service.get_account(db, account_id, user)
    wf.change_status(db, acc, user, data.action, data.reason)
    return _state(db, acc, user)


@router.get("/approvals", response_model=list[ApprovalRead], summary="Compliance inbox (all request types)")
def approvals_inbox(status: str = "Pending", request_type: Optional[str] = None, db: Session = Depends(get_db),
                    user: User = Depends(require_permission("client.approve"))):
    return [ApprovalRead.from_row(r) for r in wf.inbox(db, user, status, request_type)]


# ─── Client amendments (BRD §13) ────────────────────────────────────────────

def _amendment(db: Session, acc, user: User) -> AmendmentState:
    v = amend.view(db, acc, user)
    return AmendmentState(
        amendable=v["amendable"], diff=v["diff"], preview=v["preview"], actions=v["actions"],
        request=ApprovalRead.from_row(v["request"]) if v["request"] else None,
        previous=ApprovalRead.from_row(v["previous"]) if v["previous"] else None,
    )


@router.get("/accounts/{account_id}/amendment", response_model=AmendmentState, summary="Open amendment, its changes and allowed actions")
def get_amendment(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _amendment(db, account_service.get_account(db, account_id, user), user)


@router.post("/accounts/{account_id}/amendment", response_model=AmendmentState, summary="Start amending an approved client")
def start_amendment(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    acc = account_service.get_account(db, account_id, user)
    amend.start(db, acc, user)
    return _amendment(db, acc, user)


@router.post("/accounts/{account_id}/amendment/{action}", response_model=AmendmentState,
             summary="submit | approve | reject | withdraw | discard an amendment")
def amendment_action(account_id: int, action: str, data: Optional[RejectOrComment] = None,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    acc = account_service.get_account(db, account_id, user)
    data = data or RejectOrComment()
    if action == "submit":
        amend.submit(db, acc, user, data.comment)
    elif action == "approve":
        amend.approve(db, acc, user, data.comment)
    elif action == "reject":
        amend.reject(db, acc, user, data.reason_code, data.reason_text)
    elif action == "withdraw":
        amend.withdraw(db, acc, user)
    elif action == "discard":
        amend.discard(db, acc, user)
    else:
        raise HTTPException(status_code=404, detail=f"Unknown action '{action}'")
    db.expire_all()
    return _amendment(db, account_service.get_account(db, account_id, user), user)


# ─── Compliance approval of cases ───────────────────────────────────────────

def _case_state(db: Session, case, user: User) -> CaseComplianceState:
    v = case_ok.state(db, case, user)
    return CaseComplianceState(
        compliance_status=v["compliance_status"], actions=v["actions"],
        request=ApprovalRead.from_row(v["request"]) if v["request"] else None,
        history=[ApprovalRead.from_row(r) for r in v["history"]],
    )


@router.get("/cases/{case_id}/compliance", response_model=CaseComplianceState)
def get_case_compliance(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _case_state(db, case_service.get_case(db, case_id, user), user)


@router.post("/cases/{case_id}/compliance/{action}", response_model=CaseComplianceState,
             summary="approve | reject | withdraw | resubmit")
def case_compliance_action(case_id: int, action: str, data: Optional[RejectOrComment] = None,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = case_service.get_case(db, case_id, user)
    data = data or RejectOrComment()
    if action == "approve":
        case_ok.approve(db, case, user, data.comment)
    elif action == "reject":
        case_ok.reject(db, case, user, data.reason_code, data.reason_text)
    elif action == "withdraw":
        case_ok.withdraw(db, case, user)
    elif action == "resubmit":
        case_ok.resubmit(db, case, user, data.comment)
    else:
        raise HTTPException(status_code=404, detail=f"Unknown action '{action}'")
    db.expire_all()
    return _case_state(db, case_service.get_case(db, case_id, user), user)
