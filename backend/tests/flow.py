"""Test helpers for the new-client approval flow (Triam BRD mark-up §7–§10):
RM submits → Compliance (MLRO) completes the CDD section and approves → Approver gives final approval."""
from datetime import date

from app.schemas.account import AccountUpdate
from app.services import account_service, client_workflow_service as wf


def submit(db, acc, user, comment="Client documents collected and checked"):
    return wf.submit(db, acc, user, comment, True)


def fill_cdd(db, acc, mlro, risk="Low"):
    account_service.update_account(db, acc.id, AccountUpdate(
        risk_rating=risk, kyc_verified_by="Rita RM", cdd_completion_date=date(2026, 9, 1),
        edd_reason="High-risk country" if risk == "High" else None), mlro)
    db.refresh(acc)


def compliance_approve(db, acc, mlro, comment="CDD complete and documents verified"):
    if account_service.missing_cdd(acc):
        fill_cdd(db, acc, mlro)
    return wf.approve(db, acc, mlro, comment)


def approve_all(db, acc, mlro, approver):
    compliance_approve(db, acc, mlro)
    return wf.approve(db, acc, approver, "Final approval given")
