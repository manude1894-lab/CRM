"""UAT 05/06-11-2026 (UAT-07, 13, 25): pending approvals by level, and two people acting at once."""
import pytest
from fastapi import HTTPException

from app.services import account_service, client_workflow_service as wf, dashboard_service
from tests import flow
from tests.helpers import auth


@pytest.fixture()
def desk(real_user):
    return {"rm": real_user("Rel. Manager", "Rita"), "mlro": real_user("MLRO", "Ritu"), "co": real_user("CO", "Chris"),
            "approver": real_user("Approver", "Amir"), "admin": real_user("Rel. Manager", "Other")}


def _at_compliance(db, desk):
    acc = flow.complete_client(db, desk["rm"])
    flow.submit(db, acc, desk["rm"])
    flow.fill_cdd(db, acc, desk["mlro"])
    return acc


def test_second_checker_on_a_stale_screen_is_refused_with_a_clear_message(db, desk):
    acc = _at_compliance(db, desk)
    wf.approve(db, acc, desk["mlro"], "Checked", expected_stage="Compliance")
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, desk["co"], "Also checked", expected_stage="Compliance")
    assert e.value.status_code == 409 and "with the Approver" in e.value.detail
    assert wf.pending_request(db, acc.id).compliance_checker_id == desk["mlro"].id


def test_a_stale_click_can_not_give_the_final_approval(db, desk, make_user):
    from app.models import UserRole
    admin = make_user("Admin", role=UserRole.ADMIN)
    acc = _at_compliance(db, desk)
    wf.approve(db, acc, admin, "Compliance step", expected_stage="Compliance")
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, admin, "A second click", expected_stage="Compliance")
    assert e.value.status_code == 409
    assert acc.profile_status == "Awaiting Approval"


def test_reject_from_a_stale_screen_is_refused(db, desk, seed_master):
    seed_master("rejection_reason", ["Other"])
    acc = _at_compliance(db, desk)
    wf.approve(db, acc, desk["mlro"], "Checked", expected_stage="Compliance")
    with pytest.raises(HTTPException) as e:
        wf.reject(db, acc, desk["mlro"], "Other", "Changed my mind about this one", expected_stage="Compliance")
    assert e.value.status_code == 409


def test_client_list_says_which_level(db, desk, make_account):
    acc = _at_compliance(db, desk)
    other = make_account("Still With RM Ltd", spoc=desk["admin"], profile_status="WIP")
    stages = {a.id: a.approval_stage for a in account_service.list_accounts(db, desk["mlro"])[0]}
    assert stages[acc.id] == "Compliance" and stages[other.id] is None
    wf.approve(db, acc, desk["mlro"], "Checked")
    assert {a.id: a.approval_stage for a in account_service.list_accounts(db, desk["mlro"])[0]}[acc.id] == "Approver"


def test_client_list_api_returns_the_level(db, desk, client):
    acc = _at_compliance(db, desk)
    items = client.get("/api/v1/accounts", headers=auth(desk["mlro"])).json()["items"]
    assert next(a for a in items if a["id"] == acc.id)["approval_stage"] == "Compliance"


def test_dashboard_lists_pending_by_level(db, desk, client):
    acc = _at_compliance(db, desk)
    rows = client.get("/api/v1/dashboard", headers=auth(desk["mlro"])).json()["pending_approvals"]
    assert [(r["company_name"], r["level"], r["submitted_by"]) for r in rows] == [(acc.company_name, "Compliance", "Rita")]
    wf.approve(db, acc, desk["mlro"], "Checked")
    assert dashboard_service.build_dashboard(db, desk["mlro"])["pending_approvals"][0]["level"] == "Approver"


def test_an_rm_sees_the_level_of_their_own_cases_only(db, desk):
    _at_compliance(db, desk)
    assert len(dashboard_service.build_dashboard(db, desk["rm"])["pending_approvals"]) == 1
    assert dashboard_service.build_dashboard(db, desk["admin"])["pending_approvals"] == []


def test_actions_are_named_for_the_two_approvals(db, desk):
    acc = _at_compliance(db, desk)
    assert {a["action"]: a["label"] for a in wf.allowed_actions(db, acc, desk["mlro"])}["approve"] == "Compliance Approval"
    wf.approve(db, acc, desk["mlro"], "Checked")
    assert {a["action"]: a["label"] for a in wf.allowed_actions(db, acc, desk["approver"])}["approve"] == "Final Approval"
