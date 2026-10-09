"""Service layer: Invoice module (Triam BRD mark-up §16).

Invoicing for every new client onboarding and every service request:
  1. The RM / Sales *requests* an invoice for a client (optionally a case or service request), with the
     expected amount and currency, and attaches the pricing approvals. This is the instruction to the
     Accounts Department — every Accounts user (invoice.manage) is notified.
  2. Accounts *raises* it: Invoice No, Invoice Date, Currency, Amount and the invoice file. The requester
     is told it is ready to download and send to the client.
  3. Accounts marks it *paid*.
Only Accounts (invoice.manage) records invoice details and payments; the RM keeps read access to the
invoices of the clients they can see, and can add pricing approvals while the request is open.
"""
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.permissions import has_permission
from app.models import Account, Case, Document, Instruction, Invoice, User
from app.schemas.invoice import InvoiceCreate, InvoiceRaise, InvoiceRequest, InvoiceUpdate
from app.services import access_control, notification_service

REQUESTED, DRAFT, RAISED, PAID = "Requested", "Draft", "Raised", "Paid"
OPEN = (REQUESTED, DRAFT)
PRICING_APPROVAL, INVOICE_FILE = "Pricing Approval", "Invoice"
CURRENCIES = ("AED", "USD", "EUR", "GBP", "INR", "SGD")


def _accounts_team(db: Session) -> list[User]:
    return [u for u in db.query(User).filter(User.is_active == True).all() if has_permission(u, "invoice.manage")]  # noqa: E712


def _can_manage(user: User) -> bool:
    return has_permission(user, "invoice.manage")


