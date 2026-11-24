"""Triam UAT 19-11-2026, row 153: Invoice for Onboarding Services, on the client form after "Is entity regulated".

The RM answers Yes / No; with Yes, the amount payable by the client and to the Regn / Govt Authority, whether an
introducer / referrer is involved and what they are paid, and comments. Save keeps a draft; Submit sends it to the
Accounts Department at any stage of onboarding (Triam 23-11-2026). Accounts answers with the invoice (No., date, amount,
file) and raises it, which tells the RM.
"""
import io
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, UploadFile

from app.models import Invoice, Notification
from app.schemas.invoice import InvoiceRaise, OnboardingInvoiceSave
from app.services import client_workflow_service as wf, invoice_service, onboarding_invoice_service as onb
from tests import flow

YES = dict(wanted=True, client_amount=Decimal("15000"), client_currency="AED", govt_authority_amount=Decimal("4000"),
           govt_authority_currency="AED", introducer_involved=True, introducer_amount=Decimal("1500"), introducer_currency="USD",
           comments="DMCC formation, two visas")


@pytest.fixture()
def setup(db, people, make_user, make_role):
    accountant = make_user("Ann Accounts", business_role=make_role("Accountant", ["invoice.manage", "view.all_clients"]))
    acc = flow.complete_client(db, people["maker"])
    return {**people, "accountant": accountant, "acc": acc}


def test_saved_as_a_draft_then_sent_to_accounts_before_approval(db, setup):
    """Triam 23-11-2026 (S T Krishna): unlike a service request, the onboarding invoice goes to Accounts while the
    client is still being onboarded, before any approval."""
    s = setup
    rm, acc = s["maker"], s["acc"]
    assert acc.profile_status in wf.WITH_RM  # not submitted, not approved
    st = onb.save(db, acc.id, OnboardingInvoiceSave(**YES), rm)
    assert st.wanted is True and st.editable and st.invoice.status == "Draft" and st.invoice.kind == "Onboarding"
    assert (st.invoice.amount, st.invoice.govt_authority_amount, st.invoice.introducer_currency) == (Decimal("15000"), Decimal("4000"), "USD")
    assert st.can_submit and st.why_not is None
    assert onb.state(db, acc.id, s["accountant"]).invoice is None  # the RM's draft isn't Accounts' yet

    st = onb.save(db, acc.id, OnboardingInvoiceSave(**YES, submit=True), rm)
    assert st.invoice.status == "Requested" and not st.editable
    assert db.query(Notification).filter(Notification.user_id == s["accountant"].id,
                                         Notification.notification_type == "invoice_requested").count() == 1
    with pytest.raises(HTTPException) as e:  # it is with Accounts now
        onb.save(db, acc.id, OnboardingInvoiceSave(**YES), rm)
    assert e.value.status_code == 409


def test_also_while_awaiting_approval_but_not_once_dropped(db, setup):
    s = setup
    rm, acc = s["maker"], s["acc"]
    flow.submit(db, acc, rm)
    db.refresh(acc)
    assert acc.profile_status == wf.AWAITING
    assert onb.save(db, acc.id, OnboardingInvoiceSave(**YES, submit=True), rm).invoice.status == "Requested"
    acc.profile_status = wf.DROPPED
    db.commit()
    assert not onb.state(db, acc.id, rm).editable


def test_the_invoices_page_request_is_the_same_onboarding_invoice(db, setup):
    from app.schemas.invoice import InvoiceRequest
    s = setup
    rm, acc = s["maker"], s["acc"]
    inv = invoice_service.request_invoice(db, InvoiceRequest(account_id=acc.id, description="Onboarding services",
                                                             amount=Decimal("9000"), onboarding=True), rm)
    assert inv.kind == "Onboarding" and inv.status == "Requested"
    db.refresh(acc)
    assert acc.onboarding_invoice_wanted is True and onb.state(db, acc.id, rm).invoice.id == inv.id
    with pytest.raises(HTTPException) as e:  # one onboarding invoice per client
        invoice_service.request_invoice(db, InvoiceRequest(account_id=acc.id, description="Again", amount=Decimal("1"),
                                                           onboarding=True), rm)
    assert e.value.status_code == 409 and "already has an onboarding invoice" in e.value.detail


