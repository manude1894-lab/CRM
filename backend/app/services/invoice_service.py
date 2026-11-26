"""Service layer: Invoice module (BRD §16).

Invoicing for every new client onboarding and every service request:
  1. The RM / Sales *requests* an invoice for a client (optionally for a service request), with the
     expected amount and currency, and attaches the pricing approvals. This is the instruction to the
     Accounts Department — every Accounts user (invoice.manage) is notified. The request may first be
     saved as a draft that only the requester sees, and submitted to Accounts later.
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
from app.models import Account, Document, Instruction, Invoice, InvoiceLedgerStatus, User
from app.models.invoice import ONBOARDING, SERVICE_REQUEST
from app.schemas.invoice import InvoiceCreate, InvoiceRaise, InvoiceRequest, InvoiceUpdate
from app.services import access_control, notification_service

REQUESTED, DRAFT, RAISED, PAID = "Requested", "Draft", "Raised", "Paid"
WITH_CO = InvoiceLedgerStatus.WITH_COMPLIANCE.value
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


def _unsent(inv: Invoice) -> bool:
    """A requester's draft request, not yet submitted to Accounts."""
    return inv.status == DRAFT and inv.requested_by_id is not None and inv.requested_at is None


def _visible(db: Session, inv: Invoice, user: User) -> bool:
    if _unsent(inv) and inv.requested_by_id != user.id:
        return False
    acc = db.get(Account, inv.account_id)
    return acc is not None and access_control.user_can_access_account(db, acc, user)


