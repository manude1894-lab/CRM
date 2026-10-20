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
