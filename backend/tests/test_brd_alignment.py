"""The CRM matches the BRD flow: Prospect → Client (RM → Compliance → Approver) → Service Requests.
No case pipeline; the dashboard, reminders and links are all built on the client."""
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models import Notification
from app.services import dashboard_service, scheduler_jobs
from app.schemas.invoice import InvoiceRequest
from app.services import invoice_service
from tests.test_api_p0 import auth, client  # noqa: F401  (fixture)


def test_no_case_or_non_brd_routes_remain():
    paths = {r.path for r in app.routes}
    for gone in ("/api/v1/cases", "/api/v1/cdd", "/api/v1/compliance", "/api/v1/action-points", "/api/v1/aml/catalog",
                 "/api/v1/jurisdictions", "/api/v1/document-templates", "/api/v1/reports/case-details",
                 "/api/v1/accounts/{account_id}/track-record", "/api/v1/prospects/{prospect_id}/convert"):
        assert not any(p == gone or p.startswith(gone + "/") for p in paths), gone
    for kept in ("/api/v1/prospects", "/api/v1/accounts", "/api/v1/approvals", "/api/v1/instructions", "/api/v1/invoices",
                 "/api/v1/activities", "/api/v1/countries", "/api/v1/reports/standard", "/api/v1/dashboard"):
        assert kept in paths, kept


def test_dashboard_snapshot_follows_the_client_lifecycle(db, make_user, make_account):
    rm = make_user("Rita RM")
    make_account(name="Prep Co", spoc=rm, profile_status="WIP")
    make_account(name="Review Co", spoc=rm, profile_status="Awaiting Approval")
    make_account(name="Live Co", spoc=rm, profile_status="Active", risk_rating="High",
                 next_aml_review_date=date.today() + timedelta(days=10))
    d = dashboard_service.build_dashboard(db, rm)
    assert (d["kpis"]["clients_in_progress"], d["kpis"]["clients_awaiting_approval"], d["kpis"]["clients_active"]) == (1, 1, 1)
    assert [s["status"] for s in d["client_status_breakdown"]] == [
        "New", "WIP", "Awaiting Approval", "Approved", "Active", "Inactive", "Marked for Exit", "Exited"]
    assert [r["company_name"] for r in d["aml_reviews_due"]] == ["Live Co"]
    [row] = [p for p in d["portfolio_by_rm"] if p["name"] == "Rita RM"]
    assert (row["total"], row["in_progress"], row["active"]) == (3, 2, 1)


def test_dashboard_is_limited_to_visible_clients(db, make_user, make_account):
    rm, other = make_user("Rita"), make_user("Otto")
    make_account(spoc=other, profile_status="Active")
    assert dashboard_service.build_dashboard(db, rm)["kpis"]["clients_active"] == 0


@pytest.fixture()
def sweep_db(engine, monkeypatch):
    """The daily sweep opens its own sessions; point them at the test database."""
    monkeypatch.setattr(scheduler_jobs, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False))


def test_aml_review_reminder_goes_to_rm_and_compliance_once(db, sweep_db, make_user, make_account, make_role):
    rm = make_user("Rita RM")
    mlro = make_user("Mia MLRO", business_role=make_role("MLRO", ["client.approve"]))
    make_account(name="Due Co", spoc=rm, profile_status="Active", next_aml_review_date=date.today() + timedelta(days=30))
    make_account(name="Later Co", spoc=rm, profile_status="Active", next_aml_review_date=date.today() + timedelta(days=45))
    make_account(name="Prep Co", spoc=rm, profile_status="WIP", next_aml_review_date=date.today())
    scheduler_jobs.check_aml_reviews_due()
    scheduler_jobs.check_aml_reviews_due()  # deduped while unread
    notes = db.query(Notification).all()
    assert sorted(n.user_id for n in notes) == sorted([rm.id, mlro.id])
    assert all("Due Co" in n.message and "due in 30 days" in n.message for n in notes)


def test_expired_licence_reminds_the_anchor_rm(db, sweep_db, make_user, make_account):
    rm = make_user("Rita RM")
    make_account(name="Lapsed Co", spoc=rm, profile_status="Approved", license_expiry_date=date.today() - timedelta(days=3))
    scheduler_jobs.check_licences_expiring()
    [n] = db.query(Notification).all()
    assert n.user_id == rm.id and "has expired" in n.message and n.account_id is not None


