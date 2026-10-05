"""Client workflow router — Submit / Approve / Reject / Withdraw / status actions and the checker
inbox (BRD §11, §12 steps 11–14, §15). Rules live in client_workflow_service."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import User
from app.schemas.account import AccountRead
from app.schemas.approval import (
    ApprovalRead, ApproveRequest, RejectRequest, StatusActionRequest, SubmitRequest, WorkflowAction, WorkflowState,
)
from app.services import account_service, client_workflow_service as wf

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


@router.get("/approvals", response_model=list[ApprovalRead], summary="Checker inbox")
def approvals_inbox(status: str = "Pending", db: Session = Depends(get_db), user: User = Depends(require_permission("client.approve"))):
    return [ApprovalRead.from_row(r) for r in wf.inbox(db, user, status)]
