"""No hard delete (Triam: "no delete option in a CRM"; BRD §2 / §13 — every material change is recorded).
Records are cancelled or marked removed with a reason and stay in the database."""
import io
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, UploadFile

from app.main import app
from app.models import AccountParty, Activity, Document, Instruction, Invoice
from app.schemas.account_party import AccountPartyCreate
from app.schemas.instruction import InstructionCreate
from app.schemas.invoice import InvoiceRequest
from app.services import (account_party_service, activity_service, amendment_service as amend,
                          document_service, instruction_service, invoice_service)
from tests.test_api_p0 import auth, client  # noqa: F401  (fixture)
from tests.test_p2_workflow import complete_client, people  # noqa: F401  (fixture)
from tests.test_p3_compliance import approved_client


def test_no_delete_endpoints_remain():
    """DELETE is used only by the support account to remove a user login."""
    deletes = sorted(r.path for r in app.routes if "DELETE" in getattr(r, "methods", set()))
    assert deletes == ["/api/v1/users/{user_id}"]


def test_service_request_is_cancelled_not_deleted(db, make_user, make_account, seed_master):
    seed_master("service_request_type", ["Change of Address"])
    rm = make_user()
    acc = make_account(spoc=rm, profile_status="Active")
    sr = instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Change of Address"), rm)
    instruction_service.cancel_instruction(db, sr.id, "Client withdrew the request", rm)
    row = db.get(Instruction, sr.id)
    assert row.status == "Dropped" and row.cancel_reason == "Client withdrew the request"
    with pytest.raises(HTTPException):
        instruction_service.cancel_instruction(db, sr.id, "again", rm)


def test_invoice_is_cancelled_with_reason_and_paid_ones_cannot_be(db, make_user, make_role, make_account):
    rm = make_user()
    accounts = make_user(business_role=make_role("Accountant", ["invoice.manage", "view.all_clients"]))
    acc = make_account(spoc=rm)
    req = lambda: invoice_service.request_invoice(db, InvoiceRequest(  # noqa: E731
        account_id=acc.id, description="Formation", amount=Decimal("1000"), currency="AED"), rm)
    inv = req()
    invoice_service.cancel_invoice(db, inv.id, "Raised in error", rm)  # requester may cancel an open request
    assert db.get(Invoice, inv.id).status == "Cancelled"
    paid = req()
    paid.status = "Paid"
    db.commit()
    with pytest.raises(HTTPException) as e:
        invoice_service.cancel_invoice(db, paid.id, "Try to cancel", accounts)
    assert "paid" in e.value.detail


def test_activity_is_cancelled(db, make_user, make_account):
    rm = make_user()
    acc = make_account(spoc=rm)
    act = Activity(activity_uid="ACT-9001", company_name=acc.company_name, activity_date=date.today(),
                   activity_type="Visit Report", summary="Visit", owner_id=rm.id, account_id=acc.id)
    db.add(act)
    db.commit()
    activity_service.cancel_activity(db, act.id, "Meeting called off", rm)
    assert db.get(Activity, act.id).cancel_reason == "Meeting called off"


def test_party_removed_before_submission_is_kept_on_record(db, people):
    maker = people["maker"]
    acc = complete_client(db, maker)
    extra = account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role="Director", full_name="Wrong Person", nationality="India", country_of_residence="India"), maker)
    account_party_service.remove_party(db, extra.id, "Added to the wrong client", maker)
    row = db.get(AccountParty, extra.id)
    assert row is not None and row.removed_reason == "Added to the wrong client" and row.removed_by_id == maker.id
    assert extra.id not in {p.id for p in account_party_service.list_parties(db, acc.id)}
    removed = account_party_service.list_removed_parties(db, acc.id, maker)
    assert [(r["full_name"], r["removed_reason"]) for r in removed] == [("Wrong Person", "Added to the wrong client")]
    with pytest.raises(HTTPException):
        account_party_service.remove_party(db, extra.id, "again", maker)


def test_party_removed_by_amendment_is_kept_on_record(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = approved_client(db, people)
    jane = acc.parties[0]
    amend.start(db, acc, maker)
    account_party_service.remove_party(db, jane.id, "Shares transferred to Omar", maker)
    account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role="Shareholder", full_name="Omar New", nationality="United Arab Emirates", country_of_residence="United Arab Emirates",
        mobile_country_code="+971", mobile_number="509999999", email="omar@example.com",
        effective_ownership_percent=Decimal("100")), maker)
    assert db.get(AccountParty, jane.id).removed_at is None  # staged only
    amend.submit(db, acc, maker)
    amend.approve(db, acc, checker)
    db.expire_all()
    jane_row = db.get(AccountParty, jane.id)
    assert jane_row.removed_at is not None and jane_row.removed_reason == "Shares transferred to Omar"
    assert [p.full_name for p in acc.parties] == ["Omar New"]


def test_document_removal_keeps_the_file(db, people, seed_master):
    seed_master("document_category", ["PASSPORT"])
    maker = people["maker"]
    acc = complete_client(db, maker)
    f = UploadFile(file=io.BytesIO(b"%PDF-1.4 test"), filename="passport.pdf", headers={"content-type": "application/pdf"})
    doc = document_service.create_for_account(db, acc.id, f, "PASSPORT", maker)
    document_service.delete(db, doc.id, maker, "Wrong person's passport")
    row = db.get(Document, doc.id)
    assert row is not None and row.content and row.removed_reason == "Wrong person's passport"
    assert document_service.client_folder(db, acc.id, maker)["documents"] == []


def test_audit_log_can_be_exported(client, make_user, make_role):
    admin = make_user(role="admin")
    client.post("/api/v1/departments", json={"name": "Risk"}, headers=auth(admin))
    r = client.get("/api/v1/audit/export", headers=auth(admin))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("Date and time (UAE),User,Action") and "Risk" in text
    rm = make_user()
    assert client.get("/api/v1/audit/export", headers=auth(rm)).status_code == 403


def test_last_active_admin_cannot_be_deactivated(client, make_user):
    admin = make_user(role="admin")
    r = client.patch(f"/api/v1/users/{admin.id}", json={"is_active": False}, headers=auth(admin))
    assert r.status_code == 400 and "only active administrator" in r.json()["detail"]
    other = make_user(role="admin")
    assert client.patch(f"/api/v1/users/{other.id}", json={"is_active": False}, headers=auth(admin)).status_code == 200