def test_invoice_belongs_to_a_client(db, make_user, make_account, make_role):
    rm = make_user()
    acc = make_account(spoc=rm, profile_status="Active")
    inv = invoice_service.request_invoice(db, InvoiceRequest(account_id=acc.id, description="Onboarding fee", amount=1000), rm)
    assert inv.account_id == acc.id
    with pytest.raises(HTTPException):
        invoice_service.request_invoice(db, InvoiceRequest(account_id=99999, description="Nobody", amount=1), rm)


def test_countries_master(client, make_user):
    admin, rm = make_user("Ada", role="admin"), make_user("Rita")
    r = client.post("/api/v1/countries", json={"name": "Atlantis"}, headers=auth(admin))
    assert r.status_code == 201 and set(r.json()) == {"id", "name"}
    assert client.post("/api/v1/countries", json={"name": "Lemuria"}, headers=auth(rm)).status_code == 403
    assert "Atlantis" in {c["name"] for c in client.get("/api/v1/countries", headers=auth(rm)).json()}


def test_read_only_users_are_offered_no_actions(db, make_user, make_account, make_role):
    from app.services import amendment_service, client_workflow_service as wf
    inquiry = make_user("Ines Inquiry", business_role=make_role("Inquiry", ["read_only", "view.all_clients"]))
    acc = make_account(spoc=make_user("Rita"), profile_status="Active")
    assert wf.allowed_actions(db, acc, inquiry) == []
    assert amendment_service.view(db, acc, inquiry)["actions"] == []


def test_completing_a_request_sets_the_completion_date(db, make_user, make_account, seed_master):
    from app.schemas.instruction import InstructionCreate, InstructionUpdate
    from app.services import instruction_service
    rm = make_user()
    acc = make_account(spoc=rm, profile_status="Active")
    sr = instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Other",
                                                                      other_description="Courier"), rm)
    instruction_service.update_instruction(db, sr.id, InstructionUpdate(status="Completed"), rm)
    assert sr.date_completed == date.today()


def test_import_of_existing_clients(db, make_user):
    from app.models import Account
    from app.schemas.account import AccountImportRow
    from app.services import account_service
    admin = make_user("Ada", role="admin")
    rows = [
        AccountImportRow(company_name="Old Client Ltd", anchor_entity="TABL", risk_rating="high", cdd_completion_date=date(2026, 1, 15),
                         kyc_verified_by="Kalyan", client_category="Existing", contact_email="info@old.ae", is_one_time_service=False),
        AccountImportRow(company_name="Leaving Ltd", anchor_entity="TABL", profile_status="marked for exit"),
        AccountImportRow(company_name="Typo Ltd", profile_status="Actve"),
        AccountImportRow(company_name="Half Way Ltd", profile_status="WIP"),
        AccountImportRow(company_name="Odd Risk Ltd", risk_rating="Extreme"),
    ]
    preview = account_service.import_accounts(db, admin, rows, dry_run=True)
    assert [r.status for r in preview] == ["ok", "ok", "error", "error", "error"]
    assert "Actve" in preview[2].message and "Extreme" in preview[4].message
    assert db.query(Account).count() == 0  # the preview writes nothing

    account_service.import_accounts(db, admin, rows, dry_run=False)
    old = db.query(Account).filter(Account.company_name == "Old Client Ltd").one()
    assert (old.profile_status, old.risk_rating, old.client_id) == ("Active", "High", "TABL/00001")
    assert old.next_aml_review_date == date(2027, 1, 15)  # High risk: 1 year after the CDD date
    assert (old.kyc_verified_by, old.client_category, old.contact_email, old.is_one_time_service) == ("Kalyan", "Existing", "info@old.ae", False)
    assert db.query(Account).filter(Account.company_name == "Leaving Ltd").one().profile_status == "Marked for Exit"
    assert db.query(Account).count() == 2


def test_prospect_contact_email_must_be_valid():
    from pydantic import ValidationError
    from app.schemas.prospect import ProspectCreate, ProspectUpdate
    assert ProspectCreate(company_name="S T Krishna's new co.", contact_email=" stkrishna1@yahoo.co.in ").contact_email == "stkrishna1@yahoo.co.in"
    assert ProspectCreate(company_name="No Email Co", contact_email="").contact_email is None
    for bad in ("stkrishna1@yahoo", "stkrishna1.yahoo.co.in", "a b@c.com"):
        with pytest.raises(ValidationError):
            ProspectCreate(company_name="x", contact_email=bad)
        with pytest.raises(ValidationError):
            ProspectUpdate(contact_email=bad)
