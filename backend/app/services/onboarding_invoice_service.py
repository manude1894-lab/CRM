"""Invoice for Onboarding Services (Triam UAT 19-11-2026, the client form, after "Is entity regulated").

The RM answers "Do you want an invoice raised for onboarding services?". With Yes, they enter the amount payable
by the client and to the Regn / Govt Authority, whether an introducer / referrer is involved (and what they are
paid), and comments; Save keeps it as their draft, Submit sends it to the Accounts Department. It is an Invoice of
kind "Onboarding", so Accounts answers it like any invoice request: Invoice No., date, currency, amount and the
invoice file, then Raise ("Submit to RM"), which tells the RM.

Unlike a service request, it goes to Accounts at any stage of onboarding, before the client is approved (Triam,
S T Krishna 23-11-2026: "RMs should be able to raise requests for Invoice even if the relationship is not in
'approved' stage. This is the difference between Service Requests and Onboarding stage"). Only a Dropped or Exited
client takes none. One onboarding invoice per client; once Accounts has it, it changes only through
Accounts (who may cancel it, after which the RM can send a new one).
"""
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.permissions import has_permission
from app.models import Account, Invoice, User
from app.models.invoice import ONBOARDING
from app.schemas.invoice import OnboardingInvoiceSave, OnboardingInvoiceState, invoice_read
from app.services import access_control, client_workflow_service as wf, invoice_service

DESCRIPTION = "Onboarding services"
CLOSED = (wf.EXITED, wf.DROPPED)


def _account(db: Session, account_id: int, user: User) -> Account:
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Client not found")
    if not access_control.user_can_access_account(db, acc, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return acc


def current(db: Session, acc: Account) -> Optional[Invoice]:
    return (db.query(Invoice).filter(Invoice.account_id == acc.id, Invoice.kind == ONBOARDING,
                                     Invoice.status != invoice_service.InvoiceLedgerStatus.CANCELLED.value)
            .order_by(Invoice.id.desc()).first())


def _why_not(acc: Account, inv: Optional[Invoice], data: Optional[OnboardingInvoiceSave] = None) -> Optional[str]:
    """Why the invoice can't go to Accounts now, or None."""
    wanted = data.wanted if data is not None else acc.onboarding_invoice_wanted
    if wanted is not True:
        return "Answer Yes to raise an invoice for onboarding services"
    amount = data.client_amount if data is not None else (inv.amount if inv else None)
    if not amount:
        return "Enter the amount payable by the client"
    involved = data.introducer_involved if data is not None else (inv.introducer_involved if inv else None)
    if involved is None:
        return "Say whether an introducer / referrer is involved"
    if involved and not (data.introducer_amount if data is not None else (inv.introducer_amount if inv else None)):
        return "Enter the amount payable to the introducer"
    if acc.profile_status in CLOSED:
        return f"This client is {acc.profile_status}"
    return None


def state(db: Session, account_id: int, user: User) -> OnboardingInvoiceState:
    acc = _account(db, account_id, user)
    inv = current(db, acc)
    unsent = inv is None or invoice_service._unsent(inv)
    editable = unsent and not has_permission(user, "read_only") and acc.profile_status not in CLOSED
    why = _why_not(acc, inv) if editable else None
    if inv is not None and invoice_service._unsent(inv) and inv.requested_by_id != user.id:
        inv_out = None  # another user's draft stays theirs
    else:
        inv_out = invoice_read(inv, db) if inv is not None else None
    return OnboardingInvoiceState(wanted=acc.onboarding_invoice_wanted, invoice=inv_out, editable=editable,
                                  can_submit=editable and why is None, why_not=why, currencies=list(invoice_service.CURRENCIES))


def _currency(code: str, label: str) -> str:
    code = (code or "AED").upper()
    if code not in invoice_service.CURRENCIES:
        raise HTTPException(status_code=400, detail=f"{label}: currency must be one of {', '.join(invoice_service.CURRENCIES)}")
    return code


def save(db: Session, account_id: int, data: OnboardingInvoiceSave, user: User) -> OnboardingInvoiceState:
    acc = _account(db, account_id, user)
    if has_permission(user, "read_only"):
        raise HTTPException(status_code=403, detail="Read-only access")
    if acc.profile_status in CLOSED:
        raise HTTPException(status_code=409, detail=f"This client is {acc.profile_status}")
    inv = current(db, acc)
    if inv is not None and not invoice_service._unsent(inv):
        raise HTTPException(status_code=409, detail=f"The onboarding invoice is already with Accounts ({inv.status})")
    if inv is not None and inv.requested_by_id != user.id:
        raise HTTPException(status_code=409, detail="Another user is preparing this client's onboarding invoice")

    acc.onboarding_invoice_wanted = data.wanted
    if data.wanted is not True:
        if inv is not None:  # a draft prepared before the answer changed to No
            inv.status, inv.cancel_reason = invoice_service.InvoiceLedgerStatus.CANCELLED.value, "No invoice wanted for onboarding services"
        log_event(db, "onboarding_invoice_save", f"Invoice for onboarding services of {acc.company_name}: "
                  f"{'not wanted' if data.wanted is False else 'not answered'}", user_id=user.id, subject_type="Account",
                  subject_id=acc.id, account_id=acc.id)
        db.commit()
        if data.submit:
            raise HTTPException(status_code=400, detail="Answer Yes to raise an invoice for onboarding services")
        return state(db, acc.id, user)

    involved = data.introducer_involved
    fields = dict(
        amount=data.client_amount if data.client_amount is not None else Decimal("0"),
        currency=_currency(data.client_currency, "Amount payable by the client"),
        govt_authority_amount=data.govt_authority_amount,
        govt_authority_currency=_currency(data.govt_authority_currency, "Amount payable to the Regn / Govt Authority")
        if data.govt_authority_amount is not None else None,
        introducer_involved=involved,
        introducer_amount=data.introducer_amount if involved else None,
        introducer_currency=_currency(data.introducer_currency, "Amount payable to the introducer")
        if involved and data.introducer_amount is not None else None,
        notes=(data.comments or "").strip() or None,
    )
    if inv is None:
        inv = Invoice(account_id=acc.id, kind=ONBOARDING, description=DESCRIPTION, status=invoice_service.DRAFT,
                      requested_by_id=user.id, **fields)
        db.add(inv)
    else:
        for k, v in fields.items():
            setattr(inv, k, v)
    db.flush()
    if data.submit:
        why = _why_not(acc, inv, data)
        if why:
            db.rollback()
            raise HTTPException(status_code=400, detail=why)
        invoice_service._send_to_accounts(db, inv, acc, user)  # commits and tells the Accounts Department
    else:
        log_event(db, "onboarding_invoice_save", f"Invoice for onboarding services of {acc.company_name} saved as draft: "
                  f"{inv.currency} {inv.amount}", user_id=user.id, subject_type="Invoice", subject_id=inv.id, account_id=acc.id)
        db.commit()
    return state(db, acc.id, user)