def _client(db: Session, account_id: int, user: User) -> Account:
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=400, detail="Client not found")
    if not access_control.user_can_access_account(db, acc, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return acc


def _visible(db: Session, inv: Invoice, user: User) -> bool:
    if inv.account_id:
        acc = db.get(Account, inv.account_id)
        return acc is not None and access_control.user_can_access_account(db, acc, user)
    case = db.get(Case, inv.case_id) if inv.case_id else None
    return case is not None and access_control.user_can_access_case(case, user)


def list_invoices(db: Session, user: User, skip: int = 0, limit: int = 100, case_id: Optional[int] = None,
                  status: Optional[str] = None, search: Optional[str] = None,
                  account_id: Optional[int] = None) -> tuple[list[Invoice], int]:
    query = db.query(Invoice)
    clause = access_control.account_visibility_clause(db, user)
    if clause is not None:
        visible_accounts = [a.id for a in db.query(Account.id).filter(clause).all()]
        visible_cases = [c.id for c in db.query(Case.id).filter(access_control.rm_visibility_clause(user)).all()]
        query = query.filter(or_(Invoice.account_id.in_(visible_accounts or [-1]), Invoice.case_id.in_(visible_cases or [-1])))
    if case_id:
        query = query.filter(Invoice.case_id == case_id)
    if account_id:
        query = query.filter(Invoice.account_id == account_id)
    if status:
        query = query.filter(Invoice.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.outerjoin(Account, Invoice.account_id == Account.id).outerjoin(Case, Invoice.case_id == Case.id).filter(or_(
            Account.company_name.ilike(pattern), Case.company_name.ilike(pattern),
            Invoice.invoice_number.ilike(pattern), Invoice.description.ilike(pattern),
        ))
    total = query.count()
    items = query.order_by(Invoice.id.desc()).offset(skip).limit(limit).all()
    return items, total


def get_invoice(db: Session, invoice_id: int, user: User) -> Invoice:
    inv = db.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not _visible(db, inv, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return inv


def _label(db: Session, inv: Invoice) -> str:
    acc = db.get(Account, inv.account_id) if inv.account_id else None
    name = acc.company_name if acc else (inv.case.company_name if inv.case else "—")
    return f"invoice #{inv.id} for {name}"


def request_invoice(db: Session, data: InvoiceRequest, user: User) -> Invoice:
    """Step 1 — the RM / Sales asks Accounts to invoice a client onboarding or a service request."""
    acc = _client(db, data.account_id, user)
    case_id = data.case_id
    if data.instruction_id:
        inst = db.get(Instruction, data.instruction_id)
        if not inst or inst.account_id != acc.id:
            raise HTTPException(status_code=400, detail="That service request does not belong to this client")
        if inst.invoice_id:
            raise HTTPException(status_code=400, detail="An invoice has already been requested for this service request")
        case_id = case_id or inst.case_id
    if case_id:
        case = db.get(Case, case_id)
        if not case or case.account_id != acc.id:
            raise HTTPException(status_code=400, detail="That case does not belong to this client")
    if data.currency not in CURRENCIES:
        raise HTTPException(status_code=400, detail=f"Currency must be one of {', '.join(CURRENCIES)}")
    inv = Invoice(account_id=acc.id, case_id=case_id, description=data.description, amount=data.amount, currency=data.currency,
                  notes=data.notes, status=REQUESTED, requested_by_id=user.id, requested_at=datetime.now(timezone.utc))
    db.add(inv)
    db.flush()
    if data.instruction_id:
        db.get(Instruction, data.instruction_id).invoice_id = inv.id
    log_event(db, "invoice_request", f"Invoice requested for {acc.company_name}: {data.description} — {data.currency} {data.amount}",
              user_id=user.id, subject_type="Invoice", subject_id=inv.id, account_id=acc.id)
    db.commit()
    db.refresh(inv)
    for u in _accounts_team(db):
        if u.id != user.id:
            notification_service.notify_user(
                db, u.id, f"Invoice instruction from {user.name}: {acc.company_name} — {data.description} ({data.currency} {data.amount}).",
                "invoice_requested")
    return inv


def create_invoice(db: Session, data: InvoiceCreate, user: User) -> Invoice:
    """Accounts entering an invoice directly (e.g. consolidating several charges)."""
    if not _can_manage(user):
        raise HTTPException(status_code=403, detail="Only Accounts can create invoices — request one instead")
    if not data.account_id and not data.case_id:
        raise HTTPException(status_code=400, detail="Choose the client")
    account_id = data.account_id or db.get(Case, data.case_id).account_id
    inv = Invoice(**data.model_dump(exclude={"account_id"}), account_id=account_id)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def update_invoice(db: Session, invoice_id: int, data: InvoiceUpdate, user: User) -> Invoice:
    inv = get_invoice(db, invoice_id, user)
    payload = data.model_dump(exclude_unset=True)
    if not _can_manage(user):
        # The requester may still correct their request while Accounts hasn't raised it.
        if inv.status not in OPEN or inv.requested_by_id != user.id or set(payload) - {"description", "amount", "currency", "notes"}:
            raise HTTPException(status_code=403, detail="Only Accounts can record invoice details and payments")
    if "currency" in payload and payload["currency"] not in CURRENCIES:
        raise HTTPException(status_code=400, detail=f"Currency must be one of {', '.join(CURRENCIES)}")
    for field, value in payload.items():
        setattr(inv, field, value)
    db.commit()
    db.refresh(inv)
    return inv


def raise_invoice(db: Session, invoice_id: int, data: InvoiceRaise, user: User) -> Invoice:
    """Step 2 — Accounts records the invoice details; the invoice file must be attached first."""
    if not _can_manage(user):
        raise HTTPException(status_code=403, detail="Only Accounts can raise invoices")
    inv = get_invoice(db, invoice_id, user)
    if inv.status not in OPEN:
        raise HTTPException(status_code=400, detail=f"This invoice is already {inv.status}")
    if data.currency not in CURRENCIES:
        raise HTTPException(status_code=400, detail=f"Currency must be one of {', '.join(CURRENCIES)}")
    if not db.query(Document.id).filter(Document.invoice_id == inv.id, Document.category == INVOICE_FILE).first():
        raise HTTPException(status_code=400, detail="Attach the invoice file before raising the invoice")
    inv.invoice_number, inv.raised_date, inv.currency, inv.amount = data.invoice_number.strip(), data.invoice_date, data.currency, data.amount
    inv.due_date = data.due_date
    inv.status, inv.raised_by_id = RAISED, user.id
    log_event(db, "invoice_raise", f"{_label(db, inv)} raised: {inv.invoice_number} — {inv.currency} {inv.amount}",
              user_id=user.id, subject_type="Invoice", subject_id=inv.id, account_id=inv.account_id)
    db.commit()
    db.refresh(inv)
    if inv.requested_by_id and inv.requested_by_id != user.id:
        notification_service.notify_user(db, inv.requested_by_id,
                                         f"Invoice {inv.invoice_number} is ready to download and send to the client ({_label(db, inv)}).",
                                         "invoice_raised")
    return inv


def mark_paid(db: Session, invoice_id: int, paid_date: Optional[date], user: User) -> Invoice:
    """Step 3 — Accounts records the payment."""
    if not _can_manage(user):
        raise HTTPException(status_code=403, detail="Only Accounts can record payments")
    inv = get_invoice(db, invoice_id, user)
    if inv.status != RAISED:
        raise HTTPException(status_code=400, detail="Only a raised invoice can be marked paid")
    inv.status, inv.paid_date = PAID, paid_date or date.today()
    log_event(db, "invoice_paid", f"{_label(db, inv)} ({inv.invoice_number}) paid", user_id=user.id,
              subject_type="Invoice", subject_id=inv.id, account_id=inv.account_id)
    db.commit()
    db.refresh(inv)
    if inv.requested_by_id and inv.requested_by_id != user.id:
        notification_service.notify_user(db, inv.requested_by_id, f"Invoice {inv.invoice_number} has been paid ({_label(db, inv)}).", "invoice_paid")
    return inv


def attach(db: Session, invoice_id: int, upload: UploadFile, kind: str, user: User) -> Document:
    """Pricing approvals (RM / Sales, while the request is open) or the invoice file (Accounts)."""
    from app.services import document_service
    inv = get_invoice(db, invoice_id, user)
    if kind == INVOICE_FILE:
        if not _can_manage(user):
            raise HTTPException(status_code=403, detail="Only Accounts can attach the invoice")
    elif kind == PRICING_APPROVAL:
        if inv.status not in OPEN and not _can_manage(user):
            raise HTTPException(status_code=400, detail="Pricing approvals are attached while the invoice request is open")
    else:
        raise HTTPException(status_code=400, detail="Attach a Pricing Approval or the Invoice")
    filename, data = document_service.read_upload(upload)
    doc = Document(account_id=inv.account_id, invoice_id=inv.id, category=kind, filename=filename, content_type=upload.content_type,
                   size_bytes=len(data), content=data, uploaded_by_id=user.id)
    db.add(doc)
    db.flush()
    log_event(db, "document_upload", f"{kind} '{filename}' attached to {_label(db, inv)}", user_id=user.id,
              subject_type="Invoice", subject_id=inv.id, account_id=inv.account_id)
    db.commit()
    db.refresh(doc)
    return doc


def attachments(db: Session, invoice_id: int, user: User) -> list[Document]:
    get_invoice(db, invoice_id, user)
    return db.query(Document).filter(Document.invoice_id == invoice_id).order_by(Document.id).all()


def delete_invoice(db: Session, invoice_id: int, user: User) -> None:
    inv = get_invoice(db, invoice_id, user)
    if not (_can_manage(user) or (inv.status in OPEN and inv.requested_by_id == user.id)):
        raise HTTPException(status_code=403, detail="Only Accounts can delete an invoice")
    if inv.status == PAID:
        raise HTTPException(status_code=400, detail="A paid invoice can't be deleted")
    db.query(Instruction).filter(Instruction.invoice_id == inv.id).update({Instruction.invoice_id: None})
    db.delete(inv)
    db.commit()