def list_invoices(db: Session, user: User, skip: int = 0, limit: int = 100,
                  status: Optional[str] = None, search: Optional[str] = None,
                  account_id: Optional[int] = None) -> tuple[list[Invoice], int]:
    query = db.query(Invoice)
    clause = access_control.account_visibility_clause(db, user)
    if clause is not None:
        visible_accounts = [a.id for a in db.query(Account.id).filter(clause).all()]
        query = query.filter(Invoice.account_id.in_(visible_accounts or [-1]))
    # Draft requests stay with their requester until submitted.
    query = query.filter(or_(Invoice.status != DRAFT, Invoice.requested_by_id.is_(None),
                             Invoice.requested_at.isnot(None), Invoice.requested_by_id == user.id))
    if account_id:
        query = query.filter(Invoice.account_id == account_id)
    if status:
        query = query.filter(Invoice.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.join(Account, Invoice.account_id == Account.id).filter(or_(
            Account.company_name.ilike(pattern), Account.client_id.ilike(pattern),
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
    acc = db.get(Account, inv.account_id)
    return f"invoice #{inv.id} for {acc.company_name if acc else '—'}"


def request_invoice(db: Session, data: InvoiceRequest, user: User) -> Invoice:
    """Step 1 — the RM / Sales asks Accounts to invoice a client onboarding or a service request."""
    acc = _client(db, data.account_id, user)
    if data.instruction_id:
        inst = db.get(Instruction, data.instruction_id)
        if not inst or inst.account_id != acc.id:
            raise HTTPException(status_code=400, detail="That service request does not belong to this client")
        if inst.invoice_id:
            raise HTTPException(status_code=400, detail="An invoice has already been requested for this service request")
    if data.currency not in CURRENCIES:
        raise HTTPException(status_code=400, detail=f"Currency must be one of {', '.join(CURRENCIES)}")
    onboarding = data.onboarding and not data.instruction_id
    if onboarding:
        from app.services import onboarding_invoice_service
        if acc.profile_status in onboarding_invoice_service.CLOSED:
            raise HTTPException(status_code=409, detail=f"This client is {acc.profile_status}")
        existing = onboarding_invoice_service.current(db, acc)
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"{acc.company_name} already has an onboarding invoice "
                                                        f"({'draft' if _unsent(existing) else existing.status}). "
                                                        "Open it from the client's profile, Invoice for Onboarding Services.")
        acc.onboarding_invoice_wanted = True
    inv = Invoice(account_id=acc.id, description=data.description, amount=data.amount, currency=data.currency,
                  notes=data.notes, status=DRAFT, requested_by_id=user.id,
                  kind=SERVICE_REQUEST if data.instruction_id else ONBOARDING if onboarding else None)
    db.add(inv)
    db.flush()
    if data.instruction_id:
        db.get(Instruction, data.instruction_id).invoice_id = inv.id
    if not data.submit:
        log_event(db, "invoice_request_draft", f"Invoice request saved as draft for {acc.company_name}: {data.description}",
                  user_id=user.id, subject_type="Invoice", subject_id=inv.id, account_id=acc.id)
        db.commit()
        db.refresh(inv)
        return inv
    return _send_to_accounts(db, inv, acc, user)


def needs_co(inv: Invoice, acc: Account) -> bool:
    """Triam UAT 25-11-2026 row 182: an onboarding invoice requested while the client is still being onboarded
    goes to the CO first, who checks ID verification, name screening, alerts and open risks."""
    from app.services import client_workflow_service as wf
    return inv.kind == ONBOARDING and acc.profile_status in wf.ONBOARDING


def _compliance_team(db: Session) -> list[User]:
    from app.services import client_workflow_service as wf
    return [u for u in db.query(User).filter(User.is_active == True).all() if wf.gives_compliance_approval(u)]  # noqa: E712


def _send_to_accounts(db: Session, inv: Invoice, acc: Account, user: User) -> Invoice:
    if needs_co(inv, acc):
        inv.status, inv.requested_at = WITH_CO, datetime.now(timezone.utc)
        inv.co_decision = inv.co_decided_at = inv.co_decided_by_id = inv.co_comment = None
        log_event(db, "invoice_to_compliance", f"Onboarding invoice request for {acc.company_name} sent to Compliance: "
                  f"{inv.currency} {inv.amount}", user_id=user.id, subject_type="Invoice", subject_id=inv.id, account_id=acc.id)
        db.commit()
        db.refresh(inv)
        for u in _compliance_team(db):
            if u.id != user.id:
                notification_service.notify_user(
                    db, u.id, f"Onboarding invoice request from {user.name} for {acc.company_name} ({inv.currency} {inv.amount}) "
                              "awaits your approval.", "invoice_co_approval")
        return inv
    inv.status, inv.requested_at = REQUESTED, datetime.now(timezone.utc)
    log_event(db, "invoice_request", f"Invoice requested for {acc.company_name}: {inv.description}, {inv.currency} {inv.amount}",
              user_id=user.id, subject_type="Invoice", subject_id=inv.id, account_id=acc.id)
    db.commit()
    db.refresh(inv)
    for u in _accounts_team(db):
        if u.id != user.id:
            notification_service.notify_user(
                db, u.id, f"Invoice instruction from {user.name}: {acc.company_name}, {inv.description} ({inv.currency} {inv.amount}).",
                "invoice_requested")
    return inv


def may_co_decide(db: Session, inv: Invoice, user: User) -> Optional[str]:
    """Why this user can't decide on the request, or None. The CO, not the requester or the client's own RM."""
    from app.services import client_workflow_service as wf
    if inv.status != WITH_CO:
        return "This invoice request isn't waiting for Compliance"
    if not wf.gives_compliance_approval(user):
        return "Only Compliance (CO / MLRO) decides on onboarding invoice requests"
    requester = db.get(User, inv.requested_by_id) if inv.requested_by_id else None
    acc = db.get(Account, inv.account_id)
    if access_control.same_person(requester, user) or access_control.is_clients_rm(db, acc, user):
        return "You can't approve an invoice request for your own client"
    return None


def co_decide(db: Session, invoice_id: int, data, user: User) -> Invoice:
    """The CO approves the request (it goes to Accounts) or returns it to the RM with a reason."""
    inv = get_invoice(db, invoice_id, user)
    why = may_co_decide(db, inv, user)
    if why:
        raise HTTPException(status_code=403 if "Only" in why or "own client" in why else 400, detail=why)
    comment = (data.comment or "").strip() or None
    acc = db.get(Account, inv.account_id)
    inv.co_decided_by_id, inv.co_decided_at, inv.co_comment = user.id, datetime.now(timezone.utc), comment
    if data.approve:
        if not data.checks_confirmed:
            raise HTTPException(status_code=400, detail="Confirm the ID verification, name screening, alerts and open risks first")
        inv.co_decision, inv.status = "Approved", REQUESTED
        log_event(db, "invoice_co_approve", f"Onboarding invoice request for {acc.company_name} approved by Compliance",
                  user_id=user.id, subject_type="Invoice", subject_id=inv.id, account_id=acc.id)
        db.commit()
        db.refresh(inv)
        for u in _accounts_team(db):
            if u.id != user.id:
                notification_service.notify_user(db, u.id, f"Invoice instruction for {acc.company_name}: {inv.description} "
                                                           f"({inv.currency} {inv.amount}), approved by Compliance.", "invoice_requested")
        if inv.requested_by_id:
            notification_service.notify_user(db, inv.requested_by_id, f"Compliance approved the onboarding invoice request for "
                                                                      f"{acc.company_name}; it is with Accounts.", "invoice_co_decision")
        return inv
    if not comment:
        raise HTTPException(status_code=400, detail="Say why the request is returned")
    inv.co_decision, inv.status, inv.requested_at = "Returned", DRAFT, None  # back to the RM's draft
    log_event(db, "invoice_co_return", f"Onboarding invoice request for {acc.company_name} returned by Compliance: {comment}",
              user_id=user.id, subject_type="Invoice", subject_id=inv.id, account_id=acc.id)
    db.commit()
    db.refresh(inv)
    if inv.requested_by_id:
        notification_service.notify_user(db, inv.requested_by_id, f"Compliance returned the onboarding invoice request for "
                                                                  f"{acc.company_name}: {comment}", "invoice_co_decision")
    return inv


def submit_request(db: Session, invoice_id: int, user: User) -> Invoice:
    """The requester sends their draft request to Accounts."""
    inv = get_invoice(db, invoice_id, user)
    if not _unsent(inv) or inv.requested_by_id != user.id:
        raise HTTPException(status_code=400, detail="Only your own draft invoice request can be submitted")
    return _send_to_accounts(db, inv, _client(db, inv.account_id, user), user)


def create_invoice(db: Session, data: InvoiceCreate, user: User) -> Invoice:
    """Accounts entering an invoice directly (e.g. consolidating several charges)."""
    if not _can_manage(user):
        raise HTTPException(status_code=403, detail="Only Accounts can create invoices. Please request one instead.")
    acc = _client(db, data.account_id, user)
    inv = Invoice(**data.model_dump(exclude={"account_id"}), account_id=acc.id)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def update_invoice(db: Session, invoice_id: int, data: InvoiceUpdate, user: User) -> Invoice:
    inv = get_invoice(db, invoice_id, user)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("status") == "Cancelled" or inv.status == "Cancelled":
        raise HTTPException(status_code=400, detail="Use Cancel (with a reason) to cancel; a cancelled invoice can't be changed")
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
    log_event(db, "invoice_raise", f"{_label(db, inv)} raised: {inv.invoice_number}, {inv.currency} {inv.amount}",
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
    return db.query(Document).filter(Document.invoice_id == invoice_id, Document.removed_at.is_(None)).order_by(Document.id).all()


def cancel_invoice(db: Session, invoice_id: int, reason: str, user: User) -> None:
    """Invoices are never deleted. The requester may cancel their own open request; Accounts may cancel
    any invoice that is not paid. The invoice and its attachments stay on record."""
    inv = get_invoice(db, invoice_id, user)
    if not (_can_manage(user) or (inv.status in (*OPEN, WITH_CO) and inv.requested_by_id == user.id)):
        raise HTTPException(status_code=403, detail="Only Accounts can cancel this invoice")
    if inv.status in (PAID, InvoiceLedgerStatus.CANCELLED.value):
        raise HTTPException(status_code=400, detail=f"A {inv.status.lower()} invoice can't be cancelled")
    # The service request goes back to its RM, who may correct the charge and submit it again.
    db.query(Instruction).filter(Instruction.invoice_id == inv.id).update(
        {Instruction.invoice_id: None, Instruction.submitted_at: None, Instruction.submitted_by_id: None})
    inv.status, inv.cancel_reason = InvoiceLedgerStatus.CANCELLED.value, reason.strip()
    db.commit()
