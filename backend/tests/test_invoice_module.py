"""Triam BRD mark-up §16 — the Invoice module: RM requests, Accounts raises and records payment."""
import io
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, UploadFile

from app.models import Notification
from app.schemas.invoice import InvoiceRaise, InvoiceRequest, InvoiceUpdate
from app.services import document_service, invoice_service


def _pdf(name="file.pdf"):
    return UploadFile(file=io.BytesIO(b"%PDF-1.4 test"), filename=name, headers={"content-type": "application/pdf"})


@pytest.fixture()
def setup(make_user, make_role, make_account):
    rm = make_user("Rita RM")
    accounts = make_user("Swathi Accounts", business_role=make_role("Accountant", ["invoice.manage", "view.all_clients"]))
    other_rm = make_user("Otto RM")
    acc = make_account(name="Falcon Trading LLC", spoc=rm)
    return {"rm": rm, "accounts": accounts, "other_rm": other_rm, "acc": acc}


def _request(db, s):
    return invoice_service.request_invoice(db, InvoiceRequest(account_id=s["acc"].id, description="Company formation — ADGM SPV",
                                                              amount=Decimal("15000"), currency="AED"), s["rm"])


def test_request_is_an_instruction_to_accounts(db, setup):
    inv = _request(db, setup)
    assert inv.status == "Requested" and inv.requested_by_id == setup["rm"].id and inv.account_id == setup["acc"].id
    note = db.query(Notification).filter(Notification.user_id == setup["accounts"].id).one()
    assert "Invoice instruction" in note.message and "15000" in note.message
    with pytest.raises(HTTPException):  # another RM can't see this client
        invoice_service.get_invoice(db, inv.id, setup["other_rm"])


def test_rm_attaches_pricing_approval_but_only_accounts_raises(db, setup):
    rm, accounts = setup["rm"], setup["accounts"]
    inv = _request(db, setup)
    invoice_service.attach(db, inv.id, _pdf("pricing-approval.pdf"), "Pricing Approval", rm)
    with pytest.raises(HTTPException) as e:
        invoice_service.attach(db, inv.id, _pdf("inv.pdf"), "Invoice", rm)
    assert "Only Accounts" in e.value.detail
    details = InvoiceRaise(invoice_number="TABL-INV-0042", invoice_date=date(2026, 10, 9), currency="AED", amount=Decimal("15750"))
    with pytest.raises(HTTPException):
        invoice_service.raise_invoice(db, inv.id, details, rm)
    with pytest.raises(HTTPException) as e:  # the invoice file comes first
        invoice_service.raise_invoice(db, inv.id, details, accounts)
    assert "Attach the invoice" in e.value.detail
    invoice_service.attach(db, inv.id, _pdf("TABL-INV-0042.pdf"), "Invoice", accounts)
    invoice_service.raise_invoice(db, inv.id, details, accounts)
    assert (inv.status, inv.invoice_number, inv.amount, inv.raised_by_id) == ("Raised", "TABL-INV-0042", Decimal("15750"), accounts.id)
    assert db.query(Notification).filter(Notification.user_id == rm.id, Notification.notification_type == "invoice_raised").count() == 1
    # the RM (front end) downloads the invoice to send to the client
    invoice_doc = [d for d in invoice_service.attachments(db, inv.id, rm) if d.category == "Invoice"][0]
    data, filename, _ = document_service.stream_content(db, invoice_doc.id, rm)
    assert filename == "TABL-INV-0042.pdf" and data.startswith(b"%PDF")
    # invoice attachments don't clutter the client's KYC folder
    assert document_service.client_folder(db, setup["acc"].id, rm)["documents"] == []


def test_payment_is_recorded_by_accounts(db, setup):
    rm, accounts = setup["rm"], setup["accounts"]
    inv = _request(db, setup)
    invoice_service.attach(db, inv.id, _pdf(), "Invoice", accounts)
    invoice_service.raise_invoice(db, inv.id, InvoiceRaise(invoice_number="INV-1", invoice_date=date(2026, 10, 9), amount=Decimal("1")), accounts)
    with pytest.raises(HTTPException):
        invoice_service.mark_paid(db, inv.id, None, rm)
    invoice_service.mark_paid(db, inv.id, date(2026, 10, 20), accounts)
    assert inv.status == "Paid" and inv.paid_date == date(2026, 10, 20)


def test_rm_may_correct_an_open_request_only(db, setup):
    rm, accounts = setup["rm"], setup["accounts"]
    inv = _request(db, setup)
    invoice_service.update_invoice(db, inv.id, InvoiceUpdate(amount=Decimal("16000")), rm)
    with pytest.raises(HTTPException):
        invoice_service.update_invoice(db, inv.id, InvoiceUpdate(invoice_number="X"), rm)
    invoice_service.attach(db, inv.id, _pdf(), "Invoice", accounts)
    invoice_service.raise_invoice(db, inv.id, InvoiceRaise(invoice_number="INV-2", invoice_date=date(2026, 10, 9), amount=Decimal("16000")), accounts)
    with pytest.raises(HTTPException):
        invoice_service.update_invoice(db, inv.id, InvoiceUpdate(amount=Decimal("1")), rm)
