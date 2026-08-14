"""Service layer: Case (client onboarding) business logic.

Enforces:
  - linear stage-transition validation
  - CDD-approved gate before Invoice Raised
  - invoice-paid gate before Ops Assigned
  - auto-creation of the ComplianceSchedule on License Received
  - event-driven notification to Admin when CDD is approved (raise invoice)
  - RBAC (RM sees only their own cases)
"""
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from fastapi import HTTPException
from typing import Optional

from app.config import settings
from app.models import (
    Case, CaseStage, CaseStatus, InvoiceStatus, CASE_STAGE_TRANSITIONS,
    User, UserRole, Account, CDDRecord, CaseDocument, DocumentStatus, ComplianceSchedule,
)
from app.schemas.case import CaseCreate, CaseUpdate
from app.utils.uid import next_uid
from app.services import notification_service


def _apply_rbac_filter(query, user: User):
    if user.role == UserRole.RM:
        query = query.filter(Case.rm_id == user.id)
    return query


def list_cases(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    rm_id: Optional[int] = None,
) -> tuple[list[Case], int]:
    query = db.query(Case)
    query = _apply_rbac_filter(query, user)

    if search:
        pattern = f"%{search}%"
        query = query.filter(Case.company_name.ilike(pattern))
    if stage:
        query = query.filter(Case.stage == stage)
    if status:
        query = query.filter(Case.status == status)
    if rm_id:
        query = query.filter(Case.rm_id == rm_id)

    total = query.count()
    items = query.order_by(Case.created_at.desc()).offset(skip).limit(limit).all()
    return items, total


def get_case(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if user.role == UserRole.RM and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case


STANDARD_CDD_DOCUMENTS = [
    "Passport Copy (Shareholders & Directors)",
    "Address Proof — Utility Bill / Bank Statement (max 3 months)",
    "Source of Wealth (SoW)",
    "Source of Funds (SoF)",
]


def create_case(db: Session, data: CaseCreate, user: User) -> Case:
    rm_id = data.rm_id or (user.id if user.role == UserRole.RM else None)

    payload = data.model_dump(exclude={"rm_id"})
    case = Case(
        case_uid=next_uid(db, Case, "case_uid", "CASE"),
        **payload,
        rm_id=rm_id,
    )
    db.add(case)
    db.flush()

    cdd = CDDRecord(case_id=case.id)
    db.add(cdd)
    db.flush()

    for doc_type in STANDARD_CDD_DOCUMENTS:
        db.add(CaseDocument(cdd_record_id=cdd.id, doc_type=doc_type, received=False))

    db.commit()
    db.refresh(case)

    _refresh_account_stats(db, case.account_id)
    return case


def update_case(db: Session, case_id: int, data: CaseUpdate, user: User) -> Case:
    case = get_case(db, case_id, user)
    update_data = data.model_dump(exclude_unset=True)
    if user.role == UserRole.RM:
        update_data.pop("rm_id", None)

    for field, value in update_data.items():
        setattr(case, field, value)

    db.commit()
    db.refresh(case)
    _refresh_account_stats(db, case.account_id)
    return case


def change_stage(db: Session, case_id: int, new_stage: CaseStage, user: User) -> Case:
    """Move a case to a new stage, validating the transition and any workflow gates.

    Invoice Raised / Invoice Paid are reached only via raise_invoice()/mark_invoice_paid()
    below, so the stage pointer and the invoice fields can never drift out of sync.
    """
    case = get_case(db, case_id, user)
    _validate_transition(case.stage, new_stage)

    target = new_stage.value if isinstance(new_stage, CaseStage) else new_stage

    if target in (CaseStage.INVOICE_RAISED.value, CaseStage.INVOICE_PAID.value):
        raise HTTPException(
            status_code=400,
            detail="Use POST /cases/{id}/invoice/raise or /invoice/mark-paid to advance through the invoicing stages",
        )
    if target == CaseStage.OPS_ASSIGNED.value:
        _assert_invoice_paid(case)

    case.stage = new_stage
    db.commit()
    db.refresh(case)

    if target == CaseStage.CDD_APPROVED.value:
        notification_service.notify_role(
            db, UserRole.ADMIN,
            message=f"CDD approved for case {case.case_uid} ({case.company_name}) — ready to raise invoice.",
            link=f"/cases/{case.id}",
            notification_type="cdd_approved",
            case_id=case.id,
        )

    if target == CaseStage.LICENSE_RECEIVED.value:
        _create_compliance_schedule(db, case)

    return case


def raise_invoice(db: Session, case_id: int, user: User, amount: float = 0.0) -> Case:
    case = get_case(db, case_id, user)
    if case.stage != CaseStage.CDD_APPROVED:
        raise HTTPException(status_code=400, detail="Case must be at the CDD Approved stage to raise an invoice")
    _assert_cdd_approved(db, case)
    if case.invoice_status != InvoiceStatus.NOT_RAISED:
        raise HTTPException(status_code=400, detail="Invoice has already been raised")
    case.invoice_amount = Decimal(str(amount))
    case.invoice_status = InvoiceStatus.RAISED
    case.invoice_raised_date = date.today()
    case.stage = CaseStage.INVOICE_RAISED
    db.commit()
    db.refresh(case)
    _refresh_account_stats(db, case.account_id)
    return case


def mark_invoice_paid(db: Session, case_id: int, user: User) -> Case:
    case = get_case(db, case_id, user)
    if case.stage != CaseStage.INVOICE_RAISED:
        raise HTTPException(status_code=400, detail="Case must be at the Invoice Raised stage to mark the invoice paid")
    if case.invoice_status != InvoiceStatus.RAISED:
        raise HTTPException(status_code=400, detail="Invoice must be raised before it can be marked paid")
    case.invoice_status = InvoiceStatus.PAID
    case.invoice_paid_date = date.today()
    case.stage = CaseStage.INVOICE_PAID
    db.commit()
    db.refresh(case)
    return case


def _assert_cdd_approved(db: Session, case: Case) -> None:
    cdd = db.query(CDDRecord).filter(CDDRecord.case_id == case.id).first()
    if not cdd or cdd.cdd_form_status != DocumentStatus.APPROVED or cdd.kyc_verification_status != DocumentStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail="CDD form and KYC verification must both be Approved before raising an invoice",
        )


