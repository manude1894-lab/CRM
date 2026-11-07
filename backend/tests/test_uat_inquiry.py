"""UAT 05-11-2026 (UAT-17): Inquiry sees the whole CRM, including the queues, and changes nothing (BRD §13)."""
from app.services import client_workflow_service as wf
from tests import flow
from tests.helpers import auth


def test_inquiry_sees_cases_at_both_levels(db, real_user, client):
    rm, mlro, inquiry = real_user("Rel. Manager"), real_user("MLRO"), real_user("Inquiry")
    first = flow.complete_client(db, rm)
    flow.submit(db, first, rm)
    flow.compliance_approve(db, first, mlro)
    assert [r.id for r in wf.inbox(db, inquiry)] == [wf.pending_request(db, first.id).id]
    r = client.get("/api/v1/approvals", headers=auth(inquiry))
    assert r.status_code == 200 and r.json()[0]["stage"] == "Approver"


def test_inquiry_is_offered_no_action_and_the_server_refuses_them(db, real_user, client):
    rm, inquiry = real_user("Rel. Manager"), real_user("Inquiry")
    acc = flow.complete_client(db, rm)
    flow.submit(db, acc, rm)
    assert wf.allowed_actions(db, acc, inquiry) == []
    headers = auth(inquiry)
    for path, body in ((f"/api/v1/accounts/{acc.id}/approve", {"comment": "x"}),
                       (f"/api/v1/accounts/{acc.id}/withdraw", None),
                       ("/api/v1/prospects", {"company_name": "Should Fail Ltd"})):
        assert client.post(path, json=body, headers=headers).status_code == 403
    assert acc.profile_status == "Awaiting Approval"


def test_rm_still_has_no_queue(db, real_user, client):
    assert client.get("/api/v1/approvals", headers=auth(real_user("Rel. Manager"))).status_code == 403
