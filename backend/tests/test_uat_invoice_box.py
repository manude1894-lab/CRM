"""Triam's Invoice Box template (11-11-2026) and the decision of 12-11-2026.

- A service request can be raised once Compliance has approved the client (its Client ID is issued),
  without waiting for the Final approval; a client rejected at the Final stage takes none.
- The RM records the charge (excluding VAT) with its currency, what the client has paid and when, and any
  service provider. Submit sends the request to the Accountant's queue as an invoice instruction.
- The Accountant records the invoice and its file and sends it to the RM (raise).
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import Invoice, Notification
from app.schemas.instruction import InstructionCreate, InstructionUpdate
from app.schemas.invoice import InvoiceRaise
from app.services import client_workflow_service as wf, instruction_service as sr, invoice_service
from tests import flow


@pytest.fixture()
def setup(db, people, make_user, make_role, seed_master):
    seed_master("triam_entity", ["TCPL"])
    seed_master("service_request_type", ["Financial Audit"])
    accountant = make_user("Ann Accounts", business_role=make_role("Accountant", ["invoice.manage", "view.all_clients"]))
    acc = flow.complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    return {**people, "accountant": accountant, "acc": acc}


def _request(db, s, **fields):
    return sr.create_instruction(db, InstructionCreate(account_id=s["acc"].id, instruction_type="Financial Audit",
                                                       triam_entity="TCPL", **fields), s["maker"])


def test_requests_open_after_compliance_approval_not_before(db, setup):
    s = setup
    with pytest.raises(HTTPException) as e:  # still with Compliance
        _request(db, s)
    assert "once Compliance has approved" in e.value.detail
    flow.compliance_approve(db, s["acc"], s["checker"])
    db.refresh(s["acc"])
    assert s["acc"].profile_status == "Awaiting Approval" and s["acc"].client_id  # waiting for the Final Approver
    assert _request(db, s).id


def test_a_client_rejected_at_the_final_stage_takes_no_new_requests_but_keeps_its_own(db, setup):
    s = setup
    flow.compliance_approve(db, s["acc"], s["checker"])
    kept = _request(db, s, charge_amount=Decimal("500"))
    wf.reject(db, s["acc"], s["approver"], "Documents missing or incomplete", "Licence copy unreadable")
    db.refresh(s["acc"])
    assert s["acc"].profile_status == "Rejected"
    with pytest.raises(HTTPException):
        _request(db, s)
    with pytest.raises(HTTPException):
        sr.submit_instruction(db, kept.id, s["maker"])
    assert sr.get_instruction(db, kept.id, s["maker"]).status != "Dropped"


def test_submit_sends_the_charge_to_the_accountant_with_payment_and_provider(db, setup):
    s = setup
    flow.compliance_approve(db, s["acc"], s["checker"])
    req = _request(db, s, charge_amount=Decimal("1000"), charge_currency="usd", amount_paid=Decimal("400"),
                   payment_received_date=date(2026, 11, 10), service_provider_involved=True,
                   service_provider_name="Registry Agent Ltd", service_provider_amount=Decimal("150"))
    assert (req.charge_currency, req.amount_paid_currency, req.service_provider_currency) == ("USD", "USD", "USD")
    assert req.invoice_id is None and req.submitted_at is None

    req = sr.submit_instruction(db, req.id, s["maker"])
    inv = db.get(Invoice, req.invoice_id)
    assert req.submitted_at and req.submitted_by_id == s["maker"].id
    assert (inv.status, inv.currency, inv.amount) == ("Requested", "USD", Decimal("1000"))
    assert "Client has paid USD 400" in inv.notes and "Registry Agent Ltd, USD 150" in inv.notes
    assert db.query(Notification).filter(Notification.user_id == s["accountant"].id,
                                         Notification.notification_type == "invoice_requested").count() == 1

    with pytest.raises(HTTPException) as e:
        sr.submit_instruction(db, req.id, s["maker"])
    assert "already with the Accountant" in e.value.detail
    with pytest.raises(HTTPException) as e:
        sr.update_instruction(db, req.id, InstructionUpdate(charge_amount=Decimal("1200")), s["maker"])
    assert "Ask them to cancel the invoice" in e.value.detail
    # Other details can still be updated, e.g. a payment that arrives later.
    sr.update_instruction(db, req.id, InstructionUpdate(amount_paid=Decimal("1000"), charge_amount=Decimal("1000")), s["maker"])


def test_cancelled_invoice_returns_the_request_to_the_rm(db, setup):
    s = setup
    flow.compliance_approve(db, s["acc"], s["checker"])
    req = sr.submit_instruction(db, _request(db, s, charge_amount=Decimal("800")).id, s["maker"])
    invoice_service.cancel_invoice(db, req.invoice_id, "Wrong amount", s["accountant"])
    req = sr.get_instruction(db, req.id, s["maker"])
    assert req.invoice_id is None and req.submitted_at is None
    sr.update_instruction(db, req.id, InstructionUpdate(charge_amount=Decimal("850")), s["maker"])
    assert db.get(Invoice, sr.submit_instruction(db, req.id, s["maker"]).invoice_id).amount == Decimal("850")


def test_submit_needs_a_charge_and_a_named_provider(db, setup):
    s = setup
    flow.compliance_approve(db, s["acc"], s["checker"])
    with pytest.raises(HTTPException) as e:
        sr.submit_instruction(db, _request(db, s).id, s["maker"])
    assert "Enter the charge" in e.value.detail
    with pytest.raises(HTTPException) as e:
        sr.submit_instruction(db, _request(db, s, charge_amount=Decimal("10"), service_provider_involved=True).id, s["maker"])
    assert "name of the service provider" in e.value.detail


def test_no_provider_means_no_provider_details_and_currencies_are_checked(db, setup):
    s = setup
    flow.compliance_approve(db, s["acc"], s["checker"])
    req = _request(db, s, charge_amount=Decimal("10"), service_provider_involved=False,
                   service_provider_name="Leftover", service_provider_amount=Decimal("5"))
    assert (req.service_provider_name, req.service_provider_amount) == (None, None)
    with pytest.raises(HTTPException) as e:
        _request(db, s, charge_amount=Decimal("10"), charge_currency="XYZ")
    assert "currency must be one of" in e.value.detail


def test_completed_with_a_charge_still_goes_to_the_accountant(db, setup):
    s = setup
    flow.compliance_approve(db, s["acc"], s["checker"])
    req = _request(db, s, charge_amount=Decimal("300"), charge_currency="EUR")
    req = sr.update_instruction(db, req.id, InstructionUpdate(status="Completed"), s["maker"])
    inv = db.get(Invoice, req.invoice_id)
    assert req.submitted_at and (inv.status, inv.currency) == ("Requested", "EUR")


def test_accountant_raises_the_invoice_and_the_rm_is_told(db, setup):
    import io
    from fastapi import UploadFile
    s = setup
    flow.compliance_approve(db, s["acc"], s["checker"])
    req = sr.submit_instruction(db, _request(db, s, charge_amount=Decimal("1000")).id, s["maker"])
    invoice_service.attach(db, req.invoice_id, UploadFile(file=io.BytesIO(b"%PDF-1.4"), filename="INV-77.pdf",
                                                          headers={"content-type": "application/pdf"}),
                           invoice_service.INVOICE_FILE, s["accountant"])
    inv = invoice_service.raise_invoice(db, req.invoice_id, InvoiceRaise(
        invoice_number="TCPL-INV-77", invoice_date=date(2026, 11, 12), currency="AED", amount=Decimal("1050")), s["accountant"])
    assert inv.status == "Raised" and inv.amount == Decimal("1050")
    assert db.query(Notification).filter(Notification.user_id == s["maker"].id,
                                         Notification.notification_type == "invoice_raised").count() == 1