def _assert_invoice_paid(case: Case) -> None:
    if case.invoice_status != InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Invoice must be marked Paid before assigning Ops")


def _create_compliance_schedule(db: Session, case: Case) -> ComplianceSchedule:
    existing = db.query(ComplianceSchedule).filter(ComplianceSchedule.case_id == case.id).first()
    if existing:
        return existing
    base = case.license_received_date or date.today()
    schedule = ComplianceSchedule(
        case_id=case.id,
        renewal_due_date=base + relativedelta(months=settings.RENEWAL_CADENCE_MONTHS),
        renewal_cadence_months=settings.RENEWAL_CADENCE_MONTHS,
        compliance_filing_due_date=base + relativedelta(months=settings.COMPLIANCE_FILING_CADENCE_MONTHS),
        compliance_filing_cadence_months=settings.COMPLIANCE_FILING_CADENCE_MONTHS,
        tax_filing_due_date=base + relativedelta(months=settings.TAX_FILING_CADENCE_MONTHS),
        tax_filing_cadence_months=settings.TAX_FILING_CADENCE_MONTHS,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def _validate_transition(current_stage, new_stage) -> None:
    current = current_stage.value if isinstance(current_stage, CaseStage) else current_stage
    target = new_stage.value if isinstance(new_stage, CaseStage) else new_stage
    if current == target:
        return
    allowed = CASE_STAGE_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage transition: '{current}' → '{target}'. Allowed: {allowed}",
        )


def delete_case(db: Session, case_id: int, user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only Admin can delete cases")
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    account_id = case.account_id
    db.delete(case)
    db.commit()
    _refresh_account_stats(db, account_id)


def _refresh_account_stats(db: Session, account_id: Optional[int]) -> None:
    """Recompute the cached total_cases + total_invoiced_amount on an Account."""
    if not account_id:
        return
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return
    stats = db.query(
        func.count(Case.id).label("cnt"),
        func.coalesce(func.sum(Case.invoice_amount), 0).label("total"),
    ).filter(Case.account_id == account_id).first()
    account.total_cases = stats.cnt or 0
    account.total_invoiced_amount = stats.total or 0
    db.commit()
