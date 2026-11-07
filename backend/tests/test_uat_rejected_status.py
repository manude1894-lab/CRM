"""UAT 05-11-2026 (UAT-08): a rejected client shows as Rejected, with who, when and why (BRD §8, §19, §20)."""
import pytest

from app.schemas.account import AccountUpdate
from app.services import account_service, client_workflow_service as wf, dashboard_service, my_work_service, standard_reports_service
from tests import flow
from tests.helpers import auth

REASON = "Documents missing or incomplete"


@pytest.fixture()
def rejected(db, real_user, seed_master):
    seed_master("rejection_reason", [REASON])
    rm, mlro = real_user("Rel. Manager", "Kalyan"), real_user("MLRO", "Ritu")
    acc = flow.complete_client(db, rm)
    flow.submit(db, acc, rm)
    wf.reject(db, acc, mlro, REASON, "The passport copy is expired, please re-upload")
    return acc, rm, mlro


def test_rejected_by_compliance_shows_who_when_and_why(db, rejected):
    acc, _, _ = rejected
    assert acc.profile_status == "Rejected"
    r = wf.last_rejection(db, acc)
    assert (r["rejected_by"], r["level"], r["reason_code"]) == ("Ritu", "Compliance", REASON)
    assert "passport" in r["reason_text"] and r["rejected_at"] is not None


def test_rejected_by_the_approver_says_so(db, real_user, seed_master):
    seed_master("rejection_reason", [REASON])
    rm, mlro, approver = real_user("Rel. Manager"), real_user("MLRO"), real_user("Approver", "Final")
    acc = flow.complete_client(db, rm)
    flow.submit(db, acc, rm)
    flow.compliance_approve(db, acc, mlro)
    wf.reject(db, acc, approver, REASON, "Source of funds is not clear enough")
    assert acc.profile_status == "Rejected"
    assert (wf.last_rejection(db, acc)["level"], wf.last_rejection(db, acc)["rejected_by"]) == ("Approver", "Final")


def test_stays_rejected_while_corrected_then_resubmits(db, rejected):
    acc, rm, _ = rejected
    account_service.update_account(db, acc.id, AccountUpdate(license_activities="Corrected activities"), rm)
    db.refresh(acc)
    assert acc.profile_status == "Rejected"
    assert {a["action"]: a["allowed"] for a in wf.allowed_actions(db, acc, rm)}["submit"] is True
    flow.submit(db, acc, rm)
    assert acc.profile_status == "Awaiting Approval"
    assert wf.last_rejection(db, acc) is None
    assert wf.stage_of(wf.pending_request(db, acc.id)) == "Compliance"


def test_withdrawn_submission_is_not_rejected(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    flow.submit(db, acc, rm)
    wf.withdraw(db, acc, rm)
    assert acc.profile_status == "WIP"


def test_rejected_client_gets_no_client_id_from_saving(db, rejected):
    acc, rm, _ = rejected
    account_service.update_account(db, acc.id, AccountUpdate(license_activities="Still onboarding"), rm)
    db.refresh(acc)
    assert acc.client_id is None


def test_dashboard_and_my_work_show_it(db, rejected, real_user):
    acc, rm, _ = rejected
    dash = dashboard_service.build_dashboard(db, rm)
    assert [r["company_name"] for r in dash["rejected_clients"]] == [acc.company_name]
    assert dash["rejected_clients"][0]["rejected_by"] == "Ritu"
    assert dash["kpis"]["clients_in_progress"] == 1
    assert {s["status"]: s["count"] for s in dash["client_status_breakdown"]}["Rejected"] == 1
    work = {w["key"]: w["count"] for w in my_work_service.my_work(db, rm)}
    assert work["my_returned"] == 1 and work["my_in_progress"] == 0
    assert dashboard_service.build_dashboard(db, real_user("Rel. Manager", "Other"))["rejected_clients"] == []


def test_dashboard_api_returns_the_rejection(db, rejected, client):
    acc, rm, _ = rejected
    rows = client.get("/api/v1/dashboard", headers=auth(rm)).json()["rejected_clients"]
    assert [(r["company_name"], r["rejected_by"], r["level"]) for r in rows] == [(acc.company_name, "Ritu", "Compliance")]


def test_rejected_report_lists_it(db, rejected):
    acc, rm, _ = rejected
    rows = standard_reports_service.rejected_with_rm(db, rm)["rows"]
    assert [r[0] for r in rows] == [acc.company_name] and rows[0][3] == "Ritu"


def test_notifications_about_a_client_link_to_it(db, rejected):
    from app.models import Notification
    acc, rm, _ = rejected
    note = db.query(Notification).filter(Notification.user_id == rm.id, Notification.notification_type == "client_rejected").one()
    assert note.account_id == acc.id