def test_accounts_answers_with_the_invoice_and_the_rm_is_told(db, setup):
    s = setup
    rm, acc = s["maker"], s["acc"]
    flow.submit(db, acc, rm)
    flow.approve_all(db, acc, s["checker"], s["approver"])
    st = onb.save(db, acc.id, OnboardingInvoiceSave(**YES, submit=True), rm)
    inv_id = st.invoice.id
    invoice_service.attach(db, inv_id, UploadFile(filename="INV-77.pdf", file=io.BytesIO(b"%PDF-1.4 invoice")), "Invoice", s["accountant"])
    invoice_service.raise_invoice(db, inv_id, InvoiceRaise(invoice_number="INV-77", invoice_date=date(2026, 11, 20),
                                                           currency="AED", amount=Decimal("15750")), s["accountant"])
    st = onb.state(db, acc.id, rm)
    assert (st.invoice.status, st.invoice.invoice_number, st.invoice.amount) == ("Raised", "INV-77", Decimal("15750"))
    assert db.query(Notification).filter(Notification.user_id == rm.id, Notification.notification_type == "invoice_raised").count() == 1


@pytest.mark.parametrize("change, message", [
    ({"client_amount": None}, "amount payable by the client"),
    ({"introducer_involved": None}, "introducer / referrer"),
    ({"introducer_amount": None}, "amount payable to the introducer"),
    ({"client_currency": "XYZ"}, "currency must be one of"),
])
def test_what_is_needed_before_it_goes_to_accounts(db, setup, change, message):
    s = setup
    flow.submit(db, s["acc"], s["maker"])
    flow.compliance_approve(db, s["acc"], s["checker"])
    with pytest.raises(HTTPException) as e:
        onb.save(db, s["acc"].id, OnboardingInvoiceSave(**{**YES, **change, "submit": True}), s["maker"])
    assert message in e.value.detail


def test_no_invoice_wanted_withdraws_a_draft(db, setup):
    rm, acc = setup["maker"], setup["acc"]
    onb.save(db, acc.id, OnboardingInvoiceSave(**YES), rm)
    st = onb.save(db, acc.id, OnboardingInvoiceSave(wanted=False), rm)
    assert st.wanted is False and st.invoice is None
    draft = db.query(Invoice).filter(Invoice.account_id == acc.id).one()
    assert draft.status == "Cancelled" and draft.cancel_reason  # kept on record, never deleted


def test_without_an_introducer_no_introducer_amount_is_kept(db, setup):
    rm, acc = setup["maker"], setup["acc"]
    st = onb.save(db, acc.id, OnboardingInvoiceSave(**{**YES, "introducer_involved": False}), rm)
    assert st.invoice.introducer_involved is False and st.invoice.introducer_amount is None


def test_view_only_users_cannot_change_it(db, setup, make_user, make_role):
    inquiry = make_user("Iris", business_role=make_role("Inquiry", ["read_only", "view.all_clients"]))
    with pytest.raises(HTTPException) as e:
        onb.save(db, setup["acc"].id, OnboardingInvoiceSave(**YES), inquiry)
    assert e.value.status_code == 403
    assert onb.state(db, setup["acc"].id, inquiry).editable is False


def test_a_dropped_client_takes_no_onboarding_invoice(db, setup):
    rm, acc = setup["maker"], setup["acc"]
    wf.change_status(db, acc, rm, "drop", None, "Client withdrew")
    with pytest.raises(HTTPException) as e:
        onb.save(db, acc.id, OnboardingInvoiceSave(**YES), rm)
    assert e.value.status_code == 409
